"""Determinism contract v1 (records/replay/DETERMINISM_CONTRACT_v1.md): canonical managed-project records.

(B) canonical files are byte-identical when the same inputs, answers and version are replayed in another absolute
directory at another time; (S) the qualified numbers are equal; volatile metadata lives in sidecars; hashes in canonical
files cover only canonical bytes; projects written before the change are still read, verified and updated."""
import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time

import pytest

from rnplens import canonical as CN
from rnplens import clarify as C
from rnplens import incremental as I
from rnplens import provenance as pv
from rnplens import state as S

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location("state_fixtures", os.path.join(HERE, "fixtures_v04", "state", "make.py"))
M = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(M)
PS, RS = M.sequences()
SPEC = json.load(open(os.path.join(REPO, "records", "replay", "retest", "canonical_artifacts_v1.json")))
ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
HEX = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")


def canonical_files(project):
    out = {}
    for dp, dn, fn in os.walk(project):
        for f in fn:
            rel = os.path.relpath(os.path.join(dp, f), project).replace(os.sep, "/")
            segs = rel.split("/")
            for pat in SPEC["patterns_relative_to_project_dir"]:
                ps = pat.split("/")
                if len(ps) == len(segs) and all(fnmatch.fnmatchcase(s, q) for s, q in zip(segs, ps)):
                    out[rel] = open(os.path.join(dp, f), "rb").read()
    return out


def _numbers(P, d=None):
    """The qualified numbers of an analysis directory, location-free: summary.json's canonical view without its
    inventory (structure paths) and Report's contacts_by_output.json."""
    d = d or os.path.join(P.root, P.head()["analyses"]["main"]["dir"])
    sm = json.load(open(os.path.join(d, "summary.json")))
    sm.pop("inventory", None)
    return CN.content_view(sm, CN.Paths(P.root)), json.load(open(os.path.join(d, "report", "contacts_by_output.json")))


# ---------------------------------------------------------------- unit: path forms, volatile split, sidecar
def test_paths_canonical_forms_and_round_trip(tmp_path):
    root = str(tmp_path / "case" / "project")
    ra = str(tmp_path / "case" / "in" / "run_A")
    P = CN.Paths(root, [ra])
    obj = {ra + "/m.pdb": {"used_path": root + "/imports/v0002/main/x.pdb", "root": root},
           "run:" + ra: "h", "chain_mapping:%s|protein=A;rna=B|0123456789" % ra: 1,
           "text": "the run at %s differs; see %s/imports" % (ra, root),
           "other": str(tmp_path / "case" / "in" / "run_AB" / "f"),     # not under run_A: component boundary
           "relative_already": "imports/v0002/main", "n": 3}
    c = P.canon(obj)
    assert set(c) == {"../in/run_A/m.pdb", "run:../in/run_A", "chain_mapping:../in/run_A|protein=A;rna=B|0123456789",
                      "text", "other", "relative_already", "n"}
    assert c["../in/run_A/m.pdb"] == {"used_path": "./imports/v0002/main/x.pdb", "root": "."}
    assert c["text"] == "the run at ../in/run_A differs; see ./imports"
    assert c["other"] == "../in/run_AB/f"                      # via the common parent folder, still relative
    assert c["relative_already"] == "imports/v0002/main"
    back = P.decanon(c)
    assert {k: v for k, v in back.items() if k != "text"} == {k: v for k, v in obj.items() if k != "text"}


def test_split_and_merge_volatile_by_pointer():
    o = {"created_utc": "t0", "a": [{"recorded_utc": "t1", "x": 1}], "k/ey": {"wall_s": 0.1, "code_commit": "c"}}
    can, vol = CN.split_volatile(o)
    assert can == {"a": [{"x": 1}], "k/ey": {}}
    assert vol == {"/created_utc": "t0", "/a/0/recorded_utc": "t1", "/k~1ey/wall_s": 0.1, "/k~1ey/code_commit": "c"}
    assert CN.merge_volatile(json.loads(json.dumps(can)), vol) == o


def test_write_read_sidecar_and_missing_sidecar(tmp_path):
    root = str(tmp_path)
    sha = CN.write(root, "x/a.json", {"created_utc": "2026-10-16T00:00:00+00:00", "p": root + "/f", "v": 1.5})
    text = open(os.path.join(root, "x/a.json")).read()
    assert text == CN.dumps({"p": "./f", "v": 1.5}) and hashlib.sha256(text.encode()).hexdigest() == sha
    sc = json.load(open(os.path.join(root, ".rnplens", "run", "x", "a.json")))
    assert sc["canonical_sha256"] == sha and sc["volatile"] == {"/created_utc": "2026-10-16T00:00:00+00:00"}
    assert CN.read(root, "x/a.json") == {"created_utc": "2026-10-16T00:00:00+00:00", "p": os.path.join(root, "f"), "v": 1.5}
    os.remove(os.path.join(root, ".rnplens", "run", "x", "a.json"))
    assert CN.read(root, "x/a.json") == {"p": os.path.join(root, "f"), "v": 1.5}


def test_content_hash_ignores_creation_time_and_location(tmp_path):
    a, b = tmp_path / "a" / "project", tmp_path / "b" / "project"
    for d, t in ((a, "2026-01-01T00:00:00+00:00"), (b, "2026-02-02T00:00:00+00:00")):
        d.mkdir(parents=True)
        json.dump({"created_utc": t, "inventory": {"structures": [{"path": str(d / "imports" / "x.pdb")}]}, "n": 2},
                  open(d / "summary.json", "w"))
    ha = CN.content_sha256(str(a / "summary.json"), CN.Paths(str(a)))
    hb = CN.content_sha256(str(b / "summary.json"), CN.Paths(str(b)))
    assert ha == hb and pv.sha256_file(str(a / "summary.json")) != pv.sha256_file(str(b / "summary.json"))


def test_run_hash_is_location_independent_and_legacy_answers_still_match(tmp_path):
    fa = {"/x/a/run_A/m.pdb": "1" * 64, "/x/a/run_A/c.json": "2" * 64}
    fb = {"/y/b/run_A/m.pdb": "1" * 64, "/y/b/run_A/c.json": "2" * 64}
    assert C.run_hash("/x/a/run_A", fa) == C.run_hash("/y/b/run_A", fb)
    legacy = C.legacy_run_hash("/x/a/run_A", fa)
    ctx = {"files": fa, "constructs": {}}
    assert C.changed_dependencies({"depends_on": {"run:/x/a/run_A": legacy}}, ctx) == []
    assert C.changed_dependencies({"depends_on": {"run:/x/a/run_A": "0" * 64}}, ctx)


# ---------------------------------------------------------------- the managed-project lifecycle, twice
def _case(base, run_rc=True):
    """CASE/in/{run_A,run_B,run_C (other construct),run_D (two protein chains)} and CASE/project, then the lifecycle:
    init (questions) -> answers -> resume -> no-change update -> remove run_C. Real rnplens analyse."""
    os.makedirs(base)
    ins = M.two_runs(os.path.join(base, "in"))
    ins = [shutil.move(ins[0], os.path.join(base, "in", "run_A")), shutil.move(ins[1], os.path.join(base, "in", "run_B"))]
    rc = os.path.join(base, "in", "run_C"); M.copy_run("exec_B", rc); M.truncate_rna(os.path.join(rc, M.MODEL), 2)
    rd = os.path.join(base, "in", "run_D"); M.copy_run("exec_A", rd); M.duplicate_protein_chain(os.path.join(rd, M.MODEL))
    cwd = os.getcwd()
    os.chdir(base)
    try:
        proj = os.path.join(base, "project")
        code, _ = I.init_project(proj, ins + [rc, rd], PS, RS, "BOLTZ2", "7K9D_det")
        assert code == I.EXIT_NEEDS_ANSWER
        P = S.Project(proj)
        for _ in range(4):
            pend = P.head()["pending"]
            if not pend:
                break
            r = pend[0]
            opt = "exclude_run" if r["type"] == "construct_mismatch" else \
                next(o["id"] for o in r["options"] if o["id"].startswith("protein=A"))
            C.answer(P, r["id"], opt, text="fixed answer for the determinism test")
            code, _ = I.run_pipeline(P, "resume")
        assert code == 0 and P.head()["status"] == "COMPLETE"
        assert I.run_pipeline(P, "update")[0] == 0
        d = json.loads(json.dumps(P.head()["declared"]))
        d["inputs"] = [x for x in d["inputs"] if not x.endswith("run_C")]
        assert I.run_pipeline(P, "update", declared=d)[0] == 0
        first = next(v["version"] for v in P.versions() if v["status"] == "COMPLETE")
        r = subprocess.run([sys.executable, "-m", "rnplens", "update", proj, "--report", first, P.head_id()],
                           capture_output=True, text=True, env=dict(os.environ, MPLBACKEND="Agg"))
        assert r.returncode == 0, r.stderr
    finally:
        os.chdir(cwd)
    return P


@pytest.fixture(scope="module")
def two_cases(tmp_path_factory):
    base = tmp_path_factory.mktemp("det")
    A = _case(str(base / "first_case"))
    time.sleep(1.2)                                     # another second: every time stamp differs
    B = _case(str(base / "second_copy_elsewhere"))
    return A, B


def test_canonical_files_are_byte_identical_after_relocation_and_later_replay(two_cases):
    A, B = two_cases
    fa, fb = canonical_files(A.root), canonical_files(B.root)
    assert set(fa) == set(fb)
    kinds = {re.sub(r"v\d{4}|[0-9a-f]{64}(\.\d+)?", "*", f) for f in fa}
    for need in (".rnplens/HEAD", ".rnplens/state/*.json", ".rnplens/cache/*.json", "analyses/*/index.json",
                 "analyses/*/update_report.json", "analyses/*/update_report.html", "analyses/reports/update_*.json",
                 "analyses/*/main/report/contacts_by_output.json", "imports/*/main/construct_rna.fasta"):
        assert any(fnmatch.fnmatchcase(k, need) for k in kinds), need
    diff = [f for f in fa if fa[f] != fb[f]]
    assert diff == []
    sa, sb = A.head(), B.head()
    assert sa["analyses"]["main"]["key"] == sb["analyses"]["main"]["key"]
    assert sa["created_utc"] != sb["created_utc"]                      # the runs really were at different times
    assert _numbers(A) == _numbers(B)                                                # (S) numbers equal
    assert sa["analyses"]["main"]["summary_content_sha256"] == sb["analyses"]["main"]["summary_content_sha256"]


def test_canonical_files_hold_no_absolute_path_time_stamp_or_raw_hash_of_a_non_canonical_file(two_cases):
    A, _ = two_cases
    fa = canonical_files(A.root)
    noncanonical, inputs = set(), set()
    for dp, dn, fn in os.walk(os.path.join(os.path.dirname(A.root), "in")):
        inputs |= {pv.sha256_file(os.path.join(dp, f)) for f in fn}
    for dp, dn, fn in os.walk(A.root):
        if os.sep + os.path.join(".rnplens", "run") in dp + os.sep:
            continue
        for f in fn:
            rel = os.path.relpath(os.path.join(dp, f), A.root).replace(os.sep, "/")
            if rel not in fa:
                noncanonical.add(pv.sha256_file(os.path.join(dp, f)))
    case_root = os.path.dirname(A.root)
    for rel, b in fa.items():
        t = b.decode("utf-8")
        assert case_root not in t, rel
        assert not ISO.search(t), rel
        assert not (set(HEX.findall(t)) & (noncanonical - inputs)), rel     # rule 4: (a) input bytes are allowed


def test_volatile_metadata_is_in_sidecars_and_merged_back(two_cases):
    A, _ = two_cases
    st = A.head()
    assert st["created_utc"] and "code_commit" in st
    raw = json.load(open(os.path.join(A.root, ".rnplens", "state", A.head_id() + ".json")))
    assert raw["schema"] == "rnplens-project-state-2" and "created_utc" not in raw
    assert "summary_sha256" not in raw["analyses"]["main"] and raw["analyses"]["main"]["summary_content_sha256"]
    assert st["analyses"]["main"]["summary_sha256"] == pv.sha256_file(
        os.path.join(A.root, st["analyses"]["main"]["dir"], "summary.json"))
    sc = json.load(open(os.path.join(A.root, ".rnplens", "run", ".rnplens", "state", A.head_id() + ".json")))
    assert sc["volatile"]["/created_utc"] == st["created_utc"] and sc["execution"]["project_root"] == A.root
    rec = next(iter(st["decisions"].values()))
    assert rec["recorded_utc"] and os.path.isabs(rec["apply"].get("exclude_run") or A.root)
    assert A.verify() == []


def test_losing_the_sidecars_changes_no_result(two_cases, tmp_path):
    A, _ = two_cases
    case = os.path.dirname(A.root)
    cp = str(tmp_path / "copy")
    shutil.copytree(case, cp, symlinks=True)
    proj = os.path.join(cp, "project")
    for dp, dn, fn in os.walk(proj):
        for f in fn:
            os.chmod(os.path.join(dp, f), 0o644)
    shutil.rmtree(os.path.join(proj, ".rnplens", "run"))
    P = S.Project(proj)
    st = P.head()
    assert P.verify() == [] and st.get("created_utc") is None and st["status"] == "COMPLETE"
    view = _numbers(P)[1]
    code, _ = I.run_pipeline(P, "after sidecar loss")
    assert code == 0 and P.head()["status"] == "COMPLETE" and _numbers(P)[1] == view


# ---------------------------------------------------------------- backward compatibility (written before the change)
LEGACY = "cf81acd"
LEGACY_FILES = ("state.py", "incremental.py", "clarify.py", "provenance.py")


def _legacy_tree(dst):
    """src/ of this checkout with the four writer modules as they were at cf81acd (before the canonical records)."""
    try:
        subprocess.run(["git", "-C", REPO, "cat-file", "-e", LEGACY + "^{commit}"], check=True, capture_output=True)
    except Exception:
        pytest.skip("git history with %s not available" % LEGACY)
    shutil.copytree(os.path.join(REPO, "src"), dst, ignore=shutil.ignore_patterns("__pycache__"))
    for f in LEGACY_FILES:
        b = subprocess.run(["git", "-C", REPO, "show", "%s:src/rnplens/%s" % (LEGACY, f)], check=True,
                           capture_output=True).stdout
        open(os.path.join(dst, "rnplens", f), "wb").write(b)
    os.remove(os.path.join(dst, "rnplens", "canonical.py"))
    return dst


def test_project_written_before_the_change_is_read_verified_and_updated(tmp_path):
    legacy = _legacy_tree(str(tmp_path / "legacy_src"))
    base = str(tmp_path / "old")
    ins = M.two_runs(os.path.join(base, "in"))
    rc = os.path.join(base, "in", "exec_C"); M.copy_run("exec_B", rc); M.truncate_rna(os.path.join(rc, M.MODEL), 2)
    proj = os.path.join(base, "project")
    env = dict(os.environ, PYTHONPATH=legacy, MPLBACKEND="Agg")
    run = lambda *a: subprocess.run([sys.executable, "-m", "rnplens", *a], capture_output=True, text=True, env=env, cwd=base)
    pf, rf = os.path.join(base, "p.fasta"), os.path.join(base, "r.fasta")
    open(pf, "w").write(">p\n%s\n" % PS); open(rf, "w").write(">r\n%s\n" % RS)
    r = run("update", proj, "--init", *ins, rc, "--protein-seq", pf, "--rna-seq", rf, "--engine", "BOLTZ2", "--case-id", "old")
    assert r.returncode == 3, r.stderr
    r = run("clarify", proj, "--answer", "1", "exclude_run", "--text", "old answer")
    assert r.returncode == 0, r.stderr + r.stdout
    P = S.Project(proj)                                   # new code
    old_ids = [v["version"] for v in P.versions()]
    for v in old_ids:
        old = json.load(open(os.path.join(proj, ".rnplens", "state", v + ".json")))
        assert old["schema"] == "rnplens-project-state-1" and "created_utc" in old    # truly the old format
    assert P.verify() == [] and len(old_ids) >= 3
    st = P.head()
    assert st["status"] == "COMPLETE"
    (did,) = [k for k, v in st["decisions"].items() if v["status"] == "ACTIVE"]
    assert st["decisions"][did]["recorded_utc"]
    view = _numbers(P)[1]
    code, vid = I.run_pipeline(P, "first update with the new code")
    st2 = P.head()
    assert code == 0 and vid == "v%04d" % (len(old_ids) + 1) and P.verify() == []
    assert st2["decisions"][did]["status"] == "ACTIVE" and not st2["invalidated_in_this_version"]   # answer still applies
    assert json.load(open(os.path.join(proj, ".rnplens", "state", vid + ".json")))["schema"] == "rnplens-project-state-2"
    assert _numbers(P)[1] == view
    assert I.run_pipeline(P, "again")[0] == 0 and P.head()["analyses"]["main"]["reused"]


def test_reproducibility_doc_states_the_limits():
    t = open(os.path.join(REPO, "docs", "reproducibility.md")).read()
    for s in ("canonical", "sidecar", "not canonical", "DETERMINISM_CONTRACT_v1", "FAILED"):
        assert s in t, s
