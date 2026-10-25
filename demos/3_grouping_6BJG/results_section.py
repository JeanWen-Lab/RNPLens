"""Results section of demonstration 3, from its records only: python results_section.py ANALYSIS G H OUT_MD"""
import json
import os
import sys


def main(analysis, g, h, out):
    G = json.load(open(os.path.join(analysis, "groups", "groups.json")))
    D = json.load(open(os.path.join(analysis, "groups", "diff_%s_%s" % (g, h), "diff.json")))
    R = json.load(open("retention_check.json"))
    P = json.load(open("docs_parity.json"))
    L = ["## Results of this run (from `analysis/groups/groups.json`, `diff_%s_%s/diff.json`, `retention_check.json`, `docs_parity.json`)" % (g, h), ""]
    L.append("Structures: %d in the manifest, %d eligible, %d with an interface, %d with no interface, %d ineligible. [`groups/groups.json`]"
             % (G["n_structures"], G["n_eligible"], G["n_interface"], G["n_no_interface"], len(G["ineligible"])))
    L.append("")
    L.append("| cut | groups | surface groups | group sizes in display order (never ordered by size) | evidence |")
    L.append("|---|---|---|---|---|")
    for t in G["thresholds_reported"]:
        T = G["thresholds"][t]
        L.append("| t = %s%s | %d | %d | %s | `groups/groups.json#/thresholds/%s` |" % (t, " (primary)" if t == G["primary_threshold"] else "",
                 T["n_groups"], T["n_surface_groups"], ", ".join(str(x["size"]) for x in T["groups"]), t))
    L.append("")
    T = G["thresholds"][G["primary_threshold"]]
    L.append("At the primary cut t = %s:" % G["primary_threshold"])
    L.append("")
    L.append("| group | size | engine-weighted size | representative | engine-designated structure | mean R of members to representative | P spread, A (min / median / max) | evidence |")
    L.append("|---|---|---|---|---|---|---|---|")
    for x in T["groups"]:
        sp = x["rna_pose_difference_spread_A"] or {}
        mr = x.get("mean_R_members_to_representative")
        L.append("| %d | %d | %s | %s | %s | %s | %s | `%s` |" % (x["group"], x["size"], x["engine_weighted_size"]["fraction"], x["representative"]["id"],
                 "; ".join(d["text"].replace("engine-designated structure", d["id"]) for d in x["designated_members"]) or "-",
                 "-" if mr is None or x["size"] == 1 else "%.3f" % mr,
                 "-" if sp.get("min") is None else "%.2f / %.2f / %.2f" % (sp["min"], sp["median"], sp["max"]), x["evidence_id"]))
    L.append("")
    L.append("Size note recorded with every group: \"%s\"" % G["size_note"])
    L.append("")
    L.append("**Difference map, group %s (holds the engine-designated structure) vs group %s (next in display order)** [`groups/diff_%s_%s/diff.json`]:" % (g, h, g, h))
    L.append("")
    for k, v in D["counts"].items():
        L.append("- %s: %d" % (k, v))
    for cat in ("frequent in group %s only" % g, "frequent in group %s only" % h):
        rows = [r for r in D["rows"] if r["category"] == cat]
        L.append("- %s: %s" % (cat, ", ".join("%s%d-%s%d (%s of members; %s) [`%s`]" % (r["protein_residue"], r["protein_position"], r["rna_nucleotide"],
                 r["rna_position"], r["A"]["fraction"] if cat.endswith("%s only" % g) else r["B"]["fraction"],
                 "other group %s" % (r["B"]["fraction"] if cat.endswith("%s only" % g) else r["A"]["fraction"]), r["evidence_id"]) for r in rows)))
    nobs = sum(len(r["A"]["not_observed"]) + len(r["B"]["not_observed"]) for r in D["rows"])
    L.append("- members with a position not observed, over all listed rows: %d" % nobs)
    L.append("")
    L.append("Caveat recorded with every row: \"%s\"" % D["caveat"])
    L.append("")
    L.append("**Check: every original candidate retained** (`retention_check.json`): **%s**." % R["verdict"])
    L.append("")
    for t, r in sorted(R["cuts"].items()):
        L.append("- t = %s: %d in interface groups + %d in the no-interface group + %d ineligible = %d of %d; duplicates %s; ids equal the manifest's included ids: %s"
                 % (t, r["structures_in_interface_groups"], r["structures_in_no_interface_group"], r["ineligible"], r["total"], R["n_expected"],
                    r["duplicates"] or "none", r["ids_equal_manifest_included"]))
    L.append("")
    L.append("**Check: documented 6BJG numbers of docs/grouping.md reproduced** (`docs_parity.json`): **%s** (%d of %d checks equal)." % (P["verdict"], P["n_equal"], P["n_checks"]))
    L.append("")
    L.append("**Check: wording** (`checks/wording_scan.json`): written after this section; see `DEMOS_REPORT.md` for the result.")
    open(out, "w").write("\n".join(L) + "\n")
    print("results section written: %s" % out)


if __name__ == "__main__":
    main(*sys.argv[1:5])
