"""Development tests for the assistant with a deterministic stub in place of the language model (no network)."""
import json
import os
import re
import shutil

import pytest

from rnplens_assistant import ask, evidence as EV, gates, llm, policy, replay, tools as T

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EX = os.path.join(ROOT, "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")
RB = os.path.join(EX, "reference_based")


def _task(tmp, with_ref=False):
    t = tmp / "task"
    shutil.copytree(os.path.join(RF, "exec_A"), t / "runA"); shutil.copytree(os.path.join(RF, "exec_B"), t / "runB")
    shutil.copy(os.path.join(RB, "7K9D_protein.fasta"), t / "protein.fasta"); shutil.copy(os.path.join(RB, "7K9D_rna.fasta"), t / "rna.fasta")
    refs = []
    if with_ref:
        shutil.copy(os.path.join(RB, "7K9D_reference.cif"), t / "reference.cif"); refs = ["reference.cif"]
    json.dump({"task_id": "dev", "reference_files": refs}, open(t / "task.json", "w"))
    return t


def _step(tool, **kw):
    s = {k: None for k in ask.PLAN_SCHEMA["properties"]["steps"]["items"]["properties"]}
    s.update(tool=tool, purpose="dev", **kw); return s


def _plan(goal, steps, ref=False, caps=()):
    return {"goal": goal, "reference_supplied": ref, "requested_capabilities": list(caps), "clarification_needed": None, "steps": steps}


def _ev(user):
    return json.loads(user.split("Evidence records:\n", 1)[1].split("\n\nYour previous draft", 1)[0])


def _id(ev, pat):
    return next(r["id"] for r in ev if re.search(pat, r["what"]) and r["state"] == "COMPUTED")


IMPORT_BOTH = [_step("import_predictions", project_id="p", folders=["run_001", "run_002"], protein_fasta="protein_sequence_001", rna_fasta="rna_sequence_001", accept_offsets=False)]


def test_agreement_workflow_end_to_end_and_replay(tmp_path):
    t = _task(tmp_path)
    def draft(user):
        ev = _ev(user); s = _id(ev, "binding-surface agreement"); r = _id(ev, "contact-register agreement")
        return {"statements": [{"type": "AGREEMENT_SUMMARY", "text": "Binding-surface agreement between the two runs is {%s}; contact-register agreement is {%s}." % (s, r),
                                "evidence_ids": [s, r]},
                               {"type": "LIMITATION", "text": "Agreement between predictions does not show that either structure is right.", "evidence_ids": []}]}
    stub = llm.Stub([_plan("AGREEMENT", IMPORT_BOTH + [_step("analyse_predictions", project_id="p")]), draft])
    rec = ask.run(str(t), "Do these two runs agree?", str(tmp_path / "run"), stub, answer_mode="draft")
    assert rec["answer_mode"] == "drafted" and rec["gate_results"][0]["violations"] == []
    ans = open(tmp_path / "run" / "answer.md").read()
    S = [json.loads(l) for l in open(tmp_path / "run" / "evidence.jsonl")]
    reg = next(r for r in S if r["field"] == "repeat_agreement.BOLTZ2.register_agreement")
    assert ("%.3f" % reg["value"]) in ans                        # value inserted from the record
    exp = json.load(open(os.path.join(EX, "expected_output", "B1_report_7K9D", "result.json")))["summary"]["repeat_agreement"]["BOLTZ2"]
    assert reg["value"] == exp["register_agreement"]              # = rc3 expected output
    assert any(r["field"] == "diagnose" and r["state"] == "TOOL_BLOCKED" for r in S)
    h, _ = replay.run(str(tmp_path / "run" / "plan.json"), str(t), str(tmp_path / "replay"))
    assert h == rec["evidence_sha256"]


def test_policy_rejects_reference_tool_without_reference_and_records_it(tmp_path):
    t = _task(tmp_path)
    bad = _plan("COMPARE", IMPORT_BOTH + [_step("evaluate_against_reference", project_id="p", reference="reference_001")])
    good = _plan("WHICH_ANALYSIS", IMPORT_BOTH + [_step("analyse_predictions", project_id="p")], caps=["reference_accuracy"])
    refusal = {"statements": [{"type": "REFUSAL_WITH_ALTERNATIVE", "text": "Accuracy cannot be measured without an experimental reference; "
                               "the interface agreement of the predictions can be compared instead.", "evidence_ids": []}]}
    rec = ask.run(str(t), "Which run is more accurate?", str(tmp_path / "run"), llm.Stub([bad, good, refusal]), answer_mode="draft")
    assert rec["rejected_steps"] and rec["rejected_steps"][0]["rule"] == "P2"
    assert all(s["tool"] != "evaluate_against_reference" for s in json.load(open(tmp_path / "run" / "plan.json"))["steps"])


@pytest.mark.parametrize("plan,rule", [
    (_plan("AGREEMENT", [_step("analyse_predictions", project_id="p")]), "P3"),
    (_plan("AGREEMENT", [_step("import_predictions", project_id="p", folders=["/etc"], protein_fasta="protein.fasta", rna_fasta="rna.fasta")]), "P7"),
    (_plan("COMPARE", IMPORT_BOTH + [_step("compare_prediction_sets", before_project_id="p", after_project_id="p", reference="reference.cif")], ref=True), "P6"),
    (_plan("AGREEMENT", IMPORT_BOTH + [_step("region_contacts", project_id="p", rna_start=1, rna_end=4)]), "P3"),
])
def test_policy_rules(plan, rule):
    _, rej, _ = policy.admit(plan, {"reference_files": ["reference.cif"]})
    assert rej and rej[0][2] == rule


def test_reference_outside_task_is_unreadable(tmp_path):
    t = _task(tmp_path)
    ws = T.Workspace(str(t), str(tmp_path / "run"))
    st, res, recs = T.call(ws, "import_predictions", {"project_id": "p", "folders": ["runA"], "protein_fasta": "protein.fasta", "rna_fasta": "rna.fasta"})
    assert st == "OK"
    st, res, recs = T.call(ws, "evaluate_against_reference", {"project_id": "p", "reference": "../../" + os.path.relpath(os.path.join(RB, "7K9D_reference.cif"), "/")})
    assert st == "ACCESS_REFUSED" and recs[0]["state"] == "ACCESS_REFUSED"


def _store():
    s = EV.Store()
    s.add([EV.rec("t", "p", "a", "binding-surface agreement", 0.8, None, "descriptive", "PROTEIN_SURFACE", "x"),
           EV.rec("t", "p", "b", "DockQ of s001", 0.5, None, "reference_based", "REFERENCE", "x"),
           EV.missing("t", "p", "c", "NOT_COMPUTED", "repeat agreement not computed"),
           EV.rec("t", "p", "d", "contact-register agreement", 0.3, None, "descriptive", "EXACT_CONTACT", "x")], 0)
    return s


@pytest.mark.parametrize("st,code", [
    ({"type": "AGREEMENT_SUMMARY", "text": "Surface agreement is 0.8.", "evidence_ids": ["E1"]}, "A1"),           # digit outside slot
    ({"type": "AGREEMENT_SUMMARY", "text": "Agreement is {E3}.", "evidence_ids": ["E3"]}, "A1"),                   # slot on a not-computed record
    ({"type": "AGREEMENT_SUMMARY", "text": "Value {E9}.", "evidence_ids": ["E9"]}, "A1"),                          # unknown record
    ({"type": "AGREEMENT_SUMMARY", "text": "DockQ is {E2}.", "evidence_ids": ["E2"]}, "A2"),                       # reference evidence in agreement
    ({"type": "AGREEMENT_SUMMARY", "text": "The runs share the same contact register ({E1}).", "evidence_ids": ["E1"]}, "A3"),  # surface -> register
    ({"type": "AGREEMENT_SUMMARY", "text": "The runs improved the interface ({E1}).", "evidence_ids": ["E1"]}, "A4"),
    ({"type": "AGREEMENT_SUMMARY", "text": "All candidates are accurate ({E1}).", "evidence_ids": ["E1"]}, "A5"),  # no digit, still caught (forbidden lexicon)
    ({"type": "AGREEMENT_SUMMARY", "text": "This is the most reliable binding mode ({E4}).", "evidence_ids": ["E4"]}, "A5"),
    ({"type": "AGREEMENT_SUMMARY", "text": "Diagnose shows a high band ({E4}).", "evidence_ids": ["E4"]}, "A6"),
    ({"type": "REFUSAL_WITH_ALTERNATIVE", "text": "Not possible.", "evidence_ids": []}, "A9"),
])
def test_gate_mutations_are_caught(st, code):
    v = gates.check({"statements": [st]}, _store(), "AGREEMENT", [], False)
    assert any(x.startswith(code) for x in v), v


def test_gate_accepts_a_proper_answer_and_requires_goal_coverage():
    ok = {"statements": [{"type": "AGREEMENT_SUMMARY", "text": "Surface agreement {E1}, register agreement {E4}.", "evidence_ids": ["E1", "E4"]}]}
    assert gates.check(ok, _store(), "AGREEMENT", [], False) == []
    only_lim = {"statements": [{"type": "LIMITATION", "text": "Nothing is established.", "evidence_ids": []}]}
    assert any(x.startswith("A8") for x in gates.check(only_lim, _store(), "AGREEMENT", [], False))
    ref = {"statements": [{"type": "REFERENCE_COMPARISON", "text": "DockQ {E2}.", "evidence_ids": ["E2"]}]}
    assert any(x.startswith("A4") for x in gates.check(ref, _store(), "COMPARE", [], False))   # no reference supplied
    assert gates.check(ref, _store(), "COMPARE", [], True) == []


def test_failed_drafts_fall_back_to_the_template(tmp_path):
    t = _task(tmp_path)
    bad = {"statements": [{"type": "AGREEMENT_SUMMARY", "text": "Agreement is 0.89, the best mode.", "evidence_ids": []}]}
    rec = ask.run(str(t), "Do these agree?", str(tmp_path / "run"), llm.Stub([_plan("AGREEMENT", IMPORT_BOTH + [_step("analyse_predictions", project_id="p")]), bad, bad]), answer_mode="draft")
    assert rec["answer_mode"].startswith("fixed template") and rec["gate_results"][-1]["violations"] == []
    assert len(rec["gate_results"]) == 3


def test_top_level_loose_structure_is_never_listed_and_cannot_be_imported(tmp_path):
    """0.4 privacy rule: a top-level file that is neither a FASTA file nor a declared reference (it could be an
    undeclared or restricted reference) is not listed to the planner; a plan naming it is refused (P9), nothing runs."""
    t = tmp_path / "task"; t.mkdir()
    shutil.copy(os.path.join(RB, "7K9D_prediction.pdb"), t / "loose.pdb")
    shutil.copy(os.path.join(RB, "7K9D_protein.fasta"), t / "protein.fasta"); shutil.copy(os.path.join(RB, "7K9D_rna.fasta"), t / "rna.fasta")
    json.dump({"task_id": "dev2", "reference_files": []}, open(t / "task.json", "w"))
    seen = []
    imp = [_step("import_predictions", project_id="p", folders=["loose.pdb"], protein_fasta="protein_sequence_001", rna_fasta="rna_sequence_001", accept_offsets=False)]
    def plan_reply(user):
        seen.append(user)
        return _plan("AGREEMENT", imp + [_step("analyse_predictions", project_id="p")])
    no_q = {"statements": [{"type": "LIMITATION", "text": "The structure could not be imported.", "evidence_ids": []}]}
    rec = ask.run(str(t), "What does this prediction propose?", str(tmp_path / "run"),
                  llm.Stub([plan_reply, plan_reply, no_q, no_q]), answer_mode="draft")
    assert "loose" not in seen[0] and "Task inputs (2 files" in seen[0] and "reference supplied with this task: none" in seen[0]
    assert any(r["rule"] == "P9" for r in rec["rejected_steps"]) and not any(x["status"] == "IMPORTED" for x in rec["tool_log"])
