"""Region rule fixed in records/v04_integration/DEMOS_PLAN.md before any contact was looked at.

D = the engine-designated structures of project/manifest.json (designated == true); S = every RNA position in a
[protein_pos, rna_pos] pair of analysis/report/contacts_by_output.json for the keys of D; region = [min S, max S]
(construct numbering). If S is empty, the whole RNA construct is used and this is stated.

usage: python region_rule.py PROJECT ANALYSIS OUT_JSON      prints "a-b"
"""
import json
import os
import sys

from rnplens import provenance as pv


def main(project, analysis, out):
    man = json.load(open(os.path.join(project, "manifest.json")))
    cbo_path = os.path.join(analysis, "report", "contacts_by_output.json")
    cbo = json.load(open(cbo_path))
    rna_len = len("".join(l.strip() for l in open(os.path.join(project, "construct_rna.fasta")) if not l.startswith(">")))
    designated = []
    for s in man["structures"]:
        if s.get("designated"):
            key = "%s|%s#%s" % (s["engine"], s["run"], s["sample"])
            designated.append({"id": s["id"], "run": s["run"], "sample": s["sample"], "key": key,
                               "in_report_records": key in cbo,
                               "evidence_id": pv.evidence_id("report/contacts_by_output.json", "/" + key.replace("~", "~0").replace("/", "~1"))})
    S = sorted({int(p[1]) for d in designated for p in cbo.get(d["key"], [])})
    if S:
        a, b, note = S[0], S[-1], "union of RNA contact positions of the designated structures"
    else:
        a, b, note = 1, rna_len, "no contact in any designated structure: whole RNA construct used"
    doc = {"provenance": pv.block("demo_region_rule", [project + "/manifest.json", cbo_path],
                                  "region = [min, max] of RNA positions in the designated structures' Report contacts",
                                  {"rule_record": "records/v04_integration/DEMOS_PLAN.md"}),
           "rule": "region = [min S, max S], S = RNA positions contacted in the engine-designated structures (Report's contacts_by_output.json)",
           "designated": designated, "rna_positions_S": S, "rna_length": rna_len,
           "region": {"start": a, "end": b, "note": note}}
    pv.atomic_write_json(out, doc)
    print("%d-%d" % (a, b))


if __name__ == "__main__":
    main(*sys.argv[1:4])
