"""FOLLOWUP_SUITE_v1 Part 2: LIVE Codex follow-up scenarios (frozen; refuses unless every guard passes).

    RNPLENS_CODEX_CALLS=/home/jwen/projects/RNPBench/scratch_agent/v04/codex_calls \
    RNPLENS_FOLLOWUP_LIVE=I_CONFIRM_AUTO_RELOAD_OFF \
    python assistant/evaluation_v04/FOLLOWUP_SUITE_v1/run_part2.py --live \
        --tasks /home/jwen/projects/RNPBench/scratch_agent/assistant_dev_tasks \
        --out /home/jwen/projects/RNPBench/scratch_agent/v04/followup/part2_run1

Without --live it only prints the plan (command, scenarios, expected number of Codex calls) and calls nothing.
Guards (all must pass, checked before the first call): FREEZE.md matches; RNPLENS_FOLLOWUP_LIVE confirms that
automatic credit reload is off; not inside the sealed-evaluation window 2026-10-22T00:00 to 2026-10-25T00:00
Australia/Canberra; RNPLENS_CODEX_CALLS and --out resolve inside RNPBench/scratch_agent/v04/; the jail is this
checkout's and not under RNPLens_dev_0.3; rnplens doctor --agent is READY and the model catalog lists gpt-6.1-sol;
no other Part 2 run holds the lock. During the run: strictly serial; the CodexClient stops on any credit-balance
change and on weekly plan usage >= 10% (stricter than the evaluation's 85%); a usage stop ends the whole run."""
import argparse
import contextlib
import datetime
import io
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import score  # noqa: E402
from run_part1 import check_freeze  # noqa: E402

SCRATCH = "/home/jwen/projects/RNPBench/scratch_agent/v04/"
PROTECTED = "/home/jwen/projects/RNPBench/RNPLens_dev_0.3"
WINDOW = ("2026-10-22T00:00", "2026-10-25T00:00")
WEEKLY_GUARD = 10.0
LIVE_TOKEN = "I_CONFIRM_AUTO_RELOAD_OFF"


def in_sealed_window(now=None):
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Australia/Canberra")
    now = (now or datetime.datetime.now(datetime.timezone.utc)).astimezone(tz)
    a, b = (datetime.datetime.fromisoformat(x).replace(tzinfo=tz) for x in WINDOW)
    return a <= now < b


def _under(p, root):
    p = os.path.realpath(p)
    return p.startswith(os.path.realpath(root.rstrip("/")) + os.sep)


def guards(args, env=None, now=None, agent_status=None, model_check=None):
    """-> list of refusals (empty: the live run may start). Pure checks; nothing is called or written."""
    env = os.environ if env is None else env
    R = []
    try:
        check_freeze()
    except SystemExit as ex:
        R.append(str(ex))
    if not args.live:
        R.append("--live not given (plan only)")
    if env.get("RNPLENS_FOLLOWUP_LIVE") != LIVE_TOKEN:
        R.append("RNPLENS_FOLLOWUP_LIVE must be %s (the owner has confirmed automatic credit reload is off)" % LIVE_TOKEN)
    if in_sealed_window(now):
        R.append("inside the sealed-evaluation window %s to %s Australia/Canberra" % WINDOW)
    calls = env.get("RNPLENS_CODEX_CALLS")
    if not calls or not _under(calls, SCRATCH):
        R.append("RNPLENS_CODEX_CALLS must point into %s (got %r)" % (SCRATCH, calls))
    if not args.out or not _under(args.out, SCRATCH):
        R.append("--out must be inside %s" % SCRATCH)
    from rnplens_assistant import codex_llm
    if calls and os.path.realpath(codex_llm.CALLS_ROOT) != os.path.realpath(calls):
        R.append("codex_llm.CALLS_ROOT (%s) does not equal RNPLENS_CODEX_CALLS" % codex_llm.CALLS_ROOT)
    if _under(codex_llm.JAIL, PROTECTED) or not _under(codex_llm.JAIL, ROOT):
        R.append("the jail %s is not this checkout's" % codex_llm.JAIL)
    for p in (codex_llm.CALLS_ROOT, args.out or ""):
        if _under(p, PROTECTED):
            R.append("%s is under the protected %s" % (p, PROTECTED))
    if not R or args.live:
        from rnplens import doctor
        ready, reasons = (agent_status or doctor.agent_status)()
        if not ready:
            R.append("rnplens doctor --agent is not READY: %s" % "; ".join(reasons))
        mc = (model_check or (lambda: doctor.check_model(doctor.Env(), doctor.codex_path(doctor.Env()))))()
        if mc.get("status") != doctor.READY:
            R.append("model catalog: %s" % mc.get("detail"))
    return R


def plan_text(S, args):
    cmd = ("cd %s && RNPLENS_CODEX_CALLS=%scodex_calls RNPLENS_FOLLOWUP_LIVE=%s PYTHONPATH=$PWD/src:$PWD/assistant "
           "/home/jwen/projects/RNPBench/RNPLens_dev_0.3/venv/bin/python assistant/evaluation_v04/FOLLOWUP_SUITE_v1/run_part2.py --live "
           "--tasks /home/jwen/projects/RNPBench/scratch_agent/assistant_dev_tasks --out %sfollowup/part2_run1"
           % ("/home/jwen/projects/RNPBench/RNPLens_dev_0.4/tracks/followup/RNPLens", SCRATCH, LIVE_TOKEN, SCRATCH))
    e = S["expected_codex_calls"]
    return {"command": cmd, "n_scenarios": len(S["scenarios"]), "expected_codex_calls": e,
            "scenarios": [(s["id"], s["task"], s["question"]) for s in S["scenarios"]]}


def _auto_range(A):
    S = json.load(open(os.path.join(A, "summary.json")))
    pos = sorted(r["position"] for r in S["rna_positions"]["rows"] if any(x.get("count", 0) > 0 for x in r["per_engine"].values()))
    p, q = pos[0], pos[-1]
    return "%d-%d" % (p, min(q, p + 20))


def setup_task(task_dir, work):
    from rnplens import assist, cli
    t = os.path.join(work, "task")
    shutil.copytree(task_dir, t, ignore=shutil.ignore_patterns("reference*"))      # the reference is never copied or read
    P, A = os.path.join(work, "p"), os.path.join(work, "a")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        rc = cli.main(["import", os.path.join(t, "run_A"), os.path.join(t, "run_B"), "--protein-seq", os.path.join(t, "protein.fasta"),
                       "--rna-seq", os.path.join(t, "rna.fasta"), "--out", P, "--case-id", os.path.basename(task_dir)[:20], "--engine", "BOLTZ2"])
        assert rc == 0, "import failed for %s" % task_dir
        assert assist.main(["--project", P, "--analysis", A, "--item", "A", "--json"], out=lambda *x: None) == 0
    return P, A


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true"); ap.add_argument("--tasks"); ap.add_argument("--out")
    a = ap.parse_args(argv)
    S = json.load(open(os.path.join(HERE, "scenarios_part2.json")))
    print(json.dumps(plan_text(S, a), indent=1))
    refusals = guards(a)
    if refusals:
        print("REFUSING to run Part 2:\n" + "\n".join("  - " + r for r in refusals))
        return 3
    from rnplens import assist
    from rnplens_assistant import codex_llm, consent, followup as F
    os.makedirs(a.out, exist_ok=False)
    lock = os.path.join(codex_llm.CALLS_ROOT, "followup_part2.lock")
    os.makedirs(codex_llm.CALLS_ROOT, exist_ok=True)
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode()); os.close(fd)
    results, calls = [], 0
    try:
        prepared = {}
        for s in S["scenarios"]:                                     # strictly serial
            work = os.path.join(a.out, s["id"])
            os.makedirs(work)
            P, A = setup_task(os.path.join(a.tasks, s["task"]), work)
            initial = {"kind": "menu_item", "capability": "interface_overview"}
            if s["initial"]["item"] == "C":
                rr = _auto_range(A)
                assert assist.main(["--project", P, "--analysis", A, "--item", "C", "--rna", rr, "--runs", "run_A,run_B", "--json"], out=lambda *x: None) == 0
                initial = {"kind": "menu_item", "capability": "region_run_comparison"}
            consent.opt_in(P, "--yes")
            client = {}

            def factory():
                client["c"] = codex_llm.CodexClient("fu_suite_%s" % s["id"], config={"weekly_guard_percent": WEEKLY_GUARD})
                return client["c"]
            rec = F.run(P, A, s["question"], mode="codex", initial=initial, yes=True, ask=None, out=lambda *x: None,
                        client_factory=factory)
            calls += rec["model_calls_made"]
            md = open(os.path.join(A, rec["dir"], "followup_answer.md"), encoding="utf-8").read()
            sc = score.score_part2(s, rec, md, [p["text"] for p in rec["payloads"]])
            results.append({"id": s["id"], "scores": sc, "stop": rec["stop"], "model_calls": rec["model_calls_made"],
                            "record": os.path.join(A, rec["dir"], "followup_record.json")})
            print(s["id"], json.dumps(sc), (rec["stop"] or {}).get("kind"), flush=True)
            if (rec["stop"] or {}).get("kind") == "USAGE_GUARD":
                results.append({"stopped_run": "USAGE_GUARD after %s" % s["id"]}); break
    finally:
        os.unlink(lock)
        doc = {"suite": "FOLLOWUP_SUITE_v1", "part": 2, "codex_calls": calls, "results": results,
               "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
        with open(os.path.join(a.out, "part2_results.json"), "w") as fh:
            json.dump(doc, fh, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
