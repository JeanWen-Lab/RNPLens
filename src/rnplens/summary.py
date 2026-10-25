"""Build the analysis summary from module output files only (see analyse.py), and render it as HTML."""
import datetime
import html as H
import json
import os

DIAGNOSE_NOT_REQUALIFIED = ("Diagnose statements are shown as produced by the rc3 Diagnose tool. Their interpretation "
                            "(association with error, validated domain) is not offered by the 0.4 question menu: its "
                            "licensing evidence is being re-qualified under the corrected residue correspondence.")
from .analyse import FIXED_LIMITS, GEOMETRY_WITHHELD, REFERENCE_LIMIT, REPEAT_NOT_COMPUTED, SUMMARY_SCHEMA

CLASSES = {
    "observed": "read directly from the input files or the module outputs",
    "descriptive": "a count or agreement across the supplied predictions",
    "associated_with_error": "a Diagnose statement whose association with error was measured, inside its validated domain",
    "reference_based": "an Evaluate measurement against the experimental reference you supplied",
    "not_established": "outside what RNPLens measures",
}


def _load(p):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def _designated_cell(r, inv):
    """QA O4: the run's engine-designated structure, marked when it was excluded at import (not analysed)."""
    ex, verdict = r.get("designated_execution"), r.get("designated_verdict")
    if ex and r.get("designated_included") is None:          # manifests written before run rows carried the flag
        s = next((s for s in inv["structures"] if s.get("designated") and s["run"] == r["run"] and s["engine"] == r["engine"]), None)
        verdict = s["verdict"] if s else None
    if ex and verdict and verdict != "INCLUDED":
        return "%s - excluded at import (%s); not analysed" % (ex, verdict)
    return ex


def build(man, out, steps, reference):
    from . import __version__
    inc = [s for s in man["structures"] if s["verdict"] == "INCLUDED"]
    by_exec = {(s["engine"], s["execution"]): s["id"] for s in inc}
    ps, rs = man["construct"]["protein_sequence"], man["construct"]["rna_sequence"]
    S = {"summary": SUMMARY_SCHEMA, "rnplens_version": __version__,
         "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
         "case_id": man["case_id"], "statement_classes": CLASSES,
         "construct": {"protein_length": len(ps), "rna_length": len(rs)},
         "inventory": {"class": "observed", "source": "manifest.json", "counts": man["counts"], "runs": man["runs"],
                       "structures": [{"id": s["id"], "engine": s["engine"], "run": s["run"], "sample": s["sample"],
                                       "designated": s.get("designated"), "verdict": s["verdict"], "reasons": s["reasons"],
                                       "derived": bool(s.get("derived")), "path": s["path"]} for s in man["structures"]],
                       "unrecognised_files": man["unrecognised_files"], "decisions": man["decisions"]},
         "steps": steps,
         "limits": [REFERENCE_LIMIT if (reference and "closest to the experimental complex" in x) else x for x in FIXED_LIMITS]}

    rr = _load(os.path.join(out, "report", "result.json"))
    cbo = _load(os.path.join(out, "report", "contacts_by_output.json"))
    if rr is None or cbo is None:
        S["report"] = {"status": "NOT_AVAILABLE", "message": steps["report"]["message"]}
    else:
        summ = rr["summary"]
        elig = [(o["engine"], o["execution"]) for o in rr["per_output"] if o["state"] == "ELIGIBLE"]
        engines = sorted({e for e, _ in elig})
        den = {e: sum(1 for x, _ in elig if x == e) for e in engines}
        S["report"] = {"status": "RAN", "source": "report/result.json",
                       "eligible_structures": [by_exec[k] for k in elig],
                       "ineligible": [{"structure": by_exec.get((e, x)), "state": st} for e, x, st in summ["ineligible"]],
                       "no_interface_contact": [by_exec.get(tuple(k)) for k in summ["outputs_with_no_interface_contact"]],
                       "engines": engines, "denominators": den}
        # contacts: numerators from Report's own per-structure lists
        rows = {}
        for key, cl in sorted(cbo.items()):
            e, x = key.split("|", 1)
            sid = by_exec[(e, x)]
            for i, j in cl:
                r = rows.setdefault((i, j), {e2: [] for e2 in engines})
                r[e].append(sid)
        crow = []
        for (i, j), per in sorted(rows.items()):
            crow.append({"protein_position": i, "protein_residue": ps[i - 1], "rna_position": j, "rna_nucleotide": rs[j - 1],
                         "per_engine": {e: {"count": len(v), "of": den[e], "structures": sorted(v)} for e, v in per.items()},
                         "report_contact_support": rr["contact_support"]["%d,%d" % (i, j)]})
        S["contacts"] = {"class": "descriptive", "source": "report/contacts_by_output.json, report/result.json:contact_support",
                         "definition": "protein residue and RNA nucleotide with any heavy-atom pair within 5.0 A, in "
                                       "construct positions (Report's own contact lists)",
                         "denominators": den,
                         "engine_weighting": "report_contact_support is Report's value: for each engine, the fraction of "
                                             "that engine's eligible structures listing the contact, added over engines. "
                                             "An engine contributes at most 1, however many structures it supplied.",
                         "rows": crow}
        for kind, idx, seq in (("protein_positions", 0, ps), ("rna_positions", 1, rs)):
            pos = {}
            for key, cl in cbo.items():
                e, x = key.split("|", 1)
                for p in {c[idx] for c in cl}:
                    pos.setdefault(p, {e2: set() for e2 in engines})[e].add(by_exec[(e, x)])
            S[kind] = {"class": "descriptive", "source": "report/contacts_by_output.json",
                       "definition": "structures in which the position takes part in at least one contact",
                       "rows": [{"position": p, "residue": seq[p - 1],
                                 "per_engine": {e: {"count": len(v), "of": den[e], "structures": sorted(v)} for e, v in per.items()}}
                                for p, per in sorted(pos.items())]}
        rep = {}
        for e in engines:
            if e in summ["repeat_agreement"]:
                rep[e] = {"status": "COMPUTED_BY_REPORT", "class": "descriptive",
                          "source": "report/result.json:summary.repeat_agreement.%s" % e, **summ["repeat_agreement"][e]}
            else:
                rep[e] = {"status": "NOT_COMPUTED", "text": REPEAT_NOT_COMPUTED, "n_structures": den[e],
                          "reason": "RNPLens Report (rc3 components) computes repeat agreement only for an engine with "
                                    "exactly two eligible structures; this engine has %d. Not computed is not zero "
                                    "agreement. The contact and position counts above still apply." % den[e]}
        S["repeat_agreement"] = rep
        runrep = {}
        for st in steps.get("run_repeat", []):
            e = st["engine"]
            if st["status"] != "RAN":
                runrep[e] = {"status": "NOT_COMPUTED", "reason": st.get("reason") or st.get("message")}
                continue
            src = _load(os.path.join(out, st["dir"], "result.json"))
            ra = (src or {}).get("summary", {}).get("repeat_agreement", {}).get(e)
            if ra is None:
                runrep[e] = {"status": "NOT_COMPUTED", "reason": "Report computed no repeat agreement for the two structures"}
                continue
            rules = {r["run"]: r["designated_rule"] for r in man["runs"] if r["engine"] == e}
            runrep[e] = {"status": "COMPUTED_BY_REPORT", "class": "descriptive", "structures": st["structures"],
                         "runs": st["runs"], "designation_rules": [rules.get(r) for r in st["runs"]],
                         "source": "%s/result.json:summary.repeat_agreement.%s" % (st["dir"], e),
                         "what": "Report's repeat agreement between the engine-designated structure of each of the two runs",
                         **ra}
        S["run_repeat_agreement"] = runrep
        S["engine_pairs"] = {"class": "descriptive", "source": "report/result.json:engine_pairs",
                             "pairs": rr["engine_pairs"], "interface_hypotheses": summ["interface_hypotheses"],
                             "note": "Report groups ENGINES, not structures; with one engine there is exactly one group."} \
            if len(engines) > 1 else {"status": "NOT_APPLICABLE", "reason": "one engine supplied"}

    # Diagnose
    S["diagnose"] = []
    if steps["diagnose"] and DIAGNOSE_NOT_REQUALIFIED not in S["limits"]:
        S["limits"].append(DIAGNOSE_NOT_REQUALIFIED)
    for st in steps["diagnose"]:
        row = {k: st.get(k) for k in ("mode", "engine", "structures", "status", "reason", "message")}
        if st.get("dir"):
            d = _load(os.path.join(out, st["dir"], "report.json"))
            row.update({"class": "associated_with_error", "source": "%s/report.json" % st["dir"],
                        "applicability": d["applicability"]["status"],
                        "reasons_outside": d["applicability"]["reasons_outside"], "validity": d["validity"],
                        "statements": [{k: v for k, v in x.items() if k != "evidence"} for x in d["diagnosis"].get("statements", [])],
                        "measured_but_not_attributed": d["diagnosis"].get("measured_but_not_attributed"),
                        "refused_statements": d["diagnosis"].get("refused_statements"), "limits": d.get("limits")})
        S["diagnose"].append(row)

    # Evaluate
    S["evaluate"] = []
    for st in steps["evaluate"]:
        r = _load(os.path.join(out, st["dir"], "result.json"))
        if r is None:
            S["evaluate"].append({"structure": st["structure"], "status": "NO_RESULT", "message": st["message"]}); continue
        dq = r["dockq"]
        pi = dq.get("per_interface") or {}
        sm = next((s for s in man["structures"] if s["id"] == st["structure"]), {})
        S["evaluate"].append({"structure": st["structure"], "run": sm.get("run"), "sample": sm.get("sample"),
                              "designated": sm.get("designated"), "class": "reference_based",
                              "source": "%s/result.json" % st["dir"],
                              "dockq_status": dq["status"], "dockq": dq.get("dockq"), "dockq_class": dq.get("dockq_class"),
                              "fnat_per_interface": {k: v.get("fnat") for k, v in pi.items()} or None,
                              "irmsd_per_interface": {k: v.get("iRMSD") for k, v in pi.items()} or None,
                              "lrmsd_per_interface": {k: v.get("LRMSD") for k, v in pi.items()} or None})
    S["evaluate_reference"] = os.path.abspath(reference) if reference else None
    S["evaluate_withheld"] = GEOMETRY_WITHHELD if reference else None
    return S


# ---------------------------------------------------------------- HTML
def _cnt(per):
    return ", ".join("%s %d/%d" % (e, v["count"], v["of"]) for e, v in per.items())


def _table(head, rows):
    h = "<tr>" + "".join("<th>%s</th>" % H.escape(str(x)) for x in head) + "</tr>"
    b = "".join("<tr>" + "".join("<td>%s</td>" % H.escape("" if x is None else str(x)) for x in r) + "</tr>" for r in rows)
    return "<table>%s%s</table>" % (h, b)


def _fmt(v, nd=3):
    return "NO VALUE" if v is None else (("%." + str(nd) + "f") % v if isinstance(v, float) else str(v))


def contact_map_png(S, path):
    try:
        import matplotlib
    except ImportError:          # matplotlib is the optional "html" extra; the page is written without the image
        return None
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    rows = S["contacts"]["rows"]
    engines = list(S["contacts"]["denominators"])
    pp = sorted({r["protein_position"] for r in rows})
    if not pp:
        return False
    L = S["construct"]["rna_length"]
    fig, axs = plt.subplots(1, len(engines), figsize=(min(4 + 0.12 * L, 14) * len(engines) ** 0.5, 1.6 + 0.16 * len(pp)), squeeze=False)
    for ax, e in zip(axs[0], engines):
        M = np.full((len(pp), L), np.nan)
        for r in rows:
            v = r["per_engine"][e]
            if v["count"]:
                M[pp.index(r["protein_position"]), r["rna_position"] - 1] = v["count"] / v["of"]
        im = ax.imshow(M, aspect="auto", cmap="viridis", vmin=0, vmax=1, interpolation="nearest")
        ax.set_yticks(range(len(pp))); ax.set_yticklabels(["%s%d" % (S["protein_positions_seq"][p - 1], p) for p in pp], fontsize=7)
        ax.set_xticks(range(0, L, max(1, L // 15))); ax.set_xticklabels([str(i + 1) for i in range(0, L, max(1, L // 15))], fontsize=7)
        ax.set_xlabel("RNA position"); ax.set_title("%s\n%d structure(s)" % (e, S["contacts"]["denominators"][e]), fontsize=9)
    fig.colorbar(im, ax=axs[0].tolist(), shrink=0.8, label="fraction of the engine's structures listing the contact")
    fig.savefig(path, dpi=130, bbox_inches="tight"); plt.close(fig)
    return True


CSS = ("body{font-family:Helvetica,Arial,sans-serif;max-width:1100px;margin:24px auto;color:#222;line-height:1.4}"
       "table{border-collapse:collapse;margin:8px 0 16px;font-size:13px}td,th{border:1px solid #ccc;padding:3px 7px;text-align:left}"
       "th{background:#f1f1f1}.cls{font-size:11px;color:#555;border:1px solid #bbb;border-radius:3px;padding:0 4px;margin-left:6px}"
       ".lim{background:#fff6e5;border-left:4px solid #e0a020;padding:6px 12px}.na{color:#8a3b00}")


def render_html(S, man, out):
    S["protein_positions_seq"] = man["construct"]["protein_sequence"]
    c = lambda k: '<span class="cls">%s</span>' % H.escape(k)
    p = ["<!doctype html><html><head><meta charset='utf-8'><title>RNPLens analysis: %s</title><style>%s</style></head><body>"
         % (H.escape(S["case_id"]), CSS)]
    p.append("<h1>RNPLens analysis: %s</h1><p>RNPLens %s. Built only from the outputs of Report, Diagnose%s, each run "
             "unchanged (see <code>commands.log</code>). Labels: %s</p>" % (
                 H.escape(S["case_id"]), H.escape(S["rnplens_version"]), " and Evaluate" if S["evaluate"] else "",
                 "; ".join("%s %s" % (c(k), H.escape(v)) for k, v in S["statement_classes"].items())))
    inv = S["inventory"]
    p.append("<h2>1. Predicted complexes %s</h2>" % c("observed"))
    p.append("<p>%d structure file(s) found; %d candidate(s) recognised; %d included; %d excluded; %d unrecognised.</p>" % (
        inv["counts"]["found"], inv["counts"]["candidates"], inv["counts"]["included"], inv["counts"]["excluded"], inv["counts"]["unrecognised"]))
    p.append(_table(["run", "engine", "structures", "engine-designated structure", "rule"],
                    [[r["run"], r["engine"], r["n_structures"], _designated_cell(r, inv), r["designated_rule"]] for r in inv["runs"]]))
    exc = [s for s in inv["structures"] if s["verdict"] != "INCLUDED"]
    if exc:
        p.append("<p>Excluded:</p>" + _table(["id", "file", "verdict", "reason"], [[s["id"], s["path"], s["verdict"], "; ".join(s["reasons"])] for s in exc]))
    der = [s for s in inv["structures"] if s["derived"]]
    if der:
        p.append("<p>Derived copies used (originals unchanged): %s</p>" % H.escape(", ".join(s["id"] for s in der)))
    if S.get("report", {}).get("status") != "RAN":
        p.append("<p class='na'>Report did not produce a result: %s</p>" % H.escape(str(S.get("report", {}).get("message"))))
    else:
        R = S["report"]
        p.append("<h2>2. Contacts proposed (counts) %s</h2>" % c("descriptive"))
        p.append("<p>Contact: %s. Each count reads &quot;k/n&quot;: k of the engine's n eligible structures list the "
                 "contact (Report's own per-structure lists). %s</p>" % (H.escape(S["contacts"]["definition"]), H.escape(S["contacts"]["engine_weighting"])))
        if R["ineligible"] or R["no_interface_contact"]:
            p.append("<p>Not counted: %s. Predicted both polymers but no contact: %s.</p>" % (
                H.escape(", ".join("%s (%s)" % (x["structure"], x["state"]) for x in R["ineligible"]) or "none"),
                H.escape(", ".join(str(x) for x in R["no_interface_contact"]) or "none")))
        cm = contact_map_png(S, os.path.join(out, "contact_map.png"))
        if cm:
            p.append("<img src='contact_map.png' style='max-width:100%' alt='contact map'>")
        elif cm is None:
            p.append("<p>Contact map image not drawn: matplotlib is not installed (pip install 'rnplens[html]'). "
                     "All counts below are unaffected.</p>")
        rows = S["contacts"]["rows"]
        p.append("<details><summary>All %d contacts proposed by at least one structure</summary>%s</details>" % (len(rows), _table(
            ["protein", "RNA", "structures with the contact (k/n per engine)", "Report contact_support (engine-weighted)", "structures"],
            [["%s%d" % (r["protein_residue"], r["protein_position"]), "%s%d" % (r["rna_nucleotide"], r["rna_position"]), _cnt(r["per_engine"]),
              "%.6g" % r["report_contact_support"], " ".join(s for v in r["per_engine"].values() for s in v["structures"])] for r in rows])))
        for kind, lab in (("protein_positions", "Protein positions"), ("rna_positions", "RNA positions")):
            rr = S[kind]["rows"]
            p.append("<h3>%s in contact %s</h3>" % (lab, c("descriptive")) + _table(["position", "structures with a contact here (k/n per engine)"],
                     [["%s%d" % (r["residue"], r["position"]), _cnt(r["per_engine"])] for r in rr]))
        p.append("<h2>3. Agreement and disagreement between structures %s</h2>" % c("descriptive"))
        p.append("<h3>Agreement between an engine's structures</h3>")
        for e, v in S["repeat_agreement"].items():
            if v["status"] == "COMPUTED_BY_REPORT":
                p.append("<p>%s (Report repeat agreement, two structures): binding-surface agreement %s, contact-register "
                         "agreement %s, RNA pose difference %s &Aring;.</p>" % (e, _fmt(v["surface_agreement"]), _fmt(v["register_agreement"]), _fmt(v["rna_pose_difference_A"])))
            else:
                p.append("<p class='na'><b>%s: %s</b> %s</p>" % (e, H.escape(v["text"]), H.escape(v["reason"])))
        for e, v in S.get("run_repeat_agreement", {}).items():
            if v["status"] == "COMPUTED_BY_REPORT":
                p.append("<p>%s, between runs (Report repeat agreement on the designated structure of each run: %s from %s, "
                         "%s from %s; designation: %s): binding-surface agreement %s, contact-register agreement %s, RNA pose "
                         "difference %s &Aring;.</p>" % (e, v["structures"][0], H.escape(v["runs"][0]), v["structures"][1],
                         H.escape(v["runs"][1]), H.escape("; ".join(str(x) for x in v["designation_rules"])),
                         _fmt(v["surface_agreement"]), _fmt(v["register_agreement"]), _fmt(v["rna_pose_difference_A"])))
            else:
                p.append("<p class='na'>%s, between runs: not computed. %s</p>" % (e, H.escape(str(v["reason"]))))
        if S["engine_pairs"].get("pairs"):
            ep = S["engine_pairs"]
            p.append("<h3>Agreement between engines</h3>" + _table(["engine A", "engine B", "surface agreement", "register agreement", "RNA pose difference (A)"],
                     [[x["engine_a"], x["engine_b"], _fmt(x["surface_agreement"]), _fmt(x["register_agreement"]), _fmt(x["rna_pose_difference_A"])] for x in ep["pairs"]]))
            p.append("<p>Engine groups at register agreement 0.3 / 0.5 / 0.7: %s. %s</p>" % (H.escape(json.dumps(ep["interface_hypotheses"])), H.escape(ep["note"])))
    p.append("<h2>4. Diagnose %s</h2>" % c("associated_with_error"))
    if S["diagnose"]:
        p.append("<p class='na'>%s</p>" % H.escape(DIAGNOSE_NOT_REQUALIFIED))
    if S["steps"].get("diagnose_blocked"):
        p.append("<p class='na'>Diagnose was not run: %s (%s).</p>" % (H.escape(S["steps"]["diagnose_blocked"]["status"]),
                                                                      H.escape(S["steps"]["diagnose_blocked"]["reason"])))
    elif S["steps"].get("diagnose_skipped"):
        p.append("<p class='na'>Diagnose was not run (--without-diagnose).</p>")
    for d in S["diagnose"]:
        if d["status"] != "RAN":
            p.append("<p class='na'>%s %s: %s. %s</p>" % (d["mode"], d["engine"], d["status"], H.escape(str(d.get("reason") or d.get("message") or ""))[:900]))
            continue
        p.append("<p>%s, %s: validity %s; applicability: %s%s</p>" % (d["mode"], d["engine"], H.escape(json.dumps({k: d["validity"][k] for k in ("VALID", "TECHNICAL_FAILURE", "STRUCTURAL_FAILURE")})),
                 H.escape(d["applicability"]), (" (" + H.escape("; ".join(d["reasons_outside"])) + ")") if d["reasons_outside"] else ""))
        p.append(_table(["axis", "disagreement (A)", "band", "percentile in the frozen development reference", "Diagnose statement"],
                        [[x.get("axis"), _fmt(x.get("disagreement_angstrom")), x.get("band"), x.get("percentile_in_reference"), x.get("text")] for x in d["statements"]]))
        if d.get("measured_but_not_attributed"):
            m = d["measured_but_not_attributed"]
            p.append("<p>RNA placement disagreement %s &Aring;: measured, not interpreted (%s)</p>" % (_fmt(m.get("rna_placement_c4_rmsd")), H.escape(m.get("why", ""))))
    if S["evaluate"]:
        p.append("<h2>5. Against the experimental reference %s</h2><p>Reference: %s</p>" % (c("reference_based"), H.escape(S["evaluate_reference"])))
        jn = lambda d: ", ".join("%s %s" % (k, _fmt(v)) for k, v in (d or {}).items())
        p.append(_table(["structure", "run", "sample", "engine-designated", "DockQ status", "DockQ", "class", "fnat", "iRMSD (A)", "LRMSD (A)"],
                 [[e["structure"], e.get("run"), e.get("sample"), "yes" if e.get("designated") else "no", e.get("dockq_status"),
                   _fmt(e.get("dockq")), e.get("dockq_class"), jn(e.get("fnat_per_interface")), jn(e.get("irmsd_per_interface")),
                   jn(e.get("lrmsd_per_interface"))] for e in S["evaluate"]]))
        p.append("<p class='na'>%s</p>" % H.escape(S["evaluate_withheld"]))
    p.append("<h2>What this summary does not establish %s</h2><div class='lim'><ul>%s</ul></div>" % (c("not_established"), "".join("<li>%s</li>" % H.escape(x) for x in S["limits"])))
    p.append("</body></html>")
    S.pop("protein_positions_seq", None)
    return "\n".join(p)
