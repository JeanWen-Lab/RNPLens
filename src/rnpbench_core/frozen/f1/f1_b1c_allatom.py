#!/usr/bin/env python
"""RBP-B1c — sequence-aware ALL-ATOM repair of the B1b template baselines.

WHY THIS EXISTS. In B1b the template arms (S4 / S4p / S4o) were written as C4'-only RNA plus CA-only
protein, while S7 was Boltz's all-atom output. DockQ's native-contact terms (fnat, F1) need atomic contacts,
so the template arms scored fnat = 0 BY CONSTRUCTION. The representation-independent C4' RMSDs already
showed S7 ahead on both axes, but the DockQ effect size (+0.519) is not defensible as a headline until the
arms are representation-matched. This script rebuilds them all-atom.

THE DECISIVE DESIGN CHOICE: the PROTEIN is copied VERBATIM, all-atom, from the query's own Boltz pose into
every arm. S7 and the template arms therefore contain byte-identical protein coordinates, and the ONLY
difference between arms is the RNA. That removes protein representation as a confound completely, rather than
trying to match it approximately.

RNA RECONSTRUCTION (the brief's procedure):
  1. align query and template RNA by base sequence (difflib over one-letter bases)
  2. transfer the template's sugar-phosphate BACKBONE verbatim for each aligned position
  3. rebuild the BASE according to the QUERY's sequence: identical base type -> copy verbatim;
     different -> superpose an ideal nucleotide of the query's type onto the template residue's glycosidic
     frame and transfer the ideal base atoms
  4. query positions with no aligned template position are OMITTED and counted (never invented)
Measured on 60 pairs: median template/query aligned base identity is 0.591 and 83% of pairs are below 0.9,
so step 3 is doing real work -- this is not a cosmetic relabelling.

IDEAL NUCLEOTIDE LIBRARY: harvested from deposited natives rather than hardcoded, so geometry is
crystallographic. For each base type the residue with the full expected atom set and the lowest internal
deviation from the type's mean geometry is chosen.

SUPERPOSITION FRAME for base swapping: the atoms shared by ALL four bases via the glycosidic bond --
C1', N9/N1 (glycosidic nitrogen), and C4/C2 of the ring. Using the whole 6-ring would fail because purine
and pyrimidine rings are not in correspondence.
"""
from __future__ import annotations
import os, sys, csv, json, glob, subprocess, re, warnings, importlib.util, collections, difflib, time

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
sys.argv = _ARGV

import numpy as np

NATDIR = "outputs/rnp/fullrun/natives"
WORK = "outputs/rnp/f1/b1c_work"
LIB = "outputs/rnp/f1/b1c_ideal_nucleotides.json"
DOCKQ_BIN = "/home/jwen/miniforge3/envs/rnp-boltz/bin/DockQ"

BACKBONE = ["P", "OP1", "OP2", "O5'", "C5'", "C4'", "O4'", "C3'", "O3'", "C2'", "O2'", "C1'"]
BASE_ATOMS = {
    "A": ["N9", "C8", "N7", "C5", "C6", "N6", "N1", "C2", "N3", "C4"],
    "G": ["N9", "C8", "N7", "C5", "C6", "O6", "N1", "C2", "N2", "N3", "C4"],
    "C": ["N1", "C2", "O2", "N3", "C4", "N4", "C5", "C6"],
    "U": ["N1", "C2", "O2", "N3", "C4", "O4", "C5", "C6"],
}
PURINE = {"A", "G"}
# glycosidic frame: C1' plus the two base atoms bonded into the ring next to the glycosidic nitrogen.
FRAME = {"A": ["C1'", "N9", "C4", "C8"], "G": ["C1'", "N9", "C4", "C8"],
         "C": ["C1'", "N1", "C2", "C6"], "U": ["C1'", "N1", "C2", "C6"]}


SOLVENT = {"HOH", "WAT", "DOD", "MG", "ZN", "NA", "K", "CL", "CA", "MN", "SO4", "PO4", "GOL", "EDO"}


def base1(res):
    """Standard-RNA base letter, or None.

    Waters and ions MUST be filtered here: feat.load keeps the full chain, so `HOH` residues were being
    counted as RNA positions (1B7F: 8 of 20 'nucleotides' were water; 4JGN: 26 of 46). That inflated the
    query length, wrecked the query<->template index mapping, and was the direct cause of the 804 hard
    clashes seen in the first smoke test.
    """
    n = (res.get_resname() or "").strip().upper()
    if n in SOLVENT or not n:
        return None
    return n[-1] if n[-1] in "AUGC" else None


def build_library(entries, out=LIB):
    """Harvest one ideal (crystallographic, complete) nucleotide per base type from deposited natives."""
    best = {}
    pool = collections.defaultdict(list)
    for e in entries:
        p = f"{NATDIR}/{e}.cif"
        if not os.path.exists(p):
            continue
        try:
            st = feat.load(p)
            pid, rid = feat.contacting_pair(st)
        except Exception:
            continue
        if rid is None:
            continue
        for res in st[0][rid]:
            b = base1(res)
            if b is None:
                continue
            names = {a.get_name(): np.asarray(a.get_coord(), float) for a in res}
            need = set(BACKBONE[3:]) | set(BASE_ATOMS[b])      # P/OP1/OP2 absent at chain 5' end
            if not need.issubset(names):
                continue
            pool[b].append(names)
        if all(len(pool[b]) >= 40 for b in "AUGC"):
            break
    # pick the residue closest to its type's mean base geometry (internal coordinates, frame-invariant)
    for b, cands in pool.items():
        ats = BASE_ATOMS[b]
        D = []
        for nm in cands:
            X = np.array([nm[a] for a in ats])
            D.append(np.linalg.norm(X[:, None, :] - X[None, :, :], axis=-1))
        D = np.array(D)
        mu = D.mean(0)
        k = int(np.argmin(np.abs(D - mu).reshape(len(D), -1).mean(axis=1)))
        best[b] = {a: list(map(float, cands[k][a])) for a in cands[k]}
    json.dump({"library": best, "counts": {k: len(v) for k, v in pool.items()}}, open(out, "w"))
    return best


def kabsch_apply(src, dst, X):
    R, t = feat.kabsch(np.asarray(src, float), np.asarray(dst, float))
    return np.asarray(X, float) @ R.T + t


def rebuild_rna(tmpl_res, query_bases, lib, transform=None):
    """Sequence-aware all-atom RNA: template backbone + query-sequence bases.

    tmpl_res    : list of template Bio.PDB residues, ALREADY in 1:1 correspondence with query_bases
    query_bases : list of query base letters (same length; None entries are skipped)
    transform   : optional (R, t) applied to every produced coordinate (the arm's placement)
    Returns (atoms, stats) where atoms is [(resname, resid, atomname, element, xyz), ...].
    """
    out = []
    st = collections.Counter()
    for i, (tres, qb) in enumerate(zip(tmpl_res, query_bases)):
        if tres is None or qb is None:
            st["skipped_unaligned"] += 1
            continue
        tb = base1(tres)
        if tb is None:
            st["skipped_nonstd"] += 1
            continue
        names = {a.get_name(): np.asarray(a.get_coord(), float) for a in tres}
        got = []
        for a in BACKBONE:
            if a in names:
                got.append((a, names[a], a[0] if a[0] != "O" else "O"))
        if len([1 for a, _, _ in got if a in ("C4'", "C1'")]) < 2:
            st["skipped_no_sugar"] += 1
            continue
        if qb == tb:
            for a in BASE_ATOMS[qb]:
                if a in names:
                    got.append((a, names[a], a[0]))
            st["base_copied"] += 1
        else:
            fr_t, fr_q = FRAME[tb], FRAME[qb]
            if not all(a in names for a in fr_t) or qb not in lib:
                st["skipped_no_frame"] += 1
                continue
            ideal = {k: np.asarray(v, float) for k, v in lib[qb].items()}
            if not all(a in ideal for a in fr_q):
                st["skipped_lib_frame"] += 1
                continue
            src = np.array([ideal[a] for a in fr_q])
            dst = np.array([names[a] for a in fr_t])
            for a in BASE_ATOMS[qb]:
                if a in ideal:
                    got.append((a, kabsch_apply(src, dst, ideal[a][None, :])[0], a[0]))
            st["base_rebuilt"] += 1
        for a, xyz, el in got:
            if transform is not None:
                R, t = transform
                xyz = np.asarray(xyz, float) @ R.T + t
            out.append((qb, i + 1, a, el, np.asarray(xyz, float)))
    st["residues_emitted"] = len(set(r[1] for r in out))
    st["atoms"] = len(out)
    return out, st


def protein_allatom(pose_path):
    """The query's own Boltz protein, ALL ATOMS, verbatim -- identical in every arm."""
    st = feat.load(pose_path)
    pid, rid = feat.contacting_pair(st)
    if pid is None:
        return None, None, None
    atoms = []
    frames = []
    for i, res in enumerate(st[0][pid]):
        rn = (res.get_resname() or "ALA").strip()[:3]
        for a in res:
            atoms.append((rn, i + 1, a.get_name(), (a.element or a.get_name()[0]).strip()[:2],
                          np.asarray(a.get_coord(), float)))
        ca = [a for a in res if a.get_name() == "CA"]
        if ca:
            frames.append(np.asarray(ca[0].get_coord(), float))
    return atoms, np.array(frames), rid


def write_pdb(path, prot_atoms, rna_atoms):
    """Write a 2-chain PDB. An EMPTY chain is skipped entirely rather than emitting a bare TER: a leading
    orphan TER made OpenMM's PDBFile parser fail with "'NoneType' object has no attribute
    '_current_chain'", which silently disabled minimisation on every complex."""
    ser = 1
    lines = []
    for chain, items in (("A", prot_atoms), ("B", rna_atoms)):
        if not items:
            continue
        for resname, resid, atom, elem, xyz in items:
            an = atom if len(atom) >= 4 else (" " + atom)
            lines.append("ATOM  %5d %-4s %3s %s%4d    %8.3f%8.3f%8.3f  1.00  0.00          %2s" % (
                ser % 100000, an[:4], str(resname)[:3], chain, resid % 10000,
                xyz[0], xyz[1], xyz[2], (elem or "")[:2]))
            ser += 1
        lines.append("TER")
    open(path, "w").write("\n".join(lines) + "\n")


_RE = {k: re.compile(rf"{k}:\s*([0-9]*\.?[0-9]+)") for k in ("DockQ", "iRMSD", "LRMSD", "fnat")}


def dockq_all(model, native):
    try:
        out = subprocess.run([DOCKQ_BIN, model, native], capture_output=True, text=True,
                             timeout=900).stdout
    except Exception:
        return {k: float("nan") for k in ("dockq", "irmsd", "lrmsd", "fnat")}
    got = {}
    for key, name in (("DockQ", "dockq"), ("iRMSD", "irmsd"), ("LRMSD", "lrmsd"), ("fnat", "fnat")):
        m = _RE[key].search(out)
        got[name] = float(m.group(1)) if m else float("nan")
    return got


MAX_ALLOWED_SHIFT_A = 1.0   # a "restrained" minimisation that moves heavy atoms further is REJECTED


def minimize_rna(rna_atoms, max_iter=200, k_restraint=2000.0):
    """Restrained stereochemical minimisation of the rebuilt RNA (brief step 5).

    Heavy positional restraints keep the GROSS conformation fixed -- the point is to relieve the local
    strain introduced by grafting an ideal base onto a template sugar, not to refold anything. Returns
    (atoms, info); on any failure the INPUT atoms are returned unchanged with the reason recorded, so a
    minimisation problem can never silently masquerade as a geometry result.
    """
    try:
        import openmm as mm
        import openmm.app as app
        import openmm.unit as unit
    except Exception as ex:
        return rna_atoms, {"minimized": False, "reason": f"import:{type(ex).__name__}"}
    tmp = f"{WORK}/_min_{os.getpid()}.pdb"
    try:
        # amber14-all.xml uses TERMINAL-AWARE RNA templates: the 5' residue is G5/A5/C5/U5 (no phosphate)
        # and the 3' residue is A3/G3/C3/U3. Writing plain A/U/G/C made createSystem fail with
        # "No template found for residue 0 (G)" on every complex whose 5' residue lacks P/OP1/OP2 --
        # which is most of them, since the deposited chain starts mid-strand.
        rids = sorted(set(r[1] for r in rna_atoms))
        if not rids:
            return rna_atoms, {"minimized": False, "reason": "no_residues"}
        first, last = rids[0], rids[-1]
        renamed = []
        for rn, rid, an, el, xyz in rna_atoms:
            base = str(rn)[:1]
            if rid == first:
                nm = f"{base}5"
            elif rid == last:
                nm = f"{base}3"
            else:
                nm = base
            renamed.append((nm, rid, an, el, xyz))
        write_pdb(tmp, [], renamed)
        pdb = app.PDBFile(tmp)
        ff = app.ForceField("amber14-all.xml")
        modeller = app.Modeller(pdb.topology, pdb.positions)
        modeller.addHydrogens(ff)
        system = ff.createSystem(modeller.topology, nonbondedMethod=app.NoCutoff,
                                 constraints=None, rigidWater=False)
        rest = mm.CustomExternalForce("k*periodicdistance(x,y,z,x0,y0,z0)^2")
        rest.addGlobalParameter("k", k_restraint * unit.kilojoules_per_mole / unit.nanometer ** 2)
        for p in ("x0", "y0", "z0"):
            rest.addPerParticleParameter(p)
        heavy = [i for i, a in enumerate(modeller.topology.atoms()) if a.element is not None
                 and a.element.symbol != "H"]
        pos = modeller.positions
        for i in heavy:
            rest.addParticle(i, [pos[i][0], pos[i][1], pos[i][2]])
        system.addForce(rest)
        integ = mm.LangevinMiddleIntegrator(300 * unit.kelvin, 1 / unit.picosecond,
                                           0.002 * unit.picoseconds)
        sim = app.Simulation(modeller.topology, system, integ,
                             mm.Platform.getPlatformByName("CPU"))
        sim.context.setPositions(modeller.positions)
        e0 = sim.context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(
            unit.kilojoules_per_mole)
        sim.minimizeEnergy(maxIterations=max_iter)
        stt = sim.context.getState(getPositions=True, getEnergy=True)
        e1 = stt.getPotentialEnergy().value_in_unit(unit.kilojoules_per_mole)
        newpos = stt.getPositions(asNumpy=True).value_in_unit(unit.angstrom)
        # map minimised heavy atoms back onto the input ordering (hydrogens were appended, so the first
        # len(rna_atoms) topology atoms are the originals in order)
        out = []
        shift = []
        for i, (rn, rid, an, el, xyz) in enumerate(rna_atoms):
            nx = np.asarray(newpos[i], float)
            shift.append(float(np.linalg.norm(nx - np.asarray(xyz, float))))
            out.append((rn, rid, an, el, nx))
        info = {"energy_before": round(e0, 1), "energy_after": round(e1, 1),
                "max_atom_shift_A": round(max(shift), 3) if shift else 0.0,
                "mean_atom_shift_A": round(float(np.mean(shift)), 3) if shift else 0.0}
        # REJECT a minimisation that moved the gross conformation. The brief's step 5 is explicitly
        # "without changing the gross conformation"; an early attempt at k=50 moved atoms 5.05 A on
        # average and INCREASED clashes 2 -> 8, i.e. it was refolding, not relieving local strain.
        if info["mean_atom_shift_A"] > MAX_ALLOWED_SHIFT_A:
            info.update({"minimized": False, "reason": f"rejected_drift_{info['mean_atom_shift_A']}A"})
            return rna_atoms, info
        info["minimized"] = True
        return out, info
    except Exception as ex:
        return rna_atoms, {"minimized": False, "reason": f"{type(ex).__name__}:{str(ex)[:60]}"}
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def stereo_audit(rna_atoms):
    """Bond-length sanity + steric clashes. A rebuild that fails this must not be reported as DockQ-equal."""
    byres = collections.defaultdict(dict)
    for rn, rid, a, el, xyz in rna_atoms:
        byres[rid][a] = xyz
    bad_bond = 0
    nb = 0
    for rid, nm in byres.items():
        for u, v in [("C1'", "C2'"), ("C2'", "C3'"), ("C3'", "C4'"), ("C4'", "O4'"), ("O4'", "C1'")]:
            if u in nm and v in nm:
                d = float(np.linalg.norm(nm[u] - nm[v]))
                nb += 1
                if not (1.2 < d < 1.8):
                    bad_bond += 1
    X = np.array([x for *_, x in rna_atoms])
    clash = 0
    if len(X) > 1:
        d = np.linalg.norm(X[:, None, :] - X[None, :, :], axis=-1)
        np.fill_diagonal(d, 9e9)
        # ignore intra-residue pairs
        rid = np.array([r[1] for r in rna_atoms])
        same = rid[:, None] == rid[None, :]
        d[same] = 9e9
        clash = int((d < 2.0).sum() // 2)
    return {"bonds_checked": nb, "bonds_out_of_range": bad_bond, "hard_clashes_lt_2A": clash}


def main():
    shard = int(_ARGV[1]) if len(_ARGV) > 1 else 0
    nsh = int(_ARGV[2]) if len(_ARGV) > 2 else 1
    os.makedirs(WORK, exist_ok=True)
    rows_in = [r for r in csv.DictReader(open("outputs/rnp/f1/rbp_b1b_per_complex_metrics.tsv"),
                                        delimiter="\t")]
    if os.path.exists(LIB):
        lib = {k: v for k, v in json.load(open(LIB))["library"].items()}
    else:
        lib = build_library([r["entry_id"] for r in rows_in])
    mine = [r for i, r in enumerate(rows_in) if i % nsh == shard]
    print(f"shard {shard}/{nsh}: {len(mine)} of {len(rows_in)}", flush=True)

    out = []
    t0 = time.time()
    for n, q in enumerate(mine):
        e = q["entry_id"]
        tid = q.get("template_primary", "")
        rec = {"entry_id": e, "protein_cluster": q["protein_cluster"], "fold": q["fold"],
               "template_primary": tid}
        natp = f"{NATDIR}/{e}.cif"
        qpose = g0.top1_pose(e)
        if not tid or qpose is None or not os.path.exists(natp):
            rec["err"] = "no_template_or_pose"
            out.append(rec)
            continue
        prot, qpf_ca, _ = protein_allatom(qpose)
        if prot is None:
            rec["err"] = "no_protein"
            out.append(rec)
            continue
        try:
            stn = feat.load(natp)
            npid, nrid = feat.contacting_pair(stn)
            nat_res = [r for r in stn[0][nrid]]
            stt = feat.load(f"{NATDIR}/{tid}.cif")
            tpid, trid = feat.contacting_pair(stt)
            tmpl_res = [r for r in stt[0][trid]]
            tmpl_pf = feat.prot_frames(stt[0][tpid])
            npf = feat.prot_frames(stn[0][npid])
        except Exception as ex:
            rec["err"] = f"load:{type(ex).__name__}"
            out.append(rec)
            continue

        # Standard-RNA positions only (waters/ions already excluded by base1), keeping the residue objects
        # so the emitted chain is contiguous in sequence order.
        nat_std = [(i, r) for i, r in enumerate(nat_res) if base1(r) is not None]
        tmpl_std = [(j, r) for j, r in enumerate(tmpl_res) if base1(r) is not None]
        qb = [base1(r) for _, r in nat_std]
        tb = [base1(r) for _, r in tmpl_std]
        rec["n_query_nt_std"] = len(qb)
        rec["n_tmpl_nt_std"] = len(tb)
        if len(qb) < 3 or len(tb) < 3:
            rec["err"] = "too_few_std_nt"
            out.append(rec)
            continue
        # sequence alignment query <-> template over base letters
        sm = difflib.SequenceMatcher(None, "".join(qb), "".join(tb))
        pair = [None] * len(qb)
        for blk in sm.get_matching_blocks():
            for k in range(blk.size):
                pair[blk.a + k] = blk.b + k
        # Extend to unmatched query positions ONLY where an unused template residue is available, walking
        # outward from the anchored blocks so sequence order is preserved. INJECTIVE BY CONSTRUCTION:
        # the earlier proportional map reused one template residue for several query positions, stacking
        # rebuilt nucleotides on identical backbone coordinates (804 hard clashes on 4JGN). A query position
        # with no free template residue is left unaligned and COUNTED, never invented.
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
        tsel = [tmpl_std[j][1] if j is not None else None for j in pair]
        assert len([j for j in pair if j is not None]) == len(set(j for j in pair if j is not None)), \
            "template residue reused -- would stack atoms"
        nat_res = [r for _, r in nat_std]   # downstream C4' extraction uses standard positions only
        rec["n_query_nt"] = len(qb)
        rec["n_aligned"] = sum(1 for j in pair if j is not None)
        rec["frac_aligned"] = round(rec["n_aligned"] / max(1, len(qb)), 3)
        rec["seq_identity"] = round(sum(1 for i, j in enumerate(pair)
                                        if j is not None and qb[i] == tb[j]) / max(1, len(qb)), 3)

        # --- the three placements ------------------------------------------------
        stq_full = feat.load(qpose)
        qpid_full = feat.contacting_pair(stq_full)[0]
        qpf_full = feat.prot_frames(stq_full[0][qpid_full])
        tsrc = np.array([np.asarray(x[2]) for x in tmpl_pf])
        qdst = qpf_ca
        placements = {}
        got = gate.iterative_superpose(tsrc, qdst)
        if got is not None:
            placements["S4"] = (got[0], got[1])
        # S4p: template RNA conformation rigid-fit onto the cofolder's own predicted RNA
        stq = feat.load(qpose)
        qrid = feat.contacting_pair(stq)[1]
        qra = feat.rna_atoms(stq[0][qrid]) if qrid is not None else []
        # S4o: onto the native RNA expressed in the predicted-protein frame
        m2 = min(len(qpf_ca), len(npf))
        Rp, tp = feat.kabsch(np.array([np.asarray(x[2]) for x in npf[:m2]]), qpf_ca[:m2])
        nat_c4 = []
        for r in nat_res:
            a = [x for x in r if x.get_name() == "C4'"]
            nat_c4.append(np.asarray(a[0].get_coord(), float) if a else None)
        for tag, ref in (("S4p", [np.asarray(a[2]) for a in qra]),
                         ("S4o", [(c @ Rp.T + tp) if c is not None else None for c in nat_c4])):
            src = []
            dst = []
            refl = list(ref)
            for i, tres in enumerate(tsel):
                if tres is None or i >= len(refl) or refl[i] is None:
                    continue
                a = [x for x in tres if x.get_name() == "C4'"]
                if not a:
                    continue
                src.append(np.asarray(a[0].get_coord(), float))
                dst.append(np.asarray(refl[i], float))
            if len(src) >= 3:
                placements[tag] = feat.kabsch(np.array(src), np.array(dst))

        for tag, tf in placements.items():
            atoms, stt_ = rebuild_rna(tsel, qb, lib, transform=tf)
            if not atoms:
                rec[f"{tag}_err"] = "empty_rebuild"
                continue
            pre = stereo_audit(atoms)
            atoms, minfo = minimize_rna(atoms)
            rec.update({f"{tag}aa_min_{k}": v for k, v in minfo.items()})
            rec[f"{tag}aa_pre_clashes"] = pre["hard_clashes_lt_2A"]
            rec[f"{tag}aa_pre_bad_bonds"] = pre["bonds_out_of_range"]
            p = f"{WORK}/{e}_{tag}_aa.pdb"
            write_pdb(p, prot, atoms)
            mm = dockq_all(p, natp)
            rec.update({f"{tag}aa_{k}": v for k, v in mm.items()})
            aud = stereo_audit(atoms)
            rec.update({f"{tag}aa_{k}": v for k, v in aud.items()})
            rec[f"{tag}aa_n_atoms"] = stt_["atoms"]
            rec[f"{tag}aa_base_rebuilt"] = stt_.get("base_rebuilt", 0)
            rec[f"{tag}aa_base_copied"] = stt_.get("base_copied", 0)
            # Representation-independent C4' metrics on the rebuilt RNA, compared RESIDUE-INDEX-WISE.
            # CRITICAL: the rebuilt chain OMITS query positions with no aligned template residue (median
            # 33% of positions), so its k-th atom is NOT the k-th native nucleotide. Passing bare coordinate
            # lists to rna_metrics compares position k to position k and silently misregisters -- measured
            # as S4o placement 12.53 A here versus 5.20 A in B1b for the identical arm, an artefact that
            # vanished (4.47 A) on the fully-aligned subset. So both sides are subset to the SAME residue
            # indices before any RMSD is taken.
            c4 = {x[1]: x[4] for x in atoms if x[2] == "C4'"}      # keyed by QUERY residue index (1-based)
            idx = sorted(k for k in c4 if 1 <= k <= len(nat_c4) and nat_c4[k - 1] is not None)
            pred = [c4[k] for k in idx]
            nat = [nat_c4[k - 1] for k in idx]
            rec[f"{tag}aa_n_c4_compared"] = len(idx)
            mm2 = gate.rna_metrics(pred, nat, qpf_full, npf) if len(idx) >= 3 else {}
            rec.update({f"{tag}aa_{k}": v for k, v in mm2.items()})
            os.remove(p)

        # S7 rescored with the SAME protein source, for an exactly matched comparison
        mm = dockq_all(qpose, natp)
        rec.update({f"S7_{k}": v for k, v in mm.items()})
        out.append(rec)
        if (n + 1) % 5 == 0:
            print(f"  {n+1}/{len(mine)} ({time.time()-t0:.0f}s)", flush=True)
            json.dump(out, open(f"outputs/rnp/f1/b1c_part_{shard}.json", "w"))
    json.dump(out, open(f"outputs/rnp/f1/b1c_part_{shard}.json", "w"))
    print(f"SHARD {shard} DONE {len(out)} in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
