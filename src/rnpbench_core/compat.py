"""Supply the frozen four-axis geometry module (``score_decomp``) from the hash-verified core.

RNPBench Diagnose 0.2.1 imports the project's frozen ``score_decomp`` by name (``import score_decomp``) and
uses ``read_pose``, ``kabsch``, ``prot_pairs`` and the bound sibling namespaces ``feat`` and ``b2a``. The
original file cannot be imported off the development host: at import time it changes into a host directory
and loads sibling scripts by relative path. ``provide_score_decomp`` registers, under that name, the namespace
that ``frozen_loader`` builds from the same frozen bytes. No function is re-implemented or wrapped, and no
second copy of the code exists.
"""
import sys

from . import frozen_loader

MARK = "__rnpbench_core_frozen__"


def provide_score_decomp():
    """Register the core's frozen score_decomp namespace as ``sys.modules['score_decomp']``.

    Refuses if a different module of that name is already imported, rather than silently mixing two
    implementations. Returns a provenance record."""
    cur = sys.modules.get("score_decomp")
    if cur is not None:
        if getattr(cur, MARK, False):
            return dict(getattr(cur, MARK + "record"))
        raise RuntimeError("a different 'score_decomp' module is already imported (%s); the toolkit supplies the "
                           "hash-verified frozen copy and will not mix implementations"
                           % getattr(cur, "__file__", repr(cur)))
    built, rec = frozen_loader.load({"P": None, "REP": None})
    mod = built["score_decomp"]
    prov = {"provided_by": "rnpbench_core.compat.provide_score_decomp",
            "frozen_file": rec["namespaces"]["score_decomp"]["file"],
            "frozen_sha256": rec["manifest"]["files"][rec["namespaces"]["score_decomp"]["file"]]["sha256"],
            "bound_namespaces": rec["namespaces"]["score_decomp"]["bound_from_other_frozen_files"]}
    setattr(mod, MARK, True)
    setattr(mod, MARK + "record", prov)
    sys.modules["score_decomp"] = mod
    return dict(prov)
