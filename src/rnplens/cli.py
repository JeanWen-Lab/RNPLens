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
    rc = rnpbench_cli.main([cmd] + rest)
    if rc == 0 and rest[0] == "run":
        _write_run_record(cmd, rest)
    return rc


RUN_RECORD = "rnplens_run.json"


def _sha(p):
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _opt(args, *names):
    for i, a in enumerate(args):
        for n in names:
            if a == n and i + 1 < len(args):
                return args[i + 1]
            if a.startswith(n + "="):
                return a.split("=", 1)[1]
    return None


def _write_run_record(tool, args):
    """After a successful `run`, write rnplens_run.json into its output directory: the RNPLens release, the command,
    and the SHA-256 of every input and output file. Descriptive only; it never changes or replaces a result file."""
    import datetime
    import os
    out = _opt(args, "--out", "--outdir")
    if not out or not os.path.isdir(out) or os.path.exists(os.path.join(out, RUN_RECORD)):
        return
    files = [a for a in args[1:] if not a.startswith("-") and os.path.isfile(a)]
    for flag in ("--input", "--prediction", "--reference", "--protein-seq", "--rna-seq", "--request"):
        v = _opt(args, flag)
        if v and os.path.isfile(v):
            files.append(v)
    referenced = []
    for f in list(files):
        if f.endswith(".json"):
            try:
                c = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            base = os.path.dirname(os.path.abspath(f))
            cand = [c.get(k, {}).get("path") for k in ("prediction", "reference") if isinstance(c.get(k), dict)]
            cand += [o.get(k) for o in c.get("outputs", []) if isinstance(o, dict) for k in ("structure_path", "confidence_path")]
            for q in cand:
                if isinstance(q, str):
                    for r in (q, os.path.join(base, q)):
                        if os.path.isfile(r):
                            referenced.append(r); break
    seen, inputs = set(), []
    for f in files + referenced:
        a = os.path.abspath(f)
        if a not in seen:
            seen.add(a); inputs.append({"path": a, "sha256": _sha(a)})
    outputs = [{"file": os.path.relpath(os.path.join(d, f), out), "sha256": _sha(os.path.join(d, f))}
               for d, _, fs in os.walk(out) for f in sorted(fs) if f != RUN_RECORD]
    rec = {"record": "rnplens-run-record-1", "rnplens_version": __version__,
           "implementation": IMPLEMENTATION, "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "command": ["rnplens", tool] + list(args), "working_directory": os.getcwd(),
           "inputs": inputs, "outputs": sorted(outputs, key=lambda x: x["file"]),
           "note": "written by the rnplens command after the tool finished; the tool's own result files are unchanged"}
    with open(os.path.join(out, RUN_RECORD), "x", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
        fh.write("\n")


if __name__ == "__main__":
    sys.exit(main())
