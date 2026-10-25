"""The licensed diagnostic statements, and the refusal of the one that did not hold.

Each statement below is licensed by a pre-registered result on a named cohort. The mapping from cohort to
permitted wording is deliberately explicit, because the two cohorts licensed DIFFERENT statements:

  within one engine's candidate pool   protein disagreement is specific to protein error
                                       rho +0.869 [+0.765, +0.927], beating the RNA axes by +0.452 and +0.530
                                       the RNA axes were NOT separable from each other here, so an RNA
                                       statement in this mode may not distinguish shape from placement

  across three or more engines         RNA-conformation disagreement is specific to RNA-conformation error
                                       rho +0.901 [+0.800, +0.952], beating the others by +0.421 and +0.207
                                       protein disagreement was NOT resolved as specific here

  either mode                          placement disagreement is never specific: it failed to beat
                                       RNA-conformation error in both cohorts (-0.008 and -0.084)

`attribute_placement()` therefore raises. The value is still measured and still reported, under a key that
says it is not attributed, because hiding it would be worse than labelling it.
"""
import csv
import hashlib
import os
import statistics

MODES = ("within_engine", "cross_engine")
BANDS = ("low", "typical", "high", "very high")

EVIDENCE = {
    ("within_engine", "protein_side"): {
        "specific": True, "rho": 0.869, "ci": [0.765, 0.927],
        "cohort": "65 targets, 58 protein clusters, one engine, 50 candidates each",
        "margin_over_off_diagonals": [0.452, 0.530],
        "out_of_sample": {"rho": 0.525, "ci": [0.450, 0.593],
                          "cohort": "807 targets, 456 protein clusters, disjoint from development",
                          "margin_over_off_diagonals": [0.234, 0.129],
                          "verdict": "PASS on the same frozen criterion",
                          "note": "smaller than the development estimate; transport shrinkage of 0.344 "
                                  "with identical definitions and a matched five-candidate development "
                                  "control. Plan with 0.5, not 0.87."}},
    ("within_engine", "rna_side"): {
        "specific": False, "rho": 0.843, "ci": [0.740, 0.906],
        "cohort": "65 targets, 58 protein clusters, one engine, 50 candidates each",
        "not_separable_from": "rna_placement (paired difference +0.080 [-0.012, +0.213])"},
    ("cross_engine", "rna_side"): {
        "specific": True, "rho": 0.901, "ci": [0.800, 0.952],
        "cohort": "59 targets, 59 protein clusters, four engines, six engine pairs each",
        "margin_over_off_diagonals": [0.421, 0.207],
        "out_of_sample": {"verdict": "NOT TESTED",
                          "note": "only 13 out-of-sample targets carry three or more engines with a "
                                  "native, declared descriptive-only in advance. This statement rests on "
                                  "its development cohort and awaits prospective validation."}},
    ("cross_engine", "protein_side"): {
        "specific": False, "rho": 0.639, "ci": [0.424, 0.789],
        "cohort": "59 targets, 59 protein clusters, four engines, six engine pairs each",
        "not_separable_from": "rna_internal (paired difference +0.155 [-0.084, +0.380])"},
}

REFERENCE_FILES = {"within_engine": "cohortP_disagreement.tsv", "cross_engine": "cohortE_disagreement.tsv"}
AXIS_FOR = {"protein_side": "prot_internal_ca_rmsd", "rna_side": "rna_internal_c4_rmsd"}


class NotLicensed(Exception):
    """Raised for a statement the measurements did not support."""


def attribute_placement(*_a, **_k):
    """Refused. Placement disagreement did not separate from RNA-conformation error in either cohort."""
    raise NotLicensed(
        "placement attribution is not licensed: placement disagreement failed to beat RNA-conformation "
        "error in both cohorts (paired difference -0.008 [-0.092, +0.069] within engine and "
        "-0.084 [-0.277, +0.109] across engines). The value is reported under "
        "'measured_but_not_attributed'.")


def _reference_dir():
    return os.environ.get("RNPD_REFERENCE",
                          os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reference"))


def reference_distribution(mode, axis):
    """Benchmark distribution of this axis, read from the shipped cohort table. Refuses if absent."""
    if mode not in MODES:
        raise NotLicensed("unknown mode %r; expected one of %s" % (mode, list(MODES)))
    p = os.path.join(_reference_dir(), REFERENCE_FILES[mode])
    if not os.path.exists(p):
        raise NotLicensed("reference distribution missing: %s. The package will not band a value against "
                          "a distribution it cannot read." % p)
    col = "dis_" + axis
    vals = []
    with open(p, encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if r.get("exclusion"):
                continue
            if mode == "within_engine" and r.get("depth") not in (None, "", "50"):
                continue
            v = r.get(col, "")
            if v not in ("", None):
                vals.append(float(v))
    if len(vals) < 10:
        raise NotLicensed("reference distribution for %s/%s has only %d usable rows" % (mode, axis, len(vals)))
    vals.sort()
    return {"n": len(vals), "source": os.path.basename(p),
            "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(),
            "q1": statistics.quantiles(vals, n=4)[0], "median": statistics.median(vals),
            "q3": statistics.quantiles(vals, n=4)[2], "values": vals}


def _band(value, ref):
    if value <= ref["q1"]:
        return "low", 0
    if value <= ref["median"]:
        return "typical", 1
    if value <= ref["q3"]:
        return "high", 2
    return "very high", 3


def _percentile(value, values):
    below = sum(1 for v in values if v < value)
    return 100.0 * below / len(values)


def statement(mode, which, disagreement):
    """One diagnostic statement, with its band, its evidence, and its permitted wording."""
    if which not in AXIS_FOR:
        raise NotLicensed("no licensed statement named %r" % which)
    ev = EVIDENCE.get((mode, which))
    if ev is None:
        raise NotLicensed("no measurement licenses %r in mode %r" % (which, mode))
    axis = AXIS_FOR[which]
    if disagreement.get("refused"):
        return {"statement": which, "mode": mode, "available": False,
                "reason": disagreement["refused"]}
    value = disagreement[axis]
    ref = reference_distribution(mode, axis)
    band, rank = _band(value, ref)
    subject = {"protein_side": "the protein", "rna_side": "the RNA"}[which]
    if ev["specific"]:
        scope = subject if which == "protein_side" else "the RNA's conformation"
    else:
        scope = (subject + " (this mode cannot separate its shape from its placement)"
                 if which == "rna_side" else subject + " (not resolved as specific in this mode)")
    verdict = {0: "consistent", 1: "consistent", 2: "variable", 3: "variable"}[rank]
    # The band is stated RELATIVE TO THE FROZEN DEVELOPMENT REFERENCE, never as a quantile of the cohort
    # in hand. Out-of-sample the reference distribution did not reproduce the new cohort's distribution --
    # 368 of 807 targets fell in the top band where development had a quarter by construction -- so a
    # phrase like "top quartile in this cohort" would be false. The bands stayed discriminative anyway
    # (median protein error 0.59 A in the low band against 10.35 A in the very high band), which is why
    # the boundaries were not recalibrated.
    text = ("%s is %s across the %s: disagreement %.2f A, %s relative to the frozen development reference "
            "(%.0fth percentile of %d development targets)."
            % (scope[0].upper() + scope[1:], verdict,
               "candidates" if mode == "within_engine" else "engines",
               value, band, _percentile(value, ref["values"]), ref["n"]))
    return {"statement": which, "mode": mode, "available": True, "axis": axis,
            "disagreement_angstrom": round(value, 3), "band": band,
            "percentile_in_reference": round(_percentile(value, ref["values"]), 1),
            "reference": {kx: (round(ref[kx], 3) if isinstance(ref[kx], float) else ref[kx])
                          for kx in ("n", "source", "sha256", "q1", "median", "q3")},
            "component_specific": ev["specific"], "evidence": ev, "text": text}


def diagnose(mode, disagreement):
    """Both licensed statements, plus the measured-but-unattributed placement value."""
    if mode not in MODES:
        raise NotLicensed("unknown mode %r" % mode)
    out = {"mode": mode, "statements": [statement(mode, w, disagreement) for w in ("protein_side", "rna_side")]}
    if not disagreement.get("refused"):
        out["measured_but_not_attributed"] = {
            "rna_placement_c4_rmsd": round(disagreement["rna_placement_c4_rmsd"], 3),
            "why": attribute_placement_reason()}
    out["refused_statements"] = list(("placement_attribution", "probability_of_correctness",
                                      "best_engine_recommendation"))
    return out


def attribute_placement_reason():
    try:
        attribute_placement()
    except NotLicensed as ex:
        return str(ex)
    raise AssertionError("attribute_placement must refuse")
