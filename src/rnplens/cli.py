"""``rnplens`` command: the public entry point (dispatch only).

``rnplens <tool> <verb> ...`` runs the same code path as the internally qualified ``rnpbench <tool> <verb> ...``
(RNPBench toolkit 0.2.0.dev1), whose translation into each tool's own, unchanged command line is defined in
``rnpbench.cli``. Nothing is computed here, no output of one tool is combined with another's, and exit codes are
passed through. The only additions are this help text, ``rnplens --version`` and ``rnplens provenance``, which
also record the RNPLens release version.

0.4: Evaluate's four-axis geometry route is BLOCKED in the public interface: ``rnplens evaluate run`` publishes
DockQ-route results with every geometry value removed and an explicit BLOCKED status, and the self-tests do not
display geometry values (``rnplens.geometry_block``; the frozen component is unchanged).

0.4: Diagnose is BLOCKED in the public interface until it is re-qualified. ``rnplens diagnose run | preflight |
validity`` refuse with exit 5 (``capabilities.DIAGNOSE_BLOCKED_EXIT``) before the component is called, so nothing
is read or written; ``rnplens diagnose selftest`` and ``rnplens selftest`` still run Diagnose's internal contract
checks. The frozen component itself is unchanged.
"""
import json
import os
import sys

from . import IMPLEMENTATION, __version__, capabilities

TOOLS = {
    "evaluate": ("run | validate | selftest | provenance",
                 "Reference-based structural evaluation of ONE prediction against an experimental structure "
                 "(DockQ route: DockQ, DockQ class, fnat, iRMSD, LRMSD; unscoreable outputs are NO VALUE, never 0). The "
                 "four-axis geometry route is BLOCKED in 0.4 by the residue-correspondence defect: no geometry value is "
                 "shown or written."),
    "report": ("run | validate | selftest",
               "Reference-free, descriptive agreement among several predictions of one complex (binding surface, "
               "RNA pose, residue-nucleotide contacts). Agreement is not a probability of correctness."),
    "diagnose": ("run | preflight | validity | selftest",
                 "BLOCKED in RNPLens 0.4 until re-qualification: 'run', 'preflight' and 'validity' refuse with exit 5 "
                 "and read or write nothing; 'selftest' runs the internal contract checks only. (rc3 scope, for "
                 "reference: reference-free output-validity classes and candidate-disagreement diagnostics; "
                 "disagreement is a review flag, not a calibrated correctness score.)"),
}
WORKFLOW = {
    "import": "inventory engine output folders, check chains against the construct, write a checksummed project",
    "analyse": "run Report and (with --reference) Evaluate on a project and build one traced summary (Diagnose BLOCKED in 0.4)",
    "compare": "matched before/after Evaluate of two prediction sets of the same targets",
}
INTERACTIVE = {   # 0.4 development: command -> (module, one-line help); each module provides main(argv)
    "region": ("region", "contacts in a declared RNA (and protein) range: shared and run-specific, with provenance"),
    "group": ("grouping", "group structures into binding hypotheses (surface, then contact register); no group is ranked"),
    "group-diff": ("grouping", "shared and group-specific contacts between two hypothesis groups"),
    "explain": ("evidence_query", "trace a reported value back to its files, structures, definition and limitations"),
    "export-methods": ("methods_export", "deterministic Methods draft and provenance manifest from execution records"),
    "clarify": ("clarify", "answer a pending clarification for a project and resume"),
    "update": ("incremental", "add, change or remove prediction runs in a project and recompute only what changed"),
    "view": ("viewer", "offline local Mol* page of the project's structures with Report's contacts highlighted "
             "(automatically tested; basic display and interaction confirmed manually by the owner on macOS "
             "(2026-10-18); switching between binding-hypothesis representatives and offline operation not yet "
             "confirmed manually; not fully visually qualified)"),
    "doctor": ("doctor", "check the installation, platform and optional Codex setup (READY / ACTION REQUIRED / UNSUPPORTED)"),
    "assist": ("assist", "question menu over a project (no language model needed); optional natural-language mode"),
    "relink": ("portability", "record where a copied or moved project finds its input files (each verified by SHA-256)"),
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
             needs an experimental reference structure (0.4: geometry route BLOCKED; DockQ route only)
  report     %s
             no reference needed
  diagnose   %s
             0.4: BLOCKED (run, preflight, validity exit 5); selftest = internal contract checks only

workflow commands (0.3 development; built only on the tools above):
  import            %s
  analyse           %s
  compare           %s

interactive commands (0.4 development):
%s

other commands:
  selftest          %s
  provenance        %s
  example-contract  %s

  rnplens <tool> --help           the tool's verbs
  rnplens <tool> <verb> --help    the verb's options
  rnplens --version
""" % (TOOLS["evaluate"][0], TOOLS["report"][0], TOOLS["diagnose"][0], WORKFLOW["import"], WORKFLOW["analyse"],
       WORKFLOW["compare"], "\n".join("  %-17s %s" % (k, v[1]) for k, v in INTERACTIVE.items()), TOP["selftest"], TOP["provenance"], TOP["example-contract"])


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

_FASTA_EXT = (".fa", ".fasta", ".fna", ".faa", ".txt", ".seq")


def _looks_like_path(v):
    return bool(v) and (os.sep in v or "/" in v or v.lower().endswith(_FASTA_EXT))


def _positional(args, with_value=()):
    """First argument that is neither an option nor an option's value."""
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a.startswith("-"):
            skip = a in with_value
            continue
        return a
    return None


def _need_file(what, p):
    if p is None:
        return None
    if not os.path.exists(p):
        return "%s not found: %s" % (what, p)
    if not os.path.isfile(p):
        return "%s is a folder, not a file: %s" % (what, p)
    return None


def _need_project(p, what="project"):
    if p is None:
        return None
    if not os.path.isdir(p):
        return "%s folder not found: %s" % (what, p) if not os.path.exists(p) else "%s is a file, not a folder: %s" % (what, p)
    if not os.path.isfile(os.path.join(p, "manifest.json")):
        return "%s is not an RNPLens project (no manifest.json); create one with 'rnplens import'" % p
    return None


def _missing_dependencies():
    """Required packages that cannot be imported here (checked without importing them). -> [(name, qualified version)]"""
    import importlib.util
    from .doctor import REQUIRED
    missing = []
    for name, version in REQUIRED:
        mod = {"biopython": "Bio"}.get(name, name)
        try:
            found = sys.modules.get(mod, True) is not None and importlib.util.find_spec(mod) is not None
        except (ImportError, ValueError, AttributeError):
            found = False
        if not found:
            missing.append((name, version))
    return missing


def _dependency_text(missing):
    return ("rnplens: required package(s) not installed: %s. Nothing was run.\n"
            "  Install them:  python -m pip install %s\n"
            "  or reinstall RNPLens with its dependencies (python -m pip install <rnplens wheel or sdist>, or from a clone\n"
            "  python -m pip install -e \".[html]\"; docs/installation.md). 'rnplens doctor' checks the whole installation."
            % (", ".join("%s (qualified %s)" % m for m in missing), " ".join("'%s==%s'" % m for m in missing)))


def _input_problem(cmd, rest):
    """0.4 usability: a missing or wrong input path is refused before anything runs (no traceback). -> message or None."""
    if any(a in ("-h", "--help") for a in rest):
        return None
    verb = rest[0] if rest else None
    if cmd == "evaluate" and verb in ("run", "validate"):
        for o, what in (("--input", "input contract"), ("--prediction", "prediction"), ("--reference", "reference")):
            m = _need_file(what, _opt(rest, o))
            if m:
                return m
        for o in ("--protein-seq", "--rna-seq"):
            v = _opt(rest, o)
            if _looks_like_path(v) and not os.path.isfile(v):
                return "%s file not found: %s" % (o[2:], v)
    if cmd == "report" and verb in ("run", "validate"):
        c = _positional(rest[1:], ("--outdir", "--out", "--nproc"))
        m = _need_file("contract", c)
        if m:
            return m
        if c:
            try:
                json.load(open(c, encoding="utf-8"))
            except (ValueError, UnicodeDecodeError) as ex:
                return "contract is not valid JSON (%s): %s" % (ex, c)
    if cmd == "compare":
        for o in ("--before", "--after", "--references"):
            m = _need_file(o[2:] + " table", _opt(rest, o))
            if m:
                return m
    if cmd == "example-contract":
        d = _positional(rest, ("--out",))
        if d is not None and not os.path.isfile(os.path.join(d, "report_7K9D", "contract_template.json")):
            return "not an RNPLens examples folder (no report_7K9D/contract_template.json): %s" % d
    if cmd == "analyse":
        m = _need_project(_positional(rest, ("--out", "--reference", "--nproc"))) or _need_file("reference", _opt(rest, "--reference"))
        if m:
            return m
    if cmd == "update":
        m = _need_file("reference", _opt(rest, "--reference"))
        if m:
            return m
    if cmd == "export-methods":
        m = _need_project(_opt(rest, "--project"))
        if m:
            return m
        for i, a in enumerate(rest):
            d = rest[i + 1] if a == "--run-dir" and i + 1 < len(rest) else (a.split("=", 1)[1] if a.startswith("--run-dir=") else None)
            if d is not None and not os.path.isdir(d):
                return "assistant run folder not found: %s" % d
    return None


def main(argv=None):
    if argv is None:                     # process entry (console script, python -m rnplens): deterministic log order
        from . import ordered_output
        ordered_output.install()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0 if argv else 2
    if argv[0] in ("-V", "--version"):
        missing = _missing_dependencies()
        if missing:
            print(_dependency_text(missing), file=sys.stderr)
            return 3
        print(_version())
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd != "doctor":
        missing = _missing_dependencies()
        if missing:
            print(_dependency_text(missing), file=sys.stderr)
            return 3
    problem = _input_problem(cmd, rest)
    if problem:
        print("rnplens %s: refused: %s (nothing was run)" % (cmd, problem), file=sys.stderr)
        return 2
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
                  "example regression (internal software checks on bundled data; Diagnose is BLOCKED as a user workflow in 0.4).\n"
                  "'portable' (default) applies the frozen portable numerical profile;\n"
                  "'reference' requires bit-identical values and is meaningful only on the reference platform.")
            return 0
        if cmd == "selftest":                # display filtered: no four-axis geometry value is shown (0.4)
            from . import geometry_block
            return geometry_block.run_selftest([cmd] + rest, toolkit=True)
        return toolkit.main([cmd] + rest)
    if cmd in WORKFLOW:
        from importlib import import_module
        mod = {"import": "importer", "analyse": "analyse", "compare": "compare"}[cmd]
        return _portable(lambda: import_module("rnplens." + mod).main(rest))
    if cmd in INTERACTIVE:
        from importlib import import_module
        mod = INTERACTIVE[cmd][0]
        try:
            m = import_module("rnplens." + mod)
        except ImportError as ex:
            print("rnplens %s: not available in this installation (%s)" % (cmd, ex), file=sys.stderr)
            return 2
        return _portable(lambda: m.main(rest) if cmd != "group-diff" else m.main_diff(rest))
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
    if cmd == "diagnose" and rest[0] in capabilities.DIAGNOSE_BLOCKED_VERBS:
        if "-h" in rest or "--help" in rest:
            print("usage: rnplens diagnose %s ...\n\n%s\nExit code when run: %d (%s)." % (
                rest[0], capabilities.diagnose_blocked_text("diagnose " + rest[0]), capabilities.DIAGNOSE_BLOCKED_EXIT,
                capabilities.DIAGNOSE_BLOCKED_STATUS))
            return 0
        print(capabilities.diagnose_blocked_text("diagnose " + rest[0]), file=sys.stderr)
        return capabilities.DIAGNOSE_BLOCKED_EXIT
    if cmd == "diagnose" and rest[0] == "selftest" and not any(x in ("-h", "--help") for x in rest):
        # 0.4: Diagnose is BLOCKED; its self-test still runs, and the display masks its interpretation statements
        from . import geometry_block
        return geometry_block.run_selftest(rest, tool="diagnose")
    if cmd == "evaluate" and rest[0] in ("run", "selftest"):
        # 0.4: the four-axis geometry route is BLOCKED in everything shown or written (rnplens.geometry_block);
        # the frozen component runs unchanged into a private directory and its output is published filtered
        from . import geometry_block
        if rest[0] == "selftest":
            return geometry_block.run_selftest(rest)
        rc = geometry_block.run_evaluate(rest)
        if rc == 0 and not any(a in ("-h", "--help") for a in rest):
            _write_run_record(cmd, rest, note=geometry_block.RUN_RECORD_NOTE)
        return rc
    from rnpbench import cli as rnpbench_cli
    rc = rnpbench_cli.main([cmd] + rest)
    if rc == 0 and rest[0] == "run":
        _write_run_record(cmd, rest)
    return rc


def _portable(fn):
    """Run a command; a portability refusal (missing or changed recorded input files) prints its listing, exit 6."""
    from .portability import PortabilityError
    try:
        return fn()
    except PortabilityError as ex:
        print(str(ex), file=sys.stderr)
        return ex.exit_code


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


def _write_run_record(tool, args, note=None):
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
           "note": note or "written by the rnplens command after the tool finished; the tool's own result files are unchanged"}
    with open(os.path.join(out, RUN_RECORD), "x", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
        fh.write("\n")


if __name__ == "__main__":
    sys.exit(main())
