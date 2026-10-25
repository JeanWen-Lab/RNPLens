"""QA install-science D3: `rnplens evaluate selftest --out DIR` must not write Evaluate's blocked four-axis geometry
values (README: "no public command shows its values"; tests/test_geometry_blocked.py: no geometry value in stdout, stderr
or any written file). The checks, verdict and exit code stay those of the frozen self-test; DockQ-family values unchanged."""
import csv
import io
import json
import os
import re
import subprocess
import sys

COMPONENT = "import sys; from rnpbench import cli; sys.exit(cli.main(sys.argv[1:]))"
VALUE_KEYS = ("prot_internal_ca_rmsd", "rna_internal_c4_rmsd", "rna_placement_c4_rmsd")
COUNT_KEYS = ("n_prot_aligned", "n_prot_native", "n_prot_pose", "n_rna_aligned", "n_rna_native", "n_rna_pose")
KEY_RE = re.compile(r'"(%s)"\s*:\s*-?\d' % "|".join(VALUE_KEYS + COUNT_KEYS))
PHRASES = ("RNA internal C4' RMSD", "RNA placement C4' RMSD after", "protein internal CA RMSD", "geometry COMPUTED")
CSV_COLS = ("protein_internal_ca_rmsd", "rna_internal_c4_rmsd", "rna_placement_c4_rmsd", "n_protein_pairs", "n_rna_pairs")


def _leaks(d):
    bad = []
    for root, _, files in os.walk(d):
        for f in files:
            p = os.path.join(root, f)
            t = open(p, "rb").read().decode("utf-8", "ignore")
            bad += [(f, x) for x in PHRASES if x in t] + [(f, m.group(0)) for m in KEY_RE.finditer(t)]
            if f == "result.csv":
                bad += [(f, c) for r in csv.DictReader(io.StringIO(t)) for c in CSV_COLS if r.get(c)]
            if f == "selftest_record.json":
                rec = json.loads(t)
                for c in rec["checks"] + rec["failures"] + rec["all_deviations"]:
                    if "geometry." in c.get("check", "") and any(isinstance(c.get(k), (int, float)) and not isinstance(c.get(k), bool)
                                                                 for k in ("expected", "got")):
                        bad.append((f, c["check"]))
    return bad


def test_evaluate_selftest_out_writes_no_geometry_value(tmp_path):
    pub, raw = tmp_path / "pub", tmp_path / "raw"
    r = subprocess.run([sys.executable, "-m", "rnplens", "evaluate", "selftest", "--out", str(pub)], capture_output=True, text=True,
                       env=dict(os.environ, MPLBACKEND="Agg"))
    c = subprocess.run([sys.executable, "-c", COMPONENT, "evaluate", "selftest", "--out", str(raw)], capture_output=True, text=True)
    # the wrapper keeps the frozen self-test's exit code; with the bit-exact reference profile that code is 0 on the
    # qualified Linux platform and 3 on macOS (pre-existing last-digit DockQ deviation, records/release/MACOS_NUMERICAL_DIFFERENCE.md)
    assert r.returncode == c.returncode
    if sys.platform.startswith("linux"):
        assert r.returncode == 0
    assert _leaks(str(raw)), "positive control: the frozen component's own --out holds geometry values"
    assert _leaks(str(pub)) == []
    assert str(tmp_path / "pub") not in r.stdout or "rnplens_selftest_private_" not in r.stdout
    # same checks and verdict; per-fixture DockQ family unchanged
    rp, rr = json.load(open(pub / "selftest_record.json")), json.load(open(raw / "selftest_record.json"))
    assert (rp["verdict"], rp["n_checks"], rp["n_passed"]) == (rr["verdict"], rr["n_checks"], rr["n_passed"])
    assert [(x["check"], x["ok"]) for x in rp["checks"]] == [(x["check"], x["ok"]) for x in rr["checks"]]
    assert sorted(os.listdir(pub)) == sorted(os.listdir(raw))
    for fx in [x for x in os.listdir(raw) if os.path.isdir(raw / x)]:
        a, b = json.load(open(pub / fx / "result.json")), json.load(open(raw / fx / "result.json"))
        assert a["dockq"] == b["dockq"] and a["geometry"]["status"] == "BLOCKED"
