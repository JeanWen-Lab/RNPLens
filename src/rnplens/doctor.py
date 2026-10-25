"""``rnplens doctor [--agent] [--project P] [--out O] [--json] [--save]``: check this installation.

Every check reports READY, ACTION REQUIRED or UNSUPPORTED with a one-line remedy. The doctor installs nothing,
changes no setting, signs nobody in or out, never reads Codex's login file, and writes nothing unless --save is
given, in which case it writes exactly one file, <out>/doctor.json.

Checks: Python version; RNPLens version and the qualification state of its components (the same internals as
``rnplens provenance``: installed components and the pinned SHA-256 of every frozen source); the capability
registry; platform (Linux and macOS: toolkit and assistant, each with its own confinement of the Codex process;
anything else UNSUPPORTED); required and optional dependencies; read access to --project and write
access to --out; the vendored Mol* viewer files against their recorded SHA-256. With --agent also: the Codex CLI and
its version, the ChatGPT sign-in state (the status line only), whether the tested model is offered to this account,
the confinement mechanism (Linux: bubblewrap and unprivileged user namespaces, a harmless ``bwrap --ro-bind / / true``
probe; macOS: Seatbelt, a harmless ``sandbox-exec`` probe), the Codex jail script of this platform (its own no-model
self-probe),
and whether the language-model-dependent function (``rnplens assist --nl``) is enabled."""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys

from . import __version__

READY, ACTION, UNSUPPORTED = "READY", "ACTION REQUIRED", "UNSUPPORTED"
TESTED_CODEX = "0.159.3"
TESTED_MODEL = "gpt-6.1-sol"
NOTICE = ("Codex mode uses your own ChatGPT account and its usage allowance; RNPLens cannot guarantee that "
          "supplemental credits will not be used once the included allowance is exhausted; no API key is required "
          "or used.")
REQUIRED = [("DockQ", "2.1.3"), ("gemmi", "0.6.5"), ("biopython", "1.84"), ("numpy", "1.26.4"), ("scipy", "1.13.1")]
OPTIONAL = [("matplotlib", "3.8", "images in the HTML pages of Report and analyse")]
PY_RANGE = ((3, 10), (3, 12))
QUALIFIED_TOOLKIT = {("Linux", "x86_64"), ("Darwin", "arm64")}
NOT_VERIFIED = "not verified"
SECRET_ENV = ("OPENAI_API_KEY", "CODEX_API_KEY")

CAPABILITIES = [
    {"id": "setup_check", "menu": None, "label": "Setup check (rnplens doctor)", "status": "DESCRIPTIVE", "needs": [],
     "call": "rnplens.doctor:capability",
     "limits": "Describes this installation at the time of the check; it changes nothing and verifies no scientific result."},
]


class Env:
    """Everything the doctor observes about the system goes through this object, so tests can replace it."""
    environ = os.environ

    def system(self):
        return platform.system()

    def machine(self):
        m = platform.machine()
        return {"amd64": "x86_64", "aarch64": "arm64"}.get(m.lower(), m)

    def python_version(self):
        return tuple(sys.version_info[:3])

    def which(self, name):
        return shutil.which(name)

    def isfile(self, p):
        return os.path.isfile(p)

    def approved_jail(self):
        """The jail shipped with this installation for this system (the only backend the assistant launches)."""
        from rnplens_assistant import codex_llm
        return codex_llm.confine.default_jail(codex_llm._PKG, self.system())

    def isdir(self, p):
        return os.path.isdir(p)

    def exists(self, p):
        return os.path.exists(p)

    def access(self, p, mode):
        return os.access(p, mode)

    def dist_version(self, name):
        from importlib import metadata
        try:
            return metadata.version(name)
        except metadata.PackageNotFoundError:
            return None

    def run(self, argv, timeout=20):
        """(returncode, stdout, stderr). API-key variables are removed from the child's environment."""
        env = {k: v for k, v in os.environ.items() if k not in SECRET_ENV}
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL, env=env)
        return p.returncode, p.stdout, p.stderr


def _c(cid, label, status, detail, remedy="", group="installation"):
    return {"id": cid, "check": label, "status": status, "detail": detail, "remedy": remedy if status != READY else "",
            "group": group}


_SECRET_PATTERNS = [r"\bsk-[A-Za-z0-9_\-]{8,}", r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+(\.[A-Za-z0-9_\-]+)?",
                    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", r"\b[A-Za-z0-9_\-+/=]{24,}\b"]


def redact(text, limit=120):
    """One line, with anything that could be a token, key or e-mail address replaced. Used on every line of external
    tool output the doctor reports."""
    line = " ".join(str(text).split())
    for pat in _SECRET_PATTERNS:
        line = re.sub(pat, "<redacted>", line)
    return line[:limit]


# ---------------------------------------------------------------- installation checks

def check_python(env):
    v = env.python_version()
    s = "%d.%d.%d" % v
    if PY_RANGE[0] <= v[:2] <= PY_RANGE[1]:
        return _c("python", "Python", READY, s)
    return _c("python", "Python", UNSUPPORTED, "%s (RNPLens supports 3.10 to 3.12)" % s, "use Python 3.10, 3.11 or 3.12")


def check_rnplens(env):
    from . import provenance
    commit = provenance.code_commit()
    return _c("rnplens", "RNPLens", READY, "rnplens %s%s" % (__version__, "; source commit %s" % commit if commit else ""))


def check_components(env):
    """The same internals as `rnplens provenance`: installed components and the frozen-source pins."""
    try:
        from rnpbench_core import provenance as cprov, frozen_loader
        comps = cprov.components()
        missing = [k for k, v in comps.items() if not v.get("installed")]
        man = frozen_loader.verify_sources()
        n = len(man["files"])
    except Exception as ex:          # FrozenIntegrityError, ImportError, unreadable manifest
        return _c("components", "Qualified components", ACTION, redact("%s: %s" % (type(ex).__name__, ex), 200),
                  "reinstall RNPLens from its release; the qualified component code must be unchanged")
    if missing:
        return _c("components", "Qualified components", ACTION, "not installed: %s" % ", ".join(missing),
                  "reinstall RNPLens from its release")
    return _c("components", "Qualified components", READY,
              "%d components installed; all %d frozen sources match their pinned SHA-256" % (len(comps), n))


def check_capabilities(env):
    from . import capabilities
    offered, missing = capabilities.available()
    by = {}
    for c in offered:
        by[c["status"]] = by.get(c["status"], 0) + 1
    shown = ", ".join("%d %s" % (by[k], k) for k in ("QUALIFIED", "DESCRIPTIVE", "EXPERIMENTAL") if by.get(k)) or "none"
    return _c("capabilities", "0.4 functions", READY,
              "offered: %s; not available: %d (listed with reasons by rnplens assist)" % (shown, len(missing)))


def platform_status(env):
    """(toolkit_check, assistant_check)."""
    sysname, mach = env.system(), env.machine()
    where = "%s %s" % (sysname, mach)
    if (sysname, mach) in QUALIFIED_TOOLKIT:
        if sysname == "Darwin":
            msg = ("%s: toolkit runs; not fully qualified for 0.4 (one known numerical parity difference; "
                   "Linux x86_64 is the tested interactive environment)" % where)
        else:
            msg = "%s is a qualified platform (the tested interactive environment for 0.4)" % where
        tk = _c("platform_toolkit", "Platform (toolkit)", READY, msg)
    elif sysname in ("Linux", "Darwin"):
        tk = _c("platform_toolkit", "Platform (toolkit)", ACTION, "%s is not one of the qualified platforms (Linux x86_64, macOS arm64)" % where,
                "run 'rnplens selftest' and keep its output with your results before relying on numbers")
    else:
        tk = _c("platform_toolkit", "Platform (toolkit)", UNSUPPORTED, "%s is not supported" % where, "use Linux x86_64 or macOS arm64")
    if sysname == "Linux":
        asst = _c("platform_assistant", "Platform (natural-language assistant)", READY, "Linux: supported (subject to the --agent checks)", group="agent")
    elif sysname == "Darwin":
        asst = _c("platform_assistant", "Platform (natural-language assistant)", READY,
                  "macOS: supported (subject to the --agent checks; the Codex process runs under Seatbelt)", group="agent")
    else:
        asst = _c("platform_assistant", "Platform (natural-language assistant)", UNSUPPORTED, "%s is not supported" % sysname,
                  "use Linux", group="agent")
    return tk, asst


def check_dependencies(env):
    out = []
    for name, want in REQUIRED:
        got = env.dist_version(name)
        if got is None:
            out.append(_c("dep_" + name, "Dependency %s" % name, ACTION, "not installed (required, qualified with %s)" % want,
                          "install it: pip install '%s==%s'" % (name, want)))
        elif got != want:
            out.append(_c("dep_" + name, "Dependency %s" % name, ACTION, "%s installed; RNPLens was qualified with %s" % (got, want),
                          "install the qualified version: pip install '%s==%s'" % (name, want)))
        else:
            out.append(_c("dep_" + name, "Dependency %s" % name, READY, got))
    for name, minimum, purpose in OPTIONAL:
        got = env.dist_version(name)
        if got is None:
            c = _c("dep_" + name, "Optional %s" % name, ACTION, "not installed (optional: %s; no scientific result "
                   "depends on it)" % purpose, "only if you want images: pip install 'rnplens[html]'")
        else:
            c = _c("dep_" + name, "Optional %s" % name, READY, "%s (%s)" % (got, purpose))
        c["optional"] = True        # policy: an optional component that is missing is shown, never a failure
        out.append(c)
    return out


def check_project(env, project):
    if not env.isdir(project):
        return _c("project", "Project folder", ACTION, "%s is not a folder" % project, "give the folder written by 'rnplens import'")
    if not env.access(project, os.R_OK | os.X_OK):
        return _c("project", "Project folder", ACTION, "%s is not readable" % project, "fix the folder permissions")
    m = os.path.join(project, "manifest.json")
    if not env.isfile(m) or not env.access(m, os.R_OK):
        return _c("project", "Project folder", ACTION, "%s has no readable manifest.json" % project, "give the folder written by 'rnplens import'")
    return _c("project", "Project folder", READY, "%s readable" % project)


def check_out(env, out):
    if env.exists(out):
        if not env.isdir(out):
            return _c("out", "Output folder", ACTION, "%s exists and is not a folder" % out, "choose another output path")
        if not env.access(out, os.W_OK | os.X_OK):
            return _c("out", "Output folder", ACTION, "%s is not writable" % out, "fix the permissions or choose another output path")
        return _c("out", "Output folder", READY, "%s writable" % out)
    parent = os.path.dirname(os.path.abspath(out))
    while parent and not env.exists(parent):
        nxt = os.path.dirname(parent)
        if nxt == parent:
            break
        parent = nxt
    if env.isdir(parent) and env.access(parent, os.W_OK | os.X_OK):
        return _c("out", "Output folder", READY, "%s does not exist yet; it can be created under %s" % (out, parent))
    return _c("out", "Output folder", ACTION, "%s cannot be created (%s is not writable)" % (out, parent), "choose a writable output path")


def check_viewer(env):
    from . import viewer
    v = viewer.verify_assets()
    if v["ok"]:
        return _c("viewer", "Structure viewer (Mol*)", READY, "Mol* %s; %d files match VERSION.json" % (v["version"], len(v["files"])))
    return _c("viewer", "Structure viewer (Mol*)", ACTION, "; ".join(v["problems"])[:200],
              "reinstall RNPLens; the vendored viewer files must be the recorded release")


# ---------------------------------------------------------------- agent (Codex) checks

def codex_path(env):
    """The Codex binary the jail runs (QA fix #7: the same resolution as codex_jail.sh): RNPLENS_CODEX_BIN if set (used
    as given, no fallback), else Codex's standalone install $CODEX_HOME/packages/standalone/current/bin/codex
    (CODEX_HOME defaults to ~/.codex). A `codex` on PATH is never run by the jail and is therefore not the one checked."""
    forced = env.environ.get("RNPLENS_CODEX_BIN")
    if forced:
        return forced if env.isfile(forced) else None
    home = env.environ.get("HOME") or os.path.expanduser("~")
    ch = env.environ.get("CODEX_HOME") or os.path.join(home, ".codex")
    alt = os.path.join(ch, "packages", "standalone", "current", "bin", "codex")
    return alt if env.isfile(alt) else None


def _path_note(env, exe):
    p = env.which("codex")
    if p and (not exe or os.path.realpath(p) != os.path.realpath(exe)):
        return "; `codex` on PATH (%s) is not the binary the jail runs and is not checked" % p
    return ""


def _run(env, argv, timeout=20):
    try:
        return env.run(argv, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "", "timed out after %d s" % timeout
    except OSError as ex:
        return None, "", "%s: %s" % (type(ex).__name__, ex)


def check_codex(env):
    exe = codex_path(env)
    if not exe:
        return None, _c("codex_cli", "Codex CLI", ACTION, "not found where the jail looks (RNPLENS_CODEX_BIN, else "
                        "$CODEX_HOME/packages/standalone/current/bin/codex)%s" % _path_note(env, exe),
                        "install Codex's standalone build (tested version %s) or set RNPLENS_CODEX_BIN to a native Codex binary; "
                        "RNPLens does not install it" % TESTED_CODEX, "agent")
    rc, so, se = _run(env, [exe, "--version"])
    m = re.search(r"(\d+\.\d+\.\d+)", so or "") or re.search(r"(\d+\.\d+\.\d+)", se or "")
    if rc != 0 or not m:
        return exe, _c("codex_cli", "Codex CLI", ACTION, "found, but '--version' failed: %s" % redact(se or so), "reinstall the Codex CLI", "agent")
    v = m.group(1)
    if v != TESTED_CODEX:
        return exe, _c("codex_cli", "Codex CLI", ACTION, "version %s: untested version (tested %s); binary the jail runs: %s" % (v, TESTED_CODEX, exe),
                       "install Codex CLI %s, or accept that this version is untested with RNPLens" % TESTED_CODEX, "agent")
    return exe, _c("codex_cli", "Codex CLI", READY, "version %s (the tested version); checked binary = the binary the jail runs: %s%s"
                   % (v, exe, _path_note(env, exe)), group="agent")


def check_login(env, exe):
    if not exe:
        return _c("codex_login", "ChatGPT sign-in", ACTION, NOT_VERIFIED + " (no Codex CLI)", "install the Codex CLI first", "agent")
    rc, so, se = _run(env, [exe, "login", "status"])
    lines = [l for l in ((so or "") + "\n" + (se or "")).splitlines() if l.strip()]
    line = redact(lines[0]) if lines else ""
    low = line.lower()
    if rc == 0 and "chatgpt" in low and "not" not in low:
        return _c("codex_login", "ChatGPT sign-in", READY, line, group="agent")
    if "api key" in low or "api_key" in low:
        return _c("codex_login", "ChatGPT sign-in", ACTION, line or "signed in with an API key",
                  "RNPLens uses ChatGPT sign-in only: run 'codex login' and choose Sign in with ChatGPT", "agent")
    return _c("codex_login", "ChatGPT sign-in", ACTION, line or "status unknown (exit %s)" % rc,
              "run 'codex login' and sign in with your ChatGPT account", "agent")


def check_model(env, exe):
    if not exe:
        return _c("codex_model", "Model %s" % TESTED_MODEL, ACTION, NOT_VERIFIED + " (no Codex CLI)", "install the Codex CLI first", "agent")
    rc, so, se = _run(env, [exe, "debug", "models"], timeout=30)
    if rc != 0:
        return _c("codex_model", "Model %s" % TESTED_MODEL, ACTION, NOT_VERIFIED + ": 'codex debug models' failed (%s)" % redact(se or so),
                  "sign in with ChatGPT, then run 'rnplens doctor --agent' again", "agent")
    slugs = set(re.findall(r"[A-Za-z0-9][A-Za-z0-9._\-]*", so or ""))
    if TESTED_MODEL in slugs:
        return _c("codex_model", "Model %s" % TESTED_MODEL, READY, "offered to this account (the tested model)", group="agent")
    return _c("codex_model", "Model %s" % TESTED_MODEL, ACTION, "not listed by 'codex debug models' for this account",
              "the assistant was tested only with %s; it stays disabled until that model is offered" % TESTED_MODEL, "agent")


def check_bwrap(env):
    if env.system() != "Linux":
        return _c("bwrap", "bubblewrap and user namespaces", UNSUPPORTED, "bubblewrap jails are Linux-only", "use Linux for the assistant", "agent")
    exe = env.which("bwrap")
    if not exe:
        return _c("bwrap", "bubblewrap and user namespaces", ACTION, "bwrap not found",
                  "ask your administrator to install bubblewrap (package 'bubblewrap')", "agent")
    rc, so, se = _run(env, [exe, "--ro-bind", "/", "/", "true"], timeout=10)
    if rc == 0:
        return _c("bwrap", "bubblewrap and user namespaces", READY, "probe 'bwrap --ro-bind / / true' succeeded", group="agent")
    msg = redact(se or so or "")
    if rc is not None and re.search(r"not permitted|permission denied|no permissions|uid map|user namespace", msg, re.I):
        return _c("bwrap", "bubblewrap and user namespaces", ACTION, "unprivileged user namespaces are not usable: %s" % msg,
                  "ask your administrator to allow unprivileged user namespaces for bwrap (kernel or AppArmor setting)", "agent")
    return _c("bwrap", "bubblewrap and user namespaces", ACTION, NOT_VERIFIED + ": the probe could not run here (%s)" % (msg or "exit %s" % rc),
              "run 'rnplens doctor --agent' outside any container or sandbox to verify", "agent")


SANDBOX_EXEC = "/usr/bin/sandbox-exec"


def check_seatbelt(env):
    """macOS: Apple's Seatbelt must be usable by this process. A harmless probe applies an allow-all profile to
    /usr/bin/true; it fails when this process already runs inside another sandbox (Seatbelt cannot be nested)."""
    if not env.isfile(SANDBOX_EXEC):
        return _c("seatbelt", "Seatbelt sandbox (sandbox-exec)", ACTION, "%s not found" % SANDBOX_EXEC,
                  "use macOS 13 or later with the standard system tools", "agent")
    rc, so, se = _run(env, [SANDBOX_EXEC, "-p", "(version 1)(allow default)", "/usr/bin/true"], timeout=10)
    if rc == 0:
        return _c("seatbelt", "Seatbelt sandbox (sandbox-exec)", READY, "probe 'sandbox-exec' with an allow-all profile succeeded", group="agent")
    msg = redact(se or so or "")
    if re.search(r"not permitted|sandbox_apply", msg, re.I):
        return _c("seatbelt", "Seatbelt sandbox (sandbox-exec)", ACTION, "Seatbelt cannot be applied here: %s" % msg,
                  "run RNPLens from an ordinary Terminal session, not inside another sandboxed app or agent", "agent")
    return _c("seatbelt", "Seatbelt sandbox (sandbox-exec)", ACTION, NOT_VERIFIED + ": the probe could not run here (%s)" % (msg or "exit %s" % rc),
              "run 'rnplens doctor --agent' from an ordinary Terminal session to verify", "agent")


def check_confinement(env):
    """The confinement mechanism of this platform: Seatbelt on macOS; bubblewrap everywhere else (Linux; any other
    system gets the unchanged UNSUPPORTED answer of check_bwrap)."""
    return check_seatbelt(env) if env.system() == "Darwin" else check_bwrap(env)


def check_jail(env, hidden=None):
    """The jail script of THIS installation (the adapter's packaged default; RNPLENS_CODEX_JAIL naming any other jail
    is refused, as at the launch boundary), verified by the jail's own no-model self-probe, run with the same
    environment as a real call (codex_llm.jail_environ): inside the namespace the given host path (the project folder, else the
    current folder) must not exist, the login file must be present and the work folder writable."""
    try:
        p = env.approved_jail()
        from rnplens_assistant import codex_llm
    except Exception as ex:
        return _c("codex_jail", "Codex jail script", ACTION, "assistant package not importable (%s)" % type(ex).__name__,
                  "install the assistant package", "agent")
    o = env.environ.get("RNPLENS_CODEX_JAIL")
    if o and os.path.realpath(o) != os.path.realpath(p):        # the launch boundary refuses it; never probed or run
        return _c("codex_jail", "Codex jail script", ACTION, "RNPLENS_CODEX_JAIL=%s is not the jail shipped with this "
                  "installation (%s); the assistant refuses it" % (o, p), "unset RNPLENS_CODEX_JAIL", "agent")
    if not (env.isfile(p) and env.access(p, os.R_OK)):
        return _c("codex_jail", "Codex jail script", ACTION, "%s not found or not readable" % p,
                  "reinstall the assistant package", "agent")
    import tempfile
    hid = os.path.abspath(hidden or os.getcwd())
    keep = ["%s=%s" % kv for kv in sorted(codex_llm.jail_environ(env.environ).items())]   # the environment of a real call
    with tempfile.TemporaryDirectory(prefix="rnplens_jailprobe_") as d:
        rc, outp, msg = env.run(["/usr/bin/env", "-i"] + keep + ["RNPLENS_JAIL_PROBE=1", "RNPLENS_JAIL_PROBE_HIDDEN=" + hid,
                                                              "/bin/bash", p, d, "--"], timeout=20)
    if rc == 0 and "JAIL_OK" in (outp or ""):
        return _c("codex_jail", "Codex jail script", READY,
                  "%s; self-probe passed (%s is not visible inside; login file present)" % (p, hid), group="agent")
    return _c("codex_jail", "Codex jail script", ACTION, NOT_VERIFIED + ": jail self-probe did not pass (%s)"
              % ((msg or outp or "exit %s" % rc).strip()[:200]),
              ("check Seatbelt, 'codex login' (file-based login storage) and the Codex installation (see docs/install_macos.md)"
               if env.system() == "Darwin" else
               "check bubblewrap, 'codex login' and the Codex installation (see docs/setup_and_privacy.md)"), "agent")


def check_assistant_package(env):
    try:
        import rnplens_assistant  # noqa: F401
        from rnplens_assistant import ask  # noqa: F401
    except Exception as ex:
        return _c("assistant_pkg", "Assistant package", ACTION, "rnplens_assistant not importable (%s)" % type(ex).__name__,
                  "install the assistant package (assistant/ in the RNPLens source)", "agent")
    return _c("assistant_pkg", "Assistant package", READY, "rnplens_assistant %s" % rnplens_assistant.__version__, group="agent")


def agent_checks(env, project=None):
    _, asst = platform_status(env)
    exe, cli = check_codex(env)
    out = [asst, cli, check_login(env, exe), check_model(env, exe), check_confinement(env), check_jail(env, project), check_assistant_package(env)]
    blockers = [c for c in out if c["status"] != READY]
    if env.environ.get("RNPLENS_LLM", "").lower() in ("0", "off", "false", "no"):
        blockers.append({"check": "RNPLENS_LLM", "status": ACTION, "detail": "language-model functions switched off by RNPLENS_LLM"})
    if blockers:
        st = UNSUPPORTED if any(c["status"] == UNSUPPORTED for c in blockers) else ACTION
        out.append(_c("llm_mode", "Language-model functions", st,
                      "disabled: natural-language planner (rnplens assist --nl) is off because: %s"
                      % "; ".join("%s %s" % (c["check"], c["status"]) for c in blockers),
                      "the question menu (rnplens assist) works without any language model", "agent"))
    else:
        out.append(_c("llm_mode", "Language-model functions", READY,
                      "enabled: natural-language planner (rnplens assist --nl) and, with recorded consent, the EXPERIMENTAL Codex follow-up", group="agent"))
    return out


def agent_status(env=None):
    """(ready, reasons) used by `rnplens assist --nl`. ready is True only when every agent check is READY."""
    checks = agent_checks(env or Env())
    bad = [c for c in checks if c["status"] != READY and c["id"] != "llm_mode"]
    extra = [c for c in checks if c["id"] == "llm_mode" and c["status"] != READY]
    reasons = ["%s: %s (%s)" % (c["check"], c["status"], c["detail"]) for c in bad] or [c["detail"] for c in extra]
    return (not bad and not extra), reasons


def run_checks(agent=False, project=None, out=None, env=None):
    env = env or Env()
    tk, _ = platform_status(env)
    checks = [check_python(env), check_rnplens(env), check_components(env), check_capabilities(env), tk]
    checks += check_dependencies(env)
    if project:
        checks.append(check_project(env, project))
    if out:
        checks.append(check_out(env, out))
    checks.append(check_viewer(env))
    if agent:
        checks += agent_checks(env, project)
    summary = {s: sum(1 for c in checks if c["status"] == s) for s in (READY, ACTION, UNSUPPORTED)}
    summary["optional_not_ready"] = sum(1 for c in checks if c.get("optional") and c["status"] != READY)
    return {"record": "rnplens-doctor-1", "rnplens_version": __version__, "platform": "%s %s" % (env.system(), env.machine()),
            "agent_checked": bool(agent), "checks": checks, "summary": summary, "notice": NOTICE,
            "changes_made": "none: the doctor installs nothing, changes no setting and reads no credential file"}


def capability(**kw):
    rec = run_checks(agent=bool(kw.get("agent")), project=kw.get("project"), out=kw.get("out"))
    return dict(rec, outputs=[])


def render(rec):
    lines = ["rnplens doctor (RNPLens %s, %s)" % (rec["rnplens_version"], rec["platform"]), ""]
    for c in rec["checks"]:
        lines.append("  %-16s %-38s %s" % (c["status"], c["check"], c["detail"]))
        if c["remedy"]:
            lines.append("  %-16s %-38s remedy: %s" % ("", "", c["remedy"]))
    s = rec["summary"]
    lines += ["", "summary: %d READY, %d ACTION REQUIRED, %d UNSUPPORTED%s" % (
        s[READY], s[ACTION], s[UNSUPPORTED], " (%d of them optional; exit status 0)" % s["optional_not_ready"]
        if s.get("optional_not_ready") and s[ACTION] + s[UNSUPPORTED] == s["optional_not_ready"] else "")]
    if not rec["agent_checked"]:
        lines.append("Codex checks not run; 'rnplens doctor --agent' checks the optional natural-language mode. "
                     "The question menu (rnplens assist) needs no language model.")
    lines += ["", rec["notice"], "The doctor changed nothing on this system."]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rnplens doctor", description="Check the installation, platform and optional Codex "
                                 "setup. Each check is READY, ACTION REQUIRED or UNSUPPORTED with a one-line remedy. "
                                 "Nothing is installed or changed.")
    ap.add_argument("--agent", action="store_true", help="also check the optional Codex (ChatGPT sign-in) natural-language mode")
    ap.add_argument("--project", help="project folder to check for read access")
    ap.add_argument("--out", help="output folder to check for write access")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    ap.add_argument("--save", action="store_true", help="also write the result to <out>/doctor.json (needs --out)")
    a = ap.parse_args(argv)
    if a.save and not a.out:
        print("rnplens doctor: --save needs --out", file=sys.stderr)
        return 2
    rec = run_checks(agent=a.agent, project=a.project, out=a.out)
    if a.save:
        from . import provenance as pv
        out_check = [c for c in rec["checks"] if c["id"] == "out"][0]
        if out_check["status"] != READY:
            print("rnplens doctor: cannot save, %s" % out_check["detail"], file=sys.stderr)
            return 2
        saved = dict(rec, provenance=pv.block("doctor", [], "installation and platform checks of rnplens doctor",
                                              {"agent": a.agent, "project": a.project}))
        pv.atomic_write_json(os.path.join(a.out, "doctor.json"), saved)
    print(json.dumps(rec, indent=1) if a.json else render(rec))
    if a.save:
        print("written: %s" % os.path.join(a.out, "doctor.json"), file=sys.stderr)
    blocking = [c for c in rec["checks"] if c["status"] != READY and not c.get("optional")]
    return 0 if not blocking else 1
