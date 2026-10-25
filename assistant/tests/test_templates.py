"""Deterministic templates: every template answer must pass the gates, for each workflow."""
import json
import os
import shutil

from rnplens_assistant import ask, llm

from test_assistant_core import IMPORT_BOTH, RB, RF, _plan, _step, _task


def _run(tmp_path, plan, with_ref=False, q="question"):
    t = _task(tmp_path, with_ref=with_ref)
    rec = ask.run(str(t), q, str(tmp_path / "run"), llm.Stub([plan]))
    return rec, open(tmp_path / "run" / "answer.md").read(), json.load(open(tmp_path / "run" / "answer.json"))


def test_agreement_template_passes_gates(tmp_path):
    rec, ans, aj = _run(tmp_path, _plan("AGREEMENT", IMPORT_BOTH + [_step("analyse_predictions", project_id="p")]))
    assert rec["answer_mode"] == "deterministic template" and rec["gate_results"][0]["violations"] == []
    types = [s["type"] for s in aj["statements"]]
    assert "AGREEMENT_SUMMARY" in types and "OBSERVATION" in types and types[-1] == "LIMITATION"
    assert "contact-register agreement" in ans and "binding-surface agreement" in ans
    assert len(rec["llm_calls"]) == 1          # planning only


def test_region_template(tmp_path):
    rec, ans, aj = _run(tmp_path, _plan("REGION_CLAIM", IMPORT_BOTH + [_step("analyse_predictions", project_id="p"),
                                                                      _step("region_contacts", project_id="p", rna_start=1, rna_end=4)]))
    assert rec["gate_results"][0]["violations"] == [] and "Requested region (rna positions 1-4)" in ans


def test_reference_templates(tmp_path):
    steps = [_step("import_predictions", project_id="a", folders=["run_001"], protein_fasta="protein_sequence_001", rna_fasta="rna_sequence_001", accept_offsets=False),
             _step("import_predictions", project_id="b", folders=["run_002"], protein_fasta="protein_sequence_001", rna_fasta="rna_sequence_001", accept_offsets=False),
             _step("evaluate_against_reference", project_id="a", reference="reference_001"),
             _step("compare_prediction_sets", before_project_id="a", after_project_id="b", reference="reference_001")]
    rec, ans, aj = _run(tmp_path, _plan("COMPARE", steps, ref=True, caps=["geometry_decomposition"]), with_ref=True)
    assert rec["gate_results"][0]["violations"] == []
    types = [s["type"] for s in aj["statements"]]
    assert types.count("REFERENCE_COMPARISON") >= 5 and "REFUSAL_WITH_ALTERNATIVE" in types
    assert "change class" in ans and "not that decomposition" in ans


def test_refusal_template_without_reference(tmp_path):
    rec, ans, aj = _run(tmp_path, _plan("WHICH_ANALYSIS", IMPORT_BOTH + [_step("analyse_predictions", project_id="p")], caps=["reference_accuracy", "ranking_or_selection"]))
    assert rec["gate_results"][0]["violations"] == []
    txt = " ".join(aj["rendered"])
    assert "cannot be measured without an experimental reference" in txt and "does not rank" in txt


def test_clarification_template(tmp_path):
    t = _task(tmp_path)
    shutil.rmtree(t / "runB"); os.remove(t / "runA" / "confidence_7K9D_model_0.json")
    plan = _plan("AGREEMENT", [_step("import_predictions", project_id="p", folders=["run_001"], protein_fasta="protein_sequence_001", rna_fasta="rna_sequence_001", accept_offsets=False),
                               _step("analyse_predictions", project_id="p")])
    rec = ask.run(str(t), "q", str(tmp_path / "run"), llm.Stub([plan]))
    aj = json.load(open(tmp_path / "run" / "answer.json"))
    assert rec["gate_results"][0]["violations"] == [] and aj["statements"][0]["type"] == "CLARIFICATION_REQUEST"
