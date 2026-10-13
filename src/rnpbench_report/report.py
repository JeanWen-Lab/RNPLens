"""Reference-free interface report: HTML for a reader, JSON for a pipeline.

THREE THINGS THIS MODULE IS REQUIRED TO DO, from RNPBENCH_PREDICT_PROTOTYPE_FREEZE_V1:
  1. state that agreement is descriptive evidence about convergence of predicted interface hypotheses and not
     a probability of structural correctness;
  2. always show the ACTUAL per-engine contributions -- the per-engine table is rendered before any aggregate
     and cannot be switched off;
  3. never present a single derived reliability number in place of those contributions.
It also never prints an accuracy metric, because none is computed anywhere in this package.

Styling is vendored here (no external style dependency) so a third party gets the same figures.
"""
import base64
import collections
import html
import io
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

ENGINE_NAME = {"AF3": "AlphaFold 3", "BOLTZ2": "Boltz-2", "RF3": "RF3", "CHAI1": "Chai-1",
               "RF2NA": "RF2NA", "OTHER": "other engine"}
ENGINE_ORDER = ["AF3", "BOLTZ2", "RF3", "CHAI1", "RF2NA", "OTHER"]
ENGINE_COLOUR = {"AF3": "#4E6E8E", "BOLTZ2": "#B08560", "RF3": "#C44E52", "CHAI1": "#7A4545",
                 "RF2NA": "#9A88A8", "OTHER": "#777777"}
CONFIDENCE_LABEL = {"iptm": "ipTM (this engine's own interface confidence)",
                    "neg_mean_interchain_pae": "\u2212mean inter-chain PAE (\u00c5), this engine only",
                    "declared_in_contract": "declared in the input contract"}
META_GREY = "#777777"

# The sentence the prototype freeze requires every report to carry, held as ONE constant so that no amount of
# template rewrapping can break it and so the acceptance suite checks the same string the report emits.
SEMANTIC_SENTENCE = ("Agreement is descriptive evidence about convergence of predicted interface hypotheses; "
                     "it is not a probability of structural correctness.")


def _style():
    mpl.rcParams.update({"font.size": 7, "axes.titlesize": 7, "axes.labelsize": 7, "xtick.labelsize": 6,
                         "ytick.labelsize": 6, "axes.spines.top": False, "axes.spines.right": False,
                         "figure.dpi": 110, "savefig.dpi": 200, "font.family": "sans-serif"})


def _png(fig):
    b = io.BytesIO()
    fig.savefig(b, format="png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def _support_figure(result, engines):
    s = result["summary"]
    occ = {}
    for e in engines:
        outs = [r for r in result["per_output"] if r["engine"] == e and r["state"] == "ELIGIBLE"]
        c = collections.Counter()
        for r in outs:
            for x in result["contacts_by_output"]["%s|%s" % (e, r["execution"])]:
                c[tuple(x)] += 1.0 / len(outs)
        occ[e] = c
    support = collections.Counter()
    for e in engines:
        for k, v in occ[e].items():
            support[k] += v
    if not support:
        return None
    P = sorted({i for i, _ in support})
    Rn = list(range(1, s["construct"]["rna_length"] + 1))
    M = np.zeros((len(P), len(Rn)))
    for (i, j), v in support.items():
        M[P.index(i), j - 1] = v
    n_el = len(engines)
    _style()
    h = max(2.6, min(7.5, 0.11 * len(P) + 1.6))
    fig = plt.figure(figsize=(min(7.2, 2.4 + 0.22 * len(Rn)) + 1.9, h))
    gs = fig.add_gridspec(1, 2, width_ratios=[max(1.2, 0.22 * len(Rn)), 0.18 * n_el + 0.3], wspace=0.08)
    ax = fig.add_subplot(gs[0, 0])
    cmap = mpl.colors.ListedColormap(["#FFFFFF", "#E7EEF5", "#B9CDE0", "#7FA3C6", "#4A77A6", "#1F4E7A"][: n_el + 1])
    im = ax.imshow(M, aspect="auto", cmap=cmap, vmin=-0.5, vmax=n_el + 0.5, interpolation="nearest")
    ax.set_yticks(range(len(P)))
    ax.set_yticklabels([str(p) for p in P], fontsize=5 if len(P) > 30 else 6)
    step = max(1, len(Rn) // 40)
    ax.set_xticks(range(0, len(Rn), step))
    ax.set_xticklabels([str(Rn[i]) for i in range(0, len(Rn), step)], fontsize=6)
    ax.set_xlabel("RNA position (input numbering)")
    ax.set_ylabel("protein position (input numbering)")
    fig.suptitle("Contact support: how many of the %d eligible engines propose each contact; right, each "
                 "engine's own binding surface" % n_el, x=0.02, ha="left", fontsize=7, y=1.0)
    cb = fig.colorbar(im, ax=ax, ticks=range(n_el + 1), fraction=0.04, pad=0.02)
    cb.ax.tick_params(labelsize=6)
    ax2 = fig.add_subplot(gs[0, 1], sharey=ax)
    for k, e in enumerate(engines):
        surf = collections.Counter()
        for (i, j), f in occ[e].items():
            surf[i] = max(surf[i], f)
        for y, p in enumerate(P):
            if surf[p] > 0:
                ax2.add_patch(mpl.patches.Rectangle((k - 0.4, y - 0.5), 0.8, 1, color=ENGINE_COLOUR[e],
                                                    alpha=0.35 + 0.65 * surf[p], lw=0))
    ax2.set_xlim(-0.6, n_el - 0.4)
    ax2.set_xticks(range(n_el))
    ax2.set_xticklabels([ENGINE_NAME[e] for e in engines], rotation=90, fontsize=6)
    ax2.tick_params(axis="y", left=False, labelleft=False)
    for sp in ax2.spines.values():
        sp.set_visible(False)
    return _png(fig)


def _pairwise_figure(result, engines):
    n = len(engines)
    if n < 2:
        return None
    _style()
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.4))
    specs = (("surface_agreement", "binding-surface agreement", 1.0, "%.2f", "Blues"),
             ("register_agreement", "contact-register agreement", 1.0, "%.2f", "Blues"),
             ("rna_pose_difference_A", "RNA pose difference (\u00c5)", None, "%.0f", "Oranges"))
    for ax, (fld, lab, vmax, fmt, cm) in zip(axs, specs):
        A = np.full((n, n), np.nan)
        for p in result["engine_pairs"]:
            if p["engine_a"] in engines and p["engine_b"] in engines and p[fld] is not None:
                i, j = engines.index(p["engine_a"]), engines.index(p["engine_b"])
                A[i, j] = A[j, i] = p[fld]
        vm = vmax if vmax is not None else (float(np.nanmax(A)) if np.isfinite(A).any() else 1.0)
        ax.imshow(A, cmap=cm, vmin=0, vmax=vm or 1.0)
        for i in range(n):
            for j in range(n):
                if np.isfinite(A[i, j]):
                    ax.text(j, i, fmt % A[i, j], ha="center", va="center", fontsize=5.5, color="black")
        ax.set_xticks(range(n)); ax.set_yticks(range(n))
        ax.set_xticklabels([ENGINE_NAME[e] for e in engines], rotation=90, fontsize=6)
        ax.set_yticklabels([ENGINE_NAME[e] for e in engines], fontsize=6)
        ax.set_title(lab, loc="left", fontsize=7)
    fig.tight_layout()
    return _png(fig)


def reading(summary):
    ms = summary["median_pairwise_surface_agreement"]
    mr = summary["median_pairwise_register_agreement"]
    mp_ = summary["median_pairwise_rna_pose_difference_A"]
    if ms is None or mr is None:
        return ("Fewer than two engines produced an eligible output, so no cross-engine agreement can be "
                "assessed. This is a statement about coverage, not about accuracy.")
    if ms >= 0.5 and mr < 0.3:
        return ("The engines largely agree on which protein surface binds the RNA (median surface agreement "
                "%.2f) but disagree on which nucleotides contact it (median register agreement %.2f). The "
                "binding surface is the better-supported part of the prediction; residue-nucleotide pairings "
                "should be treated as unresolved." % (ms, mr))
    if ms >= 0.5 and mr >= 0.5:
        return ("The engines agree on both the binding surface (median %.2f) and the contact register (median "
                "%.2f). This is agreement, not verification: correlated predictors can share the same error."
                % (ms, mr))
    if ms < 0.3:
        return ("The engines disagree on the binding surface itself (median surface agreement %.2f; median RNA "
                "pose difference %s). No single interface should be taken as the prediction; the separate "
                "hypotheses listed above are the result."
                % (ms, ("%.0f \u00c5" % mp_) if mp_ is not None else "not computable"))
    return ("Partial agreement: median surface agreement %.2f, register %.2f, RNA pose difference %s. Contacts "
            "supported by several engines should be read before those proposed by one."
            % (ms, mr, ("%.0f \u00c5" % mp_) if mp_ is not None else "not computable"))


DOC = """<!doctype html><html><head><meta charset="utf-8"><title>RNPBench Predict: %(case)s</title>
<style>body{font-family:Helvetica,Arial,sans-serif;max-width:980px;margin:24px auto;color:#222;font-size:14px;
line-height:1.45}h1{font-size:20px}h2{font-size:16px;margin-top:28px;border-bottom:1px solid #ddd}
table{border-collapse:collapse;font-size:12.5px}td,th{border:1px solid #ddd;padding:3px 7px;text-align:left}
.note{background:#f6f6f7;border-left:3px solid #999;padding:8px 12px;font-size:13px}
.warn{background:#fff6e5;border-left:3px solid #d08b00;padding:8px 12px;font-size:13px}
code{font-size:11.5px;color:#555}</style></head><body>
<h1>RNPBench Predict &mdash; interface report for %(case)s</h1>
<p class="note"><b>No experimental structure was used and no accuracy was computed.</b>
<b>%(semantics)s</b> Agreement values are counts across prediction engines: engines can agree and still be
wrong. Each engine's own confidence is shown per engine and is not comparable across engines.</p>
<h2>1. Per-engine contributions</h2>
<p>Every declared output, with what it contributed. An output is <i>eligible</i> only if both polymers are
present and every chain matches the declared construct (%(lp)d protein residues, %(lr)d nucleotides), so that
positions can be compared in input numbering. %(nel)d of %(ndecl)d declared outputs are eligible, from
%(neng)d engine(s).</p>
<table><tr><th>engine</th><th>execution</th><th>status</th><th>protein / RNA copies</th><th>contacts</th>
<th>surface residues</th><th>this engine's confidence</th><th>confidence type</th></tr>%(rows)s</table>
%(flags)s
<h2>2. What the predictions propose</h2>
<p>Each cell counts how many eligible engines place that protein residue within 5 &Aring; of that RNA
nucleotide (heavy atoms, any copy). An engine with two executions contributes the fraction of its own
executions (0, 0.5 or 1), so no engine weighs more because it ran more often. Contacts proposed by at least
1, 2, &hellip; engines: %(hist)s.</p>%(fig1)s
<h2>3. Where the hypotheses agree, and where they do not</h2>
<p>Three questions are kept separate: whether engines use the same protein <b>binding surface</b>, whether they
place the RNA in the same <b>pose</b> (C4&prime; RMSD after superposing the protein), and whether they pair the
same protein residues with the same nucleotides (<b>contact register</b>). Agreement is a weighted Jaccard
index (0 none, 1 identical).</p>%(fig2)s
<p>Interface hypotheses: engines grouped when register agreement reaches the threshold. Groups are listed
separately and never averaged, and the largest group is <b>not</b> implied to be correct.</p>
<table><tr><th>threshold</th><th>groups</th></tr>%(hyp)s</table>
%(repeat)s
<h2>4. How to read this</h2><p class="note">%(reading)s</p>
<p style="font-size:11.5px;color:#777">%(prov)s</p></body></html>"""


def build_html(result):
    s = result["summary"]
    engines = [e for e in ENGINE_ORDER if e in s["eligible_engines"]]
    rows = []
    order = {e: i for i, e in enumerate(ENGINE_ORDER)}
    for r in sorted(result["per_output"], key=lambda r: (order.get(r["engine"], 99), r["execution"])):
        status = r["state"].replace("_", " ").lower()
        if r.get("no_interface_contact"):
            status += "; <b>no protein&ndash;RNA contact within 5 &Aring;</b>"
        conf = "not available" if r.get("native") is None else "%.3f" % r["native"]
        kind = r.get("native_kind") or ""
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s / %s</td><td>%s</td><td>%s</td><td>%s</td>"
                    "<td>%s</td></tr>" % (ENGINE_NAME.get(r["engine"], r["engine"]), html.escape(r["execution"]),
                    status, r.get("n_protein_copies", "\u2013"), r.get("n_rna_copies", "\u2013"),
                    r.get("n_contacts", "\u2013"), r.get("n_surface", "\u2013"), conf,
                    html.escape(CONFIDENCE_LABEL.get(kind, kind))))
    flags = []
    if s["ineligible"]:
        flags.append("<p class='warn'>Ineligible outputs: %s. An output missing a polymer is not a "
                     "low-confidence prediction of the complex; it is not a prediction of it.</p>"
                     % ", ".join("%s %s (%s)" % (ENGINE_NAME.get(e, e), x, st.replace("_", " ").lower())
                                 for e, x, st in s["ineligible"]))
    if s["outputs_with_no_interface_contact"]:
        flags.append("<p class='warn'>Outputs containing both polymers but <b>no protein&ndash;RNA contact</b> "
                     "within 5 &Aring;: %s. These contribute no interface hypothesis.</p>"
                     % ", ".join("%s %s" % (ENGINE_NAME.get(e, e), x)
                                 for e, x in s["outputs_with_no_interface_contact"]))
    if any(p.get("rna_pose_copy_permutation_capped") for p in result["engine_pairs"]):
        flags.append("<p class='warn'>This case has more equivalent copies than the copy-assignment search "
                     "enumerates, so the RNA pose differences shown are upper bounds on the best assignment.</p>")
    fig1 = _support_figure(result, engines)
    fig2 = _pairwise_figure(result, engines)
    hyp = "".join("<tr><td>%s%s</td><td>%s</td></tr>"
                  % (th, " (primary)" if float(th) == s["primary_threshold"] else "",
                     " | ".join("{" + ", ".join(ENGINE_NAME.get(e, e) for e in g) + "}" for g in groups))
                  for th, groups in sorted(s["interface_hypotheses"].items()))
    rep = s["repeat_agreement"]
    repeat = ""
    if rep:
        repeat = ("<p>Agreement between an engine's own repeated executions, which bounds how much cross-engine "
                  "disagreement can be attributed to the engines rather than to run-to-run variation:</p>"
                  "<table><tr><th>engine</th><th>surface</th><th>register</th><th>RNA pose (&Aring;)</th></tr>"
                  + "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                            % (ENGINE_NAME.get(e, e),
                               "n/a" if v["surface_agreement"] is None else "%.2f" % v["surface_agreement"],
                               "n/a" if v["register_agreement"] is None else "%.2f" % v["register_agreement"],
                               "n/a" if v["rna_pose_difference_A"] is None else "%.1f" % v["rna_pose_difference_A"])
                            for e, v in sorted(rep.items())) + "</table>")
    prov = ("Generated by %s from engine-designated outputs declared in the input contract. Environment: %s. "
            "Structure digests are in <code>result.json</code>; no reference structure was opened."
            % (result["package_version"], "; ".join("%s %s" % (k, v) for k, v in sorted(result["environment"].items())
                                                    if k in ("python", "numpy", "biopython"))))
    return DOC % {"semantics": SEMANTIC_SENTENCE, "case": html.escape(str(s["case_id"])), "lp": s["construct"]["protein_length"],
                  "lr": s["construct"]["rna_length"], "nel": s["n_eligible_outputs"],
                  "ndecl": s["n_declared_outputs"], "neng": s["n_eligible_engines"], "rows": "".join(rows),
                  "flags": "".join(flags),
                  "hist": ", ".join("\u2265%s: %s" % (k, v) for k, v in sorted(s["contact_support_histogram"].items())) or "none",
                  "fig1": ("<img src=\"%s\" style=\"max-width:100%%\">" % fig1) if fig1 else
                          "<p class='warn'>No contact was proposed by any engine, so there is no support map.</p>",
                  "fig2": ("<img src=\"%s\" style=\"max-width:100%%\">" % fig2) if fig2 else
                          "<p class='warn'>Fewer than two engines are eligible, so no pairwise comparison exists.</p>",
                  "hyp": hyp, "repeat": repeat, "reading": reading(s), "prov": prov}


def write(result, outdir):
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, "report_%s.html" % result["summary"]["case_id"])
    with open(p, "w") as fh:
        fh.write(build_html(result))
    return p
