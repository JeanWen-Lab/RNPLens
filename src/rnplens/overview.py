"""Menu item A: compare binding surfaces and contacts across the project's structures.

This is the existing qualified route, unchanged: `rnplens analyse` (Report; Diagnose not run, because its
interpretation is not re-qualified; Evaluate only with a reference). This module only runs it when no analysis
exists yet and summarises what the analysis already recorded, with evidence IDs into summary.json."""
import json
import os

from . import provenance as pv

CAPABILITIES = [
    {"id": "interface_overview", "menu": "A", "status": "QUALIFIED",
     "label": "Binding surfaces and residue-nucleotide contacts across all structures (Report, reference-free)",
     "needs": ["project", "analysis_new?"], "call": "rnplens.overview:capability_run",
     "limits": "Agreement and recurrence among predictions describe the predictions; they are not evidence of "
               "correctness."},
]


def _counts(S):
    rows = S["contacts"]["rows"]
    out = {}
    for eng, d in S["contacts"]["denominators"].items():
        n = d if isinstance(d, int) else d.get("n", d.get("of"))
        per = [r["per_engine"][eng]["count"] for r in rows if eng in r["per_engine"]]
        out[eng] = {"structures": n, "contacts_any": sum(1 for c in per if c > 0),
                    "contacts_all": sum(1 for c in per if n and c == n),
                    "contacts_at_least_half": sum(1 for c in per if n and 2 * c >= n)}
    return out


def capability_run(project, analysis=None, **_):
    from . import analyse
    if not analysis:
        analysis = os.path.join(project, "analysis_overview")
    if not os.path.exists(os.path.join(analysis, "summary.json")):
        if os.path.exists(analysis) and os.listdir(analysis):
            return {"status": "REFUSED", "outputs": [], "message": "%s exists but has no summary.json" % analysis}
        import contextlib
        import sys
        with contextlib.redirect_stdout(sys.stderr):
            code = analyse.run(project, analysis, None, 1, diagnose=False)
        if code != 0:
            return {"status": "FAILED", "outputs": [], "message": "rnplens analyse exit %d; see %s" % (code, analysis)}
    S = json.load(open(os.path.join(analysis, "summary.json")))
    agree = {}
    for key in ("repeat_agreement", "run_repeat_agreement"):
        for eng, v in (S.get(key) or {}).items():
            if isinstance(v, dict) and v.get("surface_agreement") is not None:
                agree["%s:%s" % (key, eng)] = {
                    "surface_agreement": v["surface_agreement"], "register_agreement": v.get("register_agreement"),
                    "rna_pose_difference_A": v.get("rna_pose_difference_A"),
                    "evidence_id": pv.evidence_id("summary.json", "/%s/%s" % (key, eng))}
    return {"status": "OK", "outputs": [os.path.join(analysis, "summary.html"), os.path.join(analysis, "summary.json")],
            "summary": {"contacts_by_engine": _counts(S), "agreement": agree,
                        "contact_definition": S["contacts"]["definition"],
                        "evidence_id": pv.evidence_id("summary.json", "/contacts")},
            "message": "Report analysis of %s (reference-free). %s" % (analysis, CAPABILITIES[0]["limits"])}
