"""``rnplens`` command: the public entry point (dispatch only).

``rnplens <tool> <verb> ...`` runs the same code path as the internally qualified ``rnpbench <tool> <verb> ...``
(RNPBench toolkit 0.2.0.dev1), whose translation into each tool's own, unchanged command line is defined in
``rnpbench.cli``. Nothing is computed here, no output of one tool is combined with another's, and exit codes are
passed through. The only additions are this help text, ``rnplens --version`` and ``rnplens provenance``, which
also record the RNPLens release version.
"""
import json
import sys

from . import IMPLEMENTATION, __version__

TOOLS = {
    "evaluate": ("run | validate | selftest | provenance",
                 "Reference-based structural evaluation of ONE prediction against an experimental structure "
                 "(DockQ route and geometry route, reported separately; unscoreable outputs are NO VALUE, never 0)."),
    "report": ("run | validate | selftest",
               "Reference-free, descriptive agreement among several predictions of one complex (binding surface, "
               "RNA pose, residue-nucleotide contacts). Agreement is not a probability of correctness."),
    "diagnose": ("run | preflight | validity | selftest",
                 "Reference-free output-validity classes and candidate-disagreement diagnostics. Disagreement is a "
                 "review flag, not a calibrated correctness score; low disagreement does not guarantee accuracy."),
}
TOP = {
    "selftest": "run the self-tests of all three tools (no internal file needed)",
    "provenance": "RNPLens version, component versions, dependency versions, SHA-256 of the frozen scorers",
    "example-contract": "write the bundled Report example contract with absolute paths",
}

USAGE = """usage: rnplens <command> [options]

RNPLens assesses protein-RNA complex structures that were already predicted by other methods.
It does not predict structures.

tools (each answers a different question; their outputs are never combined):
  evaluate   %s
             needs an experimental reference structure
  report     %s
             no reference needed
  diagnose   %s
             no reference needed

other commands:
  selftest          %s
  provenance        %s
  example-contract  %s

  rnplens <tool> --help           the tool's verbs
  rnplens <tool> <verb> --help    the verb's options
  rnplens --version
""" % (TOOLS["evaluate"][0], TOOLS["report"][0], TOOLS["diagnose"][0], TOP["selftest"], TOP["provenance"], TOP["example-contract"])


def _tool_help(tool):
    verbs, scope = TOOLS[tool]
    return ("usage: rnplens %s <verb> [options]\n\n%s\n\nverbs: %s\n\n"
            "Run 'rnplens %s <verb> --help' for the options of one verb (the help text of the underlying "
            "RNPLens %s component)." % (tool, scope, verbs, tool, tool.capitalize()))


def _version():
    lines = ["rnplens %s" % __version__, "  implementation: %s" % IMPLEMENTATION]
    import importlib
    for mod, attr in (("rnpbench_core", "__version__"), ("rnpbench_evaluate", "__version__"),
                      ("rnpbench_report.agreement", "VERSION"), ("rnpbench_diagnose", "__version__")):
        lines.append("  %-26s %s" % (mod.split(".")[0], getattr(importlib.import_module(mod), attr)))
    import platform
    from importlib import metadata
    def dv(d):
        try:
            return metadata.version(d)
        except metadata.PackageNotFoundError:
            return "not installed"
    lines.append("  python %s; %s" % (platform.python_version(), ", ".join(
        "%s %s" % (d, dv(d)) for d in ("DockQ", "gemmi", "biopython", "numpy", "scipy", "matplotlib"))))
    return "\n".join(lines)


def _provenance():
    import importlib
    from rnpbench_core import provenance
    from rnpbench import selftests
    rec = {
        "rnplens_version": __version__,
        "implementation": IMPLEMENTATION,
        "component_module_versions": {
            m: getattr(importlib.import_module(m if a != "VERSION" else m + ".agreement"), a)
            for m, a in (("rnpbench", "__version__"), ("rnpbench_core", "__version__"), ("rnpbench_evaluate", "__version__"),
                         ("rnpbench_report", "VERSION"), ("rnpbench_diagnose", "__version__"))},
        "note": "components are distributed inside the rnplens distribution, so their own distribution_version "
                "fields below are null; component_module_versions identifies them",
        "components": provenance.components(),
        "software_versions": provenance.software_versions(),
        "frozen_sources_sha256": provenance.frozen_sources(),
        "toolkit_example_regression_profile_sha256": selftests.PROFILE_SHA256_AT_FREEZE,
    }
    print(json.dumps(rec, indent=1))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0 if argv else 2
    if argv[0] in ("-V", "--version"):
        print(_version())
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "provenance":
        if rest and rest[0] in ("-h", "--help"):
            print("usage: rnplens provenance\n\n%s" % TOP["provenance"]); return 0
        if rest:
            print("rnplens provenance: takes no arguments", file=sys.stderr); return 2
        return _provenance()
    if cmd in ("selftest", "example-contract"):
        from rnpbench import toolkit
        if cmd == "selftest" and rest[:1] in (["-h"], ["--help"]):
            print("usage: rnplens selftest [--profile {portable,reference}] [--evaluate-internal-fixtures DIR]\n\n"
                  "Runs Evaluate's regression fixtures, Report's public self-test and Diagnose's contract checks and\n"
                  "example regression. 'portable' (default) applies the frozen portable numerical profile;\n"
                  "'reference' requires bit-identical values and is meaningful only on the reference platform.")
            return 0
        return toolkit.main([cmd] + rest)
    if cmd not in TOOLS:
        print("rnplens: unknown command %r\n\n%s" % (cmd, USAGE), file=sys.stderr)
        return 2
    if not rest or rest[0] in ("-h", "--help"):
        print(_tool_help(cmd))
        return 0 if rest else 2
    if rest[0].startswith("-"):
        print("rnplens %s: a verb is required (%s); for example 'rnplens %s %s ...'"
              % (cmd, TOOLS[cmd][0], cmd, TOOLS[cmd][0].split(" | ")[0]), file=sys.stderr)
        return 2
    from rnpbench import cli as rnpbench_cli
    return rnpbench_cli.main([cmd] + rest)


if __name__ == "__main__":
    sys.exit(main())
