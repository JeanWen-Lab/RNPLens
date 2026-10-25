"""The public self-test runs from an installed package with no internal file (0.2.0.dev1)."""
import json
import os
import subprocess
import sys

PROFILE = os.environ.get("RNPBENCH_PROFILE", "portable")


def test_public_selftest_passes_without_internal_files(tmp_path):
    out = tmp_path / "rec"
    env = {k: v for k, v in os.environ.items() if not k.startswith("RNPBENCH_PREDICT")}
    r = subprocess.run([sys.executable, "-m", "rnpbench_report", "selftest", "--profile", PROFILE, "--out", str(out)],
                       capture_output=True, text=True, env=env, cwd=str(tmp_path))
    assert r.returncode == 0, (r.stdout[-1500:], r.stderr[-800:])
    rec = json.load(open(out / "selftest_record.json"))
    assert rec["verdict"] == "PASS" and rec["sets"] == "public"
    names = [c["check"] for c in rec["checks"]]
    assert names == ["report.installation", "report.input_validation", "report.example_7K9D.run_exit",
                     "report.example_7K9D.result_and_contacts", "report.example_7K9D.html", "report.output_protection"]
    v = [c for c in rec["checks"] if c["check"] == "report.input_validation"][0]
    assert v["n_cases"] == 12 and v["n_failed"] == 0


def test_acceptance_module_is_not_shipped():
    import importlib.util
    assert importlib.util.find_spec("rnpbench_report.acceptance") is None
    assert importlib.util.find_spec("rnpbench_report.adapters") is None


def test_selftest_refuses_existing_record_dir(tmp_path):
    r = subprocess.run([sys.executable, "-m", "rnpbench_report", "selftest", "--out", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 2 and "REFUSED" in r.stderr
