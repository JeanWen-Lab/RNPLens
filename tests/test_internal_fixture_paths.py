"""Added in 0.2.0.dev1: `--internal-fixtures` given as relative and absolute paths, from different working directories,
including paths that contain spaces (the 0.1.1 / 0.2.0.dev0 defect joined a relative path to itself).

Uses the internal fixtures when RNPBENCH_INTERNAL_FIXTURES points at them; otherwise skipped (not passed).
Each case runs the complete self-test through the installed command line in a subprocess, so the working
directory is that of a real invocation.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

PROFILE = os.environ.get("RNPBENCH_PROFILE", "portable")
INTERNAL = os.environ.get("RNPBENCH_INTERNAL_FIXTURES")
pytestmark = pytest.mark.skipif(not INTERNAL, reason="internal fixtures not available (set RNPBENCH_INTERNAL_FIXTURES)")


@pytest.fixture(scope="module")
def layout(tmp_path_factory):
    root = tmp_path_factory.mktemp("paths")
    plain = root / "fixtures_plain" / "internal"
    spaced = root / "dir with spaces" / "internal fixtures"
    for d in (plain, spaced):
        shutil.copytree(INTERNAL, d)
    (root / "elsewhere" / "deeper").mkdir(parents=True)
    return root


CASES = {  # id: (working directory relative to root, path argument)
    "relative_from_parent": ("fixtures_plain", "internal"),
    "relative_dot_prefix": ("fixtures_plain", "./internal"),
    "relative_dotdot_from_other_dir": ("elsewhere/deeper", "../../fixtures_plain/internal"),
    "relative_with_spaces": ("dir with spaces", "internal fixtures"),
    "relative_dotdot_with_spaces": ("elsewhere", "../dir with spaces/internal fixtures"),
    "absolute_with_spaces": ("elsewhere/deeper", "<ROOT>/dir with spaces/internal fixtures"),
    "absolute_plain": ("elsewhere", "<ROOT>/fixtures_plain/internal"),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_internal_fixture_path_forms(layout, case, tmp_path):
    cwd, arg = CASES[case]
    arg = arg.replace("<ROOT>", str(layout))
    out = tmp_path / "record"
    r = subprocess.run([sys.executable, "-m", "rnpbench_evaluate", "selftest", "--profile", PROFILE,
                        "--internal-fixtures", arg, "--out", str(out)],
                       cwd=str(layout / cwd), capture_output=True, text=True)
    assert r.returncode == 0, (r.stdout[-800:], r.stderr[-800:])
    rec = json.load(open(out / "selftest_record.json"))
    assert rec["verdict"] == "PASS"
    assert rec["fixture_sets"] == ["public", "internal"]
    internal = {k for k, v in rec["inputs"].items() if v.get("set") == "internal"}
    assert internal == {"no_value_rf3_6NY2", "engine_af3_8QJK", "engine_chai1_9RVP", "engine_rf2na_4RCJ"}, internal
    assert rec["n_checks"] == rec["n_passed"] == 311
