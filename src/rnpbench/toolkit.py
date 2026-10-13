"""``rnpbench toolkit version | provenance | selftest | example-contract`` (descriptive; dispatch only)."""
import argparse
import json
import os
import sys


def main(argv):
    ap = argparse.ArgumentParser(prog="rnplens")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("version")
    sub.add_parser("provenance")
    s = sub.add_parser("selftest", help="run every tool's self-test")
    s.add_argument("--profile", choices=("reference", "portable"), default="portable")
    s.add_argument("--evaluate-internal-fixtures", default=None, help="INTERNAL fixture directory for Evaluate")
    e = sub.add_parser("example-contract", help="write the Report example contract with absolute paths")
    e.add_argument("examples_dir", nargs="?", default=None)
    e.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    from rnpbench_core import provenance
    if a.cmd in ("version", "provenance"):
        rec = {"components": provenance.components(), "software_versions": provenance.software_versions()}
        if a.cmd == "provenance":
            rec["frozen_sources_sha256"] = provenance.frozen_sources()
            from . import selftests
            rec["toolkit_example_regression_profile_sha256"] = selftests.PROFILE_SHA256_AT_FREEZE
        print(json.dumps(rec, indent=1))
        return 0
    if a.cmd == "example-contract":
        from . import selftests
        if os.path.exists(a.out):
            print("REFUSED: %s exists" % a.out, file=sys.stderr); return 2
        print(selftests.write_report_contract(a.examples_dir or selftests.EXAMPLES, a.out)); return 0
    from rnpbench_evaluate.cli import main as ev
    from . import selftests
    rcs = {}
    eargs = ["selftest", "--profile", a.profile] + (["--internal-fixtures", a.evaluate_internal_fixtures] if a.evaluate_internal_fixtures else [])
    print("== evaluate"); rcs["evaluate"] = ev(eargs)
    print("== report"); rcs["report"] = selftests.run("report", ["--profile", a.profile])
    print("== diagnose"); rcs["diagnose"] = selftests.run("diagnose", ["--profile", a.profile])
    ok = all(v == 0 for v in rcs.values())
    print("%s: rnplens selftest %s" % ("PASS" if ok else "FAIL", rcs))
    return 0 if ok else 3
