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
    import inspect
    from rnpbench_report import report as rr
    from rnpbench_diagnose import report as dr
    assert "<title>RNPLens Report:" in rr.DOC and "RNPBench" not in rr.DOC
    src = inspect.getsource(dr)
    assert "<title>RNPLens Diagnose:" in src and "RNPBench-Diagnose" not in src
