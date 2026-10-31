"""0.4 r3 (owner item 3A): no public RNPLens entry point shows or writes Evaluate's four-axis geometry values.

Inventory and chosen behaviour: records/release/GEOMETRY_BLOCK_INVENTORY.md. The frozen component is unchanged; the
public wrapper (rnplens.geometry_block) publishes filtered output. For every entry point, a geometry value of the
bundled 7K9D fixture must not appear in stdout, stderr or any written file, and the DockQ family (DockQ, DockQ class,
fnat, iRMSD, LRMSD) must be numerically unchanged.
"""
import csv
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys

import pytest

import _blas

from rnplens import geometry_block as GB
from rnplens import importer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(ROOT, "examples")
RB, RF = os.path.join(EX, "reference_based"), os.path.join(EX, "reference_free", "report_7K9D")
EXP = os.path.join(EX, "expected_output", "A_evaluate_7K9D")
REF, PRED = os.path.join(RB, "7K9D_reference.cif"), os.path.join(RB, "7K9D_prediction.pdb")
pytestmark = pytest.mark.skipif(not os.path.isdir(EXP), reason="examples/ not present")
COMPONENT = "import sys; from rnpbench import cli; sys.exit(cli.main(sys.argv[1:]))"

RC3 = json.load(open(os.path.join(EXP, "result.json"))) if os.path.isdir(EXP) else {}
GEO = RC3.get("geometry", {})
VALUE_KEYS = ("prot_internal_ca_rmsd", "rna_internal_c4_rmsd", "rna_placement_c4_rmsd")
COUNT_KEYS = ("n_prot_aligned", "n_prot_native", "n_prot_pose", "n_rna_aligned", "n_rna_native", "n_rna_pose")
# leak signatures: the printed geometry labels, the first 8 decimals of each rc3 value (also matches this platform's
# last-digit variants), a JSON geometry key with a number, a self-test geometry line with a number, and the rc3
# printed lines' value context
PHRASES = ("RNA internal C4' RMSD", "RNA placement C4' RMSD after", "protein internal CA RMSD", "geometry COMPUTED",
           "geometry NO_VALUE")
PREFIXES = tuple(("%.10f" % GEO[k])[:10] for k in VALUE_KEYS if k in GEO)
KEY_RE = re.compile(r'"(%s)"\s*:\s*-?\d' % "|".join(VALUE_KEYS + COUNT_KEYS))
SELFTEST_RE = re.compile(r"geometry\.(?:%s)[^\n]*?\d\.\d{3,}" % "|".join(VALUE_KEYS + COUNT_KEYS))


def leaks(text):
    hits = [p for p in PHRASES + PREFIXES if p in text]
    hits += ["json key %s" % m.group(1) for m in KEY_RE.finditer(text)]
    hits += ["selftest line %r" % m.group(0)[:80] for m in SELFTEST_RE.finditer(text)]
    return hits


def scan_tree(d):
    bad = []
    for root, _, files in os.walk(d):
        for f in files:
            p = os.path.join(root, f)
            t = open(p, "rb").read().decode("utf-8", "ignore")
            for h in leaks(t):
                bad.append((os.path.relpath(p, d), h))
            if f == "result.csv":
                rows = list(csv.DictReader(io.StringIO(t)))
                for r in rows:
                    for c in GB.CSV_VALUE_COLUMNS:
                        if r.get(c):
                            bad.append((os.path.relpath(p, d), "csv %s=%s" % (c, r[c])))
    return bad


def rn(*args, cwd=None):
    return subprocess.run([sys.executable, "-m", "rnplens", *args], capture_output=True, text=True, cwd=cwd,
                          env=dict(os.environ, MPLBACKEND="Agg"))


def test_the_leak_scanner_sees_the_rc3_values():
    """Positive control: the unfiltered rc3 record and summary are detected."""
    assert leaks(open(os.path.join(EXP, "result.json")).read())
    assert leaks(open(os.path.join(EXP, "summary.txt")).read())
    assert len(PREFIXES) == 3


# ---------------------------------------------------------------- the filters
def test_filters_remove_values_and_keep_everything_else():
    f = GB.filter_result_json(RC3)
    assert f["geometry"]["status"] == "BLOCKED" and f["geometry"]["blocked_code"] == GB.CODE
    assert not set(VALUE_KEYS + COUNT_KEYS + ("exclusion", "no_value_note")) & set(f["geometry"])
    assert {k: v for k, v in f.items() if k != "geometry"} == {k: v for k, v in RC3.items() if k != "geometry"}
    assert not leaks(json.dumps(f, indent=1))
    raw = open(os.path.join(EXP, "result.csv"), newline="").read()
    out = GB.filter_result_csv(raw)
    a, b = list(csv.reader(io.StringIO(raw))), list(csv.reader(io.StringIO(out)))
    assert a[0] == b[0]
    for c, (x, y) in enumerate(zip(a[1], b[1])):
        col = a[0][c]
        if col in GB.CSV_VALUE_COLUMNS:
            assert y == ""
        elif col == "geometry_status":
            assert y == "BLOCKED"
        elif col == "geometry_exclusion":
            assert y == GB.CODE
        else:
            assert x == y, col                               # every DockQ-route and input column unchanged
    s = open(os.path.join(EXP, "summary.txt")).read()
    fs = GB.filter_summary_text(s)
    assert not leaks(fs) and GB.SUMMARY_LINE in fs
    kept = [l for l in s.split("\n") if not (l.startswith("Structural geometry") or "C4' RMSD" in l or "CA RMSD" in l)]
    assert all(l in fs.split("\n") for l in kept)
    st = "  public ordinary 7K9D BOLTZ2 DockQ 0.936  geometry COMPUTED  39/39 checks\n  FAIL ordinary geometry.rna_internal_c4_rmsd expected 0.7509466812576658 got 0.7509466812576671\n  FAIL ordinary dockq.dockq_unrounded expected 0.9358969555710455 got 0.9358969575545348"
    fst = GB.filter_selftest_text(st)
    assert not leaks(fst) and "DockQ 0.936" in fst and "0.9358969575545348" in fst and "39/39 checks" in fst


# ---------------------------------------------------------------- rnplens evaluate run (E1-E6)
@pytest.fixture(scope="module")
def public_run(tmp_path_factory):
    t = tmp_path_factory.mktemp("ev")
    wd = t / "workdir"; wd.mkdir()
    r = rn("evaluate", "run", "--input", "example_input.json", "--out", str(t / "pub"), "--workdir", str(wd), cwd=RB)
    c = subprocess.run([sys.executable, "-c", COMPONENT, "evaluate", "run", "--input", "example_input.json", "--out", str(t / "raw")],
                       capture_output=True, text=True, cwd=RB)
    return t, r, c


def test_evaluate_run_shows_and_writes_no_geometry_value(public_run):
    t, r, c = public_run
    assert r.returncode == 0 and c.returncode == 0, r.stderr
    assert leaks(c.stdout) and scan_tree(t / "raw")                     # the component itself still prints them
    assert leaks(r.stdout) == [] and leaks(r.stderr) == []
    assert scan_tree(t / "pub") == []
    assert sorted(os.listdir(t / "pub")) == ["result.csv", "result.json", "rnplens_run.json", "summary.txt"]
    run_note = json.load(open(t / "pub" / "rnplens_run.json"))["note"]
    assert "withheld" in run_note and "BLOCKED" in run_note and "unchanged" not in run_note.split(";")[0]
    assert os.listdir(t / "workdir") == []                               # the private copy was deleted
    g = json.load(open(t / "pub" / "result.json"))["geometry"]
    assert g["status"] == "BLOCKED" and "BLOCKED" in r.stdout and GB.SUMMARY_LINE in r.stdout
    rec = json.load(open(t / "pub" / "result.json"))["rnplens_public_output"]
    assert set(rec["frozen_component_output_sha256_before_filtering"]) == {"result.csv", "result.json", "summary.txt"}


def test_dockq_family_is_unchanged(public_run):
    t, r, c = public_run
    pub, raw = json.load(open(t / "pub" / "result.json")), json.load(open(t / "raw" / "result.json"))
    assert pub["dockq"] == raw["dockq"] and pub["validity"] == raw["validity"]          # the filter never touches DockQ
    pc = list(csv.DictReader(open(t / "pub" / "result.csv"))); rc = list(csv.DictReader(open(t / "raw" / "result.csv")))
    dq = ("dockq_status", "dockq", "dockq_unrounded", "dockq_class", "fnat", "irmsd", "lrmsd", "selected_mapping",
          "n_admissible_candidates", "n_interfaces", "pairs_in_frame", "pairs_out_of_frame", "pairs_indeterminate")
    assert [{k: x[k] for k in dq} for x in pc] == [{k: x[k] for k in dq} for x in rc]
    # against the rc3 expected outputs: rounded values, class, mapping and counts exact; unrounded values within the
    # frozen portable profile (bit-exact where a reference OpenBLAS kernel is in use; tests/_blas.py)
    e, g = RC3["dockq"], pub["dockq"]
    for k in ("status", "dockq", "dockq_class", "selected_mapping"):
        assert g.get(k) == e.get(k), k
    for iface, x in e["per_interface"].items():
        y = g["per_interface"][iface]
        assert y["fnat"] == x["fnat"]
        for k, tol in (("iRMSD", 1e-5), ("LRMSD", 1e-5), ("DockQ", 1e-7)):
            assert abs(y[k] - x[k]) <= tol, (iface, k)
    assert abs(g["dockq_unrounded"] - e["dockq_unrounded"]) <= 1e-7
    if _blas.bit_exact_expected():
        assert g == e
    s = open(t / "pub" / "summary.txt").read()
    assert "DockQ 0.936  [high]   fnat 0.927   iRMSD 0.434 A   LRMSD 1.780 A" in s


def test_evaluate_validate_and_provenance_print_no_geometry():
    for args in (("evaluate", "validate", "--input", "example_input.json"), ("evaluate", "provenance"), ("provenance",),
                 ("--version",), ("evaluate", "run", "--help"), ("evaluate", "--help"), ("--help",)):
        r = rn(*args, cwd=RB)
        assert r.returncode == 0, (args, r.stderr)
        assert leaks(r.stdout + r.stderr) == [], args


def test_selftests_check_geometry_but_do_not_show_it():
    r = rn("selftest")
    assert r.returncode == 0 and "PASS: rnplens selftest" in r.stdout
    assert leaks(r.stdout + r.stderr) == [] and "geometry BLOCKED (checked, not shown)" in r.stdout
    e = rn("evaluate", "selftest")
    c = subprocess.run([sys.executable, "-c", COMPONENT, "evaluate", "selftest"], capture_output=True, text=True)
    assert e.returncode == c.returncode                                  # same verdict as the frozen self-test
    assert leaks(e.stdout + e.stderr) == []


# ---------------------------------------------------------------- workflows over a project (E9-E17)
@pytest.fixture(scope="module")
def analysis(tmp_path_factory):
    t = tmp_path_factory.mktemp("an")
    PS = importer.read_sequence_arg(os.path.join(RB, "7K9D_protein.fasta"))
    RS = importer.read_sequence_arg(os.path.join(RB, "7K9D_rna.fasta"))
    assert importer.run([os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B")], PS, RS, str(t / "p"), "7K9D_example", "BOLTZ2") == 0
    r = rn("analyse", str(t / "p"), "--out", str(t / "a"), "--reference", REF)
    assert r.returncode == 0, r.stderr
    return t, r


def test_analyse_with_reference(analysis):
    t, r = analysis
    assert leaks(r.stdout + r.stderr) == [] and scan_tree(t / "a") == []
    S = json.load(open(t / "a" / "summary.json"))
    assert S["evaluate"] and S["evaluate_withheld"]
    for e in S["evaluate"]:
        res = json.load(open(t / "a" / e["source"]))
        assert res["geometry"]["status"] == "BLOCKED" and e["dockq"] == res["dockq"]["dockq"]


def test_explain_methods_and_view_on_an_evaluated_analysis(analysis, tmp_path):
    t, _ = analysis
    out = []
    for q in ("unavailable", "limitations", "files", "definitions", "versions", "count"):
        r = rn("explain", q, "--analysis", str(t / "a"), "--no-write")
        assert r.returncode == 0, (q, r.stderr); out.append(r.stdout + r.stderr)
    r = rn("explain", "evidence", "--id", "evaluate/s001/result.json#/geometry", "--analysis", str(t / "a"), "--no-write")
    out.append(r.stdout + r.stderr)
    assert leaks("\n".join(out)) == []
    r = rn("export-methods", str(t / "a"), "--project", str(t / "p"), "--out", str(tmp_path / "m"))
    assert r.returncode == 0, r.stderr
    assert leaks(r.stdout + r.stderr) == [] and scan_tree(tmp_path / "m") == []
    r = rn("view", str(t / "p"), "--analysis", str(t / "a"), "--out", str(tmp_path / "v"))
    assert r.returncode == 0, r.stderr
    assert scan_tree(tmp_path / "v") == []


def test_compare(tmp_path):
    PS = importer.read_sequence_arg(os.path.join(RB, "7K9D_protein.fasta"))
    RS = importer.read_sequence_arg(os.path.join(RB, "7K9D_rna.fasta"))
    for n in ("before", "after"):
        with open(tmp_path / ("%s.tsv" % n), "w", newline="") as fh:
            fh.write("target_id\tprediction\tprotein_sequence\trna_sequence\nT1\t%s\t%s\t%s\n" % (PRED, PS, RS))
    (tmp_path / "refs.tsv").write_text("target_id\treference\nT1\t%s\n" % REF)
    r = rn("compare", "--before", str(tmp_path / "before.tsv"), "--after", str(tmp_path / "after.tsv"),
           "--references", str(tmp_path / "refs.tsv"), "--out", str(tmp_path / "c"))
    if r.returncode == 2 and "usage" in r.stderr:                       # positional form
        r = rn("compare", str(tmp_path / "before.tsv"), str(tmp_path / "after.tsv"), str(tmp_path / "refs.tsv"), "--out", str(tmp_path / "c"))
    assert r.returncode == 0, r.stderr
    assert leaks(r.stdout + r.stderr) == [] and scan_tree(tmp_path / "c") == []
    assert json.load(open(tmp_path / "c" / "evaluate" / "before" / "T1" / "result.json"))["geometry"]["status"] == "BLOCKED"


def test_update_with_reference(tmp_path):
    r = rn("update", str(tmp_path / "mp"), os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B"), "--init",
           "--protein-seq", os.path.join(RB, "7K9D_protein.fasta"), "--rna-seq", os.path.join(RB, "7K9D_rna.fasta"),
           "--engine", "BOLTZ2", "--reference", REF)
    assert r.returncode == 0, r.stderr
    assert leaks(r.stdout + r.stderr) == [] and scan_tree(tmp_path / "mp") == []
    assert any(f == "result.json" for _, _, fs in os.walk(tmp_path / "mp") for f in fs)   # Evaluate did run


def test_assistant_evaluate_tool(tmp_path):
    T = pytest.importorskip("rnplens_assistant.tools")
    t = tmp_path / "task"
    shutil.copytree(os.path.join(RF, "exec_A"), t / "runA"); shutil.copytree(os.path.join(RF, "exec_B"), t / "runB")
    shutil.copy(os.path.join(RB, "7K9D_protein.fasta"), t / "protein.fasta"); shutil.copy(os.path.join(RB, "7K9D_rna.fasta"), t / "rna.fasta")
    shutil.copy(REF, t / "reference.cif")
    json.dump({"task_id": "dev", "reference_files": ["reference.cif"]}, open(t / "task.json", "w"))
    ws = T.Workspace(str(t), str(tmp_path / "run"))
    st, _, _ = T.call(ws, "import_predictions", {"project_id": "p", "folders": ["runA", "runB"], "protein_fasta": "protein.fasta", "rna_fasta": "rna.fasta"})
    assert st == "OK"
    st, res, recs = T.call(ws, "evaluate_against_reference", {"project_id": "p", "reference": "reference.cif"})
    assert st == "OK", (st, res)
    assert any(x.get("state") == "TOOL_BLOCKED" for x in recs)
    assert leaks(json.dumps(recs)) == [] and scan_tree(tmp_path / "run") == []
