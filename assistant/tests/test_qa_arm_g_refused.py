"""QA agent-security regression: the hidden `--arm G` path (sealed-evaluation general-agent arm) is refused in 0.4.
Before the fix `python -m rnplens_assistant ask --arm G` ran baseline_codex.run, which sends real file names, the
target ID and reference file names (and raw tool results) to the model without the 0.4 redaction or policy."""
from rnplens_assistant import __main__ as M, codex_llm


def test_arm_g_is_refused_before_any_client(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(codex_llm, "CodexClient", lambda *a, **k: (_ for _ in ()).throw(AssertionError("client created")))
    task = tmp_path / "task"; task.mkdir()
    out = tmp_path / "RUN"
    assert M.main(["ask", "How close is each structure to the reference?", "--task", str(task), "--out", str(out), "--arm", "G"]) == 2
    assert not out.exists()
    assert "not available in RNPLens 0.4" in capsys.readouterr().err
