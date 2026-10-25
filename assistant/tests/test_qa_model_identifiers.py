"""QA agent-security regression (fix #3): model-chosen identifiers must not reach the rendered answer verbatim.
Before the fix a scripted plan with project_id 'DockQ_0_99_best' produced 'Project DockQ_0_99_best: ...' in answer.md
(the gates whitelist project ids), and an unknown metric name was echoed in the 'not computed' list."""
import json
import os

from rnplens_assistant import ask, evidence as EV, llm, tools as T

MODEL_PID, MODEL_METRIC = "DockQ_0_99_best", "best_s003_DockQ_0_95"


def _task(tmp):
    t = tmp / "task"
    for r in ("runA", "runB"):
        (t / r).mkdir(parents=True)
        (t / r / "m_0.pdb").write_text("END\n")
    (t / "protein.fasta").write_text(">p\nMKV\n"); (t / "rna.fasta").write_text(">r\nGGA\n")
    return t


def _step(tool, **kw):
    s = {k: None for k in ask.PLAN_SCHEMA["properties"]["steps"]["items"]["properties"]}
    s.update(tool=tool, purpose="qa", **kw)
    return s


def _fake_import(ws, project_id, folders, protein_fasta, rna_fasta, engine=None, accept_offsets=False, resolve=None):
    man = {"counts": {"included": 2, "found": 2, "excluded": 0, "unrecognised": 0}, "construct": {"protein_length": 3, "rna_length": 3},
           "runs": [{"run": "runA", "engine": "BOLTZ2", "n_structures": 1, "designated_execution": "runA#m_0", "designated_rule": "only structure of the run"},
                    {"run": "runB", "engine": "BOLTZ2", "n_structures": 1, "designated_execution": "runB#m_0", "designated_rule": "only structure of the run"}],
           "structures": [], "unrecognised_files": []}
    ws.projects[project_id] = {"dir": ws.out("project_" + project_id), "manifest": man}
    return {"status": "IMPORTED", "counts": man["counts"], "runs": man["runs"]}, EV.from_manifest(project_id, man, "tools/project_%s/manifest.json" % project_id)


def test_model_identifiers_never_rendered(tmp_path, monkeypatch):
    monkeypatch.setitem(T.FUNCS, "import_predictions", _fake_import)
    plan = {"goal": "UNSUPPORTED", "reference_supplied": False, "requested_capabilities": ["other"], "clarification_needed": None,
            "steps": [_step("import_predictions", project_id=MODEL_PID, folders=["run_001", "run_002"], protein_fasta="protein_sequence_001",
                            rna_fasta="rna_sequence_001", accept_offsets=False),
                      _step("explain_metric", metric_name=MODEL_METRIC)]}
    rd = tmp_path / "run"
    rec = ask.run(str(_task(tmp_path)), "Do the runs agree?", str(rd), llm.Stub([plan]))
    md = (rd / "answer.md").read_text()
    aj = (rd / "answer.json").read_text()
    for s in (MODEL_PID, MODEL_METRIC):
        assert s not in md and s not in aj, "model-chosen text %r reached the answer" % s
    assert "Project project_1:" in md and "<model-supplied value>" in md
    assert rec["gate_results"][0]["violations"] == []
    assert rec["project_ids"]["map"] == {"project_1": MODEL_PID}
    assert json.load(open(rd / "plan.json"))["steps"][0]["args"]["project_id"] == "project_1"
