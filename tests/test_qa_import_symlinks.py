"""QA agent-security regression: symbolic links inside an allowed run folder are never followed silently.
Before the fix the assistant's import tool checked only the folder argument (realpath), so a file symlink inside a run
folder that pointed outside the task was followed and INCLUDED; rnplens import read linked files without a word."""
import contextlib
import io
import json
import os

import pytest

from rnplens import cli
from rnplens_assistant import tools as T

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RF = os.path.join(ROOT, "examples", "reference_free", "report_7K9D")
PS = os.path.join(ROOT, "examples", "reference_based", "7K9D_protein.fasta")
RS = os.path.join(ROOT, "examples", "reference_based", "7K9D_rna.fasta")


def _task(tmp):
    t = tmp / "task"
    (t / "run_E").mkdir(parents=True)
    (t / "run_E" / "m_0.pdb").write_text("END\n")
    (t / "protein.fasta").write_text(">p\nMKV\n"); (t / "rna.fasta").write_text(">r\nGGA\n")
    (tmp / "outside.pdb").write_text("END\n")
    return t


def test_assistant_import_refuses_a_link_out_of_the_task(tmp_path, monkeypatch):
    t = _task(tmp_path)
    os.symlink(str(tmp_path / "outside.pdb"), str(t / "run_E" / "m_9.pdb"))
    monkeypatch.setattr(T, "_rn", lambda *a, **k: pytest.fail("rnplens import must not run"))
    ws = T.Workspace(str(t), str(tmp_path / "run"))
    status, res, recs = T.call(ws, "import_predictions", {"project_id": "project_1", "folders": ["run_E"], "protein_fasta": "protein.fasta",
                                                          "rna_fasta": "rna.fasta", "engine": "BOLTZ2", "accept_offsets": False, "resolve": None})
    assert status == "ACCESS_REFUSED" and "run_E/m_9.pdb" in res["error"] and recs[0]["state"] == "ACCESS_REFUSED"


def test_assistant_import_reports_a_link_inside_the_task(tmp_path, monkeypatch):
    t = _task(tmp_path)
    os.symlink(str(t / "run_E" / "m_0.pdb"), str(t / "run_E" / "m_1.pdb"))

    def fake_rn(ws, args, log):
        out = args[args.index("--out") + 1]; os.makedirs(out)
        json.dump({"counts": {"included": 1, "found": 2, "excluded": 1, "unrecognised": 0}, "construct": {"protein_length": 3, "rna_length": 3},
                   "runs": [], "structures": [], "unrecognised_files": []}, open(os.path.join(out, "manifest.json"), "w"))
        return 0, "", ""
    monkeypatch.setattr(T, "_rn", fake_rn)
    ws = T.Workspace(str(t), str(tmp_path / "run"))
    status, res, recs = T.call(ws, "import_predictions", {"project_id": "project_1", "folders": ["run_E"], "protein_fasta": "protein.fasta",
                                                          "rna_fasta": "rna.fasta", "engine": "BOLTZ2", "accept_offsets": False, "resolve": None})
    assert status == "OK" and res["symbolic_links_inside_task"] == ["run_E/m_1.pdb"]
    assert any(r["field"] == "symbolic_links" and r["value"] == 1 for r in recs)


def test_toolkit_import_reports_linked_files(tmp_path):
    link = tmp_path / "exec_A_link"
    os.symlink(os.path.join(RF, "exec_A"), str(link))
    out = tmp_path / "P"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        assert cli.main(["import", str(link), "--protein-seq", PS, "--rna-seq", RS, "--out", str(out), "--engine", "BOLTZ2"]) == 0
    man = json.load(open(out / "manifest.json"))
    assert man["symlinked_files"] and all(x["target"].startswith(os.path.realpath(RF)) for x in man["symlinked_files"])
    assert "read through a symbolic link" in buf.getvalue()


def test_toolkit_import_without_links_is_unchanged(tmp_path):
    out = tmp_path / "P"
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assert cli.main(["import", os.path.join(RF, "exec_A"), "--protein-seq", PS, "--rna-seq", RS, "--out", str(out), "--engine", "BOLTZ2"]) == 0
    assert "symlinked_files" not in json.load(open(out / "manifest.json"))
