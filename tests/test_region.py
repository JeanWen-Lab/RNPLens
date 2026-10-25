"""rnplens region: parity with Report's per-structure records, run classification, outputs, determinism, wording,
data access, CLI and capability registration (bundled 7K9D example only)."""
import copy
import json
import os
import shutil
import sys

import pytest

import importlib.util as _ilu
HAVE_MPL = _ilu.find_spec("matplotlib") is not None   # optional extra 'rnplens[html]'

from rnplens import capabilities, cli, provenance as pv, region, trace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures_v04", "region"))
import builders as B  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures_v04", "region")


@pytest.fixture(scope="module")
def ex(tmp_path_factory):
    t = tmp_path_factory.mktemp("region_ex")
    return B.example_project(t)


def direct_filter(A, P, rna, prot=None, runs=None):
    """The reference: Report's contacts_by_output.json filtered by hand, keyed by structure id."""
    cbo = json.load(open(os.path.join(A, "report", "contacts_by_output.json")))
    man = json.load(open(os.path.join(P, "manifest.json")))
    ids = {"%s|%s" % (s["engine"], s["execution"]): s for s in man["structures"]}
    out = {}
    for k, cl in cbo.items():
        if runs and ids[k]["run"] not in runs:
            continue
        out[ids[k]["id"]] = {(p, r) for p, r in cl if rna[0] <= r <= rna[1] and (prot is None or prot[0] <= p <= prot[1])}
    return out, ids


def region_pairs(doc):
    got = {}
    for d in doc["runs"]:
        for x in d["structures"]:
            got[x["id"]] = set()
    for row in doc["contacts"]:
        for v in row["per_run"].values():
            for w in v["structures"]["with_contact"]:
                got[w["id"]].add((row["protein_position"], row["rna_position"]))
    return got


@pytest.mark.parametrize("rna,prot", [((13, 23), None), ((1, 60), None), ((13, 23), (10, 20)), ((55, 60), (30, 55))])
def test_parity_with_direct_filter_of_contacts_by_output(ex, rna, prot):
    P, A = ex
    doc, tsv, _ = region.compute(P, A, "%d-%d" % rna, "%d-%d" % prot if prot else None)
    want, _ = direct_filter(A, P, rna, prot)
    assert region_pairs(doc) == want
    assert {(r["protein_position"], r["rna_position"]) for r in doc["contacts"]} == set().union(*want.values())
    # per-run counts are the number of structures listing the contact
    for row in doc["contacts"]:
        key = (row["protein_position"], row["rna_position"])
        for run_, v in row["per_run"].items():
            ids = [x["id"] for d in doc["runs"] if d["run"] == run_ for x in d["structures"]]
            assert v["structures"]["count"] == sum(key in want[i] for i in ids) and v["structures"]["of"] == len(ids)
    assert len(tsv) == len(doc["contacts"]) * len(doc["summary"]["runs_compared"])


def test_classes_equal_set_operations_on_the_records(ex):
    P, A = ex
    doc, _, _ = region.compute(P, A, "13-23")
    want, ids = direct_filter(A, P, (13, 23))
    a, b = want["s001"], want["s002"]
    S = doc["summary"]
    lab = lambda pairs: sorted(pairs)
    got_shared = sorted((r["protein_position"], r["rna_position"]) for r in doc["contacts"] if r["presence"] == "SHARED_BY_ALL_RUNS")
    assert got_shared == lab(a & b) and S["shared_by_all_runs"]["count"] == len(a & b)
    only_a = sorted((r["protein_position"], r["rna_position"]) for r in doc["contacts"] if r["only_in_run"] == "exec_A")
    only_b = sorted((r["protein_position"], r["rna_position"]) for r in doc["contacts"] if r["only_in_run"] == "exec_B")
    assert only_a == lab(a - b) and only_b == lab(b - a)
    assert S["n_contacts_in_range"]["count"] == len(a | b)


def test_regression_against_frozen_worked_example(ex):
    """Frozen expectation for docs/region.md (7K9D example, exec_A vs exec_B, RNA 13-23)."""
    P, A = ex
    doc, _, _ = region.compute(P, A, "13-23")
    exp = json.load(open(os.path.join(FIX, "expected_7K9D_rna13-23.json")))
    S = doc["summary"]
    assert S["shared_by_all_runs"]["contacts"] == exp["shared_by_all_runs"]
    assert {k: v["contacts"] for k, v in S["only_in_run"].items()} == exp["only_in_run"]
    assert S["n_contacts_in_range"]["count"] == exp["n_contacts_in_range"]
    assert doc["region"]["rna"]["sequence"] == exp["rna_sequence"]


def test_identifiers_and_letters_come_from_the_construct(ex):
    P, A = ex
    doc, _, _ = region.compute(P, A, "13-23")
    man = json.load(open(os.path.join(P, "manifest.json")))
    ps, rs = man["construct"]["protein_sequence"], man["construct"]["rna_sequence"]
    for r in doc["contacts"]:
        assert r["protein_label"] == "%s%d" % (ps[r["protein_position"] - 1], r["protein_position"])
        assert r["rna_label"] == "%s%d" % (rs[r["rna_position"] - 1], r["rna_position"])
    assert any(r["label"] == "K14-G20" for r in doc["contacts"])


def test_provenance_on_structures_rows_and_definition(ex):
    P, A = ex
    doc, tsv, _ = region.compute(P, A, "13-23")
    assert set(doc) >= {"provenance", "region", "contact_definition", "runs", "contacts", "summary", "limits"}
    S = json.load(open(os.path.join(A, "summary.json")))
    assert doc["contact_definition"]["text"] == S["contacts"]["definition"]          # verbatim
    man = {s["id"]: s for s in json.load(open(os.path.join(P, "manifest.json")))["structures"]}
    for d in doc["runs"]:
        for x in d["structures"]:
            m = man[x["id"]]
            assert (x["engine"], x["run"], x["sample"], x["designated"], x["used_sha256"]) == \
                   (m["engine"], m["run"], m["sample"], m["designated"], m["used_sha256"])
            assert x["evidence_id"].startswith("region_13-23/region.json#/runs/")
    for i, r in enumerate(doc["contacts"]):
        assert r["evidence_id"] == pv.evidence_id("region_13-23/region.json", "/contacts/%d" % i)
    assert all(row[-1].startswith("region_13-23/region.json#/contacts/") and row[8] in ("exec_A", "exec_B") and row[10]
               for row in tsv)
    assert region.RECURRENCE_LIMIT in doc["limits"]
    assert doc["provenance"]["kind"] == "region_contacts" and doc["provenance"]["rnplens_version"] == "0.4.0.dev0"
    ins = {os.path.basename(x["path"]) for x in doc["provenance"]["inputs"]}
    assert {"manifest.json", "contacts_by_output.json", "construct_rna.fasta", "summary.json"} <= ins


def test_evidence_ids_resolve_to_the_document(ex, tmp_path):
    P, A = ex
    code, out = region.run(P, A, "14-16", replace=True)
    assert code == 0
    doc = json.load(open(os.path.join(out, "region.json")))

    def resolve(ev):
        path, ptr = ev.split("#", 1)
        obj = json.load(open(os.path.join(A, path)))
        for part in [p for p in ptr.split("/") if p]:
            part = part.replace("~1", "/").replace("~0", "~")
            obj = obj[int(part)] if isinstance(obj, list) else obj[part]
        return obj
    assert resolve(doc["contacts"][0]["evidence_id"]) == doc["contacts"][0]
    assert resolve(doc["summary"]["shared_by_all_runs"]["evidence_id"])["count"] == doc["summary"]["shared_by_all_runs"]["count"]
    assert resolve(doc["contact_definition"]["evidence_id"]) == doc["contact_definition"]["text"]


def test_outputs_written_atomically_and_html_audited(ex):
    P, A = ex
    code, out = region.run(P, A, "13-23", replace=True)
    assert code == 0 and os.path.basename(out) == "region_13-23"
    files = sorted(os.listdir(out))
    assert files == ["region.html", "region.json", "region_contacts.tsv"] + (["region_map.png"] if HAVE_MPL else [])
    html = open(os.path.join(out, "region.html")).read()
    assert trace.wording_audit(html) == [] and "not evidence of correctness" in html
    if HAVE_MPL:
        assert open(os.path.join(out, "region_map.png"), "rb").read(8) == b"\x89PNG\r\n\x1a\n"
    doc = json.load(open(os.path.join(out, "region.json")))
    assert doc["figure"]["state"] == ("DRAWN" if HAVE_MPL else "NOT_DRAWN_MATPLOTLIB_MISSING")


def test_reuses_unchanged_result_and_refuses_overwrite_when_inputs_changed(ex):
    P, A = ex
    code, out = region.run(P, A, "20-22", replace=True)
    before = open(os.path.join(out, "region.json"), "rb").read()
    assert region.run(P, A, "20-22") == (0, out)                       # same inputs and version: reused, untouched
    assert open(os.path.join(out, "region.json"), "rb").read() == before
    doc = json.loads(before)
    doc["provenance"]["inputs"][0]["sha256"] = "0" * 64                  # a recorded input no longer matches
    open(os.path.join(out, "region.json"), "w").write(json.dumps(doc))
    with pytest.raises(region.RegionError, match="nothing is overwritten"):
        region.run(P, A, "20-22")
    assert cli.main(["region", P, A, "--rna", "20-22"]) == 2


def test_protein_range_directory_name(ex):
    P, A = ex
    code, out = region.run(P, A, "13-23", "10-20", replace=True)
    assert code == 0 and os.path.basename(out) == "region_13-23_p10-20"
    doc = json.load(open(os.path.join(out, "region.json")))
    assert all(10 <= r["protein_position"] <= 20 for r in doc["contacts"])


def test_determinism_byte_identical_apart_from_created_utc(ex):
    P, A = ex
    code, out = region.run(P, A, "17-21", replace=True)
    j1 = open(os.path.join(out, "region.json")).read()
    t1 = open(os.path.join(out, "region_contacts.tsv"), "rb").read()
    h1 = open(os.path.join(out, "region.html"), "rb").read()
    code, out = region.run(P, A, "17-21", replace=True)
    j2 = open(os.path.join(out, "region.json")).read()
    strip = lambda s: [l for l in s.splitlines() if '"created_utc"' not in l]
    assert strip(j1) == strip(j2)
    assert t1 == open(os.path.join(out, "region_contacts.tsv"), "rb").read()
    assert h1 == open(os.path.join(out, "region.html"), "rb").read()


@pytest.mark.parametrize("rna,msg", [("23-13", "reversed"), ("0-10", "outside"), ("50-61", "outside"),
                                     ("abc", "not 'start-end'"), ("1-2-3", "not 'start-end'")])
def test_range_validation(ex, rna, msg):
    P, A = ex
    with pytest.raises(region.RegionError, match=msg):
        region.compute(P, A, rna)


def test_protein_range_validation_and_cli_message(ex, capsys):
    P, A = ex
    with pytest.raises(region.RegionError, match="outside the declared protein construct"):
        region.compute(P, A, "13-23", "90-99")
    assert cli.main(["region", P, A, "--rna", "70-80"]) == 2
    assert "outside the declared RNA construct (positions 1-60)" in capsys.readouterr().err


def test_run_selection_and_unknown_run(ex):
    P, A = ex
    doc, _, _ = region.compute(P, A, "13-23", runs="exec_A")
    assert doc["summary"]["runs_compared"] == ["exec_A"] and doc["region"]["output_dir"].startswith("region_13-23_runs-")
    assert all(r["presence"] == "SHARED_BY_ALL_RUNS" for r in doc["contacts"])
    want, _ = direct_filter(A, P, (13, 23), runs=["exec_A"])
    assert region_pairs(doc) == want
    with pytest.raises(region.RegionError, match="unknown run"):
        region.compute(P, A, "13-23", runs="exec_Z")


def test_no_contacts_in_range(ex):
    P, A = ex
    code, out = region.run(P, A, "30-40", replace=True)
    doc = json.load(open(os.path.join(out, "region.json")))
    assert code == 0 and doc["contacts"] == [] and doc["summary"]["status"] == "NO_CONTACTS_IN_RANGE"
    assert doc["summary"]["n_contacts_in_range"]["count"] == 0 and doc["summary"]["n_structures_compared"] == 2
    html = open(os.path.join(out, "region.html")).read()
    assert "No contact in RNA 30-40 is listed by any of the 2 compared structure(s)" in html
    assert os.path.exists(os.path.join(out, "region_map.png")) is HAVE_MPL


def test_matplotlib_missing_degrades_gracefully(ex, monkeypatch):
    P, A = ex
    monkeypatch.setitem(sys.modules, "matplotlib", None)
    code, out = region.run(P, A, "24-26", replace=True)
    doc = json.load(open(os.path.join(out, "region.json")))
    assert code == 0 and doc["figure"]["state"] == "NOT_DRAWN_MATPLOTLIB_MISSING"
    assert not os.path.exists(os.path.join(out, "region_map.png"))
    assert "matplotlib is not installed" in open(os.path.join(out, "region.html")).read()


def test_wording_audit_blocks_the_output(ex, monkeypatch):
    P, A = ex
    monkeypatch.setattr(region, "render_text", lambda doc: "the best contact")
    code, msg = region.run(P, A, "27-29", replace=True)
    out = os.path.join(A, "region_27-29")
    assert code == 1 and os.path.exists(os.path.join(out, "WORDING_AUDIT_FAILED.txt"))
    assert not os.path.exists(os.path.join(out, "region.json"))


def test_no_two_run_agreement_number_anywhere(ex):
    P, A = ex
    doc, _, _ = region.compute(P, A, "13-23")
    txt = json.dumps(doc)
    for banned in ("register_agreement", "surface_agreement", "jaccard", "agreement_score"):
        assert banned not in txt


def test_data_access_only_declared_inputs(ex):
    """Every file Python opens during the computation is a declared input (or library code)."""
    P, A = ex
    seen = []
    active = [True]

    def hook(ev, args):
        if active[0] and ev == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            seen.append(os.path.realpath(os.fsdecode(args[0])))
    sys.addaudithook(hook)
    try:
        doc, _, _ = region.compute(P, A, "13-23")
    finally:
        active[0] = False
    allowed = {os.path.realpath(x["path"]) for x in doc["provenance"]["inputs"]}
    lib = tuple(os.path.realpath(x) + os.sep for x in {sys.prefix, sys.base_prefix,
                os.path.dirname(os.path.dirname(os.path.abspath(region.__file__)))})
    bad = [p for p in seen if p not in allowed and not p.startswith(lib) and not p.startswith("/dev/")]
    assert bad == []
    assert any(p.endswith("contacts_by_output.json") for p in seen)


def test_malformed_and_tampered_records_are_refused(ex, tmp_path):
    P, A = ex
    A2 = tmp_path / "a2"
    shutil.copytree(A, A2, ignore=shutil.ignore_patterns("region_*"))
    cp = A2 / "report" / "contacts_by_output.json"
    cbo = json.load(open(cp))
    k = sorted(cbo)[0]
    cbo[k] = cbo[k] + [[14, 22]]
    json.dump(cbo, open(cp, "w"))
    with pytest.raises(region.RegionError, match="changed after Report wrote it"):
        region.compute(P, str(A2), "13-23")
    os.unlink(A2 / "report" / "rnplens_run.json")
    cbo["BOLTZ2|exec_Q#x"] = [[1, 1]]
    json.dump(cbo, open(cp, "w"))
    with pytest.raises(region.RegionError, match="names no structure"):
        region.compute(P, str(A2), "13-23")
    cbo.pop("BOLTZ2|exec_Q#x"); cbo[k] = [[14, 99]]
    json.dump(cbo, open(cp, "w"))
    with pytest.raises(region.RegionError, match="not a pair of construct positions"):
        region.compute(P, str(A2), "13-23")
    open(cp, "w").write("{not json")
    with pytest.raises(region.RegionError, match="not valid JSON"):
        region.compute(P, str(A2), "13-23")


def test_cli_and_capabilities(ex, capsys):
    P, A = ex
    assert cli.main(["region", P, A, "--rna", "18-20", "--replace"]) == 0
    assert "Recurrence among predictions is not evidence of correctness." in capsys.readouterr().out
    offered, _ = capabilities.available()
    caps = {c["id"]: c for c in offered}
    assert caps["region_contacts"]["menu"] == "B" and caps["region_run_comparison"]["menu"] == "C"
    assert all(caps[k]["status"] == "DESCRIPTIVE" for k in ("region_contacts", "region_run_comparison"))
    fn = capabilities.resolve(caps["region_contacts"]["call"])
    res = fn(project=P, analysis=A, rna_range="18-20", replace=True)
    assert res["status"] == "OK" and any(f.endswith("region.json") for f in res["outputs"])
    assert fn(project=P, analysis=A, rna_range="20-18")["status"] == "REFUSED"


def test_worked_example_in_docs_matches(ex):
    P, A = ex
    doc, _, _ = region.compute(P, A, "13-23")
    S = doc["summary"]
    md = open(os.path.join(B.ROOT, "docs", "region.md")).read()
    assert "rnplens region" in md and "13-23" in md
    for phrase in ("%d contacts" % S["n_contacts_in_range"]["count"], "%d are shared by both runs" % S["shared_by_all_runs"]["count"],
                   ", ".join(S["only_in_run"]["exec_A"]["contacts"]), ", ".join(S["only_in_run"]["exec_B"]["contacts"])):
        assert phrase in md, phrase
    assert trace.wording_audit(md) == []
