#!/usr/bin/env python
"""RBP-B2a — family-conformer oracle matrix (arms S7, F1-F7).

Pre-registration: outputs/reports/rnp_b2_prereg.md, frozen before any arm was scored.

Reuses the B1c all-atom reconstruction wholesale (f1_b1c_allatom), so every arm here is
representation-matched to B1c: template backbone transferred, bases rebuilt to the QUERY's sequence, protein
copied VERBATIM ALL-ATOM from the query's own Boltz pose into every arm. Only the RNA differs between arms.

ARM SEMANTICS (oracles are labelled; see prereg):
  S7  Boltz top-1 by ipTM                                          deployable reference
  F1  bank MEDOID conformer      at S7 placement                   deployable
  F2  BEST bank conformer by DockQ, at S7 placement                ORACLE (bank ceiling)
  F3  bank conformer picked NATIVE-FREE (bp signature vs S7 RNA)   deployable
  F4  NATIVE query RNA internal  at S7 placement                   ORACLE (internal ceiling)
  F5  S7 internal geometry       at NATIVE placement               ORACLE (placement ceiling)
  F6  NATIVE internal            at NATIVE placement               ORACLE (full ceiling)
  F7  best of the 5 Boltz models by DockQ                          ORACLE (pool headroom)

TRAPS ALREADY PAID FOR -- do not reintroduce (each cost a debugging cycle in B1b/B1c):
  * feat.load keeps waters/ions; base1() filters them. Counting HOH as nucleotides wrecked the
    query<->template index map and produced 804 hard clashes.
  * The rebuilt chain OMITS unaligned query positions, so its k-th C4' atom is NOT the k-th native
    nucleotide. Every RMSD here keys C4' by QUERY RESIDUE INDEX and subsets BOTH sides to shared indices.
  * prot_frames carries ONE-LETTER aa codes; b1c.protein_allatom emits real 3-letter names from the pose.
  * g0.top1_pose selects highest ipTM, NOT model_0.
  * DockQ by absolute path only; NaN counted, never averaged.
"""
from __future__ import annotations
import os, sys, csv, json, glob, warnings, importlib.util, collections, time

warnings.filterwarnings("ignore")
ROOT = "/home/jwen/projects/PCfold3D-RNP"
os.chdir(ROOT)
_ARGV = list(sys.argv)
sys.argv = ["x"]


def _imp(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


feat = _imp("feat", "scripts/rnp/f1_featurize_mp.py")
g0 = _imp("g0", "scripts/rnp/f1_g0_oracle.py")
gate = _imp("gate", "scripts/rnp/f1_b1b_gate.py")
b1c = _imp("b1c", "scripts/rnp/f1_b1c_allatom.py")
sys.argv = _ARGV

import numpy as np

NATDIR = "outputs/rnp/fullrun/natives"
WORK = "outputs/rnp/f1/b2a_work"
FOLDS = "outputs/rnp/f1/rbp_b1b_fold_membership.tsv"
AUDIT = "outputs/rnp/f1/rbp_b1b_pose_coverage_audit.tsv"
ACC, MED, HIGH = 0.23, 0.49, 0.80


def std_residues(path):
    """(standard-RNA residues, protein frames) for the contacting pair; waters/ions excluded."""
    try:
        st = feat.load(path)
        pid, rid = feat.contacting_pair(st)
    except Exception:
        return None, None
    if pid is None or rid is None:
        return None, None
    res = [r for r in st[0][rid] if b1c.base1(r) is not None]
    return res, feat.prot_frames(st[0][pid])


def c4_of(res):
    a = [x for x in res if x.get_name() == "C4'"]
    return np.asarray(a[0].get_coord(), float) if a else None


def align_pairs(qres, tres):
    """Injective query->template residue correspondence (b1c semantics)."""
    import difflib
    qb = [b1c.base1(r) for r in qres]
    tb = [b1c.base1(r) for r in tres]
    sm = difflib.SequenceMatcher(None, "".join(qb), "".join(tb))
    pair = [None] * len(qb)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            pair[blk.a + k] = blk.b + k
    used = set(j for j in pair if j is not None)
    for i in range(len(qb)):
        if pair[i] is not None:
            continue
        prev = next((pair[k] for k in range(i - 1, -1, -1) if pair[k] is not None), None)
        nxt = next((pair[k] for k in range(i + 1, len(qb)) if pair[k] is not None), None)
        lo = 0 if prev is None else prev + 1
        hi = len(tb) if nxt is None else nxt
        cand = [j for j in range(lo, hi) if j not in used]
        if cand:
            pair[i] = cand[0]
            used.add(cand[0])
    return pair


def bp_sig(xyz):
    n = len(xyz)
    if n < 4:
        return set()
    X = np.asarray(xyz, float)
    d = np.linalg.norm(X[:, None, :] - X[None, :, :], axis=-1)
    return {(i, j) for i in range(n) for j in range(i + 3, n) if d[i, j] < 12.0}


def stack_sig(xyz):
    """Consecutive-nucleotide stacking proxy: adjacent C4' separation in the 4-7 A band."""
    X = np.asarray(xyz, float)
    return {i for i in range(len(X) - 1) if 4.0 <= float(np.linalg.norm(X[i + 1] - X[i])) <= 7.0}


def metrics_vs_native(pred_by_idx, nat_c4, qpf, npf, iface_idx):
    """All representation-independent geometry, keyed by QUERY residue index on BOTH sides."""
    out = {k: float("nan") for k in ("rna_internal_rmsd", "rna_rmsd_after_protein_align",
                                     "iface_nt_rmsd", "bp_recovery", "stack_recovery", "n_c4")}
    idx = sorted(k for k in pred_by_idx if 1 <= k <= len(nat_c4) and nat_c4[k - 1] is not None)
    if len(idx) < 3:
        return out
    P = np.array([pred_by_idx[k] for k in idx])
    N = np.array([nat_c4[k - 1] for k in idx])
    out["n_c4"] = len(idx)
    m = min(len(qpf), len(npf))
    if m >= 3:
        R, t = feat.kabsch(np.array([np.asarray(x[2]) for x in qpf[:m]]),
                           np.array([np.asarray(x[2]) for x in npf[:m]]))
        out["rna_rmsd_after_protein_align"] = float(np.sqrt(((P @ R.T + t - N) ** 2).sum(1).mean()))
    R2, t2 = feat.kabsch(P, N)
    out["rna_internal_rmsd"] = float(np.sqrt(((P @ R2.T + t2 - N) ** 2).sum(1).mean()))
    sel = [p for p, k in enumerate(idx) if k in iface_idx]
    if len(sel) >= 3:
        Pi, Ni = P[sel], N[sel]
        Ri, ti = feat.kabsch(Pi, Ni)
        out["iface_nt_rmsd"] = float(np.sqrt(((Pi @ Ri.T + ti - Ni) ** 2).sum(1).mean()))
    bp_p, bp_n = bp_sig(P), bp_sig(N)
    out["bp_recovery"] = float(len(bp_p & bp_n) / len(bp_n)) if bp_n else float("nan")
    st_p, st_n = stack_sig(P), stack_sig(N)
    out["stack_recovery"] = float(len(st_p & st_n) / len(st_n)) if st_n else float("nan")
    return out


def main():
    shard = int(_ARGV[1]) if len(_ARGV) > 1 else 0
    nsh = int(_ARGV[2]) if len(_ARGV) > 2 else 1
    os.makedirs(WORK, exist_ok=True)
    lib = {k: v for k, v in json.load(open(b1c.LIB))["library"].items()}
    folds = list(csv.DictReader(open(FOLDS), delimiter="\t"))
    audit = {r["entry_id"]: r for r in csv.DictReader(open(AUDIT), delimiter="\t")}
    usable = {e for e, r in audit.items()
              if r["has_pose"].strip().lower() in ("true", "1")
              and r["native_present"].strip().lower() in ("true", "1")}
    queries = [r for r in folds if r["role"] == "test"]
    train_by_fold = collections.defaultdict(list)
    for r in folds:
        if r["role"] == "train":
            train_by_fold[r["fold"]].append(r)
    mine = [q for i, q in enumerate(queries) if i % nsh == shard]
    print(f"shard {shard}/{nsh}: {len(mine)} of {len(queries)}", flush=True)

    rows = []
    t0 = time.time()
    for n, q in enumerate(mine):
        e, fold = q["entry_id"], q["fold"]
        rec = {"entry_id": e, "fold": int(fold), "protein_cluster": q["protein_cluster"],
               "rna_cluster": q["rna_cluster"], "class": audit[e]["class"],
               "rna_length": int(audit[e]["rna_length"])}
        natp = f"{NATDIR}/{e}.cif"
        qpose = g0.top1_pose(e)
        if qpose is None or not os.path.exists(natp):
            rec["err"] = "no_pose_or_native"
            rows.append(rec)
            continue
        nres, npf = std_residues(natp)
        qres, qpf = std_residues(qpose)
        prot, _, _ = b1c.protein_allatom(qpose)
        if not nres or not qres or prot is None:
            rec["err"] = "parse"
            rows.append(rec)
            continue
        nat_c4 = [c4_of(r) for r in nres]
        qb = [b1c.base1(r) for r in nres]
        rec["n_query_nt"] = len(nres)

        # interface nucleotides: within 8 A of the native protein
        npx = np.array([np.asarray(x[2]) for x in npf])
        iface = set()
        for i, c in enumerate(nat_c4):
            if c is not None and np.linalg.norm(npx - c, axis=1).min() < 8.0:
                iface.add(i + 1)
        rec["n_iface_nt"] = len(iface)

        # ---------- the bank ----------------------------------------------------
        bank = [t for t in train_by_fold[fold]
                if t["rna_cluster"] == q["rna_cluster"]
                and t["protein_cluster"] != q["protein_cluster"]
                and t["entry_id"] in usable]
        for t in bank:
            assert t["role"] == "train", f"LEAK: {t['entry_id']} not in train"
            assert t["protein_cluster"] != q["protein_cluster"], "LEAK: same protein cluster"
        bank = sorted({t["entry_id"] for t in bank})
        rec["bank_size"] = len(bank)
        if not bank:
            rec["err"] = "empty_bank"
            rows.append(rec)
            continue

        def emit(atoms, tag):
            """Write arm, score DockQ + all geometry, clean up. Returns dict of metrics."""
            if not atoms:
                return None
            p = f"{WORK}/{e}_{tag}.pdb"
            b1c.write_pdb(p, prot, atoms)
            mm = b1c.dockq_all(p, natp)
            aud = b1c.stereo_audit(atoms)
            pred = {a[1]: a[4] for a in atoms if a[2] == "C4'"}
            gm = metrics_vs_native(pred, nat_c4, qpf, npf, iface)
            os.remove(p)
            d = {}
            d.update({f"{tag}_{k}": v for k, v in mm.items()})
            d.update({f"{tag}_{k}": v for k, v in gm.items()})
            d[f"{tag}_clashes"] = aud["hard_clashes_lt_2A"]
            d[f"{tag}_bad_bonds"] = aud["bonds_out_of_range"]
            return d

        # ---------- reference frames -------------------------------------------
        # S7's own RNA, and the native RNA expressed in the predicted-protein frame (for oracle placements)
        s7_c4 = {}
        pair_q_s7 = align_pairs(nres, qres) if qres else []
        for i, j in enumerate(pair_q_s7):
            if j is not None:
                c = c4_of(qres[j])
                if c is not None:
                    s7_c4[i + 1] = c
        m2 = min(len(qpf), len(npf))
        Rp, tp = feat.kabsch(np.array([np.asarray(x[2]) for x in npf[:m2]]),
                             np.array([np.asarray(x[2]) for x in qpf[:m2]]))
        nat_in_pred = {i + 1: (c @ Rp.T + tp) for i, c in enumerate(nat_c4) if c is not None}

        def build_conformer(tid, ref_by_idx):
            """Rebuild bank conformer `tid` to the query sequence, rigid-fitted onto ref_by_idx."""
            tres, _ = std_residues(f"{NATDIR}/{tid}.cif")
            if not tres:
                return None
            pair = align_pairs(nres, tres)
            tsel = [tres[j] if j is not None else None for j in pair]
            src, dst = [], []
            for i, tr_ in enumerate(tsel):
                if tr_ is None or (i + 1) not in ref_by_idx:
                    continue
                c = c4_of(tr_)
                if c is not None:
                    src.append(c)
                    dst.append(ref_by_idx[i + 1])
            if len(src) < 3:
                return None
            tf = feat.kabsch(np.array(src), np.array(dst))
            atoms, _ = b1c.rebuild_rna(tsel, qb, lib, transform=tf)
            return atoms or None

        # ---------- S7 ----------------------------------------------------------
        mm = b1c.dockq_all(qpose, natp)
        rec.update({f"S7_{k}": v for k, v in mm.items()})
        rec.update({f"S7_{k}": v for k, v in
                    metrics_vs_native(s7_c4, nat_c4, qpf, npf, iface).items()})

        # ---------- F1 medoid (native-free) ------------------------------------
        # pairwise internal C4' RMSD between bank conformers, in query-index space
        prof = {}
        for tid in bank:
            tres, _ = std_residues(f"{NATDIR}/{tid}.cif")
            if not tres:
                continue
            pair = align_pairs(nres, tres)
            prof[tid] = {i + 1: c4_of(tres[j]) for i, j in enumerate(pair)
                         if j is not None and c4_of(tres[j]) is not None}
        def internal_rmsd(a, b):
            k = sorted(set(a) & set(b))
            if len(k) < 3:
                return None
            A = np.array([a[i] for i in k]); B = np.array([b[i] for i in k])
            R, t = feat.kabsch(A, B)
            return float(np.sqrt(((A @ R.T + t - B) ** 2).sum(1).mean()))
        medoid = None
        if len(prof) >= 2:
            best = None
            for tid, pa in prof.items():
                ds = [internal_rmsd(pa, pb) for oid, pb in prof.items() if oid != tid]
                ds = [d for d in ds if d is not None]
                if not ds:
                    continue
                mu = float(np.mean(ds))
                if best is None or mu < best[1]:
                    best = (tid, mu)
            if best:
                medoid = best[0]
                rec["F1_template"] = medoid
                rec["F1_mean_bank_spread"] = round(best[1], 2)
        elif prof:
            medoid = next(iter(prof))
            rec["F1_template"] = medoid
        if medoid:
            d = emit(build_conformer(medoid, s7_c4 or nat_in_pred), "F1")
            if d:
                rec.update(d)

        # ---------- F3 native-free selection (bp signature vs S7's own RNA) ----
        if s7_c4:
            s7_bp = bp_sig([s7_c4[k] for k in sorted(s7_c4)])
            bestf3, bd = None, None
            for tid, pa in prof.items():
                tb_bp = bp_sig([pa[k] for k in sorted(pa)])
                jac = len(s7_bp & tb_bp) / max(1, len(s7_bp | tb_bp))
                if bd is None or jac > bd:
                    bd, bestf3 = jac, tid
            if bestf3:
                rec["F3_template"] = bestf3
                rec["F3_bp_jaccard"] = round(bd, 3)
                d = emit(build_conformer(bestf3, s7_c4), "F3")
                if d:
                    rec.update(d)

        # ---------- F2 ORACLE best bank conformer ------------------------------
        bestf2, bq, bmet = None, None, None
        for tid in bank:
            atoms = build_conformer(tid, s7_c4 or nat_in_pred)
            if not atoms:
                continue
            p = f"{WORK}/{e}_F2try.pdb"
            b1c.write_pdb(p, prot, atoms)
            dq = b1c.dockq_all(p, natp)["dockq"]
            os.remove(p)
            if dq == dq and (bq is None or dq > bq):
                bq, bestf2, bmet = dq, tid, atoms
        if bestf2:
            rec["F2_template"] = bestf2
            d = emit(bmet, "F2")
            if d:
                rec.update(d)

        # ---------- F4 ORACLE native internal at S7 placement -------------------
        if s7_c4:
            src = [nat_c4[k - 1] for k in sorted(s7_c4) if nat_c4[k - 1] is not None]
            dst = [s7_c4[k] for k in sorted(s7_c4) if nat_c4[k - 1] is not None]
            if len(src) >= 3:
                R, t = feat.kabsch(np.array(src), np.array(dst))
                atoms = []
                for i, r_ in enumerate(nres):
                    for a in r_:
                        atoms.append((qb[i], i + 1, a.get_name(),
                                      (a.element or a.get_name()[0]).strip()[:2],
                                      np.asarray(a.get_coord(), float) @ R.T + t))
                d = emit(atoms, "F4")
                if d:
                    rec.update(d)

        # ---------- F5 ORACLE S7 internal at native placement ------------------
        if s7_c4:
            k = sorted(set(s7_c4) & set(nat_in_pred))
            if len(k) >= 3:
                A = np.array([s7_c4[i] for i in k]); B = np.array([nat_in_pred[i] for i in k])
                R, t = feat.kabsch(A, B)
                stq = feat.load(qpose)
                qrid = feat.contacting_pair(stq)[1]
                atoms = []
                qstd = [r for r in stq[0][qrid] if b1c.base1(r) is not None]
                pair = align_pairs(nres, qstd)
                for i, j in enumerate(pair):
                    if j is None:
                        continue
                    for a in qstd[j]:
                        atoms.append((qb[i], i + 1, a.get_name(),
                                      (a.element or a.get_name()[0]).strip()[:2],
                                      np.asarray(a.get_coord(), float) @ R.T + t))
                d = emit(atoms, "F5")
                if d:
                    rec.update(d)

        # ---------- F6 ORACLE native internal at native placement --------------
        atoms = []
        for i, r_ in enumerate(nres):
            for a in r_:
                atoms.append((qb[i], i + 1, a.get_name(),
                              (a.element or a.get_name()[0]).strip()[:2],
                              np.asarray(a.get_coord(), float) @ Rp.T + tp))
        d = emit(atoms, "F6")
        if d:
            rec.update(d)

        # ---------- F7 ORACLE best of 5 Boltz models ---------------------------
        preds = os.path.dirname(qpose)
        bestf7, b7 = None, None
        for pth in sorted(glob.glob(f"{preds}/{e}_model_*.pdb")):
            dq = b1c.dockq_all(pth, natp)["dockq"]
            if dq == dq and (b7 is None or dq > b7):
                b7, bestf7 = dq, pth
        if bestf7:
            rec["F7_model"] = os.path.basename(bestf7)
            mm7 = b1c.dockq_all(bestf7, natp)
            rec.update({f"F7_{k}": v for k, v in mm7.items()})
            r7, p7 = std_residues(bestf7)
            if r7:
                pr = align_pairs(nres, r7)
                f7c4 = {i + 1: c4_of(r7[j]) for i, j in enumerate(pr)
                        if j is not None and c4_of(r7[j]) is not None}
                rec.update({f"F7_{k}": v for k, v in
                            metrics_vs_native(f7c4, nat_c4, p7 or qpf, npf, iface).items()})

        rows.append(rec)
        if (n + 1) % 3 == 0:
            print(f"  {n+1}/{len(mine)} ({time.time()-t0:.0f}s)", flush=True)
            json.dump(rows, open(f"outputs/rnp/f1/b2a_part_{shard}.json", "w"))
    json.dump(rows, open(f"outputs/rnp/f1/b2a_part_{shard}.json", "w"))
    print(f"SHARD {shard} DONE {len(rows)} in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
