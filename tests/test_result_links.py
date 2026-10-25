"""0.4 usability (owner programme 2026-10-18, section 6): the question menu and the natural-language mode link the
produced contact tables and the offline Mol* page (rnplens.result_links). No language model: the NL test uses the
deterministic llm.Stub planner."""
import io
import json
import os
import shutil
import contextlib

import pytest

from rnplens import analyse, assist, importer

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")
PS = os.path.join(EX, "reference_based", "7K9D_protein.fasta")
RS = os.path.join(EX, "reference_based", "7K9D_rna.fasta")


@pytest.fixture
def pa(tmp_path):
    assert importer.run([os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B")], importer.read_sequence_arg(PS),
                        importer.read_sequence_arg(RS), str(tmp_path / "p"), "7K9D_links", "BOLTZ2") == 0
    assert analyse.run(str(tmp_path / "p"), str(tmp_path / "a")) == 0
    return str(tmp_path / "p"), str(tmp_path / "a")


def _menu(P, A, *args):
    lines = []
    rc = assist.main(["--project", P, "--analysis", A] + list(args), out=lines.append)
    return rc, "\n".join(lines)


def test_menu_region_result_links_tables_and_viewer(pa):
    P, A = pa
    rc, text = _menu(P, A, "--item", "B", "--rna", "13-23")
    assert rc == 0
    assert "contact tables:" in text and os.path.join(A, "report", "contacts_by_output.json") in text
    assert os.path.join(A, "region_13-23", "region_contacts.tsv") in text
    page = os.path.join(A, "viewer", "viewer.html")
    assert os.path.isfile(page) and ("structure viewer (offline Mol* page; open it from disk): %s" % page) in text
    rc, js = _menu(P, A, "--item", "C", "--rna", "13-23", "--runs", "exec_A,exec_B", "--json")
    d = json.loads(js)
    assert rc == 0 and d["result_links"]["viewer"] == page
    assert [os.path.basename(p) for _, p in d["result_links"]["contact_tables"]][:2] == ["contacts_by_output.json", "result.json"]


def test_menu_explain_result_has_no_links(pa):
    P, A = pa
    rc, js = _menu(P, A, "--item", "D", "--evidence", "summary.json#/contacts/rows/0", "--json")
    assert rc == 0 and json.loads(js)["result_links"] is None


def test_natural_language_answer_links_tables_and_viewer(tmp_path):
    llm = pytest.importorskip("rnplens_assistant.llm")
    ask = pytest.importorskip("rnplens_assistant.ask")
    t = tmp_path / "task"
    shutil.copytree(os.path.join(RF, "exec_A"), t / "runA"); shutil.copytree(os.path.join(RF, "exec_B"), t / "runB")
    shutil.copy(PS, t / "protein.fasta"); shutil.copy(RS, t / "rna.fasta")
    json.dump({"task_id": "dev", "reference_files": []}, open(t / "task.json", "w"))

    def step(tool, **kw):
        s = {k: None for k in ask.PLAN_SCHEMA["properties"]["steps"]["items"]["properties"]}
        s.update(tool=tool, purpose="t", **kw)
        return s
    plan = {"goal": "AGREEMENT", "reference_supplied": False, "requested_capabilities": [], "clarification_needed": None,
            "steps": [step("import_predictions", project_id="p", folders=["run_001", "run_002"], protein_fasta="protein_sequence_001",
                           rna_fasta="rna_sequence_001", accept_offsets=False),
                      step("analyse_predictions", project_id="p"),
                      step("region_comparison", project_id="p", rna_start=13, rna_end=23, runs=["run_001", "run_002"])]}
    lines = []
    rd = tmp_path / "run"
    rc = assist.natural_language("What do the runs share in RNA 13-23?", {"project": str(tmp_path), "analysis": None},
                                 task=str(t), nl_out=str(rd), out=lines.append, ask=None,
                                 client_factory=lambda: llm.Stub([plan]), agent_status=lambda: (True, []))
    text = "\n".join(lines)
    assert rc == 0, text[-2000:]
    L = json.load(open(rd / "result_links.json"))
    assert L["viewer"] and os.path.isfile(L["viewer"]) and L["viewer"] in text
    assert any(p.endswith("contacts_by_output.json") for _, p in L["contact_tables"]) and "contact tables:" in text
