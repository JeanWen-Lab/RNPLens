"""Region rule of demo 1b (records/v04_integration/DEMOS_PLAN.md): the 10-nt window [s, s+9] (construct numbering) with
the most distinct [protein_pos, rna_pos] pairs in the union of the engine-designated structures' contact lists of
analysis/report/contacts_by_output.json; ties to the lowest start. Writes every window's count.
usage: python region_window_rule.py PROJECT ANALYSIS OUT_JSON      prints "a-b" """
import json
import os
import sys

from rnplens import provenance as pv

W = 10


def main(project, analysis, out):
    man = json.load(open(os.path.join(project, "manifest.json")))
    cbo_path = os.path.join(analysis, "report", "contacts_by_output.json")
    cbo = json.load(open(cbo_path))
    L = len("".join(l.strip() for l in open(os.path.join(project, "construct_rna.fasta")) if not l.startswith(">")))
    des = [{"id": s["id"], "run": s["run"], "sample": s["sample"], "key": "%s|%s#%s" % (s["engine"], s["run"], s["sample"])}
           for s in man["structures"] if s.get("designated")]
    for d in des:
        d["in_report_records"] = d["key"] in cbo
        d["n_contacts"] = len(cbo.get(d["key"], []))
    union = sorted({(int(p), int(r)) for d in des for p, r in cbo.get(d["key"], [])})
    if L < W:
        raise SystemExit("RNA construct shorter than the %d-nt window" % W)
    counts = [{"start": s, "end": s + W - 1, "distinct_contacts": sum(1 for p, r in union if s <= r <= s + W - 1)} for s in range(1, L - W + 2)]
    best = max(c["distinct_contacts"] for c in counts)
    pick = min(c["start"] for c in counts if c["distinct_contacts"] == best)
    doc = {"provenance": pv.block("demo_region_window_rule", [os.path.join(project, "manifest.json"), cbo_path],
                                  "10-nt window with the most distinct contacts in the union of the designated structures; ties to the lowest start",
                                  {"window_nt": W, "rule_record": "records/v04_integration/DEMOS_PLAN.md (Demo 1b)"}),
           "designated": des, "rna_length": L, "n_union_contacts": len(union), "windows": counts,
           "max_distinct_contacts": best, "n_windows_at_max": sum(1 for c in counts if c["distinct_contacts"] == best),
           "region": {"start": pick, "end": pick + W - 1, "note": "10-nt window, most distinct contacts in the designated structures' union; ties to lowest start"}}
    pv.atomic_write_json(out, doc)
    print("%d-%d" % (pick, pick + W - 1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
