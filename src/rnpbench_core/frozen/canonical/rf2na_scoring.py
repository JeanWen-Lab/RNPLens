#!/usr/bin/env python3
"""RNPBENCH_RF2NA_RELEASED_SCORING_V1 -- score the RF2NA official artifacts through the released
construct-position configuration.

NO SECOND SCORING PATH. Every number comes from pos_adapter.one_row -- the qualified implementation
that owns candidate enumeration, admissibility, the adapter and the ADAPTER_NOT_APPLIED refusal.
This module adds no alignment logic, no metric logic and no fallback.

THE ONE THING THIS MODULE MUST RESTATE, AND HOW IT IS PROVEN RATHER THAN ASSERTED. The released
selection convention lives inline inside release_v3.stage_release() and is not callable from
outside. Refactoring the released implementation to expose it is not permitted, so the convention is
restated here, quoted from its source:

    among admissible candidates whose adapter outcome is SCORED, take the one with the greatest
    adapter total_dockq; report the FIRST interface's DockQ in the metric's own iteration order,
    rounded to three decimals. A candidate with ADAPTER_NOT_APPLIED yields NO VALUE for the row, and
    no tolerance is ever substituted to obtain a number.

A restatement is worth nothing on its own, so this module refuses to score anything until it has
reproduced the released store's own dockq values EXACTLY, row by row, by re-running the qualified
implementation and applying this selection. If a single released row disagrees, the parity gate
fails and no RF2NA value is produced. That is the same hard gate the release itself used against the
official store.

TOLERANCE IS ZERO, NOT ESCALATED. The governing decision on tolerance is explicit no-value rather
than escalation until a comparison succeeds. RF2NA rows are new, so they carry tolerance 0, stated
rather than inherited from a historical row.

THE MODEL INDEX IS EXTENDED, NOT THE SCORER. pos_adapter.model_index() globs the boltz and af3 trees
only. one_row takes the index as an ARGUMENT, so the RF2NA official artifacts are added to the index
that is passed in. Supplying an input is not modifying the implementation.
"""
import collections, glob, hashlib, importlib.util, json, os, random, sys, time

R = "/home/jwen/projects/PCfold3D-RNP"
SD = R + "/outputs/rnp/jpf/scripts_clean"
P = R + "/outputs/rnpbench/pilot"
C = R + "/outputs/rnpbench/rf2na_campaign"
REP = R + "/outputs/reports"
OUT = P + "/score_v3_released_rf2na"
CONFIG_ID = "RNPBENCH_SCORING_V3_CONSTRUCT_POSITION_DOCKQ_2_1_3"
RECON = REP + "/jpf_rnpbench_rf2na_final_artifact_reconciliation.json"
PARITY_N = 60
SENTINELS = ["8X5D", "4RDX", "1CGM", "4C9D", "1LAJ", "6NY2"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def select(rec):
    """The released selection convention, restated. Proven by the parity gate, never trusted alone."""
    if rec.get("status") != "EVALUATED":
        return {"dockq": None, "status": "NO_VALUE", "failure_stage": "candidate_enumeration",
                "failure_reason": rec.get("status"), "failure_detail": rec.get("detail"),
                "no_tolerance_substitution": True, "prediction_exists": True}
    cands = rec["candidates"]
    na = [c for c in cands if c["adapter"].get("outcome") == "ADAPTER_NOT_APPLIED_NO_NUMBERS_REPORTED"]
    scored = [c for c in cands if c["adapter"].get("outcome") == "SCORED"
              and c["adapter"].get("total_dockq") is not None]
    if na:
        return {"dockq": None, "status": "NO_VALUE", "failure_stage": "adapter_application",
                "failure_reason": "ADAPTER_NOT_APPLIED_NO_NUMBERS_REPORTED",
                "no_tolerance_substitution": True, "prediction_exists": True}
    if not scored:
        return {"dockq": None, "status": "NO_VALUE", "failure_stage": "candidate_evaluation",
                "failure_reason": "NO_ADMISSIBLE_CANDIDATE_SCORED",
                "outcomes_seen": sorted({c["adapter"].get("outcome") for c in cands}),
                "no_tolerance_substitution": True, "prediction_exists": True}
    best = max(scored, key=lambda c: c["adapter"]["total_dockq"])
    per = best["adapter"].get("per_interface") or {}
    first = list(per.values())[0].get("DockQ") if per else None
    return {"dockq": (None if first is None else round(float(first), 3)),
            "dockq_unrounded": (None if first is None else float(first)),
            "status": "SCORED", "selected_mapping": best["mapping"],
            "n_admissible_candidates": rec["n_admissible_candidates"],
            "n_interfaces": len(per),
            "adapter_total_dockq": best["adapter"]["total_dockq"],
            "correspondence": best["adapter"].get("correspondence")}


def parity_gate(PA, idx):
    """Reproduce the RELEASED store's own dockq values, row by row, before scoring anything new.

    The sample is deterministic and spans every arm, and the six release sentinels are forced in so
    the gate always exercises the rows the release itself singled out. A single disagreement fails
    the gate: the restated convention is then not the released one, and no RF2NA value is produced.
    """
    rel = {}
    for f in sorted(glob.glob(P + "/score_v3_released/released_*.json")):
        d = json.load(open(f))
        for r in d["rows"]:
            rel[(r["engine"], r["execution"], r["structure_checksum"])] = r
    assert rel, "the released store is empty or missing"
    src = {}
    for f in sorted(glob.glob(P + "/score_v2_2/rescored_*.json")):
        d = json.load(open(f))
        for r in d["rows"]:
            r["_engine"], r["_execution"] = d["engine"], d["execution"]
            src[(d["engine"], d["execution"], r["structure_checksum"])] = r

    keys = sorted(set(rel) & set(src))
    forced = [k for k in keys if rel[k]["target"] in SENTINELS]
    rng = random.Random(20260912)
    rest = [k for k in keys if k not in set(forced)]
    rng.shuffle(rest)
    sample = forced + rest[:max(0, PARITY_N - len(forced))]

    agree, disagree = 0, []
    for k in sample:
        got = select(PA.one_row(src[k], idx))
        want = rel[k]
        same = (got.get("dockq") == want.get("dockq")
                and got.get("status") == want.get("status"))
        if same:
            agree += 1
        else:
            disagree.append({"key": list(k), "target": want["target"],
                             "released": {"dockq": want.get("dockq"), "status": want.get("status")},
                             "recomputed": {"dockq": got.get("dockq"), "status": got.get("status")}})
    return {"n_released_rows_available": len(rel), "n_sampled": len(sample),
            "n_sentinels_forced": len(forced), "n_agree": agree,
            "n_disagree": len(disagree), "disagreements": disagree[:10],
            "PASSED": (len(disagree) == 0 and agree == len(sample) and len(sample) >= 20),
            "rule": ("the restated selection convention must reproduce the released store exactly "
                     "before any RF2NA value is produced")}


def rf2na_rows(recon):
    """One row per designated official RF2NA artifact, built from the reconciliation record."""
    rows, index_add = [], {}
    for t, d in sorted(recon["PER_TARGET"].items()):
        if not d.get("designated_source") or not d.get("digest"):
            continue
        p = os.path.join(R, d["artifact_path"])
        assert sha(p) == d["digest"], "designated artifact %s no longer matches its digest" % t
        index_add[d["digest"]] = p
        rows.append({"target": t, "structure_checksum": d["digest"],
                     "_engine": "RF2NA", "_execution": "exec_A", "tolerance": 0,
                     "_designated_source": d["designated_source"],
                     "_v2_valid": (d.get("v2_receipt") or {}).get("valid")})
    return rows, index_add


def main():
    t0 = time.time()
    recon = json.load(open(RECON))
    assert recon["STATUS"] == "RECONCILED_READY_FOR_SCORING", "reconciliation has not passed"
    frozen_before = sha(REP + "/jpf_rnpbench_rf2na_first_pass_closeout.json")
    PA = load("pos_adapter", SD + "/pos_adapter.py")
    os.makedirs(OUT, exist_ok=True)

    rows, add_idx = rf2na_rows(recon)
    idx = PA.model_index()
    overlap = set(idx) & set(add_idx)
    idx.update(add_idx)
    print("official RF2NA artifacts : %d | added to the index (collisions: %d)"
          % (len(rows), len(overlap)), flush=True)

    print("parity gate: reproducing the released store ...", flush=True)
    pg = parity_gate(PA, idx)
    print("   sampled %d (%d sentinels) | agree %d | disagree %d | PASSED %s"
          % (pg["n_sampled"], pg["n_sentinels_forced"], pg["n_agree"], pg["n_disagree"],
             pg["PASSED"]), flush=True)
    if not pg["PASSED"]:
        json.dump({"contract_id": "RNPBENCH_RF2NA_RELEASED_SCORING_V1",
                   "STATUS": "REFUSED_PARITY_GATE_FAILED", "PARITY_GATE": pg},
                  open(REP + "/jpf_rnpbench_rf2na_released_scoring.json", "w"), indent=1)
        print("REFUSED: the restated selection does not reproduce the released store", flush=True)
        sys.exit(3)

    print("scoring the RF2NA arm ...", flush=True)
    out_rows = []
    for i, row in enumerate(rows):
        rec = PA.one_row(row, idx)
        sel = select(rec)
        out_rows.append({"config_id": CONFIG_ID, "target": row["target"],
                         "engine": "RF2NA", "execution": "exec_A",
                         "structure_checksum": row["structure_checksum"],
                         "tolerance": 0,
                         "tolerance_is_zero_not_escalated": True,
                         "designated_source": row["_designated_source"],
                         "v2_valid": row["_v2_valid"],
                         "model_path": rec.get("model_path"),
                         "reference_sha256": rec.get("reference_sha256"), **sel})
        if (i + 1) % 12 == 0:
            print("   %2d/%d" % (i + 1, len(rows)), flush=True)

    store = {"contract_id": "RNPBENCH_RF2NA_RELEASED_SCORE_STORE_V1", "config_id": CONFIG_ID,
             "engine": "RF2NA", "execution": "exec_A", "n": len(out_rows), "rows": out_rows}
    sp = OUT + "/released_RF2NA_exec_A.json"
    json.dump(store, open(sp, "w"), indent=1)

    scored = [r for r in out_rows if r["status"] == "SCORED" and r["dockq"] is not None]
    novalue = [r for r in out_rows if r["status"] != "SCORED"]
    vals = sorted(r["dockq"] for r in scored)
    excl = set(recon["PREDECLARED_PROVENANCE_SENSITIVITY_EXCLUSION_SET"])
    prim = [r for r in scored]
    sens = [r for r in scored if r["target"] not in excl]

    def stats(rs):
        v = sorted(x["dockq"] for x in rs)
        if not v:
            return {"n": 0}
        n = len(v)
        med = (v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0)
        return {"n": n, "median": round(med, 4), "mean": round(sum(v) / n, 4),
                "min": v[0], "max": v[-1],
                "acceptable_or_better_dockq_ge_0_23": sum(1 for x in v if x >= 0.23),
                "medium_or_better_dockq_ge_0_49": sum(1 for x in v if x >= 0.49),
                "high_dockq_ge_0_80": sum(1 for x in v if x >= 0.80)}

    rep = {
        "contract_id": "RNPBENCH_RF2NA_RELEASED_SCORING_V1",
        "STATUS": "SCORED",
        "config_id": CONFIG_ID,
        "configuration_name_as_ruled": ("the official RNPBench scoring configuration using DockQ "
                                        "2.1.3 with construct-position correspondence"),
        "NO_SECOND_SCORING_PATH": ("every value was produced by pos_adapter.one_row, the qualified "
                                   "implementation; this module adds no metric or alignment logic"),
        "PARITY_GATE": pg,
        "SELECTION_CONVENTION_RESTATED_AND_PROVEN": (
            "greatest adapter total_dockq among SCORED admissible candidates; report the first "
            "interface's DockQ in the metric's own iteration order, rounded to three decimals. "
            "Proven by reproducing the released store exactly on the parity sample."),
        "LAYER_1_campaign_execution": {
            "n_attempted": recon["cohort_size"],
            "frozen_first_pass_outcomes": "see RNPBENCH_FIRST_PASS_CLOSEOUT_V1; not restated here"},
        "LAYER_2_official_valid_outputs": {
            "n_designated_official_artifacts": len(rows),
            "by_source": recon["counts_by_source"]},
        "LAYER_3_evaluator_evaluable_and_scored": {
            "n_scored": len(scored), "n_no_value": len(novalue),
            "no_value_reasons": collections.Counter(
                r.get("failure_reason") for r in novalue) if novalue else {},
            "no_value_targets": [r["target"] for r in novalue]},
        "LAYER_4_primary_accuracy_and_sensitivity": {
            "PRIMARY_full_contract_defined_population": stats(prim),
            "SENSITIVITY_excluding_the_four_administrative_recovery_targets": stats(sens),
            "excluded_in_the_sensitivity": sorted(excl),
            "THE_SENSITIVITY_DOES_NOT_CHOOSE_THE_PRIMARY": (
                "the full contract-defined population is primary; the four-target exclusion is a "
                "provenance robustness analysis, predeclared before any recovery accuracy existed")},
        "NO_ACCURACY_FOR_TARGETS_WITHOUT_A_VALID_EVALUABLE_ARTIFACT": (
            recon["targets_with_no_designated_artifact"] or "none: all 72 are designated"),
        "store": sp.replace(R + "/", ""),
        "store_sha256": sha(sp),
        "wall_seconds": round(time.time() - t0, 1),
        "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    rep["frozen_first_pass_unchanged"] = (
        sha(REP + "/jpf_rnpbench_rf2na_first_pass_closeout.json") == frozen_before)
    assert rep["frozen_first_pass_unchanged"], "the frozen first pass changed during scoring"

    p = REP + "/jpf_rnpbench_rf2na_released_scoring.json"
    if os.path.exists(p):
        os.chmod(p, 0o644)
    json.dump(rep, open(p, "w"), indent=1)
    os.chmod(p, 0o444)
    print("scored %d | no value %d" % (len(scored), len(novalue)), flush=True)
    print("PRIMARY    : %s" % json.dumps(rep["LAYER_4_primary_accuracy_and_sensitivity"]
                                         ["PRIMARY_full_contract_defined_population"]), flush=True)
    print("SENSITIVITY: %s" % json.dumps(rep["LAYER_4_primary_accuracy_and_sensitivity"]
                                         ["SENSITIVITY_excluding_the_four_administrative_recovery_targets"]),
          flush=True)
    print("frozen first pass unchanged: %s" % rep["frozen_first_pass_unchanged"], flush=True)


if __name__ == "__main__":
    main()
