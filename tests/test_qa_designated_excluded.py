"""QA install-science fix round O4: when the engine-designated structure of a run was excluded at import, every place
that reports the designated structure says so explicitly (import output, manifest run rows, analyse summary.json and
summary.html, rnplens explain structures)."""
import json
import os
import shutil
import subprocess
import sys

from rnplens import importer

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
PF = os.path.join(EX, "reference_based", "7K9D_protein.fasta")
RF = os.path.join(EX, "reference_based", "7K9D_rna.fasta")
RUN_A = os.path.join(EX, "reference_free", "report_7K9D", "exec_A")
RUN_B = os.path.join(EX, "reference_free", "report_7K9D", "exec_B")


def _project(tmp_path):
    """exec_D = byte copy of exec_A: its only structure is a DUPLICATE and also the run's designated structure."""
    a, b, dd = tmp_path / "in" / "exec_A", tmp_path / "in" / "exec_B", tmp_path / "in" / "exec_D"
    shutil.copytree(RUN_A, a); shutil.copytree(RUN_B, b); shutil.copytree(RUN_A, dd)
    return [a, b, dd]


def test_excluded_designated_structure_is_said_to_be_excluded(tmp_path, capsys):
    ins = _project(tmp_path)
    P = tmp_path / "p"
    assert importer.main([str(x) for x in ins] + ["--protein-seq", PF, "--rna-seq", RF, "--engine", "BOLTZ2", "--out", str(P)]) == 0
    out = capsys.readouterr().out
    m = json.load(open(P / "manifest.json"))
    row = next(r for r in m["runs"] if r["run"].endswith("exec_D"))
    assert row["designated_execution"] and row["designated_included"] is False and row["designated_verdict"] == "DUPLICATE"
    assert "excluded at import" in row["designated_note"] and "not analysed" in row["designated_note"]
    ok = next(r for r in m["runs"] if r["run"].endswith("exec_A"))
    assert ok["designated_included"] is True and ok.get("designated_note") is None
    line = next(l for l in out.splitlines() if l.strip().startswith("run ") and "exec_D" in l)
    assert "EXCLUDED at import" in line and "DUPLICATE" in line
    env = dict(os.environ, MPLBACKEND="Agg")
    r = subprocess.run([sys.executable, "-m", "rnplens", "analyse", str(P), "--out", str(tmp_path / "a")], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    S = json.load(open(tmp_path / "a" / "summary.json"))
    srow = next(x for x in S["inventory"]["runs"] if x["run"].endswith("exec_D"))
    assert srow["designated_included"] is False
    html = open(tmp_path / "a" / "summary.html").read()
    assert "excluded at import (DUPLICATE)" in html
    e = subprocess.run([sys.executable, "-m", "rnplens", "explain", "structures", "--analysis", str(tmp_path / "a"), "--project", str(P),
                        "--no-write"], capture_output=True, text=True, env=env)
    assert e.returncode == 0, e.stderr
    eline = next(l for l in e.stdout.splitlines() if "exec_D" in l and "engine-designated structure" in l)
    assert "excluded at import (DUPLICATE)" in eline


def test_designation_note_also_for_manifests_without_the_new_fields(tmp_path):
    """Projects imported before this change: the exclusion is derived from the structures list."""
    ins = _project(tmp_path)
    P = tmp_path / "p"
    assert importer.run([str(x) for x in ins], importer.read_sequence_arg(PF), importer.read_sequence_arg(RF), str(P), engine="BOLTZ2") == 0
    m = json.load(open(P / "manifest.json"))
    for r in m["runs"]:
        for k in ("designated_included", "designated_verdict", "designated_note"):
            r.pop(k, None)
    row = next(r for r in m["runs"] if r["run"].endswith("exec_D"))
    note = importer.designated_exclusion(m, row)
    assert note and "excluded at import (DUPLICATE" in note
