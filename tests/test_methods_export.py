"""rnplens export-methods: traceability (every sentence has sources; removing a source field removes the sentence),
determinism, missing-record behaviour, provenance manifest, LLM-free operation."""
import copy
import json
import os
import re
import shutil
import socket
import sys

import pytest

from rnplens import analyse, capabilities, cli, importer, methods_export as M, region, trace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures_v04", "region"))
import builders as B  # noqa: E402

REF = os.path.join(B.EX, "reference_based", "7K9D_reference.cif")


@pytest.fixture(scope="module")
def ws(tmp_path_factory):
    t = tmp_path_factory.mktemp("methods")
    P, A = B.example_project(t / "ex")
    assert region.run(P, A, "13-23")[0] == 0
    P2, A2 = B.project(t / "ex2", {"exec_A": [(B.EXEC_A, .5, B.renumber("B", 100))],
                                   "exec_B": [(B.EXEC_B, .5, None), (B.diag(1), .1, B.delete_residues("B", {18, 19, 20}))]},
                       accept_derived=True)
    A3 = str(t / "ex" / "r_ref")
    assert analyse.run(P, A3, reference=REF, diagnose=False) == 0
    run_dir = B.assistant_run(t / "asst")
    P4, A4 = B.project(t / "ex4", {"exec_A": [(B.EXEC_A, .5, None), (B.diag(1), .3, None)],
                                   "exec_B": [(B.EXEC_B, .5, None), (B.diag(2), .2, None)]})
    assert region.run(P4, A4, "13-23")[0] == 0
    return {"P": P, "A": A, "P2": P2, "A2": A2, "A3": A3, "A4": A4, "run": run_dir}


CASES = [("A", ()), ("A2", ()), ("A3", ()), ("A4", ()), ("A", ("run",))]


def _records(ws, a, runs):
    return M.load_records(ws[a], None, [ws[r] for r in runs])


@pytest.mark.parametrize("a,runs", CASES)
def test_every_sentence_has_sources_that_resolve(ws, a, runs):
    R = _records(ws, a, runs)
    sents, omitted = M.generate(R)
    assert len(sents) >= 12
    for s in sents:
        assert s["sources"], s["id"]
        for src in s["sources"]:
            root = R.roots[src["record"]]
            doc = json.load(open(os.path.normpath(os.path.join(root, src["file"]))))
            v = doc
            for part in [p for p in src["pointer"].split("/")[1:]]:
                part = part.replace("~1", "/").replace("~0", "~")
                v = v[int(part)] if isinstance(v, list) else v[part]
            if src["value"] != "(structured)":
                assert v == src["value"], (s["id"], src)
    assert M.audit(sents) == []


@pytest.mark.parametrize("a,runs", CASES)
def test_removing_a_source_field_removes_the_sentence(ws, a, runs):
    R0 = _records(ws, a, runs)
    sents, _ = M.generate(R0)
    n_checked = 0
    for s in sents:
        for src in s["sources"]:
            parts = [p.replace("~1", "/").replace("~0", "~") for p in src["pointer"].split("/")[1:]]
            if not parts:
                continue
            R = M.Records(copy.deepcopy(R0.docs), R0.paths, R0.roots)
            parent = R.docs[src["record"]]
            for p in parts[:-1]:
                parent = parent[int(p)] if isinstance(parent, list) else parent[p]
            if not isinstance(parent, dict):
                continue
            del parent[parts[-1]]
            got, omitted = M.generate(R)
            assert s["id"] not in {x["id"] for x in got}, (s["id"], src["pointer"])
            assert s["id"] in {x["id"] for x in omitted}
            n_checked += 1
    assert n_checked >= 20


def test_whole_record_missing_removes_its_sentences(ws, tmp_path):
    A = tmp_path / "a"
    shutil.copytree(ws["A"], A)
    os.unlink(A / "report" / "rnplens_run.json")        # also removes the way to find the project
    code, out = M.run(str(A))
    src = json.load(open(os.path.join(out, "methods_sources.json")))
    ids = {s["id"] for s in src["sentences"]}
    om = {o["id"]: o for o in src["omitted"]}
    assert "version" not in ids and om["version"]["kind"] == "field_missing"
    assert {"structures", "runs", "designation", "chains"} <= set(om)            # manifest not found
    assert "contacts" in ids                                                   # summary still there
    md = open(os.path.join(out, "methods.md")).read()
    assert "## Not stated (record field missing)" in md and "- version: report_run (record not available)" in md
    # with the project given explicitly, the manifest sentences return
    src2 = M.build(str(A), project=ws["P"])[2]
    assert {"structures", "runs"} <= {s["id"] for s in src2["sentences"]}


def test_refuses_a_directory_that_is_not_an_analysis(tmp_path, capsys):
    with pytest.raises(M.ExportError, match="no summary.json"):
        M.load_records(str(tmp_path))
    assert cli.main(["export-methods", str(tmp_path)]) == 2


def test_text_covers_the_required_topics(ws):
    md = M.build(ws["A"], None, [ws["run"]])[0]
    for phrase in ("A total of 2 predicted structures", "engine-designated structure was identified by the rule",
                   "SHA-256", "RNPLens 0.4.0.dev0", "a contact was defined as a protein residue and RNA nucleotide",
                   "no agreement score was computed", "recorded as absent only where", "not observed",
                   "No experimental reference structure was supplied", "reference-free and descriptive",
                   "question-driven assistant", "DRAFT FOR AUTHOR REVIEW"):
        assert phrase in md, phrase
    md3 = M.build(ws["A3"])[0]
    assert "required the supplied experimental reference structure (7K9D_reference.cif)" in md3
    assert "were withheld in this version" in md3
    md4 = M.build(ws["A4"])[0]
    assert "also computed for BOLTZ2, between the engine-designated structures of runs exec_A and exec_B" in md4
    assert "not computed for BOLTZ2, because Report computes them only for exactly two eligible structures" in md4
    assert "Measures that could not be computed were reported as not computed" in md4
    md2 = M.build(ws["A2"])[0]
    assert "1 candidate structure file was excluded at import (INCOMPATIBLE 1)" in md2
    assert "analysed through derived copies (renumber chain(s) B to construct positions 1..L)" in md2


def test_no_invented_versions_or_numbers(ws):
    """Every version-like token and every number in a sentence comes from that sentence's source values (or is a
    count over them)."""
    R = _records(ws, "A3", ())
    sents, _ = M.generate(R)
    for s in sents:
        vals = " ".join(str(x["value"]) for x in s["sources"])
        for tok in re.findall(r"\b\d+\.\d+(?:\.\d+)*(?:\.dev\d+)?\b", s["text"]):
            assert tok in vals or tok in json.dumps(R.docs), (s["id"], tok)
    assert "et al" not in " ".join(s["text"] for s in sents) and "doi" not in " ".join(s["text"] for s in sents).lower()


def test_determinism(ws, tmp_path):
    o1, o2 = tmp_path / "m1", tmp_path / "m2"
    assert M.run(ws["A"], None, [ws["run"]], str(o1))[0] == 0
    assert M.run(ws["A"], None, [ws["run"]], str(o2))[0] == 0
    for f in ("methods.md", "methods.txt"):
        assert open(o1 / f, "rb").read() == open(o2 / f, "rb").read()
    strip = lambda p: [l for l in open(p).read().splitlines() if '"created_utc"' not in l]
    for f in ("methods_sources.json", "provenance_manifest.json"):
        assert strip(o1 / f) == strip(o2 / f)


def test_provenance_manifest(ws):
    code, out = M.run(ws["A2"])
    pm = json.load(open(os.path.join(out, "provenance_manifest.json")))["manifest"]
    man = json.load(open(os.path.join(ws["P2"], "manifest.json")))
    by = {x["path"]: x for x in pm["inputs"]}
    for s in man["structures"]:
        assert by[s["path"]]["recorded_sha256"] == s["original_sha256"] and by[s["path"]]["matches_record"] is True
        if s["used_path"] != s["path"]:
            assert by[s["used_path"]]["matches_record"] is True
    outs = {x["file"]: x["sha256"] for x in pm["outputs"]}
    from rnplens.provenance import sha256_file
    assert outs["report/contacts_by_output.json"] == sha256_file(os.path.join(ws["A2"], "report", "contacts_by_output.json"))
    assert not any(f.startswith("methods/") for f in outs)
    assert any("report run" in " ".join(c["command"]) if isinstance(c["command"], list) else "report run" in c["command"]
               for c in pm["commands"])
    assert pm["versions"]["rnplens_analysis"] == "0.4.0.dev0"


def test_llm_free_and_offline(ws, monkeypatch):
    def no_net(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket.socket, "connect", no_net)
    before = set(sys.modules)
    M.build(ws["A"], None, [ws["run"]])
    assert not any(m.startswith(("openai", "rnplens_assistant")) for m in set(sys.modules) - before)
    src = json.loads(json.dumps(M.build(ws["A"])[2]))
    assert src["llm_used"] is False
    assert not re.search(r"^\s*(import|from)\s+(openai|rnplens_assistant)", open(M.__file__).read(), flags=re.M)


def test_wording_audit_blocks_output(ws, tmp_path, monkeypatch):
    monkeypatch.setattr(M, "t_structures", lambda R: "The best structure %s." % R.get("manifest", "/counts/included"))
    code, out = M.run(ws["A"], out=str(tmp_path / "m"))
    assert code == 1 and os.path.exists(os.path.join(out, "WORDING_AUDIT_FAILED.txt"))
    assert not os.path.exists(os.path.join(out, "methods.md"))


def test_cli_and_capability(ws, capsys):
    assert cli.main(["export-methods", ws["A"]]) == 0
    assert "METHODS (DRAFT)" in capsys.readouterr().out
    assert sorted(os.listdir(os.path.join(ws["A"], "methods"))) == ["methods.md", "methods.txt", "methods_sources.json",
                                                                     "provenance_manifest.json"]
    offered, _ = capabilities.available()
    c = next(c for c in offered if c["id"] == "export_methods")
    assert c["menu"] == "F" and c["status"] == "DESCRIPTIVE"
    r = capabilities.resolve(c["call"])(analysis=ws["A"])
    assert r["status"] == "OK" and len(r["outputs"]) == 4

def test_runs_sentence_counts_included_structures(tmp_path):
    """QA workflow-replay (2026-10-17): the runs sentence must give the structures each run contributes, not the files
    found. exec_B has two files, one excluded at import (truncated RNA): 2 + 1 = 3 structures were analysed."""
    P, A = B.project(tmp_path / "runs", {"exec_A": [(B.EXEC_A, .5, None), (B.diag(1), .1, None)],
                                         "exec_B": [(B.EXEC_B, .5, None), (B.diag(2), .1, B.delete_residues("B", {18, 19, 20}))]})
    sents, _ = M.generate(M.load_records(A, P))
    by = {s["id"]: s["text"] for s in sents}
    assert "A total of 3 predicted structures" in by["structures"]
    assert "exec_A, 2 structures; exec_B, 1 structure (2 structure files found, 1 excluded at import)." in by["runs"], by["runs"]
