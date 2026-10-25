"""The engine confidence file is a DECLARED, DIGESTED input of Report (RNPLens 0.4, owner-authorised correction
2026-10-24; release blocker "confidence-file findings").

Two defects are covered. (A) Missing input: before the correction, deleting the six bundled confidence JSONs left
`report run` at exit 0 with stdout identical apart from paths, 4 of 296 result values changed and 2 normalised HTML
lines changed -- a report no automatic means could distinguish from a qualified one. (B) Input integrity: the
confidence file was not a contract field, so an EDITED file was read with no check at all.

Every test here asserts an input-side refusal or an explicit label. None of them asserts anything about a
prediction, and none changes a scientific definition: test_complete_inputs_reproduce_the_reference_values pins the
numerical outputs of the complete input set.
"""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys

import pytest

from rnpbench_report import contract as C
from rnpbench_report import native, selftest as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(ROOT, "examples", "reference_free")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "rnplens", *args], capture_output=True, text=True,
                          env=dict(os.environ, MPLBACKEND="Agg"))


@pytest.fixture()
def case(tmp_path):
    """A private copy of the bundled 7K9D example (two Boltz-2 executions) and its contract, digests filled in."""
    ex = tmp_path / "examples" / "report_7K9D"
    shutil.copytree(os.path.join(EXAMPLES, "report_7K9D"), ex)
    cp = tmp_path / "contract.json"
    S.write_example_contract(str(ex), str(cp))
    return ex, cp


# ---------------------------------------------------------------- 1. complete, legitimate inputs
def test_complete_inputs_are_declared_and_verified(case):
    ex, cp = case
    c = json.load(open(cp))
    assert len(c["outputs"]) == 2
    for o in c["outputs"]:
        assert os.path.isabs(o["confidence_path"]) and os.path.isfile(o["confidence_path"])
        assert o["confidence_sha256"] == sha(o["confidence_path"])
    v = C.load(str(cp))
    assert C.confidence_input_findings(v) == []


def test_complete_inputs_run_and_are_not_labelled(case, tmp_path):
    pytest.importorskip("matplotlib")
    ex, cp = case
    out = tmp_path / "out"
    r = run_cli("report", "run", str(cp), "--out", str(out))
    assert r.returncode == 0, r.stderr
    res = json.load(open(out / "result.json"))
    assert "NATIVE_CONFIDENCE_INPUTS_STATUS" not in res["summary"]
    assert "native_confidence_inputs_not_verified" not in res["summary"]
    assert [p["native_kind"] for p in res["per_output"]] == ["iptm", "iptm"]
    assert all(p["native"] is not None for p in res["per_output"])
    page = open(next(out.glob("*.html"))).read()
    assert "REDUCED EVIDENCE" not in page and C.REDUCED_EVIDENCE_STATUS not in page
    assert C.REDUCED_EVIDENCE_STATUS not in r.stdout


def test_complete_inputs_reproduce_the_reference_values(case, tmp_path):
    """THE ACCEPTANCE TEST: with complete, unchanged inputs every one of the 296 frozen reference values is
    reproduced, and the page is unchanged line for line."""
    pytest.importorskip("matplotlib")
    ex, cp = case
    out = tmp_path / "out"
    assert run_cli("report", "run", str(cp), "--out", str(out)).returncode == 0
    comps = []
    for fn, drop in (("result.json", ("wall_s", "environment")), ("contacts_by_output.json", ())):
        got = S.normalise(json.load(open(out / fn)), str(tmp_path / "examples"), drop=drop)
        comps += S.compare(json.load(open(os.path.join(S.EXPECTED, "report_7K9D_" + fn))), got, "portable", "$" + fn)
    bad = [c for c in comps if not c[4]]
    assert len(comps) == 296, len(comps)
    assert not bad, bad[:5]
    e_txt, e_n = S.html_normalise(open(os.path.join(S.EXPECTED, "report_7K9D_example.html")).read())
    g_txt, g_n = S.html_normalise(open(next(out.glob("*.html"))).read())
    assert (e_n, g_n) == (1, 1)
    import difflib
    diff = [l for l in difflib.unified_diff(e_txt.splitlines(), g_txt.splitlines(), lineterm="", n=0)
            if not l.startswith(("---", "+++", "@@"))]
    assert diff == []


# ---------------------------------------------------------------- 2. missing confidence files
def test_missing_confidence_file_is_refused_and_writes_nothing(case, tmp_path):
    ex, cp = case
    c = json.load(open(cp))
    for o in c["outputs"]:
        os.remove(o["confidence_path"])
        o.pop("confidence_path"); o.pop("confidence_sha256")
    cp.write_text(json.dumps(c))
    out = tmp_path / "out"
    r = run_cli("report", "run", str(cp), "--out", str(out))
    assert r.returncode == 2
    assert C.CODE in r.stderr and native.ABSENT_REQUIRED_INPUT in r.stderr
    assert "confidence_7K9D_model_0.json" in r.stderr
    assert not out.exists()                                   # nothing qualified, nothing at all
    assert '"result"' not in r.stdout and '"case_id"' not in r.stdout


def test_missing_file_but_still_declared_is_refused_as_a_contract_error(case, tmp_path):
    ex, cp = case
    c = json.load(open(cp))
    os.remove(c["outputs"][0]["confidence_path"])
    cp.write_text(json.dumps(c))
    r = run_cli("report", "run", str(cp), "--out", str(tmp_path / "out"))
    assert r.returncode == 2 and "confidence_path does not exist" in r.stderr
    assert not (tmp_path / "out").exists()


def test_absent_input_is_reported_per_output_by_the_library(case):
    ex, cp = case
    c = json.load(open(cp))
    for o in c["outputs"]:
        os.remove(o["confidence_path"]); o.pop("confidence_path"); o.pop("confidence_sha256")
    cp.write_text(json.dumps(c))
    f = C.confidence_input_findings(C.load(str(cp)))
    assert [x["code"] for x in f] == [native.ABSENT_REQUIRED_INPUT] * 2
    assert [os.path.basename(x["expected_path"]) for x in f] == ["confidence_7K9D_model_0.json"] * 2
    assert all(x["file_present"] is False for x in f)


# ---------------------------------------------------------------- 3. MODIFIED confidence-file contents
def test_edited_confidence_file_is_refused(case, tmp_path):
    """Problem B: before the correction this file was read with no check at all."""
    ex, cp = case
    c = json.load(open(cp))
    p = c["outputs"][0]["confidence_path"]
    d = json.load(open(p)); d["iptm"] = 0.999
    open(p, "w").write(json.dumps(d))
    r = run_cli("report", "run", str(cp), "--out", str(tmp_path / "out"))
    assert r.returncode == 2 and "confidence digest mismatch" in r.stderr
    assert not (tmp_path / "out").exists()


def test_edited_confidence_file_is_refused_even_in_reduced_evidence_mode(case, tmp_path):
    ex, cp = case
    c = json.load(open(cp))
    p = c["outputs"][0]["confidence_path"]
    d = json.load(open(p)); d["iptm"] = 0.999
    open(p, "w").write(json.dumps(d))
    r = run_cli("report", "run", str(cp), "--out", str(tmp_path / "out"), "--reduced-evidence")
    assert r.returncode == 2 and "confidence digest mismatch" in r.stderr
    assert not (tmp_path / "out").exists()


def test_one_byte_appended_is_detected(case, tmp_path):
    ex, cp = case
    c = json.load(open(cp))
    with open(c["outputs"][1]["confidence_path"], "a") as fh:
        fh.write(" ")
    r = run_cli("report", "validate", str(cp))
    assert r.returncode == 2 and "confidence digest mismatch" in r.stderr


# ---------------------------------------------------------------- 4. incorrect hashes
def test_declared_digest_that_is_not_the_file_is_refused(case, tmp_path):
    ex, cp = case
    c = json.load(open(cp))
    c["outputs"][0]["confidence_sha256"] = "0" * 64
    cp.write_text(json.dumps(c))
    r = run_cli("report", "run", str(cp), "--out", str(tmp_path / "out"))
    assert r.returncode == 2 and "confidence digest mismatch" in r.stderr and not (tmp_path / "out").exists()


@pytest.mark.parametrize("bad", ["", "abc", "0" * 63, "g" * 64, 12345])
def test_malformed_digest_field_is_refused(case, bad):
    ex, cp = case
    c = json.load(open(cp))
    c["outputs"][0]["confidence_sha256"] = bad
    with pytest.raises(C.ContractError) as ex_:
        C.validate(c)
    assert "confidence_sha256" in str(ex_.value)


def test_digest_without_path_is_refused(case):
    ex, cp = case
    c = json.load(open(cp))
    c["outputs"][0].pop("confidence_path")
    with pytest.raises(C.ContractError) as ex_:
        C.validate(c)
    assert "without confidence_path" in str(ex_.value)


def test_digests_are_also_checked_when_the_contract_is_only_validated(case):
    ex, cp = case
    c = json.load(open(cp))
    c["outputs"][0]["confidence_sha256"] = "1" * 64
    cp.write_text(json.dumps(c))
    assert run_cli("report", "validate", str(cp)).returncode == 2
    assert run_cli("report", "validate", str(cp), "--no-verify-digests").returncode == 0   # declared opt-out only


# ---------------------------------------------------------------- 5. incorrect confidence-directory paths
def test_confidence_dir_pointing_elsewhere_is_refused(case, tmp_path):
    ex, cp = case
    c = json.load(open(cp))
    c["outputs"][0]["confidence_dir"] = str(tmp_path)        # the declared file is no longer the file read
    cp.write_text(json.dumps(c))
    r = run_cli("report", "run", str(cp), "--out", str(tmp_path / "out"))
    assert r.returncode == 2 and "is not the file this version reads" in r.stderr
    assert not (tmp_path / "out").exists()


def test_confidence_path_from_another_case_is_refused(case, tmp_path):
    ex, cp = case
    c = json.load(open(cp))
    other = tmp_path / "elsewhere" / "confidence_7K9D_model_0.json"
    other.parent.mkdir()
    shutil.copy(c["outputs"][0]["confidence_path"], other)
    c["outputs"][0]["confidence_path"] = str(other)
    c["outputs"][0]["confidence_sha256"] = sha(str(other))
    with pytest.raises(C.ContractError) as ex_:
        C.validate(c)
    assert "is not the file this version reads" in str(ex_.value)


def test_relative_confidence_path_is_refused(case):
    ex, cp = case
    c = json.load(open(cp))
    c["outputs"][0]["confidence_path"] = "confidence_7K9D_model_0.json"
    with pytest.raises(C.ContractError) as ex_:
        C.validate(c)
    assert "must be absolute" in str(ex_.value)


# ---------------------------------------------------------------- 6. symlinks and unexpected paths
def test_symlinked_confidence_file_is_accepted_and_disclosed(case, tmp_path):
    """A link whose target digest matches is honest evidence; the link target is recorded, never silent."""
    ex, cp = case
    c = json.load(open(cp))
    p = c["outputs"][0]["confidence_path"]
    real = tmp_path / "real_confidence.json"
    shutil.move(p, real)
    os.symlink(real, p)
    v = C.validate(copy.deepcopy(c))
    rec = [o for o in v["outputs"] if o["confidence_path"] == p][0]
    assert rec["confidence_path_symlink_target"] == os.path.realpath(str(real))
    assert C.confidence_input_findings(v) == []


def test_confidence_path_that_is_a_directory_is_refused(case, tmp_path):
    ex, cp = case
    c = json.load(open(cp))
    p = c["outputs"][0]["confidence_path"]
    os.remove(p); os.mkdir(p)
    with pytest.raises(C.ContractError) as ex_:
        C.validate(c)
    assert "not a regular file" in str(ex_.value)


def test_broken_symlink_is_refused(case, tmp_path):
    ex, cp = case
    c = json.load(open(cp))
    p = c["outputs"][0]["confidence_path"]
    os.remove(p)
    os.symlink(str(tmp_path / "nowhere.json"), p)
    with pytest.raises(C.ContractError) as ex_:
        C.validate(c)
    assert "does not exist" in str(ex_.value)


def test_declaration_for_an_engine_that_reads_no_file_is_refused(case):
    ex, cp = case
    c = json.load(open(cp))
    c["outputs"][0]["engine"] = "OTHER"
    c["outputs"][0]["native_confidence"] = None
    c["outputs"][0]["native_confidence_kind"] = None
    with pytest.raises(C.ContractError) as ex_:
        C.validate(c)
    assert "native_confidence and confidence_path" in str(ex_.value)


# ---------------------------------------------------------------- 7. the sanctioned exemption
def test_declared_native_confidence_reads_no_file_and_is_never_called_missing(case, tmp_path):
    ex, cp = case
    c = json.load(open(cp))
    for o in c["outputs"]:
        os.remove(o["confidence_path"])
        o.pop("confidence_path"); o.pop("confidence_sha256")
        o["native_confidence"] = None
        o["native_confidence_kind"] = None
    cp.write_text(json.dumps(c))
    assert C.confidence_input_findings(C.load(str(cp))) == []
    r = run_cli("report", "run", str(cp), "--out", str(tmp_path / "out"))
    assert r.returncode == 0, r.stderr
    res = json.load(open(tmp_path / "out" / "result.json"))
    assert [p["native"] for p in res["per_output"]] == [None, None]
    assert "NATIVE_CONFIDENCE_INPUTS_STATUS" not in res["summary"]


# ---------------------------------------------------------------- 8. explicit reduced-evidence behaviour
def test_reduced_evidence_runs_and_labels_every_stream(case, tmp_path):
    pytest.importorskip("matplotlib")
    ex, cp = case
    c = json.load(open(cp))
    for o in c["outputs"]:
        os.remove(o["confidence_path"]); o.pop("confidence_path"); o.pop("confidence_sha256")
    cp.write_text(json.dumps(c))
    out = tmp_path / "out"
    r = run_cli("report", "run", str(cp), "--out", str(out), "--reduced-evidence")
    assert r.returncode == 0, r.stderr
    assert C.REDUCED_EVIDENCE_STATUS in r.stdout                                   # stdout: a pipeline sees it
    s = json.load(open(out / "result.json"))["summary"]
    assert s["NATIVE_CONFIDENCE_INPUTS_STATUS"] == C.REDUCED_EVIDENCE_STATUS        # result.json: a reader sees it
    assert len(s["native_confidence_inputs_not_verified"]) == 2
    assert "not a fully qualified analysis" in s["NATIVE_CONFIDENCE_INPUTS_NOTE"]
    page = open(next(out.glob("*.html"))).read()                                   # the page: a human sees it
    assert "REDUCED EVIDENCE" in page and C.REDUCED_EVIDENCE_STATUS in page
    assert page.index(C.REDUCED_EVIDENCE_STATUS) < page.index("1. Per-engine contributions")
    assert "not a fully qualified" in page and "Do not cite the per-engine confidences" in page


def test_reduced_evidence_does_not_change_one_agreement_number(case, tmp_path):
    """Requirement 7, measured: the analysis reads coordinates only, so only the confidence leaves move."""
    ex, cp = case
    full = tmp_path / "full"
    assert run_cli("report", "run", str(cp), "--out", str(full), "--no-report").returncode == 0
    c = json.load(open(cp))
    for o in c["outputs"]:
        os.remove(o["confidence_path"]); o.pop("confidence_path"); o.pop("confidence_sha256")
    cp.write_text(json.dumps(c))
    red = tmp_path / "red"
    assert run_cli("report", "run", str(cp), "--out", str(red), "--reduced-evidence", "--no-report").returncode == 0
    a, b = (json.load(open(d / "result.json")) for d in (full, red))
    assert a["contact_support"] == b["contact_support"]
    for k in ("median_pairwise_surface_agreement", "median_pairwise_register_agreement",
              "median_pairwise_rna_pose_difference_A", "interface_hypotheses", "repeat_agreement",
              "contact_support_histogram", "n_eligible_outputs", "eligible_engines"):
        assert a["summary"][k] == b["summary"][k], k
    for x, y in zip(a["per_output"], b["per_output"]):
        assert (x["n_contacts"], x["n_surface"]) == (y["n_contacts"], y["n_surface"])
        assert y["native"] is None and x["native"] is not None


def test_reduced_evidence_is_the_only_way_through(case, tmp_path):
    ex, cp = case
    c = json.load(open(cp))
    for o in c["outputs"]:
        o.pop("confidence_path"); o.pop("confidence_sha256")                       # files present, undeclared
    cp.write_text(json.dumps(c))
    r = run_cli("report", "run", str(cp), "--out", str(tmp_path / "o1"))
    assert r.returncode == 2 and native.UNDECLARED_REQUIRED_INPUT in r.stderr
    assert "file present, no digest declared" in r.stderr
    assert run_cli("report", "run", str(cp), "--out", str(tmp_path / "o2"),
                   "--reduced-evidence", "--no-report").returncode == 0


# ---------------------------------------------------------------- 9. the four-of-296 pin
def test_exactly_four_of_296_values_move_when_the_confidence_inputs_are_dropped(case, tmp_path):
    """Pins the measurement that made this a release blocker: dropping the confidence inputs changes 4 of 296
    values and nothing else, which is why the absence had to reach the exit code rather than one table cell.
    After the correction those 4 values are reachable only through the labelled reduced-evidence mode."""
    ex, cp = case
    full = tmp_path / "full"
    assert run_cli("report", "run", str(cp), "--out", str(full), "--no-report").returncode == 0
    c = json.load(open(cp))
    for o in c["outputs"]:
        os.remove(o["confidence_path"]); o.pop("confidence_path"); o.pop("confidence_sha256")
    cp.write_text(json.dumps(c))
    red = tmp_path / "red"
    assert run_cli("report", "run", str(cp), "--out", str(red), "--reduced-evidence", "--no-report").returncode == 0
    base = str(tmp_path / "examples")
    comps = []
    for fn, drop in (("result.json", ("wall_s", "environment")), ("contacts_by_output.json", ())):
        a = S.normalise(json.load(open(full / fn)), base, drop=drop)
        b = S.normalise(json.load(open(red / fn)), base, drop=drop)
        if fn == "result.json":
            for d in (a, b):
                for k in ("NATIVE_CONFIDENCE_INPUTS_STATUS", "NATIVE_CONFIDENCE_INPUTS_NOTE",
                          "native_confidence_inputs_not_verified"):
                    d["summary"].pop(k, None)              # the label itself is the fifth difference, by design
        comps += S.compare(a, b, "portable", "$" + fn)
    bad = [x for x in comps if not x[4]]
    assert len(comps) == 296, len(comps)
    assert sorted(x[0] for x in bad) == ["$result.json.per_output[0].native",
                                         "$result.json.per_output[0].native_kind",
                                         "$result.json.per_output[1].native",
                                         "$result.json.per_output[1].native_kind"]


# ---------------------------------------------------------------- 10. the expected input of each parser
@pytest.mark.parametrize("engine,model,want", [
    ("BOLTZ2", "/d/7K9D_model_0.pdb", "/d/confidence_7K9D_model_0.json"),
    ("RF3", "/d/x_model.cif", "/d/x_summary_confidences.json"),
    ("CHAI1", "/d/pred.model_idx_2.cif", "/d/scores.model_idx_2.npz"),
    ("RF2NA", "/d/model_00.pdb", "/d/model_00.npz"),
])
def test_expected_input_names_the_file_each_parser_reads(engine, model, want):
    p, code, note = native.expected_input(engine, model, "/d")
    assert (p, code) == (want, None) and note


def test_engine_without_a_parser_reads_no_file():
    p, code, _ = native.expected_input("OTHER", "/d/m.pdb", "/d")
    assert (p, code) == (None, native.READS_NO_FILE)


def test_chai1_without_model_idx_cannot_be_named():
    p, code, _ = native.expected_input("CHAI1", "/d/pred.cif", "/d")
    assert (p, code) == (None, native.UNREADABLE_REQUIRED_INPUT)


@pytest.mark.parametrize("n,code", [(0, native.ABSENT_REQUIRED_INPUT), (2, native.AMBIGUOUS_REQUIRED_INPUT)])
def test_af3_summary_confidences_must_be_exactly_one(tmp_path, n, code):
    for i in range(n):
        (tmp_path / ("m%d_summary_confidences.json" % i)).write_text("{}")
    p, got, _ = native.expected_input("AF3", str(tmp_path / "m.cif"), str(tmp_path))
    assert (p, got) == (None, code)


# ---------------------------------------------------------------- 11. the declaration reaches the run record
def test_the_run_record_lists_the_confidence_inputs_with_their_digests(case, tmp_path):
    ex, cp = case
    out = tmp_path / "out"
    assert run_cli("report", "run", str(cp), "--out", str(out), "--no-report").returncode == 0
    rec = json.load(open(out / "rnplens_run.json"))
    declared = {o["confidence_path"] for o in json.load(open(cp))["outputs"]}
    listed = {i["path"]: i["sha256"] for i in rec["inputs"]}
    assert declared <= set(listed)
    for p in declared:
        assert listed[p] == sha(p)


# ---------------------------------------------------------------- 12. the five-part diagnostic shape
def test_the_refusal_carries_the_five_part_shape():
    f = [{"engine": "BOLTZ2", "execution": "exec_A", "code": native.ABSENT_REQUIRED_INPUT,
          "expected_path": "/d/confidence_x.json", "file_present": False, "note": "n"}]
    t = C.diagnostic(f)
    assert C.STATUS in t and C.CODE in t and C.REASON in t and C.SUMMARY_LINE in t
    assert "/d/confidence_x.json" in t and native.ABSENT_REQUIRED_INPUT in t
    assert "declared input" in C.RUN_RECORD_NOTE and C.REDUCED_EVIDENCE_STATUS


# ---------------------------------------------------------------- 13. re-verification at read time
def test_confidence_digest_is_reverified_before_the_file_is_read(case):
    """The declared digest is checked again when the file is about to be read, as the structure digest is, so a
    file swapped between validation and reading cannot reach the report."""
    from rnpbench_report import agreement
    ex, cp = case
    v = C.load(str(cp))
    job = {"protein_length": v["construct"]["protein_length"], "rna_length": v["construct"]["rna_length"]}
    row = dict(v["outputs"][0], confidence_sha256="0" * 64)
    assert agreement.analyse_output(dict(job, output=row))["state"] == "CONFIDENCE_CHECKSUM_MISMATCH"
    row2 = dict(v["outputs"][0])
    os.remove(row2["confidence_path"])
    assert agreement.analyse_output(dict(job, output=row2))["state"] == "CONFIDENCE_CHECKSUM_MISMATCH"


def test_run_writes_nothing_when_a_confidence_input_changes_during_the_run(case, tmp_path, monkeypatch, capsys):
    from rnpbench_report import agreement, cli as rcli
    ex, cp = case
    real = agreement.analyse_output

    def swapped(job):                      # the window between validation and reading, forced open
        r = real(job)
        r["state"] = "CONFIDENCE_CHECKSUM_MISMATCH"
        return r

    monkeypatch.setattr(agreement, "analyse_output", swapped)
    out = tmp_path / "o"
    rc = rcli.main(["run", str(cp), "--outdir", str(out)])
    err = capsys.readouterr().err
    assert rc == 2 and not out.exists()
    assert "CONFIDENCE_INPUT_CHANGED_DURING_RUN" in err and "Nothing was written" in err
