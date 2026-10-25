"""rnplens region edge cases: numbering offsets, modified nucleotides, incomplete structures, repeated chains,
incompatible constructs, three runs, multi-sample runs (designated versus additional samples). All fixtures are
edited copies of the bundled 7K9D example written under tmp_path."""
import json
import os
import shutil
import sys

import pytest

from rnplens import region

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures_v04", "region"))
import builders as B  # noqa: E402
from test_region import direct_filter, region_pairs  # noqa: E402


def _cov(doc):
    return {x["id"]: x["coverage"] for d in doc["runs"] for x in d["structures"]}


def test_numbering_offset_derived_copy(tmp_path):
    """RNA chain numbered 101-160 in the engine file: import writes a renumbered derived copy (accepted); region uses
    construct positions, reads coverage in the derived copy, and records the original numbering."""
    P, A = B.project(tmp_path, {"exec_A": [(B.EXEC_A, .5, B.renumber("B", 100))], "exec_B": [(B.EXEC_B, .5, None)]},
                     accept_derived=True)
    man = {s["id"]: s for s in json.load(open(os.path.join(P, "manifest.json")))["structures"]}
    assert man["s001"]["derived"] and man["s001"]["used_path"] != man["s001"]["path"]
    doc, _, _ = region.compute(P, A, "13-23")
    want, _ = direct_filter(A, P, (13, 23))
    assert region_pairs(doc) == want
    c = _cov(doc)["s001"]
    assert c["status"] == "COMPLETE" and "derived copy renumbered" in c["numbering"] and "101-160" in c["numbering"]
    x = next(x for d in doc["runs"] for x in d["structures"] if x["id"] == "s001")
    assert x["derived"] and x["used_sha256"] == man["s001"]["used_sha256"] != man["s001"]["original_sha256"]
    # same coordinates as the bundled example: the region listing is unchanged by the renumbering
    exp = json.load(open(os.path.join(B.ROOT, "tests", "fixtures_v04", "region", "expected_7K9D_rna13-23.json")))
    assert doc["summary"]["shared_by_all_runs"]["contacts"] == exp["shared_by_all_runs"]


def test_inexact_numbering_is_unresolved_never_guessed(tmp_path):
    """A used file whose numbering does not equal construct positions (here: offset, recorded as if exact) gives
    coverage UNRESOLVED; its unlisted contacts are 'not observed', never absent."""
    P, A = B.example_project(tmp_path)
    off = B.place(str(tmp_path / "off"), B.EXEC_B, 0, .5, B.renumber("B", 100))
    B.swap_used_file(P, A, "s002", off)
    doc, _, _ = region.compute(P, A, "13-23")
    c = _cov(doc)["s002"]
    assert c["status"] == "UNRESOLVED" and "not construct position" in c["reason"]
    for r in doc["contacts"]:
        v = r["per_run"]["exec_B"]
        assert v["status"] in ("PRESENT", "NOT_DETERMINED")
        if v["status"] == "NOT_DETERMINED":
            assert v["designated"]["observation"] == "NOT_OBSERVED" and r["only_in_run"] is None
    assert doc["summary"]["only_in_run"]["exec_A"]["count"] == 0          # nothing is 'only in A' without evidence


def test_modified_nucleotides(tmp_path):
    P, A = B.project(tmp_path, {"exec_A": [(B.EXEC_A, .5, B.rename_residue("B", 15, "PSU"))],
                                "exec_B": [(B.EXEC_B, .5, B.rename_residue("B", 15, "PSU"))]})
    man = json.load(open(os.path.join(P, "manifest.json")))
    assert all("PSU" in [c for ch in s["chains"] for c in ch.get("nonstandard_residues", [])] for s in man["structures"])
    doc, _, _ = region.compute(P, A, "13-23")
    want, _ = direct_filter(A, P, (13, 23))
    assert region_pairs(doc) == want
    for c in _cov(doc).values():
        assert c["status"] == "COMPLETE" and c["modified_nucleotides"] == {"15": ["PSU"]}
    rows15 = [r for r in doc["contacts"] if r["rna_position"] == 15]
    assert rows15 and all(r["rna_label"] == "U15" for r in rows15)            # letter from the construct


def test_incomplete_structure_excluded_at_import_is_listed_not_counted(tmp_path):
    """Residues 18-20 deleted from a copy of the 7K9D prediction: import excludes it (sequence differs); region lists
    it as not compared, with the reason, and it is in no denominator."""
    P, A = B.project(tmp_path, {"exec_A": [(B.EXEC_A, .5, None)],
                                "exec_B": [(B.EXEC_B, .5, None), (B.diag(1), .4, B.delete_residues("B", {18, 19, 20}))]})
    doc, _, _ = region.compute(P, A, "13-23")
    rb = next(d for d in doc["runs"] if d["run"] == "exec_B")
    assert rb["n_compared"] == 1 and len(rb["not_compared"]) == 1
    assert "INCOMPATIBLE" in rb["not_compared"][0]["reason"]
    assert all(r["per_run"]["exec_B"]["structures"]["of"] == 1 for r in doc["contacts"])


def test_incomplete_designated_structure_is_named_not_compared(tmp_path):
    P, A = B.project(tmp_path, {"exec_A": [(B.EXEC_A, .5, None)],
                                "exec_B": [(B.EXEC_B, .5, None), (B.diag(1), .9, B.delete_residues("B", {18, 19, 20}))]})
    code, out = region.run(P, A, "13-23")
    doc = json.load(open(os.path.join(out, "region.json")))
    rb = next(d for d in doc["runs"] if d["run"] == "exec_B")
    assert rb["designated_structure"] is None and rb["designated_not_compared"]["id"] == "s003"
    assert all(r["per_run"]["exec_B"]["designated"]["observation"] == "NOT_COMPARED" for r in doc["contacts"])
    assert "s003, not compared" in open(os.path.join(out, "region.html")).read()


def test_incomplete_used_file_marks_coverage_unresolved(tmp_path):
    """The used file lacks residues 18-20 (inconsistent project made on purpose): the chain cannot be mapped exactly,
    so the structure's coverage is UNRESOLVED and the run-level counts state the denominators."""
    P, A = B.example_project(tmp_path)
    trunc = B.place(str(tmp_path / "trunc"), B.EXEC_B, 0, .5, B.delete_residues("B", {18, 19, 20}))
    B.swap_used_file(P, A, "s002", trunc)
    doc, _, _ = region.compute(P, A, "13-23")
    c = _cov(doc)["s002"]
    assert c["status"] == "UNRESOLVED" and "57 residues" in c["reason"]
    v = [r["per_run"]["exec_B"]["structures"] for r in doc["contacts"] if r["per_run"]["exec_B"]["status"] != "PRESENT"]
    assert v and all(x["count"] == 0 and x["of"] == 1 and x["not_observed"] == 1 and x["observable"] == 0 for x in v)
    assert doc["summary"]["per_run"]["exec_B"]["coverage"] == {"COMPLETE": 0, "PARTIAL": 0, "UNRESOLVED": 1}


def test_unresolved_position_is_not_observed_never_no_contact(tmp_path):
    """Nucleotide 20 has no heavy atom in run B's structure (residue kept, so import and Report accept the file):
    contacts at position 20 listed by run A are 'not observed' in run B, not 'found only in run A'."""
    P, A = B.project(tmp_path, {"exec_A": [(B.EXEC_A, .5, None)], "exec_B": [(B.EXEC_B, .5, B.hydrogen_only("B", 20))]})
    code, out = region.run(P, A, "13-23")
    doc = json.load(open(os.path.join(out, "region.json")))
    want, _ = direct_filter(A, P, (13, 23))
    assert region_pairs(doc) == want
    assert _cov(doc)["s002"]["status"] == "PARTIAL" and _cov(doc)["s002"]["unresolved_rna_positions"] == [20]
    at20 = [r for r in doc["contacts"] if r["rna_position"] == 20]
    assert at20
    for r in at20:
        assert r["per_run"]["exec_B"]["status"] == "NOT_DETERMINED" and r["only_in_run"] is None
        assert r["per_run"]["exec_B"]["designated"]["observation"] == "NOT_OBSERVED"
        assert r["presence"] == "PRESENT_IN_SOME_RUNS" and r["runs"]["not_determined"] == ["exec_B"]
    assert doc["summary"]["not_determined"]["count"] == len(at20)
    html = open(os.path.join(out, "region.html")).read()
    assert "not observed" in html and "unresolved RNA 20" in html


def test_repeated_rna_chains(tmp_path):
    """Two RNA copies (chain C = translated copy of B). Report takes the union over copies; region checks coverage in
    every copy, so a position missing in one copy only is unresolved (conservative)."""
    P, A = B.project(tmp_path, {"exec_A": [(B.EXEC_A, .5, B.duplicate_chain("B", "C"))],
                                "exec_B": [(B.EXEC_B, .5, B.compose(B.duplicate_chain("B", "C"), B.hydrogen_only("C", 20)))]})
    rr = json.load(open(os.path.join(A, "report", "result.json")))
    assert [o["n_rna_copies"] for o in rr["per_output"]] == [2, 2]
    doc, _, _ = region.compute(P, A, "13-23")
    want, _ = direct_filter(A, P, (13, 23))
    assert region_pairs(doc) == want
    c = _cov(doc)
    assert c["s001"]["rna_chains"] == ["B", "C"] and c["s001"]["status"] == "COMPLETE"
    assert c["s002"]["status"] == "PARTIAL" and c["s002"]["unresolved_rna_positions"] == [20]


def test_incompatible_constructs_are_refused(tmp_path):
    P, A = B.example_project(tmp_path)
    # construct FASTA no longer matches the manifest
    P2 = tmp_path / "p2"; shutil.copytree(P, P2)
    open(P2 / "construct_rna.fasta", "w").write(">rna\n" + "A" * 60 + "\n")
    with pytest.raises(region.RegionError, match="incompatible constructs"):
        region.compute(str(P2), A, "13-23")
    # analysis of another construct
    A2 = tmp_path / "a2"; shutil.copytree(A, A2)
    S = json.load(open(A2 / "summary.json")); S["construct"]["rna_length"] = 59
    json.dump(S, open(A2 / "summary.json", "w"))
    with pytest.raises(region.RegionError, match="incompatible constructs"):
        region.compute(P, str(A2), "13-23")


def test_mutated_structure_is_excluded_and_listed(tmp_path):
    """A prediction of a different RNA sequence (G20 -> A) cannot be compared; it is listed with the import reason."""
    P, A = B.project(tmp_path, {"exec_A": [(B.EXEC_A, .5, None)],
                                "exec_B": [(B.EXEC_B, .5, None), (B.diag(2), .1, B.rename_residue("B", 20, "  A", hetatm=False))]})
    doc, _, _ = region.compute(P, A, "13-23")
    nc = [x for d in doc["runs"] for x in d["not_compared"]]
    assert len(nc) == 1 and "differ from the declared construct" in nc[0]["reason"]


def test_three_runs_no_two_run_formula(tmp_path):
    P, A = B.project(tmp_path, {"exec_A": [(B.EXEC_A, .5, None)], "exec_B": [(B.EXEC_B, .5, None)],
                                "exec_C": [(B.diag(3), .5, None)]})
    code, out = region.run(P, A, "13-23")
    doc = json.load(open(os.path.join(out, "region.json")))
    S = doc["summary"]
    assert S["n_runs_compared"] == 3 and "3 runs" in S["comparison_mode"] and "no agreement formula" in S["comparison_mode"]
    want, ids = direct_filter(A, P, (13, 23))
    sets = {x["run"]: want[x["id"]] for x in ids.values()}
    allc = set().union(*sets.values())
    assert S["shared_by_all_runs"]["count"] == len(set.intersection(*sets.values()))
    for r in ("exec_A", "exec_B", "exec_C"):
        others = set().union(*[v for k, v in sets.items() if k != r])
        assert S["only_in_run"][r]["count"] == len(sets[r] - others)
    assert sum(S["present_in_j_runs"]["counts"].values()) == len(allc) == S["n_contacts_in_range"]["count"]
    for j in (1, 2, 3):
        assert S["present_in_j_runs"]["counts"][str(j)] == sum(1 for c in allc if sum(c in v for v in sets.values()) == j)
    for row in doc["contacts"]:
        assert row["runs"]["of"] == 3 and row["runs"]["count_present"] == len(row["runs"]["present"])
    html = open(os.path.join(out, "region.html")).read()
    assert "present in exactly 2 of 3 runs" in html and "agreement" not in json.dumps(S).replace("no agreement formula", "")


def test_designated_versus_additional_samples(tmp_path):
    """One run with four samples (designated = highest Boltz-2 confidence_score, model 3 here) and one single-sample
    run: per run, the designated structure and the k of n samples are reported separately."""
    P, A = B.project(tmp_path, {"exec_A": [(B.EXEC_A, .5, None)],
                                "exec_M": [(B.diag(k), s, None) for k, s in ((1, .2), (2, .3), (3, .9), (4, .4))]})
    doc, tsv, _ = region.compute(P, A, "13-23")
    want, ids = direct_filter(A, P, (13, 23))
    rm = next(d for d in doc["runs"] if d["run"] == "exec_M")
    man = {s["id"]: s for s in json.load(open(os.path.join(P, "manifest.json")))["structures"]}
    des = rm["designated_structure"]
    assert man[des]["designated"] and man[des]["sample"] == "7K9D_model_2"   # third file placed, score .9
    assert rm["structures"][0]["id"] == des and len(rm["structures"]) == 4
    others = [x["id"] for x in rm["structures"] if x["id"] != des]
    for r in doc["contacts"]:
        c = (r["protein_position"], r["rna_position"])
        v = r["per_run"]["exec_M"]
        assert v["designated"]["observation"] == ("PRESENT" if c in want[des] else "ABSENT")
        assert v["structures"]["count"] == sum(c in want[i] for i in [des] + others) and v["structures"]["of"] == 4
        assert v["additional_samples"]["count"] == sum(c in want[i] for i in others) and v["additional_samples"]["of"] == 3
        assert [w["sample"] for w in v["structures"]["with_contact"]] == [man[w["id"]]["sample"] for w in v["structures"]["with_contact"]]
    assert region_pairs(doc) == want
    assert {row[8] for row in tsv} == {"exec_A", "exec_M"}
