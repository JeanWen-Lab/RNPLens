"""Owner decision 2026-10-18 (C7-11): an edited input file is a new input version, not a relocation of the old file.

- identical content moved -> `rnplens relink` accepts it (SHA-256 verified);
- changed content -> `rnplens relink` refuses (exit 6) and names the existing continuation exactly:
  `rnplens update PROJECT NEW_FOLDER --remove-input OLD_FOLDER`;
- running that command records the edited structure as a new project version; every file of the earlier versions
  (state, imports, analyses, manifests, provenance) stays byte-identical;
- an in-place edit is analysed as a new version by `rnplens update PROJECT`; the earlier import's commands refuse
  the changed file (MISMATCH) and name `rnplens update`.
Uses the bundled 7K9D example (a development target).
"""
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys

import pytest

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")
VOLATILE = {".rnplens/HEAD", ".rnplens/run/projection_index.json"}   # head pointer and run sidecar (by design)


def rn(*args):
    p = subprocess.run([sys.executable, "-m", "rnplens"] + [str(a) for a in args], capture_output=True, text=True,
                       timeout=900, env=dict(os.environ, MPLBACKEND="Agg"))
    return p


def tree(d):
    h = {}
    for dp, dn, fn in os.walk(d):
        for f in fn:
            p = os.path.join(dp, f)
            h[os.path.relpath(p, d)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return h


def unchanged_except_volatile(before, after):
    return sorted(k for k in before if after.get(k) != before[k] and k not in VOLATILE)


def edit(pdb):
    L = open(pdb).read().split("\n")
    i = next(i for i, l in enumerate(L) if l.startswith("ATOM"))
    L[i] = L[i][:30] + "%8.3f" % (float(L[i][30:38]) + 0.1) + L[i][38:]
    open(pdb, "w").write("\n".join(L))


@pytest.fixture(scope="module")
def original(tmp_path_factory):
    A = tmp_path_factory.mktemp("relink_edit") / "A"
    for r in ("exec_A", "exec_B"):
        shutil.copytree(os.path.join(RF, r), str(A / "in" / r))
    for f in ("7K9D_protein.fasta", "7K9D_rna.fasta"):
        shutil.copy(os.path.join(EX, "reference_based", f), str(A / f))
    p = rn("update", A / "proj", "--init", A / "in" / "exec_A", A / "in" / "exec_B", "--protein-seq",
           A / "7K9D_protein.fasta", "--rna-seq", A / "7K9D_rna.fasta", "--engine", "BOLTZ2", "--case-id", "7K9D_relink")
    assert p.returncode == 0, p.stderr[-800:]
    return A


def moved_copy(original, dest, edited):
    """The project and its inputs moved together to dest (inputs in another layout); the originals are hidden."""
    shutil.copytree(str(original / "proj"), str(dest / "proj"))
    shutil.copytree(str(original / "in"), str(dest / "moved" / "inputs"))
    if edited:
        edit(str(dest / "moved" / "inputs" / "exec_A" / "7K9D_model_0.pdb"))
    return dest


@contextlib.contextmanager
def hidden(original):
    """The recorded originals are no longer at their recorded paths (restored afterwards for the other tests)."""
    os.rename(str(original / "in"), str(original / "in.hidden"))
    try:
        yield
    finally:
        os.rename(str(original / "in.hidden"), str(original / "in"))


def test_identical_content_moved_is_relinked(original, tmp_path):
    B = moved_copy(original, tmp_path, edited=False)
    with hidden(original):
        before = tree(B / "proj")
        p = rn("relink", B / "proj", "--search", B / "moved" / "inputs")
        assert p.returncode == 0, p.stderr[-800:]
        assert "still unresolved" in p.stdout and " 0 required file(s) still unresolved" in p.stdout
        after = tree(B / "proj")
        assert unchanged_except_volatile(before, after) == [] and set(after) - set(before) == {".rnplens/relink.json"}
        p = rn("update", B / "proj")
        assert p.returncode == 0, p.stderr[-800:]
        assert unchanged_except_volatile(before, tree(B / "proj")) == []


def test_changed_content_is_refused_and_update_continues_as_new_version(original, tmp_path):
    C = moved_copy(original, tmp_path, edited=True)
    with hidden(original):
        before = tree(C / "proj")
        p = rn("relink", C / "proj", "--search", C / "moved" / "inputs")
        assert p.returncode == 6
        new, old = str(C / "moved" / "inputs" / "exec_A"), str(C / "in" / "exec_A")
        cmd = "rnplens update %s %s --remove-input %s" % (C / "proj", new, old)
        assert "edited: %s" % os.path.join(new, "7K9D_model_0.pdb") in p.stderr
        assert "  " + cmd in p.stderr.splitlines(), p.stderr[-1500:]
        rl = json.load(open(str(C / "proj" / ".rnplens" / "relink.json")))
        assert not any(e["path"].endswith(os.path.join("exec_A", "7K9D_model_0.pdb")) for e in rl["files"])  # never relinked
        assert unchanged_except_volatile(before, tree(C / "proj")) == []
        # a plain update is still refused (nothing written) and names the same continuation
        p = rn("update", C / "proj")
        assert p.returncode == 6 and "--remove-input %s" % old in p.stderr and "NEW_FOLDER" in p.stderr
        # the named command: the edited structure becomes a new project version; history byte-identical
        mid = tree(C / "proj")
        p = rn(*cmd.split()[1:])
        assert p.returncode == 0, p.stderr[-800:]
        after = tree(C / "proj")
        assert unchanged_except_volatile(mid, after) == [] and not [k for k in mid if k not in after]
        rep = json.load(open(str(C / "proj" / "analyses" / "v0003" / "update_report.json")))
        comp = rep["i_candidate_composition"]
        assert rep["from_version"] == "v0002" and rep["to_version"] == "v0003"
        assert comp["groups"]["main"]["changed"] == ["exec_A#7K9D_model_0"]
        assert comp["runs"]["new"] == ["../moved/inputs/exec_A"] and comp["runs"]["removed"] == ["../in/exec_A"]
        v = rn("update", C / "proj", "--versions").stdout.split("\n")
        assert [l.split()[:2] for l in v if l][:3] == [["v0001", "INITIALISED"], ["v0002", "COMPLETE"], ["v0003", "COMPLETE"]]


def test_in_place_edit_is_a_new_version_and_old_import_refuses(original, tmp_path):
    D = tmp_path / "D"
    shutil.copytree(str(original), str(D))     # a moved copy of everything; edit in place there
    p = rn("relink", D / "proj", "--map", "%s=%s" % (original, D))
    assert p.returncode == 0, p.stderr[-800:]
    edit(str(D / "in" / "exec_A" / "7K9D_model_0.pdb"))
    before = tree(D / "proj")
    p = rn("region", D / "proj" / "imports" / "v0002" / "main", D / "proj" / "analyses" / "v0002" / "main", "--rna", "20-30")
    assert p.returncode == 6 and "MISMATCH" in p.stderr and "'rnplens update %s'" % (D / "proj") in p.stderr
    p = rn("update", D / "proj")
    assert p.returncode == 0, p.stderr[-800:]
    after = tree(D / "proj")
    assert unchanged_except_volatile(before, after) == [] and not [k for k in before if k not in after]
    rep = json.load(open(str(D / "proj" / "analyses" / "v0003" / "update_report.json")))
    assert rep["i_candidate_composition"]["groups"]["main"]["changed"] == ["exec_A#7K9D_model_0"]
    assert rep["i_candidate_composition"]["input_files"]["changed"] == ["../in/exec_A/7K9D_model_0.pdb"]
