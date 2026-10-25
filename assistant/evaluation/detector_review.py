"""List every detector pattern match in answer texts under the given run folders, with whether the negation guard
suppressed it. Development data only. Usage: detector_review.py OUT_JSON RUN_ROOT [RUN_ROOT ...]"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score  # noqa: E402

out = []
for root in sys.argv[2:]:
    for dp, dn, fn in os.walk(root):
        if "answer.json" not in fn or "/_replay" in dp:
            continue
        if not os.path.exists(os.path.join(dp, "run_record.json")):
            continue
        L = score.load(dp)                    # exactly the text the scorer scans
        text, arm = L["text"], L["arm"]
        for code, pats in score.DETECTORS.items():
            for s in score._sentences(text):
                for p in pats:
                    for m in re.finditer(p, s, flags=re.I):
                        sup = score._neg_before(s, m.start()) or bool(score.NEG.search(s[m.start():m.end()]))
                        out.append({"run": os.path.relpath(dp, root), "root": root, "arm": arm, "code": code, "match": m.group(0),
                                    "suppressed": sup, "sentence": s[:300]})
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(len(out), "matches;", sum(x["suppressed"] for x in out), "suppressed")
