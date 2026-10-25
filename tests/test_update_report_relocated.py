"""Before/after report of a relocated managed project (QA workflow-replay, 2026-10-17): a project copied without its
inputs and relinked to verified copies has the same structures with the same bytes; the update report must not list
them as removed and added. Before the fix structures were keyed by the absolute path the import recorded."""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures_v04", "region"))
import builders as B  # noqa: E402
from rnplens import state as S  # noqa: E402


def rn(*a):
    return subprocess.run([sys.executable, "-m", "rnplens"] + [str(x) for x in a], capture_output=True, text=True)


def _report(project):
    v = S.Project(str(project)).head()["version"]
    return json.load(open(os.path.join(str(project), "analyses", v, "update_report.json")))


def test_relinked_project_report_has_no_spurious_added_or_removed_structures(tmp_path):
    inp = tmp_path / "orig" / "in"
    B.place(str(inp / "exec_A"), B.EXEC_A, 0, .5)
    B.place(str(inp / "exec_A"), B.diag(1), 1, .3)
    B.place(str(inp / "exec_B"), B.EXEC_B, 0, .5)
    proj = tmp_path / "orig" / "project"
    r = rn("update", proj, "--init", inp / "exec_A", inp / "exec_B", "--protein-seq", B.PROT_FASTA, "--rna-seq",
           B.RNA_FASTA, "--engine", "BOLTZ2", "--case-id", "relocated_report")
    assert r.returncode == 0, r.stdout + r.stderr
    copy = tmp_path / "copy" / "project"
    shutil.copytree(proj, copy)
    shutil.copytree(inp, tmp_path / "elsewhere" / "in")
    shutil.move(str(tmp_path / "orig"), str(tmp_path / "orig.away"))
    r = rn("relink", copy, "--search", tmp_path / "elsewhere")
    assert r.returncode == 0, r.stdout + r.stderr
    r = rn("update", copy)
    assert r.returncode == 0, r.stdout + r.stderr
    rep = _report(copy)
    files = rep["i_candidate_composition"]["input_files"]
    assert files["changed"] == [] and files["new"] == [] and files["removed"] == [] and files["moved"]
    g = rep["i_candidate_composition"]["groups"]["main"]
    assert g["included_before"] == g["included_after"] == 3
    assert g["added"] == [] and g["removed"] == [] and g["changed"] == [], g
    # a real content change at the new location is still reported as changed, not as added and removed
    p = tmp_path / "elsewhere" / "in" / "exec_A" / "7K9D_model_1.pdb"
    L = open(p).read().split("\n")
    i = next(i for i, l in enumerate(L) if l.startswith("ATOM"))
    L[i] = L[i][:30] + "%8.3f" % (float(L[i][30:38]) + 0.01) + L[i][38:]
    open(p, "w").write("\n".join(L))
    r = rn("update", copy)
    assert r.returncode == 0, r.stdout + r.stderr
    g = _report(copy)["i_candidate_composition"]["groups"]["main"]
    assert g["added"] == [] and g["removed"] == [] and g["changed"] == ["exec_A#7K9D_model_1"], g

