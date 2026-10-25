"""0.3 workflow: rnplens analyse (rc3 parity, repeat-agreement limitation, traceability, wording)."""
import copy
import json
import os
import shutil

import pytest

from rnplens import analyse, importer, trace

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")
EXPECTED = os.path.join(EX, "expected_output", "B1_report_7K9D", "result.json")
PS = importer.read_sequence_arg(os.path.join(EX, "reference_based", "7K9D_protein.fasta"))
RS = importer.read_sequence_arg(os.path.join(EX, "reference_based", "7K9D_rna.fasta"))


@pytest.fixture(scope="module")
def two_runs(tmp_path_factory):
    t = tmp_path_factory.mktemp("a")
    assert importer.run([os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B")], PS, RS, str(t / "p"), "7K9D_example", "BOLTZ2") == 0
    assert analyse.run(str(t / "p"), str(t / "r")) == 0
    return t


# Tolerance Policy Amendment 1 (records/release/TOLERANCE_POLICY_AMENDMENT_1.md): in this test only, the RNA pose
# difference (the one compared float computed through numpy.linalg.svd, LAPACK dgesdd, whose rounding differs between
# OpenBLAS builds) is compared with an absolute tolerance of 1e-12 A. Every other compared value stays exact, with
# equal types. The rc3 expected values are not changed.
POSE_FIELD = "rna_pose_difference_A"
POSE_TOL_A = 1e-12


def _same_exact(a, b):
    """Exact equality with equal types at every level (1 != 1.0, True != 1)."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_same_exact(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_same_exact(x, y) for x, y in zip(a, b))
    return a == b


def compare_rc3_report(got, exp):
    """Differences between a Report result and the rc3 expected one under Amendment 1 (empty list: equal)."""
    bad = []
    if not _same_exact(got.get("contact_support"), exp.get("contact_support")):
        bad.append("contact_support")
    gr, er = got["summary"]["repeat_agreement"], exp["summary"]["repeat_agreement"]
    if type(gr) is not type(er) or not isinstance(er, dict) or set(gr) != set(er):
        return bad + ["repeat_agreement: engines"]
    for e in sorted(er):
        g, x = gr[e], er[e]
        if not (isinstance(g, dict) and isinstance(x, dict)):
            if not _same_exact(g, x):
                bad.append("repeat_agreement.%s" % e)
            continue
        if set(g) != set(x):
            bad.append("repeat_agreement.%s: fields" % e)
            continue
        for f in sorted(x):
            if f == POSE_FIELD:
                a, b = g[f], x[f]
                if a is None and b is None:
                    continue
                if not (type(a) is float and type(b) is float and abs(a - b) <= POSE_TOL_A):
                    bad.append("repeat_agreement.%s.%s: %r vs %r" % (e, f, a, b))
            elif not _same_exact(g[f], x[f]):
                bad.append("repeat_agreement.%s.%s" % (e, f))
    if not _same_exact([o["n_contacts"] for o in got["per_output"]], [o["n_contacts"] for o in exp["per_output"]]):
        bad.append("per_output.n_contacts")
    return bad


def test_report_numbers_equal_the_rc3_expected_output(two_runs):
    got = json.load(open(two_runs / "r" / "report" / "result.json"))
    exp = json.load(open(EXPECTED))
    assert compare_rc3_report(got, exp) == []


# ---- Amendment 1 regression: the tolerance is 1e-12 A on one field, and nothing else gets one

def _exp():
    return json.load(open(EXPECTED))


def _pose_set(d, v):
    d["summary"]["repeat_agreement"]["BOLTZ2"][POSE_FIELD] = v
    return d


def test_amendment1_unchanged_expected_record_and_the_observed_macos_value_pass():
    assert compare_rc3_report(_exp(), _exp()) == []
    assert compare_rc3_report(_pose_set(_exp(), 0.9573833460521571), _exp()) == []      # macOS arm64 value, 3.9e-15 A
    exp = _exp()
    r = exp["summary"]["repeat_agreement"]["BOLTZ2"][POSE_FIELD]
    assert compare_rc3_report(_pose_set(_exp(), r + 0.9e-12), exp) == []
    assert compare_rc3_report(_pose_set(_exp(), r - 0.9e-12), exp) == []


@pytest.mark.parametrize("delta", [1e-9, -1e-9, 1.1e-12, -1.1e-12, 1e-6, 0.001])
def test_amendment1_pose_difference_beyond_tolerance_fails(delta):
    exp = _exp()
    r = exp["summary"]["repeat_agreement"]["BOLTZ2"][POSE_FIELD]
    bad = compare_rc3_report(_pose_set(_exp(), r + delta), exp)
    assert bad and POSE_FIELD in bad[0]


@pytest.mark.parametrize("value", [None, float("nan"), 1, "0.957383346052161"])
def test_amendment1_pose_difference_of_another_kind_fails(value):
    assert compare_rc3_report(_pose_set(_exp(), value), _exp())


def test_amendment1_every_other_field_stays_exact():
    import math
    exp = _exp()
    n_checked = 0

    def fails(mutate):
        nonlocal n_checked
        d = _exp()
        mutate(d)
        n_checked += 1
        return compare_rc3_report(d, exp) != []

    for k, v in exp["contact_support"].items():                       # every contact_support value, by one ULP and by type
        assert fails(lambda d, k=k, v=v: d["contact_support"].__setitem__(k, math.nextafter(v, 2.0))), k
        assert fails(lambda d, k=k, v=v: d["contact_support"].__setitem__(k, int(v) if v == int(v) else str(v))), k
        assert fails(lambda d, k=k: d["contact_support"].pop(k)), k
    assert fails(lambda d: d["contact_support"].__setitem__("999,999", 1.0))
    for f in ("surface_agreement", "register_agreement"):            # one ULP, and 1e-15 (inside the pose tolerance)
        for nv in (lambda v: math.nextafter(v, 2.0), lambda v: math.nextafter(v, -2.0), lambda v: v + 1e-15):
            assert fails(lambda d, f=f, nv=nv: d["summary"]["repeat_agreement"]["BOLTZ2"].__setitem__(
                f, nv(d["summary"]["repeat_agreement"]["BOLTZ2"][f]))), f
    assert fails(lambda d: d["summary"]["repeat_agreement"]["BOLTZ2"].__setitem__("rna_pose_copy_permutation_capped", True))
    assert fails(lambda d: d["summary"]["repeat_agreement"]["BOLTZ2"].__setitem__("rna_pose_copy_permutation_capped", 0))
    assert fails(lambda d: d["summary"]["repeat_agreement"]["BOLTZ2"].pop("surface_agreement"))
    assert fails(lambda d: d["summary"]["repeat_agreement"]["BOLTZ2"].__setitem__("extra_field", 0.0))
    assert fails(lambda d: d["summary"]["repeat_agreement"].__setitem__("CHAI1", dict(d["summary"]["repeat_agreement"]["BOLTZ2"])))
    assert fails(lambda d: d["summary"]["repeat_agreement"].pop("BOLTZ2"))
    for i in range(len(exp["per_output"])):                          # every n_contacts
        assert fails(lambda d, i=i: d["per_output"][i].__setitem__("n_contacts", d["per_output"][i]["n_contacts"] + 1)), i
        assert fails(lambda d, i=i: d["per_output"][i].__setitem__("n_contacts", float(d["per_output"][i]["n_contacts"]))), i
    assert fails(lambda d: d["per_output"].append(dict(d["per_output"][0])))
    assert n_checked == 3 * len(exp["contact_support"]) + 1 + 6 + 2 + 4 + 2 * len(exp["per_output"]) + 1


def test_two_runs_show_reports_repeat_agreement(two_runs):
    S = json.load(open(two_runs / "r" / "summary.json"))
    v = S["repeat_agreement"]["BOLTZ2"]
    exp = json.load(open(EXPECTED))["summary"]["repeat_agreement"]["BOLTZ2"]
    assert v["status"] == "COMPUTED_BY_REPORT" and v["register_agreement"] == exp["register_agreement"]


def test_three_runs_state_not_computed_never_zero(tmp_path):
    for r in ("exec_A", "exec_B"):
        shutil.copytree(os.path.join(RF, r), tmp_path / "in" / r)
    shutil.copytree(os.path.join(RF, "exec_A"), tmp_path / "in" / "exec_C")
    assert importer.run([str(tmp_path / "in")], PS, RS, str(tmp_path / "p"), "x", "BOLTZ2") == 0
    m = json.load(open(tmp_path / "p" / "manifest.json"))
    assert m["counts"]["included"] == 2           # exec_C is a byte-identical duplicate of exec_A
    for i, r in enumerate(("exec_A", "exec_B", "exec_C")):
        p = tmp_path / "in2" / r; shutil.copytree(os.path.join(RF, "exec_A" if r == "exec_C" else r), p)
        with open(p / "7K9D_model_0.pdb", "a") as fh:
            fh.write("REMARK distinct copy %d\n" % i)
    assert importer.run([str(tmp_path / "in2")], PS, RS, str(tmp_path / "p3"), "x", "BOLTZ2") == 0
    assert analyse.run(str(tmp_path / "p3"), str(tmp_path / "r3")) == 0
    S = json.load(open(tmp_path / "r3" / "summary.json"))
    v = S["repeat_agreement"]["BOLTZ2"]
    assert v["status"] == "NOT_COMPUTED" and v["text"] == analyse.REPEAT_NOT_COMPUTED
    assert "register_agreement" not in v
    html = open(tmp_path / "r3" / "summary.html").read()
    assert analyse.REPEAT_NOT_COMPUTED in html
    row = S["contacts"]["rows"][0]["per_engine"]["BOLTZ2"]
    assert row["of"] == 3 and len(row["structures"]) == row["count"]


def test_trace_refuses_a_tampered_number(two_runs):
    S = json.load(open(two_runs / "r" / "summary.json"))
    m = json.load(open(two_runs / "p" / "manifest.json"))
    assert trace.verify(S, m, str(two_runs / "r")) == []
    bad = copy.deepcopy(S)
    bad["contacts"]["rows"][0]["per_engine"]["BOLTZ2"]["count"] += 1
    assert trace.verify(bad, m, str(two_runs / "r"))
    bad = copy.deepcopy(S)
    bad["contacts"]["rows"][0]["report_contact_support"] = 0.99
    assert trace.verify(bad, m, str(two_runs / "r"))
    bad = copy.deepcopy(S)
    bad["repeat_agreement"]["BOLTZ2"]["register_agreement"] = 0.1
    assert trace.verify(bad, m, str(two_runs / "r"))


def test_wording_audit(two_runs):
    html = open(two_runs / "r" / "summary.html").read()
    assert trace.wording_audit(html) == []
    for w in ("the most reliable contact", "80% confidence", "the correct binding mode", "best structure", "probability 0.8"):
        assert trace.wording_audit("<p>%s</p>" % w), w


def test_refuses_existing_results_dir(two_runs):
    assert analyse.run(str(two_runs / "p"), str(two_runs / "r")) == 2
