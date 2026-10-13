"""Unified ``rnpbench`` command (dispatch only).

Each ``rnpbench <tool> <verb> ...`` call is translated into the tool's own command line, and that tool's
unchanged ``main()`` runs it. Exit codes are passed through. The translations are listed in ``VERBS``. The only
argument rewritten is ``--out``, accepted by ``report run`` as a synonym for that tool's ``--outdir``.

Backward-compatible aliases (the rnpbench-evaluate 0.1.1 command line). Each prints a one-line notice to
stderr and nothing else differs:
  rnpbench evaluate --input ... | --prediction ...   ->  rnpbench evaluate run ...
  rnpbench validate ...                              ->  rnpbench evaluate validate ...
  rnpbench selftest ...                              ->  rnpbench evaluate selftest ...
  rnpbench provenance ...                            ->  rnpbench evaluate provenance ...
The tools' own entry points remain: rnpbench-evaluate, rnpbench-report, rnpbench-diagnose,
python -m rnpbench_evaluate | rnpbench_report | rnpbench_predict | rnpbench_diagnose.
"""
import sys

from . import __version__

SCOPE = {
    "evaluate": "reference-based accuracy of one prediction against an experimental structure (DockQ route and four-axis geometry route, reported separately)",
    "report": "reference-free, descriptive agreement among existing predictions; agreement is not a calibrated probability that an interface is correct",
    "diagnose": "reference-free validity classes and component disagreement among existing predictions; the RNA-side statement is not validated out of sample",
}

# tool -> verb -> (module, native verb or None for "the tool's own selftest wrapper")
VERBS = {
    "evaluate": {"run": "evaluate", "validate": "validate", "selftest": "selftest", "provenance": "provenance"},
    "report": {"run": "run", "validate": "validate", "selftest": None},
    "diagnose": {"run": "diagnose", "preflight": "preflight", "validity": "validity", "selftest": None},
}
LEGACY_TOP = {"validate": "validate", "selftest": "selftest", "provenance": "provenance"}

USAGE = """usage: rnpbench <tool> <verb> [options]

tools and verbs:
  evaluate  run | validate | selftest | provenance
  report    run | validate | selftest
  diagnose  run | preflight | validity | selftest
  toolkit   version | provenance | selftest

  rnpbench <tool> <verb> --help     options of one verb (the tool's own help)
  rnpbench --version

The three tools answer different questions and their outputs are never combined:
  evaluate  %s
  report    %s
  diagnose  %s
""" % (SCOPE["evaluate"], SCOPE["report"], SCOPE["diagnose"])


def _notice(old, new):
    print("rnpbench: '%s' is the rnpbench-evaluate 0.1.1 form; it now runs '%s' (same behaviour)." % (old, new), file=sys.stderr)


def _evaluate(native, args):
    from rnpbench_evaluate.cli import main
    return main([native] + list(args))


def _report(native, args):
    from rnpbench_report.cli import main
    args = list(args)
    if native == "run":
        args = ["--outdir" if a == "--out" else (a.replace("--out=", "--outdir=", 1) if a.startswith("--out=") else a) for a in args]
    return main([native] + args)


def _diagnose(native, args):
    from rnpbench_diagnose._toolkit import entry
    return entry([native] + list(args))


def _tool_selftest(tool, args):
    from . import selftests
    return selftests.run(tool, list(args))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0 if argv else 2
    if argv[0] == "--version":
        from rnpbench_core import provenance
        print("rnpbench %s" % __version__)
        for d, r in provenance.components().items():
            if d != "rnpbench":
                print("  %-18s %s%s" % (d, r.get("distribution_version") if r.get("installed") else "not installed",
                                        "  (analysis implementation %s)" % r["analysis_implementation_version"] if r.get("analysis_implementation_version") else ""))
        return 0
    tool, rest = argv[0], argv[1:]
    if tool in LEGACY_TOP:
        _notice("rnpbench %s" % tool, "rnpbench evaluate %s" % tool)
        return _evaluate(LEGACY_TOP[tool], rest)
    if tool == "toolkit":
        from . import toolkit
        return toolkit.main(rest)
    if tool not in VERBS:
        print("rnpbench: unknown tool %r\n\n%s" % (tool, USAGE), file=sys.stderr)
        return 2
    if tool == "evaluate" and (not rest or rest[0].startswith("-")) and rest[:1] not in (["-h"], ["--help"]):
        _notice("rnpbench evaluate <options>", "rnpbench evaluate run <options>")
        return _evaluate("evaluate", rest)
    if not rest or rest[0] in ("-h", "--help"):
        print("rnpbench %s: %s\nverbs: %s" % (tool, SCOPE[tool], " | ".join(VERBS[tool])))
        return 0 if rest else 2
    verb, args = rest[0], rest[1:]
    if verb not in VERBS[tool]:
        print("rnpbench %s: unknown verb %r; verbs: %s" % (tool, verb, " | ".join(VERBS[tool])), file=sys.stderr)
        return 2
    native = VERBS[tool][verb]
    if native is None:
        return _tool_selftest(tool, args)
    try:
        return {"evaluate": _evaluate, "report": _report, "diagnose": _diagnose}[tool](native, args)
    except SystemExit as ex:              # Report and Diagnose signal refusals with SystemExit; pass them through
        if isinstance(ex.code, str):
            print(ex.code, file=sys.stderr)
            return 1
        return ex.code if ex.code is not None else 0


if __name__ == "__main__":
    sys.exit(main())
