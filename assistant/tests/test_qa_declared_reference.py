"""QA agent-security regression (fix #4): a model's false claim that a reference is supplied must not remove the
'needs a reference' refusal. Before the fix templates.build() trusted plan['reference_supplied'], so 'Which structure
is experimentally correct?' with a scripted plan claiming a reference got no refusal and a gate-failing fallback."""
import json

from rnplens_assistant import ask, llm


def _task(tmp, ref=False):
    t = tmp / "task"
    (t / "runA").mkdir(parents=True); (t / "runA" / "m_0.pdb").write_text("END\n")
    (t / "protein.fasta").write_text(">p\nMKV\n"); (t / "rna.fasta").write_text(">r\nGGA\n")
    refs = []
    if ref:
        (t / "reference.cif").write_text("data_x\n"); refs = ["reference.cif"]
    (t / "task.json").write_text(json.dumps({"reference_files": refs}))
    return t


def test_false_reference_claim_keeps_the_refusal(tmp_path):
    lie = {"goal": "COMPARE", "reference_supplied": True, "requested_capabilities": ["reference_accuracy"], "clarification_needed": None, "steps": []}
    rd = tmp_path / "run"
    rec = ask.run(str(_task(tmp_path)), "Which structure is experimentally correct?", str(rd), llm.Stub([lie]))
    md = (rd / "answer.md").read_text()
    assert "cannot be measured without an experimental reference structure" in md
    assert rec["gate_results"][0]["violations"] == [] and rec["answer_mode"] == "deterministic template"
    assert json.load(open(rd / "plan.json"))["reference_supplied"] is False
    assert rec["reference_claims"] == [{"plan": 0, "model_reference_supplied": True, "declared": False}]


def test_compare_goal_without_reference_capability_still_refused(tmp_path):
    p = {"goal": "COMPARE", "reference_supplied": True, "requested_capabilities": [], "clarification_needed": None, "steps": []}
    rd = tmp_path / "run"
    rec = ask.run(str(_task(tmp_path)), "Is run A closer to the crystal structure?", str(rd), llm.Stub([p]))
    assert "cannot be measured without an experimental reference structure" in (rd / "answer.md").read_text()
    assert rec["gate_results"][0]["violations"] == []


def test_declared_reference_is_used_even_if_the_model_denies_it(tmp_path):
    p = {"goal": "AGREEMENT", "reference_supplied": False, "requested_capabilities": [], "clarification_needed": None, "steps": []}
    rd = tmp_path / "run"
    rec = ask.run(str(_task(tmp_path, ref=True)), "Do they agree?", str(rd), llm.Stub([p]))
    assert json.load(open(rd / "plan.json"))["reference_supplied"] is True
    assert rec["reference_claims"][0] == {"plan": 0, "model_reference_supplied": False, "declared": True}
