"""Target rule of demo 1b (records/v04_integration/DEMOS_PLAN.md): the first of 1VTM, 24BR, 2JEA, 2Q66, 2QQP, 2XGJ whose
pilot Boltz YAML declares exactly one protein and one RNA entry, with RNA >= 20 nt, and whose exec_A and exec_B
prediction folders each hold 5 structures and 5 confidence files. Fallback: 6BJG split by sample index parity.
Reads only the YAMLs of the targets examined (in order, stopping at the first that qualifies) and lists only the
selected targets' predictions folders. usage: python select_target.py PILOT_ROOT OUT_JSON   (prints the target)"""
import glob
import json
import os
import sys

from rnplens import provenance as pv

ORDER = ["1VTM", "24BR", "2JEA", "2Q66", "2QQP", "2XGJ"]
MIN_RNA = 20


def parse(path):
    entries, kind = [], None
    for line in open(path):
        s = line.strip()
        if s.startswith("- protein:"):
            kind = "protein"; entries.append([kind, None])
        elif s.startswith("- rna:"):
            kind = "rna"; entries.append([kind, None])
        elif s.startswith(("- dna:", "- ligand:")):
            kind = "other"; entries.append([kind, None])
        elif s.startswith("sequence:") and entries and entries[-1][1] is None:
            entries[-1][1] = s.split(":", 1)[1].strip()
    return entries


def main(pilot, out):
    rows, chosen, allowed = [], None, []
    for t in ORDER:
        y = os.path.join(pilot, "inputs", "boltz", t + ".yaml")
        allowed.append(y)
        e = parse(y)
        kinds = [k for k, _ in e]
        rna = [s for k, s in e if k == "rna"]
        row = {"target": t, "yaml": y, "entries": kinds, "one_protein_one_rna": kinds.count("protein") == 1 and kinds.count("rna") == 1 and len(kinds) == 2,
               "rna_length": len(rna[0]) if len(rna) == 1 and rna[0] else None}
        row["rna_ge_20"] = bool(row["rna_length"] and row["rna_length"] >= MIN_RNA)
        if row["one_protein_one_rna"] and row["rna_ge_20"]:
            cnt = {}
            for ex in ("exec_A", "exec_B"):
                d = os.path.join(pilot, "boltz", ex, t, "boltz_results_" + t, "predictions", t)
                cnt[ex] = [len(glob.glob(os.path.join(d, t + "_model_*.pdb"))), len(glob.glob(os.path.join(d, "confidence_" + t + "_model_*.json")))]
            row["files_per_run"] = cnt
            row["five_and_five"] = all(v == [5, 5] for v in cnt.values())
        row["qualifies"] = bool(row["one_protein_one_rna"] and row["rna_ge_20"] and row.get("five_and_five"))
        rows.append(row)
        if row["qualifies"]:
            chosen = t
            allowed += [os.path.join(pilot, "boltz", ex, t, "boltz_results_" + t, "predictions", t) + "/" for ex in ("exec_A", "exec_B")]
            break
    doc = {"provenance": pv.block("demo_target_rule", [r["yaml"] for r in rows], "first listed stress-cohort target with one protein, one RNA >= 20 nt and 5+5 structures per run",
                                  {"order": ORDER, "min_rna_nt": MIN_RNA, "rule_record": "records/v04_integration/DEMOS_PLAN.md (Demo 1b)"}),
           "examined": rows, "selected": chosen or "6BJG_PARITY_FALLBACK", "allowed_pcfold_paths": allowed}
    pv.atomic_write_json(out, doc)
    print(doc["selected"])


if __name__ == "__main__":
    main(*sys.argv[1:3])
