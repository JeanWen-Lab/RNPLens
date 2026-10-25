"""Load the frozen RNPBench scoring functions WITHOUT rewriting them.

The scientific code lives, byte-for-byte as it ran in the benchmark, under ``frozen/``. Each file's
SHA-256 is pinned in ``frozen/FROZEN_SOURCES.json`` and checked before anything is executed.

The original files were research scripts: at import time they change directory into the development
host, insert host paths into ``sys.path``, create cache directories and load sibling scripts by
relative path. None of that is scoring logic, and none of it can run on another machine. So this
loader does NOT import the files. It parses each one and executes, verbatim, only

  * the top-level function/class definitions and constant assignments that the requested entry
    points need (their transitive closure inside the same file), and
  * the file's own top-level ``import`` statements for third-party/standard modules.

Names that the original code bound by loading a sibling project script (``A``, ``feat``, ``b1c``,
``b2a``, ``from rnpbench_score_v2 import ...``) are bound to the corresponding namespaces built here,
as declared in ``SPEC``. Names that held a host directory (``P``, ``REP`` in ``pos_adapter``) are
supplied as values by the caller; no assignment containing a host path is ever executed (the loader
refuses if the closure would reach one).

Nothing inside any function body is modified, wrapped or re-implemented.
"""
from __future__ import annotations

import __future__ as _future
import ast
import hashlib
import json
import os
import types

HERE = os.path.dirname(os.path.abspath(__file__))
FROZEN = os.path.join(HERE, "frozen")
MANIFEST = os.path.join(FROZEN, "FROZEN_SOURCES.json")

# alias -> (frozen file, entry points, {name in that file -> alias of another namespace or ("from", alias, attr)},
#           injected names supplied at call time)
SPEC = {
    "rnpbench_score_v2": ("canonical/rnpbench_score_v2.py", ["polymer_class", "admissibility", "to_pairs", "SCORER_VERSION"], {}, []),
    "corr_mask_audit": ("canonical/corr_mask_audit.py", ["native_label_map", "construct_lengths", "model_numbering_check"],
                        {"polymer_class": ("from", "rnpbench_score_v2", "polymer_class"),
                         "admissibility": ("from", "rnpbench_score_v2", "admissibility"),
                         "to_pairs": ("from", "rnpbench_score_v2", "to_pairs"),
                         "SCORER_VERSION": ("from", "rnpbench_score_v2", "SCORER_VERSION")}, []),
    "pos_adapter": ("canonical/pos_adapter.py", ["one_row"],
                    {"A": "corr_mask_audit",
                     "polymer_class": ("from", "rnpbench_score_v2", "polymer_class"),
                     "admissibility": ("from", "rnpbench_score_v2", "admissibility"),
                     "to_pairs": ("from", "rnpbench_score_v2", "to_pairs")}, ["P", "REP"]),
    "rf2na_scoring": ("canonical/rf2na_scoring.py", ["select"], {}, []),
    "feat": ("f1/f1_featurize_mp.py", ["load", "contacting_pair", "prot_frames", "chain_kind"], {}, []),
    "b1c": ("f1/f1_b1c_allatom.py", ["base1"], {"feat": "feat"}, []),
    "b2a": ("f1/f1_b2a_matrix.py", ["align_pairs", "c4_of"], {"feat": "feat", "b1c": "b1c"}, []),
    "score_decomp": ("decomp/score_decomp.py", ["read_pose", "four_axes", "kabsch", "prot_pairs"],
                     {"feat": "feat", "b1c": "b1c", "b2a": "b2a"}, []),
}
ORDER = ["rnpbench_score_v2", "corr_mask_audit", "pos_adapter", "rf2na_scoring", "feat", "b1c", "b2a", "score_decomp"]
PROJECT_MODULES = {"rnpbench_score_v2", "corr_mask_audit", "pos_adapter", "rf2na_scoring", "release_v3"}
FORBIDDEN_IN_EXECUTED = ("/home/", "os.chdir", "sys.path.insert", "os.makedirs")


class FrozenIntegrityError(RuntimeError):
    pass


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _defined_names(node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    if isinstance(node, ast.Assign):
        out = set()
        for t in node.targets:
            for n in ast.walk(t):
                if isinstance(n, ast.Name):
                    out.add(n.id)
        return out
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return {node.target.id}
    return set()


def _used_names(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _segment(src_lines, node):
    first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    return "\n".join(src_lines[first - 1: node.end_lineno])


def verify_sources():
    """Every vendored file must hash to its pinned value. Returns the manifest."""
    man = json.load(open(MANIFEST))
    bad = []
    for rel, rec in man["files"].items():
        got = _sha(os.path.join(FROZEN, rel))
        if got != rec["sha256"]:
            bad.append((rel, rec["sha256"][:16], got[:16]))
    if bad:
        raise FrozenIntegrityError("frozen source(s) differ from their pinned SHA-256: %s" % bad)
    return man


def _build_one(alias, built, injected):
    rel, entries, bindings, inject_names = SPEC[alias]
    path = os.path.join(FROZEN, rel)
    src = open(path, encoding="utf-8").read()
    lines = src.splitlines()
    tree = ast.parse(src, filename=path)
    top = list(tree.body)
    defs = {}
    for i, n in enumerate(top):
        for name in _defined_names(n):
            defs.setdefault(name, []).append(i)
    # names bound by sibling-script loading or supplied by the caller are never taken from the file
    external = set(bindings) | set(inject_names)
    want, stack = set(), list(entries)
    while stack:
        name = stack.pop()
        if name in external or name not in defs:
            continue
        for i in defs[name]:
            if i in want:
                continue
            want.add(i)
            stack.extend(_used_names(top[i]))
    chosen = sorted(want)
    imports = [n for n in top if isinstance(n, (ast.Import, ast.ImportFrom))
               and not (isinstance(n, ast.ImportFrom) and (n.module == "__future__" or (n.module or "") in PROJECT_MODULES))
               and not (isinstance(n, ast.Import) and any(a.name in PROJECT_MODULES for a in n.names))]
    executed = []
    for n in imports + [top[i] for i in chosen]:
        seg = _segment(lines, n)
        if not isinstance(n, (ast.Import, ast.ImportFrom)):
            for bad in FORBIDDEN_IN_EXECUTED:
                if bad in seg and isinstance(n, (ast.Assign, ast.AnnAssign, ast.Expr)):
                    raise FrozenIntegrityError("%s: closure reached a host-dependent statement: %s" % (rel, seg[:120]))
        executed.append({"lineno": n.lineno, "end_lineno": n.end_lineno, "kind": type(n).__name__,
                         "names": sorted(_defined_names(n)) or None, "sha256": hashlib.sha256(seg.encode()).hexdigest()})
    flags = 0
    if any(isinstance(n, ast.ImportFrom) and n.module == "__future__" for n in top):
        for n in top:
            if isinstance(n, ast.ImportFrom) and n.module == "__future__":
                for a in n.names:
                    flags |= getattr(_future, a.name).compiler_flag
    mod = types.ModuleType("rnpbench_frozen_" + alias)
    mod.__file__ = path
    ns = mod.__dict__
    for name, target in bindings.items():
        if isinstance(target, tuple) and target[0] == "from":
            ns[name] = getattr(built[target[1]], target[2])
        else:
            ns[name] = built[target]
    for name in inject_names:
        if name not in injected:
            raise FrozenIntegrityError("%s needs injected value %s" % (alias, name))
        ns[name] = injected[name]
    body = ast.Module(body=imports + [top[i] for i in chosen], type_ignores=[])
    exec(compile(body, path, "exec", flags=flags, dont_inherit=True), ns)
    missing = [e for e in entries if e not in ns]
    if missing:
        raise FrozenIntegrityError("%s: entry points not defined after load: %s" % (alias, missing))
    return mod, {"file": rel, "entry_points": entries, "bound_from_other_frozen_files": sorted(bindings),
                 "injected_values": inject_names, "executed_top_level_statements": executed}


def load(injected):
    """Build all frozen namespaces. ``injected`` must supply P and REP for pos_adapter."""
    man = verify_sources()
    built, record = {}, {}
    for alias in ORDER:
        built[alias], record[alias] = _build_one(alias, built, injected)
    return built, {"manifest": man, "namespaces": record}
