"""QA install-science fix round O1/O2: the installation documents state what happens without the optional matplotlib,
and the statement matches the software: rnplens report run writes result.json and contacts_by_output.json but no HTML
page; rnplens doctor shows 'Optional matplotlib' as ACTION REQUIRED and, since O1 (LIVE_QUALIFICATION_v1 Amendment 6),
exits 0 because an optional component never makes the exit status non-zero (tests/test_doctor.py checks the code)."""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(ROOT, "examples", "reference_free")
NO_MPL = ("import sys; sys.modules['matplotlib'] = None; from rnplens.cli import main; sys.exit(main(sys.argv[1:]))")


def _doc(name):
    return open(os.path.join(ROOT, "docs", name), encoding="utf-8").read()


def test_installation_docs_state_the_no_matplotlib_behaviour():
    inst = _doc("installation.md")
    assert "writes no HTML page" in inst and "Report's HTML page has no figures" not in inst
    assert "Optional matplotlib" in inst and "exits with status 0" in inst and "exits with status 1" not in inst
    sp = _doc("setup_and_privacy.md")
    assert "Optional matplotlib" in sp and "never changes the exit code" in sp


def test_report_without_matplotlib_writes_json_and_no_html(tmp_path):
    c = tmp_path / "c.json"
    env = dict(os.environ, MPLBACKEND="Agg")
    assert subprocess.run([sys.executable, "-m", "rnplens", "example-contract", EX, "--out", str(c)], env=env).returncode == 0
    r = subprocess.run([sys.executable, "-c", NO_MPL, "report", "run", str(c), "--out", str(tmp_path / "r")],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    files = sorted(os.listdir(tmp_path / "r"))
    assert "result.json" in files and "contacts_by_output.json" in files
    assert not [f for f in files if f.endswith(".html")]
    assert json.load(open(tmp_path / "r" / "result.json"))["environment"]["matplotlib"].startswith("not installed")
