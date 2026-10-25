"""0.4 owner decision (F1): the components' own command lines refuse verbs that would show a BLOCKED result.

Covers every alias found in the 0.4 audit: ``python -m`` on each component package and module (including the
``-mX`` and ``python -W ... -m`` forms), the same packages run by path, and the research drivers of the frozen
sources; and checks that the qualified routes are unaffected (help/version/provenance/validate, Report, library
imports, and the ``python -c`` component route that ``rnplens`` itself uses). Refused routes are given real-looking
arguments and an output directory; nothing may be created. The frozen research drivers are only ever reached through
``rnplens.legacy_routes.decide`` here, never executed.
"""
import importlib.util
import os
import subprocess
import sys

import pytest

from rnplens import capabilities, legacy_routes as lr

PY = sys.executable


def _pkg_dir(name):
    return list(importlib.util.find_spec(name).submodule_search_locations)[0]


def _run(args, cwd):
    return subprocess.run([PY] + args, cwd=str(cwd), capture_output=True, text=True, timeout=120)


REFUSED_M = {  # id: argv after the interpreter; "<OUT>" is an output directory that must not appear
    "rnpbench_evaluate_run": ["-m", "rnpbench", "evaluate", "run", "--input", "in.json", "--out", "<OUT>"],
    "rnpbench.cli_evaluate_run": ["-m", "rnpbench.cli", "evaluate", "run", "--input", "in.json", "--out", "<OUT>"],
    "rnpbench_evaluate_legacy_options": ["-m", "rnpbench", "evaluate", "--input", "in.json", "--out", "<OUT>"],
    "rnpbench_evaluate_selftest": ["-m", "rnpbench", "evaluate", "selftest", "--out", "<OUT>"],
    "rnpbench_selftest_legacy": ["-m", "rnpbench", "selftest", "--out", "<OUT>"],
    "rnpbench_toolkit_selftest": ["-m", "rnpbench", "toolkit", "selftest"],
    "rnpbench_diagnose_run": ["-m", "rnpbench", "diagnose", "run", "a.pdb", "b.pdb", "--out", "<OUT>"],
    "rnpbench_diagnose_preflight": ["-m", "rnpbench", "diagnose", "preflight", "a.pdb", "--out", "<OUT>"],
    "rnpbench_diagnose_validity": ["-m", "rnpbench", "diagnose", "validity", "a.pdb", "--out", "<OUT>"],
    "rnpbench_diagnose_selftest": ["-m", "rnpbench", "diagnose", "selftest", "--out", "<OUT>"],
    "rnpbench.evaluate": ["-m", "rnpbench.evaluate", "run"],
    "rnpbench.diagnose": ["-m", "rnpbench.diagnose", "run"],
    "rnpbench.toolkit": ["-m", "rnpbench.toolkit", "selftest"],
    "rnpbench.selftests": ["-m", "rnpbench.selftests"],
    "rnpbench_evaluate_module_evaluate": ["-m", "rnpbench_evaluate", "evaluate", "--input", "in.json", "--out", "<OUT>"],
    "rnpbench_evaluate.cli_evaluate": ["-m", "rnpbench_evaluate.cli", "evaluate", "--input", "in.json", "--out", "<OUT>"],
    "rnpbench_evaluate_module_selftest": ["-m", "rnpbench_evaluate", "selftest", "--out", "<OUT>"],
    "rnpbench_evaluate.selftest": ["-m", "rnpbench_evaluate.selftest"],
    "rnpbench_evaluate.engine": ["-m", "rnpbench_evaluate.engine"],
    "rnpbench_diagnose_module_diagnose": ["-m", "rnpbench_diagnose", "diagnose", "a.pdb", "b.pdb", "--out", "<OUT>"],
    "rnpbench_diagnose_module_validity": ["-m", "rnpbench_diagnose", "validity", "a.pdb", "--out", "<OUT>"],
    "rnpbench_diagnose_module_preflight": ["-m", "rnpbench_diagnose", "preflight", "a.pdb", "--out", "<OUT>"],
    "rnpbench_diagnose.cli_diagnose": ["-m", "rnpbench_diagnose.cli", "diagnose", "a.pdb", "--out", "<OUT>"],
    "rnpbench_diagnose.diagnose": ["-m", "rnpbench_diagnose.diagnose"],
    "rnpbench_diagnose_contract_checks": ["-m", "rnpbench_diagnose._checks.contract.test_contract"],
    "rnpbench_core.frozen": ["-m", "rnpbench_core.frozen"],
    "rnpbench_core.frozen_loader": ["-m", "rnpbench_core.frozen_loader"],
    "joined_-m_form": ["-mrnpbench_evaluate", "evaluate", "--input", "in.json", "--out", "<OUT>"],
    "options_before_-m": ["-W", "ignore", "-X", "utf8", "-m", "rnpbench", "evaluate", "run", "--out", "<OUT>"],
    "clustered_-Bm": ["-Bm", "rnpbench_diagnose", "diagnose", "a.pdb", "--out", "<OUT>"],
}


@pytest.mark.parametrize("case", sorted(REFUSED_M))
def test_component_module_route_refused(case, tmp_path):
    out = tmp_path / "out"
    r = _run([str(out) if a == "<OUT>" else a for a in REFUSED_M[case]], tmp_path)
    assert r.returncode == lr.EXIT_BLOCKED == 5, (r.returncode, r.stdout[-400:], r.stderr[-400:])
    assert lr.STATUS in r.stderr and "unavailable in RNPLens 0.4" in r.stderr and "rnplens" in r.stderr
    assert r.stdout == ""
    assert not out.exists()
    assert sorted(os.listdir(tmp_path)) == ["out"] or sorted(os.listdir(tmp_path)) == []


PATH_ROUTES = {  # package directories run by path (their __main__ uses absolute imports) and files run by path
    "rnpbench_diagnose_dir": ("rnpbench_diagnose", None, ["diagnose", "a.pdb", "--out", "<OUT>"]),
    "rnpbench_diagnose_contract_checks_file": ("rnpbench_diagnose", "_checks/contract/test_contract.py", []),
    "rnpbench_dir": ("rnpbench", None, ["evaluate", "run", "--out", "<OUT>"]),
    "rnpbench_cli_file": ("rnpbench", "cli.py", ["evaluate", "run", "--out", "<OUT>"]),
    "rnpbench_evaluate_dir": ("rnpbench_evaluate", None, ["evaluate", "--out", "<OUT>"]),
    "rnpbench_evaluate_cli_file": ("rnpbench_evaluate", "cli.py", ["evaluate", "--out", "<OUT>"]),
    "rnpbench_diagnose_cli_file": ("rnpbench_diagnose", "cli.py", ["diagnose", "a.pdb", "--out", "<OUT>"]),
}


@pytest.mark.parametrize("case", sorted(PATH_ROUTES))
def test_component_path_route_computes_nothing(case, tmp_path):
    """Refused (exit 5), or fails at a relative import before anything runs; never computes or writes."""
    pkg, rel, args = PATH_ROUTES[case]
    target = _pkg_dir(pkg) if rel is None else os.path.join(_pkg_dir(pkg), rel)
    out = tmp_path / "out"
    r = _run([target] + [str(out) if a == "<OUT>" else a for a in args], tmp_path)
    refused = r.returncode == 5 and lr.STATUS in r.stderr
    import_failed = r.returncode == 1 and "ImportError: attempted relative import" in r.stderr
    assert refused or import_failed, (r.returncode, r.stderr[-600:])
    assert r.stdout == "" and not out.exists()


def test_frozen_research_drivers_are_refused_by_policy():
    """`python -m rnpbench_core.frozen.<group>.<driver>` imports rnpbench_core first; the policy refuses all of it."""
    for mod in ("rnpbench_core.frozen.canonical.pos_adapter", "rnpbench_core.frozen.canonical.corr_mask_audit",
                "rnpbench_core.frozen.canonical.rnpbench_score_v2", "rnpbench_core.frozen.canonical.rf2na_scoring",
                "rnpbench_core.frozen.decomp.score_decomp", "rnpbench_core.frozen.f1.f1_featurize_mp",
                "rnpbench_core.frozen.f1.f1_b1c_allatom", "rnpbench_core.frozen.f1.f1_b2a_matrix"):
        assert lr.decide(mod, []) == "research", mod


ALLOWED = {
    "rnpbench_help": ["-m", "rnpbench", "--help"],
    "rnpbench_version": ["-m", "rnpbench", "--version"],
    "rnpbench_evaluate_provenance": ["-m", "rnpbench", "evaluate", "provenance"],
    "rnpbench_provenance_legacy": ["-m", "rnpbench", "provenance"],
    "rnpbench_toolkit_version": ["-m", "rnpbench", "toolkit", "version"],
    "rnpbench_evaluate_module_provenance": ["-m", "rnpbench_evaluate", "provenance"],
    "rnpbench_evaluate_module_help": ["-m", "rnpbench_evaluate", "--help"],
    "rnpbench_diagnose_module_help": ["-m", "rnpbench_diagnose", "--help"],
    "rnpbench_report_help": ["-m", "rnpbench_report", "--help"],
    "library_imports": ["-c", "import rnpbench, rnpbench.cli, rnpbench_core, rnpbench_core.frozen_loader, rnpbench_evaluate, "
                              "rnpbench_evaluate.cli, rnpbench_report, rnpbench_diagnose, rnpbench_diagnose.cli; print('ok')"],
    "rnplens_component_route_provenance": ["-c", "import sys; from rnpbench import cli; sys.exit(cli.main(sys.argv[1:]))",
                                           "evaluate", "provenance"],
}


@pytest.mark.parametrize("case", sorted(ALLOWED))
def test_qualified_and_library_routes_unaffected(case, tmp_path):
    r = _run(ALLOWED[case], tmp_path)
    assert r.returncode == 0, (r.stdout[-400:], r.stderr[-400:])
    assert lr.STATUS not in r.stderr and r.stdout.strip()


def test_launch_parsing():
    P = "/usr/bin/python3"
    assert lr._launch([P, "-m", "rnpbench", "evaluate"]) == ("module", "rnpbench", ["evaluate"])
    assert lr._launch([P, "-mrnpbench_evaluate", "evaluate"]) == ("module", "rnpbench_evaluate", ["evaluate"])
    assert lr._launch([P, "-IBm", "rnpbench"]) == ("module", "rnpbench", [])
    assert lr._launch([P, "-W", "ignore", "-X", "dev", "-m", "x.y", "a"]) == ("module", "x.y", ["a"])
    assert lr._launch([P, "-Wignore", "-m", "x"]) == ("module", "x", [])
    assert lr._launch([P, "-c", "import x", "-m", "rnpbench"]) == (None, None, [])
    assert lr._launch([P, "script.py", "-m", "rnpbench"]) == ("script", "script.py", ["-m", "rnpbench"])
    assert lr._launch([P]) == (None, None, [])
    assert lr._launch([P, "-"]) == (None, None, [])


def test_policy_table():
    d = lr.decide
    assert d("rnpbench_report", ["run"]) is None and d("rnpbench_report.cli", ["selftest"]) is None
    assert d("rnpbench", ["report", "run"]) is None and d("rnpbench", ["evaluate", "validate"]) is None
    assert d("rnpbench", ["toolkit", "provenance"]) is None and d("rnpbench", ["diagnose", "--help"]) is None
    assert d("rnpbench", ["evaluate", "run"]) == "geometry" and d("rnpbench", ["evaluate"]) == "geometry"
    assert d("rnpbench", ["toolkit", "selftest"]) == "toolkit" and d("rnpbench", ["diagnose"]) == "diagnose"
    assert d("rnpbench_evaluate", ["validate"]) is None and d("rnpbench_evaluate", ["evaluate"]) == "geometry"
    assert d("rnpbench_diagnose", []) is None and d("rnpbench_diagnose", ["selftest"]) == "diagnose"
    assert d("rnplens", ["evaluate", "run"]) is None and d("pytest", []) is None


def test_exit_status_matches_rnplens_blocked_exit():
    assert lr.EXIT_BLOCKED == capabilities.DIAGNOSE_BLOCKED_EXIT
