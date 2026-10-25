"""Check that every original candidate is retained by the grouping: for every cut, structures in groups (interface
groups + the no-interface group) + ineligible == the number of candidates, no structure counted twice, and the ids
equal the manifest's. python retention_check.py PROJECT GROUPS_JSON N_EXPECTED OUT_JSON"""
import json
import sys

from rnplens import provenance as pv


def main(project, gpath, n_expected, out):
    man = json.load(open(project + "/manifest.json"))
    G = json.load(open(gpath))
    n_expected = int(n_expected)
    all_ids = sorted(s["id"] for s in man["structures"])
    included = sorted(s["id"] for s in man["structures"] if str(s.get("verdict", "")).upper().startswith("INCLUDED"))
    inel = sorted(x["id"] if isinstance(x, dict) else x for x in G["ineligible"])
    res = {"n_expected": n_expected, "n_manifest_structures": len(all_ids), "n_manifest_included": len(included),
           "not_imported": G.get("not_imported"), "ineligible": inel, "cuts": {}}
    ok = len(all_ids) == n_expected and len(included) == n_expected
    for t, T in sorted(G["thresholds"].items()):
        inter = [m for x in T["groups"] if not x.get("no_interface") for m in x["members"]]
        noint = [m for x in T["groups"] if x.get("no_interface") for m in x["members"]]
        counted = inter + noint + inel
        row = {"n_groups": T["n_groups"], "structures_in_interface_groups": len(inter), "structures_in_no_interface_group": len(noint),
               "ineligible": len(inel), "total": len(counted), "duplicates": sorted({m for m in counted if counted.count(m) > 1}),
               "ids_equal_manifest_included": sorted(counted) == included,
               "sizes_in_display_order": [len(x["members"]) for x in T["groups"]],
               "no_interface_matches_summary": len(noint) == G["n_no_interface"]}
        row["pass"] = row["total"] == n_expected and not row["duplicates"] and row["ids_equal_manifest_included"] and row["no_interface_matches_summary"]
        ok = ok and row["pass"]
        res["cuts"][t] = row
    res["verdict"] = "PASS" if ok else "FAIL"
    res["provenance"] = pv.block("demo_retention_check", [project + "/manifest.json", gpath],
                                 "groups + no-interface + ineligible == candidates, per cut; ids equal the manifest's", {"n_expected": n_expected})
    pv.atomic_write_json(out, res)
    print("retention check: %s; %s" % (res["verdict"], "; ".join("t=%s: %d in groups + %d no-interface + %d ineligible = %d"
          % (t, r["structures_in_interface_groups"], r["structures_in_no_interface_group"], r["ineligible"], r["total"]) for t, r in res["cuts"].items())))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:5]))
