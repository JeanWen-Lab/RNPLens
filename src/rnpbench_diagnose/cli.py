"""One entry point: preflight, validity, diagnose.

  preflight  REQUEST.json                                   validate a request, print the receipt
  validity   STRUCTURE [STRUCTURE ...]                      classify outputs, technical vs structural
  diagnose   --out DIR --mode MODE STRUCTURE [STRUCTURE ...] validity + disagreement + the report

This command never launches a prediction. `diagnose` refuses an output directory that already holds a
report, and refuses a mode whose statements are not licensed for the structures supplied.
"""
import argparse
import json
import sys

from . import __version__
from .applicability import assess as assess_applicability
from .diagnose import MODES, NotLicensed, diagnose as run_diagnose
from .disagreement import disagreement as run_disagreement
from .preflight import PreflightRefusal, preflight
from .report import record, write
from .validity import summarize, validity


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rnplens diagnose",
                                 description="Reference-free diagnostics for a predicted protein-RNA complex. "
                                             "Launches no prediction.")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="command", required=True)
    p1 = sub.add_parser("preflight", prog="rnplens diagnose preflight", help="validate a request")
    p1.add_argument("request")
    p2 = sub.add_parser("validity", prog="rnplens diagnose validity", help="classify predicted outputs")
    p2.add_argument("structures", nargs="+")
    p3 = sub.add_parser("diagnose", prog="rnplens diagnose run", help="validity, disagreement and the user report")
    p3.add_argument("structures", nargs="+")
    p3.add_argument("--out", required=True)
    p3.add_argument("--mode", required=True, choices=list(MODES))
    p3.add_argument("--target", default=None)
    p3.add_argument("--engine", action="append", default=None,
                    help="engine label per structure, in order; required for cross_engine")
    p3.add_argument("--request", default=None, help="the request to embed as a preflight receipt")
    p3.add_argument("--allow-outside-validated-domain", action="store_true",
                    help="run even when the inputs fall outside the validated applicability domain (engine, number "
                         "of candidates, chain composition); the report then states this prominently")
    a = ap.parse_args(argv)

    if a.command == "preflight":
        try:
            print(json.dumps(preflight(json.load(open(a.request, encoding="utf-8"))), indent=1))
        except PreflightRefusal as ex:
            raise SystemExit("PREFLIGHT REFUSED: %s" % ex)
        return 0

    if a.command == "validity":
        recs = [validity(s) for s in a.structures]
        print(json.dumps({"per_structure": recs, "summary": summarize(recs)}, indent=1))
        return 0

    recs = [validity(s) for s in a.structures]
    vsum = summarize(recs)
    good = [r["path"] for r in recs if r["classification"] == "VALID"]
    declared = None
    if a.mode == "within_engine" and a.engine:
        if len(set(a.engine)) != 1 or len(a.engine) not in (1, len(a.structures)):
            raise SystemExit("DIAGNOSE REFUSED: within_engine mode compares candidates of ONE engine; give --engine "
                             "once (or the same label once per structure)")
        declared = a.engine[0]
    if a.mode == "cross_engine":
        if not a.engine or len(a.engine) != len(a.structures):
            raise SystemExit("DIAGNOSE REFUSED: cross_engine mode needs one --engine label per structure, "
                             "in the order the structures are given")
        lab = dict(zip(a.structures, a.engine))
        n_eng = len({lab[g] for g in good})
        if n_eng < 3:
            raise SystemExit("DIAGNOSE REFUSED: cross_engine statements were licensed on four engines and "
                             "require at least three; %d engine(s) supplied a valid structure" % n_eng)
        if len({lab[g] for g in good}) != len(good):
            raise SystemExit("DIAGNOSE REFUSED: cross_engine mode expects one structure per engine; "
                             "supply the engine's designated output, not several candidates")
    else:
        lab = None
        if len(good) < 2:
            raise SystemExit("DIAGNOSE REFUSED: within_engine disagreement needs at least two valid "
                             "structures; %d supplied" % len(good))
    ap = assess_applicability(a.mode, good, engine_of=lab, declared_engine=declared)
    if ap["status"] != "inside_validated_domain":
        if not a.allow_outside_validated_domain:
            raise SystemExit("DIAGNOSE REFUSED: outside the validated applicability domain:\n  - "
                             + "\n  - ".join(ap["reasons_outside"])
                             + "\nRe-run with --allow-outside-validated-domain to compute the values anyway; the report "
                               "will then be marked as outside the validated domain.")
        ap["outside_domain_accepted_by_user"] = True
    dis = run_disagreement(good, labels=lab)
    try:
        dg = run_diagnose(a.mode, dis)
    except NotLicensed as ex:
        raise SystemExit("DIAGNOSE REFUSED: %s" % ex)
    pf = None
    if a.request:
        try:
            pf = preflight(json.load(open(a.request, encoding="utf-8")))
        except PreflightRefusal as ex:
            raise SystemExit("PREFLIGHT REFUSED: %s" % ex)
    rec = record(pf, vsum, dis, dg, target=a.target,
                 engines=set(a.engine) if a.engine else None, applicability=ap)
    try:
        files = write(rec, a.out)
    except FileExistsError as ex:
        raise SystemExit("DIAGNOSE REFUSED: %s" % ex)
    print("wrote %s to %s" % (", ".join(files), a.out))
    if ap["status"] != "inside_validated_domain":
        print("  WARNING: outside the validated applicability domain (accepted with --allow-outside-validated-domain)")
    for s in dg["statements"]:
        print("  " + (s["text"] if s.get("available") else "%s: not available" % s["statement"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
