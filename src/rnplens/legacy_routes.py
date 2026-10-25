"""0.4 refusal of the components' own command lines where they would show a BLOCKED result.

RNPLens 0.4 distributes the qualified component packages (``rnpbench``, ``rnpbench_core``, ``rnpbench_evaluate``,
``rnpbench_report``, ``rnpbench_diagnose``) unchanged as libraries, and its only supported command is ``rnplens``.
In 0.4 the four-axis geometry route of Evaluate and the user-facing Diagnose workflow are BLOCKED; ``rnplens``
enforces that in everything it shows or writes. The components' own command lines (``python -m rnpbench ...``,
``python -m rnpbench_evaluate ...``, ``python -m rnpbench_diagnose ...``, the research batch drivers of the frozen
sources, or the same files run by path) predate that block and would bypass it. Each component package calls
``refuse_blocked_route()`` when it is imported; it inspects only how the *interpreter* was started
(``sys.orig_argv``) and, if the process was launched as one of those command lines with a verb that would show a
blocked result, prints why and exits with status 5 before anything is computed, read or written.

Not affected: importing the packages from Python code (the library API, used by ``rnplens`` itself in-process and
through ``python -c``), ``rnplens ...``, ``python -m rnplens ...``, test runners, and component verbs that show
nothing blocked (``validate``, ``provenance``, help, ``--version``, and every Report verb: Report is qualified).
Standard library only; this module imports nothing from RNPLens or the components.
"""
import os
import sys

EXIT_BLOCKED = 5            # = rnplens.capabilities.DIAGNOSE_BLOCKED_EXIT (asserted by tests)
STATUS = "LEGACY_ROUTE_REFUSED"
COMPONENTS = ("rnpbench", "rnpbench_core", "rnpbench_evaluate", "rnpbench_report", "rnpbench_diagnose")
_HELP = ("-h", "--help", "help", "--version")
_PY_OPT_WITH_ARG = "XW"      # CPython short options that take an argument (-X opt, -W arg)
_PY_LONG_WITH_ARG = ("--check-hash-based-pycs",)

REASONS = {
    "geometry": ("it would compute and show Evaluate's four-axis geometry route, which is BLOCKED in RNPLens 0.4 "
                 "(residue-correspondence defect).",
                 "rnplens evaluate run | selftest   (DockQ route; geometry withheld and marked BLOCKED)"),
    "diagnose": ("it would run the Diagnose workflow or show its interpretation, which is BLOCKED in RNPLens 0.4 "
                 "until re-qualification.",
                 "rnplens diagnose selftest   (internal contract checks only; run/preflight/validity refuse)"),
    "toolkit": ("it would run every component's self-test and show results that are BLOCKED in RNPLens 0.4 "
                "(four-axis geometry, Diagnose interpretation).",
                "rnplens selftest"),
    "research": ("the frozen scoring sources are library code of RNPBench Core; their command-line drivers are the "
                 "study's research batch scripts and are not part of RNPLens.",
                 "rnplens evaluate run   (the frozen sources are used through RNPLens, unchanged)"),
    "internal": ("this module is internal to the component packages and is not a command in RNPLens 0.4.",
                 "rnplens --help"),
}


def _launch(argv):
    """(kind, target, args) for a CPython command line: kind 'module' (-m), 'script' (a path), or None."""
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--":
            i += 1
            break
        if a.startswith("--"):
            i += 2 if a in _PY_LONG_WITH_ARG else 1
            continue
        if a.startswith("-") and len(a) > 1:
            j = 1
            while j < len(a):
                ch = a[j]
                if ch in "cm":
                    rest = a[j + 1:]
                    if rest:
                        val, k = rest, i + 1
                    else:
                        val, k = (argv[i + 1] if i + 1 < len(argv) else None), i + 2
                    if ch == "c" or val is None:
                        return None, None, []
                    return "module", val, list(argv[k:])
                if ch in _PY_OPT_WITH_ARG:
                    if not a[j + 1:]:
                        i += 1
                    break
                j += 1
            i += 1
            continue
        break
    if i < len(argv) and argv[i] != "-":
        return "script", argv[i], list(argv[i + 1:])
    return None, None, []


def _module_of_path(path):
    """Dotted module name if ``path`` is a file or directory inside one of the component packages, else None."""
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    try:
        rel = os.path.relpath(os.path.realpath(path), root)
    except ValueError:
        return None
    parts = rel.split(os.sep)
    if not parts or parts[0] not in COMPONENTS:
        return None
    if parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    if parts[-1] in ("__main__", "__init__"):
        parts = parts[:-1]
    return ".".join(p for p in parts if p)


def _rnpbench_toolkit(args):
    if not args or args[0] in _HELP:
        return None
    tool, rest = args[0], args[1:]
    first = rest[0] if rest else None
    if tool in ("validate", "provenance", "report"):
        return None
    if tool == "selftest":
        return "geometry"
    if tool == "toolkit":
        return None if first in (None, "version", "provenance", "example-contract", "-h", "--help") else "toolkit"
    if tool == "evaluate":
        return None if first in ("validate", "provenance", "-h", "--help") else "geometry"
    if tool == "diagnose":
        return None if first in ("-h", "--help") else "diagnose"
    return None                                   # unknown tool: the component prints its usage error


def decide(module, args):
    """None if the component command line ``python -m <module> <args>`` may run, else a REASONS key."""
    top = module.split(".")[0]
    if top not in COMPONENTS or top == "rnpbench_report":
        return None
    first = args[0] if args else None
    if top == "rnpbench_core":
        return "research"
    if top == "rnpbench_diagnose":
        if module in ("rnpbench_diagnose", "rnpbench_diagnose.cli") and (first is None or first in _HELP):
            return None
        return "diagnose"
    if top == "rnpbench_evaluate":
        if module in ("rnpbench_evaluate", "rnpbench_evaluate.cli"):
            return None if (first is None or first in _HELP or first in ("validate", "provenance")) else "geometry"
        return "geometry"
    if module in ("rnpbench", "rnpbench.cli"):
        return _rnpbench_toolkit(args)
    return "internal"


def refusal_text(command, reason):
    why, use = REASONS[reason]
    return ("rnplens: %s: '%s' is unavailable in RNPLens 0.4: %s Nothing was computed, read or written.\n"
            "  The component command lines are not a supported interface in 0.4; use the rnplens command:\n"
            "    %s\n"
            "  See docs/capabilities.md (Blocked in 0.4)." % (STATUS, command, why, use))


def refuse_blocked_route(argv=None):
    """Called from each component package's __init__; exits 5 if this process is a blocked component command line."""
    argv = list(getattr(sys, "orig_argv", None) or []) if argv is None else list(argv)
    if not argv:
        return
    kind, target, args = _launch(argv)
    verbs = []
    for a in args[:2]:
        if a.startswith("-"):
            break
        verbs.append(a)
    if kind == "module":
        module = target
        shown = "python -m %s" % " ".join([target] + verbs)
    elif kind == "script":
        module = _module_of_path(target)
        shown = "python %s" % " ".join([target] + verbs)
    else:
        return
    if not module:
        return
    reason = decide(module, args)
    if reason is None:
        return
    sys.stderr.write(refusal_text(shown.strip(), reason) + "\n")
    sys.stderr.flush()
    raise SystemExit(EXIT_BLOCKED)
