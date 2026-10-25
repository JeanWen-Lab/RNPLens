"""0.4 Project-state track, Function 3: typed clarification requests, recorded answers and resume (rnplens clarify)."""
import importlib.util
import json
import os
import subprocess
import sys

import pytest

from rnplens import clarify as C
from rnplens import incremental as I
from rnplens import state as S
from rnplens import trace

_spec = importlib.util.spec_from_file_location("state_fixtures", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fixtures_v04", "state", "make.py"))
M = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(M)
PS, RS = M.sequences()


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "rnplens", *args], capture_output=True, text=True,
                          env=dict(os.environ, MPLBACKEND="Agg"))


def _init(tmp_path, ins, **kw):
    code, vid = I.init_project(str(tmp_path / "p"), ins, PS, RS, "BOLTZ2", "7K9D_example", **kw)
    return code, S.Project(str(tmp_path / "p"))


def _main_cbo(P):
    st = P.head()
    return json.load(open(os.path.join(P.root, st["analyses"]["main"]["dir"], "report", "contacts_by_output.json")))


def _assert_nothing_chosen(P):
    st = P.head()
    assert st["status"] == "NEEDS_CLARIFICATION" and st["analyses"] == {}
    assert not os.path.exists(os.path.join(P.root, "analyses"))      # nothing analysed before the answer
    for r in st["pending"]:
        assert r["chosen_automatically"] is False and len(r["options"]) >= 2 and r["depends_on"]
        assert r["type"] in C.TYPES and all(o["id"] and o["label"] for o in r["options"])


# ---------------------------------------------------------------- construct mismatch
@pytest.fixture
def mismatch(tmp_path):
    ins = M.two_runs(str(tmp_path / "in"))
    M.truncate_rna(os.path.join(ins[1], M.MODEL), 2)
    code, P = _init(tmp_path, ins)
    return code, P, ins, tmp_path


def test_construct_mismatch_between_folders_asks_with_explicit_options(mismatch):
    code, P, ins, _ = mismatch
    assert code == C.EXIT_NEEDS_ANSWER
    _assert_nothing_chosen(P)
    (r,) = P.head()["pending"]
    assert r["type"] == "construct_mismatch" and r["id"] == "construct_mismatch:" + ins[1]
    assert [o["id"] for o in r["options"]] == ["exclude_run", "analyse_separately", "use_as_reference_set"]
    assert "wrong folder" in r["options"][0]["label"] and "intentional different constructs" in r["options"][1]["label"]
    assert r["detail"]["observed_construct"]["rna_length"] == len(RS) - 2
    assert set(r["depends_on"]) == {"run:" + ins[1], "construct:main"}


def test_exclude_run_resumes_and_matches_a_project_without_that_run(mismatch, tmp_path_factory):
    code, P, ins, _ = mismatch
    vid, rec = C.answer(P, "1", "exclude_run", text="exec_B was copied from another project")
    assert rec["text"] == "exec_B was copied from another project" and rec["depends_on"]["run:" + ins[1]]
    assert P.head()["status"] == "RESUME_PENDING"
    code, vid = I.run_pipeline(P, "resume")
    st = P.head()
    assert code == 0 and st["status"] == "COMPLETE" and st["exclusions"]["runs"] == [ins[1]]
    alone = tmp_path_factory.mktemp("alone")
    code2, vid2 = I.init_project(str(alone / "p"), [ins[0]], PS, RS, "BOLTZ2", "7K9D_example")
    Q = S.Project(str(alone / "p"))
    assert I.qualified_view(os.path.join(P.root, st["analyses"]["main"]["dir"])) == \
        I.qualified_view(os.path.join(Q.root, Q.head()["analyses"]["main"]["dir"]))
    # never asked again while the answer applies; the analysis is reused
    code, vid = I.run_pipeline(P, "again")
    assert code == 0 and P.head()["pending"] == [] and P.head()["analyses"]["main"]["reused"]


def test_analyse_separately_makes_two_construct_groups(mismatch):
    code, P, ins, _ = mismatch
    out = C.capability_answer(P.root, "1", "analyse_separately", text="exec_B used the shorter RNA on purpose")
    assert out["exit"] == 0
    st = P.head()
    groups = sorted(st["analyses"])
    assert groups[1] == "main" and groups[0].startswith("construct_") and all(a["status"] == "COMPLETE" for a in st["analyses"].values())
    other = st["analyses"][groups[0]]
    Sm = json.load(open(os.path.join(P.root, other["dir"], "summary.json")))
    assert Sm["construct"]["rna_length"] == len(RS) - 2 and Sm["inventory"]["counts"]["included"] == 1
    assert st["construct"]["groups"][groups[0]]["rna_length"] == len(RS) - 2
    assert st["construct"]["main"]["sha256"] == st["construct"]["declared"]["sha256"]


def test_answering_again_with_a_contradictory_option_is_refused(mismatch):
    code, P, ins, _ = mismatch
    qid = P.head()["pending"][0]["id"]
    C.answer(P, "1", "exclude_run")
    I.run_pipeline(P, "resume")
    head = P.head_id()
    with pytest.raises(S.StateError) as ex:                       # not pending any more
        C.answer(P, qid, "use_as_reference_set")
    assert "--revise" in str(ex.value)
    r = _cli("clarify", P.root, "--answer", qid, "use_as_reference_set")
    assert r.returncode == C.EXIT_REFUSED and "refused" in r.stderr and P.head_id() == head
    assert P.decisions()[qid]["option"] == "exclude_run"


def test_reference_set_then_the_other_run_is_asked_about(mismatch):
    code, P, ins, _ = mismatch
    C.answer(P, "1", "use_as_reference_set", text="the FASTA I declared is the old construct")
    code, vid = I.run_pipeline(P, "resume")
    st = P.head()
    assert code == C.EXIT_NEEDS_ANSWER and st["construct"]["main"]["rna_length"] == len(RS) - 2
    (r,) = st["pending"]
    assert r["id"] == "construct_mismatch:" + ins[0]
    assert "use_as_reference_set" not in [o["id"] for o in r["options"]]       # one reference set at a time
    C.answer(P, "1", "exclude_run")
    code, vid = I.run_pipeline(P, "resume")
    st = P.head()
    assert code == 0 and st["status"] == "COMPLETE" and st["exclusions"]["runs"] == [ins[0]]
    assert sorted(st["analyses"]) == ["main"]


def test_changed_input_invalidates_the_answer_and_asks_again(mismatch):
    code, P, ins, _ = mismatch
    C.answer(P, "1", "exclude_run")
    I.run_pipeline(P, "resume")
    with open(os.path.join(ins[1], M.MODEL), "a") as fh:
        fh.write("REMARK edited\n")
    code, vid = I.run_pipeline(P, "after an edit")
    st = P.head()
    assert code == C.EXIT_NEEDS_ANSWER and st["pending"][0]["id"] == "construct_mismatch:" + ins[1]
    (inv,) = st["invalidated_in_this_version"]
    assert inv["option"] == "exclude_run" and inv["changed"][0]["key"] == "run:" + ins[1]
    assert st["decisions"]["construct_mismatch:" + ins[1]]["status"] == "INVALIDATED"
    assert [r["status"] for r in st["decision_log"]] == ["ACTIVE", "INVALIDATED"]


# ---------------------------------------------------------------- competing chain mappings
def test_competing_chain_mappings_are_never_auto_chosen(tmp_path):
    ins = M.two_runs(str(tmp_path / "in"))
    M.duplicate_protein_chain(os.path.join(ins[1], M.MODEL))
    code, P = _init(tmp_path, ins)
    assert code == C.EXIT_NEEDS_ANSWER
    _assert_nothing_chosen(P)
    (r,) = P.head()["pending"]
    assert r["type"] == "chain_mapping"
    assert [o["id"] for o in r["options"]] == ["protein=A;rna=B", "protein=C;rna=B", "exclude_files"]
    out = C.capability_answer(P.root, "1", "protein=A;rna=B", text="chain C is a crystallographic copy")
    assert out["exit"] == 0
    st = P.head()
    man = json.load(open(os.path.join(P.root, st["groups"]["main"]["import_dir"], "manifest.json")))
    s = [x for x in man["structures"] if x["path"].startswith(ins[1])][0]
    assert [c["status"] for c in s["chains"]] == ["EXACT", "NOT_IN_MAPPING", "EXACT"] and s["derived"]
    assert open(s["path"], "rb").read() != open(s["used_path"], "rb").read()       # original untouched, copy used
    # parity: chain C is far away, so the mapped copy has exactly the contacts of the unmodified example
    ref = json.load(open(os.path.join(M.EX, "expected_output", "B1_report_7K9D", "contacts_by_output.json"))) \
        if os.path.exists(os.path.join(M.EX, "expected_output", "B1_report_7K9D", "contacts_by_output.json")) else None
    cbo = _main_cbo(P)
    clean = M.two_runs(str(tmp_path / "clean"))
    code, vid = I.init_project(str(tmp_path / "pc"), clean, PS, RS, "BOLTZ2", "7K9D_example")
    assert cbo == _main_cbo(S.Project(str(tmp_path / "pc")))
    if ref is not None:
        assert {k.split("#")[0]: v for k, v in cbo.items()} == ref      # rc3 expected output labels runs without #sample


# ---------------------------------------------------------------- ambiguous engine designation
def test_multiple_confidence_files_ask_for_the_designated_structure(tmp_path):
    run = M.two_sample_run(str(tmp_path / "in"))
    code, P = _init(tmp_path, [run])
    assert code == C.EXIT_NEEDS_ANSWER
    _assert_nothing_chosen(P)
    (r,) = P.head()["pending"]
    assert r["type"] == "engine_designation" and "confidence_7K9D_model_0_rerun.json" in r["question"]
    assert [o["id"] for o in r["options"]] == ["engine_files", "designate:exec_M#7K9D_model_0",
                                               "designate:exec_M#7K9D_model_1", "none"]
    C.answer(P, "1", "designate:exec_M#7K9D_model_0", text="model_0 is the engine's top sample")
    assert I.run_pipeline(P, "resume")[0] == 0
    man = json.load(open(os.path.join(P.root, P.head()["groups"]["main"]["import_dir"], "manifest.json")))
    assert [s["designated"] for s in man["structures"]] == [True, False]
    assert man["runs"][0]["designated_rule"] == "chosen in a recorded answer"


def test_tied_scores_ask_and_none_is_an_option(tmp_path):
    run = M.two_sample_run(str(tmp_path / "in"), extra_confidence=False, tie=True)
    code, P = _init(tmp_path, [run])
    (r,) = P.head()["pending"]
    assert "share the top" in r["question"] and r["options"][-1]["id"] == "none"
    C.answer(P, "1", "none")
    assert I.run_pipeline(P, "resume")[0] == 0
    man = json.load(open(os.path.join(P.root, P.head()["groups"]["main"]["import_dir"], "manifest.json")))
    assert not any(s["designated"] for s in man["structures"])


def test_cross_question_contradiction_is_refused(tmp_path):
    """One run with a designation question and a construct question pending together."""
    run = M.two_sample_run(str(tmp_path / "in"))
    M.truncate_rna(os.path.join(run, "7K9D_model_1.pdb"), 2)
    code, P = _init(tmp_path, [run])
    ids = sorted(r["type"] for r in P.head()["pending"])
    assert ids == ["construct_mismatch", "engine_designation"]
    des = next(r for r in P.head()["pending"] if r["type"] == "engine_designation")
    con = next(r for r in P.head()["pending"] if r["type"] == "construct_mismatch")
    C.answer(P, des["id"], "designate:exec_M#7K9D_model_0", text="keep this run")
    head = P.head_id()
    with pytest.raises(S.ContradictoryAnswer) as ex:
        C.answer(P, con["id"], "exclude_run")
    assert des["id"] in str(ex.value) and P.head_id() == head
    C.answer(P, con["id"], "exclude_differing_files")
    assert I.run_pipeline(P, "resume")[0] == 0


# ---------------------------------------------------------------- the importer's own questions, reused
def test_importer_question_reused_and_answered_per_file(tmp_path):
    ins = M.two_runs(str(tmp_path / "in"))
    M.renumber_protein(os.path.join(ins[1], M.MODEL))
    code, P = _init(tmp_path, ins)
    (r,) = P.head()["pending"]
    assert r["type"] == "importer_question" and r["id"] == "derived:" + os.path.join(ins[1], M.MODEL)
    assert r["detail"]["importer_question"]["options"] == ["--accept-derived"]       # the importer's own dict
    assert [o["id"] for o in r["options"]] == ["accept", "exclude_file"]
    C.answer(P, "1", "exclude_file")
    assert I.run_pipeline(P, "resume")[0] == 0
    man = json.load(open(os.path.join(P.root, P.head()["groups"]["main"]["import_dir"], "manifest.json")))
    assert [s["verdict"] for s in man["structures"]] == ["INCLUDED", "EXCLUDED_BY_USER"]


def test_importer_question_dicts_of_every_kind_become_typed_requests():
    ctx = {"files": {"/r/a.cif": "1" * 64, "/r/top.cif": "2" * 64}, "constructs": {}}
    qs = [{"id": "engine:/r", "question": "which engine?", "options": ["AF3", "RF3"]},
          {"id": "chains:/r/a.cif", "question": "exclude?", "options": ["exclude_file"]},
          {"id": "derived:/r/a.cif", "question": "derived?", "options": ["--accept-derived"]},
          {"id": "top:/r/top.cif", "question": "ignore?", "options": ["ignore"]}]
    rs = C.from_importer(qs, "main", ctx)
    assert [r["type"] for r in rs] == ["importer_question"] * 4
    assert [o["id"] for o in rs[0]["options"]] == ["AF3", "RF3"] and rs[0]["options"][0]["apply"] == {"importer_answers": {"engine:/r": "AF3"}}
    assert list(rs[0]["depends_on"]) == ["run:/r"] and rs[1]["depends_on"] == {"file:/r/a.cif": "1" * 64}
    assert rs[3]["depends_on"]["file:/r/top.cif"] == "2" * 64
    assert all(r["question"] == q["question"] for r, q in zip(rs, qs))


# ---------------------------------------------------------------- CLI, restart, wording
def test_cli_list_answer_no_resume_then_resume_in_a_new_process(mismatch):
    code, P, ins, _ = mismatch
    r = _cli("clarify", P.root)
    assert r.returncode == C.EXIT_NEEDS_ANSWER and "[1] construct_mismatch:" in r.stdout and "exclude_run" in r.stdout
    assert json.loads(_cli("clarify", P.root, "--json").stdout)[0]["type"] == "construct_mismatch"
    r = _cli("clarify", P.root, "--answer", "1", "no_such_option")
    assert r.returncode == C.EXIT_REFUSED and "not an option" in r.stderr
    r = _cli("clarify", P.root, "--answer", "1", "exclude_run", "--text", "wrong folder", "--no-resume")
    assert r.returncode == 0 and S.Project(P.root).head()["status"] == "RESUME_PENDING"
    r = _cli("clarify", P.root, "--resume")
    assert r.returncode == 0, r.stderr
    assert S.Project(P.root).head()["status"] == "COMPLETE"
    h = _cli("clarify", P.root, "--history")
    assert "exclude_run" in h.stdout and "wrong folder" in h.stdout
    assert _cli("clarify", P.root).returncode == 0


def test_clarify_refuses_a_directory_that_is_not_a_project(tmp_path):
    r = _cli("clarify", str(tmp_path))
    assert r.returncode == C.EXIT_REFUSED and "not a managed project" in r.stderr


def test_question_and_option_text_passes_the_wording_audit(mismatch, tmp_path):
    code, P, ins, _ = mismatch
    texts = [r["question"] for r in P.head()["pending"]] + [o["label"] for r in P.head()["pending"] for o in r["options"]]
    run = M.two_sample_run(str(tmp_path / "in2"))
    code, vid = I.init_project(str(tmp_path / "p2"), [run], PS, RS, "BOLTZ2", "x")
    texts += [r["question"] for r in S.Project(str(tmp_path / "p2")).head()["pending"]]
    texts += [c["limits"] for c in C.CAPABILITIES]
    assert all(trace.wording_audit(t) == [] for t in texts)


def test_capability_registered_as_descriptive():
    from rnplens import capabilities
    offered, _ = capabilities.available()
    c = [x for x in offered if x["id"] == "clarify_and_resume"]
    assert c and c[0]["status"] == "DESCRIPTIVE" and capabilities.resolve(c[0]["call"]) is C.capability_answer
