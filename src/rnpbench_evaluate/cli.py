"""rnpbench -- command-line interface.

  rnpbench evaluate --input INPUT.json --out DIR
  rnpbench evaluate --prediction P --reference R.cif --protein-seq SEQ|FASTA --rna-seq SEQ|FASTA --target-id ID --out DIR
  rnpbench validate --input INPUT.json          check an input without scoring
  rnpbench selftest [--profile reference|portable] [--internal-fixtures DIR] [--out DIR]
                                                reproduce the frozen regression fixtures (reference = bit-exact)
  rnpbench provenance [--full]                  pinned frozen sources and what is executed from them

Exit status: 0 success (including a correctly reported NO VALUE), 2 input refused, 3 self-test failed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__


def _seq(v):
    from .contract import read_fasta_or_raw
    if v and os.path.isfile(v):
        return read_fasta_or_raw(open(v).read())
    return (v or "").strip().upper()


def _build_input(a):
    if a.input:
        return a.input, None
    need = [n for n in ("prediction", "reference", "protein_seq", "rna_seq", "target_id") if not getattr(a, n)]
    if need:
        raise SystemExit("rnpbench evaluate: give --input, or all of --prediction --reference --protein-seq --rna-seq --target-id (missing: %s)" % ", ".join("--" + n.replace("_", "-") for n in need))
    d = {"contract": "RNPBENCH_EVALUATE_INPUT_V1", "target_id": a.target_id,
         "prediction": {"path": os.path.abspath(a.prediction), "engine": a.engine},
         "reference": {"path": os.path.abspath(a.reference)},
         "construct": {"protein_sequence": _seq(a.protein_seq), "rna_sequence": _seq(a.rna_seq)},
         "options": {"tolerance": a.tolerance}}
    return d, os.getcwd()


def main(argv=None):
    p = argparse.ArgumentParser(prog="rnpbench", description="RNPBench Evaluate: reference-based evaluation of predicted protein-RNA complexes under the frozen RNPBench rules.")
    p.add_argument("--version", action="version", version="rnpbench-evaluate " + __version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("evaluate", help="evaluate one prediction against one experimental reference")
    e.add_argument("--input", help="input contract JSON (RNPBENCH_EVALUATE_INPUT_V1)")
    e.add_argument("--prediction", help="predicted complex (.pdb or .cif), residues numbered 1..L along each construct")
    e.add_argument("--reference", help="experimental reference (.cif, mmCIF with label_seq_id)")
    e.add_argument("--protein-seq", help="protein construct sequence, or a FASTA file")
    e.add_argument("--rna-seq", help="RNA construct sequence (ACGU), or a FASTA file")
    e.add_argument("--target-id", help="identifier used in the report")
    e.add_argument("--engine", default=None, help="optional: the engine that produced the prediction (recorded only)")
    e.add_argument("--tolerance", type=int, default=0, help="DockQ chain-grouping tolerance; frozen default 0")
    e.add_argument("--out", required=True, help="output directory (must not already hold results)")
    e.add_argument("--workdir", default=None, help="directory for temporary staging files (default: the system temporary directory)")
    e.add_argument("--allow-unpinned", action="store_true", help="run with a DockQ version other than 2.1.3 (recorded in provenance; results are then not the frozen configuration)")
    v = sub.add_parser("validate", help="validate an input contract without scoring")
    v.add_argument("--input", required=True)
    s = sub.add_parser("selftest", help="reproduce the frozen regression fixtures")
    s.add_argument("--profile", choices=("reference", "portable"), default="reference",
                   help="reference: every value bit-identical (reference platform); portable: frozen per-quantity tolerances for unrounded floats, everything else exact")
    s.add_argument("--internal-fixtures", default=os.environ.get("RNPBENCH_INTERNAL_FIXTURES"),
                   help="directory of internal (non-redistributable) fixtures; default $RNPBENCH_INTERNAL_FIXTURES")
    s.add_argument("--out", default=None, help="optional directory for the self-test record and per-fixture results")
    s.add_argument("--allow-unpinned", action="store_true")
    pv = sub.add_parser("provenance", help="print pinned frozen sources")
    pv.add_argument("--full", action="store_true")
    a = p.parse_args(argv)

    from . import contract
    if a.cmd == "validate":
        try:
            d = contract.load(a.input)
        except contract.ContractError as ex:
            print("REFUSED: %s" % ex, file=sys.stderr)
            return 2
        print(json.dumps({"status": "VALID", "target_id": d["target_id"], "checks": d["_checks"]}, indent=1))
        return 0
    if a.cmd == "provenance":
        from . import frozen_loader
        man = frozen_loader.verify_sources()
        if a.full:
            _, rec = frozen_loader.load({"P": None, "REP": None})
            print(json.dumps(rec, indent=1))
        else:
            print(json.dumps({"origin": man.get("origin"), "files": {k: v["sha256"] for k, v in man["files"].items()}}, indent=1))
        return 0
    if a.cmd == "selftest":
        from . import selftest
        print("rnpbench-evaluate %s self-test" % __version__)
        rec, results = selftest.run(allow_unpinned=a.allow_unpinned, profile_name=a.profile, internal_fixtures=a.internal_fixtures)
        print("%s: %d/%d checks (profile %s, sets %s)" % (rec["verdict"], rec["n_passed"], rec["n_checks"], rec["profile"], "+".join(rec["fixture_sets"])))
        print("  checks required to be exact: %d/%d equal" % (rec["n_exact_required_equal"], rec["n_exact_required"]))
        print("  unrounded floats bit-exact: %d/%d" % (rec["n_unrounded_floats_bit_exact"], rec["n_unrounded_floats"]))
        for d in rec["all_deviations"][:12]:
            print("    deviation %-20s %-34s %.3g (tolerance %s) %s" % (d["fixture"], d["check"], d["abs_deviation"], d["tolerance"], "ok" if d["ok"] else "FAIL"))
        print("  all checks bit-exact: %s" % rec["all_bit_exact"])
        for f in rec["failures"][:20]:
            print("  FAIL %s %s expected %r got %r" % (f["fixture"], f["check"], f["expected"], f["got"]))
        if a.out:
            os.makedirs(a.out, exist_ok=True)
            json.dump(rec, open(os.path.join(a.out, "selftest_record.json"), "w"), indent=1)
            from . import report
            for k, r in results.items():
                report.write(r, os.path.join(a.out, k))
        return 0 if rec["verdict"] == "PASS" else 3
    # evaluate
    from . import engine, report
    src, base = _build_input(a)
    try:
        inp = contract.load(src) if isinstance(src, str) else contract.load(src, base_dir=base)
    except contract.ContractError as ex:
        print("REFUSED: %s" % ex, file=sys.stderr)
        return 2
    try:
        r = engine.evaluate(inp, allow_unpinned=a.allow_unpinned, workdir=a.workdir)
        files = report.write(r, a.out)
    except (RuntimeError, FileExistsError) as ex:
        print("REFUSED: %s" % ex, file=sys.stderr)
        return 2
    sys.stdout.write(report.summary_text(r))
    print("wrote: " + ", ".join(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
