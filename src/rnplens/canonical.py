"""Canonical serialisation of managed-project records and their volatile sidecars (DETERMINISM_CONTRACT_v1).

A *canonical* file has the same bytes whenever the same inputs (same bytes, same layout relative to the project), the
same configuration, the same recorded answers and the same RNPLens version are used, wherever the project lives and
whenever it runs. Volatile execution metadata (time stamps, durations, the source commit, raw hashes of files that
carry their own creation time) is written to a *sidecar*:

    <project>/.rnplens/run/<path of the canonical file relative to the project>

    {"schema": "rnplens-run-sidecar-1", "canonical_file": <relative path>, "canonical_sha256": <sha256 of its bytes>,
     "volatile": {<JSON pointer in the canonical file>: <value>, ...}, "execution": {...}}

Rules (contract section 4):
  * JSON is json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=True, default=str) + newline;
  * an absolute path under the project is written "./<rel>" ("." for the project itself); one under a declared input,
    the reference, or the common parent of the project and its inputs is written relative to the project
    ("../in/run_A"); this applies to values, map keys, "<kind>:<path>" identifiers and free text;
  * keys in VOLATILE_KEYS are removed at every depth and kept in the sidecar;
  * a hash of a non-canonical file is a *content hash* (`content_sha256`): sha256_json of the file's canonical view.

Readers (``read``) merge the sidecar back when it matches the canonical file and turn "./" and "../" paths back into
absolute ones, so code that works on absolute paths is unchanged. A missing sidecar never changes a result: times read
back as None and an unverifiable cache entry is a miss.
"""
import hashlib
import json
import os
import platform
import re
import sys

from . import provenance as pv

SIDECAR_DIR = os.path.join(".rnplens", "run")
SIDECAR_SCHEMA = "rnplens-run-sidecar-1"

#: removed from canonical files at every depth and kept in the sidecar
VOLATILE_KEYS = frozenset({
    "created_utc", "recorded_utc", "status_utc", "stored_utc", "since_utc", "timestamp_utc", "started_utc",
    "wall_s", "code_commit",
    # raw SHA-256 of files that are not canonical (they carry their own creation time and absolute paths)
    "manifest_sha256", "summary_sha256", "raw_file_sha256",
})

_DELIM = r"""(?=$|[/|:,;)\]}>"'\s])"""
_REL_VALUE = re.compile(r"^(\.|\.\.?/.*|\.\.)$", re.S)
_REL_KIND = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(\.|\.\.?/.*|\.\.)$", re.S)


def dumps(obj):
    """The canonical JSON text of obj."""
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=True, default=str) + "\n"


def _esc(k):
    return str(k).replace("~", "~0").replace("/", "~1")


def _unesc(t):
    return t.replace("~1", "/").replace("~0", "~")


def former_roots(root):
    """Earlier absolute locations of the project at root (a moved or copied project): ``execution.project_root`` of
    its state sidecars that differs from root (DETERMINISM_CONTRACT_v2 4.2 step 1). Sorted; empty for a project that
    never moved or for a directory that is not a project."""
    root = os.path.abspath(root)
    d = os.path.join(root, SIDECAR_DIR, ".rnplens", "state")
    out = set()
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return []
    for n in names:
        if not n.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, n), encoding="utf-8") as fh:
                r = (json.load(fh).get("execution") or {}).get("project_root")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(r, str) and os.path.isabs(r) and os.path.normpath(r) != root:
            out.add(os.path.normpath(r))
    return sorted(out)


class Paths:
    """Absolute <-> canonical path forms for one project directory.

    root: the project directory; prefixes: declared inputs, the reference, ... (absolute). The common parent of the
    root and the prefixes is added when it is at least two folders deep. former: earlier locations of the project
    (default: ``former_roots(root)``); a path under a former location, or under its parent folder, is written as if
    it were under the current one (contract v2; a project copied elsewhere keeps its canonical forms and cache keys)."""

    def __init__(self, root, prefixes=(), former=None):
        self.root = os.path.abspath(root)
        ps = {self.root} | {os.path.abspath(p) for p in prefixes if p}
        try:
            anchor = os.path.commonpath(sorted(ps))
        except ValueError:
            anchor = None
        if anchor and anchor.count(os.sep) >= 2 and anchor != self.root:
            ps.add(anchor)
        self.prefixes = sorted(ps, key=lambda p: (-len(p), p))
        former = former_roots(self.root) if former is None else [os.path.normpath(f) for f in former]
        alias = {}
        for f in former:
            if f == self.root:
                continue
            alias.setdefault(f, self.root)
            fp, cp = os.path.dirname(f), os.path.dirname(self.root)
            if fp != cp and fp.count(os.sep) >= 2:
                alias.setdefault(fp, cp)
        self.alias = {a: t for a, t in alias.items() if a not in ps}
        if not self.alias:
            self._entries = None
            self._re = re.compile("|".join("(%s)%s" % (re.escape(p), _DELIM) for p in self.prefixes))
        else:
            ent = sorted([(p, p) for p in self.prefixes] + list(self.alias.items()), key=lambda e: (-len(e[0]), e[0]))
            self._entries = ent
            self._re = re.compile("|".join("(%s)%s" % (re.escape(p), _DELIM) for p, _ in ent))

    def _sub(self, m):
        if self._entries is None:
            return self.rel(m.group(0))
        return self.rel(self._entries[m.lastindex - 1][1])

    def rel(self, p):
        p = os.path.normpath(p)
        if p == self.root:
            return "."
        r = os.path.relpath(p, self.root).replace(os.sep, "/")
        return r if r.startswith("../") or r == ".." else "./" + r

    def canon_str(self, s):
        if not isinstance(s, str) or "/" not in s:
            return s
        return self._re.sub(self._sub, s)

    def abs_str(self, s):
        if not isinstance(s, str) or "." not in s:
            return s
        if _REL_VALUE.match(s):
            return os.path.normpath(os.path.join(self.root, s))
        m = _REL_KIND.match(s)
        if m:
            return m.group(1) + ":" + os.path.normpath(os.path.join(self.root, m.group(2)))
        return s

    def canon(self, o):
        if isinstance(o, dict):
            return {self.canon_str(k): self.canon(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [self.canon(v) for v in o]
        return self.canon_str(o)

    def decanon(self, o):
        if isinstance(o, dict):
            return {self.abs_str(k): self.decanon(v) for k, v in o.items()}
        if isinstance(o, list):
            return [self.decanon(v) for v in o]
        return self.abs_str(o)


def split_volatile(o, ptr="", out=None):
    """-> (object without VOLATILE_KEYS at any depth, {JSON pointer: removed value})."""
    out = {} if out is None else out
    if isinstance(o, dict):
        keep = {}
        for k, v in o.items():
            p = ptr + "/" + _esc(k)
            if k in VOLATILE_KEYS:
                out[p] = v
            else:
                keep[k] = split_volatile(v, p, out)[0]
        return keep, out
    if isinstance(o, (list, tuple)):
        return [split_volatile(v, "%s/%d" % (ptr, i), out)[0] for i, v in enumerate(o)], out
    return o, out


def merge_volatile(o, vol):
    """Put sidecar values back at their pointers (a pointer whose parent no longer exists is skipped)."""
    for p, v in sorted((vol or {}).items(), key=lambda kv: kv[0].count("/")):
        toks = [_unesc(t) for t in p.split("/")[1:]]
        cur = o
        try:
            for t in toks[:-1]:
                cur = cur[int(t)] if isinstance(cur, list) else cur[t]
            if isinstance(cur, dict):
                cur[toks[-1]] = v
        except (KeyError, IndexError, ValueError, TypeError):
            continue
    return o


def content_view(obj, paths):
    """The canonical view of a (possibly non-canonical) JSON object: paths canonical, volatile keys removed."""
    return split_volatile(paths.canon(obj))[0]


def content_sha256(path, paths):
    """Content hash of a file: sha256_json of the canonical view of a JSON file; the byte hash of any other file."""
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except (ValueError, UnicodeDecodeError):
        return pv.sha256_file(path)
    return pv.sha256_json(content_view(obj, paths))


def sidecar_path(root, rel):
    return os.path.join(os.path.abspath(root), SIDECAR_DIR, rel)


def execution_record():
    """Where and with what this file was written (volatile by definition; never needed for a result)."""
    return {"cwd": os.getcwd(), "python": sys.version.split()[0], "platform": platform.platform()}


def write(root, rel, obj, paths=None, sidecar_only=None, mode=None):
    """Write obj as the canonical file <root>/<rel> and its sidecar. sidecar_only: {pointer: value} kept only in the
    sidecar (for example tamper-detection hashes). -> sha256 of the canonical bytes."""
    root = os.path.abspath(root)
    paths = paths or Paths(root)
    can, vol = split_volatile(paths.canon(obj))
    vol.update(sidecar_only or {})
    text = dumps(can)
    path = os.path.join(root, rel)
    pv.atomic_write_text(path, text)
    if mode is not None:
        os.chmod(path, mode)
    csha = hashlib.sha256(text.encode()).hexdigest()
    pv.atomic_write_json(sidecar_path(root, rel), {
        "schema": SIDECAR_SCHEMA, "canonical_file": rel.replace(os.sep, "/"), "canonical_sha256": csha,
        "volatile": vol, "execution": dict(execution_record(), project_root=root)})
    return csha


def write_text(root, rel, text, paths=None):
    """A canonical text file (paths canonical; the caller guarantees it holds no volatile item). -> sha256."""
    paths = paths or Paths(root)
    text = paths.canon_str(text)
    pv.atomic_write_text(os.path.join(os.path.abspath(root), rel), text)
    return hashlib.sha256(text.encode()).hexdigest()


def read_sidecar(root, rel, canonical_sha=None):
    p = sidecar_path(root, rel)
    try:
        with open(p, encoding="utf-8") as fh:
            sc = json.load(fh)
    except (OSError, ValueError):
        return None
    if sc.get("schema") != SIDECAR_SCHEMA or (canonical_sha and sc.get("canonical_sha256") != canonical_sha):
        return None
    return sc


def restore(root, rel, obj, canonical_sha=None, paths=None):
    """A canonical object as read from disk -> the in-memory object (sidecar merged, absolute paths)."""
    sc = read_sidecar(root, rel, canonical_sha)
    if sc:
        obj = merge_volatile(obj, sc.get("volatile"))
    return (paths or Paths(root)).decanon(obj)


def read(root, rel, paths=None):
    """Read a canonical file written by ``write`` (or an older file with absolute paths; then nothing changes)."""
    path = os.path.join(os.path.abspath(root), rel)
    with open(path, "rb") as fh:
        b = fh.read()
    return restore(root, rel, json.loads(b.decode("utf-8")), hashlib.sha256(b).hexdigest(), paths)


def move_with_sidecar(root, rel_from, rel_to):
    """os.replace a canonical file and its sidecar (if any) to a new relative path."""
    root = os.path.abspath(root)
    os.makedirs(os.path.dirname(os.path.join(root, rel_to)), exist_ok=True)
    os.replace(os.path.join(root, rel_from), os.path.join(root, rel_to))
    s_from, s_to = sidecar_path(root, rel_from), sidecar_path(root, rel_to)
    if os.path.exists(s_from):
        os.makedirs(os.path.dirname(s_to), exist_ok=True)
        os.replace(s_from, s_to)


def next_free(dirpath, stem, ext=".json"):
    """<stem>.<n><ext> with the smallest n >= 1 that does not exist in dirpath (deterministic, no time stamp)."""
    n = 1
    while os.path.exists(os.path.join(dirpath, "%s.%d%s" % (stem, n, ext))):
        n += 1
    return "%s.%d%s" % (stem, n, ext)
