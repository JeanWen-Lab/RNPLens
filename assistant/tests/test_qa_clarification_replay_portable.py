"""QA agent-security regression (fix #5): the evidence of a run whose import stopped with questions must not contain
absolute paths, so an LLM-free replay in a relocated task reproduces the evidence hash. Before the fix the
IDENTITY_UNRESOLVED record's value held the absolute file path from QUESTIONS.json (replay relocated: matches false)."""
import json
import os
import shutil

from rnplens_assistant import evidence as EV, tools as T


def _task(base):
    t = base / "task"
    (t / "run_B").mkdir(parents=True); (t / "run_B" / "m_0.pdb").write_text("END\n")
    (t / "protein.fasta").write_text(">p\nMKV\n"); (t / "rna.fasta").write_text(">r\nGGA\n")
    return t


def _fake_rn(ws, args, log):
    out = args[args.index("--out") + 1]
    os.makedirs(out)
    f = os.path.join(ws.task_dir, "run_B", "m_0.pdb")
    json.dump({"questions": [{"id": "derived:" + f, "question": "%s needs a derived copy: renumber chain(s) A. Accept with --accept-derived." % f,
                              "options": ["--accept-derived"]}]}, open(os.path.join(out, "QUESTIONS.json"), "w"))
    return 3, "", ""


def _import(base, monkeypatch):
    monkeypatch.setattr(T, "_rn", _fake_rn)
    t = _task(base)
    ws = T.Workspace(str(t), str(base / "run"))
    res, recs = T.import_predictions(ws, "project_1", ["run_B"], "protein.fasta", "rna.fasta")
    st = EV.Store(); st.add(recs, 0)
    return res, st


def test_clarification_evidence_is_location_independent(tmp_path, monkeypatch):
    r1, s1 = _import(tmp_path / "here", monkeypatch)
    r2, s2 = _import(tmp_path / "moved" / "elsewhere", monkeypatch)
    assert r1["status"] == "NEEDS_CONFIRMATION"
    for st, base in ((s1, tmp_path / "here"), (s2, tmp_path / "moved" / "elsewhere")):
        rec = st.records[0]
        assert rec["state"] == "IDENTITY_UNRESOLVED" and str(base) not in json.dumps(rec)
        assert rec["value"].startswith("run_B/m_0.pdb needs a derived copy")
    assert s1.content_hash() == s2.content_hash()
