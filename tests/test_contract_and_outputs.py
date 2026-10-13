import csv, json, os
import pytest
from rnpbench_evaluate import contract, report, selftest
from rnpbench_evaluate.cli import main

SRC = json.load(open(os.path.join(selftest.FIX, "fixture_sources.json")))


def _inp(**over):
    d = selftest.fixture_input(selftest.FIX, "ordinary", SRC["ordinary"])
    for k, v in over.items():
        d[k] = v
    return d


@pytest.mark.parametrize("mutate,msg", [
    (lambda d: d.update(contract="X"), "contract must be"),
    (lambda d: d["construct"].update(rna_sequence=""), "both required"),
    (lambda d: d["construct"].update(rna_sequence="ACGT"), "A, C, G, U"),
    (lambda d: d["prediction"].update(path="/nonexistent.pdb"), "not found"),
    (lambda d: d["prediction"].update(sha256="0" * 64), "sha256 does not match"),
    (lambda d: d.update(target_id="bad id!"), "target_id"),
])
def test_contract_refuses(mutate, msg):
    d = _inp(); mutate(d)
    with pytest.raises(contract.ContractError, match=msg):
        contract.load(d, base_dir=selftest.FIX)


def test_cli_evaluate_writes_outputs_and_refuses_overwrite(tmp_path):
    d = _inp(); p = tmp_path / "in.json"; p.write_text(json.dumps(d))
    out = tmp_path / "out"
    assert main(["evaluate", "--input", str(p), "--out", str(out)]) == 0
    r = json.load(open(out / "result.json"))
    assert r["dockq"]["dockq"] == SRC["ordinary"]["released_row"]["dockq"]
    row = next(csv.DictReader(open(out / "result.csv")))
    assert row["dockq_status"] == "SCORED" and float(row["dockq"]) == r["dockq"]["dockq"]
    assert main(["evaluate", "--input", str(p), "--out", str(out)]) == 2   # never overwrites


def test_csv_marks_no_value_explicitly(tmp_path):
    _, res = selftest.run(verbose=False, profile_name="portable")
    report.write(res["control_protein_residues_all_ALA"], str(tmp_path / "nv"))
    row = next(csv.DictReader(open(tmp_path / "nv" / "result.csv")))
    assert row["dockq"] == "NO_VALUE" and row["dockq_status"] == "NO_VALUE"
    assert "NO VALUE (not zero)" in open(tmp_path / "nv" / "summary.txt").read()


def test_frozen_sources_pinned():
    from rnpbench_evaluate import frozen_loader
    man = frozen_loader.verify_sources()
    assert len(man["files"]) == 8


def test_workdir_is_honoured(tmp_path):
    d = _inp(); p = tmp_path / "in.json"; p.write_text(json.dumps(d)); wd = tmp_path / "wd"; wd.mkdir()
    assert main(["evaluate", "--input", str(p), "--out", str(tmp_path / "o"), "--workdir", str(wd)]) == 0
    assert list(wd.iterdir()) == []   # staging is cleaned up inside the chosen directory
