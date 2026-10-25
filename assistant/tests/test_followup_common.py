"""Shared helpers for the follow-up tests (no tests here): the bundled 7K9D example imported with two runs and analysed."""
import contextlib
import io
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EX = os.path.join(ROOT, "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")
PS = os.path.join(EX, "reference_based", "7K9D_protein.fasta")
RS = os.path.join(EX, "reference_based", "7K9D_rna.fasta")


def make_project(base, region=True):
    from rnplens import assist, cli
    P, A = os.path.join(base, "p"), os.path.join(base, "a")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assert cli.main(["import", os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B"), "--protein-seq", PS, "--rna-seq", RS,
                         "--out", P, "--case-id", "m", "--engine", "BOLTZ2"]) == 0
        assert assist.main(["--project", P, "--analysis", A, "--item", "A", "--json"], out=lambda *x: None) == 0
        if region:
            assert assist.main(["--project", P, "--analysis", A, "--item", "C", "--rna", "13-23", "--runs", "exec_A,exec_B", "--json"],
                               out=lambda *x: None) == 0
    return P, A


def clone(src_base, dst_base):
    shutil.copytree(src_base, dst_base)
    return os.path.join(dst_base, "p"), os.path.join(dst_base, "a")
