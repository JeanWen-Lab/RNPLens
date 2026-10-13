"""Reference-free agreement over a validated contract.

WHAT THIS COMPUTES, AND WHAT IT REFUSES TO COMPUTE. Three separable questions, never collapsed into one score:
binding surface, RNA pose after protein superposition, and contact register. Cross-engine support is a COUNT of
eligible engines, and every engine with repeated executions contributes the fraction of its own executions, so
an engine cannot weigh more because it ran more often. Interface hypotheses are groups of engines listed
separately at three thresholds and are never averaged.

  Agreement is descriptive evidence about convergence of predicted interface hypotheses. It is NOT a
  probability of structural correctness. (RNPBENCH_PREDICT_PROTOTYPE_FREEZE_V1)

OUTCOME CODES, each a first-class result rather than a degraded number:
  ELIGIBLE                     both polymers present, every chain matches its declared length
  INELIGIBLE_POLYMER_ABSENT    one polymer is missing entirely -- not a low-confidence prediction of the
                               complex, but not a prediction of it at all
  INDEXING_UNVERIFIED          a chain length disagrees with the contract, so input numbering cannot be used
  CHECKSUM_MISMATCH            the file changed after the contract registered it
  ERROR                        parsing or computation failed; the exception class and message are recorded
An ELIGIBLE output with no protein-RNA contact inside the cutoff additionally carries
no_interface_contact=True: it predicted both polymers but no interface, which must never be read as agreement.

DETERMINISM. Contacts are sorted; weighted-Jaccard keys are sorted before summation; engines and pairs are
iterated in sorted order; the worker pool preserves input order. Two runs on the same contract and the same
package produce byte-identical JSON.
"""
import collections
import itertools
import json
import multiprocessing as mp
import os
import platform
import sys
import time

import numpy as np

from . import contract as contract_mod
from . import geometry, native

HYPOTHESIS_THRESHOLDS = (0.3, 0.5, 0.7)
PRIMARY_THRESHOLD = 0.5


def environment_fingerprint():
    """Versions actually in use. matplotlib is optional: the core computes and writes JSON without it, and only
    the HTML report needs it, so a pipeline user is not forced to install a plotting stack."""
    import Bio
    try:
        import matplotlib
        mpl_version = matplotlib.__version__
    except ImportError:
        mpl_version = "not installed (HTML report unavailable; JSON output unaffected)"
    return {"python": sys.version.split()[0], "platform": platform.platform(),
            "numpy": np.__version__, "biopython": Bio.__version__, "matplotlib": mpl_version,
            "package_version": VERSION}


VERSION = "rnpbench-predict-1.0.0"


def analyse_output(job):
    """One contract output -> its per-output record. Pure function of the job dict, for pool determinism."""
    row, lp, lr = job["output"], job["protein_length"], job["rna_length"]
    out = {"engine": row["engine"], "execution": row["execution"], "structure_path": row["structure_path"],
           "sha256": row["sha256"]}
    try:
        if contract_mod.sha256(row["structure_path"]) != row["sha256"]:
            out["state"] = "CHECKSUM_MISMATCH"
            return out
        model = geometry.parse_model(row["structure_path"])
        prot, rna, order = geometry.split_chains(model)
        out["n_protein_copies"], out["n_rna_copies"] = len(prot), len(rna)
        out["chain_lengths"] = [[c, len(res)] for c, res in prot + rna]
        if not prot or not rna:
            out["state"] = "INELIGIBLE_POLYMER_ABSENT"
            return out
        if any(len(res) != lp for _, res in prot) or any(len(res) != lr for _, res in rna):
            out["state"] = "INDEXING_UNVERIFIED"
            out["declared_lengths"] = {"protein": lp, "rna": lr}
            return out
        contacts, surface = geometry.interface_contacts(prot, rna)
        ca, c4 = geometry.backbone_tracks(prot, rna)
        v, kind = native.resolve(row["engine"], row["structure_path"], row["confidence_dir"], order,
                                 (row["native_confidence"], row["native_confidence_kind"]))
        out.update({"state": "ELIGIBLE", "contacts": contacts, "surface": surface,
                    "n_contacts": len(contacts), "n_surface": len(surface),
                    "no_interface_contact": len(contacts) == 0,
                    "native": v, "native_kind": kind, "ca": ca, "c4": c4})
    except Exception as ex:
        out["state"] = "ERROR"
        out["error"] = "%s: %s" % (type(ex).__name__, str(ex)[:200])
    return out


def _occupancy(outputs_for_engine):
    """Per-engine occupancy maps: each execution contributes 1/n, so repeats do not inflate an engine."""
    n = len(outputs_for_engine)
    contacts, surface = {}, {}
    for o in outputs_for_engine:
        for x in o["contacts"]:
            key = tuple(x)
            contacts[key] = contacts.get(key, 0) + 1.0 / n
        for x in o["surface"]:
            surface[x] = surface.get(x, 0) + 1.0 / n
    return contacts, surface


def run(validated_contract, nproc=None):
    """-> result dict. Reads only the contract; opens no reference structure and computes no accuracy."""
    t0 = time.time()
    c = validated_contract
    lp, lr = c["construct"]["protein_length"], c["construct"]["rna_length"]
    jobs = [{"output": o, "protein_length": lp, "rna_length": lr} for o in c["outputs"]]
    n = int(nproc or os.environ.get("RNPBENCH_PREDICT_NPROC", "1"))
    if n > 1 and len(jobs) > 1:
        with mp.get_context("fork").Pool(min(n, len(jobs))) as pool:
            records = pool.map(analyse_output, jobs, chunksize=1)
    else:
        records = [analyse_output(j) for j in jobs]

    eligible = [r for r in records if r["state"] == "ELIGIBLE"]
    engines = sorted({r["engine"] for r in eligible})
    by_engine = {e: [r for r in eligible if r["engine"] == e] for e in engines}
    occ_c, occ_s = {}, {}
    for e in engines:
        occ_c[e], occ_s[e] = _occupancy(by_engine[e])

    pairs = []
    pair_index = {}
    for a, b in itertools.combinations(engines, 2):
        poses, capped = [], False
        for x in by_engine[a]:
            for y in by_engine[b]:
                p, cp = geometry.rna_pose_difference(x, y)
                capped = capped or bool(cp)
                if p is not None:
                    poses.append(p)
        rec = {"engine_a": a, "engine_b": b,
               "surface_agreement": geometry.weighted_jaccard(occ_s[a], occ_s[b]),
               "register_agreement": geometry.weighted_jaccard(occ_c[a], occ_c[b]),
               "rna_pose_difference_A": (sum(sorted(poses)) / len(poses)) if poses else None,
               "rna_pose_copy_permutation_capped": capped,
               "n_output_pairs_compared": len(poses)}
        pairs.append(rec)
        pair_index[(a, b)] = rec

    hypotheses = {}
    for th in HYPOTHESIS_THRESHOLDS:
        edges = [(k[0], k[1]) for k, v in sorted(pair_index.items())
                 if v["register_agreement"] is not None and v["register_agreement"] >= th]
        hypotheses[str(th)] = geometry.connected_groups(engines, edges)

    support = {}
    for e in engines:
        for key, f in occ_c[e].items():
            support[key] = support.get(key, 0) + f

    repeats = {}
    for e in engines:
        if len(by_engine[e]) == 2:
            a, b = by_engine[e]
            pose, capped = geometry.rna_pose_difference(a, b)
            repeats[e] = {"surface_agreement": geometry.weighted_jaccard({x: 1 for x in a["surface"]},
                                                                        {x: 1 for x in b["surface"]}),
                          "register_agreement": geometry.weighted_jaccard({tuple(x): 1 for x in a["contacts"]},
                                                                          {tuple(x): 1 for x in b["contacts"]}),
                          "rna_pose_difference_A": pose, "rna_pose_copy_permutation_capped": bool(capped)}

    def med(vals):
        vals = sorted(v for v in vals if v is not None)
        return float(np.median(vals)) if vals else None

    per_output = []
    for r in records:
        row = {k: r.get(k) for k in ("engine", "execution", "sha256", "state", "n_protein_copies",
                                     "n_rna_copies", "chain_lengths", "n_contacts", "n_surface",
                                     "no_interface_contact", "native", "native_kind", "error",
                                     "declared_lengths")}
        if r["state"] == "ELIGIBLE":
            mine = {tuple(x): 1 for x in r["contacts"]}
            others = [geometry.weighted_jaccard(mine, occ_c[e]) for e in engines if e != r["engine"]]
            others = [x for x in others if x is not None]
            row["repeat_register_agreement"] = (repeats.get(r["engine"]) or {}).get("register_agreement")
            row["cross_engine_support"] = (sum(sorted(others)) / len(others)) if others else None
            row["n_other_engines_compared"] = len(others)
        per_output.append(row)

    summary = {
        "case_id": c["case_id"], "construct": c["construct"],
        "n_declared_outputs": len(records), "n_eligible_outputs": len(eligible),
        "eligible_engines": engines, "n_eligible_engines": len(engines),
        "ineligible": [[r["engine"], r["execution"], r["state"]] for r in records if r["state"] != "ELIGIBLE"],
        "outputs_with_no_interface_contact": [[r["engine"], r["execution"]] for r in eligible
                                              if r.get("no_interface_contact")],
        "median_pairwise_surface_agreement": med([p["surface_agreement"] for p in pairs]),
        "median_pairwise_register_agreement": med([p["register_agreement"] for p in pairs]),
        "median_pairwise_rna_pose_difference_A": med([p["rna_pose_difference_A"] for p in pairs]),
        "interface_hypotheses": hypotheses,
        "n_hypotheses_at_primary_threshold": len(hypotheses[str(PRIMARY_THRESHOLD)]),
        "primary_threshold": PRIMARY_THRESHOLD, "hypothesis_thresholds": list(HYPOTHESIS_THRESHOLDS),
        "repeat_agreement": repeats,
        "n_contacts_proposed_by_any_engine": len(support),
        "contact_support_histogram": {str(k): sum(1 for v in support.values() if round(v, 6) >= k)
                                      for k in range(1, len(engines) + 1)},
        "SEMANTICS": ("agreement is descriptive evidence about convergence of predicted interface hypotheses; "
                      "it is not a probability of structural correctness"),
        "NO_ACCURACY_IS_COMPUTED": True, "NO_REFERENCE_STRUCTURE_IS_READ": True,
    }
    return {"schema_version": "rnpbench-predict-result-1", "package_version": VERSION,
            "environment": environment_fingerprint(), "summary": summary, "per_output": per_output,
            "engine_pairs": pairs,
            "contact_support": {"%d,%d" % k: round(v, 6) for k, v in sorted(support.items())},
            "contacts_by_output": {"%s|%s" % (r["engine"], r["execution"]): r["contacts"] for r in eligible},
            "wall_s": round(time.time() - t0, 2)}


def write(result, outdir):
    os.makedirs(outdir, exist_ok=True)
    slim = {k: v for k, v in result.items() if k != "contacts_by_output"}
    with open(os.path.join(outdir, "result.json"), "w") as fh:
        json.dump(slim, fh, indent=1, sort_keys=True)
    with open(os.path.join(outdir, "contacts_by_output.json"), "w") as fh:
        json.dump(result["contacts_by_output"], fh, sort_keys=True)
    return os.path.join(outdir, "result.json")
