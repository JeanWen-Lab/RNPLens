"""Determinism contract v2 (records/replay/DETERMINISM_CONTRACT_v2.md): canonical projections of every output of a
managed project, former-location aliasing (a moved project keeps its keys), the projection index and the
location-independent follow-up evidence hash."""
import hashlib
import importlib.util
import json
import os
import shutil
import time

import pytest

from rnplens import canonical as CN
from rnplens import incremental as I
from rnplens import projection as PJ
from rnplens import provenance as pv
from rnplens import state as S

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


D1 = _load("determinism_v1_tests", os.path.join(HERE, "test_determinism.py"))
CHK = _load("check_pair_v2", os.path.join(REPO, "records", "replay", "v2", "check_pair_v2.py"))


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _mini_project(base):
    """A directory that counts as a managed project (has .rnplens/HEAD) without running the pipeline."""
    root = os.path.join(base, "project")
    os.makedirs(os.path.join(root, ".rnplens"))
    open(os.path.join(root, ".rnplens", "HEAD"), "w").write("{}")
    return root


# ---------------------------------------------------------------- unit: former locations
def test_paths_alias_a_former_location_and_its_parent(tmp_path):
    old = str(tmp_path / "first" / "case" / "project")
    new = str(tmp_path / "elsewhere" / "case_copy" / "project")
    P = CN.Paths(new, [str(tmp_path / "elsewhere" / "case_copy" / "in" / "run_A")], former=[old])
    assert P.canon_str(old + "/imports/v0002/main/x.pdb") == "./imports/v0002/main/x.pdb"
    assert P.canon_str(str(tmp_path / "first" / "case" / "in" / "run_A") + "/m.pdb") == "../in/run_A/m.pdb"
    assert P.canon_str(new + "/analyses") == "./analyses"
    assert P.canon_str("see %s and %s/in" % (old, os.path.dirname(old))) == "see . and ../in"
    # no former location: exactly the v1 forms
    Q, R = CN.Paths(new, [], former=[]), CN.Paths(new, [])
    s = "%s/a %s/b %s" % (new, os.path.dirname(new), old)
    assert Q.canon_str(s) == R.canon_str(s) and Q.alias == {}


def test_paths_current_location_wins_over_a_former_parent(tmp_path):
    old = str(tmp_path / "x" / "project")
    new = str(tmp_path / "x" / "sub" / "project")
    P = CN.Paths(new, [], former=[old])
    assert P.canon_str(new + "/imports") == "./imports"
    assert P.canon_str(old + "/imports") == "./imports"


def test_former_roots_come_from_state_sidecars(tmp_path):
    root = str(tmp_path / "p")
    d = os.path.join(root, ".rnplens", "run", ".rnplens", "state")
    os.makedirs(d)
    json.dump({"execution": {"project_root": "/somewhere/else/project"}}, open(os.path.join(d, "v0001.json"), "w"))
    json.dump({"execution": {"project_root": root}}, open(os.path.join(d, "v0002.json"), "w"))
    assert CN.former_roots(root) == ["/somewhere/else/project"]
    assert CN.former_roots(str(tmp_path / "not_a_project")) == []


# ---------------------------------------------------------------- unit: projections
def test_projection_removes_volatile_items_and_maps_hashes(tmp_path):
    root = _mini_project(str(tmp_path))
    a = os.path.join(root, "analyses", "v0002", "main", "a.json")
    pv.atomic_write_json(a, {"created_utc": "2026-10-17T00:00:00Z", "wall_s": 1.5, "argv": ["x"], "value": 0.25,
                             "detail": "opted in (2026-10-17T00:53:42+00:00, --yes)",
                             "path": root + "/imports/v0002/main/x.pdb", "consent": "consent-0001-deadbeef"})
    pa = a + ".canonical.json"
    assert os.path.exists(pa)
    pobj = json.load(open(pa))
    assert pobj == {"value": 0.25, "path": "./imports/v0002/main/x.pdb", "consent": "consent-0001",
                    "detail": "opted in (<time>, --yes)"}
    b = os.path.join(root, "analyses", "v0002", "main", "b.txt")
    pv.atomic_write_text(b, "made from %s at 2026-10-17T01:02:03Z; input %s\n" % (pv.sha256_file(a), "0" * 64))
    tb = open(b + ".canonical.txt").read()
    assert tb == "made from projection-sha256:%s at <time>; input %s\n" % (_sha(open(pa, "rb").read()), "0" * 64)
    ix = {e["raw_sha256"]: e["projection_sha256"] for e in json.load(open(os.path.join(root, PJ.INDEX_REL)))["entries"]}
    assert ix[pv.sha256_file(a)] == _sha(open(pa, "rb").read()) and ix[pv.sha256_file(b)]
    # rewriting a: a hash recorded for the earlier version still maps through the index
    old_raw, old_proj = pv.sha256_file(a), _sha(open(pa, "rb").read())
    pv.atomic_write_json(a, {"created_utc": "later", "value": 0.5})
    c = os.path.join(root, "analyses", "v0002", "main", "c.json")
    pv.atomic_write_json(c, {"recorded": old_raw})
    assert json.load(open(c + ".canonical.json")) == {"recorded": "projection-sha256:" + old_proj}
    assert PJ.errors(root) == []


def test_no_projection_outside_a_managed_project_or_for_canonical_and_sidecar_files(tmp_path):
    p = str(tmp_path / "free" / "x.json")
    pv.atomic_write_json(p, {"a": 1})
    assert not os.path.exists(p + ".canonical.json")
    root = _mini_project(str(tmp_path / "case"))
    for rel in (".rnplens/state/v0001.json", "analyses/v0002/index.json", "analyses/reports/r.json",
                "analyses/v0002/main/region_1-3/region_contacts.tsv", "analyses/v0002/main/x.pdb"):
        q = os.path.join(root, rel)
        pv.atomic_write_text(q, "{}\n")
        assert not any(os.path.exists(q + s) for s in PJ.PROJ_SUFFIXES), rel


def test_followup_evidence_content_hash_is_location_independent(tmp_path):
    out = []
    for name in ("first", "second_elsewhere"):
        root = _mini_project(str(tmp_path / name))
        fdir = os.path.join(root, "analyses", "v0002", "main", "followup", "fu_0001")
        st = [{"type": "OBSERVATION", "text": "contact {c}", "cites": ["x"],
               "slots": {"c": {"value": root + "/analyses/v0002/main/region_1-3/region.json#/contacts/0"}}}]
        log = [{"tool": "region", "call": {"rna": "1-3"}, "status": "OK", "outputs": [root + "/analyses/x.json"],
                "message": "wrote " + root + "/analyses/x.json", "started_utc": name, "wall_s": len(name)}]
        pv.atomic_write_json(os.path.join(fdir, "followup_answer.json"), {"statements": st})
        pv.atomic_write_json(os.path.join(fdir, "followup_record.json"),
                             {"tool_log": log, "evidence_sha256": _sha(name.encode()), "started_utc": name})
        out.append(json.load(open(os.path.join(fdir, "followup_record.json.canonical.json"))))
    assert out[0] == out[1]
    assert "evidence_sha256" not in out[0] and len(out[0]["evidence_content_sha256"]) == 64


# ---------------------------------------------------------------- integration: real pipeline, moved copy
@pytest.fixture(scope="module")
def cases(tmp_path_factory):
    base = tmp_path_factory.mktemp("det2")
    A = D1._case(str(base / "first_case"))
    moved = str(base / "moved_elsewhere" / "first_case_copy")
    shutil.copytree(os.path.dirname(A.root), moved, symlinks=True)
    time.sleep(1.2)
    B = D1._case(str(base / "second_copy_elsewhere"))
    Mp = S.Project(os.path.join(moved, "project"))
    na = _computed(Mp.root)
    cwd = os.getcwd()
    os.chdir(moved)
    try:
        assert I.run_pipeline(Mp, "update")[0] == 0
        assert I.run_pipeline(S.Project(A.root), "update")[0] == 0
        assert I.run_pipeline(S.Project(B.root), "update")[0] == 0
    finally:
        os.chdir(cwd)
    return A, B, Mp, na


def _computed(root):
    """analysis directories that were computed (not the per-version index folders)."""
    d = os.path.join(root, "analyses")
    return sorted(v for v in os.listdir(d) if os.path.isdir(os.path.join(d, v, "main")))


def _files(root):
    return {rel: p for rel, p in CHK.TR.walk(root).items()}


def test_every_output_has_its_projection_and_the_promised_set_is_byte_identical(cases):
    A, B, _, _ = cases
    fa, fb = _files(A.root), _files(B.root)
    assert CHK.missing_projections(fa) == [] and CHK.missing_projections(fb) == []
    pa, pb = CHK.promised(fa), CHK.promised(fb)
    assert set(pa) == set(pb) and any(f.endswith(".canonical.json") for f in pa)
    diff = [f for f in pa if open(pa[f], "rb").read() != open(pb[f], "rb").read()]
    assert diff == []
    for tail in ("/main/manifest.json.canonical.json", "/main/report_contract.json.canonical.json",
                 "/main/summary.json.canonical.json", "/main/report/rnplens_run.json.canonical.json", "/main.log.canonical.txt"):
        assert any(k.endswith(tail) for k in pa), tail
    assert PJ.errors(A.root) == [] and PJ.errors(B.root) == []


def test_a_moved_project_keeps_its_keys_and_reuses_its_work(cases):
    A, _, Mp, na = cases
    sa, sm = S.Project(A.root).head(), Mp.head()
    assert sm["analyses"]["main"]["reused"] is True
    assert sm["analyses"]["main"]["key"] == sa["analyses"]["main"]["key"]
    assert _computed(Mp.root) == na                                       # no analysis was redone
    assert CN.former_roots(Mp.root) == [A.root]
    fa, fm = _files(A.root), _files(Mp.root)
    pa, pm = CHK.promised(fa), CHK.promised(fm)
    assert set(pa) == set(pm)
    assert [f for f in pa if open(pa[f], "rb").read() != open(pm[f], "rb").read()] == []
