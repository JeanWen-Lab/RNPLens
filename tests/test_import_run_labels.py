"""Import must keep distinct engine runs apart and never write two structures under one run#sample label.

QA track outside-user-viewer (2026-10-17): two Boltz-2 output folders written into one --out_dir
(`boltz predict A.yaml --out_dir runs` and `boltz predict A_rep2.yaml --out_dir runs` give
runs/boltz_results_A and runs/boltz_results_A_rep2) were merged into one run named after the parent folder; both
model_0 files got the label `runs#0`, only one designated structure was kept, and the report contract written by
import was refused by Report ("duplicates engine/execution"), while import itself reported success.
"""
import json
import os
import shutil

import gemmi
import pytest

from rnplens import importer

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
PRED = os.path.join(EX, "reference_based", "7K9D_prediction.pdb")
PS = importer.read_sequence_arg(os.path.join(EX, "reference_based", "7K9D_protein.fasta"))
RS = importer.read_sequence_arg(os.path.join(EX, "reference_based", "7K9D_rna.fasta"))


def _imp(paths, out, **kw):
    return importer.run([str(p) for p in paths], PS, RS, str(out), **kw)


def _boltz(parent, stem, n, tag):
    d = parent / ("boltz_results_%s" % stem) / "predictions" / stem
    d.mkdir(parents=True)
    for k in range(n):
        f = d / ("%s_model_%d.pdb" % (stem, k))
        shutil.copy(PRED, f)
        with open(f, "a") as fh:
            fh.write("REMARK %s distinct copy %d\n" % (tag, k))
        json.dump({"confidence_score": 0.9 - 0.1 * k}, open(d / ("confidence_%s_model_%d.json" % (stem, k)), "w"))
    return parent / ("boltz_results_%s" % stem)


def _labels(out):
    m = json.load(open(os.path.join(out, "manifest.json")))
    c = json.load(open(os.path.join(out, "report_contract.json")))
    return m, [(o["engine"], o["execution"]) for o in c["outputs"]]


@pytest.mark.parametrize("as_parent", [True, False])
def test_two_boltz_results_folders_in_one_parent_are_two_runs(tmp_path, as_parent):
    runs = tmp_path / "runs"
    a = _boltz(runs, "X", 2, "a")
    b = _boltz(runs, "X_rep2", 2, "b")
    out = tmp_path / "p"
    assert _imp([runs] if as_parent else [a, b], out) == 0
    m, labels = _labels(out)
    assert len(labels) == 4 and len(set(labels)) == 4, labels
    assert sorted(r["run"] for r in m["runs"]) == ["boltz_results_X", "boltz_results_X_rep2"]
    assert all(r["n_structures"] == 2 and r["designated_execution"] for r in m["runs"])
    assert sum(s["designated"] for s in m["structures"]) == 2


def test_one_boltz_results_folder_per_parent_keeps_parent_run_names(tmp_path):
    _boltz(tmp_path / "in" / "exec_A", "X", 2, "a")
    _boltz(tmp_path / "in" / "exec_B", "X", 2, "b")
    assert _imp([tmp_path / "in" / "exec_A", tmp_path / "in" / "exec_B"], tmp_path / "p") == 0
    m, labels = _labels(tmp_path / "p")
    assert sorted(r["run"] for r in m["runs"]) == ["exec_A", "exec_B"]
    assert sorted(x for _, x in labels) == ["exec_A#0", "exec_A#1", "exec_B#0", "exec_B#1"]
    _boltz(tmp_path / "solo", "Y", 2, "c")
    assert _imp([tmp_path / "solo" / "boltz_results_Y"], tmp_path / "q") == 0
    assert [r["run"] for r in json.load(open(tmp_path / "q" / "manifest.json"))["runs"]] == ["solo"]


def test_clashing_run_sample_labels_are_refused_and_nothing_written(tmp_path, capsys):
    d = tmp_path / "flat"
    d.mkdir()
    shutil.copy(PRED, d / "m.pdb")
    st = gemmi.read_structure(PRED)          # the same model also written as mmCIF: same stem, so the generic
    st.setup_entities()                      # layout gives both files the label flat#m
    st.make_mmcif_document().write_file(str(d / "m.cif"))
    out = tmp_path / "p"
    assert _imp([d], out, engine="OTHER") == 2
    assert not out.exists()
    err = capsys.readouterr().err
    assert "same run and sample label" in err and "m.pdb" in err and "m.cif" in err
