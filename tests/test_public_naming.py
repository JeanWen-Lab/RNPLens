"""RNPLens is the only public name: help text, report titles and installed commands (0.2.0rc2)."""
import os
import shutil
import subprocess
import sys

import pytest

BIN = os.path.dirname(sys.executable)


def run(*args):
    return subprocess.run([sys.executable, "-m", "rnplens", *args], capture_output=True, text=True,
                          env=dict(os.environ, MPLBACKEND="Agg"))


def run_component(*args):
    """The frozen rc3 component, called internally (0.4 r2: the public 'rnplens diagnose run|preflight|validity' is
    BLOCKED). The rc3 Diagnose behaviour checked below is unchanged; only the entry point moved."""
    code = "import sys; from rnpbench import cli; sys.exit(cli.main(sys.argv[1:]))"
    return subprocess.run([sys.executable, "-c", code, *args], capture_output=True, text=True,
                          env=dict(os.environ, MPLBACKEND="Agg"))


@pytest.mark.parametrize("cmd", ["rnpbench", "rnpbench-evaluate", "rnpbench-report", "rnpbench-diagnose"])
def test_no_legacy_console_script_is_installed(cmd):
    assert not os.path.exists(os.path.join(BIN, cmd))


@pytest.mark.parametrize("args", [["--help"], ["evaluate", "--help"], ["report", "--help"], ["diagnose", "--help"],
                                  ["evaluate", "run", "--help"], ["evaluate", "validate", "--help"],
                                  ["evaluate", "selftest", "--help"], ["evaluate", "provenance", "--help"],
                                  ["report", "run", "--help"], ["report", "validate", "--help"], ["report", "selftest", "--help"],
                                  ["diagnose", "run", "--help"], ["diagnose", "validity", "--help"],
                                  ["diagnose", "preflight", "--help"], ["diagnose", "selftest", "--help"], ["selftest", "--help"]])
def test_help_names_only_rnplens(args):
    r = run(*args)
    assert r.returncode == 0, r.stderr
    text = r.stdout + r.stderr
    assert "rnplens" in text
    for legacy in ("rnpbench", "RNPBench", "Predict"):
        assert legacy not in text, (args, legacy)


def test_unknown_verb_message_names_rnplens():
    r = run("report", "no-such-verb")
    assert r.returncode == 2 and "rnplens report: unknown verb" in r.stderr


def test_report_page_titles():
    pytest.importorskip("matplotlib", reason="the frozen rc3 Report page module imports matplotlib (optional 'rnplens[html]')")
    import inspect
    from rnpbench_report import report as rr
    from rnpbench_diagnose import report as dr
    assert "<title>RNPLens Report:" in rr.DOC and "RNPBench" not in rr.DOC
    src = inspect.getsource(dr)
    assert "<title>RNPLens Diagnose:" in src and "RNPBench-Diagnose" not in src


# ---- 0.2.0rc3: hostile input text never escapes the output directory or the HTML

@pytest.mark.parametrize("cid", ["../../escaped", "a/b", "a\\\\b", ".hidden", "x\\ny"])
def test_report_refuses_case_id_that_is_a_path(tmp_path, cid):
    import json
    ex = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "reference_free")
    c = tmp_path / "c.json"
    assert run("example-contract", ex, "--out", str(c)).returncode == 0
    d = json.load(open(c)); d["case_id"] = cid; c.write_text(json.dumps(d))
    r = run("report", "run", str(c), "--out", str(tmp_path / "out"))
    assert r.returncode == 2 and "case_id" in r.stderr + r.stdout
    assert not (tmp_path / "out").exists() and not (tmp_path.parent / "escaped.html").exists()


def test_html_escapes_supplied_text(tmp_path):
    pytest.importorskip("matplotlib", reason="Report writes its HTML page only with the optional 'rnplens[html]'")
    import json
    X = "<script>alert(1)<"
    ex = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "reference_free")
    c = tmp_path / "c.json"
    assert run("example-contract", ex, "--out", str(c)).returncode == 0
    d = json.load(open(c)); d["case_id"] = X + "case"
    for i, o in enumerate(d["outputs"]):
        o["execution"] = X + "exec%d" % i
    c.write_text(json.dumps(d))
    assert run("report", "run", str(c), "--out", str(tmp_path / "r")).returncode == 0
    page = open(next(str(p) for p in (tmp_path / "r").glob("*.html"))).read()
    assert "<script>alert" not in page and "&lt;script&gt;alert" in page
    dd = tmp_path / "dd"; dd.mkdir()
    import glob, shutil
    for i, p in enumerate(sorted(glob.glob(os.path.join(ex, "diagnose_7K9D", "*.pdb")))):
        shutil.copy(p, dd / ("<img src=x onerror=alert(%d)>.pdb" % i))
    r = run_component("diagnose", "run", *sorted(str(p) for p in dd.iterdir()), "--mode", "within_engine", "--engine", "BOLTZ2",
            "--target", X, "--out", str(tmp_path / "d"))
    assert r.returncode == 0, r.stderr
    page = open(tmp_path / "d" / "report.html").read()
    assert "<script>alert" not in page and "<img src=x" not in page


# ---- 0.2.0rc3: Diagnose applicability domain is enforced

def _models():
    ex = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "reference_free", "diagnose_7K9D")
    return sorted(os.path.join(ex, f) for f in os.listdir(ex) if f.endswith(".pdb"))


@pytest.mark.parametrize("extra,reason", [([], "not declared"), (["--engine", "CHAI1"], "Boltz-2 candidates only"),
                                          (["--engine", "AF3"], "Boltz-2 candidates only")])
def test_diagnose_within_engine_outside_domain_is_refused(tmp_path, extra, reason):
    r = run_component("diagnose", "run", *_models(), "--mode", "within_engine", *extra, "--target", "T", "--out", str(tmp_path / "d"))
    assert r.returncode != 0 and "outside the validated applicability domain" in r.stderr and reason in r.stderr
    assert not (tmp_path / "d" / "report.json").exists()


def test_diagnose_too_few_candidates_is_refused(tmp_path):
    r = run_component("diagnose", "run", *_models()[:3], "--mode", "within_engine", "--engine", "BOLTZ2", "--target", "T",
            "--out", str(tmp_path / "d"))
    assert r.returncode != 0 and "not fewer than 5" in r.stderr


def test_diagnose_cross_engine_unvalidated_label_is_refused(tmp_path):
    m = _models()
    r = run_component("diagnose", "run", *m[:4], "--mode", "cross_engine", "--engine", "BOLTZ2", "--engine", "CHAI1",
            "--engine", "RF3", "--engine", "AF3", "--target", "T", "--out", str(tmp_path / "d"))
    assert r.returncode != 0 and "'AF3'" in r.stderr


def test_diagnose_outside_domain_accepted_is_marked(tmp_path):
    import json
    r = run_component("diagnose", "run", *_models()[:3], "--mode", "within_engine", "--engine", "BOLTZ2", "--target", "T",
            "--allow-outside-validated-domain", "--out", str(tmp_path / "d"))
    assert r.returncode == 0, r.stderr
    rec = json.load(open(tmp_path / "d" / "report.json"))["applicability"]
    assert rec["status"] == "outside_validated_domain" and rec["outside_domain_accepted_by_user"] is True
    assert "Outside the validated domain" in open(tmp_path / "d" / "report.html").read()


def test_diagnose_inside_domain(tmp_path):
    import json
    r = run_component("diagnose", "run", *_models(), "--mode", "within_engine", "--engine", "boltz-2", "--target", "T",
            "--out", str(tmp_path / "d"))
    assert r.returncode == 0, r.stderr
    rec = json.load(open(tmp_path / "d" / "report.json"))["applicability"]
    assert rec["status"] == "inside_validated_domain" and rec["engines_declared"] == ["BOLTZ2"]


def test_diagnose_multi_chain_structures_are_outside_domain():
    from rnpbench_diagnose.applicability import assess, chain_counts
    single = _models()
    assert all(chain_counts(p) == (1, 1) for p in single)
    import rnpbench_evaluate
    multi = os.path.join(os.path.dirname(rnpbench_evaluate.__file__), "fixtures", "equivalent_copies", "reference.cif")
    n_p, n_r = chain_counts(multi)
    assert (n_p, n_r) != (1, 1)
    rec = assess("within_engine", [multi] * 5, declared_engine="BOLTZ2")
    assert rec["status"] == "outside_validated_domain" and "one protein chain and one RNA chain" in rec["reasons_outside"][0]


# ---- 0.4 r2: the public Diagnose workflow is BLOCKED

@pytest.mark.parametrize("verb", ["run", "preflight", "validity"])
def test_public_diagnose_verbs_are_blocked_and_write_nothing(tmp_path, verb):
    from rnplens.capabilities import DIAGNOSE_BLOCKED_EXIT, DIAGNOSE_BLOCKED_STATUS
    out = tmp_path / "d"
    args = {"run": [*_models(), "--mode", "within_engine", "--engine", "BOLTZ2", "--target", "T", "--out", str(out)],
            "preflight": [str(tmp_path / "request.json")], "validity": _models()}[verb]
    r = run("diagnose", verb, *args)
    assert r.returncode == DIAGNOSE_BLOCKED_EXIT == 5
    assert DIAGNOSE_BLOCKED_STATUS in r.stderr and "rnplens diagnose %s" % verb in r.stderr and r.stdout == ""
    assert not out.exists() and os.listdir(tmp_path) == []


def test_diagnose_selftest_still_runs_the_internal_contract_checks():
    r = run("diagnose", "selftest")
    assert r.returncode == 0 and "PASS" in r.stdout
