"""QA install-science D1: a nonexistent input path given to `rnplens import` is an input error (exit 2, message,
nothing written), not an uncaught FileNotFoundError traceback (exit 1). Documented exit codes: docs/capabilities.md
("2 an input error")."""
import os

from rnplens import importer

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
PF = os.path.join(EX, "reference_based", "7K9D_protein.fasta")
RF = os.path.join(EX, "reference_based", "7K9D_rna.fasta")
RUN_A = os.path.join(EX, "reference_free", "report_7K9D", "exec_A")


def test_nonexistent_input_path_is_an_input_error(tmp_path, capsys):
    out = tmp_path / "p"
    rc = importer.main([str(tmp_path / "does_not_exist"), "--protein-seq", PF, "--rna-seq", RF, "--out", str(out)])
    err = capsys.readouterr().err
    assert rc == importer.EXIT_REFUSED == 2
    assert "does_not_exist" in err and "not found" in err
    assert not out.exists()


def test_one_missing_path_among_valid_ones_writes_nothing(tmp_path, capsys):
    out = tmp_path / "p"
    rc = importer.main([RUN_A, str(tmp_path / "missing_run"), "--protein-seq", PF, "--rna-seq", RF, "--engine", "BOLTZ2",
                        "--out", str(out)])
    assert rc == 2 and not out.exists()
    assert "missing_run" in capsys.readouterr().err
