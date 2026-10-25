"""LIVE_QUALIFICATION_v1 driver: the bounded live Codex qualification of the RNPLens 0.4 natural-language planner
(Part P) and of three frozen FOLLOWUP_SUITE_v1 Part 2 follow-up scenarios (Part F). FROZEN; see DESIGN.md.

    # 0. plan only (no call, nothing written)
    python assistant/evaluation_v04/LIVE_QUALIFICATION_v1/run_live.py --plan
    # 1. exactly ONE live call, then stop and print the balance and usage
    RNPLENS_LIVE_QUAL=I_CONFIRM_AUTO_RELOAD_OFF_AND_ACCEPT_ONE_CALL_RISK python .../run_live.py --first-call \
        --run-id lq1-run1 --confirmation /path/owner_confirmation.txt
    # 2. after the owner has compared the printed balance and usage, the rest, strictly serially
    RNPLENS_LIVE_QUAL=I_CONFIRM_AUTO_RELOAD_OFF_AND_ACCEPT_ONE_CALL_RISK python .../run_live.py --continue-after-first \
        --run-id lq1-run1 --confirmation /path/owner_confirmation.txt --go-ahead /path/owner_go_ahead.txt
    (Amendment 4: the continue needs the owner's go-ahead file, written after inspecting the first call's result,
    model identity, usage and balance; it must quote the first-call digest printed by step 1)

Every refusal is checked before anything is created or called. A stopped run (abort, defect, crash) is never resumed:
a new run needs a new run id, and every call of every run counts against one ledger capped at 24 calls. No call is
ever retried automatically. Only the Codex CLI (ChatGPT sign-in) is used; the separately billed API client
(rnplens_assistant.llm.Client) is disabled in this process."""
import argparse
import contextlib
import datetime
import decimal
import hashlib
import importlib
import io
import json
import locale
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ASSISTANT = os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.dirname(ASSISTANT)
FU_DIR = os.path.join(ASSISTANT, "evaluation_v04", "FOLLOWUP_SUITE_v1")
SUITE = "LIVE_QUALIFICATION_v1"
RNPBENCH = "/home/jwen/projects/RNPBench"
LIVE_ROOT = RNPBENCH + "/scratch_agent/v04/codex_calls_live"
DEFAULT_TASKS = RNPBENCH + "/scratch_agent/assistant_dev_tasks"
FORBIDDEN_ROOTS = [RNPBENCH + "/RNPLens_dev_0.3", RNPBENCH + "/scratch_agent/codex_calls", RNPBENCH + "/scratch_agent/v04/codex_calls",
                   RNPBENCH + "/RNPLens_release_2026-10-13", RNPBENCH + "/RNPLens-Rank", RNPBENCH + "/manuscript"]
LIVE_ENV = "RNPLENS_LIVE_QUAL"
LIVE_TOKEN = "I_CONFIRM_AUTO_RELOAD_OFF_AND_ACCEPT_ONE_CALL_RISK"
LIVE_TOKEN_BLOCK = "I_CONFIRM_HARD_SPENDING_BLOCK"                     # Amendment 4: the owner's alternative precondition
MODEL, EFFORT = "gpt-6.1-sol", "medium"
TZ = "Australia/Canberra"
BLOCK_FROM, BLOCK_TO = "2026-10-22T00:00", "2026-10-25T00:00"     # the sealed evaluation, 22-24 October (Canberra)
BLOCK_MARGIN = datetime.timedelta(hours=2)                       # clock-skew margin on both sides
EARLIEST = "2026-10-16T00:00"                                    # a clock before the freeze is not trusted
WEEKLY_MAX_RISE, USAGE_CEILING = 10.0, 85.0
LEDGER_CAP = 24
RUN_ID_RE = re.compile(r"^lq1-[a-z0-9][a-z0-9-]{0,39}$")
CONFIRM_HEADER = "RNPLens LIVE_QUALIFICATION_v1 owner confirmation"
STATEMENT = ("I confirm that automatic credit reload is OFF for the ChatGPT account used by Codex on this machine, "
             "and I accept the residual risk that one call may use existing credits.")
STATEMENT_BLOCK = ("I confirm that a hard spending block prevents any use of credits by the ChatGPT account used by Codex "
                   "on this machine.")                                      # Amendment 4: the owner's alternative precondition
STATEMENTS = (STATEMENT, STATEMENT_BLOCK)
TOKEN_FOR = {STATEMENT: LIVE_TOKEN, STATEMENT_BLOCK: LIVE_TOKEN_BLOCK}
GO_AHEAD_HEADER = "RNPLens LIVE_QUALIFICATION_v1 owner go-ahead"
GO_AHEAD_STATEMENT = ("I have inspected the first call's result, model identity, usage and credit balance, and I authorise "
                      "the remaining calls of this run.")
EXCLUDED = ("3WZI 4DWA 4KR6 4OHZ 4PMI 4RCJ 4RDX 5B63 5FN1 5HSW 5MSF 5U30 5X2G 6DCB 6E4P 6LT7 6M7K 6NY2 6O6V 6O7B 6P7P 6SCE "
            "6W11 6XMF 7QQK 7S7C 7UZW 7VYX 7XG1 7XS4 8PSQ 8UMF 8WO8 9JXX 9RVP 9U49 9YLU").split()
API_ENV = ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE", "AZURE_OPENAI_API_KEY")
JAIL_REL = "assistant/rnplens_assistant/codex_adapter/codex_jail.sh"
NOOP = lambda *a, **k: None

sys.path.insert(0, HERE)
import privacy  # noqa: E402
import score_live  # noqa: E402


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def sha_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def load_scenarios():
    with open(os.path.join(HERE, "scenarios.json"), encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- frozen files
def freeze_refusals():
    """FREEZE.md matches every file of this suite (and no unlisted file exists outside results/); the referenced
    FOLLOWUP_SUITE_v1 files and the pinned assistant sources are unchanged."""
    R = []
    fz = os.path.join(HERE, "FREEZE.md")
    if not os.path.isfile(fz):
        return ["FREEZE.md missing"]
    rows = dict(re.findall(r"^\| `([^`]+)` \| `([0-9a-f]{64})` \|", open(fz, encoding="utf-8").read(), re.M))
    if not rows:
        return ["FREEZE.md lists no file"]
    for name, h in rows.items():
        p = os.path.join(HERE, name)
        if not os.path.isfile(p) or sha_file(p) != h:
            R.append("FREEZE mismatch: %s" % name)
    for dp, dn, fn in os.walk(HERE):
        dn[:] = [d for d in dn if d not in ("results", "__pycache__")]
        for f in fn:
            rel = os.path.relpath(os.path.join(dp, f), HERE)
            if rel != "FREEZE.md" and rel not in rows:
                R.append("unfrozen file in the suite folder: %s" % rel)
    S = load_scenarios()
    pf = S["part_F"]
    for rel, key in ((pf["source"], "source_sha256"), (pf["suite_freeze"], "suite_freeze_sha256")):
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p) or sha_file(p) != pf[key]:
            R.append("FOLLOWUP_SUITE_v1 file changed: %s" % rel)
    for rel, h in S["pinned_sources"].items():
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p) or sha_file(p) != h:
            R.append("pinned source changed since the freeze: %s" % rel)
    return R


def load_followup_suite():
    """FOLLOWUP_SUITE_v1's own modules (run_part2: setup_task, _auto_range; score: score_part2, forbidden_hits;
    run_part1: check_freeze), imported by reference without clashing with same-named modules elsewhere."""
    names = ("score", "run_part1", "run_part2", "fake_client")
    saved = {n: sys.modules.pop(n) for n in names if n in sys.modules}
    saved_path = list(sys.path)
    sys.path.insert(0, FU_DIR)
    try:
        rp2 = importlib.import_module("run_part2")
        mods = {"run_part2": rp2, "score": sys.modules["score"], "run_part1": sys.modules["run_part1"]}
    finally:
        sys.path[:] = saved_path              # run_part1/run_part2 insert their folder; nothing stays behind
        for n in names:
            sys.modules.pop(n, None)
        sys.modules.update(saved)
    return mods


# ---------------------------------------------------------------- owner confirmation, clock
def _zone():
    from zoneinfo import ZoneInfo
    return ZoneInfo(TZ)


def ntp_status():
    """(synchronised, detail) from systemd-timedated. Anything else (no timedatectl, 'no', error) is not certainty."""
    try:
        p = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as ex:
        return False, "timedatectl unavailable (%s)" % type(ex).__name__
    v = (p.stdout or "").strip().lower()
    return (p.returncode == 0 and v == "yes"), "timedatectl NTPSynchronized=%s" % (v or "?")


def clock_refusals(now_utc, ntp):
    """-> (refusals, canberra_date_str). Refuses without clock/timezone certainty and inside the sealed window."""
    R = []
    try:
        tz = _zone()
    except Exception as ex:
        return ["time zone %s cannot be loaded (%s): no timezone certainty" % (TZ, type(ex).__name__)], None
    if now_utc.tzinfo is None:
        return ["the clock has no time zone: no clock certainty"], None
    local = now_utc.astimezone(tz)
    off = local.utcoffset()
    if off not in (datetime.timedelta(hours=10), datetime.timedelta(hours=11)):
        R.append("%s offset %s is neither +10:00 nor +11:00: no timezone certainty" % (TZ, off))
    ok, detail = ntp
    if not ok:
        R.append("system clock synchronisation not confirmed (%s): no clock certainty" % detail)
    a, b = (datetime.datetime.fromisoformat(x).replace(tzinfo=tz) for x in (BLOCK_FROM, BLOCK_TO))
    if a - BLOCK_MARGIN <= local < b + BLOCK_MARGIN:
        R.append("inside the sealed-evaluation block 2026-10-22..2026-10-24 Australia/Canberra (with a %s margin): %s"
                 % (BLOCK_MARGIN, local.isoformat(timespec="minutes")))
    if local < datetime.datetime.fromisoformat(EARLIEST).replace(tzinfo=tz):
        R.append("the clock reads %s, before the suite's freeze: no clock certainty" % local.isoformat(timespec="minutes"))
    return R, local.date().isoformat()


def parse_decimal(x):
    s = str(x).strip() if x is not None else ""
    if not re.fullmatch(r"-?\d+(\.\d+)?", s):
        return None
    return decimal.Decimal(s)


# ---------------------------------------------------------------- Amendment 8: call-specific authorisation binding
AUTH_KEYS = ("experiment", "mode", "run_id", "scenario", "task", "target", "task_sha256", "commit", "model",
             "reasoning_effort", "payload_sha256", "registry_sha256", "jail_sha256", "freeze_sha256", "codex_sha256",
             "bwrap_sha256", "python_sha256", "max_model_calls")
MODE_NAMES = {"first": "first-call", "continue": "continue-after-first"}
REGISTRY_REL = "assistant/rnplens_assistant/registry.json"
TASK_TARGET = re.compile(r"^d[0-9]+_([0-9][A-Za-z0-9]{3})_")


def runtime_hashes(env=None):
    """sha256 of the executables a call would use: the Codex binary the jail runs (RNPLENS_CODEX_BIN, else
    $CODEX_HOME/packages/standalone/current/bin/codex; never PATH), bubblewrap, and this Python interpreter."""
    env = os.environ if env is None else env
    home = env.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    cx = env.get("RNPLENS_CODEX_BIN") or os.path.join(home, "packages", "standalone", "current", "bin", "codex")
    bw = shutil.which("bwrap")
    f = lambda p: sha_file(os.path.realpath(p)) if p and os.path.isfile(p) else "missing"
    return {"codex_sha256": f(cx), "bwrap_sha256": f(bw), "python_sha256": f(sys.executable)}


def task_digest(task_dir):
    """Content identity of a development task folder: sha256 over 'relative path<TAB>sha256' lines, sorted."""
    lines = []
    for dp, dn, fn in os.walk(task_dir):
        dn[:] = sorted(x for x in dn if not x.startswith(".") and x != "__pycache__")
        for f in fn:
            if not f.startswith("."):
                pth = os.path.join(dp, f)
                lines.append("%s\t%s" % (os.path.relpath(pth, task_dir).replace(os.sep, "/"), sha_file(pth)))
    return sha_text("\n".join(sorted(lines)) + "\n")


def _scenario_tasks(S):
    m = {s["id"]: s["task"] for s in S["part_P"] + S["part_Z"]}
    pf = S["part_F"]
    S2 = json.load(open(os.path.join(ROOT, pf["source"]), encoding="utf-8"))
    for s in S2["scenarios"]:
        if s["id"] in pf["ids"]:
            m["F-" + s["id"]] = s["task"]
    return m


def authorisation_values(mode, run_id, tasks, S, head, runtime):
    """-> (values, detail). The exact values a call-specific authorisation must name for this mode and run (Amendment
    8). first-call: the first-call scenario only, at most 1 model call. continue-after-first: the remaining scenarios,
    at most LEDGER_CAP - 1 calls. payload_sha256 is the model-visible first planning payload (reconstructed with no
    model); for several scenarios, the sha256 of their 'id sha256' lines. Follow-up payloads depend on the analysis and
    are covered by the pre-send gate and the frozen premise record, not by this value."""
    from rnplens_assistant import codex_llm
    first = S["first_call_scenario"]
    sids = [first] if mode == "first" else S["order"][S["order"].index(first) + 1:]
    stask = _scenario_tasks(S)
    tnames = sorted({stask[x] for x in sids})
    targets = sorted({(TASK_TARGET.match(x) or [None, "unknown"])[1] for x in tnames})
    pmap = {}
    for s in S["part_P"]:
        if s["id"] in sids:
            system, user = expected_nl_payload(s["question"], os.path.join(tasks, s["task"]))
            pmap[s["id"]] = sha_text(system + "\n\n---\n\n" + user)
    tdig = {x: task_digest(os.path.join(tasks, x)) for x in tnames}
    one = lambda d: list(d.values())[0] if len(d) == 1 else sha_text("".join("%s %s\n" % kv for kv in sorted(d.items())))
    v = {"experiment": SUITE, "mode": MODE_NAMES[mode], "run_id": run_id or "", "scenario": ",".join(sids),
         "task": ",".join(tnames), "target": ",".join(targets), "task_sha256": one(tdig), "commit": head or "",
         "model": codex_llm.CONFIG.get("model"), "reasoning_effort": codex_llm.CONFIG.get("reasoning_effort"),
         "payload_sha256": one(pmap) if pmap else "none", "registry_sha256": sha_file(os.path.join(ROOT, REGISTRY_REL)),
         "jail_sha256": sha_file(os.path.join(ROOT, JAIL_REL)), "freeze_sha256": sha_file(os.path.join(HERE, "FREEZE.md")),
         "max_model_calls": str(1 if mode == "first" else LEDGER_CAP - 1)}
    v.update(runtime)
    return v, {"scenario_payloads": pmap, "task_digests": tdig}


def authorisation_refusals(conf, want):
    R = []
    for key in AUTH_KEYS:
        if conf.get(key) and conf.get(key) != want.get(key):
            R.append("authorisation %s %r does not match this run's %r: an authorisation for other inputs or another "
                     "experiment does not cover this one" % (key, conf.get(key)[:24], str(want.get(key))[:24]))
    return R


def parse_confirmation(path, today):
    """-> (fields, refusals). Format (one 'key: value' per line after the header):
    date, statement (exact text), credit_balance (as shown in Codex Usage & Billing), weekly_usage_percent (as
    shown), and zero or more acknowledge_abort: <run id>."""
    if not path:
        return None, ["--confirmation FILE not given (the owner's dated statement that automatic reload is off)"]
    if not os.path.isfile(path):
        return None, ["owner confirmation file %s does not exist" % path]
    raw = open(path, encoding="utf-8").read()
    lines = [l.rstrip() for l in raw.splitlines() if l.strip()]
    R, F = [], {"path": os.path.abspath(path), "sha256": sha_text(raw), "acknowledge_abort": []}
    if not lines or lines[0].strip() != CONFIRM_HEADER:
        R.append("confirmation file: first line must be %r" % CONFIRM_HEADER)
    for l in lines[1:]:
        k, _, v = l.partition(":")
        k, v = k.strip(), v.strip()
        if k == "acknowledge_abort":
            F["acknowledge_abort"].append(v)
        elif k in ("date", "statement", "credit_balance", "weekly_usage_percent") + AUTH_KEYS:
            if k in F:
                R.append("confirmation file: %s given twice" % k)
            F[k] = v
        else:
            R.append("confirmation file: unknown line %r" % l[:60])
    if F.get("date") != today:
        R.append("confirmation date %r is not today's date in %s (%s)" % (F.get("date"), TZ, today))
    if F.get("statement") not in STATEMENTS:
        R.append("confirmation statement is not one of the exact required statements (auto-reload off and the one-call "
                 "risk accepted, or a hard spending block)")
    else:
        F["precondition"] = "hard spending block" if F["statement"] == STATEMENT_BLOCK else "auto-reload off; one-call risk accepted"
    for key in AUTH_KEYS:                     # Amendment 8: the authorisation names every bound value
        if not F.get(key):
            R.append("authorisation %s missing: the confirmation file must name every bound value (Amendment 8)" % key)
    if parse_decimal(F.get("credit_balance")) is None:
        R.append("confirmation credit_balance %r is not a number" % F.get("credit_balance"))
    w = F.get("weekly_usage_percent")
    try:
        wf = float(w)
        if not 0 <= wf <= 100:
            raise ValueError
        F["weekly_usage_percent_value"] = wf
    except (TypeError, ValueError):
        R.append("confirmation weekly_usage_percent %r is not a percentage" % w)
    else:
        if wf >= USAGE_CEILING:
            R.append("stated weekly usage %.1f%% is at or above the %.0f%% ceiling" % (wf, USAGE_CEILING))
    return F, R


def first_call_digest(rec):
    """16 hex characters binding the go-ahead to what the first invocation printed (Amendment 4)."""
    c1 = (rec.get("calls") or [{}])[0]
    p01 = (rec.get("scenarios") or {}).get("P01") or {}
    blob = {"run_id": rec.get("run_id"), "prompt_sha256": c1.get("prompt_sha256"), "post_reading": c1.get("post_reading"),
            "p01": {k: p01.get(k) for k in ("status", "reason", "hard", "tool_selection")}}
    return hashlib.sha256(json.dumps(blob, sort_keys=True, default=str).encode()).hexdigest()[:16]


def parse_go_ahead(path, today, rec, base_balance, base_weekly):
    """-> (fields, refusals). The owner's second confirmation, required for --continue-after-first (Amendment 4)."""
    if not path:
        return None, ["--go-ahead FILE not given: the remaining calls need the owner's recorded go-ahead after the first call"]
    if not os.path.isfile(path):
        return None, ["owner go-ahead file %s does not exist" % path]
    raw = open(path, encoding="utf-8").read()
    lines = [l.rstrip() for l in raw.splitlines() if l.strip()]
    R, F = [], {"path": os.path.abspath(path), "sha256": sha_text(raw)}
    if not lines or lines[0].strip() != GO_AHEAD_HEADER:
        R.append("go-ahead file: first line must be %r" % GO_AHEAD_HEADER)
    for l in lines[1:]:
        k, _, v = l.partition(":")
        k, v = k.strip(), v.strip()
        if k in ("date", "run_id", "first_call_digest", "observed_credit_balance", "observed_weekly_usage_percent", "statement"):
            if k in F:
                R.append("go-ahead file: %s given twice" % k)
            F[k] = v
        else:
            R.append("go-ahead file: unknown line %r" % l[:60])
    if F.get("date") != today:
        R.append("go-ahead date %r is not today's date in %s (%s)" % (F.get("date"), TZ, today))
    if F.get("run_id") != rec.get("run_id"):
        R.append("go-ahead run_id %r is not this run (%s)" % (F.get("run_id"), rec.get("run_id")))
    if F.get("first_call_digest") != first_call_digest(rec):
        R.append("go-ahead first_call_digest does not match the digest printed after this run's first call")
    if F.get("statement") != GO_AHEAD_STATEMENT:
        R.append("go-ahead statement is not the exact required statement")
    b = parse_decimal(F.get("observed_credit_balance"))
    if b is None:
        R.append("go-ahead observed_credit_balance %r is not a number" % F.get("observed_credit_balance"))
    elif b != base_balance:
        R.append("the owner observed a credit balance of %s after the first call, not the baseline %s: no further call" % (b, base_balance))
    try:
        w = float(F.get("observed_weekly_usage_percent"))
        if w > base_weekly + WEEKLY_MAX_RISE or w >= USAGE_CEILING:
            R.append("the owner observed weekly usage %.1f%% after the first call: above the guard" % w)
    except (TypeError, ValueError):
        R.append("go-ahead observed_weekly_usage_percent %r is not a percentage" % F.get("observed_weekly_usage_percent"))
    done = ((rec.get("calls") or [{}])[0]).get("completed_utc")
    if done:
        t_done = datetime.datetime.fromisoformat(done).timestamp()
        if os.path.getmtime(path) < t_done:
            R.append("the go-ahead file was written before the first call completed (%s)" % done)
    return F, R


# ---------------------------------------------------------------- readings (balance and plan usage)
def reading_from_session(s):
    """Balance and plan usage from one call's Codex session log (codex_llm.read_session)."""
    rl = s.get("rate_limits")
    r = {"source": "session log", "model_returned": s.get("model_returned"), "effort_returned": s.get("effort_returned"),
         "cli_version": s.get("cli_version"), "rate_limits_present": bool(rl)}
    rl = rl or {}
    cr = rl.get("credits") if isinstance(rl.get("credits"), dict) else {}
    r["balance_raw"] = cr.get("balance")
    b = parse_decimal(cr.get("balance"))
    r["balance"] = str(b) if b is not None else None
    r["windows"] = {}
    for w in ("primary", "secondary"):
        x = rl.get(w) if isinstance(rl.get(w), dict) else None
        if x is not None:
            r["windows"][w] = {"used_percent": x.get("used_percent"), "window_minutes": x.get("window_minutes")}
    wk = [x for x in r["windows"].values() if (x.get("window_minutes") or 0) >= 7 * 24 * 60]
    try:
        r["weekly_used_percent"] = float(wk[0]["used_percent"]) if wk else None
    except (TypeError, ValueError):
        r["weekly_used_percent"] = None
    r["rate_limit_reached_type"] = rl.get("rate_limit_reached_type")
    r["plan_type"] = rl.get("plan_type")
    return r


def reading_problems(r, base_balance, base_weekly):
    """-> list of (kind, detail): any one aborts the run."""
    P = []
    if not r.get("rate_limits_present"):
        P.append(("USAGE_UNREADABLE", "no rate-limit snapshot in the Codex session log"))
    b = parse_decimal(r.get("balance"))
    if b is None:
        P.append(("BALANCE_UNREADABLE", "credit balance missing or unparseable (%r)" % (r.get("balance_raw"),)))
    elif b != base_balance:
        P.append(("CREDIT_BALANCE_CHANGED", "credit balance %s differs from the recorded baseline %s" % (b, base_balance)))
    wk = r.get("weekly_used_percent")
    if wk is None:
        P.append(("USAGE_UNREADABLE", "weekly plan usage missing or unparseable"))
    else:
        if wk > base_weekly + WEEKLY_MAX_RISE:
            P.append(("USAGE_RISE", "weekly usage %.1f%% is more than %.0f points above the start %.1f%%" % (wk, WEEKLY_MAX_RISE, base_weekly)))
        if wk >= USAGE_CEILING:
            P.append(("USAGE_CEILING", "weekly usage %.1f%% is at or above %.0f%%" % (wk, USAGE_CEILING)))
    for w, x in (r.get("windows") or {}).items():
        try:
            if float(x.get("used_percent") or 0) >= USAGE_CEILING:
                P.append(("USAGE_CEILING", "%s window usage %s%% is at or above %.0f%%" % (w, x.get("used_percent"), USAGE_CEILING)))
        except (TypeError, ValueError):
            P.append(("USAGE_UNREADABLE", "%s window usage unparseable" % w))
    if r.get("rate_limit_reached_type"):
        P.append(("RATE_LIMIT_REACHED", str(r["rate_limit_reached_type"])))
    if r.get("model_returned") != MODEL:
        P.append(("WRONG_MODEL", "Codex ran %r, not %s" % (r.get("model_returned"), MODEL)))
    return P


def baseline_reading(conf):
    return {"source": "owner confirmation (Codex Usage & Billing, before the run)", "balance": str(parse_decimal(conf["credit_balance"])),
            "weekly_used_percent": conf["weekly_usage_percent_value"], "rate_limits_present": True, "windows": {},
            "model_returned": MODEL}


# ---------------------------------------------------------------- ledger, lock, records
def ledger_path(root):
    return os.path.join(root, "LEDGER.jsonl")


def ledger(root):
    p = ledger_path(root)
    if not os.path.isfile(p):
        return []
    out = []
    with open(p, encoding="utf-8") as fh:
        for l in fh:
            l = l.strip()
            if l:
                out.append(json.loads(l))
    return out


def ledger_append(root, entry):
    entry = dict(entry, ts_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    with open(ledger_path(root), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def ledger_attempts(root):
    return sum(1 for e in ledger(root) if e.get("event") == "call_attempt")


def write_json(path, obj):
    from rnplens import provenance as pv
    pv.atomic_write_json(path, obj)


def git_state(root=ROOT):
    try:
        head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=20)
        st = subprocess.run(["git", "-C", root, "status", "--porcelain", "--", "src", "assistant"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as ex:
        return None, "git unavailable (%s)" % type(ex).__name__
    if head.returncode != 0:
        return None, "not a git checkout"
    return head.stdout.strip(), st.stdout.strip()


def _under(p, root):
    p, root = os.path.realpath(p), os.path.realpath(root.rstrip("/"))
    return p == root or p.startswith(root + os.sep)


def task_refusals(tasks, S):
    R = []
    if not tasks or not os.path.isdir(tasks):
        return ["--tasks %r is not a folder" % tasks]
    for r in FORBIDDEN_ROOTS:
        if _under(tasks, r):
            R.append("--tasks lies under the protected %s" % r)
    need = sorted({s["task"] for s in S["part_Z"] + S["part_P"]} | {"d1_7K9D_agreement", "d4_24BR_compare", "d5_24BR_geometry"})
    for t in need:
        d = os.path.join(tasks, t)
        tj = os.path.join(d, "task.json")
        if not os.path.isfile(tj):
            R.append("development task %s missing (no task.json)" % t)
            continue
        j = json.load(open(tj, encoding="utf-8"))
        if j.get("development_only") is not True:
            R.append("%s/task.json does not declare development_only" % t)
        for dp, dn, fn in os.walk(d):
            for f in dn + fn + [str(j.get("task_id", ""))]:
                if any(x.lower() in f.lower() for x in EXCLUDED):
                    R.append("%s contains a name of an excluded target (%s)" % (t, f))
    return R


def preflight(mode, a, env, hooks, S):
    """-> (refusals, ctx). Pure checks: nothing is created, written or called (the doctor's checks run the Codex CLI's
    --version, 'login status' and 'debug models' only, which make no model call)."""
    R, ctx = [], {}
    if env.get(LIVE_ENV) not in (LIVE_TOKEN, LIVE_TOKEN_BLOCK):
        R.append("%s must be %s (the owner has confirmed that automatic credit reload is off and accepts the one-call risk) "
                 "or %s (the owner has confirmed a hard spending block)" % (LIVE_ENV, LIVE_TOKEN, LIVE_TOKEN_BLOCK))
    now = (hooks.get("now") or (lambda: datetime.datetime.now(datetime.timezone.utc)))()
    cr, today = clock_refusals(now, (hooks.get("ntp") or ntp_status)())
    R += cr
    ctx["now_utc"], ctx["today"] = now.isoformat(timespec="seconds"), today
    conf, rr = parse_confirmation(a.confirmation, today) if today else (None, ["no date: confirmation not checked"])
    R += rr
    if conf and conf.get("statement") in TOKEN_FOR and env.get(LIVE_ENV) in (LIVE_TOKEN, LIVE_TOKEN_BLOCK) \
            and env.get(LIVE_ENV) != TOKEN_FOR[conf["statement"]]:
        R.append("%s=%s does not match the confirmation's statement (it needs %s)" % (LIVE_ENV, env.get(LIVE_ENV), TOKEN_FOR[conf["statement"]]))
    ctx["confirmation"] = conf
    R += freeze_refusals()
    try:
        load_followup_suite()["run_part1"].check_freeze()
    except SystemExit as ex:
        R.append("FOLLOWUP_SUITE_v1 freeze: %s" % ex)
    if not hooks.get("skip_git_clean"):
        head, dirty = git_state()
        if head is None:
            R.append("checkout state unknown: %s" % dirty)
        elif dirty:
            R.append("the checkout has uncommitted changes under src/ or assistant/: run only from a committed state")
        ctx["git_head"] = head
    else:
        ctx["git_head"] = git_state()[0]
    if conf:
        try:
            want, detail = authorisation_values(mode, a.run_id, a.tasks, S, ctx.get("git_head"),
                                                (hooks.get("runtime_hashes") or runtime_hashes)())
        except Exception as ex:                       # e.g. a missing task: refused, never guessed
            R.append("authorisation values cannot be computed: %s: %s" % (type(ex).__name__, ex))
        else:
            R += authorisation_refusals(conf, want)
            ctx["authorisation"] = {"values": want, "scenario_payloads": detail["scenario_payloads"]}
    enc = locale.getpreferredencoding(False).lower().replace("-", "")
    if enc != "utf8":
        R.append("preferred encoding is %s, not UTF-8: the bytes sent could not be certified" % enc)
    from rnplens_assistant import codex_llm
    if codex_llm.CONFIG.get("model") != MODEL or codex_llm.CONFIG.get("reasoning_effort") != EFFORT:
        R.append("codex_llm.CONFIG is %s/%s, not %s/%s" % (codex_llm.CONFIG.get("model"), codex_llm.CONFIG.get("reasoning_effort"), MODEL, EFFORT))
    jail = os.path.realpath(codex_llm.JAIL)
    want = os.path.realpath(os.path.join(ROOT, JAIL_REL))
    if not hooks.get("jail_any"):
        if jail != want:
            R.append("the jail %s is not this checkout's %s" % (jail, JAIL_REL))
        for r in FORBIDDEN_ROOTS:
            if _under(jail, r):
                R.append("the jail lies under the protected %s" % r)
    for k in API_ENV:
        if env.get(k):
            R.append("%s is set: no separately billed API path is allowed; unset it" % k)
    if env.get("RNPLENS_CODEX_CALLS"):
        R.append("RNPLENS_CODEX_CALLS is set: this driver chooses its own fresh calls folder under %s; unset it" % LIVE_ROOT)
    if (env.get("RNPLENS_LLM") or "").lower() in ("0", "off", "false", "no"):
        R.append("RNPLENS_LLM switches the language-model functions off")
    root = hooks.get("calls_root") or LIVE_ROOT
    if not hooks.get("calls_root") and os.path.realpath(root) != os.path.realpath(LIVE_ROOT):
        R.append("calls root must be %s" % LIVE_ROOT)
    for r in FORBIDDEN_ROOTS:
        if _under(root, r):
            R.append("calls root lies under the protected/frozen %s" % r)
    if not os.path.isdir(os.path.dirname(os.path.abspath(root))):
        R.append("the parent of the calls root %s does not exist" % root)
    ctx["calls_root"] = root
    R += task_refusals(a.tasks, S)
    if not a.run_id or not RUN_ID_RE.match(a.run_id):
        R.append("--run-id must match %s" % RUN_ID_RE.pattern)
    run_dir = os.path.join(root, a.run_id or "_")
    ctx["run_dir"] = run_dir
    if os.path.exists(os.path.join(root, "LIVE.lock")):
        R.append("another invocation holds %s (or a crashed one left it: inspect before removing it by hand)" % os.path.join(root, "LIVE.lock"))
    used = ledger_attempts(root) if os.path.isdir(root) else 0
    ctx["ledger_attempts"] = used
    if used >= LEDGER_CAP:
        R.append("the ledger records %d call attempts: the %d-call authorisation is used up" % (used, LEDGER_CAP))
    if mode == "first":
        if os.path.exists(run_dir):
            R.append("run %s already exists: a stopped or finished run is never resumed; choose a new run id" % a.run_id)
        aborted = sorted({e["run_id"] for e in (ledger(root) if os.path.isdir(root) else []) if e.get("event") == "run_aborted"
                          and e.get("kind") in ("CREDIT_BALANCE_CHANGED", "BALANCE_UNREADABLE")})
        missing = [x for x in aborted if conf is None or x not in conf.get("acknowledge_abort", [])]
        if missing:
            R.append("earlier run(s) %s stopped on the credit balance; the confirmation must acknowledge each "
                     "(acknowledge_abort: <run id>) after the owner has checked the balance" % ", ".join(missing))
    else:
        rec_p = os.path.join(run_dir, "run_record.json")
        if not os.path.isfile(rec_p):
            R.append("run %s has no run record: nothing to continue" % a.run_id)
        else:
            rec = json.load(open(rec_p, encoding="utf-8"))
            ctx["record"] = rec
            if rec.get("state") != "PAUSED_AFTER_FIRST_CALL":
                R.append("run %s is in state %s, not PAUSED_AFTER_FIRST_CALL: it is never resumed; start a new run id"
                         % (a.run_id, rec.get("state")))
            elif len(rec.get("calls") or []) != 1:
                R.append("run %s records %d calls, not exactly one" % (a.run_id, len(rec.get("calls") or [])))
            else:
                base = rec["baseline"]
                last = rec["calls"][0].get("post_reading") or {}
                pr = reading_problems(last, parse_decimal(base["balance"]), base["weekly_used_percent"])
                if pr:
                    R.append("the first call's reading fails the guards: %s" % "; ".join("%s: %s" % x for x in pr))
                ga, gr = parse_go_ahead(getattr(a, "go_ahead", None), today, rec, parse_decimal(base["balance"]), base["weekly_used_percent"])
                R += gr
                ctx["go_ahead"] = ga
                if conf and (parse_decimal(conf.get("credit_balance")) != parse_decimal(base["balance"])
                             or conf.get("weekly_usage_percent_value") != base["weekly_used_percent"]):
                    R.append("the confirmation's balance/usage (%s, %s) differ from the run's recorded baseline (%s, %s)"
                             % (conf.get("credit_balance"), conf.get("weekly_usage_percent"), base["balance"], base["weekly_used_percent"]))
    if not R:
        from rnplens import doctor
        ready, reasons = (hooks.get("agent_status") or doctor.agent_status)()
        if not ready:
            R.append("rnplens doctor --agent is not READY: %s" % "; ".join(reasons))
    return R, ctx


# ---------------------------------------------------------------- the live guard around every Codex call
DEFECT_KINDS = ("PRIVACY_GATE", "SCENARIO_CALL_LIMIT", "NO_SCENARIO")    # a guard stop that is itself a hard failure


_GUARD = None
_ORIG_RUN = None
_ORIG_LLM_INIT = None


def _guarded_run(client, kind, prompt, schema, extra_args=(), call_files=None, call_dir=None):
    from rnplens_assistant import codex_llm
    g = _GUARD
    if g is None:
        raise codex_llm.UsageGuard("LIVE_GUARD: no live guard installed in this process; the call was refused")
    entry = g.before(client, kind, prompt, schema, extra_args, call_files)
    cd = call_dir or client.new_call_dir(kind)
    entry["call_dir"] = cd
    entry["call_dir_clean"] = not os.listdir(cd)
    g.attempt(entry)
    err, out = None, None
    try:
        out = _ORIG_RUN(client, kind, prompt, schema, extra_args, call_files, cd)
    except Exception as ex:          # never retried
        err = ex
    g.after(entry, cd, err, out)
    if err is not None:
        raise err
    return out


def _blocked_llm_init(self, *a, **k):
    raise RuntimeError("LIVE_QUALIFICATION_v1: the separately billed API client (rnplens_assistant.llm.Client) is disabled")


class Guard:
    def __init__(self, run, mode, out=print, hooks=None):
        self.run, self.mode, self.out, self.hooks = run, mode, out, hooks or {}
        base = run.rec["baseline"]
        self.base_balance, self.base_weekly = parse_decimal(base["balance"]), base["weekly_used_percent"]
        self.calls_invocation = 0
        self.scenario = None
        self.abort = None
        self.paused = False
        # Amendment 1: the owner-stated baseline as a full reading (the bare baseline record lacks rate_limits_present)
        self.last_reading = (run.rec["calls"][-1].get("post_reading") if run.rec["calls"] else None) or dict(
            base, source="owner confirmation (Codex Usage & Billing, before the run)", rate_limits_present=True, windows={},
            model_returned=MODEL)

    def set_scenario(self, sid, max_calls, checker=None, privacy_ctx=None, phase="scenario"):
        self.scenario = {"id": sid, "max_calls": max_calls, "calls": 0, "checker": checker, "privacy": privacy_ctx or {},
                         "phase": phase, "last_out": None}

    def _refuse(self, entry, kind, detail, abort=True):
        from rnplens_assistant import codex_llm
        entry.update(refused=True, refusal={"kind": kind, "detail": detail})
        self.run.rec["refused_calls"].append(entry)
        if abort and not self.abort:
            self.abort = {"kind": kind, "detail": detail, "scenario": (self.scenario or {}).get("id"), "before_call": True}
        self.run.save()
        self.out("LIVE GUARD: call refused before sending (%s: %s)" % (kind, detail))
        raise codex_llm.UsageGuard("LIVE_GUARD %s: %s" % (kind, detail))

    def before(self, client, kind, prompt, schema, extra_args, call_files):
        sc = self.scenario or {}
        entry = {"index": len(self.run.rec["calls"]) + 1, "scenario": sc.get("id"), "phase": sc.get("phase"), "kind": kind,
                 "prompt_sha256": sha_text(prompt), "prompt_bytes": len(prompt.encode("utf-8")),
                 "pre_reading": self.last_reading, "pre_checked_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
        if self.abort:
            self._refuse(entry, "RUN_ABORTED", "the run was already stopped (%s)" % self.abort["kind"], abort=False)
        if self.mode == "first" and self.calls_invocation >= 1:
            self.paused = True
            self._refuse(entry, "FIRST_CALL_PAUSE", "the first invocation makes exactly one call", abort=False)
        if not sc:
            self._refuse(entry, "NO_SCENARIO", "a call outside any scenario")
        auth = self.run.rec.get("authorisation_bound") or {}
        if auth:                                       # Amendment 8: the authorised experiment only
            if self.calls_invocation >= int(auth["values"]["max_model_calls"]):
                self._refuse(entry, "AUTHORISATION", "the authorisation allows %s model call(s) in this invocation"
                             % auth["values"]["max_model_calls"])
            want = auth["scenario_payloads"].get(sc.get("id"))
            if kind == "plan" and want and sha_text(prompt) != want:
                self._refuse(entry, "AUTHORISATION", "the %s planning payload is not the authorised payload" % sc.get("id"))
        if sc["calls"] >= sc["max_calls"]:
            self._refuse(entry, "SCENARIO_CALL_LIMIT", "scenario %s (%s) allows %d call(s)" % (sc["id"], sc["phase"], sc["max_calls"]))
        now = (self.hooks.get("now") or (lambda: datetime.datetime.now(datetime.timezone.utc)))()
        cr, today = clock_refusals(now, (self.hooks.get("ntp") or ntp_status)())
        if cr or today != self.run.rec["confirmation"]["date"]:
            self._refuse(entry, "CLOCK", "; ".join(cr) or "the Canberra date changed during the run (%s)" % today)
        if ledger_attempts(self.run.root) >= LEDGER_CAP:
            self._refuse(entry, "BUDGET", "the %d-call ledger cap is reached" % LEDGER_CAP)
        cfg = getattr(client, "config", {}) or {}
        if cfg.get("model") != MODEL or cfg.get("reasoning_effort") != EFFORT:
            self._refuse(entry, "WRONG_MODEL", "client configured for %s/%s" % (cfg.get("model"), cfg.get("reasoning_effort")))
        if call_files or tuple(extra_args or ()):
            self._refuse(entry, "PRIVACY_GATE", "files or extra arguments were attached to the call")
        pr = reading_problems(self.last_reading, self.base_balance, self.base_weekly)
        if pr:
            self._refuse(entry, pr[0][0], "pre-call reading: " + "; ".join("%s: %s" % x for x in pr))
        want_schema = expected_schema(kind)
        if want_schema is None or json.dumps(schema, sort_keys=True) != json.dumps(want_schema, sort_keys=True):
            self._refuse(entry, "PRIVACY_GATE", "unexpected schema for a %r call" % kind)
        findings = privacy.gate(prompt, **sc["privacy"])
        entry["privacy_findings"] = findings
        if sc.get("checker"):
            ok, detail = sc["checker"](kind, prompt, sc.get("last_out"))
            entry["exact_bytes_ok"], entry["exact_bytes_detail"] = ok, detail
        else:
            ok = False
            entry["exact_bytes_ok"], entry["exact_bytes_detail"] = False, "no expected-payload checker for this scenario"
        sent = os.path.join(self.run.dir, "sent", "%03d_%s_%s.txt" % (entry["index"], sc["id"], kind))
        os.makedirs(os.path.dirname(sent), exist_ok=True)
        from rnplens import provenance as pv
        pv.atomic_write_bytes(sent, prompt.encode("utf-8"))
        entry["sent_copy"] = os.path.relpath(sent, self.run.dir)
        if findings or not ok:
            self._refuse(entry, "PRIVACY_GATE", "; ".join(findings + ([] if ok else [entry["exact_bytes_detail"]])))
        self.out("[call %d] %s %s: before: balance %s, weekly usage %s%% (%s)" % (
            entry["index"], sc["id"], kind, self.last_reading.get("balance"), self.last_reading.get("weekly_used_percent"),
            self.last_reading.get("source")))
        return entry

    def attempt(self, entry):
        ledger_append(self.run.root, {"event": "call_attempt", "run_id": self.run.id, "index": entry["index"],
                                      "scenario": entry["scenario"], "kind": entry["kind"]})
        self.run.rec["calls"].append(entry)
        self.calls_invocation += 1
        self.scenario["calls"] += 1
        self.run.save()

    def after(self, entry, cd, err, out):
        from rnplens_assistant import codex_llm
        s = codex_llm.read_session(cd)
        r = reading_from_session(s)
        entry["post_reading"] = r
        entry["error"] = None if err is None else "%s: %s" % (type(err).__name__, str(err)[:500])
        entry["completed_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        entry["call_dir_files"] = sorted(os.listdir(cd))
        P = reading_problems(r, self.base_balance, self.base_weekly)
        if err is not None:
            P.insert(0, ("CALL_FAILED", entry["error"]))
        self.last_reading = r
        self.scenario["last_out"] = out
        ledger_append(self.run.root, {"event": "call_result", "run_id": self.run.id, "index": entry["index"],
                                      "balance": r.get("balance"), "weekly_used_percent": r.get("weekly_used_percent"),
                                      "model_returned": r.get("model_returned"), "error": entry["error"], "problems": [p[0] for p in P]})
        self.out("[call %d] after: balance %s (baseline %s), weekly usage %s%% (start %s%%), model %s%s" % (
            entry["index"], r.get("balance"), self.base_balance, r.get("weekly_used_percent"), self.base_weekly,
            r.get("model_returned"), "" if not P else "  -> ABORT: " + "; ".join("%s: %s" % p for p in P)))
        if P:
            self.abort = {"kind": P[0][0], "detail": "; ".join("%s: %s" % p for p in P), "scenario": entry["scenario"],
                          "after_call": entry["index"]}
            entry["abort"] = self.abort
            self.run.save()
            raise codex_llm.UsageGuard("LIVE_GUARD %s: %s" % (P[0][0], P[0][1]))
        self.run.save()


def expected_schema(kind):
    from rnplens_assistant import ask, followup
    if kind in ("plan", "replan"):
        return ask.PLAN_SCHEMA
    if kind in ("followup", "followup_replan"):
        return followup.FOLLOWUP_SCHEMA
    return None


def install(guard):
    global _GUARD, _ORIG_RUN, _ORIG_LLM_INIT
    from rnplens_assistant import codex_llm, llm
    if _ORIG_RUN is None:
        _ORIG_RUN = codex_llm.CodexClient.run
        _ORIG_LLM_INIT = llm.Client.__init__
    codex_llm.CodexClient.run = _guarded_run
    llm.Client.__init__ = _blocked_llm_init
    _GUARD = guard


def uninstall():
    global _GUARD
    from rnplens_assistant import codex_llm, llm
    if _ORIG_RUN is not None:
        codex_llm.CodexClient.run = _ORIG_RUN
        llm.Client.__init__ = _ORIG_LLM_INIT
    _GUARD = None


class Run:
    def __init__(self, root, run_id, rec=None):
        self.root, self.id = root, run_id
        self.dir = os.path.join(root, run_id)
        self.rec = rec

    def save(self):
        write_json(os.path.join(self.dir, "run_record.json"), self.rec)

    def log(self, event, **kw):
        with open(os.path.join(self.dir, "run_log.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(kw, event=event, ts_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")),
                                sort_keys=True, default=str) + "\n")


# ---------------------------------------------------------------- the declared payloads, reconstructed independently
STRUCT_EXT = (".pdb", ".cif", ".mmcif", ".ent", ".pdb.gz", ".cif.gz")
FASTA_EXT = (".fasta", ".fa", ".faa", ".fna", ".fas")


def expected_nl_payload(question, task_dir):
    """(system, user) of the planner's first call as declared by assist.NL_PRIVACY after Amendment 4: the question, opaque
    identifiers for the task's folders and files, whether a reference is supplied (identifier only) and the RNPLens
    documentation. Built here from the prompt files and the declared rule, not by calling the assistant's code. The
    questions of this suite contain no file or folder name, so the question is expected unchanged."""
    from rnplens_assistant.ask import AVAILABILITY_NOTE
    pkg = os.path.join(ASSISTANT, "rnplens_assistant")
    planner = open(os.path.join(pkg, "prompts", "planner.md"), encoding="utf-8").read()
    guide = open(os.path.join(pkg, "docs", "which_analysis_should_i_use.md"), encoding="utf-8").read()
    system = planner + "\n\n# RNPLens documentation (which analysis to use)\n\n" + AVAILABILITY_NOTE + guide
    tj = os.path.join(task_dir, "task.json")
    refs = (json.load(open(tj, encoding="utf-8")).get("reference_files") or []) if os.path.isfile(tj) else []
    key = lambda s: (s.lower(), s)
    tops = sorted((e for e in os.listdir(task_dir) if not e.startswith(".") and e != "task.json"), key=key)
    lines = []
    dirs = [e for e in tops if os.path.isdir(os.path.join(task_dir, e))]
    for i, d in enumerate(dirs, 1):
        rels = []
        for dp, dn, fn in os.walk(os.path.join(task_dir, d)):
            dn[:] = [x for x in dn if not x.startswith(".")]
            rels += [os.path.relpath(os.path.join(dp, f), task_dir) for f in fn if not f.startswith(".")]
        nc = nf = 0
        for r in sorted(set(rels), key=key):
            if r.lower().endswith(STRUCT_EXT):
                nc += 1
                lines.append("run_%03d/candidate_%03d" % (i, nc))
            else:
                nf += 1
                lines.append("run_%03d/file_%03d" % (i, nf))
    kinds = {}
    for f in [e for e in tops if e not in dirs]:
        if f in refs or not f.lower().endswith(FASTA_EXT):
            continue
        seq = "".join(l.strip() for l in open(os.path.join(task_dir, f), encoding="utf-8", errors="replace") if l.strip() and not l.startswith(">")).upper()
        k = "rna_sequence" if seq and set(seq) <= set("ACGUTN") else ("protein_sequence" if seq else "sequence")
        kinds[k] = kinds.get(k, 0) + 1
        lines.append("%s_%03d" % (k, kinds[k]))
    ref_ids = ["reference_%03d" % i for i in range(1, len(refs) + 1)]
    user = ("Question:\n%s\n\nTask inputs (%d files; opaque identifiers, the real names stay on this computer; use these "
            "identifiers as the paths in the plan):\n%s\n\nExperimental reference supplied with this task: %s\n"
            % (question, len(lines), "\n".join(lines[:300]),
               ("yes (%s); reference-based metrics are available" % ", ".join(ref_ids)) if ref_ids else "none"))
    return system, user


TARGET_RX = re.compile(r"(?<![A-Za-z0-9])([0-9][A-Za-z0-9]{3})(?=[_.]|$)")


def real_names(*roots):
    """Every name an input or output could reveal (Amendment 4): relative paths, basenames, name-like stems, folder
    names and target IDs found in file names. Names shorter than four characters are not listed."""
    out = set()
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        out.add(os.path.basename(os.path.abspath(root)))
        for dp, dn, fn in os.walk(root):
            dn[:] = [x for x in dn if not x.startswith(".")]
            for x in dn + fn:
                rel = os.path.relpath(os.path.join(dp, x), root)
                stem = x.split(".")[0]
                out.update({rel, x})
                if re.search(r"[0-9_]", stem):
                    out.add(stem)
                out.update(TARGET_RX.findall(stem))
    return {n for n in out if len(n) >= 4}


def manifest_names(project):
    out = set()
    p = os.path.join(project, "manifest.json")
    if os.path.isfile(p):
        man = json.load(open(p, encoding="utf-8"))
        for r in man.get("runs") or []:
            out.add(r.get("run") or "")
        for s in man.get("structures") or []:
            out.add(s.get("sample") or "")
            for k in ("used_path", "path", "original_path"):
                if s.get(k):
                    b = os.path.basename(s[k])
                    out.update({b, b.split(".")[0]})
                    out.update(TARGET_RX.findall(b.split(".")[0]))
    return {n for n in out if len(n) >= 4}


REPLAN_LINE = re.compile(r"^- step \d+ \([^)]*\): P\d+ .*$")


def nl_checker(question, task_dir):
    system, user = expected_nl_payload(question, task_dir)
    first = system + "\n\n---\n\n" + user

    def check(kind, prompt, last_out):
        if kind == "plan":
            return (prompt == first), ("equals the declared payload" if prompt == first else "differs from the declared planner payload")
        if kind == "replan":
            head = first + "\n\nYour previous plan:\n"
            if not prompt.startswith(head) or last_out is None:
                return False, "replan payload does not extend the declared payload"
            rest = prompt[len(head):]
            prev = json.dumps(last_out)
            if not rest.startswith(prev + "\n\nThe policy rejected these steps:\n") or not rest.endswith("\nReturn a corrected plan."):
                return False, "replan payload carries more than the previous plan and the policy's rejections"
            mid = rest[len(prev + "\n\nThe policy rejected these steps:\n"):-len("\nReturn a corrected plan.")]
            bad = [l for l in mid.split("\n") if not REPLAN_LINE.match(l)]
            return (not bad), ("replan: previous plan + %d policy line(s)" % len(mid.split("\n")) if not bad else "unexpected replan line %r" % bad[0][:80])
        return False, "unexpected call kind %r in a planner scenario" % kind
    return check, system


def followup_checker(question, analysis):
    from rnplens_assistant import followup as F
    system = F.prompt_system()

    def latest_summary():
        cand = sorted(glob_(os.path.join(analysis, "followup", "fu_*", "evidence_summary.json")))
        return open(cand[-1], encoding="utf-8").read() if cand else None

    def check(kind, prompt, last_out):
        sm = latest_summary()
        if sm is None:
            return False, "no evidence summary written before the call"
        base = system + "\n\n---\n\n" + F.prompt_user(question, sm)
        if kind == "followup":
            return (prompt == base), ("equals the declared follow-up payload" if prompt == base else "differs from the declared follow-up payload")
        if kind == "followup_replan":
            ok = prompt.startswith(base + "\nYour previous proposal:\n") and "The RNPLens policy rejected it: F" in prompt
            return ok, ("replan: declared payload + policy feedback" if ok else "replan payload carries unexpected content")
        return False, "unexpected call kind %r in a follow-up scenario" % kind
    return check, system


def glob_(pattern):
    import glob
    return glob.glob(pattern)


def privacy_ctx(task_dir, system, extra_forbidden, names=()):
    seqs = privacy.fasta_sequences([os.path.join(task_dir, "protein.fasta"), os.path.join(task_dir, "rna.fasta")])
    content = privacy.file_lines(list(privacy.text_files([task_dir])))
    forb = set(x for x in extra_forbidden if x) | set(names)            # Amendment 4: no real name may be sent
    forb = {n for n in forb if n not in system}                         # (none of them occurs in the fixed documentation)
    return {"sequences": seqs, "content_lines": sorted(content), "allowed_lines": sorted(set(l.strip() for l in system.splitlines())),
            "forbidden_strings": sorted(forb)}


# ---------------------------------------------------------------- scenarios
class Ctx:
    def __init__(self, run, guard, tasks, S, fu, hooks, out):
        self.run, self.guard, self.tasks, self.S, self.fu, self.hooks, self.out = run, guard, tasks, S, fu, hooks, out


def _quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        r = fn(*a, **k)
    return r, buf.getvalue()


def _setup(c, sid, task):
    work = os.path.join(c.run.dir, "work", sid)
    os.makedirs(work)
    c.guard.set_scenario(sid, 0, phase="setup")
    P, A = c.fu["run_part2"].setup_task(os.path.join(c.tasks, task), work)
    return work, P, A


def _abs_forbidden(c, work):
    return [c.run.dir, work, os.path.realpath(c.tasks), RNPBENCH, os.path.expanduser("~") + "/"]


def run_z(c, s):
    from rnplens import assist
    from rnplens_assistant import consent
    work, P, A = _setup(c, s["id"], s["task"])
    obs = {"calls_before": len(c.run.rec["calls"])}
    if s["id"] == "Z1":
        task_nl = os.path.join(work, "task_nl")
        shutil.copytree(os.path.join(c.tasks, s["task"]), task_nl)
        c.guard.set_scenario(s["id"], 0, phase="scenario")
        old = os.environ.get("RNPLENS_LLM")
        os.environ["RNPLENS_LLM"] = "off"
        try:
            lines = []
            rc = assist.main(["--project", P, "--analysis", A, "--nl", s["question"], "--task", task_nl, "--nl-out", os.path.join(work, "nl")],
                             ask=lambda p: "", out=lambda *x: lines.append(" ".join(str(y) for y in x)))
        finally:
            if old is None:
                os.environ.pop("RNPLENS_LLM", None)
            else:
                os.environ["RNPLENS_LLM"] = old
        obs.update(rc=rc, nl_run_dir_created=os.path.exists(os.path.join(work, "nl")), output_tail=lines[-6:])
    else:
        rr = c.fu["run_part2"]._auto_range(A)
        rc0, _ = _quiet(assist.main, ["--project", P, "--analysis", A, "--item", "C", "--rna", rr, "--runs", "run_A,run_B", "--json"], out=NOOP)
        assert rc0 == 0, "item C failed in Z2 setup"
        consent.opt_in(P, "--yes")
        consent.opt_out(P, "--yes")
        c.guard.set_scenario(s["id"], 0, phase="scenario")
        man = assist.load_manifest(P)
        ctx = {"project": os.path.abspath(P), "analysis": os.path.abspath(A), "manifest": man}
        rc, _ = _quiet(assist.followup, ctx, "codex", question=s["question"], yes=True, ask=None, out=NOOP,
                       initial={"kind": "menu_item", "capability": "region_run_comparison"})
        recs = sorted(glob_(os.path.join(A, "followup", "fu_*", "followup_record.json")))
        fr = json.load(open(recs[-1], encoding="utf-8")) if recs else {}
        obs.update(rc=rc, followup_stop=(fr.get("stop") or {}).get("kind"), followup_model_calls=fr.get("model_calls_made"))
    obs["calls_made"] = len(c.run.rec["calls"]) - obs.pop("calls_before") + len([x for x in c.run.rec["refused_calls"] if x.get("scenario") == s["id"]])
    return obs


def run_p(c, s):
    from rnplens import assist
    from rnplens_assistant import followup as F, replay
    work, P, A = _setup(c, s["id"], s["task"])
    task_nl = os.path.join(work, "task_nl")
    shutil.copytree(os.path.join(c.tasks, s["task"]), task_nl)
    check, system = nl_checker(s["question"], task_nl)
    c.guard.set_scenario(s["id"], s["max_calls"], checker=check, phase="scenario",
                         privacy_ctx=privacy_ctx(task_nl, system, _abs_forbidden(c, work), real_names(task_nl) | {s["task"]}))
    nl = os.path.join(work, "nl")
    argv = ["--project", P, "--analysis", A, "--nl", s["question"], "--task", task_nl, "--nl-out", nl]
    if s.get("followup") == "codex_no_consent":
        argv += ["--followup", "codex", "--yes"]
    obs = {}
    lines = []
    from rnplens_assistant import codex_llm
    try:
        obs["rc"] = assist.main(argv, ask=lambda p: "", out=lambda *x: lines.append(" ".join(str(y) for y in x)))
    except codex_llm.UsageGuard as ex:
        obs["incomplete"] = "INCOMPLETE_FIRST_CALL_PAUSE" if c.guard.paused and not c.guard.abort else "GUARD_STOP: %s" % ex
    except Exception as ex:          # an RNPLens defect: recorded, scored as H4 failure
        obs["rc"] = "exception %s: %s" % (type(ex).__name__, str(ex)[:300])
    obs["calls"] = [x for x in c.run.rec["calls"] if x.get("scenario") == s["id"]] + \
                   [x for x in c.run.rec["refused_calls"] if x.get("scenario") == s["id"] and x["refusal"]["kind"] == "PRIVACY_GATE"]
    obs["output_tail"] = lines[-8:]
    if obs.get("incomplete"):
        return obs
    rp = os.path.join(nl, "run_record.json")
    if os.path.isfile(rp):
        obs["record"] = json.load(open(rp, encoding="utf-8"))
        obs["answer_json"] = json.load(open(os.path.join(nl, "answer.json"), encoding="utf-8"))
        obs["answer_md"] = open(os.path.join(nl, "answer.md"), encoding="utf-8").read()
        found = F.from_assistant_run(nl)
        if found:
            recs = sorted(glob_(os.path.join(found[1], "followup", "fu_*", "followup_record.json")))
            obs["followup_record"] = json.load(open(recs[-1], encoding="utf-8")) if recs else None
        c.guard.set_scenario(s["id"], 0, phase="replay")
        h, _log = replay.run(os.path.join(nl, "plan.json"), task_nl, os.path.join(work, "replay"))
        obs["replay_hash"] = h
    return obs


def run_f(c, sid):
    from rnplens import assist
    from rnplens_assistant import codex_llm, consent, followup as F, replay
    lid = sid.split("-", 1)[1]
    S2 = json.load(open(os.path.join(ROOT, c.S["part_F"]["source"]), encoding="utf-8"))
    s = next(x for x in S2["scenarios"] if x["id"] == lid)
    work, P, A = _setup(c, sid, s["task"])
    initial = {"kind": "menu_item", "capability": "interface_overview"}
    if s["initial"]["item"] == "C":
        rr = c.fu["run_part2"]._auto_range(A)
        rc0, _ = _quiet(assist.main, ["--project", P, "--analysis", A, "--item", "C", "--rna", rr, "--runs", "run_A,run_B", "--json"], out=NOOP)
        assert rc0 == 0, "item C failed in %s setup" % sid
        initial = {"kind": "menu_item", "capability": "region_run_comparison"}
    consent.opt_in(P, "--yes")
    check, system = followup_checker(s["question"], A)
    pctx = privacy_ctx(os.path.join(work, "task"), system, _abs_forbidden(c, work) + ([s["reference_file"]] if s.get("reference_file") else []),
                       real_names(os.path.join(work, "task")) | manifest_names(P) | {s["task"], "summary.json", "region.json"}
                       | {d for d in os.listdir(A) if d.startswith("region_")})
    c.guard.set_scenario(sid, c.S["part_F"]["max_calls_each"], checker=check, phase="scenario", privacy_ctx=pctx)
    wk = min(c.guard.base_weekly + WEEKLY_MAX_RISE, USAGE_CEILING)
    factory = lambda: codex_llm.CodexClient("lq1_%s" % lid, config={"weekly_guard_percent": wk})
    rec, _ = _quiet(F.run, P, A, s["question"], mode="codex", initial=initial, yes=True, ask=None, out=NOOP, client_factory=factory)
    obs = {"scenario": s, "record": rec}
    obs["answer_md"] = open(os.path.join(A, rec["dir"], "followup_answer.md"), encoding="utf-8").read()
    obs["calls"] = [x for x in c.run.rec["calls"] if x.get("scenario") == sid] + \
                   [x for x in c.run.rec["refused_calls"] if x.get("scenario") == sid and x["refusal"]["kind"] == "PRIVACY_GATE"]
    if (rec.get("stop") or {}).get("kind") == "USAGE_GUARD" and c.guard.paused and not c.guard.abort:
        obs["incomplete"] = "INCOMPLETE_FIRST_CALL_PAUSE"
        return obs
    c.guard.set_scenario(sid, 0, phase="replay")
    h, _log, ok = replay.run_followup(os.path.join(A, rec["dir"], "followup_plan.json"), P, A)
    obs["replay_matches"] = ok
    return obs


def score_one(c, sid, obs):
    from rnplens.trace import wording_audit
    S = c.S
    if sid.startswith("Z"):
        return score_live.score_z(next(x for x in S["part_Z"] if x["id"] == sid), obs)
    if sid.startswith("P"):
        s = dict(next(x for x in S["part_P"] if x["id"] == sid), _blocked_catalogue=S["blocked_capabilities"])
        return score_live.score_p(s, obs, c.fu["score"].forbidden_hits, wording_audit)
    return score_live.score_f(obs.get("scenario"), obs, c.fu["score"].score_part2)


def run_scenario(c, sid):
    t0 = time.time()
    c.out("== %s" % sid)
    c.run.log("scenario_start", scenario=sid)
    try:
        if sid.startswith("Z"):
            obs = run_z(c, next(x for x in c.S["part_Z"] if x["id"] == sid))
        elif sid.startswith("P"):
            obs = run_p(c, next(x for x in c.S["part_P"] if x["id"] == sid))
        else:
            obs = run_f(c, sid)
    except Exception as ex:
        if c.guard.abort:
            obs = {"incomplete": "GUARD_STOP: %s" % c.guard.abort["kind"], "calls": [x for x in c.run.rec["calls"] if x.get("scenario") == sid]}
        else:
            obs = {"rc": "exception %s: %s" % (type(ex).__name__, str(ex)[:300]), "setup_error": True,
                   "calls": [x for x in c.run.rec["calls"] if x.get("scenario") == sid]}
    if c.guard.abort and not obs.get("incomplete") and c.guard.abort.get("scenario") == sid:
        obs["incomplete"] = "GUARD_STOP: %s" % c.guard.abort["kind"]
    if obs.get("setup_error"):
        sc = {"status": "COMPLETED", "hard": {"setup": False}, "hard_pass": False, "error": obs["rc"]}
    else:
        try:
            sc = score_one(c, sid, obs)
        except Exception as ex:
            sc = {"status": "COMPLETED", "hard": {"scoring": False}, "hard_pass": False, "error": "%s: %s" % (type(ex).__name__, ex)}
    if c.guard.abort and c.guard.abort.get("scenario") == sid and c.guard.abort["kind"] in DEFECT_KINDS:
        sc = dict(sc, status="COMPLETED", hard_pass=False,
                  hard=dict(sc.get("hard") or {}, **{"guard_defect_" + c.guard.abort["kind"]: False}))
    sc["wall_s"] = round(time.time() - t0, 1)
    sc["calls"] = len([x for x in c.run.rec["calls"] if x.get("scenario") == sid])
    c.run.rec["scenarios"][sid] = sc
    keep = {k: v for k, v in obs.items() if k not in ("record", "answer_json", "scenario", "calls", "followup_record", "answer_md")}
    if obs.get("followup_record"):
        keep["followup_stop"] = (obs["followup_record"].get("stop") or {}).get("kind")
        keep["followup_model_calls"] = obs["followup_record"].get("model_calls_made")
    if obs.get("record") and sid.startswith("F-"):
        keep["followup_stop"] = (obs["record"].get("stop") or {}).get("kind")
        keep["followup_dir"] = obs["record"].get("dir")
    c.run.rec.setdefault("observations", {})[sid] = keep
    c.run.save()
    c.run.log("scenario_end", scenario=sid, status=sc.get("status"), hard_pass=sc.get("hard_pass"))
    c.out("   %s %s hard=%s tool_selection=%s calls=%d" % (sid, sc.get("status"), sc.get("hard_pass"), sc.get("tool_selection_pass"), sc["calls"]))
    return sc


def finish(c, state, reason=None):
    S = c.S
    c.run.rec["state"] = state
    if reason:
        c.run.rec["stop"] = reason
        if reason.get("kind"):
            ledger_append(c.run.root, {"event": "run_aborted" if state == "ABORTED" else "run_stopped", "run_id": c.run.id, "kind": reason["kind"]})
    v = score_live.verdict(S["order"], c.run.rec["scenarios"], [x["id"] for x in S["part_P"]])
    c.run.rec["verdict"] = v
    c.run.rec["ended_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    c.run.save()
    write_json(os.path.join(c.run.dir, "results.json"), {"suite": SUITE, "run_id": c.run.id, "state": state, "verdict": v,
                                                          "scenarios": c.run.rec["scenarios"], "calls": len(c.run.rec["calls"]),
                                                          "stop": reason})


def plan_doc(S):
    return {"suite": SUITE, "order": S["order"], "budget": S["budget"], "first_call_scenario": S["first_call_scenario"],
            "guards": {"env": "%s=%s or %s" % (LIVE_ENV, LIVE_TOKEN, LIVE_TOKEN_BLOCK), "confirmation": "--confirmation FILE (header %r; date, statement, credit_balance, weekly_usage_percent, and the Amendment 8 authorisation fields %s)" % (CONFIRM_HEADER, ", ".join(AUTH_KEYS)),
                       "date_block": "%s .. %s %s, +/- %s" % (BLOCK_FROM, BLOCK_TO, TZ, BLOCK_MARGIN), "calls_root": LIVE_ROOT,
                       "weekly_usage": "<= start + %.0f points and < %.0f%%" % (WEEKLY_MAX_RISE, USAGE_CEILING),
                       "balance": "any change from the confirmation's credit_balance aborts", "model": MODEL, "ledger_cap": LEDGER_CAP,
                       "go_ahead": "--continue-after-first needs --go-ahead FILE (header %r; date, run_id, first_call_digest, "
                                   "observed_credit_balance == baseline, observed_weekly_usage_percent, statement)" % GO_AHEAD_HEADER}}


def main(argv=None, hooks=None, out=print):
    """hooks (Python API only, for the mocked tests; the command line cannot set them): now, ntp, agent_status,
    calls_root, skip_git_clean, jail_any."""
    hooks = hooks or {}
    ap = argparse.ArgumentParser(prog="run_live.py")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true", help="print the plan and the guards; no call, nothing written")
    g.add_argument("--first-call", action="store_true", help="make exactly one live call, then stop")
    g.add_argument("--continue-after-first", action="store_true", help="continue a run paused after its first call")
    ap.add_argument("--run-id"); ap.add_argument("--confirmation"); ap.add_argument("--tasks", default=DEFAULT_TASKS)
    ap.add_argument("--go-ahead", help="with --continue-after-first: the owner's go-ahead file (Amendment 4)")
    a = ap.parse_args(argv)
    S = load_scenarios()
    out(json.dumps(plan_doc(S), indent=1))
    if a.plan:
        if a.run_id:                              # Amendment 8: the exact values an authorisation must name
            head = git_state()[0]
            rt = (hooks.get("runtime_hashes") or runtime_hashes)()
            out(json.dumps({"authorisation_values": {MODE_NAMES[m]: authorisation_values(m, a.run_id, a.tasks, S, head, rt)[0]
                                                     for m in ("first", "continue")}}, indent=1))
        return 0
    mode = "first" if a.first_call else "continue"
    refusals, pre = preflight(mode, a, os.environ, hooks, S)
    if refusals:
        out("REFUSING (%s): nothing was created and no call was made:\n%s" % (mode, "\n".join("  - " + r for r in refusals)))
        return 3
    root = pre["calls_root"]
    os.makedirs(root, exist_ok=True)
    lock = os.path.join(root, "LIVE.lock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, ("%d %s %s" % (os.getpid(), a.run_id, mode)).encode()); os.close(fd)
    from rnplens_assistant import codex_llm
    old_calls_root = codex_llm.CALLS_ROOT
    patched = []
    try:
        conf = pre["confirmation"]
        if mode == "first":
            os.makedirs(pre["run_dir"])
            rec = {"suite": SUITE, "run_id": a.run_id, "state": "FIRST_CALL_RUNNING", "created_utc": pre["now_utc"],
                   "git_head": pre.get("git_head"), "freeze_sha256": sha_file(os.path.join(HERE, "FREEZE.md")),
                   "confirmation": {k: conf[k] for k in ("path", "sha256", "date", "credit_balance", "weekly_usage_percent", "acknowledge_abort")},
                   "precondition": conf.get("precondition"),
                   "authorisation_bound": pre.get("authorisation"),
                   "baseline": {"balance": str(parse_decimal(conf["credit_balance"])), "weekly_used_percent": conf["weekly_usage_percent_value"],
                                "source": "owner confirmation"},
                   "model": MODEL, "tasks": os.path.realpath(a.tasks), "invocations": [], "calls": [], "refused_calls": [],
                   "scenarios": {}, "codex_jail": os.path.realpath(codex_llm.JAIL), "python": sys.version.split()[0],
                   "privacy_gate_limits": "RNA constructs shorter than %d nt are not checked by K-mers" % privacy.K}
            run = Run(root, a.run_id, rec)
            todo = S["order"][:S["order"].index(S["first_call_scenario"]) + 1]
        else:
            run = Run(root, a.run_id, pre["record"])
            run.rec["state"] = "RUNNING"
            run.rec.setdefault("confirmation_history", []).append(run.rec["confirmation"])
            run.rec["confirmation"] = {k: conf[k] for k in ("path", "sha256", "date", "credit_balance", "weekly_usage_percent", "acknowledge_abort")}
            run.rec["go_ahead"] = pre.get("go_ahead")
            run.rec.setdefault("authorisation_history", []).append(run.rec.get("authorisation_bound"))
            run.rec["authorisation_bound"] = pre.get("authorisation")
            todo = [x for x in S["order"] if x not in run.rec["scenarios"]]
        run.rec["invocations"].append({"mode": mode, "started_utc": pre["now_utc"], "pid": os.getpid(), "confirmation_sha256": conf["sha256"],
                                       "ledger_attempts_before": pre["ledger_attempts"], "git_head": pre.get("git_head")})
        run.save()
        codex_llm.CALLS_ROOT = os.path.join(run.dir, "calls")
        os.makedirs(codex_llm.CALLS_ROOT, exist_ok=True)
        if hooks.get("agent_status"):
            from rnplens import doctor
            patched.append((doctor, "agent_status", doctor.agent_status))
            doctor.agent_status = hooks["agent_status"]
        guard = Guard(run, mode, out=out, hooks=hooks)
        install(guard)
        c = Ctx(run, guard, a.tasks, S, load_followup_suite(), hooks, out)
        state, reason = None, None
        for sid in todo:
            sc = run_scenario(c, sid)
            if guard.abort:
                state, reason = "ABORTED", guard.abort
                break
            if sc.get("status") == "COMPLETED" and not sc.get("hard_pass"):
                state, reason = "STOPPED_DEFECT", {"kind": "HARD_CRITERION", "detail": "hard criterion failed in %s" % sid, "scenario": sid}
                break
        if state is None:
            if mode == "first":
                if len(run.rec["calls"]) == 1:
                    state = "PAUSED_AFTER_FIRST_CALL"
                else:
                    state, reason = "ABORTED", {"kind": "FIRST_CALL_COUNT", "detail": "the first invocation made %d calls, not 1" % len(run.rec["calls"])}
            else:
                state = "COMPLETE"
        run.rec["invocations"][-1]["ended_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        run.rec["invocations"][-1]["calls"] = guard.calls_invocation
        finish(c, state, reason)
        last = run.rec["calls"][-1]["post_reading"] if run.rec["calls"] else {}
        out("\nSTATE: %s  run %s  calls in this invocation: %d  ledger: %d of %d" % (state, run.id, guard.calls_invocation,
                                                                                ledger_attempts(root), LEDGER_CAP))
        out("credit balance: %s (baseline %s)   weekly usage: %s%% (start %s%%)   model: %s" % (
            last.get("balance"), run.rec["baseline"]["balance"], last.get("weekly_used_percent"), run.rec["baseline"]["weekly_used_percent"],
            last.get("model_returned")))
        if state == "PAUSED_AFTER_FIRST_CALL":
            dg = first_call_digest(run.rec)
            run.rec["first_call_digest"] = dg
            run.save()
            p01 = run.rec["scenarios"].get("P01") or {}
            out("FIRST CALL RESULT (P01): status %s; hard criteria %s; tool selection %s; answer %s" % (
                p01.get("status"), json.dumps(p01.get("hard")), json.dumps(p01.get("tool_selection")),
                os.path.join(run.dir, "work", "P01", "nl", "answer.md")))
            out("model identity: %s (effort %s, Codex CLI %s)" % (last.get("model_returned"), last.get("effort_returned"), last.get("cli_version")))
            out("No further call is made. Inspect the result, the model identity, the usage and the balance (Codex -> Usage &\n"
                "Billing). Only if you authorise the remaining calls, write a go-ahead file:\n\n%s\ndate: <today, %s>\nrun_id: %s\n"
                "first_call_digest: %s\nobserved_credit_balance: <as shown now>\nobserved_weekly_usage_percent: <as shown now>\n"
                "statement: %s\n\nand then run:\n  %s=%s python %s --continue-after-first --run-id %s --confirmation %s --go-ahead <file>" % (
                    GO_AHEAD_HEADER, TZ, run.id, dg, GO_AHEAD_STATEMENT, LIVE_ENV, TOKEN_FOR.get(conf.get("statement"), LIVE_TOKEN),
                    os.path.abspath(__file__), run.id, conf["path"]))
        if reason:
            out("STOP: %s: %s" % (reason.get("kind"), reason.get("detail")))
        out("verdict so far: %s" % json.dumps(run.rec["verdict"]))
        return 0 if state in ("PAUSED_AFTER_FIRST_CALL", "COMPLETE") else 5
    finally:
        uninstall()
        for mod, name, val in patched:
            setattr(mod, name, val)
        codex_llm.CALLS_ROOT = old_calls_root
        os.unlink(lock)


if __name__ == "__main__":
    sys.exit(main())
