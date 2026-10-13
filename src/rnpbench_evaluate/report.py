"""Write result.json, result.csv and summary.txt. No value is created or rounded here."""
from __future__ import annotations

import csv
import json
import os

CSV_COLS = [
    ("target_id", lambda r: r["target_id"]),
    ("prediction_sha256", lambda r: r["input"]["prediction"]["sha256"]),
    ("reference_sha256", lambda r: r["input"]["reference"]["sha256"]),
    ("engine", lambda r: r["input"]["prediction"].get("engine")),
    ("dockq_status", lambda r: r["dockq"]["status"]),
    ("dockq", lambda r: r["dockq"]["dockq"]),
    ("dockq_unrounded", lambda r: r["dockq"]["dockq_unrounded"]),
    ("dockq_class", lambda r: r["dockq"]["dockq_class"]),
    ("fnat", lambda r: _first(r, "fnat")),
    ("irmsd", lambda r: _first(r, "iRMSD")),
    ("lrmsd", lambda r: _first(r, "LRMSD")),
    ("selected_mapping", lambda r: r["dockq"]["selected_mapping"]),
    ("n_admissible_candidates", lambda r: r["dockq"]["n_admissible_candidates"]),
    ("n_interfaces", lambda r: r["dockq"]["n_interfaces"]),
    ("pairs_in_frame", lambda r: (r["dockq"]["correspondence"] or {}).get("in_frame")),
    ("pairs_out_of_frame", lambda r: (r["dockq"]["correspondence"] or {}).get("out_of_frame")),
    ("pairs_indeterminate", lambda r: (r["dockq"]["correspondence"] or {}).get("indeterminate")),
    ("dockq_failure_stage", lambda r: r["dockq"]["failure_stage"]),
    ("dockq_failure_reason", lambda r: r["dockq"]["failure_reason"]),
    ("geometry_status", lambda r: r["geometry"]["status"]),
    ("protein_internal_ca_rmsd", lambda r: r["geometry"].get("prot_internal_ca_rmsd")),
    ("rna_internal_c4_rmsd", lambda r: r["geometry"].get("rna_internal_c4_rmsd")),
    ("rna_placement_c4_rmsd", lambda r: r["geometry"].get("rna_placement_c4_rmsd")),
    ("n_protein_pairs", lambda r: r["geometry"].get("n_prot_aligned")),
    ("n_rna_pairs", lambda r: r["geometry"].get("n_rna_aligned")),
    ("geometry_exclusion", lambda r: r["geometry"].get("exclusion")),
]


def _first(r, k):
    per = r["dockq"].get("per_interface") or {}
    return list(per.values())[0].get(k) if per else None


def _f(v, d=3):
    return "NO VALUE" if v is None else ("%.*f" % (d, v) if isinstance(v, float) else str(v))


def summary_text(r):
    dq, g, v = r["dockq"], r["geometry"], r["validity"]
    L = []
    L.append("RNPLens Evaluate (component %s)  --  target %s" % (r["rnpbench_evaluate_version"], r["target_id"]))
    L.append("prediction  %s  (sha256 %s)" % (os.path.basename(r["input"]["prediction"]["path"]), r["input"]["prediction"]["sha256"][:16]))
    L.append("reference   %s  (sha256 %s)" % (os.path.basename(r["input"]["reference"]["path"]), r["input"]["reference"]["sha256"][:16]))
    L.append("construct   protein %d aa, RNA %d nt" % (r["input"]["construct"]["protein_length"], r["input"]["construct"]["rna_length"]))
    L.append("")
    L.append("DockQ (frozen RNPLens scoring configuration, construct-position correspondence)")
    if dq["status"] == "SCORED":
        L.append("  DockQ %s  [%s]   fnat %s   iRMSD %s A   LRMSD %s A" % (_f(dq["dockq"]), dq["dockq_class"], _f(_first(r, "fnat")), _f(_first(r, "iRMSD")), _f(_first(r, "LRMSD"))))
        c = dq["correspondence"] or {}
        L.append("  chain mapping %s (best of %d admissible); residue pairs in frame %s, out of frame %s, indeterminate %s"
                 % (dq["selected_mapping"], dq["n_admissible_candidates"], c.get("in_frame"), c.get("out_of_frame"), c.get("indeterminate")))
    else:
        L.append("  NO VALUE (not zero). stage: %s; reason: %s" % (dq["failure_stage"], dq["failure_reason"]))
    L.append("")
    L.append("Structural geometry (frozen four-axis decomposition; alignment-based correspondence)")
    if g["status"] == "COMPUTED":
        L.append("  RNA internal C4' RMSD %s A over %s nt" % (_f(g["rna_internal_c4_rmsd"], 2), g["n_rna_aligned"]))
        L.append("  RNA placement C4' RMSD after protein superposition %s A" % _f(g["rna_placement_c4_rmsd"], 2))
        L.append("  protein internal CA RMSD %s A over %s residues (whole construct; scales with length)" % (_f(g["prot_internal_ca_rmsd"], 2), g["n_prot_aligned"]))
    else:
        L.append("  NO VALUE (not zero). exclusion: %s" % g.get("exclusion"))
    L.append("")
    L.append("Validity: protein chain %s, RNA chain %s; model numbering usable as construct positions: %s"
             % (v["prediction_has_protein_chain"], v["prediction_has_rna_chain"], v["model_numbering_usable_as_construct_positions"]))
    for c, x in (v.get("prediction_residues_vs_construct") or {}).items():
        if isinstance(x, dict) and "residues" in x:
            L.append("Prediction chain %s (%s): %d residues, %d letters equal to the construct at their residue number, %d numbered outside the construct"
                     % (c, x["kind"], x["residues"], x["letters_equal_to_construct"], x["numbered_outside_construct"]))
    ck = r["input"].get("construct_checks") or {}
    na = lambda v: "not assessable (no _entity_poly sequence in reference)" if v is None else v
    L.append("Construct equals a reference entity sequence: protein %s, RNA %s"
             % (na(ck.get("protein_construct_equals_a_reference_entity_sequence")), na(ck.get("rna_construct_equals_a_reference_entity_sequence"))))
    for side in ("protein", "rna"):
        dd = ck.get("%s_positions_differing_from_same_length_entity" % side)
        if dd:
            L.append("  %s construct differs from the reference entity at %s (X = modified residue in the reference); reported, not corrected"
                     % (side, ", ".join("%d %s/%s" % (x["position"], x["construct"], x["reference"]) for x in dd[:8]) + (" ..." if len(dd) > 8 else "")))
    L.append("")
    L.append("Software: DockQ %s, gemmi %s, biopython %s, numpy %s, python %s" % tuple(r["provenance"]["software_versions"].get(k) for k in ("DockQ", "gemmi", "biopython", "numpy", "python")))
    L.append("These are reference-based accuracy measurements of one prediction. They are not a confidence estimate.")
    return "\n".join(L) + "\n"


def write(r, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    existing = [f for f in ("result.json", "result.csv", "summary.txt") if os.path.exists(os.path.join(out_dir, f))]
    if existing:
        raise FileExistsError("output directory already holds %s; choose a new directory (results are never overwritten)" % existing)
    json.dump(r, open(os.path.join(out_dir, "result.json"), "w"), indent=1)
    with open(os.path.join(out_dir, "result.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([c for c, _ in CSV_COLS])
        w.writerow(["NO_VALUE" if (v := f(r)) is None and c not in ("engine", "dockq_failure_stage", "dockq_failure_reason", "geometry_exclusion") else ("" if v is None else v) for c, f in CSV_COLS])
    open(os.path.join(out_dir, "summary.txt"), "w").write(summary_text(r))
    return [os.path.join(out_dir, f) for f in ("result.json", "result.csv", "summary.txt")]
