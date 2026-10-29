"""0.4 Project-state track: rnplens.state (versioned store, atomic commits, corruption detection, decisions, cache)."""
import json
import os
import stat
import subprocess
import sys

import pytest

from rnplens import provenance as pv
from rnplens import state as S


def _p(tmp_path):
    return S.Project(str(tmp_path / "proj"))


def test_empty_project_has_no_version(tmp_path):
    P = _p(tmp_path)
    assert P.head() is None and P.versions() == [] and P.verify() == [] and not P.exists()
    assert not os.path.exists(P.dir)          # reading never writes


def test_commit_versions_are_immutable_snapshots_with_hash_chain(tmp_path):
    P = _p(tmp_path)
    v1 = P.commit({"a": 1, "inputs": {"files": {"/x": "0" * 64}}}, "first")
    v2 = P.commit({"b": 2}, "second")
    assert (v1, v2) == ("v0001", "v0002")
    h = P.head()
    assert h["a"] == 1 and h["b"] == 2 and h["parent"] == "v0001" and h["version"] == "v0002"
    assert h["parent_sha256"] == pv.sha256_file(os.path.join(P.state_dir, "v0001.json"))
    assert h["tool_version"] == S.tool_version() == "0.4.0"
    assert [v["version"] for v in P.versions()] == ["v0001", "v0002"]
    assert P.load("v0001")["a"] == 1 and "b" not in P.load("v0001")
    for v in ("v0001", "v0002"):
        mode = os.stat(os.path.join(P.state_dir, v + ".json")).st_mode
        assert not mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    ptr = json.load(open(P.head_path))
    assert ptr == {"version": "v0002", "sha256": pv.sha256_file(os.path.join(P.state_dir, "v0002.json"))}


def test_commit_refuses_reserved_fields(tmp_path):
    P = _p(tmp_path)
    with pytest.raises(S.StateError):
        P.commit({"version": "v0009"}, "x")
    with pytest.raises(S.StateError):
        P.commit(["not", "a", "dict"], "x")
    assert P.head() is None


def test_failed_head_update_keeps_previous_version_current(tmp_path, monkeypatch):
    P = _p(tmp_path)
    P.commit({"n": 1}, "ok")
    before = open(P.head_path, "rb").read()

    def boom(self, vid, sha):
        raise OSError("disk full (injected)")
    monkeypatch.setattr(S.Project, "_write_head", boom)
    with pytest.raises(OSError):
        P.commit({"n": 2}, "fails")
    monkeypatch.undo()
    assert open(P.head_path, "rb").read() == before
    assert P.head()["n"] == 1 and P.verify() == []
    assert not os.path.exists(os.path.join(P.dir, "LOCK"))
    # the interrupted version file is kept aside, unchanged, when its number is reused
    orphan = open(os.path.join(P.state_dir, "v0002.json"), "rb").read()
    assert P.commit({"n": 3}, "retry") == "v0002" and P.head()["n"] == 3
    ab = os.listdir(os.path.join(P.state_dir, "abandoned"))
    assert len(ab) == 1 and open(os.path.join(P.state_dir, "abandoned", ab[0]), "rb").read() == orphan


def test_crash_during_version_write_leaves_no_partial_file(tmp_path, monkeypatch):
    P = _p(tmp_path)
    P.commit({"n": 1}, "ok")
    real = pv.atomic_write_text

    def boom(path, text):
        real(path + ".never", "")            # side effect to prove the call happened
        raise KeyboardInterrupt("killed (injected)")
    monkeypatch.setattr(pv, "atomic_write_text", boom)
    with pytest.raises(KeyboardInterrupt):
        P.commit({"n": 2}, "killed")
    monkeypatch.undo()
    assert P.head()["n"] == 1 and not os.path.exists(os.path.join(P.state_dir, "v0002.json"))


def test_corruption_of_an_earlier_version_is_detected(tmp_path):
    P = _p(tmp_path)
    P.commit({"n": 1}, "a"); P.commit({"n": 2}, "b"); P.commit({"n": 3}, "c")
    p1 = os.path.join(P.state_dir, "v0001.json")
    os.chmod(p1, 0o644)
    d = json.load(open(p1)); d["n"] = 99
    open(p1, "w").write(json.dumps(d))
    probs = P.verify()
    assert probs and "v0001" in probs[0] and "changed after it was written" in probs[0]
    with pytest.raises(S.StateCorrupted):
        P.versions()
    with pytest.raises(S.StateCorrupted):
        P.load("v0001")
    assert P.head()["n"] == 3                  # HEAD itself still verifies


def test_corrupted_or_malformed_head_is_refused(tmp_path):
    P = _p(tmp_path)
    P.commit({"n": 1}, "a")
    p = os.path.join(P.state_dir, "v0001.json")
    os.chmod(p, 0o644)
    open(p, "a").write(" ")
    with pytest.raises(S.StateCorrupted):
        P.head()
    open(P.head_path, "w").write("{not json")
    with pytest.raises(S.StateCorrupted):
        P.head()
    with pytest.raises(S.StateCorrupted):
        P.commit({"n": 2}, "must not proceed on a corrupted state")


def test_missing_version_file_is_detected(tmp_path):
    P = _p(tmp_path)
    P.commit({"n": 1}, "a"); P.commit({"n": 2}, "b")
    os.replace(os.path.join(P.state_dir, "v0001.json"), str(tmp_path / "moved.json"))
    assert P.verify() and "missing" in P.verify()[0]


def test_state_persists_across_instances_and_processes(tmp_path):
    P = _p(tmp_path)
    P.commit({"n": 1}, "a")
    code = ("import sys; from rnplens import state as S; P = S.Project(sys.argv[1]); "
            "assert P.head()['n'] == 1; print(P.commit({'n': 2}, 'from another process'))")
    r = subprocess.run([sys.executable, "-c", code, P.root], capture_output=True, text=True, env=dict(os.environ))
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "v0002" and S.Project(P.root).head()["n"] == 2


def test_lock_refuses_a_live_holder_and_takes_over_a_dead_one(tmp_path):
    P = _p(tmp_path)
    P.commit({"n": 1}, "a")
    lp = os.path.join(P.dir, "LOCK")
    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        open(lp, "w").write(json.dumps({"pid": sleeper.pid, "since_utc": "x"}))
        with pytest.raises(S.ProjectLocked):
            P.commit({"n": 2}, "blocked")
    finally:
        sleeper.kill(); sleeper.wait()
    open(lp, "w").write(json.dumps({"pid": sleeper.pid, "since_utc": "x"}))   # holder exited without unlocking
    assert P.commit({"n": 2}, "takes over") == "v0002" and not os.path.exists(lp)


# ---------------------------------------------------------------- cache keys
BASE = dict(kind="analyse", config={"diagnose": True, "reference": None}, input_hashes={"a": "1", "b": "2"},
            construct_sha="c" * 64, correspondence={"s001": ["A", "B"]}, selection_rule={"run": "highest"},
            tool_version="0.4.0")


def test_analysis_key_is_deterministic_and_order_independent():
    k = S.analysis_key(**BASE)
    assert k == S.analysis_key(**BASE) and len(k) == 64
    assert k == S.analysis_key(**dict(BASE, input_hashes={"b": "2", "a": "1"}))
    assert k == S.analysis_key(**dict(BASE, config={"reference": None, "diagnose": True}))
    assert S.analysis_key(**BASE) == S.analysis_key(**dict(BASE, definition=None))


@pytest.mark.parametrize("field,value", [
    ("kind", "import"), ("config", {"diagnose": False, "reference": None}), ("input_hashes", {"a": "1", "b": "3"}),
    ("input_hashes", {"a": "1"}), ("construct_sha", "d" * 64), ("correspondence", {"s001": ["C", "B"]}),
    ("selection_rule", {"run": "chosen in a recorded answer"}), ("tool_version", "0.4.1"), ("definition", {"cutoff": 4.5})])
def test_every_key_component_changes_the_key(field, value):
    assert S.analysis_key(**dict(BASE, **{field: value})) != S.analysis_key(**BASE)
    comp_a, comp_b = S.key_components(**BASE), S.key_components(**dict(BASE, **{field: value}))
    assert [k for k in comp_a if comp_a[k] != comp_b[k]]      # the changed part is identifiable


def test_cache_store_lookup_verifies_files(tmp_path):
    P = _p(tmp_path)
    d = os.path.join(P.root, "analyses", "v0001", "main")
    os.makedirs(os.path.join(d, "report"))
    open(os.path.join(d, "summary.json"), "w").write("{}")
    open(os.path.join(d, "report", "x.json"), "w").write("[]")
    k = S.analysis_key(**BASE)
    assert P.cache_lookup(k) is None
    e = P.cache_store(k, d, {"group": "main"})
    assert e["outdir"] == "analyses/v0001/main" and set(e["files"]) == {"summary.json", "report/x.json"}
    assert P.cache_lookup(k)["path"] == d and P.cache_lookup(k)["meta"] == {"group": "main"}
    assert P.cache_store(k, d, {"group": "other"})["meta"] == {"group": "main"}     # never overwritten
    open(os.path.join(d, "summary.json"), "w").write('{"tampered": 1}')
    assert P.cache_lookup(k) is None                                               # changed work is not reused
    e2 = P.cache_store(k, d, {"group": "main", "again": True})
    assert P.cache_lookup(k)["meta"]["again"] and os.listdir(os.path.join(P.cache_dir, "invalid"))
    with pytest.raises(S.StateError):
        P.cache_lookup("../../etc/passwd")
    with pytest.raises(S.StateError):
        P.cache_store(k, str(tmp_path), {})                                        # outside the project


def test_cache_stays_valid_when_later_outputs_are_added_but_not_when_a_recorded_file_goes(tmp_path):
    """Integration defect D1: region/methods/explain/follow-up outputs written into an analysis folder later must not
    invalidate the cached analysis; a missing or changed recorded file must."""
    P = _p(tmp_path)
    d = os.path.join(P.root, "analyses", "v0001", "main")
    os.makedirs(os.path.join(d, "report"))
    open(os.path.join(d, "summary.json"), "w").write("{}")
    k = S.analysis_key(**BASE)
    P.cache_store(k, d, {"group": "main"})
    os.makedirs(os.path.join(d, "region_13-23"))
    open(os.path.join(d, "region_13-23", "region.json"), "w").write("{}")       # added later
    assert P.cache_lookup(k) is not None
    os.remove(os.path.join(d, "summary.json"))                                   # recorded file removed
    assert P.cache_lookup(k) is None


# ---------------------------------------------------------------- decisions
def _ans(option, **kw):
    return dict({"option": option, "text": "my words", "effects": {}, "question": {"id": "q"}}, **kw)


def test_record_decision_keeps_provenance(tmp_path):
    P = _p(tmp_path)
    P.commit({"n": 1}, "a")
    vid, rec = P.record_decision("construct_mismatch:/r", _ans("exclude_run", effects={"run_in_analysis:/r": False}),
                                 {"run:/r": "f" * 64})
    assert vid == "v0002" and rec["recorded_in_version"] == "v0002"
    for k in ("recorded_utc", "text", "option", "depends_on", "question", "serial", "status"):
        assert rec[k] is not None
    assert rec["status"] == "ACTIVE" and P.decisions()["construct_mismatch:/r"]["option"] == "exclude_run"
    assert P.decision_log()[0]["text"] == "my words"
    # the same answer again changes nothing
    assert P.record_decision("construct_mismatch:/r", _ans("exclude_run", effects={"run_in_analysis:/r": False}),
                             {"run:/r": "f" * 64})[0] == "v0002"
    with pytest.raises(S.StateError):
        P.record_decision("q2", _ans("x"), {})                     # an answer must name what it depends on
    with pytest.raises(S.StateError):
        P.record_decision("q2", {"text": "no option"}, {"file:/x": "1"})


def test_contradictory_answer_to_the_same_question_is_refused_not_overwritten(tmp_path):
    P = _p(tmp_path)
    P.commit({"n": 1}, "a")
    P.record_decision("construct_mismatch:/r", _ans("exclude_run"), {"run:/r": "1"})
    with pytest.raises(S.ContradictoryAnswer) as ex:
        P.record_decision("construct_mismatch:/r", _ans("use_as_reference_set"), {"run:/r": "1"})
    assert "already answered 'exclude_run'" in str(ex.value) and "--revise" in str(ex.value)
    assert P.head_id() == "v0002" and P.decisions()["construct_mismatch:/r"]["option"] == "exclude_run"
    vid, rec = P.record_decision("construct_mismatch:/r", _ans("use_as_reference_set"), {"run:/r": "1"}, revise=True)
    assert rec["supersedes"] == 1 and P.decisions()["construct_mismatch:/r"]["option"] == "use_as_reference_set"
    assert [(r["option"], r["status"]) for r in P.decision_log()] == [
        ("exclude_run", "ACTIVE"), ("exclude_run", "SUPERSEDED"), ("use_as_reference_set", "ACTIVE")]
    assert P.load("v0002")["decisions"]["construct_mismatch:/r"]["option"] == "exclude_run"   # earlier state kept


def test_contradictory_effects_across_questions_are_refused(tmp_path):
    P = _p(tmp_path)
    P.commit({"n": 1}, "a")
    P.record_decision("engine_designation:/r", _ans("designate:r#0", effects={"run_in_analysis:/r": True}), {"run:/r": "1"})
    with pytest.raises(S.ContradictoryAnswer) as ex:
        P.record_decision("construct_mismatch:/r", _ans("exclude_run", effects={"run_in_analysis:/r": False}), {"run:/r": "1"})
    assert "engine_designation:/r" in str(ex.value) and "run_in_analysis:/r" in str(ex.value)
    assert "construct_mismatch:/r" not in P.decisions()
