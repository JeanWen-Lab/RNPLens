"""Synthetic protein-RNA structures with controllable contacts, for the grouping tests (written under tmp_path).

Geometry: protein residue i (1-based) has its heavy atoms at about (10 i, 0, 2 (i mod 2)); neighbouring residues are
>= 10 A apart. RNA residue j is placed 3 A from the protein residue it is assigned to, so it contacts that residue
only (distance to the neighbours > 10 A), or 100 A away when unassigned. The contact set of a structure is therefore
exactly {(assign[j], j)} over assigned j. A protein position listed in `unresolved` carries only a hydrogen atom
(present as a residue, so chain lengths match, but not resolved).
"""
import hashlib
import json
import os

from rnpbench_report import agreement, contract


def _line(serial, name, resn, chain, resi, xyz, element):
    nm = (" %-3s" % name) if len(name) < 4 else name
    return "ATOM  %5d %-4s %3s %1s%4d    %8.3f%8.3f%8.3f%6.2f%6.2f          %2s" % (
        serial, nm, resn, chain, resi, xyz[0], xyz[1], xyz[2], 1.0, 50.0, element)


def write_pdb(path, n_prot, assign, unresolved=(), jitter=0.0):
    """assign: list (length = RNA length) of protein position or None. jitter shifts RNA atoms (changes P only)."""
    L, s = [], 1
    for i in range(1, n_prot + 1):
        x, z = 10.0 * i, 2.0 * (i % 2)
        if i in unresolved:
            L.append(_line(s, "H", "ALA", "A", i, (x, 0.0, z), "H")); s += 1
            continue
        for name, el, dx in (("N", "N", -0.8), ("CA", "C", 0.0), ("C", "C", 0.8)):
            L.append(_line(s, name, "ALA", "A", i, (x + dx, 0.0, z), el)); s += 1
    L.append("TER")
    for j, p in enumerate(assign, 1):
        if p is None:
            base = (10.0 * j, 100.0, 0.0)
        else:
            base = (10.0 * p, 3.0, 2.0 * (p % 2))
        b = (base[0] + jitter, base[1], base[2])
        for name, el, dy in (("P", "P", 0.5), ("C4'", "C", 0.0)):
            L.append(_line(s, name, "  A", "B", j, (b[0], b[1] + dy, b[2]), el)); s += 1
    L.append("TER")
    L.append("END")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("\n".join(L) + "\n")
    return path


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def make_project(root, n_prot, n_rna, specs):
    """specs: list of dicts {engine, run, sample, assign, designated, unresolved?, jitter?, broken?}.
    Writes structures, manifest.json and report_contract.json in the importer's layout. Returns the project path."""
    proj = os.path.join(root, "project")
    os.makedirs(proj, exist_ok=True)
    pseq, rseq = "A" * n_prot, "A" * n_rna
    structs, outs = [], []
    for i, sp in enumerate(specs, 1):
        path = os.path.join(root, "in", sp["engine"], sp["run"], "%s.pdb" % sp["sample"])
        if sp.get("broken"):                       # wrong RNA length -> Report INDEXING_UNVERIFIED
            write_pdb(path, n_prot, sp["assign"][:-1])
        else:
            write_pdb(path, n_prot, sp["assign"], sp.get("unresolved", ()), sp.get("jitter", 0.0) + 0.001 * i)
        ex = "%s#%s" % (sp["run"], sp["sample"])
        h = sha(path)
        structs.append({"id": "s%03d" % i, "engine": sp["engine"], "run": sp["run"], "sample": sp["sample"],
                        "execution": ex, "path": path, "original_sha256": h, "used_path": path, "used_sha256": h,
                        "designated": bool(sp.get("designated")), "chains": [], "verdict": "INCLUDED", "reasons": []})
        o = {"engine": sp["engine"], "execution": ex, "structure_path": path, "sha256": h,
             "confidence_dir": os.path.dirname(path)}
        if sp["engine"] == "OTHER":
            o.update(native_confidence=None, native_confidence_kind=None)
        outs.append(o)
    man = {"case_id": "synthetic", "construct": {"protein_sequence": pseq, "rna_sequence": rseq,
                                                 "protein_length": n_prot, "rna_length": n_rna},
           "structures": structs, "runs": [], "decisions": [], "resolution_answers": {}, "counts": {}}
    con = {"schema_version": "rnpbench-predict-contract-1", "case_id": "synthetic",
           "construct": {"protein_length": n_prot, "rna_length": n_rna, "protein_sequence": pseq, "rna_sequence": rseq},
           "outputs": outs}
    json.dump(man, open(os.path.join(proj, "manifest.json"), "w"), indent=1)
    json.dump(con, open(os.path.join(proj, "report_contract.json"), "w"), indent=1)
    return proj


def make_analysis(project, root):
    """Run rc3 Report's own agreement code on the project contract and write A/report/ as 'rnplens analyse' does."""
    a = os.path.join(root, "analysis")
    res = agreement.run(contract.load(os.path.join(project, "report_contract.json")))
    agreement.write(res, os.path.join(a, "report"))
    return a
