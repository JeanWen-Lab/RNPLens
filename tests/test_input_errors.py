"""0.4 usability (owner programme 2026-10-18, section 6): a missing or invalid input gives a controlled refusal, not a
traceback, and nothing is run or written; a missing required package gives installation guidance.

The cases are the ones that ended in a Python traceback (or exited 0 after silently ignoring a missing path) at the RC
head b8d1362 (records: rc/out/U/u1/U1.json).
"""
import os
import subprocess
import sys

import pytest

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")
PS = os.path.join(EX, "reference_based", "7K9D_protein.fasta")
RS = os.path.join(EX, "reference_based", "7K9D_rna.fasta")


def rn(args, cwd):
    return subprocess.run([sys.executable, "-m", "rnplens"] + [str(a) for a in args], cwd=str(cwd), capture_output=True,
                          text=True, timeout=600, env=dict(os.environ, MPLBACKEND="Agg"))


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    d = tmp_path_factory.mktemp("inerr")
    assert rn(["import", RF + "/exec_A", "--protein-seq", PS, "--rna-seq", RS, "--engine", "BOLTZ2", "--case-id", "7K9D_e",
               "--out", d / "p"], d).returncode == 0
    assert rn(["analyse", d / "p", "--out", d / "a"], d).returncode == 0
    return d


CASES = {  # id: (argv with NX = missing path, F = a non-JSON file, E = an empty folder, O = an output path)
    "evaluate_run_input_missing": ["evaluate", "run", "--input", "NX", "--out", "O"],
    "evaluate_run_prediction_missing": ["evaluate", "run", "--prediction", "NX", "--reference", "NX", "--protein-seq", PS,
                                        "--rna-seq", RS, "--target-id", "T", "--out", "O"],
    "evaluate_validate_input_missing": ["evaluate", "validate", "--input", "NX"],
    "report_run_contract_missing": ["report", "run", "NX", "--outdir", "O"],
    "report_run_contract_not_json": ["report", "run", "F", "--outdir", "O"],
    "report_validate_contract_missing": ["report", "validate", "NX"],
    "report_validate_contract_is_folder": ["report", "validate", "E"],
    "analyse_project_missing": ["analyse", "NX", "--out", "O"],
    "analyse_project_is_file": ["analyse", "F", "--out", "O"],
    "analyse_project_empty_folder": ["analyse", "E", "--out", "O"],
    "analyse_reference_missing": ["analyse", "P", "--out", "O", "--reference", "NX"],
    "compare_tables_missing": ["compare", "--before", "NX", "--after", "NX", "--references", "NX", "--out", "O"],
    "compare_tables_are_folders": ["compare", "--before", "E", "--after", "E", "--references", "E", "--out", "O"],
    "example_contract_folder_missing": ["example-contract", "NX", "--out", "O"],
    "export_methods_project_missing": ["export-methods", "A", "--project", "NX", "--out", "O"],
    "import_sequence_file_missing": ["import", RF + "/exec_A", "--protein-seq", "NX.fasta", "--rna-seq", RS, "--out", "O"],
    "update_reference_missing": ["update", "O", "--init", RF + "/exec_A", "--protein-seq", PS, "--rna-seq", RS, "--reference", "NX"],
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_controlled_refusal(case, project, tmp_path):
    (tmp_path / "f.txt").write_text("not json\n")
    (tmp_path / "empty").mkdir()
    sub = {"NX": str(tmp_path / "does" / "not" / "exist"), "NX.fasta": str(tmp_path / "nope" / "protein.fasta"),
           "F": str(tmp_path / "f.txt"), "E": str(tmp_path / "empty"), "O": str(tmp_path / "out"),
           "P": str(project / "p"), "A": str(project / "a")}
    r = rn([sub.get(a, a) for a in CASES[case]], tmp_path)
    assert "Traceback" not in r.stderr + r.stdout, r.stderr[-1500:]
    assert r.returncode == 2, (r.returncode, r.stderr[-800:])
    assert "refused" in r.stderr
    assert not (tmp_path / "out").exists()


def test_missing_required_package_gives_install_guidance(tmp_path):
    code = ("import sys; sys.modules['gemmi'] = None; sys.modules['numpy'] = None; from rnplens.cli import main; "
            "sys.exit(main(sys.argv[1:]))")
    for args in (["--version"], ["report", "validate", "x.json"], ["import", "x", "--protein-seq", "A", "--rna-seq", "A", "--out", "o"]):
        r = subprocess.run([sys.executable, "-c", code] + args, cwd=str(tmp_path), capture_output=True, text=True, timeout=120)
        assert r.returncode == 3 and "Traceback" not in r.stderr, (args, r.stderr[-800:])
        assert "gemmi (qualified 0.6.5)" in r.stderr and "numpy (qualified 1.26.4)" in r.stderr
        assert "python -m pip install 'gemmi==0.6.5' 'numpy==1.26.4'" in r.stderr and "rnplens doctor" in r.stderr
    assert not os.listdir(tmp_path)
