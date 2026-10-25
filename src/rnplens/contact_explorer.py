"""Data for the viewer's nucleotide contact explorer (rnplens view; display only, no new scientific method).

For one structure copy this module records, from the structure file and Report's own per-structure contact record
(ANALYSIS/report/contacts_by_output.json):

  residues   construct position -> structure residue (chain, auth_seq_id, insertion code, residue name), using the
             correspondence Report itself uses: the i-th residue (waters dropped, HETATM kept) of a chain is construct
             position i (rnpbench_report.geometry.split_chains; Report only analyses chains whose length equals the
             construct length, so i is the construct position).
  contacts   every Report pair (protein position, RNA position) of this structure, with the chain pair(s) in which it
             occurs, and -- only when the distance check passes -- the minimum heavy-atom distance and the closest
             atom pair (names and file coordinates, used to draw the contact line).

Distance check (pre-registered in records/viewer/nt_contacts/PREREG_NT_CONTACTS.md): the viewer recomputes, for every
protein/RNA residue pair, the minimum distance between heavy atoms (element != H) with Report's own parser
(rnpbench_report.geometry.parse_model / split_chains, imported read-only). The set of pairs with minimum distance
<= CONTACT_CUTOFF_A (5.0 A, Report's constant) must equal Report's recorded pair set for the structure exactly. If it
does, distances are shown rounded to 0.01 A; if not, every distance of that structure is 'Not available' and the
reason is recorded. Report's record stays the only source of which residues are in contact.

Ensemble support (kept separate from the structure on screen): for each engine, how many of the engine's structures
with a Report contact record list a pair / an RNA position / a protein position, with the structure ids and the
denominator. Engines are never pooled. Recurrence is a count of predictions, not evidence about the real complex.
"""
import json
import os

import numpy as np

from . import provenance as pv

REL = "report/contacts_by_output.json"
DIST_DECIMALS = 2


class ExplorerError(ValueError):
    pass


def _geometry():
    from rnpbench_report import geometry      # frozen Report component, used read-only
    return geometry


def cutoff():
    return float(_geometry().CONTACT_CUTOFF_A)


def _ptr(key):
    return key.replace("~", "~0").replace("/", "~1")


def residue_map(path):
    """{chain: [[construct_position, auth_seq_id, insertion_code, residue_name, is_hetero], ...]} and
    {'protein': [chains], 'rna': [chains]} classified exactly as Report classifies them."""
    G = _geometry()
    prot, rna, _ = G.split_chains(G.parse_model(path))
    res = {}
    for ch, rs in prot + rna:
        res[ch] = [[i + 1, int(x.id[1]), (x.id[2] or "").strip(), x.get_resname().strip(), x.id[0] != " "]
                   for i, x in enumerate(rs)]
    return res, {"protein": [c for c, _ in prot], "rna": [c for c, _ in rna]}, (prot, rna)


def _heavy(res):
    xyz, owner, names = [], [], []
    for i, x in enumerate(res):
        for a in x:
            if a.element != "H":
                xyz.append(a.coord)
                owner.append(i)
                names.append(a.get_id())
    return np.asarray(xyz, dtype=np.float64).reshape(-1, 3), np.asarray(owner, dtype=np.int64), names


def min_distances(prot_res, rna_res, limit):
    """{(i, j): (d, protein_atom_index, rna_atom_index)} for 1-based residue indices whose minimum heavy-atom
    distance is <= limit, plus the heavy-atom arrays. float64 arithmetic on the parser's coordinates."""
    P, po, pn = _heavy(prot_res)
    R, ro, rn = _heavy(rna_res)
    out = {}
    if not len(P) or not len(R):
        return out, (P, pn, R, rn)
    for i in range(len(prot_res)):
        rows = np.nonzero(po == i)[0]
        if not len(rows):
            continue
        d = np.sqrt(((P[rows][:, None, :] - R[None, :, :]) ** 2).sum(-1))    # (atoms of residue i) x (RNA atoms)
        col = d.min(axis=0)
        near = np.nonzero(col <= limit)[0]
        for j in sorted(set(ro[near].tolist())):
            cols = np.nonzero(ro == j)[0]
            sub = d[:, cols]
            k = int(np.argmin(sub))                     # first minimum in file atom order
            a, b = divmod(k, len(cols))
            out[(i + 1, j + 1)] = (float(sub[a, b]), int(rows[a]), int(cols[b]))
    return out, (P, pn, R, rn)


def structure_record(path, chains, report_pairs, key, structure_id=None, engine=None, construct_lengths=None):
    """Contact-explorer record for one structure copy (see module docstring). report_pairs: Report's list
    [[protein_pos, rna_pos], ...] for this structure, or None when Report has no record for it."""
    rec = {"key": key, "structure_id": structure_id, "engine": engine, "record": REL,
           "chains": {"protein": [chains["protein"]] if isinstance(chains.get("protein"), str) else list(chains.get("protein") or []),
                      "rna": [chains["rna"]] if isinstance(chains.get("rna"), str) else list(chains.get("rna") or [])},
           "available": False, "reason": None, "residues": {}, "contacts": [],
           "distance_check": {"status": "NOT_RUN", "cutoff_A": None}}
    try:
        res, by_report, (prot, rna) = residue_map(path)
    except Exception as ex:                                     # unreadable file: say so, show nothing
        rec["reason"] = "structure file could not be parsed (%s)" % type(ex).__name__
        return rec
    if construct_lengths is not None:
        lp, lr = construct_lengths
        bad = [c for c in by_report["protein"] if len(res[c]) != lp] + [c for c in by_report["rna"] if len(res[c]) != lr]
        if bad:                                   # index i is not construct position i: no correspondence is shown
            rec["reason"] = ("chain(s) %s differ in length from the construct (protein %d, RNA %d); construct positions "
                             "cannot be assigned" % (",".join(bad), lp, lr))
            rec["numbering"] = "INDEXING_UNVERIFIED"
            return rec
    rec["residues"] = res
    rec["numbering"] = "construct position = residue index in chain (Report's correspondence)"
    if report_pairs is None:
        rec["reason"] = "Report has no contact record for this structure (it was not analysed as ELIGIBLE)"
        return rec
    if sorted(rec["chains"]["protein"]) != sorted(by_report["protein"]) or sorted(rec["chains"]["rna"]) != sorted(by_report["rna"]):
        rec["reason"] = ("declared chains %s / %s differ from the chains Report's parser classifies as protein %s / RNA %s"
                         % (rec["chains"]["protein"], rec["chains"]["rna"], by_report["protein"], by_report["rna"]))
        return rec
    lim = cutoff()
    rec["distance_check"]["cutoff_A"] = lim
    found = {}                                                  # (p, r) -> [(pc, rc, d, pa, ra, pxyz, rxyz)]
    for pc, pres in prot:
        for rc, rres in rna:
            md, (P, pn, R, rn) = min_distances(pres, rres, lim)
            for (i, j), (d, a, b) in md.items():
                found.setdefault((i, j), []).append((pc, rc, d, pn[a], rn[b], [round(float(v), 3) for v in P[a]],
                                                     [round(float(v), 3) for v in R[b]]))
    want = {(int(p), int(r)) for p, r in report_pairs}
    got = set(found)
    ok = want == got
    near = [abs(c[2] - lim) for v in found.values() for c in v]
    rec["distance_check"].update({
        "status": "PASS" if ok else "FAIL", "n_report_pairs": len(want), "n_recomputed_pairs": len(got),
        "only_in_report": sorted([list(x) for x in want - got])[:50], "only_recomputed": sorted([list(x) for x in got - want])[:50],
        "smallest_margin_to_cutoff_A": round(min(near), 6) if near else None,
        "method": "minimum heavy-atom distance per residue pair, float64, rnpbench_report.geometry.parse_model/split_chains"})
    rec["available"] = True
    rows = []
    for idx, (p, r) in enumerate(report_pairs):
        eid = pv.evidence_id(REL, "/%s/%d" % (_ptr(key), idx))
        hits = found.get((int(p), int(r))) or []
        if ok and hits:
            for pc, rc, d, pa, ra, pxyz, rxyz in hits:
                rows.append({"pc": pc, "p": int(p), "rc": rc, "r": int(r), "d": round(d, DIST_DECIMALS), "pa": pa, "ra": ra,
                             "pxyz": pxyz, "rxyz": rxyz, "eid": eid})
        else:                                                   # Report's pair is shown; no distance, no line
            for pc in rec["chains"]["protein"]:
                for rc in rec["chains"]["rna"]:
                    rows.append({"pc": pc, "p": int(p), "rc": rc, "r": int(r), "d": None, "pa": None, "ra": None,
                                 "pxyz": None, "rxyz": None, "eid": eid})
    if not ok:
        rec["reason_distances"] = ("recomputed contact set differs from Report's record (%d only in Report, %d only "
                                   "recomputed); distances are not shown for this structure" % (len(want - got), len(got - want)))
    rec["contacts"] = rows
    return rec


def ensemble(cbo, key_to_id):
    """{engine: {'n': n, 'ids': [...], 'pair': {'p-r': [k...]}, 'rna': {r: [k...]}, 'protein': {p: [k...]}}} where k
    indexes 'ids'. Built from every structure of the engine that has a Report contact record."""
    out = {}
    for key in sorted(cbo):
        eng = key.split("|", 1)[0]
        e = out.setdefault(eng, {"n": 0, "ids": [], "keys": [], "pair": {}, "rna": {}, "protein": {}})
        k = len(e["ids"])
        e["ids"].append(key_to_id.get(key, key))
        e["keys"].append(key)
        e["n"] += 1
        pairs = {(int(p), int(r)) for p, r in cbo[key]}
        for p, r in sorted(pairs):
            e["pair"].setdefault("%d-%d" % (p, r), []).append(k)
        for r in sorted({r for _, r in pairs}):
            e["rna"].setdefault(str(r), []).append(k)
        for p in sorted({p for p, _ in pairs}):
            e["protein"].setdefault(str(p), []).append(k)
    return out


def load_records(analysis_dir):
    with open(os.path.join(analysis_dir, REL), encoding="utf-8") as fh:
        return json.load(fh)
