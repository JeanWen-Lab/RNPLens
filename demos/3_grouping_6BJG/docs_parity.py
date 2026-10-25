"""Reproduction check of the 6BJG worked example in docs/grouping.md (values copied from that page at 5caccec).
python docs_parity.py ANALYSIS G H OUT_JSON"""
import json
import os
import sys

from rnplens import provenance as pv

DOC = {
    "groups_per_cut": {"0.3": 2, "0.5": 5, "0.7": 18},
    "surface_groups_per_cut": {"0.3": 1, "0.5": 1, "0.7": 5},
    "sizes_per_cut": {"0.3": [47, 3], "0.5": [26, 19, 2, 1, 2],
                      "0.7": [15, 2, 1, 7, 2, 7, 2, 2, 1, 1, 1, 1, 1, 1, 2, 1, 1, 2]},
    "t05_groups": [  # group, size, engine-weighted size, representative, mean R to representative (3 dp), P min/median/max (2 dp)
        [1, 26, "13/25", "s013", 0.746, [1.65, 16.71, 47.54]],
        [2, 19, "19/50", "s033", 0.718, [1.65, 7.93, 22.48]],
        [3, 2, "1/25", "s016", 0.889, [1.75, 1.75, 1.75]],
        [4, 1, "1/50", "s039", None, None],
        [5, 2, "1/25", "s020", 0.739, [1.76, 1.76, 1.76]]],
    "designated": "s001",
    "diff_1_2_counts": {"frequent in both": 14, "frequent in group 1 only": 4, "frequent in group 2 only": 4,
                        "contacts frequent in neither group (not listed)": 38},
    "diff_1_only": ["W39-C18", "E41-U21", "N46-U21", "L53-U21"],
    "diff_2_only": ["W39-G3", "W39-A4", "W39-A5", "R43-G3"],
    "diff_denominators": [26, 19],
}


def main(analysis, g, h, out):
    G = json.load(open(os.path.join(analysis, "groups", "groups.json")))
    obs, checks = {}, []

    def chk(name, expected, observed):
        checks.append({"check": name, "documented": expected, "observed": observed, "equal": expected == observed})

    for t in ("0.3", "0.5", "0.7"):
        T = G["thresholds"][t]
        chk("groups at t=%s" % t, DOC["groups_per_cut"][t], T["n_groups"])
        chk("surface groups at t=%s" % t, DOC["surface_groups_per_cut"][t], T["n_surface_groups"])
        chk("sizes in display order at t=%s" % t, DOC["sizes_per_cut"][t], [x["size"] for x in T["groups"]])
    for row, x in zip(DOC["t05_groups"], G["thresholds"]["0.5"]["groups"]):
        sp = x["rna_pose_difference_spread_A"] or {}
        mr = x.get("mean_R_members_to_representative")
        o = [x["group"], x["size"], x["engine_weighted_size"]["fraction"], x["representative"]["id"],
             None if mr is None or x["size"] == 1 else round(mr, 3),
             None if sp.get("min") is None else [round(sp["min"], 2), round(sp["median"], 2), round(sp["max"], 2)]]
        chk("t=0.5 group %d row" % row[0], row, o)
    chk("engine-designated structure", DOC["designated"], [d["id"] for d in G["thresholds"]["0.5"]["designated"]][0])
    if (g, h) == ("1", "2"):
        D = json.load(open(os.path.join(analysis, "groups", "diff_1_2", "diff.json")))
        chk("diff 1-2 counts", DOC["diff_1_2_counts"], D["counts"])
        lab = lambda r: "%s%d-%s%d" % (r["protein_residue"], r["protein_position"], r["rna_nucleotide"], r["rna_position"])
        chk("diff group 1 only", sorted(DOC["diff_1_only"]), sorted(lab(r) for r in D["rows"] if r["category"] == "frequent in group 1 only"))
        chk("diff group 2 only", sorted(DOC["diff_2_only"]), sorted(lab(r) for r in D["rows"] if r["category"] == "frequent in group 2 only"))
        chk("diff denominators", DOC["diff_denominators"],
            [max(r["A"]["denominator_resolved_members"] for r in D["rows"]), max(r["B"]["denominator_resolved_members"] for r in D["rows"])])
    else:
        checks.append({"check": "diff 1-2", "equal": None, "note": "groups compared are %s and %s, not the documented 1 and 2" % (g, h)})
    res = {"provenance": pv.block("demo_docs_parity", [os.path.join(analysis, "groups", "groups.json")],
                                  "documented 6BJG numbers of docs/grouping.md compared with this run", {"g": g, "h": h}),
           "checks": checks, "n_checks": len(checks), "n_equal": sum(1 for c in checks if c["equal"]),
           "verdict": "PASS" if all(c["equal"] for c in checks) else "FAIL"}
    pv.atomic_write_json(out, res)
    print("docs parity: %s (%d of %d checks equal)" % (res["verdict"], res["n_equal"], res["n_checks"]))
    for c in checks:
        if not c["equal"]:
            print("  differs: %s: documented %s, observed %s" % (c["check"], c.get("documented"), c.get("observed")))
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:5]))
