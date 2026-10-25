"""Portability of managed projects (records/replay/PORTABILITY_TEST_v1.md): hash-verified resolution of recorded
structure files, explicit relinking, clear refusal, the NOT SELF-CONTAINED notice, and the location-independent
follow-up evidence hash (definition 2) with replay under the recorded definition."""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

import pytest

from rnplens import portability as PT
from rnplens import provenance as pv
from rnplens import state as S
from rnplens_assistant import followup as F

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("determinism_v1_tests_p", os.path.join(HERE, "test_determinism.py"))
D1 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(D1)


def rn(*a, cwd=None):
    return subprocess.run([sys.executable, "-m", "rnplens", *a], capture_output=True, text=True, cwd=cwd,
                          env=dict(os.environ, MPLBACKEND="Agg"))


def ra(*a, cwd=None):
    return subprocess.run([sys.executable, "-m", "rnplens_assistant", *a], capture_output=True, text=True, cwd=cwd,
                          env=dict(os.environ, MPLBACKEND="Agg"))


def heads(case):
    st = S.Project(os.path.join(case, "project")).head()
    return (os.path.join(case, "project", st["groups"]["main"]["import_dir"]),
            os.path.join(case, "project", st["analyses"]["main"]["dir"]))


def snap(d):
    return {os.path.relpath(os.path.join(dp, f), d): pv.sha256_file(os.path.join(dp, f))
            for dp, dn, fn in os.walk(d) for f in fn}


@pytest.fixture(scope="module")
def cases(tmp_path_factory):
    base = str(tmp_path_factory.mktemp("port"))
    D1._case(os.path.join(base, "orig"))
    orig = os.path.join(base, "orig")
    imp, an = heads(orig)
    r = rn("region", imp, an, "--rna", "1-3"); assert r.returncode == 0, r.stderr
    r = rn("assist", "--project", imp, "--analysis", an, "--item", "C", "--rna", "1-3", "--runs", "run_A,run_B",
           "--followup", "local", "--question", "Which contacts in RNA 1-3 are found in only one run?", cwd=orig)
    assert r.returncode == 0, r.stderr + r.stdout
    case_copy = os.path.join(base, "copies", "case_copy")
    shutil.copytree(orig, case_copy, symlinks=True)
    po = {}
    for n in ("p2", "p3"):
        po[n] = os.path.join(base, "copies", n)
        os.makedirs(po[n])
        shutil.copytree(os.path.join(orig, "project"), os.path.join(po[n], "project"), symlinks=True)
    return {"base": base, "orig": orig, "case": case_copy, "rel": [os.path.relpath(x, orig) for x in (imp, an)], **po}


def rel_dirs(c, case):
    return [os.path.join(case, x) for x in c["rel"]]


def test_in_place_project_is_local_and_silent(cases):
    imp, an = heads(cases["orig"])
    r = rn("region", imp, an, "--rna", "1-3")
    assert r.returncode == 0 and "PORTABILITY" not in r.stderr and "NOT SELF-CONTAINED" not in r.stderr
    man = json.load(open(os.path.join(imp, "manifest.json")))
    rep = PT.check_manifest(imp, man, "read", "test")[1]
    assert rep["self_contained"] and {x["status"] for x in rep["rows"] if x["required"]} == {"LOCAL"}


def test_followup_records_definition_2_and_replays(cases):
    imp, an = heads(cases["orig"])
    fdir = os.path.join(an, "followup", "fu_0001")
    rec, plan = (json.load(open(os.path.join(fdir, f))) for f in ("followup_record.json", "followup_plan.json"))
    assert rec["evidence_hash_version"] == plan["evidence_hash_version"] == F.EVIDENCE_HASH_V2
    r = ra("replay-followup", os.path.join(fdir, "followup_plan.json"), "--project", imp, "--analysis", an)
    assert r.returncode == 0 and json.loads(r.stdout.strip().splitlines()[-1])["matches"] is True


def test_project_only_copy_with_original_present_is_not_self_contained(cases):
    imp, an = rel_dirs(cases, cases["p3"])
    r = rn("region", imp, an, "--rna", "1-3")
    assert r.returncode == 0 and "NOT SELF-CONTAINED" in r.stderr and cases["orig"] in r.stderr
    P = S.Project(os.path.join(cases["p3"], "project"))
    before = open(P.head_path, "rb").read()
    r = rn("update", P.root)
    assert r.returncode == 6 and "PORTABILITY REFUSED" in r.stderr and "rnplens relink" in r.stderr
    assert "exists at the former location" in r.stderr
    assert open(P.head_path, "rb").read() == before and not os.path.exists(os.path.join(P.dir, "LOCK"))


def test_changed_original_is_refused_and_nothing_is_written(cases):
    imp, an = rel_dirs(cases, cases["p3"])
    man = json.load(open(os.path.join(imp, "manifest.json")))
    target = next(s["path"] for s in man["structures"] if s["verdict"] == "INCLUDED")
    keep = open(target, "rb").read()
    try:
        open(target, "ab").write(b"REMARK changed\n")
        before = snap(os.path.join(cases["p3"], "project"))
        for args in (("region", imp, an, "--rna", "1-3"), ("view", imp, "--analysis", an, "--rna", "1-3"),
                     ("group", imp, "--analysis", an), ("export-methods", an, "--project", imp)):
            r = rn(*args)
            assert r.returncode == 6 and "MISMATCH" in r.stderr and os.path.basename(target) in r.stderr, (args, r.stderr)
        assert snap(os.path.join(cases["p3"], "project")) == before
        r = rn("explain", "structures", "--analysis", an, "--project", imp)
        assert r.returncode == 0 and "PORTABILITY WARNING" in r.stderr
    finally:
        open(target, "wb").write(keep)


def test_original_unavailable_copy_relink_and_same_name_file(cases):
    orig, away = cases["orig"], cases["orig"] + ".away"
    imp0, an0 = rel_dirs(cases, orig)
    tsv = open(os.path.join(an0, "region_1-3", "region_contacts.tsv"), "rb").read()
    man = json.load(open(os.path.join(imp0, "manifest.json")))
    inc = [s for s in man["structures"] if s["verdict"] == "INCLUDED"]
    os.rename(orig, away)
    try:
        # whole-case copy: self-contained, same numbers, the follow-up replays in the moved project
        imp, an = rel_dirs(cases, cases["case"])
        r = rn("region", imp, an, "--rna", "1-3")
        assert r.returncode == 0 and "NOT SELF-CONTAINED" not in r.stderr and "PORTABILITY" not in r.stderr, r.stderr
        assert open(os.path.join(an, "region_1-3", "region_contacts.tsv"), "rb").read() == tsv
        r = ra("replay-followup", os.path.join(an, "followup", "fu_0001", "followup_plan.json"), "--project", imp, "--analysis", an)
        assert r.returncode == 0 and '"matches": true' in r.stdout, r.stdout + r.stderr
        r = rn("analyse", imp, "--out", os.path.join(cases["base"], "an_case"))
        assert r.returncode == 6 and "rnplens update" in r.stderr
        assert rn("update", os.path.join(cases["case"], "project")).returncode == 0
        # project-only copy: refusal, then relink by search, then the commands run and say where the files are
        imp, an = rel_dirs(cases, cases["p2"])
        before = snap(os.path.join(cases["p2"], "project"))
        r = rn("region", imp, an, "--rna", "1-3")
        assert r.returncode == 6 and "missing:" in r.stderr and os.path.basename(inc[0]["path"]) in r.stderr
        assert "rnplens relink" in r.stderr and snap(os.path.join(cases["p2"], "project")) == before
        r = rn("relink", os.path.join(cases["p2"], "project"), "--search", os.path.join(away, "in"), "--dry-run")
        assert r.returncode == 0 and not os.path.exists(os.path.join(cases["p2"], "project", PT.RELINK_REL))
        r = rn("relink", os.path.join(cases["p2"], "project"), "--search", os.path.join(away, "in"))
        assert r.returncode == 0, r.stdout + r.stderr
        rj = json.load(open(os.path.join(cases["p2"], "project", PT.RELINK_REL)))
        assert rj["schema"] == PT.RELINK_SCHEMA and rj["files"] and rj["inputs"]
        assert all(pv.sha256_file(e["path"]) == e["sha256"] for e in rj["files"])
        r = rn("region", imp, an, "--rna", "1-3")
        assert r.returncode == 0 and "NOT SELF-CONTAINED" in r.stderr and away in r.stderr
        assert open(os.path.join(an, "region_1-3", "region_contacts.tsv"), "rb").read() == tsv
        r = rn("update", os.path.join(cases["p2"], "project"))
        assert r.returncode == 0, r.stdout + r.stderr
        st = S.Project(os.path.join(cases["p2"], "project")).head()
        assert all(x.startswith(away) for x in st["declared"]["inputs"])
        # a different file with the same name at the original path is never used, and never relinked
        imp, an = rel_dirs(cases, cases["p3"])
        os.makedirs(os.path.dirname(inc[0]["path"]))
        other = next(s for s in inc if s["original_sha256"] != inc[0]["original_sha256"])
        shutil.copy2(away + other["path"][len(orig):], inc[0]["path"])
        r = rn("region", imp, an, "--rna", "1-3")
        assert r.returncode == 6 and "MISMATCH" in r.stderr and os.path.basename(inc[0]["path"]) in r.stderr
        r = rn("relink", os.path.join(cases["p3"], "project"), "--search", os.path.join(orig, "in"))
        assert r.returncode == 6 and "rejected (same name, different SHA-256)" in r.stdout
        rj = PT.load_relink(os.path.join(cases["p3"], "project"))
        # the planted bytes are another structure's: they may relink THAT record (same name, same SHA-256), never inc[0]'s
        assert rj["files"].get((os.path.realpath(inc[0]["path"]), inc[0]["original_sha256"])) != inc[0]["path"]
        assert all(pv.sha256_file(q) == h for (p_, h), q in rj["files"].items())
        # --map relinks the same copy explicitly
        r = rn("relink", os.path.join(cases["p3"], "project"), "--map", "%s=%s" % (orig, away))
        assert r.returncode == 0, r.stdout + r.stderr
        assert rn("region", imp, an, "--rna", "1-3").returncode == 0
    finally:
        if os.path.isdir(orig):
            shutil.rmtree(orig)
        os.rename(away, orig)


# ---------------------------------------------------------------- evidence hash definition 2 (unit)
def _records(root, managed):
    os.makedirs(os.path.join(root, "a"), exist_ok=True)
    if managed:
        os.makedirs(os.path.join(root, ".rnplens"), exist_ok=True)
        open(os.path.join(root, ".rnplens", "HEAD"), "w").write("{}")
    s = os.path.join(root, "a", "summary.json")
    pv.atomic_write_json(s, {"created_utc": root, "inventory": [root + "/in/x.pdb"], "value": 0.5})
    st = [{"type": "RECORD", "text": "summary {h}", "cites": ["a/summary.json"],
           "slots": {"h": {"value": pv.sha256_file(s)}, "p": {"value": root + "/a/region.json"}}}]
    log = [{"tool": "region", "call": {"rna": "1-3"}, "status": "OK", "outputs": ["region_1-3/region.json"],
            "message": "read %s (sha256 %s)" % (s, pv.sha256_file(s))}]
    return st, log


@pytest.mark.parametrize("managed", [False, True])
def test_definition_2_is_location_independent(tmp_path, managed):
    hs = {}
    for n in ("first", "second_elsewhere"):
        root = str(tmp_path / n / "proj")
        st, log = _records(root, managed)
        hs[n] = (F.evidence_hash(st, log, root, os.path.join(root, "a")),
                 F.evidence_hash(st, log, root, os.path.join(root, "a"), version=F.EVIDENCE_HASH_V2))
    assert hs["first"][0] != hs["second_elsewhere"][0]            # definition 1: depends on where the records are
    assert hs["first"][1] == hs["second_elsewhere"][1]            # definition 2: does not
    if not managed:
        assert not any(f.endswith(".canonical.json") for dp, dn, fn in os.walk(str(tmp_path)) for f in fn)


def test_old_record_without_version_replays_under_definition_1(cases, tmp_path):
    imp, an = heads(cases["orig"])
    fdir = os.path.join(an, "followup", "fu_0001")
    plan = json.load(open(os.path.join(fdir, "followup_plan.json")))
    rec = json.load(open(os.path.join(fdir, "followup_record.json")))
    ans = json.load(open(os.path.join(fdir, "followup_answer.json")))
    core = [s for s in ans["statements"] if s["type"] not in ("NOTICE",)]
    old = dict(plan)
    old.pop("evidence_hash_version")
    p = str(tmp_path / "old_plan.json")
    json.dump(old, open(p, "w"))
    h1, _ = F.replay_plan(p, imp, an)
    h2, _ = F.replay_plan(os.path.join(fdir, "followup_plan.json"), imp, an)
    assert h2 == rec["evidence_sha256"]          # (this local follow-up has no raw-hash slot, so h1 may equal h2)
    v1 = dict(plan, evidence_hash_version=F.EVIDENCE_HASH_V1)       # a plan without the field is definition 1
    p1 = str(tmp_path / "v1_plan.json")
    json.dump(v1, open(p1, "w"))
    assert F.replay_plan(p1, imp, an)[0] == h1
    with pytest.raises(ValueError):
        F.evidence_hash(core, rec["tool_log"], imp, an, version="rnplens.followup.evidence.9")


def _tracer():
    root = os.path.dirname(HERE)
    sys.path.insert(0, os.path.join(root, "records", "replay"))
    try:
        sp = importlib.util.spec_from_file_location("trace_replay_diffs_p", os.path.join(root, "records", "replay", "trace_replay_diffs.py"))
        m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
        return m
    finally:
        sys.path.pop(0)


def test_tracer_recomputes_under_the_declared_definition(cases, tmp_path):
    """Contract v1 / v2 Amendment 2: the frozen checkers' tracer recomputes each follow-up evidence hash under the
    record's evidence_hash_version (absent = definition 1, the earlier inline rule, unchanged)."""
    TR = _tracer()
    rel = "project/" + os.path.relpath(os.path.join(heads(cases["orig"])[1], "followup", "fu_0001", "followup_record.json"),
                                       os.path.join(cases["orig"], "project"))
    T = TR.Tracer(cases["orig"], cases["case"])          # whole-case copy at another absolute path
    for tree in (T.A, T.B):
        chk = tree.derived_check[rel]
        assert chk["definition"] == F.EVIDENCE_HASH_V2 and chk["equal"], chk
    # definition 1: a record without the field, carrying the definition-1 hash, is checked by the inline rule
    d1 = str(tmp_path / "d1"); shutil.copytree(cases["orig"], d1, symlinks=True)
    p = os.path.join(d1, rel); rec = json.load(open(p))
    ans = json.load(open(p.replace("followup_record.json", "followup_answer.json")))
    imp, an = heads(d1)
    rec.pop("evidence_hash_version")
    rec["evidence_sha256"] = F.evidence_hash(ans["statements"], rec["tool_log"], imp, an, version=None)
    json.dump(rec, open(p, "w"))
    chk = TR.Tree(d1).derived_check[rel]
    assert chk["equal"] and chk["definition"].startswith(F.EVIDENCE_HASH_V1)
    # an unknown definition is never equal
    rec["evidence_hash_version"] = "rnplens.followup.evidence.99"
    json.dump(rec, open(p, "w"))
    assert TR.Tree(d1).derived_check[rel]["equal"] is False
