"""Pre-freeze premise check (not part of the suite): build the declared first-call payloads for every Part P/Z task
and the follow-up payloads for the Part F tasks from the real development tasks, and run the privacy gate on them.
No scenario, no driver run, no language model, no Codex subprocess."""
import contextlib, io, json, os, shutil, sys, tempfile
CLONE, OUT, SCR = sys.argv[1], sys.argv[2], sys.argv[3]
LQ = os.path.join(CLONE, "assistant/evaluation_v04/LIVE_QUALIFICATION_v1")
sys.path.insert(0, LQ)
import run_live as R, privacy
from rnplens_assistant import ask, followup as F
from rnplens import assist
S = R.load_scenarios()
res = {"P": {}, "F": {}}
fu = R.load_followup_suite()
for s in S["part_P"] + S["part_Z"]:
    tmp = tempfile.mkdtemp(dir=SCR); tn = os.path.join(tmp, "task_nl")
    shutil.copytree(os.path.join(R.DEFAULT_TASKS, s["task"]), tn)
    system, user = R.expected_nl_payload(s["question"], tn)
    payload = system + "\n\n---\n\n" + user
    ctx = R.privacy_ctx(tn, system, [tmp, R.RNPBENCH, os.path.expanduser("~") + "/"])
    files, n = ask.listing(tn); t = ask.load_task(tn)
    sysp = ask._read("planner.md") + "\n\n# RNPLens documentation (which analysis to use)\n\n" + ask.doc_text()
    u = ("Question:\n%s\n\nTask inputs (%d files, paths relative to the task folder):\n%s\n\nExperimental reference files supplied with this task: %s\n"
         % (s["question"], n, "\n".join(files), ", ".join(t["reference_files"]) or "none"))
    res["P"][s["id"]] = {"bytes": len(payload.encode()), "findings": privacy.gate(payload, **ctx), "reconstruction_equals_ask": (sysp == system and u == user),
                         "followup_privacy_check": F.privacy_check(payload, tn), "n_content_lines": len(ctx["content_lines"]), "n_seqs": [len(x) for x in ctx["sequences"]]}
S2 = json.load(open(os.path.join(CLONE, S["part_F"]["source"])))
for lid in S["part_F"]["ids"]:
    s = next(x for x in S2["scenarios"] if x["id"] == lid)
    work = tempfile.mkdtemp(dir=SCR)
    P, A = fu["run_part2"].setup_task(os.path.join(R.DEFAULT_TASKS, s["task"]), work)
    initial = {"kind": "menu_item", "capability": "interface_overview"}
    if s["initial"]["item"] == "C":
        rr = fu["run_part2"]._auto_range(A)
        with contextlib.redirect_stdout(io.StringIO()):
            assert assist.main(["--project", P, "--analysis", A, "--item", "C", "--rna", rr, "--runs", "run_A,run_B", "--json"], out=lambda *x: None) == 0
        initial = {"kind": "menu_item", "capability": "region_run_comparison"}
    summ = F.build_summary(P, A, s["question"], False, initial)
    st = F.summary_text(summ)
    system = F.prompt_system()
    payload = system + "\n\n---\n\n" + F.prompt_user(s["question"], st)
    ctx = R.privacy_ctx(os.path.join(work, "task"), system, [work, R.RNPBENCH, os.path.expanduser("~") + "/"] + ([s["reference_file"]] if s.get("reference_file") else []))
    res["F"][lid] = {"bytes": len(payload.encode()), "findings": privacy.gate(payload, **ctx), "followup_privacy_check": F.privacy_check(payload, P)}
json.dump(res, open(OUT, "w"), indent=1)
print("PREMISE DONE")
