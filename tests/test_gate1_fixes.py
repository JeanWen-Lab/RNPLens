"""Gate-1 regression tests (2026-10-16) for the 0.3.0.dev0 first-use test findings M1-M4 and for the withheld
four-axis geometry route. Each test names the finding it covers."""
import copy
import csv
import json
import os
import shutil
import subprocess
import sys

import pytest

from rnplens import analyse, compare, importer, trace

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
PRED = os.path.join(EX, "reference_based", "7K9D_prediction.pdb")
REF = os.path.join(EX, "reference_based", "7K9D_reference.cif")
PFA, RFA = os.path.join(EX, "reference_based", "7K9D_protein.fasta"), os.path.join(EX, "reference_based", "7K9D_rna.fasta")
PS, RS = importer.read_sequence_arg(PFA), importer.read_sequence_arg(RFA)
RF = os.path.join(EX, "reference_free", "report_7K9D")


def _flat_run(d, n, scores=None, with_conf=True, src=None):
    """A Boltz-2 output copied out of its nesting: <T>_model_<k>.pdb + confidence_<T>_model_<k>.json."""
    d.mkdir(parents=True)
    for k in range(n):
        shutil.copy(src or PRED, d / ("X_model_%d.pdb" % k))
        with open(d / ("X_model_%d.pdb" % k), "a") as fh:
            fh.write("REMARK distinct copy %s %d\n" % (d.name, k))
        if with_conf:
            json.dump({"confidence_score": (scores or [0.5] * n)[k], "iptm": 0.8}, open(d / ("confidence_X_model_%d.json" % k), "w"))
    return d


# ---------------------------------------------------------------- M1
def test_M1_flat_boltz2_folder_is_recognised_without_engine(tmp_path):
    src = _flat_run(tmp_path / "run1", 3, scores=[0.2, 0.9, 0.4])
    assert importer.run([str(src)], PS, RS, str(tmp_path / "p")) == 0
    m = json.load(open(tmp_path / "p" / "manifest.json"))
    assert m["counts"]["included"] == 3 and m["counts"]["unrecognised"] == 0
    assert {s["engine"] for s in m["structures"]} == {"BOLTZ2"}
    assert [s["designated"] for s in m["structures"]] == [False, True, False]      # highest confidence_score
    assert all("confidence_*.json" in s["engine_source"] for s in m["structures"])
    assert m["runs"][0]["designated_rule"] == "highest Boltz-2 confidence_score"


def test_M1_name_pattern_without_boltz_confidence_is_not_guessed(tmp_path, capsys):
    src = _flat_run(tmp_path / "run1", 2, with_conf=False)
    json.dump({"ranking_score": 0.3}, open(src / "confidence_X_model_0.json", "w"))   # not Boltz-2's key
    assert importer.run([str(src)], PS, RS, str(tmp_path / "p")) == importer.EXIT_REFUSED
    assert not (tmp_path / "p").exists()
    err = capsys.readouterr().err
    assert "Nothing was written" in err and "--engine" in err


def test_M1_partial_recognition_reports_the_rest(tmp_path, capsys):
    src = _flat_run(tmp_path / "run1", 2)
    shutil.copy(PRED, src / "loose_copy.pdb")
    with open(src / "loose_copy.pdb", "a") as fh:
        fh.write("REMARK loose\n")
    assert importer.run([str(src)], PS, RS, str(tmp_path / "p")) == 0
    m = json.load(open(tmp_path / "p" / "manifest.json"))
    assert m["counts"]["included"] == 2 and m["unrecognised_files"] == [str(src / "loose_copy.pdb")]
    assert "no recognised layout were not imported" in capsys.readouterr().out


# ---------------------------------------------------------------- M2
def _tsvs(d, pred_before, pred_after, ref, ps="protein.fasta", rs="rna.fasta"):
    d.mkdir(parents=True, exist_ok=True)
    for name, pred in (("before.tsv", pred_before), ("after.tsv", pred_after)):
        with open(d / name, "w", newline="") as fh:
            w = csv.writer(fh, delimiter="\t"); w.writerow(["target_id", "prediction", "protein_sequence", "rna_sequence"])
            w.writerow(["t1", pred, ps, rs])
    with open(d / "refs.tsv", "w") as fh:
        fh.write("target_id\treference\nt1\t%s\n" % ref)


def test_M2_relative_paths_resolve_against_the_tsv_directory(tmp_path, monkeypatch):
    d = tmp_path / "inputs"
    (d / "data").mkdir(parents=True)
    for f in (PRED, REF):
        shutil.copy(f, d / "data" / os.path.basename(f))
    shutil.copy(PFA, d / "protein.fasta"); shutil.copy(RFA, d / "rna.fasta")
    _tsvs(d, "data/7K9D_prediction.pdb", "data/7K9D_prediction.pdb", "data/7K9D_reference.cif")
    elsewhere = tmp_path / "cwd"; elsewhere.mkdir(); monkeypatch.chdir(elsewhere)
    assert compare.run(str(d / "before.tsv"), str(d / "after.tsv"), str(d / "refs.tsv"), str(tmp_path / "out")) == 0
    runs = json.load(open(tmp_path / "out" / "evaluate_runs.json"))
    assert all(r["exit"] == 0 for r in runs)
    assert open(tmp_path / "out" / "evaluate" / "before" / "t1.in" / "protein.fasta").read().split("\n")[1] == PS


def test_M2_missing_input_is_refused_not_classified(tmp_path, capsys):
    d = tmp_path / "inputs"
    shutil.copy  # noqa
    d.mkdir()
    shutil.copy(PFA, d / "protein.fasta"); shutil.copy(RFA, d / "rna.fasta")
    _tsvs(d, "no_such_model.pdb", PRED, REF)
    assert compare.run(str(d / "before.tsv"), str(d / "after.tsv"), str(d / "refs.tsv"), str(tmp_path / "out")) == 2
    assert not (tmp_path / "out").exists()
    err = capsys.readouterr().err
    assert "before prediction file not found" in err and "TSV's own directory" in err


def test_M2_missing_sequence_file_is_refused(tmp_path):
    d = tmp_path / "inputs"; d.mkdir()
    _tsvs(d, PRED, PRED, REF, ps="missing_protein.fasta", rs=RS)
    assert compare.run(str(d / "before.tsv"), str(d / "after.tsv"), str(d / "refs.tsv"), str(tmp_path / "out")) == 2
    assert not (tmp_path / "out").exists()


def test_M2_evaluate_refusal_stops_with_nonzero_exit(tmp_path):
    # an unreadable reference passes the existence preflight but Evaluate refuses it (exit 2): that is a run
    # error, reported as RUN_FAILED with a non-zero exit, never as NOT_EVALUABLE_IN_BOTH
    d = tmp_path / "inputs"; d.mkdir()
    (d / "bad.cif").write_text("garbage\n")
    _tsvs(d, PRED, PRED, "bad.cif", ps=PS, rs=RS)
    assert compare.run(str(d / "before.tsv"), str(d / "after.tsv"), str(d / "refs.tsv"), str(tmp_path / "out")) == 1
    rows = list(csv.DictReader(open(tmp_path / "out" / "comparison.tsv"), delimiter="\t"))
    assert {r["class"] for r in rows} == {"RUN_FAILED"}
    s = json.load(open(tmp_path / "out" / "comparison_summary.json"))
    assert s["evaluate_run_failures"] == ["t1"] and s["metrics"]["dockq"]["like_for_like_n"] == 0


def test_M2_empty_prediction_is_a_named_outcome_not_a_run_failure(tmp_path):
    # an empty structure file is read by Evaluate and recorded as NO_VALUE (exit 0): a scientific outcome
    d = tmp_path / "inputs"; d.mkdir()
    (d / "empty.pdb").write_text("")
    _tsvs(d, PRED, "empty.pdb", REF, ps=PS, rs=RS)
    assert compare.run(str(d / "before.tsv"), str(d / "after.tsv"), str(d / "refs.tsv"), str(tmp_path / "out")) == 0
    rows = {r["metric"]: r["class"] for r in csv.DictReader(open(tmp_path / "out" / "comparison.tsv"), delimiter="\t")}
    assert rows["dockq"] == "NEWLY_UNEVALUABLE"


# ---------------------------------------------------------------- M3 (+ m5, m6)
def test_M3_one_target_has_no_interval_and_unchanged_is_listed(tmp_path):
    d = tmp_path / "inputs"; d.mkdir()
    _tsvs(d, PRED, PRED, REF, ps=PS, rs=RS)
    assert compare.run(str(d / "before.tsv"), str(d / "after.tsv"), str(d / "refs.tsv"), str(tmp_path / "out")) == 0
    s = json.load(open(tmp_path / "out" / "comparison_summary.json"))
    for m in ("dockq", "fnat", "irmsd", "lrmsd"):
        r = s["metrics"][m]
        assert r["ci95_bootstrap"] is None and r["interval_note"] == "n = 1 resampling unit: no interval"
        assert r["targets_by_class"] == {"UNCHANGED": ["t1"]}
    txt = open(tmp_path / "out" / "comparison_summary.txt").read()
    assert "bootstrap interval" not in txt and "no threshold of practical relevance" in txt
    assert b"\r\n" not in open(tmp_path / "out" / "comparison.tsv", "rb").read()
    assert set(s["metrics"]) == {"dockq", "fnat", "irmsd", "lrmsd"}
    assert s["withheld"]["route"] == "geometry"


# ---------------------------------------------------------------- M4
@pytest.fixture(scope="module")
def two_runs_unequal(tmp_path_factory):
    t = tmp_path_factory.mktemp("m4")
    # run1: three samples (designated = highest confidence), run2: one sample; the engine has 4 structures, so
    # Report's per-engine repeat agreement is not computed, but the two runs can be compared
    a = os.path.join(RF, "exec_A", "7K9D_model_0.pdb"); b = os.path.join(RF, "exec_B", "7K9D_model_0.pdb")
    _flat_run(t / "in" / "run1", 3, scores=[0.3, 0.8, 0.5], src=a)
    _flat_run(t / "in" / "run2", 1, scores=[0.6], src=b)
    assert importer.run([str(t / "in")], PS, RS, str(t / "p"), "m4") == 0
    assert analyse.run(str(t / "p"), str(t / "r")) == 0
    return t


def test_M4_two_runs_get_reports_repeat_agreement_between_designated_structures(two_runs_unequal):
    t = two_runs_unequal
    S = json.load(open(t / "r" / "summary.json"))
    m = json.load(open(t / "p" / "manifest.json"))
    assert S["repeat_agreement"]["BOLTZ2"]["status"] == "NOT_COMPUTED"            # unchanged rc3 behaviour
    v = S["run_repeat_agreement"]["BOLTZ2"]
    assert v["status"] == "COMPUTED_BY_REPORT"
    des = {s["id"]: s for s in m["structures"] if s["designated"]}
    assert set(v["structures"]) == set(des) and len({des[x]["run"] for x in v["structures"]}) == 2
    # the values are Report's own two-output computation on exactly those two files
    direct = t / "direct"
    c = json.load(open(t / "p" / "report_contract.json"))
    c["outputs"] = [o for o in c["outputs"] if o["structure_path"] in {des[x]["used_path"] for x in v["structures"]}]
    json.dump(c, open(t / "c2.json", "w"))
    subprocess.run([sys.executable, "-m", "rnplens", "report", "run", str(t / "c2.json"), "--out", str(direct)], check=True,
                   capture_output=True)
    ra = json.load(open(direct / "result.json"))["summary"]["repeat_agreement"]["BOLTZ2"]
    for f in ("surface_agreement", "register_agreement", "rna_pose_difference_A"):
        assert v[f] == ra[f]
    html = open(t / "r" / "summary.html").read()
    assert "between runs" in html and trace.wording_audit(html) == []


def test_M4_trace_refuses_tampered_run_agreement(two_runs_unequal):
    t = two_runs_unequal
    S = json.load(open(t / "r" / "summary.json")); m = json.load(open(t / "p" / "manifest.json"))
    assert trace.verify(S, m, str(t / "r")) == []
    bad = copy.deepcopy(S); bad["run_repeat_agreement"]["BOLTZ2"]["register_agreement"] = 0.123
    assert trace.verify(bad, m, str(t / "r"))
    bad = copy.deepcopy(S); bad["run_repeat_agreement"]["BOLTZ2"]["structures"] = [x["id"] for x in m["structures"]][:2]
    assert trace.verify(bad, m, str(t / "r"))


# ---------------------------------------------------------------- withheld geometry route
def test_geometry_route_is_withheld_from_the_summary(tmp_path):
    assert importer.run([os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B")], PS, RS, str(tmp_path / "p"), "g") == 0
    assert analyse.run(str(tmp_path / "p"), str(tmp_path / "r"), reference=REF) == 0
    S = json.load(open(tmp_path / "r" / "summary.json"))
    for e in S["evaluate"]:
        assert not {"prot_internal_ca_rmsd", "rna_internal_c4_rmsd", "rna_placement_c4_rmsd", "geometry_status"} & set(e)
        assert e["irmsd_per_interface"] and e["lrmsd_per_interface"] and "designated" in e
    html = open(tmp_path / "r" / "summary.html").read()
    assert "withheld" in html and "<th>RNA placement RMSD</th>" not in html and "<th>iRMSD (A)</th>" in html
    assert any("Section 5 measures" in x for x in S["limits"])
    m = json.load(open(tmp_path / "p" / "manifest.json"))
    bad = copy.deepcopy(S); bad["evaluate"][0]["rna_placement_c4_rmsd"] = 1.0
    assert trace.verify(bad, m, str(tmp_path / "r"))


def test_analyse_without_diagnose_states_it(tmp_path):
    assert importer.run([os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B")], PS, RS, str(tmp_path / "p"), "nd") == 0
    assert analyse.run(str(tmp_path / "p"), str(tmp_path / "r"), diagnose=False) == 0
    S = json.load(open(tmp_path / "r" / "summary.json"))
    assert S["diagnose"] == [] and S["steps"]["diagnose_skipped"] is True
    assert not any(n.startswith("diagnose") for n in os.listdir(tmp_path / "r"))
    assert "Diagnose was not run" in open(tmp_path / "r" / "summary.html").read()


# ------------------------------------------------- install test finding (16 Oct): analyse without the "html" extra
def test_analyse_without_matplotlib_writes_same_summary(two_runs_unequal, monkeypatch, tmp_path):
    t = two_runs_unequal
    for m in [k for k in sys.modules if k == "matplotlib" or k.startswith("matplotlib.")]:
        monkeypatch.delitem(sys.modules, m)
    monkeypatch.setitem(sys.modules, "matplotlib", None)        # import matplotlib -> ImportError
    assert analyse.run(str(t / "p"), str(tmp_path / "r")) == 0
    a = json.load(open(t / "r" / "summary.json")); b = json.load(open(tmp_path / "r" / "summary.json"))
    strip = lambda d: json.loads(json.dumps(d).replace(str(t / "r"), "OUT").replace(str(tmp_path / "r"), "OUT"))
    a.pop("created_utc"); b.pop("created_utc")
    assert strip(a) == strip(b)
    html = open(tmp_path / "r" / "summary.html").read()
    assert "matplotlib is not installed" in html and not os.path.exists(tmp_path / "r" / "contact_map.png")
