"""Integration: every menu item A-F runs end to end on the bundled 7K9D example without any language model, and a
refused request is reported as refused (exit 4), never as success."""
import json
import os
import subprocess
import sys

import pytest

from rnplens import assist, cli

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(ROOT, "examples")


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    t = tmp_path_factory.mktemp("menu_e2e")
    rf = os.path.join(EX, "reference_free", "report_7K9D")
    assert cli.main(["import", os.path.join(rf, "exec_A"), os.path.join(rf, "exec_B"), "--protein-seq",
                     os.path.join(EX, "reference_based", "7K9D_protein.fasta"), "--rna-seq",
                     os.path.join(EX, "reference_based", "7K9D_rna.fasta"), "--out", str(t / "p"), "--case-id", "m",
                     "--engine", "BOLTZ2"]) == 0
    return str(t / "p"), str(t / "a")


def _item(P, A, letter, *extra):
    lines = []
    rc = assist.main(["--project", P, "--analysis", A, "--item", letter, "--json"] + list(extra), out=lines.append)
    doc = json.loads([l for l in lines if l.lstrip().startswith("{")][-1]) if lines else {}
    return rc, doc


def test_items_a_to_f_run_without_llm(proj, monkeypatch):
    P, A = proj
    real = subprocess.run
    def guard(args, *a, **k):
        assert "codex" not in " ".join(map(str, args if isinstance(args, (list, tuple)) else [args])), "LLM call"
        return real(args, *a, **k)
    monkeypatch.setattr(subprocess, "run", guard)
    rc, d = _item(P, A, "A"); assert rc == 0 and d["result_status"] == "OK" and os.path.isfile(os.path.join(A, "summary.json"))
    rc, d = _item(P, A, "B", "--rna", "13-23"); assert rc == 0 and d["result_status"] == "OK" and d["evidence_ids"]
    rc, d = _item(P, A, "C", "--rna", "13-23", "--runs", "exec_A,exec_B"); assert rc == 0 and d["result_status"] == "OK"
    rc, d = _item(P, A, "D", "--evidence", "summary.json#/contacts/rows/0"); assert rc == 0 and d["outputs"]
    rc, d = _item(P, A, "E"); assert rc == 0 and any(o.endswith("groups.json") for o in d["outputs"])
    rc, d = _item(P, A, "F"); assert rc == 0 and any(o.endswith("methods.md") for o in d["outputs"])


def test_refused_request_is_not_reported_as_success(proj):
    P, A = proj
    if not os.path.isfile(os.path.join(A, "summary.json")):
        _item(P, A, "A")
    rc, d = _item(P, A, "D", "--evidence", "summary.json#/no/such/pointer")
    assert rc == 4 and d["result_status"] in assist.FAILED_STATES


def test_view_command_writes_offline_region_page(proj):
    P, A = proj
    if not os.path.isfile(os.path.join(A, "summary.json")):
        _item(P, A, "A")
    assert cli.main(["view", P, "--analysis", A, "--rna", "13-23"]) == 0
    page = os.path.join(A, "viewer_13-23", "viewer.html")
    html = open(page).read()
    assert "http://" not in html and "https://" not in html
    man = json.load(open(os.path.join(A, "viewer_13-23", "viewer_manifest.json")))
    assert any(i["path"].endswith("contacts_by_output.json") for i in man["provenance"]["inputs"])
    assert cli.main(["view", P, "--analysis", A, "--rna", "50-99"]) == 2          # beyond the 60-nt construct


def test_followup_without_assistant_package_explains_and_exits_3(proj, monkeypatch):
    P, A = proj
    if not os.path.isfile(os.path.join(A, "summary.json")):
        _item(P, A, "A")
    for m in ("rnplens_assistant", "rnplens_assistant.followup", "rnplens_assistant.consent"):
        monkeypatch.setitem(sys.modules, m, None)                 # as if the assistant were not installed
    lines = []
    rc = assist.main(["--project", P, "--analysis", A, "--item", "B", "--rna", "13-23", "--followup", "local", "--yes"],
                     out=lines.append)
    assert rc == 3 and any("pip install ./assistant" in l for l in lines)


def test_explain_text_shows_structured_value(proj):
    P, A = proj
    if not os.path.isfile(os.path.join(A, "summary.json")):
        _item(P, A, "A")
    from rnplens import evidence_query as E
    r = E.capability_run(analysis=A, project=P, evidence_id="summary.json#/contacts/rows/0", write_out=False)
    assert r["status"] == "OK" and '"protein_position"' in r["message"]
