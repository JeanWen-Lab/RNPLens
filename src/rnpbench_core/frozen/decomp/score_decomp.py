#!/usr/bin/env python3
"""Bounded scoring pass on stored coordinates. Frozen protocol: SCORING_PROTOCOL.md.

No prediction, docking, candidate generation, training or target reselection. Every coordinate file
read here already existed. The project's own modules supply every correspondence definition; nothing
is re-implemented except the protein correspondence, which applies the project's own align_pairs
algorithm to the one-letter amino-acid sequence because no protein analogue existed (protocol s3).
"""
from __future__ import annotations
import csv
import difflib
import glob
import importlib.util
import json
import os
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor

import numpy as np

warnings.filterwarnings("ignore")
P = "/home/jwen/projects/PCfold3D-RNP"
os.chdir(P)


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    sys.modules[name] = m
    s.loader.exec_module(m)
    return m


feat = _load("feat", "scripts/rnp/f1_featurize_mp.py")
b1c = _load("b1c", "scripts/rnp/f1_b1c_allatom.py")
b2a = _load("b2a", "scripts/rnp/f1_b2a_matrix.py")

NAT = P + "/outputs/rnp/fullrun/natives"
OUT = os.environ.get("SCORE_OUT", "/tmp/decomp")
os.makedirs(OUT, exist_ok=True)


def kabsch(src, dst):
    """Rotation+translation taking src onto dst; returns (R, t, rmsd) over the supplied pairs."""
    sc, dc = src.mean(0), dst.mean(0)
    A, Bm = src - sc, dst - dc
    U, S, Vt = np.linalg.svd(A.T @ Bm)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1.0, 1.0, d])
    R = Vt.T @ D @ U.T
    fitted = (R @ A.T).T + dc
    rms = float(np.sqrt(((fitted - dst) ** 2).sum(1).mean()))
    return R, dc - (R @ sc), rms


def prot_pairs(q_letters, t_letters):
    """The project's align_pairs algorithm (b2a), applied to protein one-letter sequences."""
    sm = difflib.SequenceMatcher(None, "".join(q_letters), "".join(t_letters))
    pair = [None] * len(q_letters)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            pair[blk.a + k] = blk.b + k
    used = {j for j in pair if j is not None}
    for i in range(len(q_letters)):
        if pair[i] is not None:
            continue
        prev = next((pair[k] for k in range(i - 1, -1, -1) if pair[k] is not None), None)
        nxt = next((pair[k] for k in range(i + 1, len(q_letters)) if pair[k] is not None), None)
        lo = 0 if prev is None else prev + 1
        hi = len(t_letters) if nxt is None else nxt
        cand = [j for j in range(lo, hi) if j not in used]
        if cand:
            pair[i] = cand[0]
            used.add(cand[0])
    return pair


def read_pose(path):
    """(rna residues, protein frames) for the contacting pair, by the project's own chain selection."""
    try:
        st = feat.load(path)
        pid, rid = feat.contacting_pair(st)
    except Exception as ex:
        return None, None, "load_failed:" + type(ex).__name__
    if pid is None:
        return None, None, "no_contacting_pair"
    rna = [r for r in st[0][rid] if b1c.base1(r) is not None] if rid is not None else []
    prot = feat.prot_frames(st[0][pid])
    return rna, prot, None


def four_axes(pose_path, nat_rna, nat_prot):
    """Protein internal, RNA internal, RNA placement. Each computed independently (protocol s1)."""
    rec = {}
    q_rna, q_prot, err = read_pose(pose_path)
    if err:
        return {"exclusion": err}
    # ---- protein internal: CA superposed on native CA over corresponding residues
    if not q_prot or not nat_prot:
        rec["exclusion"] = "no_protein_chain"
        return rec
    qp = [x[1] for x in q_prot]
    tp = [x[1] for x in nat_prot]
    pp = prot_pairs(qp, tp)
    idx = [(i, j) for i, j in enumerate(pp) if j is not None]
    if len(idx) < 3:
        rec["exclusion"] = "protein_pairs_lt_3"
        return rec
    A = np.array([q_prot[i][3] for i, _ in idx], float)          # CA of pose
    Bm = np.array([nat_prot[j][3] for _, j in idx], float)       # CA of native
    R, t, rec["prot_internal_ca_rmsd"] = kabsch(A, Bm)
    rec["n_prot_aligned"] = len(idx)
    rec["n_prot_pose"] = len(qp)
    rec["n_prot_native"] = len(tp)
    # ---- RNA internal: C4' superposed on native C4' over the project's RNA correspondence
    if not q_rna or not nat_rna:
        rec["exclusion"] = "no_rna_chain"
        return rec
    rp = b2a.align_pairs(q_rna, nat_rna)
    ridx = [(i, j) for i, j in enumerate(rp) if j is not None
            and b2a.c4_of(q_rna[i]) is not None and b2a.c4_of(nat_rna[j]) is not None]
    if len(ridx) < 3:
        rec["exclusion"] = "rna_pairs_lt_3"
        return rec
    QR = np.array([b2a.c4_of(q_rna[i]) for i, _ in ridx], float)
    TR = np.array([b2a.c4_of(nat_rna[j]) for _, j in ridx], float)
    _, _, rec["rna_internal_c4_rmsd"] = kabsch(QR, TR)
    rec["n_rna_aligned"] = len(ridx)
    rec["n_rna_pose"] = len(q_rna)
    rec["n_rna_native"] = len(nat_rna)
    # ---- placement: apply the PROTEIN transform to the pose RNA, no RNA-side fitting
    moved = (R @ QR.T).T + t
    rec["rna_placement_c4_rmsd"] = float(np.sqrt(((moved - TR) ** 2).sum(1).mean()))
    return rec


def native_of(entry):
    p = os.path.join(NAT, entry + ".cif")
    if not os.path.exists(p):
        return None, None, "native_absent"
    nat_rna, nat_prot, err = read_pose(p)
    if err:
        return None, None, "native_" + err
    return nat_rna, nat_prot, None


# ---------------------------------------------------------------- cohort A: the 65 x 50 pool
POOL = P + "/outputs/rnp/jpf/nscale/boltz_out"


def do_entry_A(entry):
    nat_rna, nat_prot, err = native_of(entry)
    rows = []
    if err:
        return [{"entry_id": entry, "sample_index": -1, "exclusion": err}]
    pat = "%s/boltz_results_%s/predictions/%s/%s_model_*.pdb" % (POOL, entry, entry, entry)
    for f in sorted(glob.glob(pat)):
        si = int(f.rsplit("_model_", 1)[1].split(".")[0])
        rec = {"entry_id": entry, "sample_index": si, "pose_path": f}
        rec.update(four_axes(f, nat_rna, nat_prot))
        if "exclusion" not in rec:
            try:
                mm = b1c.dockq_all(f, os.path.join(NAT, entry + ".cif"))
                rec["fnat"] = mm.get("fnat")
                rec["dockq_recomputed"] = mm.get("dockq")
                rec["irmsd"] = mm.get("irmsd")
                rec["lrmsd"] = mm.get("lrmsd")
            except Exception as ex:
                rec["dockq_err"] = type(ex).__name__
        rows.append(rec)
    if not rows:
        rows = [{"entry_id": entry, "sample_index": -1, "exclusion": "no_models_found"}]
    return rows


# ------------------------------------------------- cohort B: protein internal for the stored arms
P3DIRS = ["outputs/rnp/f1/boltz_regen_out", "outputs/rnp/f1/boltz_scale_out"]
P4DIR = "outputs/rnp/f1/boltz_cc_p4_out"
P0DIR = "outputs/rnp/f1/boltz_cc_p0_out"


def prot_only(pose_path, nat_prot):
    q_rna, q_prot, err = read_pose(pose_path)
    if err:
        return {"exclusion": err}
    if not q_prot or not nat_prot:
        return {"exclusion": "no_protein_chain"}
    qp = [x[1] for x in q_prot]
    tp = [x[1] for x in nat_prot]
    pp = prot_pairs(qp, tp)
    idx = [(i, j) for i, j in enumerate(pp) if j is not None]
    if len(idx) < 3:
        return {"exclusion": "protein_pairs_lt_3"}
    A = np.array([q_prot[i][3] for i, _ in idx], float)
    Bm = np.array([nat_prot[j][3] for _, j in idx], float)
    _, _, rms = kabsch(A, Bm)
    return {"prot_internal_ca_rmsd": rms, "n_prot_aligned": len(idx),
            "n_prot_pose": len(qp), "n_prot_native": len(tp)}


def do_entry_B(args):
    entry, donor = args
    out = []
    nat_rna, nat_prot, err = native_of(entry)
    if err:
        return [{"entry_id": entry, "arm": "-", "exclusion": err}]
    p3d = next((d for d in P3DIRS
                if os.path.isdir("%s/boltz_results_%s/predictions/%s" % (d, entry, entry))), None)
    # P3: the CORRECT protein -> scored against the target's own native protein
    if p3d is None:
        out.append({"entry_id": entry, "arm": "P3", "exclusion": "arm_not_stored"})
    else:
        for f in sorted(glob.glob("%s/boltz_results_%s/predictions/%s/%s_model_*.pdb" % (p3d, entry, entry, entry))):
            r = {"entry_id": entry, "arm": "P3", "reference": entry,
                 "sample_index": int(f.rsplit("_model_", 1)[1].split(".")[0])}
            r.update(prot_only(f, nat_prot))
            out.append(r)
    # P4: an UNRELATED protein -> the target native is NOT its reference (protocol s7).
    # Scored against the DONOR's native where one exists; otherwise excluded with that reason.
    dn_rna, dn_prot, dn_err = (None, None, "donor_unknown") if not donor else native_of(donor)
    for f in sorted(glob.glob("%s/boltz_results_%s/predictions/%s/%s_model_*.pdb" % (P4DIR, entry, entry, entry))):
        r = {"entry_id": entry, "arm": "P4", "reference": donor or "",
             "sample_index": int(f.rsplit("_model_", 1)[1].split(".")[0])}
        if dn_err:
            r["exclusion"] = "donor_native_absent" if dn_err != "donor_unknown" else "donor_unknown"
        else:
            r.update(prot_only(f, dn_prot))
        out.append(r)
    # P0: RNA alone, contains no protein by construction
    if glob.glob("%s/boltz_results_%s/predictions/%s/%s_model_*.pdb" % (P0DIR, entry, entry, entry)):
        out.append({"entry_id": entry, "arm": "P0", "reference": entry,
                    "exclusion": "arm_contains_no_protein_by_construction"})
    return out


def write(rows, name, cols):
    with open(os.path.join(OUT, name), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "A"
    nw = int(os.environ.get("SCORE_WORKERS", "24"))
    if which == "A":
        ents = [r["entry_id"] for r in csv.DictReader(
            open("outputs/rnp/jpf/nscale/nscale_input_manifest.tsv"), delimiter="\t")]
        rows = []
        with ProcessPoolExecutor(nw) as ex:
            for i, rr in enumerate(ex.map(do_entry_A, ents)):
                rows += rr
                print("  A %d/%d" % (i + 1, len(ents)), flush=True)
        write(rows, "cohortA_four_axes.tsv",
              ["entry_id", "sample_index", "prot_internal_ca_rmsd", "rna_internal_c4_rmsd",
               "rna_placement_c4_rmsd", "fnat", "dockq_recomputed", "irmsd", "lrmsd",
               "n_prot_aligned", "n_prot_pose", "n_prot_native", "n_rna_aligned", "n_rna_pose",
               "n_rna_native", "exclusion", "dockq_err", "pose_path"])
        print("cohort A rows", len(rows), flush=True)
    else:
        don = {}
        dp = "outputs/rnp/f1/rnp_cf0cc_output_effect_by_cluster.tsv"
        if os.path.exists(dp):
            for r in csv.DictReader(open(dp), delimiter="\t"):
                e = (r.get("entry_id") or "").strip().upper()
                if e:
                    don[e] = (r.get("donor") or "").strip().upper()
        ents = sorted({d.split("boltz_results_")[-1] for d in os.listdir(P4DIR)
                       if d.startswith("boltz_results_")})
        rows = []
        with ProcessPoolExecutor(nw) as ex:
            for i, rr in enumerate(ex.map(do_entry_B, [(e, don.get(e, "")) for e in ents])):
                rows += rr
                print("  B %d/%d" % (i + 1, len(ents)), flush=True)
        write(rows, "cohortB_protein_internal.tsv",
              ["entry_id", "arm", "reference", "sample_index", "prot_internal_ca_rmsd",
               "n_prot_aligned", "n_prot_pose", "n_prot_native", "exclusion"])
        print("cohort B rows", len(rows), "| donor map", len(don), flush=True)
