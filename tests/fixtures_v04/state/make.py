"""Fixture builders for the project-state tests (Project-state track).

Every fixture is generated under the test's tmp_path from the bundled 7K9D example (two Boltz-2 runs); nothing
binary is stored here. Builders never modify the bundled example.
"""
import json
import os
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EX = os.path.join(REPO, "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")
PROTEIN_FASTA = os.path.join(EX, "reference_based", "7K9D_protein.fasta")
RNA_FASTA = os.path.join(EX, "reference_based", "7K9D_rna.fasta")
MODEL = "7K9D_model_0.pdb"
CONF = "confidence_7K9D_model_0.json"


def sequences():
    from rnplens import importer
    return importer.read_sequence_arg(PROTEIN_FASTA), importer.read_sequence_arg(RNA_FASTA)


def copy_run(src_run, dst, sample=0, remark=None):
    """A run folder holding the example structure of ``src_run`` as Boltz-2 flat sample ``sample``."""
    os.makedirs(dst, exist_ok=True)
    m = os.path.join(dst, "7K9D_model_%d.pdb" % sample)
    shutil.copy(os.path.join(RF, src_run, MODEL), m)
    shutil.copy(os.path.join(RF, src_run, CONF), os.path.join(dst, "confidence_7K9D_model_%d.json" % sample))
    if remark:
        with open(m, "a") as fh:
            fh.write("REMARK %s\n" % remark)
    return m


def two_runs(base):
    """base/exec_A, base/exec_B: byte copies of the example runs."""
    return [os.path.dirname(copy_run("exec_A", os.path.join(base, "exec_A"))),
            os.path.dirname(copy_run("exec_B", os.path.join(base, "exec_B")))]


def third_run(base, name="exec_C"):
    """A new run built from a copy of exec_B content, as a different sample (model_1), with distinct bytes."""
    return os.path.dirname(copy_run("exec_B", os.path.join(base, name), sample=1, remark="copy of exec_B as a new run"))


def _edit(path, fn):
    import gemmi
    st = gemmi.read_structure(path)
    fn(st)
    st.write_pdb(path)


def shift_chain(path, chain, dx):
    """Translate one chain (changes the coordinates and so the contacts)."""
    import gemmi

    def f(st):
        for ch in st[0]:
            if ch.name == chain:
                for r in ch:
                    for a in r:
                        a.pos = gemmi.Position(a.pos.x + dx, a.pos.y, a.pos.z)
    _edit(path, f)


def truncate_rna(path, n=1):
    """Remove the last n nucleotides of chain B (a different RNA construct)."""
    def f(st):
        for ch in st[0]:
            if ch.name == "B":
                for _ in range(n):
                    del ch[len(ch) - 1]
    _edit(path, f)


def duplicate_protein_chain(path, new="C", dx=80.0):
    """Add a copy of protein chain A as chain ``new``, far away: two chains match the protein construct."""
    import gemmi

    def f(st):
        m = st[0]
        m.add_chain(m.find_chain("A"))
        c = m[len(m) - 1]
        c.name = new
        for r in c:
            for at in r:
                at.pos = gemmi.Position(at.pos.x + dx, at.pos.y, at.pos.z)
        st.setup_entities()
    _edit(path, f)


def renumber_protein(path, offset=10):
    """Shift chain A residue numbers (the importer then asks to accept a derived copy)."""
    import gemmi

    def f(st):
        for ch in st[0]:
            if ch.name == "A":
                for r in ch:
                    r.seqid = gemmi.SeqId(r.seqid.num + offset, " ")
    _edit(path, f)


def set_score(run_dir, sample, score, name=None):
    p = os.path.join(run_dir, name or "confidence_7K9D_model_%d.json" % sample)
    c = json.load(open(os.path.join(run_dir, "confidence_7K9D_model_%d.json" % sample)))
    c["confidence_score"] = score
    with open(p, "w") as fh:
        json.dump(c, fh)


def two_sample_run(base, name="exec_M", extra_confidence=True, tie=False):
    """One run with two samples (exec_A and exec_B content); optionally a second confidence file for sample 0
    (ambiguous designation) or equal confidence scores (a tie)."""
    d = os.path.join(base, name)
    copy_run("exec_A", d, sample=0)
    copy_run("exec_B", d, sample=1)
    if tie:
        set_score(d, 0, 0.5); set_score(d, 1, 0.5)
    if extra_confidence:
        set_score(d, 0, 0.1, name="confidence_7K9D_model_0_rerun.json")
    return d
