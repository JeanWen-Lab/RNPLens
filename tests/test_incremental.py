"""0.4 Project-state track, Function 5: incremental projects (rnplens update).

Acceptance: an incremental update and a complete fresh recomputation on the same final inputs give identical
qualified numerical results (summary.json without creation times, and contacts_by_output.json)."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys

import pytest

import rnplens
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


def _fresh(root, inputs):
    code, vid = I.init_project(str(root), inputs, PS, RS, "BOLTZ2", "7K9D_example")
    assert code == 0
    return S.Project(str(root))


def _view(P, g="main"):
    return I.qualified_view(os.path.join(P.root, P.head()["analyses"][g]["dir"]))


def _update(P, add=(), remove=(), **kw):
    st = P.head()
    d = json.loads(json.dumps(st["declared"]))
    d["inputs"] = sorted((set(d["inputs"]) | set(add)) - set(remove))
    return I.run_pipeline(P, "update", declared=d, **kw)


# ---------------------------------------------------------------- acceptance: incremental == fresh
def test_add_modify_remove_runs_equal_fresh_recomputation(tmp_path):
    ins = M.two_runs(str(tmp_path / "in"))
    P = _fresh(tmp_path / "p", ins)
    v_first = P.head()
    first_dir = os.path.join(P.root, v_first["analyses"]["main"]["dir"])
    first_tree = S.tree_hashes(first_dir)

    # (1) add a third run (exec_B content as a new sample in a new folder)
    c = M.third_run(str(tmp_path / "in"))
    code, vid = _update(P, add=[c])
    st = P.head()
    assert code == 0 and st["status"] == "COMPLETE" and not st["analyses"]["main"]["reused"]
    assert st["changes_since_parent"]["runs"]["new"] == [c]
    F = _fresh(tmp_path / "fresh3", ins + [c])
    assert _view(P) == _view(F)
    assert _view(P)["summary"]["contacts"]["denominators"] == {"BOLTZ2": 3}
    R = json.load(open(os.path.join(P.root, st["update_report"]["json"])))
    assert R["i_candidate_composition"]["groups"]["main"]["added"] == ["exec_C#7K9D_model_1"]
    assert R["analyses"]["main"]["computation"] == "RECOMPUTED" and "inputs_sha256" in R["analyses"]["main"]["key_components_changed"]
    assert R["iii_analysis_contract_and_tool_version"]["config"] == [] and R["ii_correspondence_and_construct"]["construct"] == []

    # (2) modify one file: exec_A's RNA moves 2 A, so its contacts change
    before_a = _view(P)["contacts_by_output"]["BOLTZ2|exec_A#7K9D_model_0"]
    M.shift_chain(os.path.join(ins[0], M.MODEL), "B", 2.0)
    code, vid = _update(P)
    st = P.head()
    assert code == 0 and st["changes_since_parent"]["files"]["changed"] == [os.path.join(ins[0], M.MODEL)]
    assert _view(P)["contacts_by_output"]["BOLTZ2|exec_A#7K9D_model_0"] != before_a
    F2 = _fresh(tmp_path / "fresh_mod", ins + [c])
    assert _view(P) == _view(F2)
    R = json.load(open(os.path.join(P.root, st["update_report"]["json"])))
    assert R["i_candidate_composition"]["groups"]["main"]["changed"] == ["exec_A#7K9D_model_0"]

    # (3) remove the third run again
    code, vid = _update(P, remove=[c])
    st = P.head()
    assert code == 0 and st["changes_since_parent"]["runs"]["removed"] == [c]
    F3 = _fresh(tmp_path / "fresh_rm", ins)
    assert _view(P) == _view(F3)
    assert _view(P)["summary"]["contacts"]["denominators"] == {"BOLTZ2": 2}

    # earlier versions are preserved, never overwritten
    assert S.tree_hashes(first_dir) == first_tree
    assert [v["version"] for v in P.versions()] == ["v0001", "v0002", "v0003", "v0004", "v0005"]
    assert P.verify() == []
    dirs = [P.load(v)["analyses"]["main"]["dir"] for v in ("v0002", "v0003", "v0004", "v0005")]
    assert len(set(dirs)) == 4 and all(d.startswith("analyses/%s/" % v) for d, v in zip(dirs, ("v0002", "v0003", "v0004", "v0005")))


def test_returning_to_earlier_inputs_reuses_the_earlier_analysis(tmp_path):
    ins = M.two_runs(str(tmp_path / "in"))
    P = _fresh(tmp_path / "p", ins)
    c = M.third_run(str(tmp_path / "in"))
    _update(P, add=[c])
    code, vid = _update(P, remove=[c])
    a = P.head()["analyses"]["main"]
    assert code == 0 and a["reused"] and a["computed_in_version"] == "v0002" and a["dir"] == "analyses/v0002/main"
    idx = json.load(open(os.path.join(P.root, "analyses", vid, "index.json")))
    assert idx["groups"]["main"]["analysis_dir"] == "analyses/v0002/main" and idx["provenance"]["kind"] == "analysis_index"


def test_update_report_separates_the_three_kinds_of_change(tmp_path):
    ins = M.two_runs(str(tmp_path / "in"))
    P = _fresh(tmp_path / "p", ins)
    _update(P, add=[M.third_run(str(tmp_path / "in"))])
    st = P.head()
    R = json.load(open(os.path.join(P.root, st["update_report"]["json"])))
    html = open(os.path.join(P.root, st["update_report"]["html"])).read()
    for k in ("i_candidate_composition", "ii_correspondence_and_construct", "iii_analysis_contract_and_tool_version"):
        assert k in R and R[k]["evidence_id"].startswith(".rnplens/state/")
    assert any("not evidence of increased correctness or confidence" in s for s in R["statements"])
    assert any("contact-support distribution are descriptive" in s for s in R["statements"])
    assert "(i) Candidate composition" in html and "(ii) Correspondence and construct" in html
    assert "(iii) Analysis contract and tool version" in html
    assert trace.wording_audit(html) == [] and all(trace.wording_audit(s) == [] for s in R["statements"])
    d = R["descriptive_contact_support"]["main"]
    assert d["before"]["per_engine"]["BOLTZ2"]["structures"] == 2 and d["after"]["per_engine"]["BOLTZ2"]["structures"] == 3
    assert d["after"]["evidence_id"] == st["analyses"]["main"]["dir"] + "/summary.json#/contacts/rows"
    sm = json.load(open(os.path.join(P.root, st["analyses"]["main"]["dir"], "summary.json")))
    assert d["after"]["contacts_listed"] == len(sm["contacts"]["rows"])
    assert sum(d["after"]["per_engine"]["BOLTZ2"]["bins"].values()) == d["after"]["per_engine"]["BOLTZ2"]["contacts_listed"]
    assert R["provenance"]["kind"] == "update_report" and all(len(i.get("sha256") or i["content_sha256"]) == 64 for i in R["provenance"]["inputs"])
    g = R["i_candidate_composition"]["groups"]["main"]
    assert g["evidence_id"] == ".rnplens/state/v0003.json#/groups/main/counts"
    assert P.load("v0003")["groups"]["main"]["counts"]["included"] == g["included_after"]          # the pointer resolves
    assert d["after"]["per_engine"]["BOLTZ2"]["evidence_id"].endswith("summary.json#/contacts/denominators/BOLTZ2")
    # report between any two complete versions, on request
    r = _cli("update", P.root, "--report", "v0002", "v0003")
    assert r.returncode == 0 and os.path.exists(os.path.join(P.root, "analyses", "reports", "update_v0002_v0003.json"))


# ---------------------------------------------------------------- what is recomputed (each key component)
class FakeAnalyse:
    """Stands in for rnplens analyse in key tests: records calls, writes a minimal analysis directory."""

    def __init__(self):
        self.calls = []

    def __call__(self, project_dir, out, reference, nproc, diagnose):
        self.calls.append({"project": project_dir, "out": out, "reference": reference, "diagnose": diagnose})
        os.makedirs(os.path.join(out, "report"))
        man = json.load(open(os.path.join(project_dir, "manifest.json")))
        json.dump({"contacts": {"rows": [], "denominators": {}}, "n": len(man["structures"])},
                  open(os.path.join(out, "summary.json"), "w"))
        json.dump({}, open(os.path.join(out, "report", "contacts_by_output.json"), "w"))
        return 0


def _keyed(tmp_path, runs=None):
    fa = FakeAnalyse()
    ins = runs or M.two_runs(str(tmp_path / "in"))
    code, vid = I.init_project(str(tmp_path / "p"), ins, PS, RS, "BOLTZ2", "x", analyse_fn=fa)
    return S.Project(str(tmp_path / "p")), ins, fa


def _changed(P):
    R = json.load(open(os.path.join(P.root, P.head()["update_report"]["json"])))
    return R["analyses"]["main"]["key_components_changed"]


def test_nothing_changed_nothing_recomputed(tmp_path):
    P, ins, fa = _keyed(tmp_path)
    assert I.run_pipeline(P, "again", analyse_fn=fa)[0] == 0
    g, a = P.head()["groups"]["main"], P.head()["analyses"]["main"]
    assert len(fa.calls) == 1 and g["import_reused"] and a["reused"] and _changed(P) == []


def test_input_hash_change_recomputes(tmp_path):
    P, ins, fa = _keyed(tmp_path)
    with open(os.path.join(ins[1], M.MODEL), "a") as fh:
        fh.write("REMARK one byte more\n")
    I.run_pipeline(P, "edit", analyse_fn=fa)
    assert len(fa.calls) == 2 and not P.head()["groups"]["main"]["import_reused"] and "inputs_sha256" in _changed(P)


def test_unrelated_file_redoes_import_but_reuses_analysis(tmp_path):
    P, ins, fa = _keyed(tmp_path)
    open(os.path.join(ins[0], "README.txt"), "w").write("notes\n")
    I.run_pipeline(P, "readme", analyse_fn=fa)
    st = P.head()
    assert not st["groups"]["main"]["import_reused"] and st["analyses"]["main"]["reused"] and len(fa.calls) == 1
    assert st["changes_since_parent"]["files"]["new"] == [os.path.join(ins[0], "README.txt")]


def test_tool_version_change_recomputes(tmp_path, monkeypatch):
    P, ins, fa = _keyed(tmp_path)
    monkeypatch.setattr(rnplens, "__version__", "0.4.1+other")
    I.run_pipeline(P, "new tool", analyse_fn=fa)
    assert len(fa.calls) == 2 and not P.head()["groups"]["main"]["import_reused"] and "tool_version" in _changed(P)
    R = json.load(open(os.path.join(P.root, P.head()["update_report"]["json"])))
    assert R["iii_analysis_contract_and_tool_version"]["tool_version"] == {"before": "0.4.1", "after": "0.4.1+other"}


def test_metric_definition_change_recomputes_only_the_analysis(tmp_path, monkeypatch):
    P, ins, fa = _keyed(tmp_path)
    real = I.metric_definition()
    monkeypatch.setattr(I, "metric_definition", lambda: dict(real, contact_cutoff_A=4.5))
    I.run_pipeline(P, "new cutoff", analyse_fn=fa)
    assert len(fa.calls) == 2 and P.head()["groups"]["main"]["import_reused"] and _changed(P) == ["definition_sha256"]
    R = json.load(open(os.path.join(P.root, P.head()["update_report"]["json"])))
    assert "main" in R["iii_analysis_contract_and_tool_version"]["metric_definition"]


def test_configuration_change_recomputes_only_the_analysis(tmp_path):
    # r2: Diagnose is BLOCKED, so the configuration change exercised here is the reference (an analysis-contract
    # change); the assertions on what is recomputed are unchanged.
    P, ins, fa = _keyed(tmp_path)
    d = P.head()["declared"]
    assert d["config"]["diagnose"] is False                  # 0.4: Diagnose is never declared on
    ref = tmp_path / "reference_stand_in.cif"
    ref.write_text("data_x\n")                              # FakeAnalyse never reads it; only its hash enters the key
    d["config"]["reference"] = {"path": str(ref)}
    I.run_pipeline(P, "with reference", declared=d, analyse_fn=fa)
    assert len(fa.calls) == 2 and fa.calls[-1]["reference"] == str(ref) and _changed(P) == ["config_sha256"]
    R = json.load(open(os.path.join(P.root, P.head()["update_report"]["json"])))
    assert R["iii_analysis_contract_and_tool_version"]["config"][0]["key"] == "reference"
    d["nproc"] = 4                                       # not part of any result: nothing recomputed
    I.run_pipeline(P, "nproc", declared=d, analyse_fn=fa)
    assert len(fa.calls) == 2


def test_a_contract_asking_for_diagnose_is_refused_and_nothing_changes(tmp_path):
    from rnplens.capabilities import DIAGNOSE_BLOCKED_EXIT, DiagnoseBlocked
    P, ins, fa = _keyed(tmp_path)
    before = P.head()["version"]
    for value in (True, None):                           # declared on, or absent (absent used to mean on)
        d = P.head()["declared"]
        if value is None:
            d["config"].pop("diagnose")
        else:
            d["config"]["diagnose"] = value
        with pytest.raises(DiagnoseBlocked):
            I.run_pipeline(P, "diagnose", declared=d, analyse_fn=fa)
        assert P.head()["version"] == before and len(fa.calls) == 1
    with pytest.raises(DiagnoseBlocked):
        I.init_project(str(tmp_path / "new"), ins, PS, RS, diagnose=True, analyse_fn=fa)
    assert not (tmp_path / "new").exists()
    assert I.main([P.root, "--with-diagnose"]) == DIAGNOSE_BLOCKED_EXIT
    assert P.head()["version"] == before


def test_construct_change_redoes_the_import_and_never_reuses_results(tmp_path):
    P, ins, fa = _keyed(tmp_path)
    d = P.head()["declared"]; d["rna_sequence"] = RS[:-1]
    code, vid = I.run_pipeline(P, "other construct", declared=d, analyse_fn=fa)
    st = P.head()
    assert code == C.EXIT_NEEDS_ANSWER and not st["groups"]["main"]["import_reused"] and len(fa.calls) == 1
    assert st["groups"]["main"]["import_components"]["construct_sha256"] != P.load("v0002")["groups"]["main"]["import_components"]["construct_sha256"]
    assert {r["type"] for r in st["pending"]} == {"construct_mismatch"} and st["analyses"] == {}


def test_correspondence_change_recomputes(tmp_path):
    ins = M.two_runs(str(tmp_path / "in"))
    M.duplicate_protein_chain(os.path.join(ins[1], M.MODEL))
    P, ins, fa = _keyed(tmp_path, ins)
    qid = P.head()["pending"][0]["id"]
    C.answer(P, "1", "protein=A;rna=B"); I.run_pipeline(P, "resume", analyse_fn=fa)
    C.answer(P, qid, "protein=C;rna=B", revise=True, text="chain C is the biological copy")
    I.run_pipeline(P, "revised", analyse_fn=fa)
    assert len(fa.calls) == 2 and "correspondence_sha256" in _changed(P)
    R = json.load(open(os.path.join(P.root, P.head()["update_report"]["json"])))
    assert R["ii_correspondence_and_construct"]["chain_correspondence"]["main"]
    assert [x["status"] for x in R["ii_correspondence_and_construct"]["answers_invalidated_or_superseded"]] == ["SUPERSEDED"]


def test_selection_rule_change_recomputes(tmp_path):
    run = M.two_sample_run(str(tmp_path / "in"))
    P, ins, fa = _keyed(tmp_path, [run])
    qid = P.head()["pending"][0]["id"]
    C.answer(P, "1", "engine_files"); I.run_pipeline(P, "resume", analyse_fn=fa)
    C.answer(P, qid, "designate:exec_M#7K9D_model_0", revise=True); I.run_pipeline(P, "revised", analyse_fn=fa)
    assert len(fa.calls) == 2 and "selection_rule_sha256" in _changed(P)
    R = json.load(open(os.path.join(P.root, P.head()["update_report"]["json"])))
    (d,) = R["iii_analysis_contract_and_tool_version"]["selection_rules"]["main"]
    assert (d["before"]["designated_execution"], d["after"]["designated_execution"]) == ("exec_M#7K9D_model_1", "exec_M#7K9D_model_0")


# ---------------------------------------------------------------- failure, restart, determinism, missingness
@pytest.mark.parametrize("step", ["after_import", "after_analyse", "before_commit"])
def test_exception_mid_update_keeps_previous_version_current(tmp_path, monkeypatch, step):
    ins = M.two_runs(str(tmp_path / "in"))
    P = _fresh(tmp_path / "p", ins)
    head_bytes = open(P.head_path, "rb").read()
    prev_dir = os.path.join(P.root, P.head()["analyses"]["main"]["dir"])
    prev_tree = S.tree_hashes(prev_dir)
    c = M.third_run(str(tmp_path / "in"))

    def boom(s):
        if s == step:
            raise RuntimeError("injected failure at " + s)
    monkeypatch.setattr(I, "_hook", boom)
    with pytest.raises(RuntimeError):
        _update(P, add=[c])
    monkeypatch.setattr(I, "_hook", lambda s: None)
    assert open(P.head_path, "rb").read() == head_bytes and P.head_id() == "v0002" and P.verify() == []
    assert P.head()["status"] == "COMPLETE" and S.tree_hashes(prev_dir) == prev_tree
    assert not os.path.exists(os.path.join(P.dir, "LOCK"))
    code, vid = _update(P, add=[c])                       # the same update again completes
    assert code == 0 and vid == "v0003"
    st = P.head()
    assert st["groups"]["main"]["import_reused"] == (step != "after_import")
    assert st["analyses"]["main"]["reused"] == (step == "before_commit")
    assert _view(P) == _view(_fresh(tmp_path / "fresh", ins + [c]))


def test_process_exit_mid_update_then_resume_in_a_new_process(tmp_path):
    ins = M.two_runs(str(tmp_path / "in"))
    P = _fresh(tmp_path / "p", ins)
    c = M.third_run(str(tmp_path / "in"))
    code = ("import os, sys; from rnplens import incremental as I\n"
            "I._hook = lambda s: os._exit(9) if s == 'before_commit' else None\n"
            "I.capability_update(sys.argv[1], add=[sys.argv[2]])\n")
    r = subprocess.run([sys.executable, "-c", code, P.root, c], capture_output=True, text=True, env=dict(os.environ, MPLBACKEND="Agg"))
    assert r.returncode == 9
    assert S.Project(P.root).head_id() == "v0002" and os.path.exists(os.path.join(P.dir, "LOCK"))   # died holding it
    r = _cli("update", P.root, c)
    assert r.returncode == 0, r.stderr
    st = S.Project(P.root).head()
    assert st["version"] == "v0003" and st["analyses"]["main"]["reused"]            # completed work reused
    assert _view(S.Project(P.root)) == _view(_fresh(tmp_path / "fresh", ins + [c]))


def test_determinism_two_projects_same_inputs(tmp_path):
    ins = M.two_runs(str(tmp_path / "in"))
    A, B = _fresh(tmp_path / "a", ins), _fresh(tmp_path / "b", ins)
    sa, sb = A.head(), B.head()
    assert sa["analyses"]["main"]["key"] == sb["analyses"]["main"]["key"]
    assert sa["groups"]["main"]["import_key"] == sb["groups"]["main"]["import_key"]
    assert _view(A) == _view(B)
    vol = {"created_utc", "parent_sha256", "code_commit",
           "manifest_sha256", "summary_sha256"}          # hashes of files that carry their own creation time
    strip = lambda x: {k: strip(v) for k, v in x.items() if k not in vol} if isinstance(x, dict) else [strip(v) for v in x] if isinstance(x, list) else x
    assert strip(sa) == strip(sb)


def test_state_records_hashes_construct_correspondence_tool_config_and_selection(tmp_path):
    ins = M.two_runs(str(tmp_path / "in"))
    P = _fresh(tmp_path / "p", ins)
    st = P.head()
    f = os.path.join(ins[0], M.MODEL)
    from rnplens import provenance as pv
    assert st["inputs"]["files"][f] == pv.sha256_file(f)
    assert all(len(v) == 64 for v in st["inputs"]["files"].values())
    assert st["construct"]["declared"]["protein_sha256"] == C.seq_sha(PS) and st["construct"]["declared"]["rna_length"] == len(RS)
    assert st["correspondence"]["main"][f]["chains"][0][:3] == ["A", "protein", "EXACT"]
    assert st["tool_version"] == "0.4.1" and len(st["config_sha256"]) == 64
    assert st["selection_rules"]["main"]["runs"][0]["designated_rule"] == "only structure of the run"
    assert st["analyses"]["main"]["components"]["definition_sha256"] and st["analyses"]["main"]["summary_sha256"]


def test_missing_input_folder_is_a_removed_run(tmp_path):
    P, ins, fa = _keyed(tmp_path)
    shutil.rmtree(ins[1])
    code, vid = I.run_pipeline(P, "folder gone", analyse_fn=fa)
    st = P.head()
    assert code == 0 and st["inputs"]["missing_inputs"] == [ins[1]] and st["changes_since_parent"]["runs"]["removed"] == [ins[1]]
    assert len(fa.calls) == 2
    shutil.rmtree(ins[0])
    code, vid = I.run_pipeline(P, "all gone", analyse_fn=fa)
    assert code == C.EXIT_FAILED and P.head()["status"] == "FAILED" and P.head()["groups"]["main"]["status"] == "EMPTY"


def test_corrupted_state_refuses_update_and_changes_nothing(tmp_path):
    P, ins, fa = _keyed(tmp_path)
    p = os.path.join(P.state_dir, "v0001.json")
    os.chmod(p, 0o644); open(p, "a").write("\n")
    before = sorted(os.listdir(P.state_dir))
    r = _cli("update", P.root)
    assert r.returncode == I.EXIT_REFUSED and "changed after it was written" in r.stderr
    assert sorted(os.listdir(P.state_dir)) == before


def test_cli_init_update_status_versions(tmp_path):
    ins = M.two_runs(str(tmp_path / "in"))
    p = str(tmp_path / "p")
    r = _cli("update", p, "--init", *ins, "--protein-seq", M.PROTEIN_FASTA, "--rna-seq", M.RNA_FASTA,
             "--engine", "BOLTZ2", "--case-id", "7K9D_example")
    assert r.returncode == 0, r.stderr
    c = M.third_run(str(tmp_path / "in"))
    r = _cli("update", p, c)
    assert r.returncode == 0 and "before/after report" in r.stdout
    assert "COMPLETE" in _cli("update", p, "--status").stdout
    assert len(_cli("update", p, "--versions").stdout.strip().splitlines()) == 3
    assert _cli("update", str(tmp_path / "nothing")).returncode == I.EXIT_REFUSED
    r = _cli("update", p, os.path.join(p, "analyses"))
    assert r.returncode == I.EXIT_REFUSED and "must not contain each other" in r.stderr
    r = _cli("update", p, "--init", *ins, "--protein-seq", M.PROTEIN_FASTA, "--rna-seq", M.RNA_FASTA)
    assert r.returncode == I.EXIT_REFUSED and "already a managed project" in r.stderr


def test_reads_only_declared_inputs_and_the_project(tmp_path):
    """Data access: nothing outside the declared inputs, the project, the Python installation and the source tree
    (and matplotlib's own font cache) is opened, and an undeclared sibling folder is never read."""
    ins = M.two_runs(str(tmp_path / "in"))
    M.copy_run("exec_A", str(tmp_path / "in" / "not_declared"))
    third = M.third_run(str(tmp_path / "in2"))
    opened, args = set(), []
    flag = {"on": False}

    def hook(ev, a):
        if flag["on"] and ev == "open" and isinstance(a[0], str):
            opened.add(os.path.realpath(a[0]))
        if flag["on"] and ev == "subprocess.Popen":
            args.append([str(x) for x in a[1]])
    sys.addaudithook(hook)
    flag["on"] = True
    try:
        P = _fresh(tmp_path / "p", ins)
        _update(P, add=[third])
    finally:
        flag["on"] = False
    try:                                    # matplotlib is optional ('rnplens[html]'); its font cache only if installed
        import matplotlib
        mpl_cache = [matplotlib.get_cachedir()]
    except ImportError:
        mpl_cache = []
    allowed = [os.path.realpath(x) for x in [str(tmp_path), sys.prefix, sys.base_prefix, sys.exec_prefix,
                                             os.path.dirname(os.path.dirname(rnplens.__file__))] + mpl_cache + ["/dev"]]
    outside = sorted(p for p in opened if not any(p == r or p.startswith(r + os.sep) for r in allowed))
    assert outside == []
    assert not [p for p in opened if "not_declared" in p or p.startswith(os.path.realpath(M.EX))]
    for a in args:
        for x in a:
            if x.startswith(os.sep) and os.path.exists(x) and not os.path.realpath(x).startswith(os.path.realpath(sys.prefix)) \
                    and not os.path.realpath(x).startswith(os.path.realpath(sys.base_prefix)):
                assert any(os.path.realpath(x).startswith(r) for r in allowed), x


def test_capability_registered_as_descriptive():
    from rnplens import capabilities
    offered, _ = capabilities.available()
    c = [x for x in offered if x["id"] == "incremental_update"]
    assert c and c[0]["status"] == "DESCRIPTIVE" and capabilities.resolve(c[0]["call"]) is I.capability_update
    assert trace.wording_audit(c[0]["limits"]) == []


# ---------------------------------------------------------------- the worked example of docs/project_state.md
def test_worked_example_of_the_docs_page(tmp_path):
    ins = M.two_runs(str(tmp_path / "in"))
    oc = os.path.dirname(M.copy_run("exec_B", str(tmp_path / "in" / "other_construct")))
    M.truncate_rna(os.path.join(oc, M.MODEL), 2)
    p = str(tmp_path / "demo")
    r = _cli("update", p, "--init", *ins, oc, "--protein-seq", M.PROTEIN_FASTA, "--rna-seq", M.RNA_FASTA,
             "--engine", "BOLTZ2", "--case-id", "7K9D_example")
    assert r.returncode == 3 and "NEEDS_CLARIFICATION" in r.stdout
    r = _cli("clarify", p)
    assert r.returncode == 3 and "[1] construct_mismatch:" in r.stdout and "wrong folder" in r.stdout
    r = _cli("clarify", p, "--answer", "1", "exclude_run", "--text", "copied in by mistake")
    assert r.returncode == 0 and "COMPLETE" in r.stdout
    r = _cli("clarify", p, "--answer", "construct_mismatch:" + oc, "use_as_reference_set")
    assert r.returncode == 2 and "Use --revise" in r.stderr
    r = _cli("update", p)
    assert r.returncode == 0 and "(reused from v0004)" in r.stdout
    c = M.third_run(str(tmp_path / "in"))
    r = _cli("update", p, c)
    assert r.returncode == 0 and "before/after report" in r.stdout
    P = S.Project(p)
    R = json.load(open(os.path.join(p, P.head()["update_report"]["json"])))
    assert (R["from_version"], R["to_version"]) == ("v0005", "v0006")
    assert R["i_candidate_composition"]["groups"]["main"]["added"] == ["exec_C#7K9D_model_1"]
    assert R["analyses"]["main"]["computation"] == "RECOMPUTED"
    assert R["ii_correspondence_and_construct"]["construct"] == [] and R["iii_analysis_contract_and_tool_version"]["config"] == []
    d = R["descriptive_contact_support"]["main"]
    assert d["before"]["per_engine"]["BOLTZ2"]["contacts_listed"] == d["after"]["per_engine"]["BOLTZ2"]["contacts_listed"] == 47
    assert d["after"]["per_engine"]["BOLTZ2"]["bins"] == {"listed in every structure of the engine": 42,
                                                         "listed in at least half, not all": 3, "listed in fewer than half": 2}
    assert _view(P) == _view(_fresh(tmp_path / "fresh", ins + [c]))


def test_docs_page_present_and_passes_the_wording_audit():
    doc = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "project_state.md")
    if not os.path.exists(doc):
        pytest.skip("docs/ not present (installed without the source tree)")
    text = open(doc, encoding="utf-8").read()
    assert trace.wording_audit(text) == []
    for s in ("## Interpretation limits", "## Worked example", "DESCRIPTIVE", "not evidence of increased correctness or confidence"):
        assert s in text
