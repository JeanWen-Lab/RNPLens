"""Contract tests. Each one asserts a refusal the package must make, or a statement it must carry.

These are not unit tests of arithmetic; the arithmetic was gated against the frozen scoring module before
any of it was used. They test that the package cannot be made to say something the measurements do not
support.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from rnpbench_diagnose import LICENSED_STATEMENTS, REFUSED_STATEMENTS
from rnpbench_diagnose.diagnose import (NotLicensed, attribute_placement, diagnose, reference_distribution,
                                        statement)
from rnpbench_diagnose.preflight import PreflightRefusal, preflight
from rnpbench_diagnose.report import LIMITS, record, render_html

OK_REQUEST = {"sample": {"name": "demo_target",
                         "sequences": [{"proteinChain": {"sequence": "MKTAYIAKQRQISFVK"}},
                                       {"rnaSequence": {"sequence": "GGACUUCGGUCC"}},
                                       {"ion": {"ion": "MG"}}]},
              "evidence": {"1": {"unpaired_msa": "..."}}}
FAKE_DIS = {"prot_internal_ca_rmsd": 0.9, "rna_internal_c4_rmsd": 1.4,
            "rna_placement_c4_rmsd": 3.6, "usable": 50, "n_pairs": 1225, "refused": None}
FAILS = []


def check(name, fn):
    try:
        fn()
        print("  PASS  %s" % name)
    except AssertionError as ex:
        FAILS.append((name, str(ex)))
        print("  FAIL  %s -- %s" % (name, ex))


def t_preflight_accepts_a_valid_request():
    r = preflight(OK_REQUEST)
    assert r["copy_number"] == {"protein_chains": 1, "rna_chains": 1, "ion_sites": 1}, r
    assert "msa_use_declared" in r["gates_passed"]


def t_preflight_refuses_unpermitted_chemistry():
    q = json.loads(json.dumps(OK_REQUEST))
    q["sample"]["sequences"].append({"ion": {"ion": "FE"}})
    try:
        preflight(q)
    except PreflightRefusal as ex:
        assert "FE" in str(ex), ex
        return
    raise AssertionError("accepted an unpermitted ion")


def t_preflight_refuses_undeclared_msa():
    q = json.loads(json.dumps(OK_REQUEST))
    q["evidence"] = {}
    try:
        preflight(q)
    except PreflightRefusal as ex:
        assert "MSA" in str(ex) or "msa" in str(ex), ex
        return
    raise AssertionError("accepted a request that declares no MSA use")


def t_preflight_refuses_rna_only_and_protein_only():
    for drop, word in ((0, "protein"), (1, "RNA")):
        q = json.loads(json.dumps(OK_REQUEST))
        q["sample"]["sequences"] = [e for i, e in enumerate(q["sample"]["sequences"]) if i != drop]
        q["evidence"] = {"1": {"declared_no_msa": True}}
        try:
            preflight(q)
        except PreflightRefusal as ex:
            assert word.lower() in str(ex).lower(), ex
            continue
        raise AssertionError("accepted a request with no %s chain" % word)


def t_preflight_refuses_nonstandard_sequence():
    q = json.loads(json.dumps(OK_REQUEST))
    q["sample"]["sequences"][1]["rnaSequence"]["sequence"] = "GGACTTCGGTCC"      # DNA letters
    try:
        preflight(q)
    except PreflightRefusal as ex:
        assert "ACGU" in str(ex), ex
        return
    raise AssertionError("accepted a non-ACGU RNA sequence")


def t_placement_attribution_is_refused():
    try:
        attribute_placement()
    except NotLicensed as ex:
        assert "-0.008" in str(ex) and "-0.084" in str(ex), "the refusal must cite both measurements"
        return
    raise AssertionError("placement attribution was not refused")


def t_only_two_statements_are_licensed():
    assert LICENSED_STATEMENTS == ("protein_side", "rna_side"), LICENSED_STATEMENTS
    assert "placement_attribution" in REFUSED_STATEMENTS
    try:
        statement("within_engine", "placement", FAKE_DIS)
    except NotLicensed:
        return
    raise AssertionError("a placement statement was produced")


def t_specificity_flags_match_the_cohorts():
    w = {s["statement"]: s for s in diagnose("within_engine", FAKE_DIS)["statements"]}
    c = {s["statement"]: s for s in diagnose("cross_engine", FAKE_DIS)["statements"]}
    assert w["protein_side"]["component_specific"] is True, "protein must be specific within engine"
    assert w["rna_side"]["component_specific"] is False, "RNA must NOT be specific within engine"
    assert c["rna_side"]["component_specific"] is True, "RNA must be specific across engines"
    assert c["protein_side"]["component_specific"] is False, "protein must NOT be specific across engines"
    assert "cannot separate its shape from its placement" in w["rna_side"]["text"], w["rna_side"]["text"]


def t_placement_value_is_reported_but_flagged():
    d = diagnose("within_engine", FAKE_DIS)
    na = d["measured_but_not_attributed"]
    assert na["rna_placement_c4_rmsd"] == 3.6, na
    assert "not licensed" in na["why"]


def t_reference_distribution_is_digest_bound_and_refuses_when_absent():
    for mode, axis in (("within_engine", "prot_internal_ca_rmsd"), ("cross_engine", "rna_internal_c4_rmsd")):
        ref = reference_distribution(mode, axis)
        assert ref["n"] >= 50 and len(ref["sha256"]) == 64, ref
        assert ref["q1"] <= ref["median"] <= ref["q3"], ref
    old = os.environ.get("RNPD_REFERENCE")
    os.environ["RNPD_REFERENCE"] = tempfile.mkdtemp()
    try:
        reference_distribution("within_engine", "prot_internal_ca_rmsd")
        raise AssertionError("banded a value with no reference distribution present")
    except NotLicensed:
        pass
    finally:
        if old is None:
            del os.environ["RNPD_REFERENCE"]
        else:
            os.environ["RNPD_REFERENCE"] = old


def t_disagreement_refusal_propagates_into_the_report():
    dis = {"usable": 1, "refused": "fewer than two usable structures: disagreement is undefined"}
    d = diagnose("within_engine", dis)
    assert all(not s["available"] for s in d["statements"]), d
    assert "measured_but_not_attributed" not in d


def t_report_refuses_without_limits():
    rec = record(None, {"n_total": 1, "VALID": 1, "TECHNICAL_FAILURE": 0, "STRUCTURAL_FAILURE": 0,
                        "n_valid": 1, "details": []}, FAKE_DIS, diagnose("within_engine", FAKE_DIS),
                 target="demo")
    assert rec["limits"] == LIMITS
    h = render_html(rec)
    assert "variance, not bias" in h and "not blind validation" in h
    rec2 = dict(rec); rec2["limits"] = []
    try:
        render_html(rec2)
    except ValueError:
        return
    raise AssertionError("rendered a report with no limits block")


def t_no_statement_claims_superiority_over_model_confidence():
    """The out-of-sample budget advantage over protein pTM does not resolve, so the tool must not imply
    it replaces or outperforms the engine's own confidence. Phrased as a ban on superiority language in
    the statements, not on the word 'confidence', which the limits legitimately discuss."""
    BAD = ("outperform", "better than the engine", "beats the engine", "supersede", "instead of confidence",
           "replaces confidence", "more informative than confidence")
    for mode in ("within_engine", "cross_engine"):
        rec = diagnose(mode, FAKE_DIS)
        for s in rec["statements"]:
            low = s["text"].lower()
            for b in BAD:
                assert b not in low, "statement claims superiority over model confidence: %r" % s["text"]


def t_limits_state_the_complementarity_finding():
    """A reader must be told, in the report itself, that this is complementary and not independent.

    `limits` is attached by report.record, not by diagnose, so the check goes through the record the user
    actually receives rather than through the statement list.
    """
    from rnpbench_diagnose.report import LIMITS
    joined = " ".join(LIMITS).lower()
    assert "complementary" in joined, "the limits must say the information is complementary"
    assert "does not resolve" in joined, "the limits must state that the advantage over pTM does not resolve"
    assert "0.167" in joined and "53.7" in joined, "the limits must carry the numbers, not just the adjective"


def t_band_is_stated_relative_to_the_frozen_reference():
    """The band must never be phrased as a quantile of the cohort in hand: out of sample the reference
    distribution did not reproduce the new cohort, so that phrasing would be false."""
    for mode in ("within_engine", "cross_engine"):
        for s in diagnose(mode, FAKE_DIS)["statements"]:
            t = s["text"]
            assert "relative to the frozen development reference" in t, t
            assert "development targets" in t, t
            for banned in ("for this benchmark", "top quartile in this", "of this cohort"):
                assert banned not in t, "band phrased against the cohort in hand: %r" % t


def t_out_of_sample_status_is_carried_per_statement():
    w = {s["statement"]: s for s in diagnose("within_engine", FAKE_DIS)["statements"]}
    c = {s["statement"]: s for s in diagnose("cross_engine", FAKE_DIS)["statements"]}
    oos = w["protein_side"]["evidence"]["out_of_sample"]
    assert oos["rho"] == 0.525 and oos["ci"] == [0.450, 0.593], oos
    assert "PASS" in oos["verdict"]
    assert c["rna_side"]["evidence"]["out_of_sample"]["verdict"] == "NOT TESTED", \
        "the RNA statement must declare it is not validated out of sample"


def t_limits_disclose_the_distribution_shift_and_the_validation_asymmetry():
    rec = record(None, {"n_total": 2, "VALID": 2, "TECHNICAL_FAILURE": 0, "STRUCTURAL_FAILURE": 0,
                        "n_valid": 2, "details": []}, FAKE_DIS, diagnose("within_engine", FAKE_DIS),
                 target="demo")
    joined = " ".join(rec["limits"])
    assert "not recalibrated" in joined, "the limits must state the boundaries were not recalibrated"
    assert "awaits prospective validation" in joined, "the limits must state the asymmetry"
    h = render_html(rec)
    assert "not recalibrated" in h and "awaits prospective validation" in h


def t_report_never_says_probability_or_confidence_of_correctness():
    rec = record(None, {"n_total": 2, "VALID": 2, "TECHNICAL_FAILURE": 0, "STRUCTURAL_FAILURE": 0,
                        "n_valid": 2, "details": []}, FAKE_DIS, diagnose("cross_engine", FAKE_DIS),
                 target="demo", engines={"A", "B", "C"})
    # the banned phrasing must be absent from what the report ASSERTS -- the statement texts and the
    # unattributed value -- while the limits block must contain the negation of exactly that phrasing
    asserted = " ".join([s.get("text", "") for s in rec["diagnosis"]["statements"]]).lower()
    for banned in ("probability", "confidence that", "likely correct", "accuracy estimate", "% correct"):
        assert banned not in asserted, "a diagnostic statement contains %r" % banned
    limits = " ".join(rec["limits"]).lower()
    assert "no probability of correctness is offered" in limits, "the limits block must negate it explicitly"
    h = render_html(rec).lower()
    assert "no probability of correctness is offered" in h, "the negation must survive into the page"
    # and the only place the phrase may appear in the page is inside the limits list
    body_without_limits = h.split("what this report does not tell you")[0]
    assert "probability" not in body_without_limits, "the word appears outside the limits block"


if __name__ == "__main__":
    print("contract tests")
    for nm, fn in sorted((k[2:], v) for k, v in list(globals().items()) if k.startswith("t_")):
        check(nm, fn)
    print("\n%d checks, %d failures" % (sum(1 for k in globals() if k.startswith("t_")), len(FAILS)))
    raise SystemExit(1 if FAILS else 0)
