"""LLM-free replay of every R trial (protocol v2: replay mandatory). Replays write to RUNS/_replay/, never into trial
folders. Writes RUNS/REPLAY.json. Usage: replay_all.py SEALED_DIR RUNS_DIR"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_eval import trials, verify_sealed   # noqa: E402
from rnplens_assistant import replay         # noqa: E402

S, runs = sys.argv[1], sys.argv[2]
seal = verify_sealed(S)
out = {"sealed_manifest_sha256": seal, "trials": []}
for t, arm, rep in sorted(x for x in trials(S) if x[1] == "R"):
    rd = os.path.join(runs, t, arm, "rep%d" % rep)
    row = {"task": t, "repeat": rep}
    if not os.path.exists(os.path.join(rd, "run_record.json")):
        row["status"] = "NO_RUN"
    elif not os.path.exists(os.path.join(rd, "plan.json")):
        row["status"] = "NO_PLAN"
    else:
        want = json.load(open(os.path.join(rd, "run_record.json"))).get("evidence_sha256")
        dst = os.path.join(runs, "_replay", t, "rep%d" % rep)
        if os.path.exists(dst):
            os.rename(dst, dst + ".old_%d" % len(os.listdir(os.path.dirname(dst))))
        try:
            h, _ = replay.run(os.path.join(rd, "plan.json"), os.path.join(S, "tasks", t), dst)
            row.update(status="MATCH" if h == want else "MISMATCH", original=want, replay=h)
        except Exception as ex:
            row.update(status="REPLAY_ERROR", error="%s: %s" % (type(ex).__name__, str(ex)[:300]))
    out["trials"].append(row)
out["n"] = len(out["trials"]); out["n_match"] = sum(r["status"] == "MATCH" for r in out["trials"])
out["all_match"] = out["n"] > 0 and out["n_match"] == out["n"]
json.dump(out, open(os.path.join(runs, "REPLAY.json"), "w"), indent=1)
print(json.dumps({k: out[k] for k in ("n", "n_match", "all_match")}))
