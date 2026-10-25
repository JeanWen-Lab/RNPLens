"""0.4 r3 (owner item 4, menu part): in the question menu a BLOCKED capability exits with code 5; a function that ran
and refused or failed (including a refused clarification answer) stays exit code 4. Before r3 a menu function that
raised DiagnoseBlocked was not caught (traceback), and a result with status BLOCKED was reported as success."""
import json
import os

import pytest

from rnplens import assist, capabilities, clarify, importer
from rnplens import incremental as I
from rnplens import state as S

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
RF, RB = os.path.join(EX, "reference_free", "report_7K9D"), os.path.join(EX, "reference_based")
pytestmark = pytest.mark.skipif(not os.path.isdir(RF), reason="examples/ not present")


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    t = tmp_path_factory.mktemp("menu")
    PS = importer.read_sequence_arg(os.path.join(RB, "7K9D_protein.fasta"))
    RS = importer.read_sequence_arg(os.path.join(RB, "7K9D_rna.fasta"))
    assert importer.run([os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B")], PS, RS, str(t / "p"), "7K9D_example", "BOLTZ2") == 0
    return str(t / "p")


def _menu_with(monkeypatch, fn, cap_id="synthetic_function"):
    cap = {"id": cap_id, "menu": "C", "label": "synthetic function", "status": "DESCRIPTIVE", "needs": [],
           "call": "x:y", "limits": "test only", "module": "test"}
    real = assist.build_menu
    monkeypatch.setattr(assist, "build_menu", lambda offered=None, missing=None: real([cap], []))
    monkeypatch.setattr(capabilities, "resolve", lambda call: fn)


def _raise_blocked(**kw):
    raise capabilities.DiagnoseBlocked("the declared analysis contract asks for Diagnose")


@pytest.mark.parametrize("fn", [_raise_blocked, lambda **kw: {"status": "BLOCKED", "message": "blocked in 0.4", "outputs": []},
                                lambda **kw: {"status": "DIAGNOSE_BLOCKED", "message": "blocked in 0.4", "outputs": []}])
def test_a_blocked_capability_exits_5(monkeypatch, project, capsys, fn):
    _menu_with(monkeypatch, fn)
    assert assist.main(["--project", project, "--item", "C"]) == assist.EXIT_BLOCKED == 5
    assert "BLOCKED" in capsys.readouterr().err


@pytest.mark.parametrize("status", ["REFUSED", "FAILED", "ERROR", "NEEDS_CLARIFICATION"])
def test_a_refusal_or_failure_stays_exit_4(monkeypatch, project, status):
    _menu_with(monkeypatch, lambda **kw: {"status": status, "message": "the function refused the input", "outputs": []})
    assert assist.main(["--project", project, "--item", "C"]) == 4


def test_a_raised_refusal_is_exit_4(monkeypatch, project):
    def refuse(**kw):
        raise S.StateError("the answer contradicts an earlier answer")
    _menu_with(monkeypatch, refuse)
    assert assist.main(["--project", project, "--item", "C"]) == 4


def test_success_is_still_0(monkeypatch, project):
    _menu_with(monkeypatch, lambda **kw: {"status": "OK", "outputs": []})
    assert assist.main(["--project", project, "--item", "C"]) == 0


def test_interactive_menu_reports_blocked_and_stays_open(monkeypatch, project):
    _menu_with(monkeypatch, _raise_blocked)
    answers = iter(["C", "q"]); lines = []
    assert assist.main(["--project", project], ask=lambda prompt: next(answers), out=lines.append) == 0
    assert any(l.startswith("  BLOCKED:") and "DIAGNOSE_BLOCKED" in l for l in lines)


class _FakeAnalyse:
    def __call__(self, project_dir, out, reference, nproc, diagnose):
        os.makedirs(os.path.join(out, "report"))
        man = json.load(open(os.path.join(project_dir, "manifest.json")))
        json.dump({"schema": "fake", "steps": {}, "structures": len(man["structures"])}, open(os.path.join(out, "summary.json"), "w"))
        json.dump({}, open(os.path.join(out, "report", "contacts_by_output.json"), "w"))
        json.dump({}, open(os.path.join(out, "report", "result.json"), "w"))
        return 0


def test_clarify_and_resume_on_a_diagnose_contract_is_exit_5_and_a_refused_answer_is_4(monkeypatch, tmp_path, project):
    """The real clarify function (clarify.capability_answer -> incremental.run_pipeline) on a real managed project whose
    contract still asks for Diagnose, run through the menu's capability machinery. The registered clarify capability has
    no menu letter and declares an input ('project_state') its function does not take, so it is wrapped here with the
    project bound (records/release/DOCS_AUDIT.md section 7 lists that registry mismatch)."""
    PS = importer.read_sequence_arg(os.path.join(RB, "7K9D_protein.fasta"))
    RS = importer.read_sequence_arg(os.path.join(RB, "7K9D_rna.fasta"))
    root = str(tmp_path / "mp")
    I.init_project(root, [os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B")], PS, RS, engine="BOLTZ2", analyse_fn=_FakeAnalyse())
    P = S.Project(root)
    d = P.head()["declared"]; d["config"]["diagnose"] = True
    P.commit({"declared": d}, "test: a contract recorded before r2 that still asks for Diagnose")
    before = P.head_id()
    # 1) a question that is not pending: the clarify function refuses (StateError) -> 4, nothing changes
    _menu_with(monkeypatch, lambda **kw: clarify.capability_answer(root, "no_such_question", "x"), cap_id="clarify_and_resume")
    assert assist.main(["--project", project, "--item", "C"]) == 4 and P.head_id() == before
    # 2) an accepted answer whose resume reaches the Diagnose block -> 5 (answer() records; the resume is the real one)
    monkeypatch.setattr(clarify, "answer", lambda project_, q, o, text=None, revise=False: (P.head_id(), {"id": q, "option": o}))
    _menu_with(monkeypatch, lambda **kw: clarify.capability_answer(root, "q1", "o1"), cap_id="clarify_and_resume")
    assert assist.main(["--project", project, "--item", "C"]) == 5 and P.head_id() == before
