"""At the primary cut, print "G H": G = the group holding the engine-designated structure (engine-pick group), H = the
next group in display order. Rule fixed in records/v04_integration/DEMOS_PLAN.md. python group_pick.py GROUPS_JSON"""
import json
import sys

g = json.load(open(sys.argv[1]))
t = g["thresholds"][g["primary_threshold"]]
groups = t["groups"]                                   # already in display order
idx = [i for i, x in enumerate(groups) if x.get("contains_designated")]
if not idx or idx[0] + 1 >= len(groups):
    raise SystemExit("no engine-pick group with a next group at t=%s" % g["primary_threshold"])
print(groups[idx[0]]["group"], groups[idx[0] + 1]["group"])
