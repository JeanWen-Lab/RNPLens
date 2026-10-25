"""The user-facing report: one JSON record and one self-contained HTML page.

The HTML carries no external assets and no scripts. Every number in it comes from the JSON record, and the
limits block is not optional -- `render_html` refuses to emit a page without it, because a report that
states a diagnosis without stating what the diagnosis cannot do is the failure mode this package exists to
avoid.
"""
import html
import json

LIMITS = [
    "These statements describe DISAGREEMENT among structures, not correctness. No probability of "
    "correctness is offered, and none should be inferred.",
    "Disagreement measures variance, not bias. Candidates that are all wrong in the same way will look "
    "consistent here. This is the failure mode the diagnostic cannot see.",
    "The correlations behind each statement were measured on cohorts used in the benchmark's own "
    "development. They are not blind validation.",
    "Error is not attributed to RNA placement separately from RNA shape: that attribution was measured and "
    "did not hold. The placement disagreement is reported without interpretation.",
    "A band names where a value sits in the frozen development reference, not where it sits among the "
    "structures you are looking at. Out of sample that reference did not reproduce the new cohort's "
    "distribution, and the boundaries were deliberately not recalibrated.",
    "The protein-side statement has been validated out of sample (807 targets, 456 clusters, rho 0.525 "
    "[0.450, 0.593]) at an effect substantially smaller than its development estimate. The RNA-side "
    "statement rests on its development cohort and awaits prospective validation.",
    "Candidate disagreement provides COMPLEMENTARY triage information. It is not independent of what the "
    "engine already reports: on the out-of-sample cohort its association with protein error falls from "
    "0.525 to 0.167 [0.069, 0.265] once protein length, protein pTM and mean protein pLDDT are accounted "
    "for, and at a fixed 20% review budget its advantage over protein pTM alone (53.7% against 51.2% of "
    "highest-quintile-error targets recovered) does not resolve, +2.5 percentage points [-3.2, +7.4]. "
    "Read this alongside the engine's own per-chain confidence, not instead of it.",
]
BUDGET_NOTE = ("On the benchmark population, the candidate a user receives improves by about 4 percentage "
               "points from 1 to 5 samples and by about 3.5 more from 5 to 50, while the best candidate "
               "present improves by about 21. Deeper sampling produces better complexes than the engine's "
               "own ranking can identify. The diagnostic above is available from 5 candidates.")


def record(preflight_receipt, validity_summary, disagreement, diagnosis, *, target=None, engines=None,
           applicability=None):
    """The JSON record. Everything the HTML shows is here, and nothing is here that it hides."""
    from . import __version__
    return {"rnpbench_diagnose_version": __version__,
            "target": target,
            "engines": sorted(engines) if engines else None,
            "preflight": preflight_receipt,
            "validity": validity_summary,
            "disagreement": {kx: v for kx, v in disagreement.items() if kx != "values"},
            "diagnosis": diagnosis,
            "applicability": applicability,
            "sampling_budget_note": BUDGET_NOTE,
            "limits": LIMITS}


def render_html(rec):
    """A self-contained page. Refuses to render without the limits block."""
    if not rec.get("limits"):
        raise ValueError("refusing to render a report without its limits block")
    e = html.escape

    def row(k, v):
        return "<tr><th>%s</th><td>%s</td></tr>" % (e(str(k)), e(str(v)))

    v = rec["validity"]
    vrows = "".join(row(kx, v[kx]) for kx in ("n_total", "VALID", "TECHNICAL_FAILURE", "STRUCTURAL_FAILURE")
                    if kx in v)
    if v.get("details"):
        vrows += row("reasons", "; ".join(v["details"]))
    st = []
    for s in rec["diagnosis"]["statements"]:
        if not s.get("available"):
            st.append("<li class='na'><b>%s</b>: not available &mdash; %s</li>"
                      % (e(s["statement"]), e(s.get("reason", ""))))
            continue
        ev = s["evidence"]
        tag = "component-specific" if s["component_specific"] else "not component-specific in this mode"
        st.append("<li><p class='stmt'>%s</p><p class='meta'>%s &middot; Spearman &rho; %.3f "
                  "[%.3f, %.3f] on %s &middot; reference %s (n = %d)</p></li>"
                  % (e(s["text"]), e(tag), ev["rho"], ev["ci"][0], ev["ci"][1], e(ev["cohort"]),
                     e(s["reference"]["source"]), s["reference"]["n"]))
    ap = rec.get("applicability")
    ap_html = banner = ""
    if ap:
        dom = ap["validated_domain"]
        inside = ap["status"] == "inside_validated_domain"
        ap_html = ("<h2>Validated applicability</h2><p class='%s'><b>%s.</b> %s</p><p class='meta'>Validated on: %s. "
                   "Required: %s.</p>%s"
                   % ("ok" if inside else "warnp",
                      "Inside the validated domain" if inside else "Outside the validated domain",
                      "This run matches the conditions under which the statements below were validated."
                      if inside else "The statements below were computed as usual, but no validation covers this "
                      "configuration; do not read them as validated diagnostics.",
                      e(dom["evidence"]), e(dom["chains"]),
                      "" if inside else "<ul class='limits'>%s</ul>" % "".join("<li>%s</li>" % e(x) for x in ap["reasons_outside"])))
        if not inside:
            banner = ("<p class='banner'><b>Outside the validated domain.</b> This configuration was run at the user's "
                      "explicit request; see &ldquo;Validated applicability&rdquo;.</p>")
    na = rec["diagnosis"].get("measured_but_not_attributed")
    na_html = ""
    if na:
        na_html = ("<h2>Measured, not attributed</h2><p>RNA placement disagreement "
                   "<b>%.2f &Aring;</b>. This value is reported without interpretation.</p>"
                   "<p class='meta'>%s</p>" % (na["rna_placement_c4_rmsd"], e(na["why"])))
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>RNPLens Diagnose: %(target)s</title>
<style>
body{font:14px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:52em;margin:2.2em auto;padding:0 1.2em;color:#1d1d1f}
h1{font-size:1.5em;margin:0 0 .15em} h2{font-size:1.05em;margin:1.8em 0 .5em;border-bottom:1px solid #e3e3e6;padding-bottom:.25em}
table{border-collapse:collapse;margin:.4em 0} th,td{padding:.22em .9em .22em 0;text-align:left;vertical-align:top}
th{font-weight:600;color:#3d3d42;white-space:nowrap} ul{list-style:none;padding:0} li{margin:.1em 0 1.1em}
.stmt{margin:0;font-size:1.05em} .meta{margin:.2em 0 0;color:#6e6e73;font-size:.86em}
.na .stmt,.na{color:#6e6e73} .sub{color:#6e6e73;margin:0 0 1.4em}
.limits li{margin:.35em 0;color:#3d3d42;font-size:.92em;padding-left:1.1em;text-indent:-1.1em}
.limits li:before{content:"\u2014\u00a0"}
code{background:#f4f4f6;padding:.05em .3em;border-radius:3px}
.banner{background:#fff1e6;border-left:4px solid #b3541e;padding:.6em .9em;margin:0 0 1.2em} .warnp{color:#8a3a10} .ok{color:#1d1d1f}
</style></head><body>
<h1>Predicted protein&ndash;RNA complex: diagnostic report</h1>
<p class="sub">Target <code>%(target)s</code> &middot; %(mode)s &middot; RNPLens Diagnose (component %(version)s)</p>
%(banner)s<h2>Output validity</h2><table>%(vrows)s</table>
%(ap)s
<h2>What the structures agree about</h2><ul>%(stmts)s</ul>
%(na)s
<h2>Sampling budget</h2><p class="meta">%(budget)s</p>
<h2>What this report does not tell you</h2><ul class="limits">%(limits)s</ul>
</body></html>
""" % {"target": e(str(rec.get("target") or "unnamed")),
       "mode": e(rec["diagnosis"]["mode"].replace("_", " ")),
       "version": e(rec["rnpbench_diagnose_version"]),
       "vrows": vrows, "stmts": "".join(st), "na": na_html, "ap": ap_html, "banner": banner,
       "budget": e(rec["sampling_budget_note"]),
       "limits": "".join("<li>%s</li>" % e(x) for x in rec["limits"])}


def write(rec, outdir):
    """Write report.json and report.html into a directory that must not already hold a report."""
    import os
    os.makedirs(outdir, exist_ok=True)
    for n in ("report.json", "report.html"):
        if os.path.exists(os.path.join(outdir, n)):
            raise FileExistsError("%s already exists; this command will not overwrite a report" % n)
    with open(os.path.join(outdir, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    with open(os.path.join(outdir, "report.html"), "w", encoding="utf-8") as fh:
        fh.write(render_html(rec))
    return sorted(os.listdir(outdir))
