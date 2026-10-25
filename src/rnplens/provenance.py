"""Shared provenance and file helpers for the 0.4 interactive workflow (contracts document, section 3).

Every new output JSON carries a `provenance` block made by `block()`. Every reported value carries an evidence ID
made by `evidence_id()`. All writes go through `atomic_write_*`, so a crash never leaves a half-written file."""
import datetime
import hashlib
import json
import os
import subprocess
import tempfile

from . import __version__

SCHEMA_VERSION = "rnplens.v04.1"


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def sha256_json(obj):
    """Hash of a JSON-serialisable object with sorted keys; used for configuration and cache keys."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def code_commit():
    """Git commit of the running source tree, or None for an installed package (never guessed)."""
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        p = subprocess.run(["git", "-C", here, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        dirty = subprocess.run(["git", "-C", here, "status", "--porcelain", "--", "."], capture_output=True, text=True, timeout=10)
        return (p.stdout.strip() + ("+dirty" if dirty.stdout.strip() else "")) if p.returncode == 0 else None
    except Exception:
        return None


def block(kind, inputs, definition, config=None, extra=None):
    """Provenance for one output.
    kind: e.g. "region_contacts"; inputs: list of file paths (hashed here) or dicts {path, sha256} (or, for a file
    that is not canonical, {path, content_sha256, raw_file_sha256}; see canonical.py);
    definition: plain-language calculation or filtering definition (also used by the Methods export);
    config: the parameters that change the result (hashed into config_sha256)."""
    ins = []
    for x in inputs:
        if isinstance(x, dict):
            ins.append({k: x[k] for k in ("path", "sha256", "content_sha256", "raw_file_sha256") if k in x})
        else:
            ins.append({"path": os.path.abspath(x), "sha256": sha256_file(x)})
    b = {"schema": SCHEMA_VERSION, "kind": kind, "rnplens_version": __version__, "code_commit": code_commit(),
         "created_utc": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
         "inputs": sorted(ins, key=lambda d: d["path"]), "definition": definition, "config": config or {},
         "config_sha256": sha256_json(config or {})}
    if extra:
        b.update(extra)
    return b


def evidence_id(artifact_relpath, pointer):
    """Evidence ID = '<path relative to the analysis root>#<JSON pointer>', e.g. 'region_40-60/region.json#/contacts/3'."""
    return "%s#%s" % (artifact_relpath.replace(os.sep, "/"), pointer if pointer.startswith("/") else "/" + pointer)


def _atomic(path, data, mode):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp_", suffix=os.path.basename(path))
    try:
        with os.fdopen(fd, mode) as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _project(path):
    """Write the canonical projection of an output inside a managed project (DETERMINISM_CONTRACT_v2; never raises)."""
    from . import projection
    projection.after_write(path)


def atomic_write_json(path, obj):
    _atomic(path, json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n", "w")
    _project(path)


def atomic_write_text(path, text):
    _atomic(path, text, "w")
    _project(path)


def atomic_write_bytes(path, data):
    _atomic(path, data, "wb")
