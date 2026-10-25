"""Command line: validate a contract, run the analysis, write the report.

  rnplens report validate CONTRACT.json
  rnplens report run      CONTRACT.json --out DIR [--nproc N]
  rnplens report selftest [--profile portable|reference] [--out DIR]
                                      [--acceptance-store DIR --overlay DIR]   (internal acceptance suite)

Exit codes are meaningful: 0 success, 2 contract error or refused invocation (including an existing output
directory, and an engine-confidence input that is not declared and verified), 3 no eligible output (coverage
failure, not an accuracy failure), 4 selftest failure.

Changed in RNPLens 0.4 (owner-authorised correction, 2026-10-24): the engine's own confidence file is a declared
input (contract.py: confidence_path, confidence_sha256). `run` and `validate` refuse with exit 2, before any
output directory exists, when a required confidence input is missing, undeclared or does not verify;
`--reduced-evidence` runs the coordinate-only analysis anyway and labels it, in the result, the page and on
stdout, as not a fully qualified analysis. Nothing else about the command changed: a complete, declared and
verified input set produces exactly the output it produced before.

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
    ap = argparse.ArgumentParser(prog="rnplens report")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", prog="rnplens report validate"); v.add_argument("contract")
    v.add_argument("--no-verify-digests", action="store_true")
    r = sub.add_parser("run", prog="rnplens report run"); r.add_argument("contract")
    r.add_argument("--outdir", required=True, help="output directory; must not exist (rnplens report run also accepts --out)")
    r.add_argument("--nproc", type=int, default=1); r.add_argument("--no-report", action="store_true")
    for _p in (v, r):
        _p.add_argument("--reduced-evidence", action="store_true",
                        help="accept an engine confidence input that is not declared and verified, and label the "
                             "result, the page and the printed summary as not a fully qualified analysis "
                             "(the agreement analysis reads coordinates only and is unaffected)")
    s = sub.add_parser("selftest", prog="rnplens report selftest")
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

    # The engine-confidence files are declared inputs. Checked here, before an output directory is created and
    # before any structure file is parsed, so a run that cannot verify its evidence produces nothing at all.
    findings = contract.confidence_input_findings(c)
    if findings and not a.reduced_evidence:
        print(contract.diagnostic(findings, command="rnplens report %s" % a.cmd), file=sys.stderr)
        return 2

    if a.cmd == "validate":
        declared = [{"engine": o["engine"], "execution": o["execution"], "confidence_path": o["confidence_path"],
                     "confidence_sha256": o["confidence_sha256"]}
                    for o in c["outputs"] if o.get("confidence_path")]
        print(json.dumps({"case_id": c["case_id"], "n_outputs": len(c["outputs"]),
                          "engines": sorted({o["engine"] for o in c["outputs"]}),
                          "construct": c["construct"],
                          "confidence_inputs": {"status": contract.REDUCED_EVIDENCE_STATUS if findings else "VERIFIED",
                                                "declared_and_verified": declared, "not_verified": findings},
                          "status": "CONTRACT_VALID"}, indent=1))
        return 0

    res = agreement.run(c, nproc=a.nproc, confidence_findings=findings)
    changed = [r_ for r_ in res["per_output"] if r_["state"] == "CONFIDENCE_CHECKSUM_MISMATCH"]
    if changed:
        print("rnplens report run: %s: CONFIDENCE_INPUT_CHANGED_DURING_RUN\n"
              "A declared engine-confidence input changed between contract validation and reading it: %s. "
              "Nothing was written.\n%s"
              % (contract.STATUS,
                 ", ".join("%s %s" % (r_["engine"], r_["execution"]) for r_ in changed), contract.SUMMARY_LINE),
              file=sys.stderr)
        return 2
    p = agreement.write(res, a.outdir)
    report_path = None
    if not a.no_report:
        try:
            from . import report
            report_path = report.write(res, a.outdir)
        except ImportError as ex:
            print("HTML report skipped: %s. The JSON result is complete and unaffected." % ex, file=sys.stderr)
    s_ = res["summary"]
    blk = {"case_id": s_["case_id"], "eligible": "%d/%d" % (s_["n_eligible_outputs"], s_["n_declared_outputs"]),
           "eligible_engines": s_["eligible_engines"],
           "median_surface_agreement": s_["median_pairwise_surface_agreement"],
           "median_register_agreement": s_["median_pairwise_register_agreement"],
           "n_hypotheses": s_["n_hypotheses_at_primary_threshold"],
           "no_interface_contact": s_["outputs_with_no_interface_contact"],
           "result": p, "report": report_path}
    if findings:                     # a pipeline reading stdout sees the status, not only a reader of the page
        blk["NATIVE_CONFIDENCE_INPUTS_STATUS"] = contract.REDUCED_EVIDENCE_STATUS
        blk["native_confidence_inputs_not_verified"] = findings
    print(json.dumps(blk, indent=1))
    return 0 if s_["n_eligible_outputs"] else 3


if __name__ == "__main__":
    sys.exit(main())
