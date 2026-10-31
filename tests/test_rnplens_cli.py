"""Tests of the RNPLens public command (``rnplens``), a dispatch-only wrapper over the qualified implementation.

They check discoverable help, argument errors, version and provenance records, and that ``rnplens <tool> ...``
writes byte-identical outputs to the qualified ``rnpbench <tool> ...`` path on the bundled examples
(after removing the run timestamp, wall time and output directory, which differ between any two runs).
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

import rnplens
from rnplens import cli

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(ROOT, "examples")
have_examples = os.path.isdir(os.path.join(EX, "reference_based"))


def run(*args, cwd=None):
    env = dict(os.environ, MPLBACKEND="Agg")
    return subprocess.run([sys.executable, "-m", "rnplens", *args], capture_output=True, text=True, cwd=cwd, env=env)


def run_component(*args):
    """The frozen rc3 component, called internally (the public 'rnplens diagnose run|preflight|validity' is BLOCKED in 0.4)."""
    code = "import sys; from rnpbench import cli; sys.exit(cli.main(sys.argv[1:]))"
    return subprocess.run([sys.executable, "-c", code, *args], capture_output=True, text=True, env=dict(os.environ, MPLBACKEND="Agg"))


def test_version_is_a_release_candidate_not_stable():
    assert rnplens.__version__ == "0.4.1"
    assert rnplens.IMPLEMENTATION == "qualified component set 0.2.0.dev1 (internal identifier: RNPBench toolkit 0.2.0.dev1)"


@pytest.mark.parametrize("args", [["--help"], ["evaluate", "--help"], ["report", "--help"], ["diagnose", "--help"],
                                  ["selftest", "--help"], ["provenance", "--help"]])
def test_help_is_discoverable(args):
    r = run(*args)
    assert r.returncode == 0, r.stderr
    assert "usage: rnplens" in r.stdout


@pytest.mark.parametrize("tool,verb", [("evaluate", "run"), ("evaluate", "validate"), ("report", "run"), ("report", "validate")])
def test_verb_help_reaches_the_implementation(tool, verb):
    r = run(tool, verb, "--help")
    assert r.returncode == 0, r.stderr
    assert ("usage: rnplens %s %s" % (tool, verb)) in r.stdout


@pytest.mark.parametrize("verb", ["run", "validity", "preflight"])
def test_diagnose_verb_help_states_blocked(verb):
    # 0.4 r2: the public Diagnose verbs are BLOCKED; their help says so and names the exit code
    r = run("diagnose", verb, "--help")
    assert r.returncode == 0, r.stderr
    assert ("usage: rnplens diagnose %s" % verb) in r.stdout and "DIAGNOSE_BLOCKED" in r.stdout and "Exit code when run: 5" in r.stdout


def test_help_states_scope_limits():
    out = run("--help").stdout
    assert "does not predict structures" in out
    for tool in ("report", "diagnose"):
        t = run(tool, "--help").stdout.lower()
        assert "not a probability of correctness" in t or "not a calibrated correctness score" in t


@pytest.mark.parametrize("args,code", [([], 2), (["no-such-command"], 2), (["evaluate"], 2), (["evaluate", "--input", "x.json"], 2),
                                       (["provenance", "extra"], 2)])
def test_argument_errors_exit_2(args, code):
    assert run(*args).returncode == code


def test_version_lists_components_and_dependencies():
    out = run("--version").stdout
    assert out.startswith("rnplens 0.4.1")
    for s in ("RNPBench toolkit 0.2.0.dev1", "rnpbench_evaluate", "rnpbench_report", "rnpbench_diagnose", "DockQ 2.1.3"):
        assert s in out


def test_provenance_record():
    r = run("provenance")
    assert r.returncode == 0, r.stderr
    rec = json.loads(r.stdout)
    assert rec["rnplens_version"] == "0.4.1"
    assert rec["component_module_versions"]["rnpbench_evaluate"] == "0.2.0.dev1"
    assert rec["frozen_sources_sha256"] and all(len(h) == 64 for h in rec["frozen_sources_sha256"].values())


def _strip(o, drop=("created_utc", "wall_s")):
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if k not in drop}
    if isinstance(o, list):
        return [_strip(v) for v in o]
    return o


def _same_json(a, b, outdirs):
    ta, tb = open(a).read(), open(b).read()
    for d, tag in zip(outdirs, ("<OUT>", "<OUT>")):
        ta, tb = ta.replace(outdirs[0], tag), tb.replace(outdirs[1], tag)
    return _strip(json.loads(ta)) == _strip(json.loads(tb))


@pytest.mark.skipif(not have_examples, reason="examples/ not present (installed without the source tree)")
def test_evaluate_rnplens_equals_rnpbench_path(tmp_path):
    inp = os.path.join(EX, "reference_based", "example_input.json")
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    cwd = os.path.join(EX, "reference_based")
    assert run("evaluate", "run", "--input", inp, "--out", a, cwd=cwd).returncode == 0
    from rnpbench import cli as rcli
    here = os.getcwd(); os.chdir(cwd)
    try:
        assert rcli.main(["evaluate", "run", "--input", inp, "--out", b]) == 0
    finally:
        os.chdir(here)
    # 0.4 r3: the public output is exactly the component's output passed through the documented geometry filter
    # (rnplens.geometry_block; records/release/GEOMETRY_BLOCK_INVENTORY.md), plus the filter's own provenance record
    from rnplens import geometry_block as GB
    pub = json.load(open(os.path.join(a, "result.json")))
    assert pub.pop("rnplens_public_output")["frozen_component_output_sha256_before_filtering"]
    comp = GB.filter_result_json(json.load(open(os.path.join(b, "result.json"))))
    assert _strip(pub) == _strip(json.loads(json.dumps(comp).replace(b, a)))
    assert open(os.path.join(a, "result.csv"), newline="").read().replace(a, "") == \
        GB.filter_result_csv(open(os.path.join(b, "result.csv"), newline="").read()).replace(b, "")
    assert open(os.path.join(a, "summary.txt")).read().replace(a, "") == \
        GB.filter_summary_text(open(os.path.join(b, "summary.txt")).read()).replace(b, "")


@pytest.mark.skipif(not have_examples, reason="examples/ not present (installed without the source tree)")
def test_evaluate_refuses_existing_output(tmp_path):
    inp = os.path.join(EX, "reference_based", "example_input.json")
    out = tmp_path / "o"
    assert run("evaluate", "run", "--input", inp, "--out", str(out), cwd=os.path.join(EX, "reference_based")).returncode == 0
    before = {p: open(os.path.join(out, p), "rb").read() for p in os.listdir(out)}
    r = run("evaluate", "run", "--input", inp, "--out", str(out), cwd=os.path.join(EX, "reference_based"))
    assert r.returncode != 0
    assert {p: open(os.path.join(out, p), "rb").read() for p in os.listdir(out)} == before


@pytest.mark.skipif(not have_examples, reason="examples/ not present (installed without the source tree)")
def test_report_and_diagnose_examples_run(tmp_path):
    c = str(tmp_path / "contract.json")
    assert run("example-contract", os.path.join(EX, "reference_free"), "--out", c).returncode == 0
    assert run("report", "validate", c).returncode == 0
    r = run("report", "run", c, "--out", str(tmp_path / "rep"))
    assert r.returncode == 0, r.stderr
    res = json.load(open(tmp_path / "rep" / "result.json"))
    assert res["summary"]["NO_REFERENCE_STRUCTURE_IS_READ"] is True
    assert "not a probability of structural correctness" in res["summary"]["SEMANTICS"]
    models = sorted(os.path.join(EX, "reference_free", "diagnose_7K9D", f) for f in os.listdir(os.path.join(EX, "reference_free", "diagnose_7K9D")))
    # 0.4 r2: public Diagnose is BLOCKED (exit 5, nothing written); the rc3 component's own output is checked internally
    r = run("diagnose", "run", *models, "--mode", "within_engine", "--engine", "BOLTZ2", "--target", "7K9D", "--out", str(tmp_path / "dia_public"))
    assert r.returncode == 5 and "DIAGNOSE_BLOCKED" in r.stderr and not (tmp_path / "dia_public").exists()
    r = run_component("diagnose", "run", *models, "--mode", "within_engine", "--engine", "BOLTZ2", "--target", "7K9D", "--out", str(tmp_path / "dia"))
    assert r.returncode == 0, r.stderr
    d = json.load(open(tmp_path / "dia" / "report.json"))
    assert "probability_of_correctness" in d["diagnosis"]["refused_statements"]
    assert os.path.exists(tmp_path / "dia" / "report.html")


def test_report_rejects_empty_candidate_set(tmp_path):
    c = tmp_path / "c.json"
    c.write_text(json.dumps({"schema_version": "rnpbench-predict-contract-1", "case_id": "x",
                             "construct": {"protein_length": 1, "rna_length": 1, "protein_sequence": "M", "rna_sequence": "G"}, "outputs": []}))
    r = run("report", "validate", str(c))
    assert r.returncode != 0


def test_diagnose_needs_candidates(tmp_path):
    r = run_component("diagnose", "run", "--mode", "within_engine", "--target", "X", "--out", str(tmp_path / "d"))
    assert r.returncode != 0
