"""Descriptive qualification of binding-hypothesis grouping on development pools A and B (Spec B v2 section 5,
Amendments 1-3). Reference-free only: opens no DockQ or other accuracy record.

Usage: python qualify.py --pool A|B --out DIR [--workers 32] [--targets T1,T2]
Writes DIR/targets/<T>.json per target, DIR/summary_pool<P>.json, DIR/DONE_pool<P> at the end.
Label: exploratory, development-pool, descriptive.
"""
import argparse
import collections
import copy
import hashlib
import json
import math
import multiprocessing as mp
import os
import re
import sys
import time
import traceback
from fractions import Fraction

import numpy as np

from rnplens import grouping as G
from rnplens import provenance as pv
from rnpbench_report import contract as report_contract

SEED = 20261016
LABEL = "exploratory, development-pool, descriptive"
RNP = "/home/jwen/projects/PCfold3D-RNP/outputs/rnp"
RANK = "/home/jwen/projects/RNPBench/RNPLens-Rank/derived"
EXCLUDED = set("3WZI 4DWA 4KR6 4OHZ 4PMI 4RCJ 4RDX 5B63 5FN1 5HSW 5MSF 5U30 5X2G 6DCB 6E4P 6LT7 6M7K 6NY2 6O6V 6O7B "
               "6P7P 6SCE 6W11 6XMF 7QQK 7S7C 7UZW 7VYX 7XG1 7XS4 8PSQ 8UMF 8WO8 9JXX 9RVP 9U49 9YLU".split())
POOLS = {
    "A": {"targets": os.path.join(RANK, "poolA_targets.txt"), "drop": {"5MSF"}, "n_models": 50, "expect": 64,
          "pred": RNP + "/jpf/nscale/boltz_out/boltz_results_{T}/predictions/{T}",
          "inputs": [RNP + "/jpf/nscale/inputs/{T}.yaml"]},
    "B": {"targets": os.path.join(RANK, "poolB_targets.txt"),
          "drop": {"4KR6", "4PMI", "4RDX", "5FN1", "5HSW", "6DCB", "6NY2", "6XMF"}, "n_models": 5, "expect": 216,
          "pred": RNP + "/fullrun/boltz_out/boltz_results_{T}/predictions/{T}",
          "inputs": [RNP + "/fullrun/inputs_gpu0/{T}.yaml", RNP + "/fullrun/inputs_gpu1/{T}.yaml"]},
}
KS = (3, 5)


def targets(pool):
    P = POOLS[pool]
    ts = [l.strip() for l in open(P["targets"]) if l.strip()]
    ts = [t for t in ts if t not in P["drop"]]
    bad = sorted(set(ts) & EXCLUDED)
    if bad:
        raise SystemExit("refused: excluded targets in pool %s list: %s" % (pool, bad))
    if len(ts) != P["expect"]:
        raise SystemExit("pool %s: %d targets, expected %d" % (pool, len(ts), P["expect"]))
    return ts


def construct(pool, t):
    fs = [f.format(T=t) for f in POOLS[pool]["inputs"] if os.path.isfile(f.format(T=t))]
    if not fs:
        raise RuntimeError("no input YAML for %s" % t)
    ents, cur = [], None
    for line in open(fs[0]):
        m = re.match(r"\s*-\s*(protein|rna|dna|ligand):", line)
        if m:
            cur = {"t": m.group(1)}
            ents.append(cur)
            continue
        m = re.match(r"\s*(id|sequence):\s*(.*)", line)
        if m and cur is not None:
            cur[m.group(1)] = m.group(2).strip()
    p = [e["sequence"] for e in ents if e["t"] == "protein"]
    r = [e["sequence"] for e in ents if e["t"] == "rna"]
    if len(p) != 1 or len(r) != 1 or any(e["t"] not in ("protein", "rna") for e in ents):
        raise RuntimeError("%s: not one protein and one RNA entity" % t)
    return {"protein_length": len(p[0]), "rna_length": len(r[0]), "protein_sequence": p[0], "rna_sequence": r[0]}, fs[0]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def canon(d):
    d = copy.deepcopy(d)
    d.pop("provenance", None)
    return json.dumps(d, sort_keys=True)


# --------------------------------------------------------------------------------------------- shown sets
def r_pair(C, a, b):
    """Report's R for ids a, b (None for empty-empty)."""
    return G.exact_jaccard(C[a], C[b])


def set_metrics(ids, C, groups05):
    """Diversity, redundancy, coverage for a set of structure ids (A1.5, A1.9)."""
    ds, red, undef = [], 0, 0
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            r = r_pair(C, a, b)
            if r is None:
                undef += 1
                continue
            ds.append(1 - r)
            red += r >= Fraction(1, 2)
    cov = sum(1 for g in groups05 if set(g) & set(ids)) / len(groups05) if groups05 else None
    return {"size": len(ids), "diversity": float(sum(ds, Fraction(0)) / len(ds)) if ds else None,
            "redundancy": red, "coverage": cov, "n_pairs_undefined": undef}


def shown_set(T05, designated, k):
    out = [designated] if designated else []
    for g in T05["groups"]:
        if k is not None and len(out) >= k:
            break
        r = g["representative"]["id"]
        if r not in out:
            out.append(r)
    return out


def random_draws(elig_sorted, m, n_draws=200):
    rng = np.random.default_rng(SEED)
    if m > len(elig_sorted) or m == 0:
        return []
    return [[elig_sorted[i] for i in sorted(rng.choice(len(elig_sorted), size=m, replace=False))] for _ in range(n_draws)]


def by_confidence(elig_sorted, conf):
    """Eligible ids ordered by engine confidence_score, descending; ties by canonical key (the sorted order)."""
    pos = {x: i for i, x in enumerate(elig_sorted)}
    return sorted(elig_sorted, key=lambda x: (-conf[x], pos[x]))


def inspection(doc, C, conf, designated):
    T05 = doc["thresholds"]["0.5"]
    g05 = [g["members"] for g in T05["groups"]]
    elig_sorted = [s["id"] for s in doc["structures"] if s["state"] == "ELIGIBLE"]   # canonical-key order
    order = by_confidence(elig_sorted, conf)
    out = {}
    for k in KS + (None,):
        ids = shown_set(T05, designated, k)
        m = len(ids)
        draws = random_draws(elig_sorted, m)
        rm = [set_metrics(d, C, g05) for d in draws]

        def mean(key):
            v = [x[key] for x in rm if x[key] is not None]
            return float(np.mean(v)) if v else None
        top = order[:m]
        pick = ([designated] + [x for x in order if x != designated][:m - 1]) if designated else order[:m]
        out["all" if k is None else str(k)] = {
            "k": k, "shown": ids, "metrics": set_metrics(ids, C, g05),
            "baselines": {"random_expected": {"n_draws": len(draws), "diversity": mean("diversity"),
                                              "redundancy": mean("redundancy"), "coverage": mean("coverage")},
                          "top_m_by_confidence": dict(set_metrics(top, C, g05), ids=top),
                          "designated_plus_next_by_confidence": dict(set_metrics(pick, C, g05), ids=pick)},
            "top_equals_designated_plus_next": top == pick}
    return out


# --------------------------------------------------------------------------------------------- per target
def labels_of(doc, t):
    lab = {}
    for g in doc["thresholds"][t]["groups"]:
        for m in g["members"]:
            lab[m] = g["group"]
    return lab


def one_target(args):
    pool, t, outdir = args
    t0 = time.time()
    try:
        P = POOLS[pool]
        cons, yml = construct(pool, t)
        d = P["pred"].format(T=t)
        outs, conf_all = [], {}
        for i in range(P["n_models"]):
            f = os.path.join(d, "%s_model_%d.pdb" % (t, i))
            cf = os.path.join(d, "confidence_%s_model_%d.json" % (t, i))
            if not os.path.isfile(f):
                raise RuntimeError("missing model file %s" % f)
            outs.append({"engine": "BOLTZ2", "execution": "model_%d" % i, "structure_path": f, "sha256": sha(f),
                         "confidence_dir": d})
            conf_all["model_%d" % i] = float(json.load(open(cf))["confidence_score"]) if os.path.isfile(cf) else None
        vc = report_contract.validate({"schema_version": "rnpbench-predict-contract-1", "case_id": t,
                                       "construct": dict(cons), "outputs": outs})
        recs = G.records_from_contract(vc, designated={("BOLTZ2", "model_0"): True})
        doc, dend, pw = G.compute(recs, vc["construct"])
        ref = [canon(x) for x in (doc, dend, pw)]
        # order invariance: 5 permutations
        rng = np.random.default_rng(SEED)
        diffs = 0
        for _ in range(5):
            perm = [recs[i] for i in rng.permutation(len(recs))]
            if [canon(x) for x in G.compute(perm, vc["construct"])] != ref:
                diffs += 1
        elig = [r for r in recs if r["state"] == "ELIGIBLE"]
        es = sorted(elig, key=G.canonical_key)
        C = {r["id"]: frozenset(tuple(x) for x in r["contacts"]) for r in elig}
        conf = {r["id"]: conf_all[r["id"]] for r in elig}
        if any(v is None for v in conf.values()):
            raise RuntimeError("confidence_score missing for an eligible model")
        designated = "model_0" if "model_0" in C else None
        # subsampling ARI
        n = len(es)
        nsub = int(Fraction(4, 5) * n)
        rng = np.random.default_rng(SEED)
        ari = {th: [] for th in G.THRESHOLDS}
        full = {th: labels_of(doc, th) for th in G.THRESHOLDS}
        for _ in range(20):
            idx = sorted(rng.choice(n, size=nsub, replace=False))
            sub = [es[i] for i in idx]
            sd, _, _ = G.compute(sub, pose=False)
            for th in G.THRESHOLDS:
                ls = labels_of(sd, th)
                ids = [s["id"] for s in sub]
                ari[th].append(G.adjusted_rand_index([full[th][x] for x in ids], [ls[x] for x in ids]))
        # properties
        props = {}
        for th in G.THRESHOLDS:
            T = doc["thresholds"][th]
            sizes = [g["size"] for g in T["groups"]]
            to_rep = [x for g in T["groups"] if not g["no_interface"] for x in g["R_members_to_representative"]]
            props[th] = {"n_groups": T["n_groups"], "n_surface_groups": T["n_surface_groups"],
                         "sizes_display_order": sizes,
                         "singleton_fraction_of_groups": (sum(s == 1 for s in sizes) / len(sizes)) if sizes else None,
                         "singleton_fraction_of_structures": (sum(s == 1 for s in sizes) / n) if n else None,
                         "reduction_factor": (n / len(sizes)) if sizes else None,
                         "mean_R_members_to_representative": float(np.mean(to_rep)) if to_rep else None,
                         "n_members_compared_to_representative": len(to_rep),
                         "has_no_interface_group": any(g["no_interface"] for g in T["groups"]),
                         "groups": [{"group": g["group"], "members": g["members"], "representative": g["representative"]["id"],
                                     "no_interface": g["no_interface"], "surface_group": g["surface_group"],
                                     "P_spread_A": g["rna_pose_difference_spread_A"]} for g in T["groups"]]}
        order = [conf_all["model_%d" % i] for i in range(P["n_models"])]
        rec = {"target": t, "pool": pool, "label": LABEL, "construct_yaml": yml,
               "construct_lengths": [cons["protein_length"], cons["rna_length"]],
               "n_models": P["n_models"], "n_eligible": n, "n_interface": doc["n_interface"],
               "n_no_interface": doc["n_no_interface"],
               "ineligible": [[r["id"], r["state"]] for r in doc["ineligible"]],
               "designation": {"rule": "engine model_0 (Boltz-2 writes models in descending confidence_score)",
                               "designated": designated,
                               "model_0_has_max_confidence": conf_all["model_0"] is not None and all(
                                   v is None or v <= conf_all["model_0"] for v in order),
                               "order_non_increasing": all(order[i] is not None and order[i + 1] is not None and
                                                           order[i] >= order[i + 1] for i in range(len(order) - 1))},
               "confidence_score": conf_all,
               "structures": [{"id": s["id"], "sha256": s["sha256"], "state": s["state"], "n_contacts": s["n_contacts"],
                               "contacts": s["contacts"]} for s in doc["structures"]],
               "properties": props,
               "order_invariance": {"n_permutations": 5, "n_differing": diffs},
               "subsampling_ari": {"subset_size": nsub, "n_subsets": 20, "values": ari,
                                   "mean": {th: float(np.mean(v)) for th, v in ari.items()}},
               "inspection": inspection(doc, C, conf, designated) if n else None,
               "pairwise_P_available": sum(p["rna_pose_difference_P_A"] is not None for p in pw["pairs"]),
               "n_pairs": len(pw["pairs"]), "wall_s": round(time.time() - t0, 1)}
        pv.atomic_write_json(os.path.join(outdir, "targets", "%s.json" % t), rec)
        return t, "OK", rec["wall_s"]
    except Exception as ex:
        pv.atomic_write_json(os.path.join(outdir, "targets", "%s.error.json" % t),
                             {"target": t, "error": "%s: %s" % (type(ex).__name__, ex), "tb": traceback.format_exc()})
        return t, "ERROR %s: %s" % (type(ex).__name__, ex), round(time.time() - t0, 1)


# --------------------------------------------------------------------------------------------- summary
def dist(v):
    v = [x for x in v if x is not None]
    if not v:
        return {"n": 0}
    return {"n": len(v), "median": float(np.median(v)), "mean": float(np.mean(v)), "min": float(min(v)),
            "max": float(max(v))}


def summarise(pool, outdir, ts):
    recs = []
    for t in ts:
        p = os.path.join(outdir, "targets", "%s.json" % t)
        if os.path.isfile(p):
            recs.append(json.load(open(p)))
    S = {"label": LABEL, "pool": pool, "n_targets_listed": len(ts), "n_targets_completed": len(recs),
         "failed": sorted(set(ts) - {r["target"] for r in recs}),
         "n_structures": sum(r["n_models"] for r in recs), "n_eligible": sum(r["n_eligible"] for r in recs),
         "n_no_interface_structures": sum(r["n_no_interface"] for r in recs),
         "ineligible_states": dict(collections.Counter(s for r in recs for _, s in r["ineligible"])),
         "designation": {"rule": "engine model_0 (Boltz-2 ranks by confidence_score)",
                         "targets_model_0_max_confidence": sum(r["designation"]["model_0_has_max_confidence"] for r in recs),
                         "targets_order_non_increasing": sum(r["designation"]["order_non_increasing"] for r in recs),
                         "targets_model_0_ineligible": sum(r["designation"]["designated"] is None for r in recs)},
         "order_invariance": {"targets_checked": len(recs), "permutations_per_target": 5,
                              "targets_with_any_difference": sum(r["order_invariance"]["n_differing"] > 0 for r in recs)},
         "properties": {}, "subsampling_ari": {}, "inspection": {}}
    for th in G.THRESHOLDS:
        P = [r["properties"][th] for r in recs]
        hist = collections.Counter(s for p in P for s in p["sizes_display_order"])
        S["properties"][th] = {
            "groups_per_target": dist([p["n_groups"] for p in P]),
            "surface_groups_per_target": dist([p["n_surface_groups"] for p in P]),
            "singleton_fraction_of_groups": dist([p["singleton_fraction_of_groups"] for p in P]),
            "singleton_fraction_of_structures": dist([p["singleton_fraction_of_structures"] for p in P]),
            "reduction_factor": dist([p["reduction_factor"] for p in P]),
            "mean_R_members_to_representative": dist([p["mean_R_members_to_representative"] for p in P]),
            "group_size_histogram": {str(k): hist[k] for k in sorted(hist)},
            "targets_with_one_group": sum(p["n_groups"] == 1 for p in P),
            "targets_with_no_interface_group": sum(p["has_no_interface_group"] for p in P)}
        S["subsampling_ari"][th] = {"per_target_mean": dist([r["subsampling_ari"]["mean"][th] for r in recs]),
                                    "targets_all_20_equal_1": sum(all(v == 1.0 for v in r["subsampling_ari"]["values"][th])
                                                                  for r in recs)}
    for key in ("3", "5", "all"):
        I = [r["inspection"][key] for r in recs if r["inspection"]]
        row = {"shown_size": dist([i["metrics"]["size"] for i in I]),
               "targets_shown_smaller_than_k": (sum(i["metrics"]["size"] < int(key) for i in I) if key != "all" else None),
               "targets_top_equals_designated_plus_next": sum(i["top_equals_designated_plus_next"] for i in I)}
        for name, get in (("grouping_shown_set", lambda i: i["metrics"]),
                          ("random_expected", lambda i: i["baselines"]["random_expected"]),
                          ("top_m_by_confidence", lambda i: i["baselines"]["top_m_by_confidence"]),
                          ("designated_plus_next_by_confidence", lambda i: i["baselines"]["designated_plus_next_by_confidence"])):
            row[name] = {m: dist([get(i)[m] for i in I]) for m in ("diversity", "redundancy", "coverage")}
        S["inspection"][key] = row
    S["wall_s_per_target"] = dist([r["wall_s"] for r in recs])
    S["provenance"] = pv.block("grouping_qualification_pool%s" % pool,
                               [{"path": os.path.join(outdir, "targets", "%s.json" % r["target"]),
                                 "sha256": pv.sha256_file(os.path.join(outdir, "targets", "%s.json" % r["target"]))}
                                for r in recs], "Spec B v2 section 5 reference-free properties (Amendments 1-3).",
                               {"seed": SEED, "pool": pool, "ks": list(KS)})
    pv.atomic_write_json(os.path.join(outdir, "summary_pool%s.json" % pool), S)
    return S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True, choices=("A", "B"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--targets", default=None)
    a = ap.parse_args()
    if a.workers > 32:
        raise SystemExit("at most 32 workers")
    ts = targets(a.pool)
    run = [t for t in a.targets.split(",")] if a.targets else ts
    if set(run) - set(ts):
        raise SystemExit("not in pool %s: %s" % (a.pool, sorted(set(run) - set(ts))))
    os.makedirs(os.path.join(a.out, "targets"), exist_ok=True)
    jobs = [(a.pool, t, a.out) for t in run]
    with mp.get_context("fork").Pool(min(a.workers, len(jobs))) as pool:
        for t, st, w in pool.imap_unordered(one_target, jobs):
            print("%s %s %.1fs" % (t, st, w), flush=True)
    if not a.targets:
        S = summarise(a.pool, a.out, ts)
        print("summary: %d/%d targets" % (S["n_targets_completed"], S["n_targets_listed"]), flush=True)
    open(os.path.join(a.out, "DONE_pool%s%s" % (a.pool, "_partial" if a.targets else "")), "w").write(time.ctime() + "\n")


if __name__ == "__main__":
    main()
