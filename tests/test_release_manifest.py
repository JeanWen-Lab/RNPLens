"""tools/release_manifest.py on synthetic git repositories (no network; packages built from HEAD in a temp dir)."""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "release_manifest.py")
if not os.path.isfile(TOOL):
    pytest.skip("tools/ not present (installed without the source tree)", allow_module_level=True)
_spec = importlib.util.spec_from_file_location("release_manifest", TOOL)
RM = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RM)

GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@localhost", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@localhost", GIT_CONFIG_NOSYSTEM="1", HOME=os.environ.get("HOME", "/tmp"))


def g(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"] + list(args),
                       capture_output=True, text=True, env=GIT_ENV)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def can_build():
    """The tool builds in-process with the interpreter's own setuptools; a wheel needs bdist_wheel, which setuptools
    provides from 70.1 and older setuptools only together with the separate `wheel` package."""
    try:
        import setuptools.build_meta  # noqa: F401
    except Exception:
        return False
    try:
        from setuptools.command.bdist_wheel import bdist_wheel  # noqa: F401  (setuptools >= 70.1)
        return True
    except Exception:
        pass
    try:
        import wheel.bdist_wheel  # noqa: F401
        return True
    except Exception:
        return False


needs_build = pytest.mark.skipif(not can_build(), reason="setuptools with bdist_wheel unavailable (install the test extra)")


@pytest.fixture
def repo(tmp_path):
    """A tiny package repository with two commits; the second is documentation-only."""
    r = tmp_path / "repo"
    (r / "src" / "toypkg").mkdir(parents=True)
    (r / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools>=61"]\nbuild-backend = "setuptools.build_meta"\n\n'
                                      '[project]\nname = "toypkg"\nversion = "0.0.1"\n\n'
                                      '[tool.setuptools.packages.find]\nwhere = ["src"]\n')
    (r / "src" / "toypkg" / "__init__.py").write_text('VALUE = 1\n')
    (r / "README.md").write_text("toy\n")
    (r / ".gitignore").write_text("__pycache__/\n*.egg-info/\nbuild/\n")
    g(tmp_path, "init", "-q", str(r))
    g(r, "checkout", "-q", "-b", "dev")
    g(r, "add", "-A"); g(r, "commit", "-q", "-m", "first")
    first = g(r, "rev-parse", "HEAD")
    (r / "README.md").write_text("toy, documented\n")
    g(r, "add", "-A"); g(r, "commit", "-q", "-m", "documentation only")
    return {"root": r, "first": first, "head": g(r, "rev-parse", "HEAD"), "tmp": tmp_path}


def receipt(tmp, name, obj=None, text=None):
    p = tmp / "receipts" / name
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(obj) if obj is not None else text)
    return str(p)


def run(repo, *extra, out=None):
    out = out or str(repo["tmp"] / ("out_%d" % len(os.listdir(repo["tmp"]))))
    code = RM.main(["--repo", str(repo["root"]), "--out", out] + list(extra))
    files = sorted(os.listdir(out)) if os.path.isdir(out) else []
    m = None
    for n in ("RELEASE_MANIFEST.json", "RELEASE_MANIFEST.FAILED.json"):
        if n in files:
            m = json.load(open(os.path.join(out, n)))
    return code, m, files, out


# ---------------------------------------------------------------- pass, with the real build
@needs_build
def test_pass_records_head_receipts_packages_and_open_conditions(repo):
    rc = receipt(repo["tmp"], "tests.json", {"receipt": "test_run", "receipt_commit": repo["head"], "result": {"passed": 3}})
    code, m, files, out = run(repo, "--receipts", rc, "--require-kind", "test_run")
    assert code == 0 and files == ["RELEASE_MANIFEST.json", "RELEASE_MANIFEST.md"]
    assert m["verdict"] == "PASS" and m["failures"] == []
    r = m["repository"]
    assert r["head"] == repo["head"] and r["branch"] == "dev" and r["clean"] is True
    assert m["receipts"][0]["sha256"] == hashlib.sha256(open(rc, "rb").read()).hexdigest()
    assert m["receipts"][0]["status"] == "OK" and m["receipts"][0]["claim_source"] == "json:receipt_commit"
    kinds = {a["kind"]: a for a in m["packages"][0]["archives"]}
    assert set(kinds) == {"wheel", "sdist"}
    init_sha = hashlib.sha256(b"VALUE = 1\n").hexdigest()
    assert any(x["name"] == "toypkg/__init__.py" and x["sha256"] == init_sha for x in kinds["wheel"]["members"])
    assert kinds["wheel"]["record_check"]["wheel_record_consistent"] is True
    hc = kinds["sdist"]["head_comparison"]
    assert hc["members_differing_from_head"] == [] and hc["members_identical_to_head"] >= 3
    assert all(len(a["sha256"]) == 64 for a in kinds.values())
    assert [c["status"] for c in m["conditions"]] == ["OPEN", "OPEN"]
    assert [c["id"] for c in m["conditions"]] == ["licence", "distribution"]
    md = open(os.path.join(out, "RELEASE_MANIFEST.md")).read()
    assert repo["head"] in md and "OPEN" in md and init_sha in md
    assert g(repo["root"], "status", "--porcelain", "--untracked-files=all") == ""      # the tool wrote nothing into the repo


@needs_build
def test_build_is_deterministic_in_members_and_wheel(repo):
    rc = receipt(repo["tmp"], "t.json", {"commit": repo["head"]})
    _, a, _, _ = run(repo, "--receipts", rc)
    _, b, _, _ = run(repo, "--receipts", rc)
    for x, y in zip(a["packages"][0]["archives"], b["packages"][0]["archives"]):
        assert x["members"] == y["members"] and x["members_digest"] == y["members_digest"]
        if x["kind"] == "wheel":
            assert x["sha256"] == y["sha256"]


@needs_build
def test_build_failure_is_a_failure(repo):
    (repo["root"] / "pyproject.toml").write_text('[build-system]\nbuild-backend = "no_such_backend_xyz"\n')
    g(repo["root"], "commit", "-q", "-am", "break the build")
    rc = receipt(repo["tmp"], "t.json", {"commit": g(repo["root"], "rev-parse", "HEAD")})
    code, m, files, _ = run(repo, "--receipts", rc)
    assert code == 1 and "RELEASE_MANIFEST.FAILED.json" in files
    assert [f["code"] for f in m["failures"]] == ["BUILD_FAILED"]


# ---------------------------------------------------------------- failures (no build needed)
def test_receipt_at_an_earlier_commit_fails_and_shows_what_changed(repo):
    rc = receipt(repo["tmp"], "t.json", {"commit": repo["first"][:7]})
    code, m, files, _ = run(repo, "--receipts", rc, "--no-build")
    assert code == 1 and files == ["RELEASE_MANIFEST.FAILED.json", "RELEASE_MANIFEST.FAILED.md"]
    x = m["receipts"][0]
    assert x["status"] == "MISMATCH" and x["claimed_commit_resolved"] == repo["first"]
    assert x["commits_between"] == 1 and x["files_changed_since_claim"]["first_50"] == ["README.md"]
    codes = [f["code"] for f in m["failures"]]
    assert "RECEIPT_COMMIT_MISMATCH" in codes and "BUILD_SKIPPED" in codes


def test_dirty_tree_fails_tracked_and_untracked(repo):
    rc = receipt(repo["tmp"], "t.json", {"commit": repo["head"]})
    (repo["root"] / "README.md").write_text("edited\n")
    code, m, _, _ = run(repo, "--receipts", rc, "--no-build")
    assert code == 1 and m["repository"]["clean"] is False and m["failures"][0]["code"] == "DIRTY_TREE"
    g(repo["root"], "checkout", "README.md")
    (repo["root"] / "new_file.txt").write_text("x\n")
    code, m, _, _ = run(repo, "--receipts", rc, "--no-build")
    assert code == 1 and m["failures"][0]["code"] == "DIRTY_TREE" and "new_file.txt" in m["failures"][0]["message"]


def test_receipt_without_commit_fails(repo):
    a = receipt(repo["tmp"], "a.json", {"result": "pass"})
    b = receipt(repo["tmp"], "b.md", text="# Report\nAll tests passed on Linux.\n")
    code, m, _, _ = run(repo, "--receipts", a, b, "--no-build")
    assert code == 1
    assert [x["status"] for x in m["receipts"]] == ["NO_COMMIT", "NO_COMMIT"]
    assert sum(f["code"] == "RECEIPT_WITHOUT_COMMIT" for f in m["failures"]) == 2


def test_accepted_text_forms_and_ambiguity(repo):
    h = repo["head"]
    ok_md = receipt(repo["tmp"], "ok.md", text="# Viewer check\n\n**Receipt-Commit:** `%s`\n\nprose mentioning %s\n" % (h[:7], repo["first"][:7]))
    ok_txt = receipt(repo["tmp"], "commit.txt", text=h + "\n")
    amb = receipt(repo["tmp"], "amb.md", text="Tested commit: %s\nTested commit: %s\n" % (h, repo["first"]))
    code, m, _, _ = run(repo, "--receipts", ok_md, ok_txt, amb, "--no-build")
    st = {os.path.basename(x["path"]): x["status"] for x in m["receipts"]}
    assert st == {"ok.md": "OK", "commit.txt": "OK", "amb.md": "AMBIGUOUS"}
    assert any(f["code"] == "RECEIPT_AMBIGUOUS_COMMIT" for f in m["failures"]) and code == 1


def test_directory_of_receipts_and_unknown_commit(repo):
    receipt(repo["tmp"], "x.json", {"commit": repo["head"]})
    receipt(repo["tmp"], "y.json", {"provenance": {"code_commit": "0123456789abcdef0123456789abcdef01234567"}})
    code, m, _, _ = run(repo, "--receipts", str(repo["tmp"] / "receipts"), "--no-build")
    st = {os.path.basename(x["path"]): x["status"] for x in m["receipts"]}
    assert st == {"x.json": "OK", "y.json": "UNRESOLVED"}
    assert any(f["code"] == "RECEIPT_COMMIT_UNKNOWN" for f in m["failures"]) and code == 1


def test_index_transcribes_prose_receipts_and_detects_conflict(repo):
    prose = repo["root"] / "REPORT.md"
    prose.write_text("A report that mentions several commits in prose.\n")
    g(repo["root"], "add", "REPORT.md"); g(repo["root"], "commit", "-q", "-m", "report")
    head = g(repo["root"], "rev-parse", "HEAD")
    idx = repo["tmp"] / "index.json"
    idx.write_text(json.dumps({"receipts": [{"path": "REPORT.md", "claimed_commit": head[:9], "kind": "replay_retest",
                                             "claim_source": "section 2"}]}))
    code, m, _, _ = run(repo, "--index", str(idx), "--require-kind", "replay_retest", "--no-build")
    x = m["receipts"][0]
    assert x["status"] == "OK" and x["repo_path"] == "REPORT.md" and x["tracked_at_head"] is True
    assert x["claim_source"] == "index (section 2)" and m["receipt_index"]["sha256"]
    assert [f["code"] for f in m["failures"]] == ["BUILD_SKIPPED"] and code == 1
    conflict = receipt(repo["tmp"], "c.md", text="Receipt-Commit: %s\n" % head)
    idx.write_text(json.dumps({"receipts": [{"path": conflict, "claimed_commit": repo["first"]}]}))
    code, m, _, _ = run(repo, "--index", str(idx), "--no-build")
    assert m["receipts"][0]["status"] == "CONFLICT" and code == 1


def test_no_receipts_and_missing_required_kind(repo):
    code, m, _, _ = run(repo, "--no-build", "--require-kind", "viewer_verification")
    codes = [f["code"] for f in m["failures"]]
    assert code == 1 and "NO_RECEIPTS" in codes and "REQUIRED_RECEIPT_MISSING" in codes


def test_approval_records(repo, tmp_path):
    good = tmp_path / "dist.json"
    good.write_text(json.dumps({"condition": "distribution", "status": "APPROVED", "approved_by": "office",
                                "date": "2026-11-01", "reference": "ref-1"}))
    bad = tmp_path / "lic.json"
    bad.write_text(json.dumps({"condition": "licence", "status": "PENDING"}))
    rc = receipt(repo["tmp"], "t.json", {"commit": repo["head"]})
    code, m, _, _ = run(repo, "--receipts", rc, "--no-build", "--approval", str(good), "--approval", str(bad))
    st = {c["id"]: c["status"] for c in m["conditions"]}
    assert st == {"licence": "OPEN", "distribution": "APPROVAL RECORD SUPPLIED"}
    cond = {c["id"]: c for c in m["conditions"]}
    assert cond["distribution"]["records"][0]["sha256"] == hashlib.sha256(good.read_bytes()).hexdigest()
    assert m["approval_record_problems"][0]["problems"]


@needs_build
def test_require_approvals_exit_code(repo, tmp_path):
    rc = receipt(repo["tmp"], "t.json", {"commit": repo["head"]})
    code, m, _, _ = run(repo, "--receipts", rc, "--require-approvals")
    assert code == 3 and m["verdict"] == "PASS"
    recs = []
    for cid in ("licence", "distribution"):
        p = tmp_path / ("%s.json" % cid)
        p.write_text(json.dumps({"condition": cid, "status": "APPROVED", "approved_by": "x", "date": "d", "reference": "r"}))
        recs += ["--approval", str(p)]
    code, m, _, _ = run(repo, "--receipts", rc, "--require-approvals", *recs)
    assert code == 0 and all(c["status"] != "OPEN" for c in m["conditions"])


def test_usage_errors_write_nothing(repo, capsys):
    rc = receipt(repo["tmp"], "t.json", {"commit": repo["head"]})
    inside = str(repo["root"] / "manifest_out")
    assert RM.main(["--repo", str(repo["root"]), "--receipts", rc, "--out", inside, "--no-build"]) == 2
    assert not os.path.exists(inside)
    out = repo["tmp"] / "existing"
    out.mkdir()
    (out / "RELEASE_MANIFEST.FAILED.json").write_text("{}")
    assert RM.main(["--repo", str(repo["root"]), "--receipts", rc, "--out", str(out), "--no-build"]) == 2
    assert (out / "RELEASE_MANIFEST.FAILED.json").read_text() == "{}"                  # never overwritten
    assert RM.main(["--repo", str(repo["root"]), "--receipts", str(repo["tmp"] / "absent.json"), "--out", str(repo["tmp"] / "o9")]) == 2
    assert "nothing written" in capsys.readouterr().err


def test_command_line_entry_point(repo):
    rc = receipt(repo["tmp"], "t.json", {"commit": repo["first"]})
    out = str(repo["tmp"] / "cli_out")
    r = subprocess.run([sys.executable, TOOL, "--repo", str(repo["root"]), "--receipts", rc, "--no-build", "--out", out],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "FAIL RECEIPT_COMMIT_MISMATCH" in r.stdout and "OPEN: licence, distribution" in r.stdout


def test_manifest_markdown_passes_the_wording_audit(repo):
    trace = pytest.importorskip("rnplens.trace")
    rc = receipt(repo["tmp"], "t.json", {"commit": repo["first"]})
    _, _, _, out = run(repo, "--receipts", rc, "--no-build")
    assert trace.wording_audit(open(os.path.join(out, "RELEASE_MANIFEST.FAILED.md")).read()) == []
