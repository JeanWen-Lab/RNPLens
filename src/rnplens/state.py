"""Versioned, persistent project state (contracts document, section 5; Project-state track).

A project's state lives in ``<project>/.rnplens/``:

    HEAD                   {"version": "v0003", "sha256": <sha256 of state/v0003.json>}, replaced atomically
    state/v0001.json ...   one immutable (read-only) file per version; never rewritten
    state/abandoned/       a version file that was written but never became HEAD (an interrupted commit), moved
                           here unchanged before its number is reused
    cache/<key>.json       one entry per completed computation: its output directory and the SHA-256 of every file
                           in it, so a later lookup can verify the work before reusing it
    LOCK                   held while one process changes the state
    run/...                volatile execution metadata (time stamps, source commit, raw hashes of non-canonical
                           files) of the canonical files above, one sidecar per file (``canonical.py``)

State versions, HEAD and cache entries are *canonical* (DETERMINISM_CONTRACT_v1): paths relative to the project
("./..." inside it, "../..." for inputs beside it), no time stamp, sorted keys; the same inputs, answers and version
give the same bytes wherever the project lives. ``head()``/``load()`` return the in-memory form (absolute paths, time
stamps merged back from the sidecar). Versions written before this change (schema rnplens-project-state-1, absolute
paths and inline times) are read unchanged; a history may mix both.

Every version is a complete snapshot. It records the SHA-256 of every input file (never a file name or a time stamp
alone), the construct sequence hashes, the correspondence and chain decisions, the tool version, configuration
hashes and selection rules (the pipeline in ``incremental.py`` fills these in), and the SHA-256 of its parent
version's file, so a changed or damaged earlier version is detected (``verify()``).

A failed update never changes the current version: a new version file is complete before HEAD is replaced, and
HEAD is replaced with ``os.replace``. Nothing in this module deletes a file.
"""
import contextlib
import copy
import datetime
import json
import os
import re

from . import canonical as CN
from . import provenance as pv

STATE_SCHEMA = "rnplens-project-state-2"
STATE_SCHEMAS = ("rnplens-project-state-1", STATE_SCHEMA)       # readable; -1 = written before canonical records
CACHE_SCHEMA = "rnplens-cache-entry-2"
CACHE_SCHEMAS = ("rnplens-cache-entry-1", CACHE_SCHEMA)
DIRNAME = ".rnplens"
_VID = re.compile(r"^v(\d{4,})\.json$")


class StateError(Exception):
    """A project-state operation was refused; the message says why and what to do."""


class StateCorrupted(StateError):
    """A state file does not match the hash recorded for it."""


class ContradictoryAnswer(StateError):
    """An answer contradicts a recorded answer that still applies."""


class ProjectLocked(StateError):
    """Another live process holds the project lock."""


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def tool_version():
    """The running RNPLens version, read at call time."""
    import rnplens
    return rnplens.__version__


def key_components(kind, config, input_hashes, construct_sha, correspondence, selection_rule, tool_version,
                   definition=None):
    """The named parts of a cache key, each hashed separately so a report can say which part changed."""
    return {"kind": kind,
            "config_sha256": pv.sha256_json(config),
            "inputs_sha256": pv.sha256_json(input_hashes),
            "construct_sha256": construct_sha,
            "correspondence_sha256": pv.sha256_json(correspondence),
            "selection_rule_sha256": pv.sha256_json(selection_rule),
            "tool_version": tool_version,
            "definition_sha256": pv.sha256_json(definition)}


def analysis_key(kind, config, input_hashes, construct_sha, correspondence, selection_rule, tool_version,
                 definition=None):
    """Cache key of one computation: exact input hashes, construct identity, chain correspondence, candidate and
    engine selection rules, tool version, metric definition and thresholds, and analysis configuration. Two
    computations share a key only if all of these are equal; JSON key order does not matter."""
    return pv.sha256_json(key_components(kind, config, input_hashes, construct_sha, correspondence, selection_rule,
                                         tool_version, definition))


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False
    return True


def tree_hashes(d):
    """{relative path: sha256} of every regular file under d (sorted walk)."""
    out = {}
    for dp, dn, fn in os.walk(d):
        dn.sort()
        for f in sorted(fn):
            p = os.path.join(dp, f)
            if os.path.isfile(p) and not os.path.islink(p):
                out[os.path.relpath(p, d).replace(os.sep, "/")] = pv.sha256_file(p)
    return out


class Project:
    """Versioned state of one project directory. ``Project(root)`` never writes until ``commit`` or a cache store."""

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.dir = os.path.join(self.root, DIRNAME)
        self.state_dir = os.path.join(self.dir, "state")
        self.cache_dir = os.path.join(self.dir, "cache")
        self.head_path = os.path.join(self.dir, "HEAD")
        self._lock_depth = 0

    # ------------------------------------------------------------------ reading
    def exists(self):
        return os.path.exists(self.head_path)

    def _pointer(self):
        if not os.path.exists(self.head_path):
            return None
        try:
            p = json.load(open(self.head_path, encoding="utf-8"))
            assert isinstance(p, dict) and _VID.match(p["version"] + ".json") and len(p["sha256"]) == 64
            return p
        except Exception as ex:
            raise StateCorrupted("%s is unreadable (%s: %s); no version is trusted until it is restored"
                                 % (self.head_path, type(ex).__name__, ex))

    def _path(self, vid):
        return os.path.join(self.state_dir, vid + ".json")

    def _read(self, vid, expect_sha=None):
        p = self._path(vid)
        if not os.path.exists(p):
            raise StateCorrupted("state version %s is missing (%s)" % (vid, p))
        sha = pv.sha256_file(p)
        if expect_sha is not None and sha != expect_sha:
            raise StateCorrupted("state version %s has SHA-256 %s but %s was recorded for it; the file was changed "
                                 "after it was written. Nothing was changed; restore the file or start a new "
                                 "project." % (vid, sha[:12], expect_sha[:12]))
        try:
            st = json.load(open(p, encoding="utf-8"))
        except Exception as ex:
            raise StateCorrupted("state version %s is not valid JSON (%s)" % (vid, ex))
        if st.get("schema") not in STATE_SCHEMAS or st.get("version") != vid:
            raise StateCorrupted("state version %s does not identify itself as %s/%s" % (vid, STATE_SCHEMA, vid))
        if st.get("schema") != STATE_SCHEMAS[0]:
            st = CN.restore(self.root, self._rel(vid), st, sha, self.paths())
        return st, sha

    def _rel(self, vid):
        return os.path.join(DIRNAME, "state", vid + ".json")

    def paths(self, st=None):
        """Path converter for this project; prefixes = declared inputs and reference of ``st`` (when given)."""
        pre = []
        decl = (st or {}).get("declared") or {}
        pre += list(decl.get("inputs") or [])
        ref = (decl.get("config") or {}).get("reference")
        if ref and ref.get("path"):
            pre.append(ref["path"])
        return CN.Paths(self.root, pre)

    def head_id(self):
        p = self._pointer()
        return p["version"] if p else None

    def head(self):
        """The current state (a dict), verified against the hash in HEAD; None for a project with no version."""
        p = self._pointer()
        if p is None:
            return None
        return self._read(p["version"], p["sha256"])[0]

    def load(self, vid):
        """One version, verified through the hash chain from HEAD."""
        for v in self.versions():
            if v["version"] == vid:
                return self._read(vid, v["sha256"])[0]
        raise StateError("no version %s in the history of this project" % vid)

    def versions(self):
        """The committed history, oldest first: [{version, parent, sha256, reason, created_utc, status}].
        Every parent hash is checked; a mismatch raises StateCorrupted."""
        p = self._pointer()
        if p is None:
            return []
        out, vid, sha = [], p["version"], p["sha256"]
        seen = set()
        while vid:
            if vid in seen:
                raise StateCorrupted("state history has a cycle at %s" % vid)
            seen.add(vid)
            st, _ = self._read(vid, sha)
            out.append({"version": vid, "parent": st.get("parent"), "sha256": sha, "reason": st.get("reason"),
                        "created_utc": st.get("created_utc"), "status": st.get("status")})
            vid, sha = st.get("parent"), st.get("parent_sha256")
            if vid and not sha:
                raise StateCorrupted("state version %s records no hash for its parent %s" % (out[-1]["version"], vid))
        return out[::-1]

    def verify(self):
        """-> list of problems (empty when HEAD and every earlier version match their recorded hashes)."""
        try:
            self.versions()
        except StateError as ex:
            return [str(ex)]
        return []

    # ------------------------------------------------------------------ writing
    @contextlib.contextmanager
    def lock(self):
        """Exclusive, re-entrant within one process; a lock left by a process that no longer runs is taken over
        (and the take-over is noted in the lock file)."""
        if self._lock_depth:
            self._lock_depth += 1
            try:
                yield
            finally:
                self._lock_depth -= 1
            return
        os.makedirs(self.dir, exist_ok=True)
        lp = os.path.join(self.dir, "LOCK")
        body = json.dumps({"pid": os.getpid(), "since_utc": now_utc()})
        try:
            fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.write(fd, body.encode()); os.close(fd)
        except FileExistsError:
            try:
                held = json.load(open(lp, encoding="utf-8"))
            except Exception:
                held = {"pid": None}
            if held.get("pid") and held["pid"] != os.getpid() and _pid_alive(held["pid"]):
                raise ProjectLocked("project %s is being changed by process %s (since %s); try again when it has "
                                    "finished" % (self.root, held["pid"], held.get("since_utc")))
            pv.atomic_write_text(lp, json.dumps({"pid": os.getpid(), "since_utc": now_utc(),
                                                 "took_over_from": held}))
        self._lock_depth = 1
        try:
            yield
        finally:
            self._lock_depth = 0
            try:
                os.unlink(lp)
            except FileNotFoundError:
                pass

    def _write_head(self, vid, sha):
        """Replace HEAD atomically (separate method so tests can inject a failure here)."""
        pv.atomic_write_json(self.head_path, {"version": vid, "sha256": sha})

    def commit(self, change, reason):
        """New version = current state with the top-level keys of ``change`` replaced. Returns its id.
        The version file is written completely (and made read-only) before HEAD moves to it."""
        if not isinstance(change, dict):
            raise StateError("commit needs a dict of state fields to change")
        with self.lock():
            prev_ptr = self._pointer()
            prev = self.head()
            st = copy.deepcopy(prev) if prev else {}
            for k, v in change.items():
                if k in ("schema", "version", "parent", "parent_sha256"):
                    raise StateError("commit cannot set %r" % k)
                st[k] = copy.deepcopy(v)
            n = int(prev["version"][1:]) + 1 if prev else 1
            vid = "v%04d" % n
            st.update({"schema": STATE_SCHEMA, "version": vid, "parent": prev["version"] if prev else None,
                       "parent_sha256": prev_ptr["sha256"] if prev_ptr else None, "created_utc": now_utc(),
                       "reason": reason, "changed_fields": sorted(change), "tool_version": tool_version(),
                       "code_commit": pv.code_commit()})
            os.makedirs(self.state_dir, exist_ok=True)
            path = self._path(vid)
            if os.path.exists(path):         # written by an interrupted commit, never HEAD: keep it, aside
                ab = os.path.join(self.state_dir, "abandoned")
                os.makedirs(ab, exist_ok=True)
                CN.move_with_sidecar(self.root, self._rel(vid), os.path.join(
                    os.path.relpath(ab, self.root), CN.next_free(ab, vid)))
            sha = CN.write(self.root, self._rel(vid), st, self.paths(st), mode=0o444)
            self._write_head(vid, sha)
            return vid

    # ------------------------------------------------------------------ decisions
    def decisions(self, include_inactive=False):
        """Recorded answers of the current version: {question id: record}. Only ACTIVE ones unless asked."""
        st = self.head() or {}
        d = st.get("decisions") or {}
        return {k: v for k, v in d.items() if include_inactive or v.get("status") == "ACTIVE"}

    def decision_log(self):
        return list((self.head() or {}).get("decision_log") or [])

    def check_answer(self, id, answer, depends_on, revise=False):
        """-> None if the answer can be recorded, "unchanged" if exactly this answer is already recorded; raises
        ContradictoryAnswer otherwise. Never overwrites silently."""
        active = self.decisions()
        cur = active.get(id)
        if cur is not None:
            if cur["option"] == answer["option"] and cur["depends_on"] == depends_on:
                return "unchanged"
            if not revise:
                raise ContradictoryAnswer(
                    "%s was already answered %r (recorded %s, in %s) and that answer still applies. The new answer "
                    "%r contradicts it, so nothing was recorded. To replace it, answer again with --revise (the "
                    "earlier answer is kept in the history as superseded)." % (
                        id, cur["option"], cur["recorded_utc"], cur["recorded_in_version"], answer["option"]))
        for oid, rec in sorted(active.items()):
            if oid == id:
                continue
            for k, v in sorted((answer.get("effects") or {}).items()):
                if k in (rec.get("effects") or {}) and rec["effects"][k] != v:
                    raise ContradictoryAnswer(
                        "the answer %r to %s sets %s = %r, but the recorded answer %r to %s (recorded %s) sets it to "
                        "%r. Nothing was recorded. Revise %s first if it no longer holds." % (
                            answer["option"], id, k, v, rec["option"], oid, rec["recorded_utc"], rec["effects"][k], oid))
        return None

    def record_decision(self, id, answer, depends_on, revise=False, extra_change=None, reason=None):
        """Record a user's answer with provenance and commit a new version. ``answer`` holds at least ``option``;
        optional ``text`` (the user's own words), ``effects`` (facts it fixes, checked for contradictions),
        ``apply`` (how the pipeline uses it) and ``question`` (the request as shown). ``depends_on`` maps each input
        the answer rests on to its SHA-256; when one of them changes the answer stops applying.
        -> (version id, record)."""
        if not isinstance(answer, dict) or not answer.get("option"):
            raise StateError("an answer needs an option id")
        if not isinstance(depends_on, dict) or not depends_on:
            raise StateError("an answer must name the input hashes it depends on")
        with self.lock():
            if self.check_answer(id, answer, depends_on, revise) == "unchanged":
                return self.head_id(), self.decisions()[id]
            st = self.head() or {}
            decs = copy.deepcopy(st.get("decisions") or {})
            log = copy.deepcopy(st.get("decision_log") or [])
            nxt = "v%04d" % ((int(st["version"][1:]) if st else 0) + 1)
            prev = decs.get(id)
            rec = {"id": id, "option": answer["option"], "text": answer.get("text"),
                   "effects": answer.get("effects") or {}, "apply": answer.get("apply") or {},
                   "question": answer.get("question"), "request_type": answer.get("request_type"),
                   "depends_on": dict(sorted(depends_on.items())), "recorded_utc": now_utc(),
                   "recorded_in_version": nxt, "status": "ACTIVE", "serial": len(log) + 1,
                   "supersedes": prev["serial"] if prev and prev.get("status") == "ACTIVE" else None}
            if rec["supersedes"]:
                log.append(dict(prev, status="SUPERSEDED", status_utc=rec["recorded_utc"],
                                status_reason="replaced by answer %d (--revise)" % rec["serial"]))
            decs[id] = rec
            log.append(rec)
            change = {"decisions": decs, "decision_log": log}
            change.update(extra_change or {})
            vid = self.commit(change, reason or "answer recorded for %s: %s" % (id, answer["option"]))
            return vid, rec

    # ------------------------------------------------------------------ cache
    def _cache_path(self, key):
        if not re.fullmatch(r"[0-9a-f]{64}", key or ""):
            raise StateError("cache keys are SHA-256 hex strings")
        return os.path.join(self.cache_dir, key + ".json")

    def cache_lookup(self, key):
        """-> the cache entry (with ``path``, the absolute output directory) if the work for ``key`` exists and
        every file it recorded still has its recorded SHA-256; otherwise None (the work is redone, never trusted)."""
        p = self._cache_path(key)
        if not os.path.exists(p):
            return None
        try:
            e = json.load(open(p, encoding="utf-8"))
            if e.get("schema") == CACHE_SCHEMA:          # canonical entry: file hashes and time in the sidecar
                e = CN.read(self.root, os.path.relpath(p, self.root))
        except Exception:
            return None
        d = os.path.join(self.root, e.get("outdir", ""))
        if e.get("schema") not in CACHE_SCHEMAS or e.get("key") != key or not os.path.isdir(d):
            return None
        now = tree_hashes(d)
        rec = e.get("files") or {}
        if not rec or any(now.get(f) != h for f, h in rec.items()):      # a recorded file changed or is missing
            return None
        return dict(e, path=d)

    def cache_store(self, key, outdir, meta):
        """Record completed work for ``key``. ``outdir`` must lie inside the project. An existing valid entry is
        kept (the same key means the same computation); an invalid one is moved to cache/invalid/."""
        a = os.path.abspath(outdir)
        if os.path.commonpath([a, self.root]) != self.root or not os.path.isdir(a):
            raise StateError("cache_store: %s is not a directory inside the project %s" % (outdir, self.root))
        with self.lock():
            old = self.cache_lookup(key)
            if old is not None:
                return old
            p = self._cache_path(key)
            rel = os.path.relpath(p, self.root)
            if os.path.exists(p):
                inv = os.path.join(self.cache_dir, "invalid")
                os.makedirs(inv, exist_ok=True)
                CN.move_with_sidecar(self.root, rel, os.path.join(os.path.relpath(inv, self.root), CN.next_free(inv, key)))
            e = {"schema": CACHE_SCHEMA, "key": key, "outdir": os.path.relpath(a, self.root).replace(os.sep, "/"),
                 "meta": meta or {}, "stored_utc": now_utc(), "tool_version": tool_version()}
            files = tree_hashes(a)
            CN.write(self.root, rel, e, CN.Paths(self.root), sidecar_only={"/files": files})
            return dict(e, files=files, path=a)
