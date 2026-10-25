"""Portability of managed projects: hash-verified resolution of recorded structure files, explicit relinking, and
clear refusal (records/replay/PORTABILITY_TEST_v1.md, section 2).

The importer's ``manifest.json`` records absolute paths; that record and what the importer computes are unchanged.
This module sits around it. A recorded file ``(p, sha256)`` resolves, in order:

  RELINKED  a mapping recorded by ``rnplens relink`` (``<project>/.rnplens/relink.json``);
  LOCAL     p lies in the project's current location (the project directory, its declared inputs, its reference);
  MAPPED    p lies under a former location of the project (or its parent folder): the same place now (a copy that
            brought its inputs along); if nothing is there, ->
  EXTERNAL  p itself.

The file must then exist with the recorded SHA-256; otherwise it is MISSING or MISMATCH and is never used. Commands
that read structure bytes refuse (exit 6, ``PORTABILITY REFUSED``) when a required file is MISSING or MISMATCH, and
say ``NOT SELF-CONTAINED`` when they use RELINKED or EXTERNAL files. Commands that only report records never refuse
and print ``PORTABILITY WARNING`` instead. Directories outside a managed project keep their 0.3 behaviour.
"""
import copy
import json
import os
import sys

from . import provenance as pv

EXIT_PORTABILITY = 6
RELINK_REL = os.path.join(".rnplens", "relink.json")
RELINK_SCHEMA = "rnplens-relink-1"
USABLE = ("LOCAL", "MAPPED", "RELINKED", "EXTERNAL")
_PRINTED = set()


class PortabilityError(Exception):
    """A command refused because recorded input files are missing or differ (exit code 6)."""
    exit_code = EXIT_PORTABILITY


def _norm(p):
    return os.path.normpath(os.path.abspath(p))


def _under(p, base):
    p, base = _norm(p), _norm(base)
    return p == base or p.startswith(base.rstrip(os.sep) + os.sep)


def _sha(p):
    from .projection import _sha as cached
    return cached(_norm(p))


def _former_roots(root):
    try:
        from . import canonical as CN
    except ImportError:                    # an installation without canonical records has no recorded former location
        return []
    return CN.former_roots(root)


def managed_root(d):
    """The managed project (directory with .rnplens/HEAD) that contains directory d, or None."""
    from .projection import project_root
    return project_root(os.path.join(os.path.abspath(d), "_"))


def load_relink(root):
    try:
        with open(os.path.join(root, RELINK_REL), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        doc = {}
    return {"files": {(e["recorded"], e["sha256"]): e["path"] for e in doc.get("files") or [] if isinstance(e, dict)},
            "inputs": {e["recorded"]: e["path"] for e in doc.get("inputs") or [] if isinstance(e, dict)},
            "doc": doc}


class Context:
    """Where a managed project is now: its root, declared inputs and reference, former locations and relinks."""

    def __init__(self, root, extra_location=()):
        from . import state as S
        self.root = _norm(root)
        try:
            st = S.Project(self.root).head() or {}
        except Exception:                     # an unreadable state is reported by the state layer itself
            st = {}
        decl = st.get("declared") or {}
        self.relink = load_relink(self.root)
        self.inputs = [_norm(self.relink["inputs"].get(a, a)) for a in decl.get("inputs") or []]
        ref = ((decl.get("config") or {}).get("reference") or {}).get("path")
        self.location = [self.root] + self.inputs + ([_norm(ref)] if ref else []) + [_norm(x) for x in extra_location if x]
        self.former = _former_roots(self.root)
        al = {}
        for f in self.former:
            al.setdefault(f, self.root)
            fp, cp = os.path.dirname(f), os.path.dirname(self.root)
            if fp != cp and fp.count(os.sep) >= 2:
                al.setdefault(fp, cp)
        self.alias = sorted(al.items(), key=lambda kv: -len(kv[0]))
        self.state_files = dict((st.get("inputs") or {}).get("files") or {})

    def aliased(self, p):
        for a, t in self.alias:
            if _under(p, a):
                return _norm(t + _norm(p)[len(a):])
        return None

    def former_equivalent(self, p):
        """The place of a current-location path at the most recent former location (for messages)."""
        for f in self.former:
            for cur, old in ((self.root, f), (os.path.dirname(self.root), os.path.dirname(f))):
                if _under(p, cur):
                    return _norm(old + _norm(p)[len(cur):])
        return None

    def resolve(self, p, h):
        r = {"recorded": p, "sha256": h}
        if not p:
            r.update(status="MISSING", kind="NONE", path=None)
            return r
        p = _norm(p)
        q = self.relink["files"].get((p, h))
        if q:
            kind = "RELINKED"
        elif any(_under(p, b) for b in self.location):
            q, kind = p, "LOCAL"
        else:
            m = self.aliased(p)
            if m and os.path.lexists(m):
                q, kind = m, "MAPPED"
            else:
                q, kind = p, "EXTERNAL"
        r.update(path=q, kind=kind)
        if not os.path.isfile(q):
            r["status"] = "MISSING"
        else:
            s = _sha(q)
            if s == h:
                r["status"] = kind
            else:
                r.update(status="MISMATCH", found_sha256=s)
        return r


def _rows(ctx, man):
    """One row per recorded file: path/original_sha256 and used_path/used_sha256 of every structure (used_path is
    folded into path when they name the same file with the same hash). row["index"] is the structure's position."""
    rows = []
    for i, s in enumerate(man.get("structures") or []):
        req = s.get("verdict") == "INCLUDED"
        same = s.get("used_path") == s.get("path") and s.get("used_sha256") == s.get("original_sha256")
        for pk, hk in (("path", "original_sha256"), ("used_path", "used_sha256")):
            if pk == "used_path" and same:
                continue
            r = ctx.resolve(s.get(pk), s.get(hk))
            r.update(structure=s.get("id"), field=pk, required=req, index=i,
                     fields=("path", "used_path") if (pk == "path" and same) else (pk,))
            rows.append(r)
    return rows


def _advice(root):
    return ("To restore: put the files back at the paths shown (or copy the prediction folders next to the project, "
            "in the same layout), or let RNPLens find them and verify them by SHA-256:\n"
            "  rnplens relink %s --search DIR        (looks for files with the same name under DIR)\n"
            "  rnplens relink %s --map OLD=NEW       (replaces the path prefix OLD by NEW)\n"
            "A file with the same name but another SHA-256 is never used.\n"
            "An edited file is a new input version (never relinked): analyse it with 'rnplens update %s' (edited in "
            "place) or 'rnplens update %s NEW_FOLDER --remove-input OLD_FOLDER' (edited copy elsewhere); earlier "
            "versions stay unchanged." % (root, root, root, root))


MAX_LISTED = 6


def _listing(bad):
    """Changed files first, then missing ones (record order); at most MAX_LISTED rows."""
    order = [r for r in bad if r["status"] == "MISMATCH"] + [r for r in bad if r["status"] != "MISMATCH"]
    L = []
    for r in order[:MAX_LISTED]:
        if r["status"] == "MISSING":
            L.append("  missing: %s  (structure %s; recorded SHA-256 %s%s)" % (
                r["recorded"], r.get("structure"), r["sha256"], "" if r["path"] == r["recorded"] else "; looked at %s" % r["path"]))
        else:
            L.append("  MISMATCH: %s  (structure %s; recorded SHA-256 %s, found %s%s)" % (
                r["recorded"], r.get("structure"), r["sha256"], r.get("found_sha256"),
                "" if r["path"] == r["recorded"] else " at %s" % r["path"]))
    if len(order) > MAX_LISTED:
        L.append("  ... and %d more (all listed by 'rnplens relink <project> --search DIR --dry-run')" % (len(order) - MAX_LISTED))
    return L


def refused_text(command, where, root, bad, extra="", written="nothing was written."):
    nm, nx = sum(r["status"] == "MISMATCH" for r in bad), sum(r["status"] != "MISMATCH" for r in bad)
    return "\n".join(["PORTABILITY REFUSED (rnplens %s): %d required structure file(s) recorded by %s cannot be used; "
                      "%s" % (command, len(bad), where, written)] + _listing(bad) +
                     ([extra] if extra else []) + [_advice(root),
                      "PORTABILITY REFUSED (rnplens %s): %d changed (MISMATCH), %d missing; fix with 'rnplens relink' or "
                      "restore the files; an edited file is analysed as a new version with 'rnplens update' (above)."
                      % (command, nm, nx)])


def _say(key, text, out=None):
    if key in _PRINTED:
        return
    _PRINTED.add(key)
    print(text, file=out or sys.stderr)


def notice_text(command, ext):
    dirs = sorted({os.path.dirname(r["path"]) for r in ext})
    kinds = sorted({r["kind"] for r in ext})
    return ("NOT SELF-CONTAINED (rnplens %s): %d structure file(s) are read from outside the place this project records "
            "for them (%s), each verified by SHA-256:\n%s\nThe project depends on these locations. To make it "
            "self-contained, copy the files next to the project and run 'rnplens relink <project> --search <copy>'."
            % (command, len(ext), " and ".join(k.lower() for k in kinds), "\n".join("  " + d for d in dirs[:8])))


def check_manifest(import_dir, man, mode="read", command="", out=None):
    """-> (manifest with resolved paths, report or None). mode: 'read' (refuse on a missing/changed required file),
    'report' (never refuse; warn), 'recorded' (the caller reads the recorded paths: also refuse unless every required
    file is LOCAL or EXTERNAL at its recorded path). Outside a managed project: (man, None), unchanged."""
    root = managed_root(import_dir)
    if root is None or not isinstance(man, dict):
        return man, None
    ctx = Context(root)
    rows = _rows(ctx, man)
    res = copy.deepcopy(man)
    for r in rows:
        if r["status"] in USABLE:
            for f in r["fields"]:
                res["structures"][r["index"]][f] = r["path"]
    req = [r for r in rows if r["required"]]
    bad = [r for r in req if r["status"] not in USABLE]
    ext = [r for r in req if r["status"] in ("EXTERNAL", "RELINKED")]
    moved = [r for r in req if r["status"] in ("MAPPED", "RELINKED")]
    rep = {"root": root, "rows": rows, "bad": bad, "external": ext, "self_contained": not bad and not ext}
    where = os.path.relpath(import_dir, os.path.dirname(root)) if _under(import_dir, os.path.dirname(root)) else import_dir
    if mode in ("read", "recorded") and bad:
        raise PortabilityError(refused_text(command, where, root, bad))
    if mode == "recorded" and moved:
        raise PortabilityError("\n".join([
            "PORTABILITY REFUSED (rnplens %s): %s reads the structure files at the paths the import recorded, and %d of "
            "them are now elsewhere (a moved or relinked project); nothing was written:" % (command, command, len(moved))] +
            ["  recorded %s -> now %s (%s)" % (r["recorded"], r["path"], r["kind"].lower()) for r in moved[:MAX_LISTED]] +
            (["  ... and %d more" % (len(moved) - MAX_LISTED)] if len(moved) > MAX_LISTED else []) +
            ["Run 'rnplens update %s' (it re-imports from the current inputs when an analysis has to be redone), or "
             "restore the files at the recorded paths. 'rnplens relink' records where the files are for the other "
             "commands." % root, "PORTABILITY REFUSED (rnplens %s): run 'rnplens update' or restore the files at the "
             "recorded paths." % command]))
    if mode == "report" and bad:
        _say(("warn", root, where, command), "\n".join(
            ["PORTABILITY WARNING (rnplens %s): %d required structure file(s) recorded by %s cannot be used:"
             % (command, len(bad), where)] + _listing(bad) + [_advice(root),
             "PORTABILITY WARNING (rnplens %s): the report above names recorded files that are not available here."
             % command]), out)
    if ext:
        _say(("ext", root, where, command), notice_text(command, ext), out)
    return res, rep


def file_verified(path, sha256, where):
    """True if the recorded file (path, sha256) is available with that SHA-256: at its path, or (inside a managed
    project that contains `where`) where it resolves to (relinked, or the same place under the current location)."""
    if path and os.path.isfile(path) and _sha(path) == sha256:
        return True
    root = managed_root(where)
    if root is None:
        return False
    return Context(root).resolve(path, sha256)["status"] in USABLE


def load_manifest(import_dir, mode="read", command=""):
    with open(os.path.join(import_dir, "manifest.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    return check_manifest(import_dir, man, mode, command)[0]


def recorded_paths_local(import_dir, declared=()):
    """True if every required structure file of the import is LOCAL at its recorded path (or outside a managed
    project). Used by the managed pipeline before it re-analyses a reused import; declared: the inputs (and
    reference) of the update in progress, which count as the project's location."""
    root = managed_root(import_dir)
    if root is None:
        return True
    try:
        with open(os.path.join(import_dir, "manifest.json"), encoding="utf-8") as fh:
            man = json.load(fh)
    except (OSError, ValueError):
        return False
    rows = _rows(Context(root, declared), man)
    return all(r["status"] == "LOCAL" for r in rows if r["required"])


# ------------------------------------------------------------------------------------------- declared inputs
def apply_relinked_inputs(root, decl):
    """Replace relinked declared inputs by their new location (in place). -> list of (old, new)."""
    m = load_relink(root)["inputs"]
    out = []
    ins = []
    for a in decl.get("inputs") or []:
        b = m.get(_norm(a))
        if b and _norm(b) != _norm(a):
            out.append((a, b))
            ins.append(b)
        else:
            ins.append(a)
    decl["inputs"] = ins
    return out


def translate_paths(obj, pairs):
    """obj with every path under an old declared input (in keys, values and identifiers such as
    'chain_mapping:<path>|...') moved to its relinked folder. pairs: [(old, new)] from apply_relinked_inputs. The
    recorded answers then refer to the same, hash-verified files at their new place (their dependency hashes are still
    checked by the pipeline)."""
    import re
    if not pairs:
        return obj
    ps = sorted(((_norm(a), _norm(b)) for a, b in pairs), key=lambda ab: -len(ab[0]))
    rx = re.compile("|".join("(%s)(?=$|[/|:,;)\\]}>\"'\\s])" % re.escape(a) for a, _ in ps))
    sub = lambda s: rx.sub(lambda m: ps[m.lastindex - 1][1], s) if isinstance(s, str) else s

    def walk(o):
        if isinstance(o, dict):
            return {sub(k): walk(v) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v) for v in o]
        return sub(o)
    return walk(obj)


def check_declared_inputs(root, decl, command="update"):
    """In a project that has a former location, a declared input missing here is a refusal (not a removed run)."""
    if not _former_roots(root):
        return
    missing = [a for a in decl.get("inputs") or [] if not os.path.exists(a)]
    if not missing:
        return
    ctx = Context(root)
    L = ["PORTABILITY REFUSED (rnplens %s): this project was copied or moved from %s, and %d declared input(s) are "
         "not at the place they resolve to now; nothing was written (no new version):"
         % (command, ", ".join(ctx.former), len(missing))]
    for a in missing:
        f = ctx.former_equivalent(a)
        L.append("  missing: %s%s" % (a, "" if not f else ("  (exists at the former location %s)" % f if os.path.exists(f)
                                                            else "  (not at the former location %s either)" % f)))
    L.append("Copy the inputs to the place shown, or record where they are with 'rnplens relink %s --map OLD=NEW' "
             "(or --search DIR); to drop an input deliberately use 'rnplens update %s --remove-input PATH'."
             % (root, root))
    L.append("If files of a missing input were edited, they are a new input version: add the folder that holds the "
             "edited copies and drop that input in one update (earlier versions stay unchanged), e.g.\n"
             "  rnplens update %s NEW_FOLDER --remove-input %s" % (root, missing[0]))
    L.append(_advice(root))
    L.append("PORTABILITY REFUSED (rnplens %s): moved from %s; %d declared input(s) missing; fix with 'rnplens relink' "
             "or restore the inputs; nothing was written." % (command, ", ".join(ctx.former), len(missing)))
    raise PortabilityError("\n".join(L))


def report_head(root, command="update", out=None):
    """Report (never refuse) the portability of the head state's import directories."""
    from . import state as S
    try:
        st = S.Project(root).head() or {}
    except Exception:
        return None
    reps = []
    for g, rec in sorted((st.get("groups") or {}).items()):
        d = rec.get("import_dir")
        if d and os.path.isfile(os.path.join(root, d, "manifest.json")):
            reps.append(check_manifest(os.path.join(root, d), json.load(open(os.path.join(root, d, "manifest.json"))),
                                       "report", command, out)[1])
    return reps


# ------------------------------------------------------------------------------------------------- relink
def relink(root, search=(), maps=(), dry_run=False, out=None):
    """Find recorded files that are not where the project records them, verify them by SHA-256, record the mapping.
    -> exit code (0: every required file of every import directory resolves; 6 otherwise)."""
    out = out or sys.stdout
    root = _norm(root)
    if not os.path.isfile(os.path.join(root, ".rnplens", "HEAD")):
        print("rnplens relink: %s is not a managed project (no .rnplens/HEAD)" % root, file=sys.stderr)
        return 2
    pairs = []
    for m in maps:
        if "=" not in m:
            print("rnplens relink: --map needs OLD=NEW, got %r" % m, file=sys.stderr)
            return 2
        a, b = m.split("=", 1)
        pairs.append((_norm(a), _norm(b)))
    ctx = Context(root)
    imports = sorted(os.path.dirname(p) for p in _glob_manifests(root))
    targets = {}
    for d in imports:
        man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
        for r in _rows(ctx, man):
            k = (_norm(r["recorded"]), r["sha256"])
            targets[k] = targets.get(k, False) or r["required"]
    for p, h in ctx.state_files.items():
        targets.setdefault((_norm(p), h), False)
    index = {}
    for d in search:
        for dp, dn, fn in os.walk(_norm(d)):
            dn.sort()
            for f in sorted(fn):
                index.setdefault(f, []).append(os.path.join(dp, f))
    found, rejected, how = {}, [], {}
    for (p, h) in sorted(targets):
        r = ctx.resolve(p, h)
        if r["status"] in ("LOCAL", "MAPPED", "RELINKED"):
            continue
        cands = [(_norm(b + p[len(a):]), "map %s=%s" % (a, b)) for a, b in pairs if _under(p, a)]
        found_here = [(c, "search %s" % d) for d in search for c in index.get(os.path.basename(p), []) if _under(c, d)]
        # among search hits, prefer the one whose trailing path components match the recorded path best (two runs
        # can hold byte-identical files; the same layout keeps declared input folders mappable); then walk order
        found_here.sort(key=lambda cw: -_common_tail(cw[0], p))
        cands += found_here
        for c, why in cands:
            if not os.path.isfile(c):
                continue
            s = _sha(c)
            if s == h:
                found[(p, h)] = c
                how[(p, h)] = why
                break
            rejected.append((p, c, s))
    # declared inputs whose recorded files were all relinked under one folder
    new_inputs = {}
    for a in ctx.inputs:
        if os.path.exists(a):
            continue
        rels = {p: os.path.relpath(p, a) for (p, h) in ctx.state_files.items() if _under(p, a)}
        heads = set()
        for p, rel in rels.items():
            c = found.get((_norm(p), ctx.state_files[p]))
            heads.add(_norm(c[: len(c) - len(rel)]) if c and c.endswith(rel) else None)
        if rels and len(heads) == 1 and None not in heads:
            new_inputs[a] = heads.pop()
    for (p, h), c in sorted(found.items()):
        print("relinked: %s -> %s  (SHA-256 %s verified; %s)" % (p, c, h, how[(p, h)]), file=out)
    for a, b in sorted(new_inputs.items()):
        print("declared input relinked: %s -> %s  (all its recorded files found there)" % (a, b), file=out)
    for p, c, s in rejected:
        print("rejected (same name, different SHA-256): %s  (SHA-256 %s; recorded %s needs %s)"
              % (c, s, p, next(h for (q, h) in targets if q == p)), file=out)
    if (found or new_inputs) and not dry_run:
        doc = load_relink(root)["doc"] or {}
        files = {(e["recorded"], e["sha256"]): e for e in doc.get("files") or []}
        for (p, h), c in found.items():
            files[(p, h)] = {"recorded": p, "sha256": h, "path": c, "how": how[(p, h)]}
        ins = {e["recorded"]: e for e in doc.get("inputs") or []}
        for a, b in new_inputs.items():
            ins[a] = {"recorded": a, "path": b}
        pv.atomic_write_json(os.path.join(root, RELINK_REL), {
            "schema": RELINK_SCHEMA, "files": [files[k] for k in sorted(files)], "inputs": [ins[k] for k in sorted(ins)],
            "note": "paths are absolute: this record describes where this copy of the project finds its inputs"})
    # what remains
    ctx = Context(root) if not dry_run else ctx
    if dry_run:
        for k, c in found.items():
            ctx.relink["files"][k] = c
    bad = []
    for d in imports:
        man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
        bad += [dict(r, where=os.path.relpath(d, root)) for r in _rows(ctx, man) if r["required"] and r["status"] not in USABLE]
    print("rnplens relink: %d file(s) relinked%s, %d rejected candidate(s), %d required file(s) still unresolved%s"
          % (len(found), " (dry run: nothing recorded)" if dry_run else "", len(rejected), len(bad),
             "" if not new_inputs else "; %d declared input(s) relinked: run 'rnplens update %s'" % (len(new_inputs), root)),
          file=out)
    if bad:
        extra = _edited_text(root, ctx, targets, found, rejected)
        written = "nothing was written."
        if (found or new_inputs) and not dry_run:   # the verified mappings above were recorded (QA workflow-replay)
            written = ("the %d verified file mapping(s) and %d declared input(s) listed above were recorded in %s; "
                       "nothing else was written." % (len(found), len(new_inputs), RELINK_REL))
        print(refused_text("relink", "the project's import directories", root, bad, extra=extra, written=written),
              file=sys.stderr)
        return EXIT_PORTABILITY
    return 0


def _edited_continuations(ctx, targets, found, rejected):
    """Required recorded files that relink rejected because a same-name candidate has another SHA-256 (an edited copy).
    -> [(recorded path, recorded sha, candidate, candidate sha, old declared input, new folder)], one per recorded file,
    using the candidate whose path tail matches best; candidates accepted for another recorded file are skipped."""
    accepted = set(found.values())
    resolved = {p for (p, h) in found}
    need = {}
    for (p, h), req in targets.items():
        if req:
            need[p] = h
    best = {}
    for p, c, s in rejected:
        if p not in need or p in resolved or c in accepted:
            continue
        t = _common_tail(c, p)
        if p not in best or t > best[p][2]:
            best[p] = (c, s, t)
    out, seen_files = [], set()
    for p, (c, s, t) in sorted(best.items()):
        cur = p if any(_under(p, x) for x in ctx.inputs) else (ctx.aliased(p) or p)   # recorded at a former location
        a = next((x for x in ctx.inputs if _under(cur, x)), None)
        if a is None:
            continue                              # not inside a declared input: covered by the general advice
        rel = os.path.relpath(cur, a)
        new = _norm(c[: len(c) - len(rel)]) if c.endswith(os.sep + rel) else os.path.dirname(c)
        if c in seen_files:
            continue
        seen_files.add(c)
        out.append((p, need[p], c, s, a, new))
    return out


def _edited_text(root, ctx, targets, found, rejected):
    rows = _edited_continuations(ctx, targets, found, rejected)
    if not rows:
        return ""
    L = ["%d recorded structure file(s) were found with the same name but different content (edited). An edited file "
         "is a new input version, not the old file in a new place, so relink does not accept it:" % len(rows)]
    for p, h, c, s, a, new in rows:
        L.append("  edited: %s  (recorded %s, SHA-256 %s; found %s)" % (c, p, h, s))
    L.append("To analyse the edited structure(s) as a new project version (earlier versions and their results stay "
             "unchanged), run:")
    for a, new in sorted({(a, new) for p, h, c, s, a, new in rows}):
        L.append("  rnplens update %s %s --remove-input %s" % (root, new, a))
    return "\n".join(L)


def _common_tail(a, b):
    x, y = _norm(a).split(os.sep)[::-1], _norm(b).split(os.sep)[::-1]
    n = 0
    while n < min(len(x), len(y)) and x[n] == y[n]:
        n += 1
    return n


def _glob_manifests(root):
    import glob
    return sorted(glob.glob(os.path.join(root, "imports", "v*", "*", "manifest.json")))


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="rnplens relink", description="Record where a copied or moved managed project "
                                 "finds its recorded input files. Every candidate is verified by SHA-256; a file with "
                                 "the same name and another SHA-256 is never accepted.")
    ap.add_argument("project", help="managed project directory (with .rnplens/HEAD)")
    ap.add_argument("--search", action="append", default=[], metavar="DIR", help="look for files with the same name under DIR")
    ap.add_argument("--map", action="append", default=[], metavar="OLD=NEW", help="replace the path prefix OLD by NEW")
    ap.add_argument("--dry-run", action="store_true", help="report only; record nothing")
    a = ap.parse_args(argv)
    if not a.search and not a.map:
        ap.error("give --search DIR and/or --map OLD=NEW")
    return relink(a.project, a.search, a.map, a.dry_run)
