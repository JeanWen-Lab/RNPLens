#!/usr/bin/env python3
"""Release manifest verifier for RNPLens (development tool; stdlib only).

Given a git repository and qualification receipts (test-run records, clean-install records, replay, viewer and
live-qualification reports, each with the commit it was produced at), it writes RELEASE_MANIFEST.json and .md with:
  - HEAD sha, branch, clean-tree status;
  - every receipt with its file SHA-256 and the commit it claims, compared with HEAD;
  - a wheel and an sdist of every package, built from HEAD (``git archive``) in a temporary directory, with every
    member's SHA-256 and the archives' SHA-256;
  - the non-technical release conditions (licence, distribution), OPEN unless an approval record is supplied.

It FAILS (exit 1; the files are then named RELEASE_MANIFEST.FAILED.*) when the tree is dirty, when no receipt is
given, when a receipt states no commit, several commits, or a commit other than HEAD, or when a package build fails
or is skipped. A passing run only says that the receipts point at HEAD and that the packages were built from it; it
does not check what the receipts say, and it cannot verify that an approval record is authentic.

How a receipt states its commit (exactly one distinct commit per receipt):
  * JSON: a key ``receipt_commit``, ``commit``, ``recorded_commit``, ``tested_commit``, ``git_commit``,
    ``source_commit``, ``code_commit`` or ``head``, at top level or inside ``provenance``/``source``/``git``/
    ``repository``;
  * text or Markdown: a line ``Receipt-Commit: <sha>`` (also ``Recorded commit:`` or ``Tested commit:``; Markdown
    bold and backticks allowed);
  * a text file whose whole content is one sha;
  * for older prose records: an index file (``--index``) that transcribes each record's claimed commit, with
    ``{"receipts": [{"path": ..., "claimed_commit": ..., "kind": ..., "claim_source": ...}]}`` (relative paths are
    relative to the repository root; every indexed receipt is assessed). A commit declared in
    the file itself must agree with the index.

Approval records (``--approval FILE``, JSON): ``{"condition": "licence" | "distribution",
"status": "APPROVED", "approved_by": ..., "date": ..., "reference": ...}``.

``--require-kind KIND`` (repeatable) fails the run unless a receipt of that kind points at HEAD; without it, the
tool does not know which receipts a release needs.

Exit codes: 0 technical checks pass; 1 verification failed; 2 usage or input error (nothing written);
3 technical checks pass but ``--require-approvals`` was given and a condition is OPEN.

Usage:
  python tools/release_manifest.py --repo . --receipts RECEIPT_OR_DIR ... [--index INDEX.json]
         [--approval APPROVAL.json ...] [--package . --package assistant] [--no-build] --out DIR
"""
import argparse
import base64
import csv
import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile

SCHEMA = "RNPLENS_RELEASE_MANIFEST_V1"
SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
JSON_KEYS = ("receipt_commit", "commit", "recorded_commit", "tested_commit", "git_commit", "source_commit",
             "code_commit", "head")
JSON_NESTS = ("provenance", "source", "git", "repository")
TEXT_DECL = re.compile(r"^[\s>*\-]*(?:\*\*)?\s*(receipt[- ]commit|recorded commit|tested commit)\s*(?:\*\*)?\s*[:=]"
                       r"\s*(?:\*\*)?\s*`?([0-9a-fA-F]{7,40})`?", re.I)
RECEIPT_EXT = (".json", ".md", ".txt", ".log")
CONDITIONS = [
    ("licence", "Approval of the licence (MIT, as stated in LICENSE) for public distribution"),
    ("distribution", "Approval to distribute publicly (public GitHub release, package index, archive DOI)"),
]


class UsageError(Exception):
    pass


# ---------------------------------------------------------------- small helpers
def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic(path, data, mode):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=d)
    try:
        with os.fdopen(fd, mode) as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def atomic_write_json(path, obj):
    _atomic(path, json.dumps(obj, indent=1, sort_keys=True) + "\n", "w")


def atomic_write_text(path, text):
    _atomic(path, text, "w")


def git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True)
    if check and r.returncode != 0:
        raise UsageError("git %s failed: %s" % (" ".join(args), r.stderr.strip()))
    return r


def resolve(repo, sha):
    r = git(repo, "rev-parse", "--verify", "--quiet", sha + "^{commit}", check=False)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


# ---------------------------------------------------------------- repository state
def repo_state(repo):
    top = git(repo, "rev-parse", "--show-toplevel").stdout.strip()
    head = git(top, "rev-parse", "HEAD").stdout.strip()
    branch = git(top, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    dirty = [l for l in git(top, "status", "--porcelain", "--untracked-files=all").stdout.splitlines() if l.strip()]
    tags = [t for t in git(top, "tag", "--points-at", "HEAD").stdout.split() if t]
    ctime = int(git(top, "show", "-s", "--format=%ct", "HEAD").stdout.strip())
    subject = git(top, "show", "-s", "--format=%s", "HEAD").stdout.strip()
    return {"toplevel": top, "head": head, "head_short": head[:7], "branch": "DETACHED" if branch == "HEAD" else branch,
            "clean": not dirty, "dirty_entries": dirty, "tags_at_head": tags, "head_subject": subject,
            "head_commit_time_utc": datetime.datetime.fromtimestamp(ctime, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "_ctime": ctime}


# ---------------------------------------------------------------- receipts
def collect_receipts(paths):
    out, seen = [], set()
    for p in paths:
        if not os.path.exists(p):
            raise UsageError("receipt path does not exist: %s" % p)
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__")
                for f in sorted(files):
                    if f.lower().endswith(RECEIPT_EXT) and not f.startswith("."):
                        fp = os.path.abspath(os.path.join(root, f))
                        if fp not in seen:
                            seen.add(fp); out.append(fp)
        else:
            fp = os.path.abspath(p)
            if fp not in seen:
                seen.add(fp); out.append(fp)
    return out


def declared_commits(path):
    """-> (list of (sha, where)) declared by the file itself."""
    raw = open(path, "rb").read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return []
    found = []
    if path.lower().endswith(".json"):
        try:
            obj = json.loads(text)
        except ValueError:
            obj = None
        if isinstance(obj, dict):
            scopes = [("", obj)] + [(n + ".", obj[n]) for n in JSON_NESTS if isinstance(obj.get(n), dict)]
            for prefix, d in scopes:
                for k in JSON_KEYS:
                    if k in d:
                        v = d[k]
                        found.append((v if isinstance(v, str) else repr(v), "json:%s%s" % (prefix, k)))
            return found
    stripped = text.strip()
    if SHA_RE.match(stripped):
        return [(stripped, "whole file")]
    for i, line in enumerate(text.splitlines(), 1):
        m = TEXT_DECL.match(line)
        if m:
            found.append((m.group(2), "line %d: %s" % (i, m.group(1))))
    return found


def load_index(path, repo):
    if path is None:
        return {}, None
    try:
        obj = json.load(open(path))
    except (OSError, ValueError) as ex:
        raise UsageError("cannot read index %s: %s" % (path, ex))
    if not isinstance(obj, dict) or not isinstance(obj.get("receipts"), list):
        raise UsageError("index %s must be {\"receipts\": [...]}" % path)
    base = repo                                        # relative receipt paths are relative to the repository root
    entries = {}
    for e in obj["receipts"]:
        if not isinstance(e, dict) or "path" not in e:
            raise UsageError("index entry without a path: %r" % (e,))
        p = e["path"] if os.path.isabs(e["path"]) else os.path.join(base, e["path"])
        entries[os.path.abspath(p)] = e
    return entries, {"path": os.path.abspath(path), "sha256": sha256_file(path), "n_entries": len(entries),
                     "note": obj.get("note")}


def assess_receipt(repo, head, path, index_entry):
    rec = {"path": path, "sha256": sha256_file(path), "size": os.path.getsize(path),
           "kind": (index_entry or {}).get("kind"), "claim_source": None, "claimed_commit": None,
           "claimed_commit_resolved": None, "matches_head": False}
    rel = os.path.relpath(path, repo)
    if not rel.startswith(".."):
        rec["repo_path"] = rel
        tracked = git(repo, "ls-files", "--error-unmatch", rel, check=False).returncode == 0
        rec["tracked_at_head"] = tracked
    if rec["kind"] is None and path.lower().endswith(".json"):
        try:
            obj = json.load(open(path))
            if isinstance(obj, dict) and isinstance(obj.get("receipt"), str):
                rec["kind"] = obj["receipt"]
        except (OSError, ValueError):
            pass
    decl = declared_commits(path)
    distinct = sorted({s.lower() for s, _ in decl})
    idx = (index_entry or {}).get("claimed_commit")
    if len(distinct) > 1:
        rec.update(status="AMBIGUOUS", claim_source="; ".join(w for _, w in decl),
                   message="states %d different commits (%s); a receipt must state exactly one" % (len(distinct), ", ".join(distinct)))
        return rec
    if distinct and idx and resolve(repo, distinct[0]) != resolve(repo, str(idx)):
        rec.update(status="CONFLICT", claimed_commit=distinct[0], claim_source=decl[0][1],
                   message="the file states %s but the index says %s" % (distinct[0], idx))
        return rec
    if distinct:
        claim, src = distinct[0], decl[0][1]
    elif idx:
        claim, src = str(idx), "index" + (" (%s)" % index_entry["claim_source"] if index_entry.get("claim_source") else "")
    else:
        rec.update(status="NO_COMMIT", message="states no commit (see the module docstring for the accepted forms)")
        return rec
    rec["claimed_commit"], rec["claim_source"] = claim, src
    if not SHA_RE.match(claim):
        rec.update(status="NO_COMMIT", message="the stated commit %r is not a commit id" % claim)
        return rec
    full = resolve(repo, claim)
    if full is None:
        rec.update(status="UNRESOLVED", message="commit %s is not in this repository (or is ambiguous)" % claim)
        return rec
    rec["claimed_commit_resolved"] = full
    if full == head:
        rec.update(status="OK", matches_head=True, message="points at HEAD")
        return rec
    anc = git(repo, "merge-base", "--is-ancestor", full, head, check=False).returncode == 0
    rec["claimed_is_ancestor_of_head"] = anc
    if anc:
        rec["commits_between"] = int(git(repo, "rev-list", "--count", "%s..%s" % (full, head)).stdout.strip())
        changed = [l for l in git(repo, "diff", "--name-only", full, head).stdout.splitlines() if l]
        rec["files_changed_since_claim"] = {"count": len(changed), "first_50": changed[:50]}
    rec.update(status="MISMATCH", message="claims %s, HEAD is %s%s" % (full[:7], head[:7],
               " (%d later commit(s))" % rec["commits_between"] if anc else " (not an ancestor of HEAD)"))
    return rec


# ---------------------------------------------------------------- approvals
def assess_conditions(approval_paths):
    by = {}
    notes = []
    for p in approval_paths:
        try:
            obj = json.load(open(p))
        except (OSError, ValueError) as ex:
            raise UsageError("cannot read approval record %s: %s" % (p, ex))
        cid = obj.get("condition") if isinstance(obj, dict) else None
        rec = {"path": os.path.abspath(p), "sha256": sha256_file(p)}
        problems = []
        if cid not in dict(CONDITIONS):
            problems.append("unknown condition %r" % (cid,))
        if not isinstance(obj, dict) or obj.get("status") != "APPROVED":
            problems.append("status is not APPROVED")
        for f in ("approved_by", "date", "reference"):
            if not (isinstance(obj, dict) and isinstance(obj.get(f), str) and obj.get(f).strip()):
                problems.append("missing %s" % f)
        if problems:
            notes.append({"record": rec, "problems": problems})
            continue
        rec.update({f: obj[f] for f in ("approved_by", "date", "reference")})
        by.setdefault(cid, []).append(rec)
    out = []
    for cid, desc in CONDITIONS:
        if cid in by:
            out.append({"id": cid, "description": desc, "status": "APPROVAL RECORD SUPPLIED", "records": by[cid],
                        "note": "the record is listed with its SHA-256; this tool cannot verify that it is authentic"})
        else:
            out.append({"id": cid, "description": desc, "status": "OPEN", "records": []})
    return out, notes


# ---------------------------------------------------------------- packages
def _build_one(pkgdir, outdir, env):
    code = ("import os, re, sys\n"
            "d, out = sys.argv[1], sys.argv[2]\n"
            "os.chdir(d)\n"
            "try:\n"
            "    import tomllib\n"
            "    name = tomllib.load(open('pyproject.toml', 'rb')).get('build-system', {}).get('build-backend')\n"
            "except ImportError:\n"
            "    name = None\n"
            "    for line in open('pyproject.toml'):\n"
            "        if line.strip().startswith('build-backend') and '=' in line:\n"
            "            name = line.split('=', 1)[1].strip().strip('\"').strip(\"'\")\n"
            "name = name or 'setuptools.build_meta:__legacy__'\n"
            "mod, _, obj = name.partition(':')\n"
            "import importlib\n"
            "b = importlib.import_module(mod)\n"
            "if obj:\n"
            "    for part in obj.split('.'): b = getattr(b, part)\n"
            "s = b.build_sdist(out)\n"
            "w = b.build_wheel(out)\n"
            "try:\n"
            "    import importlib.metadata as md; ver = md.version(mod.split('.')[0])\n"
            "except Exception:\n"
            "    ver = 'unknown'\n"
            "print('BUILT', name, ver, s, w)\n")
    r = subprocess.run([sys.executable, "-c", code, pkgdir, outdir], capture_output=True, text=True, env=env)
    return r


def _members_zip(path):
    out = []
    with zipfile.ZipFile(path) as z:
        for info in sorted(z.infolist(), key=lambda i: i.filename):
            if info.is_dir():
                continue
            data = z.read(info.filename)
            out.append({"name": info.filename, "size": len(data), "sha256": sha256_bytes(data)})
        record_ok, record_problems = True, []
        recs = [n for n in z.namelist() if n.endswith(".dist-info/RECORD")]
        if len(recs) != 1:
            record_ok, record_problems = False, ["expected one RECORD, found %d" % len(recs)]
        else:
            listed = {}
            for row in csv.reader(io.StringIO(z.read(recs[0]).decode("utf-8"))):
                if row and row[0] != recs[0]:
                    listed[row[0]] = row[1] if len(row) > 1 else ""
            for m in out:
                if m["name"] == recs[0]:
                    continue
                want = listed.pop(m["name"], None)
                got = "sha256=" + base64.urlsafe_b64encode(bytes.fromhex(m["sha256"])).rstrip(b"=").decode()
                if want != got:
                    record_ok = False; record_problems.append("RECORD hash differs or missing: %s" % m["name"])
            for n in listed:
                record_ok = False; record_problems.append("RECORD lists a missing file: %s" % n)
    return out, {"wheel_record_consistent": record_ok, "problems": record_problems[:20]}


def _members_tar(path):
    out = []
    with tarfile.open(path, "r:*") as t:
        for m in sorted(t.getmembers(), key=lambda m: m.name):
            if not m.isfile():
                continue
            data = t.extractfile(m).read()
            out.append({"name": m.name, "size": len(data), "sha256": sha256_bytes(data)})
    return out


def build_packages(repo, head, ctime, packages):
    results, failures = [], []
    with tempfile.TemporaryDirectory(prefix="rnplens_release_manifest_") as tmp:
        src = os.path.join(tmp, "src")
        os.makedirs(src)
        arch = subprocess.run(["git", "-C", repo, "archive", "--format=tar", head], capture_output=True)
        if arch.returncode != 0:
            return [], [("BUILD_FAILED", "git archive of HEAD failed: %s" % arch.stderr.decode(errors="replace").strip())]
        with tarfile.open(fileobj=io.BytesIO(arch.stdout)) as t:
            t.extractall(src)
        head_files = {}
        for root, _, files in os.walk(src):
            for f in files:
                p = os.path.join(root, f)
                head_files[os.path.relpath(p, src).replace(os.sep, "/")] = sha256_file(p)
        env = dict(os.environ, SOURCE_DATE_EPOCH=str(ctime), PYTHONDONTWRITEBYTECODE="1")
        env.pop("PYTHONPATH", None)
        for pkg in packages:
            pdir = os.path.normpath(os.path.join(src, pkg))
            entry = {"package_dir": pkg, "archives": []}
            if not os.path.isfile(os.path.join(pdir, "pyproject.toml")):
                failures.append(("BUILD_FAILED", "package %s: no pyproject.toml at HEAD" % pkg))
                entry["status"] = "NO_PYPROJECT"; results.append(entry); continue
            out = os.path.join(tmp, "dist", pkg.replace("/", "_").replace(".", "_root") or "root")
            os.makedirs(out)
            r = _build_one(pdir, out, env)
            if r.returncode != 0:
                failures.append(("BUILD_FAILED", "package %s: build failed: %s" % (pkg, (r.stderr or r.stdout).strip()[-800:])))
                entry["status"] = "BUILD_FAILED"; results.append(entry); continue
            line = [l for l in r.stdout.splitlines() if l.startswith("BUILT ")][-1].split()
            entry.update(status="BUILT", build_backend=line[1], build_backend_version=line[2])
            prefix = os.path.relpath(pdir, src).replace(os.sep, "/")
            prefix = "" if prefix == "." else prefix + "/"
            for fname in sorted(os.listdir(out)):
                fp = os.path.join(out, fname)
                a = {"file": fname, "sha256": sha256_file(fp), "size": os.path.getsize(fp)}
                if fname.endswith(".whl"):
                    a["kind"] = "wheel"
                    a["members"], a["record_check"] = _members_zip(fp)
                    if not a["record_check"]["wheel_record_consistent"]:
                        failures.append(("BUILD_FAILED", "package %s: wheel RECORD inconsistent" % pkg))
                elif fname.endswith((".tar.gz", ".zip")):
                    a["kind"] = "sdist"
                    a["members"] = _members_tar(fp)
                    top = fname[:-7] if fname.endswith(".tar.gz") else fname[:-4]
                    same, generated, differs = 0, [], []
                    for m in a["members"]:
                        rel = m["name"][len(top) + 1:] if m["name"].startswith(top + "/") else m["name"]
                        h = head_files.get(prefix + rel)
                        if h is None:
                            generated.append(rel)
                        elif h == m["sha256"]:
                            same += 1
                        else:
                            differs.append(rel)
                    a["head_comparison"] = {"members_identical_to_head": same, "members_not_in_head": generated,
                                            "members_differing_from_head": differs}
                    if differs:
                        failures.append(("BUILD_FAILED", "package %s: sdist members differ from HEAD: %s" % (pkg, ", ".join(differs[:5]))))
                else:
                    a["kind"] = "other"
                a["n_members"] = len(a.get("members", []))
                a["members_digest"] = sha256_bytes("".join("%s\t%s\n" % (x["name"], x["sha256"]) for x in a.get("members", [])).encode())
                entry["archives"].append(a)
            names = [a["file"] for a in entry["archives"]]
            entry["name_version"] = names[0].rsplit(".tar.gz", 1)[0] if names else None
            results.append(entry)
    return results, failures


# ---------------------------------------------------------------- report
def render_md(m):
    L = []
    ok = m["verdict"] == "PASS"
    L.append("# RNPLens release manifest" if ok else "# RNPLens release manifest: VERIFICATION FAILED (not a release manifest)")
    L.append("")
    L.append("**Verdict: %s.** %s" % (m["verdict"], "Every receipt points at HEAD, the tree is clean and the packages were built from HEAD."
             if ok else "%d failure(s); see below." % len(m["failures"])))
    open_c = [c["id"] for c in m["conditions"] if c["status"] == "OPEN"]
    L.append("**Non-technical release conditions OPEN: %s.**" % (", ".join(open_c) if open_c else "none (approval records supplied; authenticity not verified by this tool)"))
    L.append("")
    r = m["repository"]
    L += ["## Repository", "", "| field | value |", "|---|---|",
          "| HEAD | `%s` |" % r["head"], "| branch | `%s` |" % r["branch"], "| clean tree | %s |" % ("yes" if r["clean"] else "**no** (%d entries)" % len(r["dirty_entries"])),
          "| tags at HEAD | %s |" % (", ".join(r["tags_at_head"]) or "none"), "| HEAD commit time (UTC) | %s |" % r["head_commit_time_utc"],
          "| HEAD subject | %s |" % r["head_subject"].replace("|", "\\|"), ""]
    if m["failures"]:
        L += ["## Failures", ""] + ["- **%s**: %s" % (f["code"], f["message"]) for f in m["failures"]] + [""]
    L += ["## Receipts", "", "| receipt | sha256 | claimed commit | source of claim | status |", "|---|---|---|---|---|"]
    for x in m["receipts"]:
        L.append("| `%s` | `%s` | %s | %s | %s |" % (x.get("repo_path", x["path"]), x["sha256"][:16] + "…",
                 "`%s`" % x["claimed_commit"] if x["claimed_commit"] else "-", (x["claim_source"] or "-").replace("|", "\\|"),
                 x["status"] + ("" if x["status"] == "OK" else ": " + x.get("message", ""))))
    if m.get("required_kinds"):
        L += ["", "Required receipt kinds: " + "; ".join("%s: %s" % (r["kind"], ", ".join("`%s`" % p for p in r["receipts_ok"]) or "**missing**") for r in m["required_kinds"])]
    if m.get("receipt_index"):
        L += ["", "Index of transcribed claims: `%s` (sha256 `%s`)." % (m["receipt_index"]["path"], m["receipt_index"]["sha256"])]
    L += ["", "## Packages (built from HEAD in a temporary directory)", ""]
    if not m["packages"]:
        L.append("No package was built (%s)." % m.get("build_note", "build skipped"))
    for p in m["packages"]:
        L.append("### `%s` (%s)" % (p["package_dir"], p.get("status")))
        for a in p.get("archives", []):
            L.append("")
            L.append("- **%s** `%s`: sha256 `%s`, %d bytes, %d members; member digest `%s`" % (a["kind"], a["file"], a["sha256"], a["size"], a["n_members"], a.get("members_digest")))
            if a["kind"] == "wheel":
                L.append("  - RECORD consistent: %s" % a["record_check"]["wheel_record_consistent"])
            if a["kind"] == "sdist":
                hc = a["head_comparison"]
                L.append("  - members identical to HEAD: %d; generated by the build (not in HEAD): %d; differing from HEAD: %d"
                         % (hc["members_identical_to_head"], len(hc["members_not_in_head"]), len(hc["members_differing_from_head"])))
            L += ["", "  | member | size | sha256 |", "  |---|---|---|"]
            L += ["  | `%s` | %d | `%s` |" % (x["name"], x["size"], x["sha256"]) for x in a.get("members", [])]
        L.append("")
    L += ["## Non-technical release conditions", "", "| condition | status | record |", "|---|---|---|"]
    for c in m["conditions"]:
        L.append("| %s | %s | %s |" % (c["description"], c["status"],
                 "; ".join("`%s` (sha256 `%s…`)" % (x["path"], x["sha256"][:16]) for x in c["records"]) or "-"))
    if m.get("approval_record_problems"):
        L += ["", "Approval records not accepted:"] + ["- `%s`: %s" % (x["record"]["path"], "; ".join(x["problems"])) for x in m["approval_record_problems"]]
    e = m["execution"]
    L += ["", "## Execution (volatile; not part of the verified content)", "",
          "Created %s by `tools/release_manifest.py` (sha256 `%s`), Python %s on %s." % (e["created_utc"], e["tool_sha256"], e["python"], e["platform"]),
          "", "The wheel archives were byte-reproducible in development; sdist archives are not (the gzip header holds a",
          "time stamp), so for an sdist compare the member digest (SHA-256 over the sorted member names and hashes).",
          "", "This manifest describes HEAD and is not part of it: keep it outside the release commit (for example as an",
          "attachment of the release), otherwise committing it changes HEAD and the receipts no longer match.", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- main
def run(args):
    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        raise UsageError("not a directory: %s" % repo)
    st = repo_state(repo)
    repo = st["toplevel"]
    out = os.path.abspath(args.out)
    if os.path.commonpath([out, repo]) == repo:
        raise UsageError("--out %s is inside the repository; write the manifest outside the release tree" % out)
    for n in ("RELEASE_MANIFEST.json", "RELEASE_MANIFEST.md", "RELEASE_MANIFEST.FAILED.json", "RELEASE_MANIFEST.FAILED.md"):
        if os.path.exists(os.path.join(out, n)):
            raise UsageError("%s already exists in %s; nothing is overwritten" % (n, out))
    index, index_meta = load_index(args.index, repo)
    paths = collect_receipts(args.receipts or [])
    for p in index:
        if p not in paths:
            if not os.path.exists(p):
                raise UsageError("index names a receipt that does not exist: %s" % p)
            paths.append(p)
    conditions, approval_problems = assess_conditions(args.approval or [])
    failures = []
    if not st["clean"]:
        failures.append(("DIRTY_TREE", "the working tree is not clean (%d entries, e.g. %s)" % (len(st["dirty_entries"]), st["dirty_entries"][0])))
    if not paths:
        failures.append(("NO_RECEIPTS", "no qualification receipt was supplied"))
    receipts = [assess_receipt(repo, st["head"], p, index.get(p)) for p in paths]
    for x in receipts:
        if x["status"] != "OK":
            code = {"MISMATCH": "RECEIPT_COMMIT_MISMATCH", "NO_COMMIT": "RECEIPT_WITHOUT_COMMIT",
                    "AMBIGUOUS": "RECEIPT_AMBIGUOUS_COMMIT", "UNRESOLVED": "RECEIPT_COMMIT_UNKNOWN",
                    "CONFLICT": "RECEIPT_INDEX_CONFLICT"}[x["status"]]
            failures.append((code, "%s: %s" % (x.get("repo_path", x["path"]), x["message"])))
    required = []
    for kind in args.require_kind or []:
        ok_ = [x for x in receipts if x.get("kind") == kind and x["status"] == "OK"]
        required.append({"kind": kind, "receipts_ok": [x.get("repo_path", x["path"]) for x in ok_]})
        if not ok_:
            failures.append(("REQUIRED_RECEIPT_MISSING", "no receipt of kind %r points at HEAD" % kind))
    packages = args.package or (["."] + (["assistant"] if os.path.isfile(os.path.join(repo, "assistant", "pyproject.toml")) else []))
    build_note = None
    if args.no_build:
        pkgs, bf = [], [("BUILD_SKIPPED", "package build skipped (--no-build); a release manifest needs the build")]
        build_note = "--no-build"
    else:
        pkgs, bf = build_packages(repo, st["head"], st["_ctime"], packages)
    failures += bf
    ctime = st.pop("_ctime")
    verdict = "PASS" if not failures else "FAIL"
    m = {"schema": SCHEMA, "verdict": verdict, "failures": [{"code": c, "message": msg} for c, msg in failures],
         "repository": st, "receipts": receipts, "receipt_index": index_meta, "required_kinds": required, "packages": pkgs,
         "conditions": conditions, "approval_record_problems": approval_problems,
         "execution": {"created_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "tool_sha256": sha256_file(os.path.abspath(__file__)), "python": sys.version.split()[0],
                       "platform": sys.platform, "packages_requested": packages,
                       "SOURCE_DATE_EPOCH": None if args.no_build else str(ctime)}}
    if build_note:
        m["build_note"] = build_note
    os.makedirs(out, exist_ok=True)
    stem = "RELEASE_MANIFEST" if verdict == "PASS" else "RELEASE_MANIFEST.FAILED"
    atomic_write_json(os.path.join(out, stem + ".json"), m)
    atomic_write_text(os.path.join(out, stem + ".md"), render_md(m))
    open_c = [c["id"] for c in conditions if c["status"] == "OPEN"]
    print("release manifest: %s (HEAD %s, branch %s, tree %s, %d receipt(s))" % (verdict, st["head"][:7], st["branch"],
          "clean" if st["clean"] else "DIRTY", len(receipts)))
    for c, msg in failures:
        print("  FAIL %s: %s" % (c, msg))
    print("  non-technical conditions OPEN: %s" % (", ".join(open_c) or "none"))
    print("  wrote %s" % os.path.join(out, stem + ".{json,md}"))
    if verdict != "PASS":
        return 1
    if args.require_approvals and open_c:
        return 3
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verify that qualification receipts point at HEAD and write a release manifest.")
    ap.add_argument("--repo", default=".", help="git repository (default: .)")
    ap.add_argument("--receipts", nargs="*", default=[], help="receipt files or directories (*.json, *.md, *.txt, *.log)")
    ap.add_argument("--index", help="JSON index transcribing the claimed commit of older prose receipts")
    ap.add_argument("--approval", action="append", help="approval record JSON (repeatable)")
    ap.add_argument("--package", action="append", help="package directory relative to the repository root (repeatable; default: . and assistant)")
    ap.add_argument("--require-kind", action="append", help="receipt kind that must be present and point at HEAD (repeatable; "
                    "the kind is the JSON 'receipt' field or the index 'kind')")
    ap.add_argument("--no-build", action="store_true", help="skip the package build (the verdict is then FAIL)")
    ap.add_argument("--require-approvals", action="store_true", help="exit 3 if a non-technical condition is OPEN")
    ap.add_argument("--out", required=True, help="output directory, outside the repository")
    args = ap.parse_args(argv)
    try:
        return run(args)
    except UsageError as ex:
        print("release manifest: input error: %s (nothing written)" % ex, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
