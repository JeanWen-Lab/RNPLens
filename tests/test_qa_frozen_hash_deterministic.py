"""QA install-science fix round O7: the hash of the frozen component's output that 'rnplens evaluate run' records
(rnplens_public_output.frozen_component_output_sha256_before_filtering) was a raw byte hash and changed between identical
runs, because the frozen result.json carries its own created_utc. It is now, per file, a deterministic content_sha256
(DETERMINISM_CONTRACT_v1 rule: sha256_json of the JSON without volatile keys; the byte hash for non-JSON files) plus the
raw byte hash under the contract's declared volatile key raw_file_sha256. Apart from volatile keys the published record is
identical between identical runs."""
import json
import os
import subprocess
import sys
import time

from rnplens import canonical
from rnplens import provenance as pv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RB = os.path.join(ROOT, "examples", "reference_based")
COMPONENT = "import sys; from rnpbench import cli; sys.exit(cli.main(sys.argv[1:]))"
KEY = "frozen_component_output_sha256_before_filtering"


def _run(out):
    r = subprocess.run([sys.executable, "-m", "rnplens", "evaluate", "run", "--input", "example_input.json", "--out", str(out)],
                       capture_output=True, text=True, cwd=RB, env=dict(os.environ, MPLBACKEND="Agg"))
    assert r.returncode == 0, r.stderr
    return json.load(open(os.path.join(out, "result.json")))


def test_recorded_frozen_output_hash_is_deterministic(tmp_path):
    a = _run(tmp_path / "a")
    time.sleep(1.2)                                  # a different created_utc second
    b = _run(tmp_path / "b")
    ha, hb = a["rnplens_public_output"][KEY], b["rnplens_public_output"][KEY]
    assert set(ha) == {"result.csv", "result.json", "summary.txt"}
    for f in ha:
        assert set(ha[f]) >= {"content_sha256", "raw_file_sha256"}
        assert ha[f]["content_sha256"] == hb[f]["content_sha256"], f
    assert a["created_utc"] != b["created_utc"]
    assert canonical.split_volatile(a)[0] == canonical.split_volatile(b)[0]
    # the recorded content hash is the contract's content hash of the frozen component's own result.json
    raw = tmp_path / "raw"
    c = subprocess.run([sys.executable, "-c", COMPONENT, "evaluate", "run", "--input", "example_input.json", "--out", str(raw)],
                       capture_output=True, text=True, cwd=RB)
    assert c.returncode == 0, c.stderr
    obj = json.load(open(raw / "result.json"))
    assert pv.sha256_json(canonical.split_volatile(obj)[0]) == ha["result.json"]["content_sha256"]
    assert pv.sha256_file(str(raw / "summary.txt")) == ha["summary.txt"]["content_sha256"] == ha["summary.txt"]["raw_file_sha256"]
