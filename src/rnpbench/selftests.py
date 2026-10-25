"""Toolkit self-tests for Report and Diagnose (the Evaluate self-test is Evaluate's own, unchanged).

Report  : Report's own public self-test (rnpbench_report.selftest, 0.2.0.dev1), the same function the standalone
          `rnpbench-report selftest` runs; optional, internal: the original acceptance suite
          (``--acceptance-store DIR --overlay DIR``) against the frozen development store, which is not distributed.
Diagnose: (1) the 18 established contract checks (the original file, unchanged);
          (2) public example regression: within-engine diagnosis of the bundled 7K9D samples, compared with
              the output of the original RNPBench-Diagnose 0.2.1 on the reference platform.
Comparison follows toolkit_example_regression_profile_v1.json (frozen before any run).
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(HERE, "examples")
EXPECTED = os.path.join(HERE, "expected")
PROFILE_PATH = os.path.join(HERE, "profiles", "toolkit_example_regression_profile_v1.json")
PROFILE_SHA256_AT_FREEZE = "f5ddd3d6e66e84bfeba7e071408aa8dcc5586f5e3e50fdef26438e70dce1b2df"
PORTABLE_FLOAT_TOL = 1e-5


def _profile():
    got = hashlib.sha256(open(PROFILE_PATH, "rb").read()).hexdigest()
    if got != PROFILE_SHA256_AT_FREEZE:
        raise RuntimeError("toolkit example-regression profile differs from the version frozen before testing")
    return json.load(open(PROFILE_PATH))


# ------------------------------------------------------------------ normalisation and comparison
# One implementation, owned by Report's public self-test (moved there in 0.2.0.dev1); the same profile file.
from rnpbench_report.selftest import normalise, compare, summarise as _summ   # noqa: E402


# ------------------------------------------------------------------ Report
def write_report_contract(examples_dir, out_path):
    from rnpbench_report import contract as C
    t = json.load(open(os.path.join(examples_dir, "report_7K9D", "contract_template.json")))
    for o in t["outputs"]:
        o["structure_path"] = o["structure_path"].replace("<EXAMPLES>", os.path.abspath(examples_dir))
        o["sha256"] = C.sha256(o["structure_path"])
        C.declare_confidence_input(o)                    # the engine confidence file is a declared input too
    json.dump(t, open(out_path, "w"), indent=1)
    return out_path


# ------------------------------------------------------------------ Diagnose
def diagnose_contract_checks():
    from rnpbench_diagnose._toolkit import prepare
    prepare()
    import importlib.util
    p = os.path.join(os.path.dirname(__import__("rnpbench_diagnose").__file__), "_checks", "contract", "test_contract.py")
    spec = importlib.util.spec_from_file_location("rnpbench_diagnose_contract_checks", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    res = []
    for name, fn in sorted((k[2:], v) for k, v in vars(m).items() if k.startswith("t_") and callable(v)):
        try:
            fn(); res.append((name, True, ""))
        except AssertionError as ex:
            res.append((name, False, str(ex)))
    return {"check": "diagnose.contract_checks", "n_checks": len(res), "n_failed": sum(not r[1] for r in res),
            "failures": [r for r in res if not r[1]], "ok": len(res) == 18 and all(r[1] for r in res)}


def diagnose_example(tmp, profile):
    from rnpbench_diagnose._toolkit import entry
    ex = os.path.join(tmp, "examples"); shutil.copytree(EXAMPLES, ex) if not os.path.exists(ex) else None
    d = os.path.join(ex, "diagnose_7K9D"); out = os.path.join(tmp, "diagnose_out")
    files = sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".pdb"))
    rc = entry(["diagnose", *files, "--mode", "within_engine", "--engine", "BOLTZ2", "--target", "7K9D", "--out", out])
    got = normalise(json.load(open(os.path.join(out, "report.json"))), ex)
    exp = json.load(open(os.path.join(EXPECTED, "diagnose_7K9D_report.json")))
    s = _summ("diagnose.example_7K9D.report", compare(exp, got, profile)); s["exit"] = rc; s["ok"] = s["ok"] and rc == 0
    return s


# ------------------------------------------------------------------ entry
def run(tool, argv):
    ap = argparse.ArgumentParser(prog="rnplens %s selftest" % tool)
    ap.add_argument("--profile", choices=("reference", "portable"), default="portable")
    ap.add_argument("--out", default=None, help="directory for the self-test record (never overwritten)")
    if tool == "report":
        ap.add_argument("--acceptance-store", default=None, help="INTERNAL: frozen Report development store (not distributed)")
        ap.add_argument("--overlay", default=None, help="INTERNAL: report qualification overlay (acceptance suite, benchmark adapter)")
    a = ap.parse_args(argv)
    if tool == "report":                 # Report's own public self-test (the same function as `rnpbench-report selftest`)
        from rnpbench_report import selftest as rs
        return rs.run(a.profile, a.out, a.acceptance_store, a.overlay)[0]
    _profile()
    if a.out and os.path.exists(a.out):
        print("REFUSED: %s exists (self-test records are never overwritten)" % a.out, file=sys.stderr); return 2
    if a.out:
        os.makedirs(a.out)
    tmp = tempfile.mkdtemp(prefix="rnpbench_selftest_")
    try:
        checks = []
        if tool == "diagnose":
            checks.append(diagnose_contract_checks())
            checks.append(diagnose_example(tmp, a.profile))
        rec = {"tool": tool, "profile": a.profile, "profile_sha256": PROFILE_SHA256_AT_FREEZE, "checks": checks,
               "verdict": "PASS" if all(c["ok"] for c in checks) else "FAIL"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for c in checks:
        print("  %-34s %s  %s" % (c["check"], "ok  " if c["ok"] else "FAIL", ", ".join("%s=%s" % (k, c[k]) for k in ("n_values", "n_checks", "n_failed", "n_floats_not_bit_identical", "max_abs_deviation", "verdict", "groups") if k in c)))
    print("%s: RNPLens %s self-test (profile %s)" % (rec["verdict"], tool.capitalize(), a.profile))
    if a.out:
        json.dump(rec, open(os.path.join(a.out, "selftest_record.json"), "w"), indent=1)
    return 0 if rec["verdict"] == "PASS" else 3
