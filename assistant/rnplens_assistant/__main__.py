"""python -m rnplens_assistant ask|replay|followup|replay-followup|consent   (Codex CLI backend, ChatGPT sign-in; see assistant/README.md)."""
import argparse
import json
import os
import sys
import time


def main(argv=None):
    if argv is None:                     # process entry: deterministic stdout/stderr order (rnplens.ordered_output)
        from rnplens import ordered_output
        ordered_output.install()
    ap = argparse.ArgumentParser(prog="python -m rnplens_assistant")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask", help="answer a question about predictions in a task folder (needs Codex CLI signed in with ChatGPT)")
    a.add_argument("question"); a.add_argument("--task", required=True, help="folder with the prediction folders, FASTA files and optional task.json")
    a.add_argument("--out", required=True, help="run directory to create"); a.add_argument("--arm", choices=["R", "G"], default="R", help=argparse.SUPPRESS)
    r = sub.add_parser("replay", help="re-run a saved plan without any language model and check the evidence hash")
    r.add_argument("plan"); r.add_argument("--task", required=True); r.add_argument("--out", required=True)
    r.add_argument("--expect", help="evidence_sha256 from the original run_record.json")
    f = sub.add_parser("followup", help="one bounded follow-up on an analysis (local rules, or Codex with recorded consent)")
    f.add_argument("question"); f.add_argument("--project", required=True); f.add_argument("--analysis", required=True)
    f.add_argument("--mode", choices=["local", "codex"], default="local"); f.add_argument("--choice", type=int)
    f.add_argument("--yes", action="store_true", help="confirm without a prompt (tests and scripted use; recorded)")
    fr = sub.add_parser("replay-followup", help="re-run a saved follow-up plan without any language model")
    fr.add_argument("plan"); fr.add_argument("--project", required=True); fr.add_argument("--analysis", required=True)
    c = sub.add_parser("consent", help="show, record or revoke the follow-up opt-in for a project")
    c.add_argument("action", choices=["show", "opt-in", "opt-out", "status"]); c.add_argument("--project", required=True)
    c.add_argument("--yes", action="store_true", help="record the opt-in without the prompt (scripted use; recorded as --yes)")
    c.add_argument("--allow-reference-derived", action="store_true", help="also allow DockQ-family values (never the reference file)")
    x = ap.parse_args(argv)
    if x.cmd == "ask" and x.arm == "G":     # QA fix: the sealed evaluation's general-agent arm is not offered in 0.4
        print("python -m rnplens_assistant ask: --arm G (the sealed evaluation's general-agent comparison arm) is not "
              "available in RNPLens 0.4: it sends real file names and raw tool results to the model and has no policy, "
              "pre-send check or templated answer. Nothing was sent.", file=sys.stderr)
        return 2
    if x.cmd in ("ask", "replay") and os.path.lexists(x.out):   # QA fix: an existing result is never overwritten
        print("python -m rnplens_assistant %s: %s already exists; give a new --out folder (an existing result is never "
              "overwritten)" % (x.cmd, x.out), file=sys.stderr)
        return 2
    if x.cmd in ("followup", "replay-followup", "consent"):
        return _followup_cmds(x)
    if x.cmd == "ask":
        from . import codex_llm
        cl = codex_llm.CodexClient("cli_%s" % time.strftime("%H%M%S"))
        if x.arm == "R":
            from . import ask
            ask.run(x.task, x.question, x.out, cl)
        else:
            from . import baseline_codex
            baseline_codex.run(x.task, x.question, x.out, cl)
        print(open(x.out + "/answer.md").read())
        return 0
    from . import replay
    try:                                     # 0.4 replay integrity: the recorded plan, re-admitted, or nothing runs
        h, _, identity, recorded = replay.run_checked(x.plan, x.task, x.out)
    except replay.ReplayRefused as ex:
        print("python -m rnplens_assistant replay: refused, nothing was run: %s" % ex, file=sys.stderr)
        return 5
    expect = x.expect or recorded            # without --expect, the run record's evidence hash is the expectation
    print(json.dumps({"evidence_sha256": h, "matches": (h == expect) if expect else None, "plan_identity": identity,
                      "expected_from": "--expect" if x.expect else ("run_record.json" if recorded else None)}))
    return 0 if (not expect or h == expect) else 1


def _followup_cmds(x):
    from . import consent, followup, replay
    if x.cmd == "consent":
        if x.action == "show":
            print(consent.screen_text(x.allow_reference_derived)); return 0
        if x.action == "status":
            ok, r, why = consent.status(x.project); print(json.dumps({"granted": ok, "detail": why, "record": r}, indent=1)); return 0
        if x.action == "opt-out":
            print(json.dumps(consent.opt_out(x.project, "--yes" if x.yes else "interactive"), indent=1)); return 0
        if x.yes:
            print(consent.screen_text(x.allow_reference_derived))
            print(json.dumps(consent.opt_in(x.project, "--yes", x.allow_reference_derived), indent=1)); return 0
        r = consent.interactive_opt_in(x.project, input, allow_reference_derived=x.allow_reference_derived)
        return 0 if r else 1
    if x.cmd == "replay-followup":
        from rnplens.portability import PortabilityError
        try:
            h, log, ok, identity = replay.run_followup_checked(x.plan, x.project, x.analysis)
        except PortabilityError as ex:              # recorded files missing or changed: no replay, exit 6
            print(str(ex), file=sys.stderr)
            return ex.exit_code
        except replay.ReplayRefused as ex:          # plan and record disagree: no replay, exit 5
            print("python -m rnplens_assistant replay-followup: refused, nothing was run: %s" % ex, file=sys.stderr)
            return 5
        print(json.dumps({"evidence_sha256": h, "matches": ok, "tool_calls": len(log), "plan_identity": identity})); return 0 if ok else 1
    factory = None
    if x.mode == "codex":
        from . import codex_llm
        factory = lambda: codex_llm.CodexClient("followup_%s" % time.strftime("%H%M%S"))
    rec = followup.run(x.project, x.analysis, x.question, mode=x.mode, choice=x.choice, yes=x.yes,
                       ask=input if (sys.stdin.isatty() and not x.yes) else None, client_factory=factory)
    return 0 if not rec["traceability_violations"] and (rec["stop"] is None or rec["stop"]["kind"] in ("NO_CONSENT", "REJECTED")) else 4


if __name__ == "__main__":
    sys.exit(main())
