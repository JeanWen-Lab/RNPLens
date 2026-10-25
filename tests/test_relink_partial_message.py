"""rnplens relink: a partially successful relink records its verified mappings and must say so (QA workflow-replay,
2026-10-17). Before the fix the refusal printed 'nothing was written' after .rnplens/relink.json had been written."""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures_v04", "region"))
import builders as B  # noqa: E402
from rnplens import portability as PT  # noqa: E402


def rn(*a):
    return subprocess.run([sys.executable, "-m", "rnplens"] + [str(x) for x in a], capture_output=True, text=True)


def test_partial_relink_reports_the_mappings_it_recorded(tmp_path):
    inp = tmp_path / "orig" / "in"
    B.place(str(inp / "exec_A"), B.EXEC_A, 0, .5)
    B.place(str(inp / "exec_A"), B.diag(1), 1, .3)
    B.place(str(inp / "exec_B"), B.EXEC_B, 0, .5)
    B.place(str(inp / "exec_B"), B.diag(2), 1, .2)
    proj = tmp_path / "orig" / "project"
    r = rn("update", proj, "--init", inp / "exec_A", inp / "exec_B", "--protein-seq", B.PROT_FASTA, "--rna-seq",
           B.RNA_FASTA, "--engine", "BOLTZ2", "--case-id", "relink_message")
    assert r.returncode == 0, r.stdout + r.stderr
    copy, dry = tmp_path / "copy" / "project", tmp_path / "dry" / "project"
    shutil.copytree(proj, copy)
    shutil.copytree(proj, dry)
    search = tmp_path / "search"
    shutil.copytree(inp, search / "in")
    os.unlink(search / "in" / "exec_B" / "7K9D_model_1.pdb")           # one required structure cannot be found
    shutil.move(str(tmp_path / "orig"), str(tmp_path / "orig.away"))
    r = rn("relink", dry, "--search", search, "--dry-run")
    assert r.returncode == PT.EXIT_PORTABILITY and not os.path.exists(dry / PT.RELINK_REL)
    assert "nothing was written" in r.stderr                             # true for a dry run
    r = rn("relink", copy, "--search", search)
    assert r.returncode == PT.EXIT_PORTABILITY, r.stdout + r.stderr
    rj = json.load(open(copy / PT.RELINK_REL))
    assert rj["files"]                                                   # verified mappings were recorded ...
    assert "nothing was written" not in r.stderr, r.stderr               # ... so the refusal must not deny it
    assert PT.RELINK_REL in r.stderr and "%d verified" % len(rj["files"]) in r.stderr

