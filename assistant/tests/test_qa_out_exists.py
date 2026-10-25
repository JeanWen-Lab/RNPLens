"""QA agent-security regression (qa/agent-security): `python -m rnplens_assistant ask|replay --out DIR` must refuse an
existing DIR (exit 2) before any Codex client is created, and leave the existing result unchanged. Before the fix the
CLI used os.makedirs(exist_ok=True) and overwrote answer.md / run_record.json / evidence.jsonl of a completed run."""
import json
import os

import pytest

from rnplens_assistant import __main__ as M, codex_llm


def _existing(tmp_path):
    out = tmp_path / "RUN"
    out.mkdir()
    (out / "answer.md").write_text("previous answer\n")
    return out


def test_ask_refuses_existing_out_before_any_client(tmp_path, monkeypatch, capsys):
    def no_client(*a, **k):
        raise AssertionError("a Codex client was created for an existing --out")
    monkeypatch.setattr(codex_llm, "CodexClient", no_client)
    task = tmp_path / "task"
    task.mkdir()
    out = _existing(tmp_path)
    assert M.main(["ask", "Do the runs agree?", "--task", str(task), "--out", str(out)]) == 2
    assert (out / "answer.md").read_text() == "previous answer\n"
    assert sorted(os.listdir(out)) == ["answer.md"]
    assert "already exists" in capsys.readouterr().err


def test_replay_refuses_existing_out(tmp_path, capsys):
    task = tmp_path / "task"
    task.mkdir()
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"goal": "AGREEMENT", "reference_supplied": False, "requested_capabilities": [], "steps": []}))
    out = _existing(tmp_path)
    assert M.main(["replay", str(plan), "--task", str(task), "--out", str(out)]) == 2
    assert sorted(os.listdir(out)) == ["answer.md"]
    assert "already exists" in capsys.readouterr().err


def test_replay_into_a_new_out_still_works(tmp_path, capsys):
    task = tmp_path / "task"
    task.mkdir()
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"goal": "AGREEMENT", "reference_supplied": False, "requested_capabilities": [], "steps": []}))
    assert M.main(["replay", str(plan), "--task", str(task), "--out", str(tmp_path / "NEW")]) == 0
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["matches"] is None
