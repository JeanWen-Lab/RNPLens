"""QA agent-security regression (fix #6): user-typed text is redacted and checked before anything is sent.
Before the fix the planner sent an absolute path, a case variant of a folder name ('RUN_B') and the name of an
undeclared reference typed in the question verbatim, and had no pre-send gate."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_followup_common import clone, make_project  # noqa: E402

from rnplens_assistant import ask, consent, followup as F, llm, redact as RD  # noqa: E402

NONE = {"goal": "UNSUPPORTED", "reference_supplied": False, "requested_capabilities": ["other"], "clarification_needed": None, "steps": []}


def _task(tmp):
    t = tmp / "task"
    for r in ("run_A", "run_B"):
        (t / r).mkdir(parents=True); (t / r / "m_0.pdb").write_text("END\n")
    (t / "protein.fasta").write_text(">p\nMKV\n"); (t / "rna.fasta").write_text(">r\nGGA\n")
    (t / "secret_ref_24BR.cif").write_text("data_x\n")                     # undeclared (restricted) reference
    (t / "task.json").write_text(json.dumps({"reference_files": []}))
    return t


def _capture():
    seen = []
    return seen, llm.Stub([lambda user: seen.append(user) or NONE, lambda user: seen.append(user) or NONE])


def test_planner_question_is_redacted(tmp_path):
    t = _task(tmp_path)
    q = "Do %s/run_A and RUN_B agree? Compare with /etc/hosts and with secret_ref_24BR.cif (also SECRET_REF_24BR)." % t
    seen, stub = _capture()
    rec = ask.run(str(t), q, str(tmp_path / "run"), stub)
    assert len(seen) == 1
    u = seen[0]
    for bad in (str(t), "/etc/hosts", "RUN_B", "run_A", "secret_ref", "SECRET_REF"):
        assert bad not in u, bad
    assert "Do run_001 and run_002 agree?" in u and "<path>" in u and u.count(RD.UNDISCLOSED) == 2
    kinds = {r["kind"] for r in rec["redaction"]["question_redactions"]}
    assert kinds == {"absolute_path", "real_name", "undisclosed_file_name"}


def test_gate_refuses_when_redaction_misses(tmp_path, monkeypatch):
    t = _task(tmp_path)
    monkeypatch.setattr(RD, "scrub_user_text", lambda text, task_dir, m: (text, []))    # simulate a missed redaction
    seen, stub = _capture()
    rd = tmp_path / "run"
    rec = ask.run(str(t), "Is /home/someone/data/run_B right?", str(rd), stub)
    assert seen == [] and stub.calls == [] and rec["privacy_refusal"]
    assert "Not sent" in (rd / "answer.md").read_text()


def test_question_without_names_is_byte_identical(tmp_path):
    t = _task(tmp_path)
    q = "Do the two runs agree on where the protein contacts the RNA?"
    user, m = RD.planner_user(q, str(t), {"reference_files": []})
    assert user.startswith("Question:\n%s\n\nTask inputs" % q) and m.question_redactions == []


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    b = tmp_path_factory.mktemp("fu_presend")
    make_project(str(b / "x"))
    return str(b / "x")


def test_followup_question_is_redacted(base, tmp_path):
    P, A = clone(base, str(tmp_path / "w"))
    consent.opt_in(P, "--yes")
    q = "Which contacts in RNA 13-23 are found only in EXEC_B, as listed in %s/region_13-23?" % A
    rec = F.run(P, A, q, mode="codex", yes=True, out=lambda *x: None, agent_status=lambda: (True, []),
                client_factory=lambda: llm.Stub([{"follow_up": "none", "args": F._blank(), "rationale": "x"}]))
    assert rec["stop"] is None, rec["stop"]
    sent = rec["payloads"][0]["text"]
    assert "EXEC_B" not in sent and "exec_B" not in sent and A not in sent and "<path>" in sent
    assert {r["kind"] for r in rec["question_redactions"]} >= {"absolute_path", "real_name"}


def test_undeclared_reference_cif_does_not_redact_or_block_the_word_reference(tmp_path):
    t = _task(tmp_path)
    (t / "reference.cif").write_text("data_x\n")                        # undeclared: its stem 'reference' is a common word
    seen, stub = _capture()
    rec = ask.run(str(t), "How accurate are these structures compared with the experimental reference?", str(tmp_path / "run"), stub)
    assert len(seen) == 1 and "compared with the experimental reference?" in seen[0] and "privacy_refusal" not in rec
    assert "reference.cif" not in seen[0]
