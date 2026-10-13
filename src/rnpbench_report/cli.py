"""Command line: validate a contract, run the analysis, write the report.

  python -m rnpbench_predict validate CONTRACT.json
  python -m rnpbench_predict run      CONTRACT.json --outdir DIR [--nproc N]
  python -m rnpbench_predict selftest [--profile portable|reference] [--out DIR]
                                      [--acceptance-store DIR --overlay DIR]   (internal acceptance suite)

Exit codes are meaningful: 0 success, 2 contract error or refused invocation (including an existing output
directory), 3 no eligible output (coverage failure, not an accuracy failure), 4 selftest failure.

Changed in toolkit 0.2.0.dev1 (analysis modules unchanged):
  * `run` refuses if --outdir already exists (RNPBENCH_REPORT_OUTPUT_PROTECTION_V1); there is no overwrite option.
  * `selftest` is the public self-test (selftest.py; RNPBENCH_REPORT_PUBLIC_SELFTEST_SPEC_V1) and needs no
    internal file. The original 888-check acceptance suite runs only with --acceptance-store and --overlay.
"""
import argparse
import json
import os
import sys

from . import agreement, contract


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rnpbench_predict")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate"); v.add_argument("contract")
    v.add_argument("--no-verify-digests", action="store_true")
    r = sub.add_parser("run"); r.add_argument("contract"); r.add_argument("--outdir", required=True)
    r.add_argument("--nproc", type=int, default=1); r.add_argument("--no-report", action="store_true")
    s = sub.add_parser("selftest")
    s.add_argument("--profile", choices=("portable", "reference"), default="portable")
    s.add_argument("--out", "--outdir", dest="out", default=None, help="directory for the self-test record (must not exist)")
    s.add_argument("--acceptance-store", default=None, help="INTERNAL: frozen development store (not distributed)")
    s.add_argument("--overlay", default=None, help="INTERNAL: report qualification overlay (acceptance suite, benchmark adapter)")
    a = ap.parse_args(argv)

    if a.cmd == "selftest":
        from . import selftest
        return selftest.run(a.profile, a.out, a.acceptance_store, a.overlay)[0]

    if a.cmd == "run" and os.path.lexists(a.outdir):
        print("REFUSED: output directory exists: %s. Report never writes into an existing directory; "
              "give a new --outdir." % a.outdir, file=sys.stderr)
        return 2

    try:
        c = contract.load(a.contract, verify_digests=not getattr(a, "no_verify_digests", False))
    except contract.ContractError as ex:
        print("CONTRACT ERROR: %s" % ex, file=sys.stderr)
        return 2
    if a.cmd == "validate":
        print(json.dumps({"case_id": c["case_id"], "n_outputs": len(c["outputs"]),
                          "engines": sorted({o["engine"] for o in c["outputs"]}),
                          "construct": c["construct"], "status": "CONTRACT_VALID"}, indent=1))
        return 0

    res = agreement.run(c, nproc=a.nproc)
    p = agreement.write(res, a.outdir)
    report_path = None
    if not a.no_report:
        try:
            from . import report
            report_path = report.write(res, a.outdir)
        except ImportError as ex:
            print("HTML report skipped: %s. The JSON result is complete and unaffected." % ex, file=sys.stderr)
    s_ = res["summary"]
    print(json.dumps({"case_id": s_["case_id"], "eligible": "%d/%d" % (s_["n_eligible_outputs"], s_["n_declared_outputs"]),
                      "eligible_engines": s_["eligible_engines"],
                      "median_surface_agreement": s_["median_pairwise_surface_agreement"],
                      "median_register_agreement": s_["median_pairwise_register_agreement"],
                      "n_hypotheses": s_["n_hypotheses_at_primary_threshold"],
                      "no_interface_contact": s_["outputs_with_no_interface_contact"],
                      "result": p, "report": report_path}, indent=1))
    return 0 if s_["n_eligible_outputs"] else 3


if __name__ == "__main__":
    sys.exit(main())
