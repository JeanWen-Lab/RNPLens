"""Score every trial under a pilot/evaluation output directory against a key file. Usage: score_dir.py OUT KEYS TASKS_ROOT"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score

out, keys, troot = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
rows = []
for task in sorted(keys):
    for arm in ("R", "G"):
        rd = os.path.join(out, task, arm)
        if not os.path.exists(os.path.join(rd, "answer.json")):
            rows.append({"task": task, "arm": arm, "missing": True}); continue
        r = score.score_trial(rd, keys[task], os.path.join(troot, task))
        r.update(task=task); rows.append(r)
json.dump(rows, open(os.path.join(out, "scores.json"), "w"), indent=1)
for r in rows:
    print(r["task"], r.get("arm"), "correct=%s" % r.get("correct"), "action=%s" % r.get("action"), "missing=%s" % r.get("required_missing"),
          "flags=%s" % [(f["code"], f["match"]) for f in r.get("critical", [])])
