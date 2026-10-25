"""rnplens assist: the question menu over fake registry capabilities (the real functions belong to other tracks)."""
import builtins
import json
import os
import shutil
import socket
import subprocess
import sys
import types

import pytest

from rnplens import assist, capabilities, importer, provenance as pv, trace

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")
PS = os.path.join(EX, "reference_based", "7K9D_protein.fasta")
RS = os.path.join(EX, "reference_based", "7K9D_rna.fasta")
LABELS = ["Compare binding surfaces and contacts", "Inspect contacts in an RNA region",
          "Compare two prediction runs or model versions", "Explain an existing result",
          "Group distinct binding hypotheses", "Export results and Methods"]
CALLS = []


def region_contacts(project, analysis, rna_start, rna_end, runs, protein_range=None):
    """Fake deterministic function: writes one JSON with evidence IDs and returns its path."""
    CALLS.append({"fn": "region", "project": project, "analysis": analysis, "rna": (rna_start, rna_end), "runs": runs,
                  "protein_range": protein_range})
    rel = "region_%d-%d/region.json" % (rna_start, rna_end)
    rows = [{"rna_position": r, "runs": runs, "evidence_id": pv.evidence_id(rel, "/rows/%d" % i)} for i, r in enumerate(range(rna_start, rna_end + 1))]
    pv.atomic_write_json(os.path.join(analysis, rel), {"provenance": pv.block("fake_region", [], "fake", {}), "rows": rows})
    return {"outputs": [os.path.join(analysis, rel)]}


def explain(**kw):
    CALLS.append({"fn": "explain", **kw})
    return {"outputs": [{"path": "explain/x.json", "evidence_ids": [kw["evidence_id"]]}]}


def grouping(project, analysis):
    CALLS.append({"fn": "grouping"})
    return {"outputs": [], "evidence_ids": ["groups/groups.json#/groups/0"]}


def export_two(project):
    CALLS.append({"fn": "export_two"})
    return {"outputs": []}


def needs_unknown(project, other):
    CALLS.append({"fn": "unknown", "other": other})
    return {"outputs": []}


FAKES = {
    "fake_region": [{"id": "region_contacts", "menu": "B", "label": "Contacts in an RNA region", "status": "QUALIFIED",
                     "needs": ["project", "analysis", "rna_range", "protein_range?", "two_runs"],
                     "call": "test_assist:region_contacts", "limits": "Contacts are those of Report's per-structure records."}],
    "fake_explain": [{"id": "explain_value", "menu": "D", "label": "Explain a value", "status": "DESCRIPTIVE",
                      "needs": ["project", "analysis", "evidence_id"], "call": "test_assist:explain", "limits": "Traces only."}],
    "fake_grouping": [{"id": "grouping", "menu": "E", "label": "Binding hypotheses", "status": "EXPERIMENTAL",
                       "needs": ["project", "analysis"], "call": "test_assist:grouping", "limits": "Groups are not ordered."}],
    "fake_compare": [{"id": "run_compare", "menu": "C", "label": "Compare runs", "status": "UNAVAILABLE",
                      "reason": "test reason: not qualified", "needs": ["two_runs"], "call": "test_assist:region_contacts"}],
    "fake_export": [{"id": "export_a", "menu": "F", "label": "Export one", "status": "DESCRIPTIVE", "needs": ["project", "other"],
                     "call": "test_assist:needs_unknown", "limits": "x"},
                    {"id": "export_b", "menu": "F", "label": "Export two", "status": "DESCRIPTIVE", "needs": ["project"],
                     "call": "test_assist:export_two", "limits": "y"}],
}


@pytest.fixture
def fake_registry(monkeypatch):
    CALLS.clear()
    for name, caps in FAKES.items():
        mod = types.ModuleType("rnplens." + name)
        mod.CAPABILITIES = caps
        monkeypatch.setitem(sys.modules, "rnplens." + name, mod)
    monkeypatch.setitem(sys.modules, "test_assist", sys.modules[__name__])
    monkeypatch.setattr(capabilities, "MODULES", list(FAKES) + ["fake_missing_module", "doctor"])
    return CALLS


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    t = tmp_path_factory.mktemp("assist")
    assert importer.run([os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B")], importer.read_sequence_arg(PS),
                        importer.read_sequence_arg(RS), str(t / "p"), "7K9D_example", "BOLTZ2") == 0
    a = t / "a"; a.mkdir()
    (a / "summary.json").write_text("{}")
    return t


def run_cli(argv, answers=None):
    out = []
    it = iter(answers or [])

    def ask(prompt):
        out.append(prompt)
        try:
            return next(it)
        except StopIteration:
            raise EOFError
    rc = assist.main(argv, ask=ask if answers is not None else None, out=out.append)
    return rc, "\n".join(map(str, out))


def test_menu_has_exactly_six_items_with_the_specified_labels(fake_registry):
    items, na = assist.build_menu()
    assert [i["letter"] for i in items] == list("ABCDEF") and [i["label"] for i in items] == LABELS


def test_unavailable_and_missing_items_are_shown_with_reasons_and_cannot_run(fake_registry, project):
    items, na = assist.build_menu()
    c = items[2]
    assert not c["available"] and "test reason: not qualified" in c["reasons"][0]
    a = items[0]
    assert not a["available"] and a["reasons"] == ["no function for this item is installed in this configuration"]
    text = assist.render_menu(items, na)
    for b in capabilities.BLOCKED:
        assert b["label"] in text and b["reason"] in text
    assert "fake_missing_module: module not installed" in text
    rc, out = run_cli(["--project", str(project / "p"), "--item", "C", "--runs", "exec_A,exec_B"])
    assert rc == 3 and fake_registry == []
    rc, out = run_cli(["--project", str(project / "p")], answers=["C", "A", "q"])
    assert "C is unavailable: Compare runs: test reason" in out and "A is unavailable" in out and fake_registry == []


def test_missing_region_module_makes_item_b_unavailable(monkeypatch, project):
    monkeypatch.setattr(capabilities, "MODULES", ["region"])
    monkeypatch.setitem(sys.modules, "rnplens.region", None)          # import fails
    items, na = assist.build_menu()
    assert not items[1]["available"] and "module not installed" in items[1]["reasons"][0]


def test_non_interactive_item_calls_the_function_directly(fake_registry, project, capsys):
    rc, out = run_cli(["--project", str(project / "p"), "--analysis", str(project / "a"), "--item", "B", "--rna", "40-60", "--runs", "exec_A,exec_B"])
    assert rc == 0, out
    assert fake_registry == [{"fn": "region", "project": str(project / "p"), "analysis": str(project / "a"), "rna": (40, 60),
                              "runs": ["exec_A", "exec_B"], "protein_range": None}]
    assert str(project / "a" / "region_40-60" / "region.json") in out
    assert "evidence IDs (21)" in out and "region_40-60/region.json#/rows/0" in out and "... and 11 more" in out
    assert "limits: Contacts are those of Report's per-structure records." in out


def test_non_interactive_json_and_protein_range(fake_registry, project):
    rc, out = run_cli(["--project", str(project / "p"), "--analysis", str(project / "a"), "--item", "b", "--rna", "5-6",
                       "--protein", "10-20", "--runs", "2,1", "--json"])
    assert rc == 0
    rec = json.loads(out)
    assert rec["capability"] == "region_contacts" and len(rec["evidence_ids"]) == 2
    assert fake_registry[0]["protein_range"] == [10, 20] and fake_registry[0]["runs"] == ["exec_B", "exec_A"]


@pytest.mark.parametrize("args,msg", [
    (["--rna", "0-10"], "within 1-60"), (["--rna", "50-40"], "start is after end"), (["--rna", "1-61"], "within 1-60"),
    (["--rna", "abc"], "start-end"), (["--rna", "40-60", "--protein", "1-99"], "within 1-98"),
    (["--rna", "40-60", "--runs", "exec_A"], "exactly 2"), (["--rna", "40-60", "--runs", "exec_A,exec_Z"], "not in this project"),
    (["--rna", "40-60", "--runs", "exec_A,exec_A"], "given twice"), (["--runs", "exec_A,exec_B"], "missing input"),
])
def test_input_validation(fake_registry, project, capsys, args, msg):
    rc, out = run_cli(["--project", str(project / "p"), "--analysis", str(project / "a"), "--item", "B"] + (args if "--runs" in args else args + ["--runs", "exec_A,exec_B"]))
    err = capsys.readouterr().err
    assert rc == 2 and msg in err and fake_registry == []


def test_project_and_analysis_are_validated(fake_registry, tmp_path, project, capsys):
    rc, _ = run_cli(["--project", str(tmp_path), "--list"])
    assert rc == 2 and "no manifest.json" in capsys.readouterr().err
    rc, _ = run_cli(["--project", str(project / "p"), "--analysis", str(tmp_path), "--item", "B", "--rna", "1-2", "--runs", "1,2"])
    assert rc == 2 and "no summary.json" in capsys.readouterr().err


def test_interactive_prompts_reask_until_valid(fake_registry, project):
    answers = ["B", "70-80", "40-45", "", "1", "1,2", "q"]
    rc, out = run_cli(["--project", str(project / "p"), "--analysis", str(project / "a")], answers=answers)
    assert rc == 0
    assert "within 1-60" in out and "choose exactly 2 run(s)" in out
    assert fake_registry[0]["rna"] == (40, 45) and fake_registry[0]["runs"] == ["exec_A", "exec_B"] and fake_registry[0]["protein_range"] is None
    assert "RNA range (construct positions 1-60" in out and "1=exec_A, 2=exec_B" in out


def test_interactive_analysis_prompt_and_evidence_id(fake_registry, project):
    rc, out = run_cli(["--project", str(project / "p")], answers=["D", "/nonexistent", str(project / "a"), "bad id",
                                                                   "region_1-2/region.json#/rows/0", "q"])
    assert rc == 0 and "no summary.json" in out and "expected <file>#/<pointer>" in out
    assert fake_registry[0]["evidence_id"] == "region_1-2/region.json#/rows/0" and "evidence IDs (1)" in out


def test_experimental_needs_confirmation(fake_registry, project, capsys):
    rc, _ = run_cli(["--project", str(project / "p"), "--analysis", str(project / "a"), "--item", "E"])
    assert rc == 2 and "--allow-experimental" in capsys.readouterr().err and fake_registry == []
    rc, out = run_cli(["--project", str(project / "p"), "--analysis", str(project / "a"), "--item", "E", "--allow-experimental"])
    assert rc == 0 and "EXPERIMENTAL" in out and "groups/groups.json#/groups/0" in out
    fake_registry.clear()
    rc, out = run_cli(["--project", str(project / "p"), "--analysis", str(project / "a")], answers=["E", "n", "E", "y", "q"])
    assert len(fake_registry) == 1


def test_item_with_several_functions(fake_registry, project, capsys):
    rc, _ = run_cli(["--project", str(project / "p"), "--item", "F"])
    assert rc == 2 and "--capability" in capsys.readouterr().err
    rc, out = run_cli(["--project", str(project / "p"), "--item", "F", "--capability", "export_a", "--param", "other=xyz"])
    assert rc == 0 and fake_registry[-1] == {"fn": "unknown", "other": "xyz"}
    rc, out = run_cli(["--project", str(project / "p")], answers=["F", "3", "2", "q"])
    assert "choose 1-2" in out and fake_registry[-1] == {"fn": "export_two"}


def test_kwarg_mapping_refuses_inputs_a_function_cannot_take():
    def f(project):
        return {}
    with pytest.raises(assist.Unavailable):
        assist.to_kwargs(f, {"project": "p", "rna_range": (1, 2)})

    def g(**kw):
        return kw
    assert assist.to_kwargs(g, {"two_runs": ["a", "b"], "rna_range": (1, 2)}) == {"runs": ["a", "b"], "rna_range": [1, 2]}

    def h(project_dir, rna_range, run_a, run_b):
        return {}
    assert assist.to_kwargs(h, {"project": "p", "rna_range": (3, 4), "two_runs": ["x", "y"]}) == \
        {"project_dir": "p", "rna_range": [3, 4], "run_a": "x", "run_b": "y"}


def test_failing_function_keeps_the_menu_open(fake_registry, project, monkeypatch):
    def boom(**kw):
        raise RuntimeError("disk full")
    monkeypatch.setattr(sys.modules[__name__], "grouping", boom)
    rc, out = run_cli(["--project", str(project / "p"), "--analysis", str(project / "a")], answers=["E", "y", "q"])
    assert rc == 0 and "the function failed: RuntimeError: disk full" in out


def _no_llm_guards(monkeypatch):
    spawned = []
    real_popen = subprocess.Popen

    class Guard(real_popen):
        def __init__(self, args, *a, **k):
            spawned.append(args)
            super().__init__(args, *a, **k)
    monkeypatch.setattr(subprocess, "Popen", Guard)

    def no_net(*a, **k):
        raise AssertionError("network connection attempted")
    monkeypatch.setattr(socket.socket, "connect", no_net)
    for k in [k for k in sys.modules if k.startswith("rnplens_assistant")]:
        monkeypatch.delitem(sys.modules, k)
    return spawned


def test_menu_never_uses_a_language_model_or_the_network(fake_registry, project, monkeypatch):
    spawned = _no_llm_guards(monkeypatch)
    rc, out = run_cli(["--project", str(project / "p"), "--analysis", str(project / "a"), "--item", "B", "--rna", "1-3", "--runs", "1,2"])
    assert rc == 0
    rc, out = run_cli(["--project", str(project / "p"), "--analysis", str(project / "a")], answers=["B", "1-2", "", "1,2", "D", "x.json#/a", "q"])
    assert rc == 0
    assert not any("codex" in " ".join(map(str, a if isinstance(a, (list, tuple)) else [a])) for a in spawned)
    assert not any(k.startswith("rnplens_assistant") for k in sys.modules)


def test_nl_mode_refuses_when_doctor_is_not_ready(fake_registry, project, monkeypatch):
    spawned = _no_llm_guards(monkeypatch)
    from rnplens import doctor
    monkeypatch.setattr(doctor, "agent_status", lambda env=None: (False, ["Codex CLI: ACTION REQUIRED (not found)"]))
    rc, out = run_cli(["--project", str(project / "p"), "--nl", "Do the runs agree?", "--task", str(project)])
    assert rc == 3 and "not sent anywhere" in out and "Codex CLI: ACTION REQUIRED" in out and "rnplens assist --project" in out
    rc, out = run_cli(["--project", str(project / "p"), "--nl", "Do the runs agree?"], answers=["y", "q"])
    assert rc == 0 and "RNPLens question menu" in out
    assert not any(k.startswith("rnplens_assistant") for k in sys.modules)
    assert not any("codex" in str(a) for a in spawned)


def test_nl_mode_hands_the_question_to_the_assistant_when_ready(project, tmp_path, monkeypatch):
    spawned = _no_llm_guards(monkeypatch)
    from rnplens import doctor
    monkeypatch.setattr(doctor, "agent_status", lambda env=None: (True, []))
    from rnplens_assistant import ask, llm
    task = tmp_path / "task"
    shutil.copytree(os.path.join(RF, "exec_A"), task / "runA"); shutil.copytree(os.path.join(RF, "exec_B"), task / "runB")
    shutil.copy(PS, task / "protein.fasta"); shutil.copy(RS, task / "rna.fasta")
    step = {k: None for k in ask.PLAN_SCHEMA["properties"]["steps"]["items"]["properties"]}
    imp = dict(step, tool="import_predictions", project_id="p", folders=["run_001", "run_002"], protein_fasta="protein_sequence_001",
               rna_fasta="rna_sequence_001", accept_offsets=False, purpose="t")
    plan = {"goal": "AGREEMENT", "reference_supplied": False, "requested_capabilities": [], "clarification_needed": None,
            "steps": [imp, dict(step, tool="analyse_predictions", project_id="p", purpose="t")]}
    seen = {}

    def factory():
        seen["stub"] = llm.Stub([plan])
        return seen["stub"]
    monkeypatch.setattr(assist, "_make_client", factory)
    rc, out = run_cli(["--project", str(project / "p"), "--nl", "Do the runs agree?", "--task", str(task), "--nl-out", str(tmp_path / "nl")])
    assert rc == 0, out
    assert len(seen["stub"].calls) == 1 and seen["stub"].calls[0]["kind"] == "plan"
    assert assist.NL_PRIVACY in out and doctor.NOTICE in out
    assert (tmp_path / "nl" / "answer.md").is_file() and "evidence IDs (" in out and "evidence IDs (0)" not in out
    assert not any("codex" in str(a) for a in spawned)
    rc, out = run_cli(["--project", str(project / "p"), "--nl", "again", "--task", str(task), "--nl-out", str(tmp_path / "nl")])
    assert rc == 2 and "already exists" in out
    rc, out = run_cli(["--project", str(project / "p"), "--nl", "again"])
    assert rc == 2 and "needs --task" in out


def test_menu_reads_only_declared_inputs(fake_registry, project, monkeypatch):
    opened = []
    real = builtins.open

    def rec(f, *a, **k):
        opened.append(os.path.abspath(str(f)))
        return real(f, *a, **k)
    monkeypatch.setattr(builtins, "open", rec)
    rc, _ = run_cli(["--project", str(project / "p"), "--analysis", str(project / "a"), "--item", "B", "--rna", "1-2", "--runs", "1,2"])
    assert rc == 0
    roots = [str(project / "p"), str(project / "a")]
    assert opened and all(any(o.startswith(r) for r in roots) or o.startswith(os.path.dirname(pv.__file__)) for o in opened), opened


def test_deterministic_and_wording(fake_registry, project):
    outs = [run_cli(["--project", str(project / "p"), "--analysis", str(project / "a"), "--item", "B", "--rna", "2-4", "--runs", "1,2"])[1] for _ in range(2)]
    assert outs[0] == outs[1]
    items, na = assist.build_menu()
    assert trace.wording_audit(assist.render_menu(items, na)) == []
    assert trace.wording_audit(assist.MENU_PRIVACY + assist.NL_PRIVACY) == []


def test_docs_pages_state_modes_limits_and_notice():
    from rnplens import doctor
    root = os.path.dirname(EX)
    sp = " ".join(open(os.path.join(root, "docs", "setup_and_privacy.md"), encoding="utf-8").read().split())
    am = " ".join(open(os.path.join(root, "docs", "assist.md"), encoding="utf-8").read().split())
    assert doctor.NOTICE in sp
    for phrase in ("Question menu (`rnplens assist`).** Nothing", "never sends atomic coordinates, sequences, or any computed value",
                   "Future follow-up mode", "only after an explicit opt-in", "Linux x86_64", "supported natively, with Seatbelt",
                   "bubblewrap", "## Interpretation limits"):
        assert phrase in sp, phrase
    for letter, label in assist.ITEMS:
        assert "| %s | %s |" % (letter, label) in am
    assert "## Interpretation limits" in am and "Manual open check" in am
    assert trace.wording_audit(sp) == [] and trace.wording_audit(am) == []
