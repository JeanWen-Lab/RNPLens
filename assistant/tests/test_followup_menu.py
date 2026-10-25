"""Follow-ups in rnplens assist (menu and NL mode) and the 0.4 functions registered as assistant tools."""
import json
import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_followup_common import PS, RF, RS, clone, make_project  # noqa: E402

from rnplens import assist, capabilities  # noqa: E402
from rnplens_assistant import ask, consent, gates, llm, policy, tools as T  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    b = tmp_path_factory.mktemp("fu_menu")
    make_project(str(b / "x"))
    return str(b / "x")


@pytest.fixture
def pa(base, tmp_path):
    return clone(base, str(tmp_path / "w"))


def _no_codex(monkeypatch):
    spawned = []
    real = subprocess.run
    def guard(args, *a, **k):
        if "codex" in " ".join(map(str, args if isinstance(args, (list, tuple)) else [args])):
            spawned.append(args); raise AssertionError("codex")
        return real(args, *a, **k)
    monkeypatch.setattr(subprocess, "run", guard)
    return spawned


def test_menu_item_then_local_followup_non_interactive(pa, monkeypatch):
    P, A = pa
    spawned = _no_codex(monkeypatch)
    out = []
    rc = assist.main(["--project", P, "--analysis", A, "--item", "C", "--rna", "13-23", "--runs", "exec_A,exec_B",
                      "--followup", "local", "--yes", "--question", "Which contacts are found in only one run?"], out=out.append)
    assert rc == 0 and not spawned
    txt = "\n".join(map(str, out))
    assert "# RNPLens follow-up" in txt and "replay-followup" in txt
    rec = json.load(open(os.path.join(A, "followup", "fu_0001", "followup_record.json")))
    assert rec["initial_result"]["capability"] == "region_run_comparison" and rec["chosen"]["source"] == "local"
    assert rec["user_confirmation"]["method"] == "--yes" and rec["tool_log"][0]["status"] == "OK"


def test_codex_followup_without_consent_falls_back_to_local(pa, monkeypatch):
    P, A = pa
    spawned = _no_codex(monkeypatch)
    made = []
    monkeypatch.setattr(assist, "_make_followup_client", lambda: made.append(1))
    out = []
    rc = assist.main(["--project", P, "--analysis", A, "--item", "B", "--rna", "13-23", "--followup", "codex", "--yes"], out=out.append)
    assert rc == 0 and made == [] and not spawned
    assert "nothing is sent" in "\n".join(map(str, out))


def test_codex_followup_with_consent_and_ready(pa, monkeypatch):
    P, A = pa
    consent.opt_in(P, "--yes")
    from rnplens import doctor
    monkeypatch.setattr(doctor, "agent_status", lambda env=None: (True, []))
    N = {k: None for k in ("rna_start", "rna_end", "protein_start", "protein_end", "runs", "metric", "query", "contact", "evidence_id", "export")}
    stub = llm.Stub([{"follow_up": "inspect_existing_comparison", "args": dict(N, evidence_id="region_13-23/region.json#/summary/only_in_run/exec_B"), "rationale": "x"}])
    monkeypatch.setattr(assist, "_make_followup_client", lambda: stub)
    rc = assist.main(["--project", P, "--analysis", A, "--item", "D", "--evidence", "summary.json#/contacts/rows/0", "--followup", "codex",
                      "--yes", "--question", "Which structures list the contacts found only in exec_B in 13-23?"], out=lambda *x: None)
    assert rc == 0 and len(stub.calls) == 1
    rec = json.load(open(os.path.join(A, "followup", "fu_0001", "followup_record.json")))
    assert rec["mode"] == "codex" and rec["chosen"]["source"] == "codex" and rec["consent_record_id"]


def test_interactive_menu_offers_followups_after_a_result(pa, monkeypatch):
    P, A = pa
    _no_codex(monkeypatch)
    answers = iter(["C", "13-23", "", "1,2", "s", "Which contacts are only in one run?", "1", "y", "q"])
    out = []
    rc = assist.main(["--project", P, "--analysis", A], ask=lambda p: next(answers), out=out.append)
    txt = "\n".join(map(str, out))
    assert rc == 0 and "type s for suggested follow-ups (local" in txt and "Suggested follow-ups (local, no language model)" in txt
    assert os.path.isfile(os.path.join(A, "followup", "fu_0001", "followup_answer.md"))


def test_nl_mode_gains_a_follow_up(pa, tmp_path, monkeypatch):
    P, _ = pa
    from rnplens import doctor
    monkeypatch.setattr(doctor, "agent_status", lambda env=None: (True, []))
    task = tmp_path / "task"
    shutil.copytree(os.path.join(RF, "exec_A"), task / "runA"); shutil.copytree(os.path.join(RF, "exec_B"), task / "runB")
    shutil.copy(PS, task / "protein.fasta"); shutil.copy(RS, task / "rna.fasta")
    step = {k: None for k in ask.PLAN_SCHEMA["properties"]["steps"]["items"]["properties"]}
    plan = {"goal": "AGREEMENT", "reference_supplied": False, "requested_capabilities": ["diagnose_disagreement"], "clarification_needed": None,
            "steps": [dict(step, tool="import_predictions", project_id="p", folders=["run_001", "run_002"], protein_fasta="protein_sequence_001", rna_fasta="rna_sequence_001",
                           accept_offsets=False, purpose="t"), dict(step, tool="analyse_predictions", project_id="p", purpose="t")]}
    monkeypatch.setattr(assist, "_make_client", lambda: llm.Stub([plan]))
    out = []
    rc = assist.main(["--project", P, "--nl", "Do the runs agree, and can Diagnose explain the differences?", "--task", str(task),
                      "--nl-out", str(tmp_path / "nl"), "--followup", "local", "--yes"], out=out.append)
    assert rc == 0, out
    fr = json.load(open(tmp_path / "nl" / "tools" / "analysis_project_1" / "followup" / "fu_0001" / "followup_record.json"))
    assert fr["initial_result"]["kind"] == "assistant_answer" and fr["chosen"]["id"] == "explain_unavailable_metric"
    assert fr["chosen"]["args"]["metric"] in ("diagnose", "diagnose_interpretation")


# ---------------------------------------------------------------- registry and planner
def test_registry_statuses_mirror_capabilities_and_blocked_stay_blocked():
    reg = T.REGISTRY
    offered, missing = capabilities.available()
    caps = {c["id"]: c["status"] for c in offered + missing}
    for name, t in reg["tools"].items():
        if "capability" in t:
            assert t["status"] == caps[t["capability"].split(":")[1]], name
    assert set(reg["tools"]) >= {"region_comparison", "explain_evidence", "export_methods", "show_distinct_proposals"}
    assert all(reg["unavailable"][k]["status"] in ("BLOCKED", "CLOSED", "NOT_OFFERED") for k in reg["unavailable"])
    assert {"diagnose", "geometry_decomposition", "ranking", "grouping", "new_predictions", "mutation_advice"} <= set(reg["unavailable"])
    assert "selection" in reg["unavailable"]["grouping"]["reason"] and reg["followup"]["status"] == "EXPERIMENTAL"
    assert set(T.FUNCS) == set(T.SCHEMAS) and all(t in T.FUNCS for t in reg["tools"])


def _step(tool, **kw):
    s = {k: None for k in ask.PLAN_SCHEMA["properties"]["steps"]["items"]["properties"]}
    s.update(tool=tool, purpose="t", **kw)
    return s


def test_planner_admits_new_tools_only_after_analyse():
    imp = _step("import_predictions", project_id="p", folders=["a"], protein_fasta="p.fa", rna_fasta="r.fa")
    plan = {"steps": [imp, _step("region_comparison", project_id="p", rna_start=1, rna_end=5)], "requested_capabilities": []}
    adm, rej, _ = policy.admit(plan, {"reference_files": []})
    assert rej and rej[0][2] == "P3"
    plan["steps"].insert(1, _step("analyse_predictions", project_id="p"))
    adm, rej, _ = policy.admit(plan, {"reference_files": []})
    assert not rej and [s["tool"] for _, s, _ in adm] == ["import_predictions", "analyse_predictions", "region_comparison"]


def test_new_tools_end_to_end_through_the_pipeline(tmp_path):
    t = tmp_path / "task"
    shutil.copytree(os.path.join(RF, "exec_A"), t / "runA"); shutil.copytree(os.path.join(RF, "exec_B"), t / "runB")
    shutil.copy(PS, t / "protein.fasta"); shutil.copy(RS, t / "rna.fasta")
    json.dump({"task_id": "dev", "reference_files": []}, open(t / "task.json", "w"))
    steps = [_step("import_predictions", project_id="p", folders=["run_001", "run_002"], protein_fasta="protein_sequence_001", rna_fasta="rna_sequence_001", accept_offsets=False),
             _step("analyse_predictions", project_id="p"),
             _step("region_comparison", project_id="p", rna_start=13, rna_end=23, runs=["run_001", "run_002"]),
             _step("explain_evidence", project_id="p", query="unavailable"),
             _step("export_methods", project_id="p"), _step("show_distinct_proposals", project_id="p")]
    plan = {"goal": "AGREEMENT", "reference_supplied": False, "requested_capabilities": [], "clarification_needed": None, "steps": steps}
    rec = ask.run(str(t), "What do the runs share in RNA 13-23?", str(tmp_path / "run"), llm.Stub([plan]))
    assert rec["gate_results"][0]["violations"] == [], rec["gate_results"]
    st = {x["tool"]: x["status"] for x in rec["tool_log"]}
    assert st == {"import_predictions": "IMPORTED", "analyse_predictions": "ANALYSED", "region_comparison": "COMPARED",
                  "explain_evidence": "EXPLAINED", "export_methods": "EXPORTED", "show_distinct_proposals": "GROUPED"}
    ans = open(tmp_path / "run" / "answer.md").read()
    assert "distinct binding proposals" in ans and "found only in run" in ans
    from rnplens_assistant import replay
    h, _ = replay.run(str(tmp_path / "run" / "plan.json"), str(t), str(tmp_path / "replay"))
    assert h == rec["evidence_sha256"]
