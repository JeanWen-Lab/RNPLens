"""Structure parsing, chain typing, interface contacts and RNA pose comparison.

Extracted verbatim in behaviour from RNPBENCH_PREDICT_AGREEMENT_V1 (development prototype). The numerical
definitions are unchanged, because the frozen development result was computed with them and the acceptance
suite requires this package to reproduce it. What changed is only where the declared lengths come from: the
contract, not a benchmark key.

TWO DECISIONS THAT LOOK LIKE DETAILS AND ARE NOT.
  1. Polymer residues include HETATM-flagged ones. Modified nucleotides and non-standard residues are written
     as HETATM by several engines; excluding them silently shortens chains and turns a correct prediction into
     an indexing failure. Only waters are dropped. (The development prototype's first run made this mistake;
     it was corrected before any comparison and the superseded run was retained.)
  2. Contacts are heavy-atom pairs within 5.0 A, in INPUT numbering, taking the closest copy implicitly by
     union over copies. Positions are only comparable across engines because eligibility already required
     every chain to match its declared length.
"""
import itertools

import numpy as np
from Bio.PDB import MMCIFParser, NeighborSearch, PDBParser

CONTACT_CUTOFF_A = 5.0
MAX_COPIES_FOR_PERMUTATION = 4
NUCLEIC_RESIDUE_NAMES = {"A", "C", "G", "U", "RA", "RC", "RG", "RU", "DA", "DC", "DG", "DT",
                         "PSU", "5MU", "OMG", "OMC", "2MG", "7MG", "1MA", "H2U", "M2G"}


def parse_model(path):
    parser = MMCIFParser(QUIET=True) if path.endswith((".cif", ".mmcif")) else PDBParser(QUIET=True)
    return parser.get_structure("m", path)[0]


def split_chains(model):
    """-> (protein_chains, rna_chains, chain_order). A chain is nucleic if >50% of its residue names are."""
    prot, rna, order = [], [], []
    for ch in model:
        res = [x for x in ch if x.id[0] != "W"]
        if not res:
            continue
        names = [x.get_resname().strip() for x in res]
        nucleic = sum(n in NUCLEIC_RESIDUE_NAMES for n in names) / len(names) > 0.5
        (rna if nucleic else prot).append((ch.id, res))
        order.append((ch.id, len(res), nucleic))
    return prot, rna, order


def interface_contacts(prot, rna, cutoff=CONTACT_CUTOFF_A):
    """-> (sorted contact pairs in 1-based input numbering, sorted protein surface positions)."""
    ratoms = [(j + 1, a) for _, res in rna for j, x in enumerate(res) for a in x if a.element != "H"]
    if not ratoms:
        return [], []
    ns = NeighborSearch([a for _, a in ratoms])
    rpos = {id(a): j for j, a in ratoms}
    contacts = set()
    for _, res in prot:
        for i, x in enumerate(res):
            for a in x:
                if a.element == "H":
                    continue
                for b in ns.search(a.coord, cutoff):
                    contacts.add((i + 1, rpos[id(b)]))
    return sorted(contacts), sorted({i for i, _ in contacts})


def backbone_tracks(prot, rna):
    """CA per protein residue and C4' per nucleotide, None where the atom is absent."""
    ca = [[(x["CA"].coord.tolist() if "CA" in x else None) for x in res] for _, res in prot]
    c4 = [[(x["C4'"].coord.tolist() if "C4'" in x else None) for x in res] for _, res in rna]
    return ca, c4


def kabsch_rmsd(P, Q, X, Y):
    """Superpose P onto Q (protein), apply to X, compare with Y (RNA). Returns RNA C4' RMSD in A."""
    Pc, Qc = P.mean(0), Q.mean(0)
    H = (P - Pc).T @ (Q - Qc)
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    Rm = Vt.T @ np.diag([1, 1, d]) @ U.T
    return float(np.sqrt((((X - Pc) @ Rm.T + Qc - Y) ** 2).sum(1).mean()))


def rna_pose_difference(o1, o2):
    """Minimum RNA C4' RMSD after protein superposition, over copy assignments.

    Copy permutations are enumerated only up to MAX_COPIES_FOR_PERMUTATION per polymer; beyond that the
    identity assignment is used. That bound is declared rather than hidden: with more copies the reported
    pose difference is an upper bound on the best assignment, and report.py labels it as such.
    """
    np_, nr = len(o1["ca"]), len(o1["c4"])
    if np_ != len(o2["ca"]) or nr != len(o2["c4"]):
        return None, None
    capped = np_ > MAX_COPIES_FOR_PERMUTATION or nr > MAX_COPIES_FOR_PERMUTATION
    perms_p = list(itertools.permutations(range(np_))) if np_ <= MAX_COPIES_FOR_PERMUTATION else [tuple(range(np_))]
    perms_r = list(itertools.permutations(range(nr))) if nr <= MAX_COPIES_FOR_PERMUTATION else [tuple(range(nr))]
    best = None
    for sp in perms_p:
        P, Q = [], []
        for a, b in zip(range(np_), sp):
            for u, v in zip(o1["ca"][a], o2["ca"][b]):
                if u is not None and v is not None:
                    P.append(u)
                    Q.append(v)
        if len(P) < 3:
            continue
        P, Q = np.array(P), np.array(Q)
        for sr in perms_r:
            X, Y = [], []
            for a, b in zip(range(nr), sr):
                for u, v in zip(o1["c4"][a], o2["c4"][b]):
                    if u is not None and v is not None:
                        X.append(u)
                        Y.append(v)
            if not X:
                continue
            r = kabsch_rmsd(P, Q, np.array(X), np.array(Y))
            best = r if best is None or r < best else best
    return best, capped


def weighted_jaccard(a, b):
    """Weighted Jaccard over per-engine occupancy maps. Keys sorted so the float sum is order-independent."""
    keys = sorted(set(a) | set(b))
    den = sum(max(a.get(k, 0), b.get(k, 0)) for k in keys)
    if den == 0:
        return None
    return sum(min(a.get(k, 0), b.get(k, 0)) for k in keys) / den


def connected_groups(nodes, edges):
    parent = {n: n for n in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        parent[find(a)] = find(b)
    groups = {}
    for n in nodes:
        groups.setdefault(find(n), []).append(n)
    return sorted(sorted(v) for v in groups.values())
