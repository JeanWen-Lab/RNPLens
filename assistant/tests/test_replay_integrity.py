"""Replay integrity (0.4 release audit): a replay runs only the plan its run recorded, re-admitted by the policy; a
follow-up replay only the choice its followup_record.json recorded. Deterministic stub planner, public 7K9D example,
local follow-up rules: no network and no language model."""
import contextlib
import copy
import io
import json
import os
import shutil
import sys

import pytest

from rnplens_assistant import ask, llm, replay

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_assistant_core import IMPORT_BOTH, _plan, _step, _task  # noqa: E402
from test_followup_common import make_project  # noqa: E402


@pytest.fixture
def base(tmp_path):
    t = _task(tmp_path, with_ref=False)
    stub = llm.Stub([_plan("AGREEMENT", IMPORT_BOTH + [_step("analyse_predictions", project_id="p")])])
    rec = ask.run(str(t), "Do these two runs agree?", str(tmp_path / "run"), stub)
    plan = json.load(open(tmp_path / "run" / "plan.json"))
    return tmp_path, t, rec, plan


def _put(tmp_path, name, plan, record=None):
    d = tmp_path / name; d.mkdir()
    json.dump(plan, open(d / "plan.json", "w"))
    if record is not None:
        json.dump(record, open(d / "run_record.json", "w"))
    return str(d / "plan.json")


def test_recorded_plan_replays_verified_and_run_keeps_its_signature(base):
    tmp, t, rec, plan = base
    assert rec["plan_sha256"] == replay.plan_sha256(plan)
    h, _log, identity, recorded = replay.run_checked(str(tmp / "run" / "plan.json"), str(t), str(tmp / "r0"))
    assert (h, identity, recorded) == (rec["evidence_sha256"], "VERIFIED", rec["evidence_sha256"])
    h2, _ = replay.run(str(tmp / "run" / "plan.json"), str(t), str(tmp / "r1"))
    assert h2 == rec["evidence_sha256"]


def _variants(plan, pred):
    out = {}
    p = copy.deepcopy(plan); p["steps"] = []; out["empty"] = p
    p = copy.deepcopy(plan); p["steps"].append({"index": 2, "tool": "predict_structure", "args": {}}); out["unregistered"] = p
    p = copy.deepcopy(plan); p["steps"].append({"index": 2, "tool": "region_contacts", "args": {"no_such_argument": 1}}); out["bad_args"] = p
    p = copy.deepcopy(plan); p["goal"] = "RANKING"; out["goal"] = p
    p = copy.deepcopy(plan); p["steps"].append({"index": 2, "tool": "evaluate_against_reference",
                                                "args": {"project_id": "project_1", "reference": pred}}); out["p2"] = p
    return out


def _pred(t):
    for root, _d, files in sorted(os.walk(t / "runB")):
        for f in sorted(files):
            if f.endswith((".cif", ".pdb")):
                return os.path.relpath(os.path.join(root, f), t)


@pytest.mark.parametrize("which", ["empty", "unregistered", "bad_args", "goal", "p2"])
def test_changed_plan_is_refused_before_anything_runs(base, which):
    tmp, t, rec, plan = base
    f = _put(tmp, which, _variants(plan, _pred(t))[which], rec)
    with pytest.raises(replay.ReplayRefused) as ex:
        replay.run(f, str(t), str(tmp / ("out_" + which)))
    assert ex.value.code == "PLAN_CHANGED" and not (tmp / ("out_" + which)).exists()


def test_policy_violation_is_refused_even_with_a_consistent_record(base):
    tmp, t, rec, plan = base
    p = _variants(plan, _pred(t))["p2"]
    f = _put(tmp, "p2c", p, dict(rec, plan_sha256=replay.plan_sha256(p)))
    with pytest.raises(replay.ReplayRefused) as ex:
        replay.run(f, str(t), str(tmp / "out_p2c"))
    assert ex.value.code == "STEP_REJECTED" and "P2" in ex.value.message
    assert not (tmp / "out_p2c").exists()


def test_unregistered_tool_with_a_consistent_record_is_refused(base):
    tmp, t, rec, plan = base
    p = _variants(plan, _pred(t))["unregistered"]
    f = _put(tmp, "unc", p, dict(rec, plan_sha256=replay.plan_sha256(p)))
    with pytest.raises(replay.ReplayRefused) as ex:
        replay.run(f, str(t), str(tmp / "out_unc"))
    assert ex.value.code == "STEP_REJECTED"


def test_arguments_outside_the_admitted_arguments_are_refused(base):
    tmp, t, rec, plan = base
    p = copy.deepcopy(plan); p["steps"][-1]["args"]["extra"] = "x"
    f = _put(tmp, "args", p, dict(rec, plan_sha256=replay.plan_sha256(p)))
    with pytest.raises(replay.ReplayRefused) as ex:
        replay.run(f, str(t), str(tmp / "out_args"))
    assert ex.value.code == "STEP_ARGS_CHANGED"


def test_plan_without_record_or_historical_record_is_not_verified_but_replays(base):
    tmp, t, rec, plan = base
    for name, record in (("norec", None), ("hist", {k: v for k, v in rec.items() if k != "plan_sha256"})):
        f = _put(tmp, name, copy.deepcopy(plan), record)
        h, _log, identity, _r = replay.run_checked(f, str(t), str(tmp / ("out_" + name)))
        assert identity == "NOT_VERIFIED" and h == rec["evidence_sha256"], name


def _cli(args):
    from rnplens_assistant import __main__ as M
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        rc = M.main(args)
    return rc, o.getvalue(), e.getvalue()


def test_cli_uses_the_recorded_hash_and_exits_5_on_refusal(base):
    tmp, t, rec, plan = base
    rc, out, _ = _cli(["replay", str(tmp / "run" / "plan.json"), "--task", str(t), "--out", str(tmp / "c0")])
    j = json.loads(out.strip().splitlines()[-1])
    assert rc == 0 and j["matches"] is True and j["plan_identity"] == "VERIFIED" and j["expected_from"] == "run_record.json"
    f = _put(tmp, "cg", _variants(plan, _pred(t))["goal"], rec)
    rc, out, err = _cli(["replay", f, "--task", str(t), "--out", str(tmp / "c1"), "--expect", rec["evidence_sha256"]])
    assert rc == 5 and "PLAN_CHANGED" in err and "nothing was run" in err and not (tmp / "c1").exists()


@pytest.fixture
def fu(tmp_path):
    from rnplens_assistant import followup as F
    P, A = make_project(str(tmp_path), region=False)
    rec = F.run(P, A, "Which residues contact RNA 13-23?", mode="local", choice=1, yes=True, out=lambda *a: None)
    d = os.path.join(A, rec["dir"])
    assert rec["tool_log"], rec.get("stop")
    return P, A, rec, d


def test_followup_recorded_plan_is_verified(fu):
    P, A, rec, d = fu
    h, _log, ok, identity = replay.run_followup_checked(os.path.join(d, "followup_plan.json"), P, A)
    assert ok and identity == "VERIFIED" and h == rec["evidence_sha256"]
    assert replay.run_followup(os.path.join(d, "followup_plan.json"), P, A)[2] is True


def test_followup_plan_rewritten_with_its_own_hash_is_refused(fu, tmp_path):
    P, A, rec, d = fu
    f = os.path.join(d, "followup_plan.json")
    p = json.load(open(f))
    region = [c for c in p["tool_calls"] if c.get("tool") == "region"]
    assert region, p["tool_calls"]
    lo = int(region[0]["rna_range"].split("-")[0])
    p["tool_calls"] = [dict(c, rna_range="%d-%d" % (lo, lo + 5)) if c.get("tool") == "region" else c for c in p["tool_calls"]]
    p["args"] = dict(p["args"], rna_end=lo + 5)
    alone = tmp_path / "alone"; alone.mkdir()
    json.dump(p, open(alone / "followup_plan.json", "w"))
    h_t, _log = __import__("rnplens_assistant.followup", fromlist=["x"]).replay_plan(str(alone / "followup_plan.json"), P, A)
    assert h_t != rec["evidence_sha256"]                      # the change alters the evidence
    p["evidence_sha256"] = h_t                                # the plan now agrees with itself
    json.dump(p, open(f, "w"))
    with pytest.raises(replay.ReplayRefused) as ex:
        replay.run_followup(f, P, A)
    assert ex.value.code == "PLAN_CHANGED" and "tool_calls" in ex.value.message
    json.dump(p, open(alone / "followup_plan.json", "w"))     # without its record: replays, never VERIFIED
    h, _log, ok, identity = replay.run_followup_checked(str(alone / "followup_plan.json"), P, A)
    assert ok and identity == "NOT_VERIFIED"


def test_recorded_plan_whose_import_was_removed_after_admission_still_replays(base):
    """Historical pattern: the run's identifier check (P9) removed the import after policy admission, so the saved
    plan holds only the analysis step; sequencing (P3) is not re-applied and the step fails as a tool error, as it did."""
    tmp, t, rec, plan = base
    p = copy.deepcopy(plan); p["steps"] = [s for s in p["steps"] if s["tool"] != "import_predictions"]
    assert [s["tool"] for s in p["steps"]] == ["analyse_predictions"]
    f = _put(tmp, "noimport", p, dict(rec, plan_sha256=replay.plan_sha256(p)))
    h, log, identity, _r = replay.run_checked(f, str(t), str(tmp / "out_noimport"))
    assert identity == "VERIFIED" and h != rec["evidence_sha256"] and log


def test_reference_imported_as_prediction_is_refused_even_when_imported_twice(tmp_path):
    t = _task(tmp_path, with_ref=True)
    stub = llm.Stub([_plan("AGREEMENT", IMPORT_BOTH + [_step("analyse_predictions", project_id="p")])])
    rec = ask.run(str(t), "Do these two runs agree?", str(tmp_path / "run"), stub)
    plan = json.load(open(tmp_path / "run" / "plan.json"))
    imp = next(s for s in plan["steps"] if s["tool"] == "import_predictions")
    p = copy.deepcopy(plan)
    p["steps"].append({"index": 9, "tool": "import_predictions", "args": dict(imp["args"], folders=["reference.cif"])})
    f = _put(tmp_path, "refimp", p, dict(rec, plan_sha256=replay.plan_sha256(p)))
    with pytest.raises(replay.ReplayRefused) as ex:
        replay.run(f, str(t), str(tmp_path / "out_refimp"))
    assert ex.value.code == "STEP_REJECTED" and "P2" in ex.value.message


def test_extra_step_with_invalid_arguments_and_a_consistent_record_is_refused(base):
    tmp, t, rec, plan = base
    p = _variants(plan, _pred(t))["bad_args"]
    f = _put(tmp, "badc", p, dict(rec, plan_sha256=replay.plan_sha256(p)))
    with pytest.raises(replay.ReplayRefused) as ex:
        replay.run(f, str(t), str(tmp / "out_badc"))
    assert ex.value.code == "STEP_ARGS_CHANGED"
