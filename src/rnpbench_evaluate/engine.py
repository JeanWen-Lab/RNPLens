"""One evaluation: a prediction against an experimental reference, under the frozen RNPBench rules.

Two frozen routes are called, and their outputs are kept apart because they are different objects:

1. DockQ route -- the released RNPBench scoring configuration
   (``RNPBENCH_SCORING_V3_CONSTRUCT_POSITION_DOCKQ_2_1_3``): DockQ 2.1.3's own candidate chain
   mappings, the polymer-class admissibility restriction, construct-position residue correspondence
   (``pos_adapter.one_row``) and the released selection/reporting convention (``rf2na_scoring.select``,
   parity-proven against the released store).
2. Geometry route -- the frozen four-axis decomposition (``score_decomp.four_axes``): protein Calpha
   RMSD after protein superposition, RNA C4' RMSD after RNA superposition, and RNA C4' placement RMSD
   after protein superposition, on the contacting protein-RNA chain pair chosen by the project's own
   rule, with its own sequence-alignment correspondence.

This module only stages inputs where the frozen code expects them, calls it, and copies its results
into the report. It computes no metric of its own.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile

from . import __version__
from . import frozen_loader

CONFIG_ID = "RNPBENCH_SCORING_V3_CONSTRUCT_POSITION_DOCKQ_2_1_3"
GEOMETRY_ID = "RNPBENCH_FOUR_AXIS_DECOMPOSITION_SCORE_DECOMP_V1"
PINNED = {"DockQ": "2.1.3"}
DOCKQ_BINS = ((0.23, "incorrect"), (0.49, "acceptable"), (0.80, "medium"), (float("inf"), "high"))

_CACHE = {}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def versions():
    from importlib import metadata
    out = {"python": platform.python_version(), "platform": platform.platform()}
    for d in ("DockQ", "gemmi", "biopython", "numpy", "scipy"):
        try:
            out[d] = metadata.version(d)
        except metadata.PackageNotFoundError:
            out[d] = None
    return out


def frozen(allow_unpinned=False):
    if "ns" not in _CACHE:
        v = versions()
        for k, want in PINNED.items():
            if v.get(k) != want and not allow_unpinned:
                raise RuntimeError("%s %s is installed; the frozen RNPLens scoring configuration requires %s %s. "
                                   "Install the pinned version (see environment.yml)." % (k, v.get(k), k, want))
        ns, rec = frozen_loader.load({"P": None, "REP": None})
        _CACHE["ns"], _CACHE["rec"] = ns, rec
    return _CACHE["ns"], _CACHE["rec"]


def _jsonable(o):
    if hasattr(o, "item"):
        return o.item()
    if isinstance(o, (set, frozenset, tuple)):
        return list(o)
    return str(o)


def _clean(o):
    return json.loads(json.dumps(o, default=_jsonable))


def dockq_class(v):
    if v is None:
        return None
    for hi, lab in DOCKQ_BINS:
        if v < hi:
            return lab


PROT3 = {"ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
         "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V"}


def prediction_vs_construct(pred, construct):
    """Descriptive only (never used in scoring): for each prediction chain, compare the residue at each
    residue number with the construct letter at that position (residue numbers read as 1-based
    construct positions, as the frozen correspondence does)."""
    import gemmi
    out = {}
    try:
        st = gemmi.read_structure(pred)
        st.setup_entities()
    except Exception as ex:
        return {"error": type(ex).__name__}
    for ch in st[0]:
        pt = ch.get_polymer().check_polymer_type()
        if pt in (gemmi.PolymerType.PeptideL, gemmi.PolymerType.PeptideD):
            kind, seq, conv = "protein", construct["protein_sequence"], lambda n: PROT3.get(n, "X")
        elif pt == gemmi.PolymerType.Rna:
            kind, seq, conv = "rna", construct["rna_sequence"], lambda n: n[-1] if n and n[-1] in "ACGU" and len(n) <= 2 else "X"
        else:
            continue
        n = eq = outside = 0
        diffs = []
        for r in ch:
            if r.het_flag == "H" and kind == "protein" and r.name not in PROT3:
                continue
            n += 1; p = r.seqid.num
            if p < 1 or p > len(seq):
                outside += 1; continue
            a, b = conv(r.name), seq[p - 1]
            if a == b:
                eq += 1
            elif len(diffs) < 8:
                diffs.append({"position": p, "prediction": r.name, "construct": b})
        out[ch.name] = {"kind": kind, "residues": n, "letters_equal_to_construct": eq, "numbered_outside_construct": outside,
                        "first_differences": diffs}
    return out


def evaluate(inp, allow_unpinned=False, keep_stage=False, workdir=None):
    """``inp`` is a validated input contract (see contract.py). Returns the result record."""
    ns, rec = frozen(allow_unpinned)
    PA, SEL, SD, FEAT, A = ns["pos_adapter"], ns["rf2na_scoring"], ns["score_decomp"], ns["feat"], ns["corr_mask_audit"]
    tid = inp["target_id"]
    pred, ref = inp["prediction"]["path"], inp["reference"]["path"]
    psha, rsha = sha256(pred), sha256(ref)
    tol = int(inp.get("options", {}).get("tolerance", 0))
    stage = tempfile.mkdtemp(prefix="rnpbench_eval_", dir=workdir)
    try:
        os.makedirs(os.path.join(stage, "references"))
        os.makedirs(os.path.join(stage, "reports"))
        shutil.copyfile(ref, os.path.join(stage, "references", tid + ".cif"))
        json.dump({"targets": [{"target": tid, "protein_sequence": inp["construct"]["protein_sequence"],
                                "rna_sequence": inp["construct"]["rna_sequence"]}]},
                  open(os.path.join(stage, "reports", "jpf_rnpbench_pilot_target_key.json"), "w"))
        PA.P, PA.REP = stage, os.path.join(stage, "reports")
        row = {"target": tid, "structure_checksum": psha, "tolerance": tol,
               "_engine": inp["prediction"].get("engine") or "UNSPECIFIED", "_execution": "user"}
        # ---------------- DockQ route (frozen) ----------------
        raw = PA.one_row(row, {psha: pred})
        sel = SEL.select(raw)
        per = None
        if sel.get("status") == "SCORED":
            match = [c for c in raw["candidates"] if c["mapping"] == sel["selected_mapping"]
                     and c["adapter"].get("outcome") == "SCORED"]
            assert len(match) == 1, "selected mapping is not unique among scored candidates"
            per = match[0]["adapter"].get("per_interface")
            first = list(per.values())[0]["DockQ"] if per else None
            assert first is not None and round(float(first), 3) == sel["dockq"], "per-interface record disagrees with the selection"
        model_num = A.model_numbering_check(pred, A.construct_lengths(tid, {tid: {
            "protein_sequence": inp["construct"]["protein_sequence"], "rna_sequence": inp["construct"]["rna_sequence"]}}))
        dockq = {
            "configuration": CONFIG_ID,
            "status": sel.get("status"),
            "dockq": sel.get("dockq"),
            "dockq_unrounded": sel.get("dockq_unrounded"),
            "dockq_class": dockq_class(sel.get("dockq_unrounded")),
            "reported_statistic": "first interface in DockQ's own iteration order, rounded to 3 decimals (the frozen convention)",
            "selected_mapping": sel.get("selected_mapping"),
            "n_admissible_candidates": raw.get("n_admissible_candidates"),
            "n_interfaces": sel.get("n_interfaces"),
            "adapter_total_dockq": sel.get("adapter_total_dockq"),
            "correspondence": sel.get("correspondence"),
            "per_interface": per,
            "failure_stage": sel.get("failure_stage"),
            "failure_reason": sel.get("failure_reason"),
            "failure_detail": sel.get("failure_detail"),
            "outcomes_seen": sel.get("outcomes_seen"),
            "candidate_outcomes": ([{"mapping": c["mapping"], "outcome": c["adapter"].get("outcome"),
                                     "total_dockq": c["adapter"].get("total_dockq"),
                                     "exception": c["adapter"].get("exception")} for c in raw.get("candidates", [])]
                                   if raw.get("status") == "EVALUATED" else None),
            "model_numbering": model_num,
            "tolerance": tol,
        }
        if dockq["status"] != "SCORED":
            dockq["dockq"] = None
            dockq["no_value_note"] = ("NO VALUE: this is not DockQ = 0. The frozen rules give no accuracy value "
                                      "for this input; see failure_stage / failure_reason.")
        # ---------------- geometry route (frozen) ----------------
        nat_rna, nat_prot, err = SD.read_pose(ref)
        if err:
            geom = {"status": "NO_VALUE", "exclusion": "reference_" + err}
        else:
            g = SD.four_axes(pred, nat_rna, nat_prot)
            geom = {"status": "NO_VALUE" if g.get("exclusion") else "COMPUTED", **g}
        try:
            geom["chains_used"] = {"prediction": list(FEAT.contacting_pair(FEAT.load(pred))),
                                   "reference": list(FEAT.contacting_pair(FEAT.load(ref)))}
        except Exception as ex:  # chain choice is provenance only
            geom["chains_used"] = {"error": type(ex).__name__}
        geom["configuration"] = GEOMETRY_ID
        geom["correspondence_note"] = ("contacting protein-RNA chain pair chosen by the project's rule; residue "
                                       "correspondence by sequence alignment, not construct positions; "
                                       "a different route from the DockQ correspondence")
        if geom["status"] != "COMPUTED":
            geom["no_value_note"] = "NO VALUE: geometry could not be computed for this input (see exclusion)."
        # ---------------- validity summary ----------------
        try:
            kinds = [FEAT.chain_kind(ch)[0] for ch in next(iter(FEAT.load(pred)))]
        except Exception as ex:
            kinds = ["unreadable:" + type(ex).__name__]
        validity_seq = prediction_vs_construct(pred, inp["construct"])
        validity = {
            "prediction_residues_vs_construct": validity_seq,
            "prediction_chain_kinds": kinds,
            "prediction_has_protein_chain": "prot" in kinds,
            "prediction_has_rna_chain": "rna" in kinds,
            "model_numbering_usable_as_construct_positions": {c: v["usable_as_construct_positions"] for c, v in model_num.items()},
            "evaluable_dockq": dockq["status"] == "SCORED",
            "evaluable_geometry": geom["status"] == "COMPUTED",
        }
        result = {
            "rnpbench_evaluate_version": __version__,
            "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "target_id": tid,
            "input": {"prediction": {**inp["prediction"], "sha256": psha},
                      "reference": {**inp["reference"], "sha256": rsha},
                      "construct": {"protein_length": len(inp["construct"]["protein_sequence"]),
                                    "rna_length": len(inp["construct"]["rna_sequence"]),
                                    "protein_sequence": inp["construct"]["protein_sequence"],
                                    "rna_sequence": inp["construct"]["rna_sequence"]},
                      "construct_checks": inp.get("_checks")},
            "dockq": dockq,
            "geometry": geom,
            "validity": validity,
            "provenance": {"software_versions": versions(),
                           "frozen_sources": {k: v["sha256"] for k, v in rec["manifest"]["files"].items()},
                           "frozen_origin": rec["manifest"].get("origin"),
                           "frozen_execution_record": "rnplens evaluate provenance --full prints every executed top-level statement and its hash"},
        }
        return _clean(result)
    finally:
        PA.P = PA.REP = None
        if not keep_stage:
            shutil.rmtree(stage, ignore_errors=True)
