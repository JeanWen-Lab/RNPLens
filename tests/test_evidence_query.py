"""rnplens explain: deterministic evidence lookups over analysis, region, assistant-run and compare records."""
import json
import os
import re
import socket
import sys

import pytest

from rnplens import capabilities, cli, evidence_query as EQ, region, trace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures_v04", "region"))
import builders as B  # noqa: E402


@pytest.fixture(scope="module")
def ws(tmp_path_factory):
    t = tmp_path_factory.mktemp("explain")
    P, A = B.example_project(t / "ex")
    assert region.run(P, A, "13-23")[0] == 0
    # a project with an excluded file and a derived (renumbered) copy
    P2, A2 = B.project(t / "ex2", {"exec_A": [(B.EXEC_A, .5, B.renumber("B", 100))],
                                   "exec_B": [(B.EXEC_B, .5, None), (B.diag(1), .1, B.delete_residues("B", {18, 19, 20}))]},
                       accept_derived=True)
    run_dir = B.assistant_run(t / "asst")
    cmp_dir = B.compare_dir(t / "cmp")
    return {"P": P, "A": A, "P2": P2, "A2": A2, "run": run_dir, "cmp": cmp_dir}


def _resolve(stmt):
    """Follow a statement's evidence ID within its root (files outside JSON are only checked to exist)."""
    if stmt["root"] == "rnplens":
        return True
    path, ptr = stmt["evidence_id"].split("#", 1)
    p = os.path.normpath(os.path.join(stmt["root"], path))
    assert os.path.exists(p), stmt["evidence_id"]
    if p.endswith(".jsonl"):
        if ptr in ("", "/"):
            return True
        lines = [l for l in open(p) if l.strip()]
        parts = [x for x in ptr.split("/") if x]
        obj = json.loads(lines[int(parts[0])])
        return EQ.resolve_pointer(obj, "/" + "/".join(parts[1:]) if len(parts) > 1 else "/")
    if not p.endswith(".json"):
        return True
    return EQ.resolve_pointer(json.load(open(p)), ptr)


ALL = [q for q in EQ.QUERIES if q not in ("evidence", "contact")]


@pytest.mark.parametrize("query", ALL)
def test_every_statement_resolves_and_passes_the_wording_audit(ws, query):
    doc = EQ.build([ws["A"], ws["A2"]], None, [ws["run"]], [ws["cmp"]], query)
    assert doc["statements"], query
    for s in doc["statements"]:
        assert s["evidence_id"] and "#" in s["evidence_id"]
        _resolve(s)
        if "quoted" in s and s["root"] != "rnplens" and s["evidence_id"].split("#")[0].endswith(".json"):
            v = _resolve(s)
            if isinstance(v, str):
                assert s["quoted"] == v                                              # verbatim
    assert EQ.audit(doc) == []                     # generated wording; verbatim record quotations are exempt


def test_explain_region_evidence_id(ws):
    doc = EQ.build([ws["A"]], query="evidence", evidence_id="region_13-23/region.json#/contacts/0")
    S = doc["statements"]
    row = json.load(open(os.path.join(ws["A"], "region_13-23", "region.json")))["contacts"][0]
    assert S[0]["value"] == row
    man = {s["id"]: s for s in json.load(open(os.path.join(ws["P"], "manifest.json")))["structures"]}
    got = {s["structure"]: s for s in S if s.get("structure")}
    assert set(got) == {"s001", "s002"}
    for sid, s in got.items():
        assert (s["run"], s["sample"], s["designated"], s["used_sha256"], s["engine"]) == \
               (man[sid]["run"], man[sid]["sample"], man[sid]["designated"], man[sid]["used_sha256"], man[sid]["engine"])
    assert any(s.get("quoted") == region.RECURRENCE_LIMIT for s in S)
    assert any(s.get("quoted") == region.DEFINITION for s in S)                      # filtering definition
    assert any(s["evidence_id"] == "region_13-23/region.json#/provenance" for s in S)  # tool and version


def test_explain_summary_row_gives_definition_source_and_version(ws):
    doc = EQ.build([ws["A"]], query="evidence", evidence_id="summary.json#/contacts/rows/0")
    q = {s["evidence_id"]: s.get("quoted") for s in doc["statements"]}
    S = json.load(open(os.path.join(ws["A"], "summary.json")))
    assert q["summary.json#/contacts/definition"] == S["contacts"]["definition"]
    assert q["summary.json#/contacts/source"] == S["contacts"]["source"]
    assert "summary.json#/rnplens_version" in q


def test_which_structures_support_a_contact(ws):
    doc = EQ.build([ws["A"]], query="contact", contact="K14-G20")
    cbo = json.load(open(os.path.join(ws["A"], "report", "contacts_by_output.json")))
    want = sorted(k for k, cl in cbo.items() if [14, 20] in cl)
    listed = sorted(s["evidence_id"].split("#/")[1].rsplit("/", 1)[0] for s in doc["statements"]
                    if s.get("structure") and s.get("listed") is not False)
    assert listed == want
    assert doc["statements"][0]["value"] == [len(want), len(cbo)]
    assert any(s.get("presence") == "SHARED_BY_ALL_RUNS" for s in doc["statements"])
    assert EQ.build([ws["A"]], query="contact", contact="14-20")["statements"][0]["value"] == [len(want), len(cbo)]
    with pytest.raises(EQ.QueryError, match="does not match the construct"):
        EQ.build([ws["A"]], query="contact", contact="A14-G20")
    with pytest.raises(EQ.QueryError, match="outside the construct"):
        EQ.build([ws["A"]], query="contact", contact="K14-G99")


def test_excluded_files_with_reasons(ws):
    doc = EQ.build([ws["A2"]], query="excluded")
    man = json.load(open(os.path.join(ws["P2"], "manifest.json")))
    exc = [s for s in man["structures"] if s["verdict"] != "INCLUDED"]
    got = [s for s in doc["statements"] if s.get("verdict")]
    assert [s["structure"] for s in got] == [s["id"] for s in exc]
    assert got[0]["quoted"] == "; ".join(exc[0]["reasons"])


def test_counts_equal_the_records(ws):
    doc = EQ.build([ws["A"]], query="count")
    man = json.load(open(os.path.join(ws["P"], "manifest.json")))
    S = json.load(open(os.path.join(ws["A"], "summary.json")))
    v = {s["evidence_id"]: s.get("value") for s in doc["statements"]}
    assert v["../p/manifest.json#/counts"] == man["counts"]
    assert v["summary.json#/contacts/denominators/BOLTZ2"] == S["contacts"]["denominators"]["BOLTZ2"]
    assert v["region_13-23/region.json#/summary"] == 2


def test_versions_and_commands(ws):
    doc = EQ.build([ws["A"]], None, [ws["run"]], query="versions")
    txt = EQ.render_text(doc)
    assert "0.4.0.dev0" in txt and "rnplens report run" in txt and "assistant 0.1.0.dev0" in txt


def test_unavailable_metrics_and_why(ws):
    doc = EQ.build([ws["A"]], None, [ws["run"]], query="unavailable")
    states = {s.get("state") for s in doc["statements"]}
    assert {"TOOL_BLOCKED", "INPUT_MISSING", "UNAVAILABLE", "NOT_COMPUTED"} <= states
    assert any(s.get("record_id") and s["state"] == "TOOL_BLOCKED" for s in doc["statements"])   # assistant record
    assert any("geometry" in s["text"].lower() for s in doc["statements"])


def test_correspondence_rule_and_derived_copies(ws):
    doc = EQ.build([ws["A2"]], query="correspondence")
    man = json.load(open(os.path.join(ws["P2"], "manifest.json")))
    st = {(s["structure"], s["evidence_id"].rsplit("/", 1)[1]): s["status"] for s in doc["statements"] if s.get("status")}
    for s in man["structures"]:
        for j, c in enumerate(s["chains"]):
            assert st[(s["id"], str(j))] == c["status"]
    assert any(s.get("quoted", "").startswith("renumber chain(s) B") for s in doc["statements"])


def test_region_mapping(ws):
    doc = EQ.build([ws["A"]], None, [ws["run"]], query="region_mapping")
    cov = [s for s in doc["statements"] if s.get("structure")]
    assert {s["structure"] for s in cov} == {"s001", "s002"} and all("COMPLETE" in s["text"] for s in cov)
    assert any(s.get("record_id") for s in doc["statements"])


def test_not_like_for_like_from_compare(ws):
    doc = EQ.build([], None, [], [ws["cmp"]], "not_like_for_like")
    cs = json.load(open(os.path.join(ws["cmp"], "comparison_summary.json")))
    want = sorted((m, t, c) for m, r in cs["metrics"].items() for c in EQ.NOT_LIKE for t in r["targets_by_class"].get(c, []))
    got = sorted((s["metric"], s["target"], s["compare_class"]) for s in doc["statements"] if s.get("compare_class"))
    assert got == want and ("dockq", "corr", "CORRESPONDENCE_CHANGED") in got and ("dockq", "lost", "NEWLY_UNEVALUABLE") in got
    assert any("like-for-like" in s["text"] and s.get("value") == cs["metrics"]["dockq"]["like_for_like_n"] for s in doc["statements"])


def test_not_like_for_like_from_run_differences(ws):
    doc = EQ.build([ws["A2"]], query="not_like_for_like")
    # A2: exec_A has 1 file, exec_B 2 files of which 1 is excluded at import, so both runs contribute 1 structure
    # (QA workflow-replay 2026-10-17: the run-size statement previously compared files found, 1/2)
    assert not any("runs differ in size" in s["text"] for s in doc["statements"])
    assert any("1/2 files found, 1/1 included per run" in s["text"] for s in doc["statements"])


def test_assistant_record_lookup(ws):
    E = [json.loads(l) for l in open(os.path.join(ws["run"], "evidence.jsonl"))]
    rid = next(e["id"] for e in E if e["tool"] == "region_contacts" and e["unit"] == "fraction_kn")
    doc = EQ.build([], None, [ws["run"]], [], "evidence", evidence_id=rid)
    S = doc["statements"]
    assert S[0]["record_id"] == rid and any(s["evidence_id"].startswith("plan.json#/steps/") for s in S)
    assert {s["structure"] for s in S if s.get("structure")} == set(next(e for e in E if e["id"] == rid)["structures"])
    i = next(i for i, e in enumerate(E) if e["id"] == rid)
    assert EQ.build([], None, [ws["run"]], [], "evidence", evidence_id="evidence.jsonl#/%d" % i)["statements"][0]["record_id"] == rid


def test_malformed_queries_are_refused(ws):
    for ev, msg in (("nohash", "is not '<file>#"), ("missing.json#/x", "in none of the given"),
                    ("summary.json#/nope/1", "does not exist"), ("E9999", "not found")):
        with pytest.raises(EQ.QueryError, match=msg):
            EQ.build([ws["A"]], None, [ws["run"]], query="evidence", evidence_id=ev)
    with pytest.raises(EQ.QueryError, match="at least one"):
        EQ.build([], query="count")
    with pytest.raises(EQ.QueryError, match="unknown query"):
        EQ.build([ws["A"]], query="ranking")


def test_determinism(ws):
    a = EQ.build([ws["A"]], None, [ws["run"]], query="unavailable")
    b = EQ.build([ws["A"]], None, [ws["run"]], query="unavailable")
    a["provenance"].pop("created_utc"); b["provenance"].pop("created_utc")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert EQ.render_text(a) == EQ.render_text(b)


def test_llm_free_and_offline(ws, monkeypatch):
    def no_net(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket.socket, "connect", no_net)
    before = set(sys.modules)
    for q in ALL:
        EQ.build([ws["A"]], None, [ws["run"]], [ws["cmp"]], q)
    new = set(sys.modules) - before
    assert not any(m.startswith(("openai", "rnplens_assistant.llm", "rnplens_assistant.codex")) for m in new)
    src = open(EQ.__file__).read()
    assert not re.search(r"^\s*(import|from)\s+(openai|rnplens_assistant)", src, flags=re.M)


def test_data_access_only_declared_roots(ws):
    seen, on = [], [True]

    def hook(ev, args):
        if on[0] and ev == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            seen.append(os.path.realpath(os.fsdecode(args[0])))
    sys.addaudithook(hook)
    try:
        for q in ALL:
            EQ.build([ws["A"]], None, [ws["run"]], [ws["cmp"]], q)
    finally:
        on[0] = False
    roots = tuple(os.path.realpath(x) + os.sep for x in (ws["A"], ws["P"], ws["run"], ws["cmp"], sys.prefix, sys.base_prefix,
                                                          os.path.dirname(os.path.dirname(EQ.__file__))))
    assert [p for p in seen if not p.startswith(roots) and not p.startswith("/dev/")] == []


def test_cli_writes_under_analysis_explain_and_capability(ws, capsys):
    assert cli.main(["explain", "contact", "--contact", "K14-G20", "--analysis", ws["A"]]) == 0
    out = capsys.readouterr().out
    assert "K14-G20 is listed by 2 of 2" in out
    files = sorted(os.listdir(os.path.join(ws["A"], "explain")))
    assert any(f.endswith(".json") for f in files) and any(f.endswith(".txt") for f in files)
    d = json.load(open(os.path.join(ws["A"], "explain", [f for f in files if f.endswith(".json")][0])))
    assert d["provenance"]["kind"] == "evidence_query" and d["query"]["name"] == "contact"
    assert cli.main(["explain", "--id", "x.json", "--analysis", ws["A"], "--no-write"]) == 2
    offered, _ = capabilities.available()
    c = next(c for c in offered if c["id"] == "explain_evidence")
    assert c["menu"] == "D" and c["status"] == "DESCRIPTIVE"
    r = capabilities.resolve(c["call"])(analysis=ws["A"], query="count", write_out=False)
    assert r["status"] == "OK" and r["statements"]


def test_docs_page_worked_examples_match(ws):
    md = open(os.path.join(B.ROOT, "docs", "evidence_and_methods.md")).read()
    assert trace.wording_audit(md) == []
    doc = EQ.build([ws["A"]], query="contact", contact="K14-G20")
    first = EQ.render_text(doc).splitlines()[2]
    assert first in md                                                             # the worked example line, verbatim
    from rnplens import methods_export as M
    txt = M.build(ws["A"])[1]
    assert "A total of 2 predicted structures of one protein-RNA construct (protein, 98 residues; RNA, 60 nucleotides) were" in txt
    for q in EQ.QUERIES:
        assert q in md

def test_not_like_for_like_run_size_counts_included_structures(tmp_path):
    """QA workflow-replay (2026-10-17): the run-size statement must compare the structures each run contributes
    (verdict INCLUDED), not the files found. Both runs here have two files, but one file of exec_B is excluded at
    import (truncated RNA), so the per-run denominators are 2 and 1."""
    P, A = B.project(tmp_path / "nlfl", {"exec_A": [(B.EXEC_A, .5, None), (B.diag(1), .1, None)],
                                         "exec_B": [(B.EXEC_B, .5, None), (B.diag(2), .1, B.delete_residues("B", {18, 19, 20}))]})
    man = json.load(open(os.path.join(P, "manifest.json")))
    assert [r["n_structures"] for r in man["runs"]] == [2, 2]
    assert sorted(s["verdict"] for s in man["structures"]).count("INCLUDED") == 3
    doc = EQ.build([A], query="not_like_for_like")
    size = [s for s in doc["statements"] if "runs differ in size" in s["text"]]
    assert len(size) == 1 and "2/1 included structures per run" in size[0]["text"], doc["statements"]
    _resolve(size[0])
    assert any("excluded at import" in s["text"] for s in doc["statements"])
    assert EQ.audit(doc) == []
