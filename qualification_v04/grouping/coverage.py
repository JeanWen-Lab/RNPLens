"""Retrospective inspection-set accuracy coverage (Spec B v2 section 5, secondary, reference-based, descriptive;
Amendments 1 (A1.9, A1.12) and 3 (A3.5, A3.6)). Run ONLY after records/grouping/CODE_FREEZE.md is committed.

Reads the frozen labels read-only (pool A: nscale_sample_dockq.tsv; pool B: rank_corpus.tsv) and the per-target
JSON written by qualify.py. Measures whether a small inspection set retains an acceptable proposal. It does not
test whether RNPLens can tell which one it is; it is never a selection or accuracy-improvement result.

Usage: python coverage.py --pool A|B --qual DIR --out FILE
"""
import argparse
import csv
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qualify as Q  # noqa: E402

from rnplens import provenance as pv  # noqa: E402

LABELS = {"A": Q.RNP + "/jpf/nscale/nscale_sample_dockq.tsv", "B": Q.RNP + "/f1/rank_corpus.tsv"}
ACCEPTABLE = 0.23
WITHIN = 0.05
TARGET_COLS = {"target", "entry_id", "pdb_id", "pdb", "target_id", "t", "entry"}          # "entry": Amendment 4
MODEL_COLS = {"model", "model_idx", "model_index", "sample", "sample_idx", "sample_index", "model_id", "rank",
              "pose"}                                                                    # "pose": Amendment 4


class LabelFormatError(RuntimeError):
    pass


def detect(header):
    """A3.6: unique target, model and DockQ columns, decided by name only."""
    low = [h.strip().lower() for h in header]
    tc = [h for h, l in zip(header, low) if l in TARGET_COLS]
    mc = [h for h, l in zip(header, low) if l in MODEL_COLS]
    dc = [h for h, l in zip(header, low) if l == "dockq"]
    if len(tc) != 1 or len(mc) != 1 or len(dc) != 1:
        raise LabelFormatError("columns not uniquely identified: target %s, model %s, dockq %s; header=%s"
                               % (tc, mc, dc, header))
    return tc[0], mc[0], dc[0]


def model_index(v, t):
    s = str(v).strip()
    if s.startswith(t + "_"):
        s = s[len(t) + 1:]
    m = re.fullmatch(r"(?:model_)?(\d+)", s)
    if not m:
        raise LabelFormatError("model value %r (target %s) cannot be mapped to an index" % (v, t))
    return int(m.group(1))


def load_labels(pool, wanted):
    path = LABELS[pool]
    with open(path, newline="") as fh:
        rd = csv.reader(fh, delimiter="\t")
        header = next(rd)
        tc, mc, dc = detect(header)
        it, im, idq = header.index(tc), header.index(mc), header.index(dc)
        ip = [h.strip().lower() for h in header].index("iptm") if "iptm" in [h.strip().lower() for h in header] else None
        out, join = {}, {"rows_checked": 0, "rows_mismatched": 0, "mismatches": []}
        cache = {}
        for row in rd:
            if not row or len(row) <= max(it, im, idq):
                continue
            t = row[it].strip()
            if t not in wanted:
                continue
            i = model_index(row[im], t)
            if ip is not None:                       # Amendment 4: join check against the engine's own iptm
                key = (t, i)
                if key not in cache:
                    cf = os.path.join(Q.POOLS[pool]["pred"].format(T=t), "confidence_%s_model_%d.json" % (t, i))
                    cache[key] = float(json.load(open(cf))["iptm"]) if os.path.isfile(cf) else None
                join["rows_checked"] += 1
                if cache[key] is None or abs(float(row[ip]) - cache[key]) > 1e-6:
                    join["rows_mismatched"] += 1
                    if len(join["mismatches"]) < 10:
                        join["mismatches"].append([t, i])
                    continue
            v = row[idq].strip()
            val = float(v) if v not in ("", "NA", "nan", "None") else None
            prev = out.setdefault(t, {}).get(i, "unset")
            if prev != "unset" and prev != val:
                raise LabelFormatError("conflicting DockQ values for %s model %d: %s vs %s" % (t, i, prev, val))
            out[t][i] = val
    return out, {"path": path, "sha256": pv.sha256_file(path), "columns": [tc, mc, dc], "join_check_iptm": join}


def frac(v):
    v = [x for x in v if x is not None]
    return {"n": len(v), "fraction": float(np.mean(v)) if v else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True, choices=("A", "B"))
    ap.add_argument("--qual", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if not os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "records", "grouping",
                                       "CODE_FREEZE.md")):
        raise SystemExit("refused: records/grouping/CODE_FREEZE.md is not present")
    ts = Q.targets(a.pool)
    recs = {t: json.load(open(os.path.join(a.qual, "targets", "%s.json" % t))) for t in ts
            if os.path.isfile(os.path.join(a.qual, "targets", "%s.json" % t))}
    labels, src = load_labels(a.pool, set(recs))
    per, missing = {}, {"targets_without_labels": [], "eligible_structures_without_label": 0}
    for t, r in sorted(recs.items()):
        L = labels.get(t)
        if not L:
            missing["targets_without_labels"].append(t)
            continue
        elig = [s["id"] for s in r["structures"] if s["state"] == "ELIGIBLE"]     # canonical-key order
        dq = {}
        for sid in elig:
            v = L.get(int(sid.split("_")[1]))
            if v is None:
                missing["eligible_structures_without_label"] += 1
            else:
                dq[sid] = v
        if not dq or max(dq.values()) < ACCEPTABLE:
            per[t] = {"included": False, "max_dockq_eligible": max(dq.values()) if dq else None}
            continue
        topv = max(dq.values())
        top = [s for s in elig if dq.get(s) == topv][0]                            # ties by canonical key
        g05 = [g for g in r["properties"]["0.5"]["groups"] if top in g["members"]][0]
        rep = g05["representative"]
        acc = lambda ids: any(dq.get(x, -1) >= ACCEPTABLE for x in ids)          # noqa: E731
        near = lambda ids: any(dq.get(x, -1) >= topv - WITHIN for x in ids)      # noqa: E731
        row = {"included": True, "top_dockq": topv, "top_id": top,
               "rep_of_top_group": rep, "rep_of_top_group_dockq": dq.get(rep),
               "rep_of_top_group_within_0.05": (dq.get(rep) is not None and dq[rep] >= topv - WITHIN),
               "designated_alone_acceptable": acc([r["inspection"]["3"]["shown"][0]]) if r["designation"]["designated"] else None,
               "settings": {}}
        for key in ("3", "5", "all"):
            I = r["inspection"][key]
            m = len(I["shown"])
            draws = Q.random_draws(elig, m)
            row["settings"][key] = {
                "m": m,
                "grouping_shown_set": {"acceptable": acc(I["shown"]), "within_0.05": near(I["shown"])},
                "random_expected": {"acceptable": float(np.mean([acc(d) for d in draws])) if draws else None,
                                    "within_0.05": float(np.mean([near(d) for d in draws])) if draws else None},
                "top_m_by_confidence": {"acceptable": acc(I["baselines"]["top_m_by_confidence"]["ids"]),
                                        "within_0.05": near(I["baselines"]["top_m_by_confidence"]["ids"])},
                "designated_plus_next_by_confidence": {
                    "acceptable": acc(I["baselines"]["designated_plus_next_by_confidence"]["ids"]),
                    "within_0.05": near(I["baselines"]["designated_plus_next_by_confidence"]["ids"])}}
        per[t] = row
    inc = [x for x in per.values() if x["included"]]
    S = {"label": Q.LABEL + "; secondary, reference-based, retrospective",
         "statement": "Measures whether a small inspection set retains an acceptable proposal. It does not test "
                      "whether RNPLens can tell which one it is, and it is not a selection or accuracy result.",
         "pool": a.pool, "labels": src, "acceptable_threshold": ACCEPTABLE, "within": WITHIN,
         "n_targets_with_grouping": len(recs), "n_targets_with_labels": len(per),
         "n_targets_with_acceptable_candidate": len(inc), "missing": missing,
         "rep_of_top_group_within_0.05": frac([x["rep_of_top_group_within_0.05"] for x in inc]),
         "designated_alone_acceptable": frac([x["designated_alone_acceptable"] for x in inc]),
         "settings": {}}
    for key in ("3", "5", "all"):
        S["settings"][key] = {name: {m: frac([x["settings"][key][name][m] for x in inc])
                                     for m in ("acceptable", "within_0.05")}
                              for name in ("grouping_shown_set", "random_expected", "top_m_by_confidence",
                                           "designated_plus_next_by_confidence")}
        S["settings"][key]["shown_size"] = Q.dist([x["settings"][key]["m"] for x in inc])
    S["per_target"] = per
    S["provenance"] = pv.block("grouping_retrospective_coverage_pool%s" % a.pool, [src["path"]],
                               "Spec B v2 section 5 retrospective coverage (Amendments 1 and 3).",
                               {"acceptable": ACCEPTABLE, "within": WITHIN, "seed": Q.SEED})
    pv.atomic_write_json(a.out, S)
    print("pool %s: %d targets with an acceptable candidate of %d labelled" % (a.pool, len(inc), len(per)))


if __name__ == "__main__":
    main()
