"""Template answer to "Which protein residues contact this RNA region, and which exact contacts differ between runs?"
built only from ANALYSIS/region_<a>-<b>/region.json (every value cites its evidence ID). No language model.

usage: python region_answer.py ANALYSIS REGION_DIR OUT_MD OUT_JSON
"""
import json
import os
import sys

from rnplens import provenance as pv, trace


def k_of_n(s):
    x = s["structures"]
    t = "%d of %d" % (x["count"], x["of"])
    if x.get("not_observed"):
        t += " (%d not observed)" % x["not_observed"]
    return t


def add_t(s):
    a = s["additional_samples"]
    if not a["of"]:
        return "none"
    t = "%d of %d" % (a["count"], a["of"])
    if a.get("not_observed"):
        t += " (%d not observed)" % a["not_observed"]
    return t


def main(analysis, rdir, out_md, out_json):
    rp = os.path.join(analysis, rdir, "region.json")
    R = json.load(open(rp))
    S, reg = R["summary"], R["region"]["rna"]
    runs = [r["run"] for r in R["runs"]]
    L = []
    L.append("## Results of this run (template answer from `%s/region.json`)" % rdir)
    L.append("")
    L.append("Region: %s, `%s` (%d nt), construct numbering. [%s]" % (reg["label"], reg["sequence"], reg["length"], R["region"]["evidence_id"]))
    L.append("")
    L.append("### Structures compared")
    L.append("")
    L.append("| run | structures compared | engine-designated structure (rule) | coverage COMPLETE / PARTIAL / UNRESOLVED | not compared | evidence |")
    L.append("|---|---|---|---|---|---|")
    for r in R["runs"]:
        c = r["coverage_counts"]
        L.append("| %s | %d | %s (%s) | %d / %d / %d | %d | `%s` |" % (r["run"], r["n_compared"], r["designated_structure"], r["designated_rule"],
                 c["COMPLETE"], c["PARTIAL"], c["UNRESOLVED"], len(r["not_compared"]), r["evidence_id"]))
    L.append("")
    L.append("### Overview counts")
    L.append("")
    L.append("- Contacts listed in the region by any compared structure: %d [`%s`]" % (S["n_contacts_in_range"]["count"], S["n_contacts_in_range"]["evidence_id"]))
    L.append("- Shared by all runs: %d [`%s`]" % (S["shared_by_all_runs"]["count"], S["shared_by_all_runs"]["evidence_id"]))
    for run in runs:
        o = S["only_in_run"].get(run)
        if o is not None:
            L.append("- Found only in run %s: %d (%s) [`%s`]" % (run, o["count"], ", ".join(o["contacts"]) or "none", o["evidence_id"]))
    L.append("- Present in some runs: %d [`%s`]" % (S["present_in_some_runs"]["count"], S["present_in_some_runs"]["evidence_id"]))
    L.append("- Not determined in some run: %d [`%s`]" % (S["not_determined"]["count"], S["not_determined"]["evidence_id"]))
    L.append("")
    # protein residues contacting the region
    prot = {}
    for c in R["contacts"]:
        prot.setdefault((c["protein_position"], c["protein_label"]), []).append(c)
    L.append("### Protein residues that contact the region (%d residues)" % len(prot))
    L.append("")
    L.append("| protein residue | contacts (RNA nucleotide: runs listing it) |")
    L.append("|---|---|")
    for (pos, lab), cs in sorted(prot.items()):
        L.append("| %s | %s |" % (lab, "; ".join("%s: %s [`%s`]" % (c["rna_label"], ",".join(c["runs"]["present"]) or "none", c["evidence_id"]) for c in cs)))
    L.append("")
    diff = [c for c in R["contacts"] if c["presence"] != "SHARED_BY_ALL_RUNS"]
    L.append("### Contacts that differ between runs (%d)" % len(diff))
    L.append("")
    if diff:
        L.append("| contact | class | " + " | ".join("%s: designated / k of n / additional samples / structures with it" % r for r in runs) + " | evidence |")
        L.append("|---|---|" + "---|" * len(runs) + "---|")
        for c in diff:
            cells = []
            for r in runs:
                s = c["per_run"][r]
                d = s["designated"]
                cells.append("%s / %s / %s / %s" % (d.get("observation") if d else "not compared", k_of_n(s), add_t(s),
                                                     ", ".join("%s:%s" % (w["id"], w["sample"]) for w in s["structures"]["with_contact"]) or "none"))
            cls = c["presence"] + (" (%s)" % c["only_in_run"] if c.get("only_in_run") else "")
            L.append("| %s | %s | %s | `%s` |" % (c["label"], cls, " | ".join(cells), c["evidence_id"]))
    else:
        L.append("Every contact listed in the region is listed by at least one structure of every run.")
    L.append("")
    L.append("### Shared contacts: designated structures and additional samples")
    L.append("")
    L.append("| contact | " + " | ".join("%s: designated / k of n / additional samples" % r for r in runs) + " | evidence |")
    L.append("|---|" + "---|" * len(runs) + "---|")
    for c in R["contacts"]:
        if c["presence"] == "SHARED_BY_ALL_RUNS":
            L.append("| %s | %s | `%s` |" % (c["label"], " | ".join("%s / %s / %s" % ((c["per_run"][r]["designated"] or {}).get("observation", "not compared"),
                     k_of_n(c["per_run"][r]), add_t(c["per_run"][r])) for r in runs), c["evidence_id"]))
    L.append("")
    L.append("Region map: `%s/%s` (state %s). Limits recorded with this output:" % (rdir, R["figure"]["file"], R["figure"]["state"]))
    L.append("")
    for i, l in enumerate(R["limits"]):
        L.append("- %s [`%s/region.json#/limits/%d`]" % (l, rdir, i))
    text = "\n".join(L) + "\n"
    body = "\n".join(L[:-len(R["limits"]) - 1])           # the recorded limits are quoted verbatim (they say what is NOT shown)
    bad = trace.wording_audit(body)
    if bad:
        print("wording audit refused the answer:", bad)
        return 1
    pv.atomic_write_text(out_md, text)
    pv.atomic_write_json(out_json, {"provenance": pv.block("demo_region_answer", [rp], "template answer built from region.json only", {"region_dir": rdir}),
                                    "region": reg, "n_protein_residues": len(prot), "protein_residues": [lab for (_, lab) in sorted(prot)],
                                    "differing_contacts": [{"label": c["label"], "presence": c["presence"], "only_in_run": c.get("only_in_run"),
                                                            "evidence_id": c["evidence_id"]} for c in diff],
                                    "wording_audit": bad})
    print("answer: %d protein residues contact %s; %d contacts differ between runs" % (len(prot), reg["label"], len(diff)))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:5]))
