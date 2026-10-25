"""FOLLOWUP_SUITE_v1 Part 1: scripted scenarios, no language model, no network. Run only after FREEZE.md exists.

    python assistant/evaluation_v04/FOLLOWUP_SUITE_v1/run_part1.py --out RESULTS_DIR [--only P1-01,...]

Each scenario runs in a fresh temporary copy: import the bundled 7K9D example (two runs), run the initial menu item,
set the consent state, run one follow-up with the scripted client (or the real CodexClient against the fake jail),
then compare the observed facts with the frozen expectations (score.score_part1). The doctor's READY check is
replaced by a scripted READY (the agent prerequisites are not part of what Part 1 tests)."""
import argparse
import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import fake_client  # noqa: E402
import score  # noqa: E402

EX = os.path.join(ROOT, "examples")


def check_freeze():
    fz = os.path.join(HERE, "FREEZE.md")
    if not os.path.isfile(fz):
        raise SystemExit("REFUSING: FREEZE.md is missing; the suite must be frozen before it is run")
    bad = []
    for line in open(fz, encoding="utf-8"):
        if line.startswith("| `"):
            name, h = line.split("`")[1], line.split("`")[3]
            if hashlib.sha256(open(os.path.join(HERE, name), "rb").read()).hexdigest() != h:
                bad.append(name)
    if bad:
        raise SystemExit("REFUSING: frozen files changed since FREEZE.md: %s" % ", ".join(bad))


def setup(tmp, initial):
    from rnplens import assist, cli
    rf = os.path.join(EX, "reference_free", "report_7K9D")
    P, A = os.path.join(tmp, "p"), os.path.join(tmp, "a")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assert cli.main(["import", os.path.join(rf, "exec_A"), os.path.join(rf, "exec_B"), "--protein-seq",
                         os.path.join(EX, "reference_based", "7K9D_protein.fasta"), "--rna-seq",
                         os.path.join(EX, "reference_based", "7K9D_rna.fasta"), "--out", P, "--case-id", "m", "--engine", "BOLTZ2"]) == 0
        lines = []
        assert assist.main(["--project", P, "--analysis", A, "--item", "A", "--json"], out=lines.append) == 0
        if initial["item"] != "A":
            argv = ["--project", P, "--analysis", A, "--item", initial["item"], "--json"]
            for k in ("rna", "runs", "evidence"):
                if initial.get(k):
                    argv += ["--" + k, initial[k]]
            assert assist.main(argv, out=lines.append) == 0
    cap = {"A": "interface_overview", "B": "region_contacts", "C": "region_run_comparison", "D": "explain_evidence",
           "F": "export_methods"}[initial["item"]]
    return P, A, {"kind": "menu_item", "capability": cap}


def run_scenario(s, workdir):
    from rnplens_assistant import codex_llm, consent, followup as F
    tmp = tempfile.mkdtemp(prefix=s["id"] + "_", dir=workdir)
    P, A, initial = setup(tmp, s["initial"])
    snap = os.path.join(tmp, "a_snapshot")
    shutil.copytree(A, snap)
    if s["consent"] in ("opt_in", "opt_in_then_out"):
        consent.opt_in(P, "--yes")
    if s["consent"] == "opt_in_then_out":
        consent.opt_out(P, "--yes")
    facts = {"factory_called": False}
    calls_root = os.path.join(tmp, "codex_calls"); os.makedirs(calls_root)
    with open(os.path.join(calls_root, "credits_baseline.json"), "w") as fh:
        json.dump({"balance": "0", "recorded": "suite"}, fh)
    jail = fake_client.write_fake_jail(os.path.join(tmp, "fake_jail.sh"))
    client = {"obj": None}
    cl = s["client"]
    env_backup = dict(os.environ)
    if cl["type"] == "fake_jail":
        os.environ["FAKE_CODEX_MODE"] = cl["jail_mode"]
        os.environ["FAKE_CODEX_REPLY"] = fake_client.write_reply(os.path.join(tmp, "reply.json"), cl["reply"])

    def factory():
        facts["factory_called"] = True
        if cl["type"] == "scripted":
            client["obj"] = fake_client.ScriptedClient(copy.deepcopy(cl["replies"]))
        elif cl["type"] == "fake_jail":
            client["obj"] = codex_llm.CodexClient("suite_%s" % s["id"], config={"timeout_s": cl.get("timeout_s", 60)})
        else:
            raise AssertionError("no client in this scenario")
        return client["obj"]
    spawned = []
    real_run = subprocess.run

    def guard(args, *a, **k):
        flat = " ".join(map(str, args if isinstance(args, (list, tuple)) else [args]))
        if jail in flat or "codex" in os.path.basename(str(args[0] if isinstance(args, (list, tuple)) else args)):
            spawned.append(flat)
        return real_run(args, *a, **k)
    saved = (codex_llm.JAIL, codex_llm.CALLS_ROOT, subprocess.run, F.tool_calls_for)
    codex_llm.JAIL, codex_llm.CALLS_ROOT, subprocess.run = jail, calls_root, guard
    if s.get("patch") == "five_tool_calls":
        orig = saved[3]
        F.tool_calls_for = lambda fid, args, summ: orig(fid, args, summ) * 5
    try:
        if s.get("pre") == "codex_round_same_question":
            pre = fake_client.ScriptedClient([{"follow_up": "none", "args": F._blank(), "rationale": "pre"}])
            F.run(P, A, s["question"], mode="codex", initial=initial, yes=True, out=lambda *x: None,
                  client_factory=lambda: pre, agent_status=lambda: (True, []))
        rec = F.run(P, A, s["question"], mode=s["mode"], initial=initial, choice=s.get("choice"), yes=s.get("yes", False),
                    ask=None, out=lambda *x: None, client_factory=factory, agent_status=lambda: (True, []))
    finally:
        codex_llm.JAIL, codex_llm.CALLS_ROOT, subprocess.run, F.tool_calls_for = saved
        os.environ.clear(); os.environ.update(env_backup)
    fdir = os.path.join(A, rec["dir"])
    md = open(os.path.join(fdir, "followup_answer.md"), encoding="utf-8").read()
    executed = bool(rec["tool_log"]) and all(e["status"] == "OK" for e in rec["tool_log"])
    facts.update({"stop": (rec["stop"] or {}).get("kind"), "executed": executed, "chosen": (rec["chosen"] or {}).get("id"),
                  "rules": [p["verdict"]["rule"] for p in rec["proposals"]], "model_calls": rec["model_calls_made"],
                  "codex_subprocess": len(spawned), "traceability_clean": rec["traceability_violations"] == [],
                  "wording_clean": rec["wording_audit"] == [] and score.forbidden_hits(md) == [],
                  "local_suggestions_listed": "Local suggestion (not run)" in md,
                  "call_error_recorded": bool(rec["model_calls"] and rec["model_calls"][-1].get("error")),
                  "usage_recorded": bool(rec["model_calls"] and rec["model_calls"][-1].get("plan_used_percent") == 99.0),
                  "credit_baseline_unchanged": json.load(open(os.path.join(calls_root, "credits_baseline.json")))["balance"] == "0",
                  "model_returned": (rec["model_calls"][0].get("model_returned") if rec["model_calls"] else None),
                  "rationale_in_record": bool(rec["chosen"] and rec["chosen"].get("rationale_stored_not_shown")),
                  "scripted_replies_left": len(client["obj"].replies) if isinstance(client["obj"], fake_client.ScriptedClient) else None})
    if "answer_excludes" in s["expect"]:
        facts["answer_excludes"] = [x for x in s["expect"]["answer_excludes"] if x not in md]
    if executed or rec["chosen"]:
        h, _ = F.replay_plan(os.path.join(fdir, "followup_plan.json"), P, A)
        facts["replay_matches"] = h == rec["evidence_sha256"]
        h2, _ = F.replay_plan(os.path.join(fdir, "followup_plan.json"), P, snap)
        facts["replay_fresh_copy_matches"] = h2 == rec["evidence_sha256"]
    if s.get("check") == "traceability_injection":
        ans = json.load(open(os.path.join(fdir, "followup_answer.json"), encoding="utf-8"))
        st = ans["statements"]
        toks = F.allowed_tokens(F.build_summary(P, A))
        args = rec["chosen"]["args"]
        facts["control_clean"] = F.check_traceable(st, A, args, rec["tool_log"], toks) == []
        inj = copy.deepcopy(st); inj[-2]["text"] = inj[-2]["text"].rstrip(".") + " (agreement 0.73)."
        facts["injected_number_detected"] = any(v.startswith("T1") for v in F.check_traceable(inj, A, args, rec["tool_log"], toks))
        alt = copy.deepcopy(st)
        k = next(i for i, x in enumerate(alt) if any("evidence_id" in sl for sl in x["slots"].values()))
        n = next(n for n, sl in alt[k]["slots"].items() if "evidence_id" in sl)
        alt[k]["slots"][n]["value"] = "altered"
        facts["altered_slot_detected"] = any(v.startswith("T2") for v in F.check_traceable(alt, A, args, rec["tool_log"], toks))
        facts["empty_answer_detected"] = F.check_traceable([], A, args, rec["tool_log"], toks) == ["T0 no statements"]
    exp = dict(s["expect"])
    if "answer_excludes" in exp:
        exp["answer_excludes"] = list(exp["answer_excludes"])
        facts["answer_excludes"] = [x for x in exp["answer_excludes"] if x in facts["answer_excludes"]]
    ok, bad = score.score_part1(exp, facts)
    return {"id": s["id"], "category": s["category"], "passed": ok, "mismatches": bad, "facts": facts,
            "record": os.path.relpath(os.path.join(fdir, "followup_record.json"), workdir)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--only")
    a = ap.parse_args(argv)
    a.out = os.path.abspath(a.out)       # Amendment 1: the fake jail runs with cwd = the call directory, so paths must be absolute
    check_freeze()
    import rnplens
    assert rnplens.__version__ == "0.4.0.dev0", rnplens.__version__
    os.makedirs(a.out, exist_ok=True)
    work = os.path.join(a.out, "work"); os.makedirs(work, exist_ok=True)
    S = json.load(open(os.path.join(HERE, "scenarios_part1.json")))["scenarios"]
    if a.only:
        S = [s for s in S if s["id"] in a.only.split(",")]
    res = []
    t0 = time.time()
    for s in S:
        try:
            r = run_scenario(s, work)
        except Exception as ex:
            import traceback
            r = {"id": s["id"], "category": s["category"], "passed": False, "mismatches": ["runner error: %s: %s" % (type(ex).__name__, ex)],
                 "traceback": traceback.format_exc()[-3000:]}
        res.append(r)
        print("%s %s %s" % (r["id"], "PASS" if r["passed"] else "FAIL", "; ".join(r["mismatches"])[:300]), flush=True)
    doc = {"suite": "FOLLOWUP_SUITE_v1", "part": 1, "n": len(res), "passed": sum(r["passed"] for r in res),
           "failed": [r["id"] for r in res if not r["passed"]], "wall_s": round(time.time() - t0, 1),
           "freeze_sha256": hashlib.sha256(open(os.path.join(HERE, "FREEZE.md"), "rb").read()).hexdigest(),
           "rnplens_version": rnplens.__version__, "python": sys.version.split()[0], "platform": sys.platform, "results": res}
    with open(os.path.join(a.out, "part1_results.json"), "w") as fh:
        json.dump(doc, fh, indent=1, default=str)
    print("PART1 %d/%d passed" % (doc["passed"], doc["n"]))
    return 0 if doc["passed"] == doc["n"] else 1


if __name__ == "__main__":
    sys.exit(main())
