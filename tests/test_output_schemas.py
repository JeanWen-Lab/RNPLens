"""Every JSON result RNPLens writes on the bundled examples matches its documented schema (docs/schemas/)."""
import json
import os
import subprocess
import sys

import pytest

jsonschema = pytest.importorskip("jsonschema")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCH = os.path.join(ROOT, "docs", "schemas")
EXP = os.path.join(ROOT, "examples", "expected_output")
pytestmark = pytest.mark.skipif(not os.path.isdir(SCH), reason="schemas not present")


def check(schema_file, instance):
    s = json.load(open(os.path.join(SCH, schema_file)))
    jsonschema.Draft202012Validator.check_schema(s)
    jsonschema.Draft202012Validator(s).validate(instance)


@pytest.mark.parametrize("schema_file,path", [("evaluate_result.schema.json", "A_evaluate_7K9D/result.json"),
                                              ("report_result.schema.json", "B1_report_7K9D/result.json"),
                                              ("diagnose_report.schema.json", "B2_diagnose_7K9D/report.json")])
def test_expected_outputs_match_schema(schema_file, path):
    check(schema_file, json.load(open(os.path.join(EXP, path))))


def test_fresh_outputs_match_schema(tmp_path):
    out = tmp_path / "ex"
    env = dict(os.environ, MPLBACKEND="Agg", PATH=os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", ""))
    r = subprocess.run(["bash", os.path.join(ROOT, "examples", "run_examples.sh"), str(out)], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr[-2000:]
    check("evaluate_result.schema.json", json.load(open(out / "A_evaluate_7K9D" / "result.json")))
    check("report_result.schema.json", json.load(open(out / "B1_report_7K9D" / "result.json")))
    check("diagnose_report.schema.json", json.load(open(out / "B2_diagnose_7K9D" / "report.json")))
    for d in ("A_evaluate_7K9D", "B1_report_7K9D", "B2_diagnose_7K9D"):
        rec = json.load(open(out / d / "rnplens_run.json"))
        check("rnplens_run_record.schema.json", rec)
        for o in rec["outputs"]:
            import hashlib
            assert hashlib.sha256(open(out / d / o["file"], "rb").read()).hexdigest() == o["sha256"]


def test_no_value_is_null_not_zero():
    s = json.load(open(os.path.join(SCH, "evaluate_result.schema.json")))
    dq = s["properties"]["dockq"]["properties"]
    assert "null" in dq["dockq"]["type"] and "NO_VALUE" in s["description"]


def test_prediction_alias_is_not_distributed():
    import importlib.util
    assert importlib.util.find_spec("rnpbench_predict") is None
