"""Subscription-backed language-model adapter: `codex exec` (ChatGPT sign-in) inside a jail (confine.py): bubblewrap on
Linux, Seatbelt on macOS.

* No API key is used or read. OPENAI_API_KEY and CODEX_API_KEY are removed from the environment by the jail.
* The jail (codex_adapter/codex_jail.sh) exposes only read-only system directories, the Codex binary, the login file
  (bound, never read or copied here), a private tmpfs CODEX_HOME and one per-call directory. The RNPLens repository,
  references, answer keys and manuscript do not exist inside it. Codex's own shell sandbox cannot start inside the
  jail, so model-generated shell commands fail closed.
* Every call records the effective model and reasoning effort read from Codex's own session log (turn_context), token
  counts, the plan's rate-limit usage and the credits balance. A call is refused when the plan's usage reaches the
  guard threshold, and the run stops if the credits balance changes (no paid credits may be drawn)."""
import glob
import hashlib
import json
import os
import subprocess
import time

from . import confine

CONFIG = {"provider": "codex-cli (ChatGPT subscription)", "model": "gpt-6.1-sol", "reasoning_effort": "medium",
          "sandbox": "read-only (inside bubblewrap jail)", "approval_policy": "never", "ignore_user_config": True,
          "timeout_s": 900, "usage_guard_percent": 85.0}
_PKG = os.path.dirname(os.path.abspath(__file__))


def default_jail():
    """The jail script shipped with THIS installation for this operating system (confine.py): the packaged copy
    (rnplens_assistant/codex_adapter/), else the source checkout's assistant/codex_adapter/. Never a path of another
    installation (0.4: the earlier default pointed at the frozen evaluation's installation)."""
    return confine.default_jail(_PKG)


def default_calls_root():
    """Per-user call records outside any project: ~/.rnplens/codex_calls (RNPLENS_CODEX_CALLS overrides). The credits
    baseline of a run lives here, so a default may never be a shared or frozen evaluation folder."""
    return os.path.join(os.path.expanduser("~"), ".rnplens", "codex_calls")


# Launch boundary (0.4): the confinement backend is the jail shipped with THIS installation for this operating system.
# It is never chosen from the environment: RNPLENS_CODEX_JAIL is refused unless it names this same jail, and the
# shipped jail's process receives only the variables in JAIL_ENV_KEEP plus a fixed PATH (no BASH_ENV, exported shell
# functions or PATH entries of the caller can run before or instead of it). Only code can substitute another jail
# (codex_llm.JAIL = ..., as the test harnesses and the frozen FOLLOWUP_SUITE_v1 do); such a jail keeps the caller's
# environment, which those harnesses use to script their fake Codex.
APPROVED_JAIL = default_jail()
JAIL = APPROVED_JAIL
JAIL_PATH = "/usr/bin:/bin"
JAIL_ENV_KEEP = ("HOME", "CODEX_HOME", "RNPLENS_CODEX_BIN")
CONFIG["sandbox"] = confine.sandbox_label(JAIL)          # Linux: unchanged ("... bubblewrap jail")
# code_mode_host stays enabled: in Codex 0.159.3 MCP tool calls are made through it (required for arm G; kept identical in R)
# identical in both arms: no shell, no code execution, no browser/computer use, no image viewer, no web search
_OFF = ["shell_tool", "unified_exec", "browser_use", "browser_use_external", "in_app_browser", "computer_use", "view_image",
        "multi_agent", "image_generation", "goals", "apps", "plugins", "remote_plugin", "sleep_tool",
        "tool_suggest", "skill_search", "skill_mcp_dependency_install", "hooks", "worktrees", "workspace_dependencies",
        "realtime_conversation", "fast_mode"]
HARDENING = [x for f in _OFF for x in ("--disable", f)] + ["-c", 'web_search="disabled"']
CALLS_ROOT = os.environ.get("RNPLENS_CODEX_CALLS") or default_calls_root()


class UsageGuard(Exception):
    pass


class JailRefused(RuntimeError):
    """The confinement backend is not the one shipped with this installation: nothing is started or sent."""


def refuse_unapproved_jail(environ=None):
    """Raise JailRefused when RNPLENS_CODEX_JAIL names anything other than this installation's own jail."""
    e = os.environ if environ is None else environ
    o = e.get("RNPLENS_CODEX_JAIL")
    if o and os.path.realpath(o) != os.path.realpath(APPROVED_JAIL):
        raise JailRefused("RNPLENS_CODEX_JAIL=%s is not the jail shipped with this installation (%s): refused, nothing "
                          "was started or sent; unset RNPLENS_CODEX_JAIL" % (o, APPROVED_JAIL))


def jail_environ(environ=None):
    """The complete environment of the jail process: JAIL_ENV_KEEP from the caller, and PATH=JAIL_PATH."""
    e = os.environ if environ is None else environ
    out = {k: e[k] for k in JAIL_ENV_KEEP if e.get(k)}
    out["PATH"] = JAIL_PATH
    return out


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def read_session(call_dir):
    """Effective model/effort, token usage and rate limits from Codex's own rollout file."""
    out = {"model_returned": None, "effort_returned": None, "tokens": None, "rate_limits": None, "cli_version": None}
    for f in sorted(glob.glob(os.path.join(call_dir, ".codex_sessions", "**", "*.jsonl"), recursive=True)):
        for line in open(f):
            try:
                e = json.loads(line)
            except Exception:
                continue
            p = e.get("payload") or {}
            if e.get("type") == "turn_context":
                out["model_returned"], out["effort_returned"] = p.get("model"), p.get("effort")
            elif e.get("type") == "session_meta":
                out["cli_version"] = p.get("cli_version")
            elif e.get("type") == "event_msg" and p.get("type") == "token_count":
                if p.get("info"):
                    out["tokens"] = p["info"].get("total_token_usage")
                if p.get("rate_limits"):
                    out["rate_limits"] = p["rate_limits"]
    return out


class CodexClient:
    def __init__(self, run_tag, config=None, mcp=None):
        refuse_unapproved_jail()                 # launch boundary: before any folder is created
        self.config = dict(CONFIG, **(config or {}))
        base = os.path.join(CALLS_ROOT, "%s_%s_%d" % (run_tag, time.strftime("%Y%m%dT%H%M%S"), os.getpid()))
        root, n = base, 1
        while True:     # unique call folder: two clients with one tag in one second must not collide (0.4 fix)
            try:
                os.makedirs(root)
                break
            except FileExistsError:
                n += 1
                root = "%s_%d" % (base, n)
        self.root = root
        self.calls, self.last_limits, self.credits0 = [], None, None
        self.mcp = mcp          # optional {"relay": path, "socket": path} for the general-agent arm

    def _guard(self):
        rl = self.last_limits
        if not rl:
            return
        if rl.get("rate_limit_reached_type"):
            raise UsageGuard("plan rate limit reached (%s)" % rl.get("rate_limit_reached_type"))
        for w in ("primary", "secondary"):
            if rl.get(w) and (rl[w].get("used_percent") or 0) >= self.config["usage_guard_percent"]:
                raise UsageGuard("plan usage %.1f%% in the %s window reached the %.0f%% guard" % (
                    rl[w]["used_percent"], w, self.config["usage_guard_percent"]))
        wk = self.config.get("weekly_guard_percent")     # optional, stricter guard on the weekly window (0.4 follow-up suite)
        if wk is not None:
            for w in ("primary", "secondary"):
                x = rl.get(w) or {}
                if (x.get("window_minutes") or 0) >= 7 * 24 * 60 and (x.get("used_percent") or 0) >= wk:
                    raise UsageGuard("weekly plan usage %.1f%% reached the %.0f%% guard" % (x["used_percent"], wk))
        bal = (rl.get("credits") or {}).get("balance")
        base = os.path.join(CALLS_ROOT, "credits_baseline.json")
        if self.credits0 is None:
            if not os.path.exists(base):
                json.dump({"balance": bal, "recorded": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, open(base, "w"))
            self.credits0 = json.load(open(base))["balance"]
        if bal != self.credits0:
            raise UsageGuard("credits balance changed (%s -> %s): stopping so that no paid credits are drawn" % (self.credits0, bal))

    def new_call_dir(self, kind):
        cd = os.path.join(self.root, "%03d_%s" % (len(self.calls) + 1, kind))
        os.makedirs(cd)
        return cd

    def run(self, kind, prompt, schema, extra_args=(), call_files=None, call_dir=None):
        refuse_unapproved_jail()                 # launch boundary, checked again at every call
        if not os.path.isfile(JAIL):
            raise JailRefused("the jail %s does not exist: refused, nothing was started or sent" % JAIL)
        self._guard()
        cd = call_dir or self.new_call_dir(kind)
        json.dump(schema, open(os.path.join(cd, "schema.json"), "w"))
        for name, src in (call_files or {}).items():
            open(os.path.join(cd, name), "wb").write(open(src, "rb").read())
        view = confine.call_view(JAIL, cd)        # the call folder as Codex sees it: /work (Linux jail) or its real path (Seatbelt)
        args = [os.path.abspath(JAIL), cd, "--", "exec", "--skip-git-repo-check", "--json", "-s", "read-only", "-m", self.config["model"],
                "-c", 'model_reasoning_effort="%s"' % self.config["reasoning_effort"], "--output-schema", view + "/schema.json",
                "-o", view + "/last.json"]
        if self.config["ignore_user_config"]:
            args.insert(5, "--ignore-user-config")
        args += HARDENING + list(extra_args) + ["-"]
        t0 = time.time(); err = None; out = None
        try:
            p = subprocess.run(args, input=prompt, capture_output=True, text=True, timeout=self.config["timeout_s"], cwd=cd,
                               env=jail_environ() if os.path.realpath(JAIL) == os.path.realpath(APPROVED_JAIL) else None)
            open(os.path.join(cd, "events.jsonl"), "w").write(p.stdout)
            open(os.path.join(cd, "stderr.txt"), "w").write(p.stderr[-20000:])
            if p.returncode != 0:
                err = "codex exec exit %d: %s" % (p.returncode, p.stderr.strip()[-300:])
            else:
                out = json.load(open(os.path.join(cd, "last.json")))
        except subprocess.TimeoutExpired:
            err = "codex exec exceeded %d s" % self.config["timeout_s"]
        except Exception as ex:
            err = "%s: %s" % (type(ex).__name__, str(ex)[:300])
        s = read_session(cd)
        if s["rate_limits"]:
            self.last_limits = s["rate_limits"]
        tok = s["tokens"] or {}
        rl = s["rate_limits"] or {}
        self.calls.append({"kind": kind, "call_dir": cd, "prompt_sha256": sha(prompt), "schema_sha256": sha(json.dumps(schema, sort_keys=True)),
                           "model_requested": self.config["model"], "model_returned": s["model_returned"],
                           "effort_requested": self.config["reasoning_effort"], "effort_returned": s["effort_returned"], "cli_version": s["cli_version"],
                           "latency_s": round(time.time() - t0, 2), "input_tokens": tok.get("input_tokens"), "cached_input_tokens": tok.get("cached_input_tokens"),
                           "output_tokens": tok.get("output_tokens"), "reasoning_tokens": tok.get("reasoning_output_tokens"),
                           "plan_used_percent": (rl.get("primary") or {}).get("used_percent"), "plan_window_minutes": (rl.get("primary") or {}).get("window_minutes"),
                           "credits_balance": (rl.get("credits") or {}).get("balance"), "plan_type": rl.get("plan_type"), "error": err})
        if s["model_returned"] and s["model_returned"] != self.config["model"]:
            err = (err or "") + " model mismatch: requested %s, Codex ran %s" % (self.config["model"], s["model_returned"])
        if err:
            raise RuntimeError(err)
        self._guard()
        return out

    def structured(self, kind, system, user, schema_name, schema):
        return self.run(kind, system + "\n\n---\n\n" + user, schema)
