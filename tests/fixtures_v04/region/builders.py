"""Fixture builders for the region tests. Every fixture is written under the test's tmp_path from the bundled 7K9D
example (Boltz-2 predictions of an example complex); nothing here is a sealed or excluded target, and nothing is
read from outside the repository."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EX = os.path.join(ROOT, "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")
DG = os.path.join(EX, "reference_free", "diagnose_7K9D")
PROT_FASTA = os.path.join(EX, "reference_based", "7K9D_protein.fasta")
RNA_FASTA = os.path.join(EX, "reference_based", "7K9D_rna.fasta")
EXEC_A = os.path.join(RF, "exec_A", "7K9D_model_0.pdb")
EXEC_B = os.path.join(RF, "exec_B", "7K9D_model_0.pdb")


def diag(k):
    """Further Boltz-2 samples of the same example (model_0 is byte-identical to exec_A)."""
    return os.path.join(DG, "7K9D_model_%d.pdb" % k)


def place(dst_dir, src_pdb, k=0, score=0.5, edit=None):
    """Write <dst_dir>/7K9D_model_<k>.pdb (optionally edited) plus a Boltz-2 confidence file, so import recognises the
    Boltz-2 flat layout and can designate the highest-scoring sample of the run."""
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, "7K9D_model_%d.pdb" % k)
    lines = open(src_pdb).read().splitlines()
    if edit:
        lines = edit(lines)
    open(dst, "w").write("\n".join(lines) + "\n")
    json.dump({"confidence_score": score}, open(os.path.join(dst_dir, "confidence_7K9D_model_%d.json" % k), "w"))
    return dst


def _is_atom(l):
    return l.startswith(("ATOM  ", "HETATM"))


def _chain(l):
    return l[21]


def _resseq(l):
    return int(l[22:26])


def delete_residues(chain, positions):
    def f(lines):
        return [l for l in lines if not (_is_atom(l) and _chain(l) == chain and _resseq(l) in positions)]
    return f


def renumber(chain, offset):
    def f(lines):
        return [(l[:22] + "%4d" % (_resseq(l) + offset) + l[26:]) if _is_atom(l) and _chain(l) == chain else l for l in lines]
    return f


def rename_residue(chain, pos, new, hetatm=True):
    """E.g. U15 -> PSU written as HETATM, as engines write modified nucleotides."""
    def f(lines):
        out = []
        for l in lines:
            if _is_atom(l) and _chain(l) == chain and _resseq(l) == pos:
                l = ("HETATM" if hetatm else l[:6]) + l[6:17] + "%3s" % new + l[20:]
            out.append(l)
        return out
    return f


def hydrogen_only(chain, pos):
    """Keep one atom of the residue and turn it into a hydrogen: the residue is still present (chain length and
    sequence unchanged) but has no heavy atom, i.e. the position is not resolved."""
    def f(lines):
        out, kept = [], False
        for l in lines:
            if _is_atom(l) and _chain(l) == chain and _resseq(l) == pos:
                if kept:
                    continue
                kept = True
                l = l[:12] + " H1'" + l[16:76] + " H" + l[78:]
            out.append(l)
        return out
    return f


def duplicate_chain(src_chain, new_chain, shift=(200.0, 0.0, 0.0)):
    """Append a second copy of an RNA chain, translated far away (two RNA copies; Report takes the union)."""
    def f(lines):
        body = [l for l in lines if not l.startswith("END")]
        extra = []
        for l in lines:
            if _is_atom(l) and _chain(l) == src_chain:
                x, y, z = float(l[30:38]) + shift[0], float(l[38:46]) + shift[1], float(l[46:54]) + shift[2]
                extra.append(l[:21] + new_chain + l[22:30] + "%8.3f%8.3f%8.3f" % (x, y, z) + l[54:])
        return body + ["TER"] + extra + ["END"]
    return f


def compose(*fs):
    def f(lines):
        for g in fs:
            lines = g(lines)
        return lines
    return f


def project(tmp, runs, name="p", accept_derived=False):
    """runs: {run_name: [(src_pdb, score, edit), ...]} -> (project dir, analysis dir); Diagnose is not run."""
    from rnplens import analyse, importer
    inp = os.path.join(str(tmp), "in_" + name)
    for r, items in runs.items():
        for k, (src, score, edit) in enumerate(items):
            place(os.path.join(inp, r), src, k, score, edit)
    ps, rs = importer.read_sequence_arg(PROT_FASTA), importer.read_sequence_arg(RNA_FASTA)
    P, A = os.path.join(str(tmp), name), os.path.join(str(tmp), name + "_analysis")
    code = importer.run([inp], ps, rs, P, "7K9D_example", "BOLTZ2", accept_derived=accept_derived)
    assert code == 0, "import failed with %d" % code
    assert analyse.run(P, A, diagnose=False) == 0
    return P, A


def example_project(tmp):
    """The bundled two-run example exactly as docs/region.md uses it (exec_A, exec_B)."""
    from rnplens import analyse, importer
    ps, rs = importer.read_sequence_arg(PROT_FASTA), importer.read_sequence_arg(RNA_FASTA)
    P, A = os.path.join(str(tmp), "p"), os.path.join(str(tmp), "r")
    assert importer.run([os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B")], ps, rs, P, "7K9D_example", "BOLTZ2") == 0
    assert analyse.run(P, A, diagnose=False) == 0
    return P, A


def swap_used_file(P, A, sid, new_file):
    """Make a deliberately inconsistent project: structure `sid` now points at `new_file`, with the manifest and
    Report's per-output checksum updated, while Report's contact list is the one of the old file. Used only to test
    that coverage is checked in the used file and never guessed."""
    from rnplens.provenance import sha256_file
    mp = os.path.join(P, "manifest.json")
    man = json.load(open(mp))
    h = sha256_file(new_file)
    ex = None
    for s in man["structures"]:
        if s["id"] == sid:
            s["used_path"], s["used_sha256"] = os.path.abspath(new_file), h
            ex = (s["engine"], s["execution"])
    assert ex is not None
    json.dump(man, open(mp, "w"), indent=1)
    rp = os.path.join(A, "report", "result.json")
    rr = json.load(open(rp))
    for o in rr["per_output"]:
        if (o["engine"], o["execution"]) == ex:
            o["sha256"] = h
    json.dump(rr, open(rp, "w"), indent=1)


def assistant_run(tmp, rna=(13, 23)):
    """An assistant run directory made with the deterministic stub planner (no language model, no network): import
    both example runs, analyse, region counts; answer in deterministic template mode."""
    import shutil
    from rnplens_assistant import ask, llm
    t = os.path.join(str(tmp), "task")
    shutil.copytree(os.path.join(RF, "exec_A"), os.path.join(t, "runA"))
    shutil.copytree(os.path.join(RF, "exec_B"), os.path.join(t, "runB"))
    shutil.copy(PROT_FASTA, os.path.join(t, "protein.fasta")); shutil.copy(RNA_FASTA, os.path.join(t, "rna.fasta"))
    json.dump({"task_id": "dev_region", "reference_files": []}, open(os.path.join(t, "task.json"), "w"))

    def step(tool, **kw):
        s = {k: None for k in ask.PLAN_SCHEMA["properties"]["steps"]["items"]["properties"]}
        s.update(tool=tool, purpose="dev", **kw)
        return s
    plan = {"goal": "AGREEMENT", "reference_supplied": False, "requested_capabilities": [], "clarification_needed": None,
            "steps": [step("import_predictions", project_id="p", folders=["run_001", "run_002"],     # opaque identifiers (0.4)
                           protein_fasta="protein_sequence_001", rna_fasta="rna_sequence_001", accept_offsets=False),
                      step("analyse_predictions", project_id="p"),
                      step("region_contacts", project_id="p", rna_start=rna[0], rna_end=rna[1])]}
    run_dir = os.path.join(str(tmp), "run")
    ask.run(t, "Which residues contact RNA %d-%d in both runs?" % rna, run_dir, llm.Stub([plan]), answer_mode="template")
    return run_dir


def compare_dir(tmp):
    """A real 'rnplens compare' output: target 'same' unchanged; 'corr' with chains relabelled in the after set
    (CORRESPONDENCE_CHANGED); 'lost' with five protein residues removed (no DockQ value after: NEWLY_UNEVALUABLE)."""
    import csv
    import gemmi
    from rnplens import compare, importer
    pred = os.path.join(EX, "reference_based", "7K9D_prediction.pdb")
    ref = os.path.join(EX, "reference_based", "7K9D_reference.cif")
    ps, rs = importer.read_sequence_arg(PROT_FASTA), importer.read_sequence_arg(RNA_FASTA)
    os.makedirs(str(tmp), exist_ok=True)
    st = gemmi.read_structure(pred)
    for i in range(4, -1, -1):
        del st[0]["A"][i]
    trunc = os.path.join(str(tmp), "trunc.pdb"); st.write_pdb(trunc)
    st = gemmi.read_structure(pred)
    st[0]["A"].name = "P"; st[0]["B"].name = "R"
    relab = os.path.join(str(tmp), "relabel.pdb"); st.write_pdb(relab)
    for name, rows in (("before", [["same", pred], ["corr", pred], ["lost", pred]]),
                       ("after", [["same", pred], ["corr", relab], ["lost", trunc]])):
        with open(os.path.join(str(tmp), name + ".tsv"), "w", newline="") as fh:
            w = csv.writer(fh, delimiter="\t"); w.writerow(["target_id", "prediction", "protein_sequence", "rna_sequence"])
            w.writerows([[t, p, ps, rs] for t, p in rows])
    with open(os.path.join(str(tmp), "refs.tsv"), "w") as fh:
        fh.write("target_id\treference\nsame\t%s\ncorr\t%s\nlost\t%s\n" % (ref, ref, ref))
    out = os.path.join(str(tmp), "cmp")
    assert compare.run(os.path.join(str(tmp), "before.tsv"), os.path.join(str(tmp), "after.tsv"),
                       os.path.join(str(tmp), "refs.tsv"), out, jobs=2) == 0
    return out
