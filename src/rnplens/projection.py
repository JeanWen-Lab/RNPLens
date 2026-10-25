"""Canonical projections of managed-project outputs (records/replay/DETERMINISM_CONTRACT_v2.md, section 4).

Every JSON or text output F inside a managed project (the nearest ancestor directory holding ``.rnplens/HEAD``) that
is not a v1 canonical file gets a *projection*:

    F.json -> F.json.canonical.json        F.md / .txt / .html / .tsv / .svg / .log -> F.<ext>.canonical.txt

The projection keeps every scientifically meaningful field of F and nothing that depends on where or when the
project ran: paths written relative to the project (also paths under a former location of a moved project), the
volatile keys removed, consent ids reduced to their counter, hashes over volatile bytes replaced by the hash of the
hashed file's projection, and (follow-up records) the evidence hash replaced by a location-independent content hash.
The raw file F is never changed; readers keep using it.

Projections are written by ``provenance.atomic_write_json``/``atomic_write_text`` (``after_write``) and, for files
the 0.3 importer and analysis write themselves, by the managed pipeline (``sweep``). Each projection adds
an entry ``{file, raw_sha256, projection_sha256}`` to ``<project>/.rnplens/run/projection_index.json`` (a sidecar,
append-only list in write order), so
a recorded hash of an earlier version of a rewritten file still maps to the projection of that version.
"""
import fnmatch
import hashlib
import json
import os
import re

from . import provenance as pv

PROJ_EXT = {".json": ".canonical.json", ".md": ".canonical.txt", ".txt": ".canonical.txt", ".html": ".canonical.txt",
            ".tsv": ".canonical.txt", ".svg": ".canonical.txt", ".log": ".canonical.txt"}
PROJ_SUFFIXES = (".canonical.json", ".canonical.txt")
#: removed from projections at every depth, in addition to canonical.VOLATILE_KEYS (contract 4.2 step 2)
EXTRA_VOLATILE_KEYS = frozenset({"command", "argv", "working_directory", "cwd", "pid", "hostname", "host",
                                 "project_root", "platform", "python", "executable"})
#: v1 canonical files (records/replay/retest/canonical_artifacts_v1.json); they are promised themselves
V1_CANONICAL = (".rnplens/HEAD", ".rnplens/state/v*.json", ".rnplens/cache/*.json", ".rnplens/cache/invalid/*.json",
                "analyses/v*/index.json", "analyses/v*/update_report.json", "analyses/v*/update_report.html",
                "analyses/reports/*.json", "analyses/reports/*.html", "imports/v*/*/construct_protein.fasta",
                "imports/v*/*/construct_rna.fasta", "imports/v*/*/derived/*/*",
                "analyses/v*/*/report/contacts_by_output.json", "analyses/v*/*/report_runs_*/contacts_by_output.json",
                "analyses/v*/*/region_*/region_contacts.tsv")
INDEX_REL = os.path.join(".rnplens", "run", "projection_index.json")
INDEX_SCHEMA = "rnplens-projection-index-2"
HASH_PREFIX = "projection-sha256:"

_HEX64 = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
_CONSENT = re.compile(r"\b(consent-\d{4})-[0-9a-f]{8}\b")
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")
_COMPACT = re.compile(r"\d{8}T\d{6}Z")
_SHA_CACHE = {}


def project_root(path):
    """The managed project that contains path (nearest ancestor with .rnplens/HEAD), or None."""
    d = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.isfile(os.path.join(d, ".rnplens", "HEAD")):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            return None
        d = nd


def _v1(rel):
    segs = rel.split("/")
    for pat in V1_CANONICAL:
        ps = pat.split("/")
        if len(ps) == len(segs) and all(fnmatch.fnmatchcase(s, q) for s, q in zip(segs, ps)):
            return True
    return False


def eligible(root, path):
    """-> path relative to the project if path needs a projection, else None."""
    rel = os.path.relpath(os.path.abspath(path), root).replace(os.sep, "/")
    if rel.startswith("../") or rel == ".." or rel.split("/")[0] == ".rnplens" or rel.endswith(PROJ_SUFFIXES):
        return None
    if os.path.splitext(rel)[1] not in PROJ_EXT or _v1(rel):
        return None
    return rel


def projection_path(path):
    return path + PROJ_EXT[os.path.splitext(path)[1]]


def _sha(path):
    st = os.stat(path)
    k = (path, st.st_size, st.st_mtime_ns)
    if k not in _SHA_CACHE:
        _SHA_CACHE[k] = pv.sha256_file(path)
    return _SHA_CACHE[k]


def _paths(root):
    from . import canonical as CN
    try:
        from . import state as S
        P = S.Project(root)
        return P.paths(P.head())
    except Exception:
        return CN.Paths(root)


class _Ctx:
    def __init__(self, root, write=True):
        self.root = root
        self.write = write                 # False: projections are computed in memory only (nothing is written)
        self.paths = _paths(root)
        self.index_path = os.path.join(root, INDEX_REL)
        try:
            if not write:
                raise OSError
            with open(self.index_path, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            doc = {}
        self.entries = [e for e in (doc.get("entries") or []) if isinstance(e, dict)]
        self.index = {e.get("raw_sha256"): e.get("projection_sha256") for e in self.entries}
        self.errors = list(doc.get("errors") or [])
        self._scan = None
        self.busy = set()

    def save(self):
        if not self.write:
            return
        pv._atomic(self.index_path, json.dumps({"schema": INDEX_SCHEMA, "entries": self.entries,
                                                "errors": self.errors[-50:]}, indent=1, sort_keys=True) + "\n", "w")

    def add(self, rel, raw_sha, proj_sha):
        """Record raw sha256 -> projection sha256 (list in write order; the latest entry for a raw hash wins)."""
        self.entries.append({"file": rel, "raw_sha256": raw_sha, "projection_sha256": proj_sha})
        self.index[raw_sha] = proj_sha

    def scan(self):
        """{raw sha256: [paths]} of every file of the project that needs a projection (sorted walk order). Several
        files can hold the same bytes (for example the Mol* assets of two viewer pages); each needs its projection."""
        if self._scan is None:
            out = {}
            for dp, dn, fn in os.walk(self.root):
                dn.sort()
                if dp == self.root and ".rnplens" in dn:
                    dn.remove(".rnplens")
                for f in sorted(fn):
                    p = os.path.join(dp, f)
                    if os.path.isfile(p) and not os.path.islink(p) and eligible(self.root, p):
                        out.setdefault(_sha(p), []).append(p)
            self._scan = out
        return self._scan

    def map_hash(self, h):
        """Hash -> projection hash. Every file of the project holding these bytes gets its projection (0.4 RC fix:
        before, only the first such file was projected, so a second identical copy had none)."""
        paths = [p for p in self.scan().get(h, []) if p not in self.busy and not os.path.exists(projection_path(p))]
        for p in paths:
            project_file(p, self)
        if h in self.index:
            return HASH_PREFIX + self.index[h]
        return h

    def text(self, s):
        """Paths, hashes, consent ids and time stamps of one string (JSON value or key, or a whole text file)."""
        s = self.paths.canon_str(s)
        s = _HEX64.sub(lambda m: self.map_hash(m.group(0)), s)
        s = _CONSENT.sub(r"\1", s)
        return _COMPACT.sub("<time>", _ISO.sub("<time>", s))

    def obj(self, o, drop):
        if isinstance(o, dict):
            return {self.text(k) if isinstance(k, str) else k: self.obj(v, drop) for k, v in o.items() if k not in drop}
        if isinstance(o, (list, tuple)):
            return [self.obj(v, drop) for v in o]
        return self.text(o) if isinstance(o, str) else o


def _drop():
    from . import canonical as CN
    return set(CN.VOLATILE_KEYS) | EXTRA_VOLATILE_KEYS | {"evidence_sha256"}


def project_json(obj, ctx, path=None):
    """The projection object of a JSON object (contract 4.2)."""
    o = ctx.obj(ctx.paths.canon(obj), _drop())
    if path and os.path.basename(path) == "followup_record.json" and isinstance(o, dict):
        sib = os.path.join(os.path.dirname(path), "followup_answer.json")
        statements = None
        if os.path.exists(sib):
            with open(sib, encoding="utf-8") as fh:
                statements = (project_json(json.load(fh), ctx, sib) or {}).get("statements")
        log = [{"tool": e.get("tool"), "call": e.get("call"), "status": e.get("status"), "outputs": e.get("outputs"),
                "message": e.get("message")} for e in (o.get("tool_log") or []) if isinstance(e, dict)]
        o["evidence_content_sha256"] = pv.sha256_json({"statements": statements, "tool_log": log})
    return o


def project_text(s, ctx):
    """The projection of a text file (contract 4.3)."""
    return ctx.text(s)


def project_file(path, ctx):
    """Write the projection of path (if it is not already current). -> projection path."""
    from . import canonical as CN
    raw_sha = _sha(path)
    ppath = projection_path(path)
    if not ctx.write and raw_sha in ctx.index:
        return None
    if ctx.write and raw_sha in ctx.index and os.path.exists(ppath) and pv.sha256_file(ppath) == ctx.index[raw_sha]:
        return ppath
    ctx.busy.add(path)
    with open(path, "rb") as fh:
        raw = fh.read()
    text = None
    if path.endswith(".json"):
        try:
            text = CN.dumps(project_json(json.loads(raw.decode("utf-8")), ctx, path))
        except (ValueError, UnicodeDecodeError):
            text = None
    if text is None:
        text = project_text(raw.decode("utf-8", "replace"), ctx)
    if ctx.write:
        pv._atomic(ppath, text, "w")
    ctx.add(os.path.relpath(path, ctx.root).replace(os.sep, "/"), raw_sha, hashlib.sha256(text.encode()).hexdigest())
    ctx.busy.discard(path)
    ctx.save()
    return ppath


def after_write(path):
    """Hook of provenance.atomic_write_json/text: project path if it is an output inside a managed project.
    Never raises; a failure is recorded in the projection index (and shows as a missing projection)."""
    try:
        root = project_root(path)
        if root is None or eligible(root, path) is None:
            return None
    except Exception:
        return None
    ctx = None
    try:
        ctx = _Ctx(root)
        return project_file(os.path.abspath(path), ctx)
    except Exception as ex:      # noqa: BLE001 - an output must never fail because of its projection
        try:
            ctx = ctx or _Ctx(root)
            ctx.errors.append("%s: %s: %s" % (os.path.relpath(path, root), type(ex).__name__, ex))
            ctx.save()
        except Exception:
            pass
        return None


def sweep(root, d):
    """Project every eligible file under d (an import or analysis directory the 0.3 code wrote itself)."""
    root = os.path.abspath(root)
    if not os.path.isdir(d):
        return []
    ctx = _Ctx(root)
    out = []
    for dp, dn, fn in os.walk(d):
        dn.sort()
        for f in sorted(fn):
            p = os.path.join(dp, f)
            if os.path.isfile(p) and not os.path.islink(p) and eligible(root, p):
                out.append(project_file(p, ctx))
    return out


def errors(root):
    try:
        with open(os.path.join(root, INDEX_REL), encoding="utf-8") as fh:
            return list(json.load(fh).get("errors") or [])
    except (OSError, ValueError):
        return []


def location_independent_mapper(*dirs):
    """h -> 'projection-sha256:<...>' when h is the raw SHA-256 of a JSON/text file of these directories, else h.
    Inside a managed project the project's projections and index are used (contract v2); outside one, the same
    projection is computed in memory relative to the common folder of the directories, and nothing is written."""
    dirs = [os.path.abspath(d) for d in dirs if d]
    if not dirs:
        return lambda h: h
    root = project_root(os.path.join(dirs[0], "_"))
    if root is not None:
        ctx = _Ctx(root)
    else:
        try:
            base = os.path.commonpath(dirs)
        except ValueError:
            base = dirs[0]
        ctx = _Ctx(base, write=False)
    return ctx.map_hash
