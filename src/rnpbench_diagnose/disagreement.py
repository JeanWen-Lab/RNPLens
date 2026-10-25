"""Component disagreement among candidate structures. No reference structure is read.

The three quantities are the benchmark's own decomposition axes -- protein internal, RNA internal, RNA
placement -- computed candidate-against-candidate rather than candidate-against-reference, through the
project's frozen correspondence and superposition. The routine used here was gated against
score_decomp.four_axes and agreed to within 1e-9 on 36 candidates.
"""
from itertools import combinations
import statistics

AXES = ("prot_internal_ca_rmsd", "rna_internal_c4_rmsd", "rna_placement_c4_rmsd")


def _deps():
    try:
        import numpy as np
        import score_decomp as SD
    except Exception as ex:
        raise RuntimeError("disagreement requires numpy and score_decomp on sys.path: %s" % ex)
    return np, SD


def axes_between(q, t):
    """The three axes between two parsed structures ((rna, prot) each). Reference-free."""
    np, SD = _deps()
    q_rna, q_prot = q
    t_rna, t_prot = t
    if not q_prot or not t_prot:
        return {"exclusion": "no_protein_chain"}
    pp = SD.prot_pairs([x[1] for x in q_prot], [x[1] for x in t_prot])
    idx = [(i, j) for i, j in enumerate(pp) if j is not None]
    if len(idx) < 3:
        return {"exclusion": "protein_pairs_lt_3"}
    A = np.array([q_prot[i][3] for i, _ in idx], float)
    B = np.array([t_prot[j][3] for _, j in idx], float)
    R, tr, prot_rmsd = SD.kabsch(A, B)
    if not q_rna or not t_rna:
        return {"exclusion": "no_rna_chain"}
    rp = SD.b2a.align_pairs(q_rna, t_rna)
    ridx = [(i, j) for i, j in enumerate(rp) if j is not None
            and SD.b2a.c4_of(q_rna[i]) is not None and SD.b2a.c4_of(t_rna[j]) is not None]
    if len(ridx) < 3:
        return {"exclusion": "rna_pairs_lt_3"}
    QR = np.array([SD.b2a.c4_of(q_rna[i]) for i, _ in ridx], float)
    TR = np.array([SD.b2a.c4_of(t_rna[j]) for _, j in ridx], float)
    _, _, rna_rmsd = SD.kabsch(QR, TR)
    moved = (R @ QR.T).T + tr
    place = float((((moved - TR) ** 2).sum(1).mean()) ** 0.5)
    return {"prot_internal_ca_rmsd": float(prot_rmsd), "rna_internal_c4_rmsd": float(rna_rmsd),
            "rna_placement_c4_rmsd": place, "n_prot_aligned": len(idx), "n_rna_aligned": len(ridx)}


def parse_all(paths):
    """Parse each structure once. Returns (parsed dict, exclusions dict)."""
    _, SD = _deps()
    parsed, excl = {}, {}
    for p in paths:
        rna, prot, err = SD.read_pose(p)
        if err:
            excl[p] = err
            continue
        parsed[p] = (rna, prot)
    return parsed, excl


def disagreement(paths, labels=None):
    """Median pairwise disagreement over the supplied structures. Refuses on fewer than two usable."""
    parsed, excl = parse_all(paths)
    if len(parsed) < 2:
        return {"usable": len(parsed), "exclusions": excl,
                "refused": "fewer than two usable structures: disagreement is undefined"}
    keys = list(parsed)
    vals = {a: [] for a in AXES}
    pair_excl = {}
    for i, j in combinations(range(len(keys)), 2):
        r = axes_between(parsed[keys[i]], parsed[keys[j]])
        if "exclusion" in r:
            pair_excl[r["exclusion"]] = pair_excl.get(r["exclusion"], 0) + 1
            continue
        for a in AXES:
            vals[a].append(r[a])
    if not vals[AXES[0]]:
        return {"usable": len(parsed), "exclusions": excl, "pair_exclusions": pair_excl,
                "refused": "no usable pair"}
    out = {"usable": len(parsed), "n_pairs": len(vals[AXES[0]]), "exclusions": excl,
           "pair_exclusions": pair_excl, "refused": None}
    if labels:
        out["members"] = [labels.get(kx, kx) for kx in keys]
    for a in AXES:
        out[a] = float(statistics.median(vals[a]))
    return out
