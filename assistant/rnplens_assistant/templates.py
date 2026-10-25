"""Deterministic, evidence-linked answers (no second language-model call). Each statement is built from evidence
records by fixed rules; every value is a slot filled from the record. The only comparisons are between two measured
values (for example register agreement lower than surface agreement); no threshold is introduced."""
from . import evidence as EV

CAP_TEXT = {
    "ranking_or_selection": "RNPLens does not rank, select or recommend structures in this version (the Rank study was closed without a public method). "
                            "It can instead describe what the supplied structures agree and disagree on and, with an experimental reference, report DockQ, fnat, iRMSD and LRMSD for each structure.",
    "diagnose_disagreement": "Diagnose is not available in this assistant version while its statements are requalified against corrected evidence. "
                             "The contact and agreement summaries of the supplied structures can be run instead.",
    "geometry_decomposition": "The decomposition into RNA conformation, RNA placement and protein-internal geometry is not available: that route has a known residue-correspondence defect and its corrected implementation is not yet qualified. "
                              "With a reference, DockQ, fnat, iRMSD and LRMSD can be compared instead; iRMSD and LRMSD are DockQ quantities with their own definitions, not that decomposition.",
    "new_prediction": "RNPLens assesses existing predictions and does not predict structures. Predictions made elsewhere can be imported and analysed instead.",
    "mutation_advice": "RNPLens does not recommend mutations or experiments. It can instead list the contacts and positions the supplied structures propose and how often each recurs.",
    "grouping": "Selecting or ranking a group of structures is not offered. The structures can instead be shown as distinct binding proposals (which structures make the same proposal), without any order by size or selection.",
    "reference_accuracy_without_reference": "Accuracy against the experimental complex cannot be measured without an experimental reference structure. "
                                            "The agreement between the supplied predictions can be described instead, or an experimental reference can be supplied for an Evaluate comparison.",
    "other": "This request is outside the analyses available in this version. The available analyses are contact and agreement summaries without a reference and DockQ-family comparisons with a supplied reference.",
}


def _f(store, pred):
    return [r for r in store.records if r["state"] == "COMPUTED" and pred(r)]


def _one(store, pred):
    x = _f(store, pred)
    return x[0] if x else None


def build(plan, store, notes):
    goal, S = plan["goal"], []
    add = lambda t, text, ids: S.append({"type": t, "text": text, "evidence_ids": [i for i in ids if i]})
    q = [r for r in store.records if r["state"] == "IDENTITY_UNRESOLVED"]
    refused = [r for r in store.records if r["tool"] == "import_predictions" and r["state"] in ("INPUT_REFUSED", "INPUT_MISSING", "INPUT_INVALID", "ACCESS_REFUSED")]
    if q:
        add("CLARIFICATION_REQUEST", "The import stopped because something is ambiguous; nothing was analysed. Please answer the question(s) listed under "
            "'not computed' (records cited), and the analysis can then proceed.", [r["id"] for r in q])
    if refused:
        add("CLARIFICATION_REQUEST", "The predictions could not be imported, so nothing was analysed. The reason is given in the records cited; please fix the "
            "input or state which engine produced files in an unrecognised layout.", [r["id"] for r in refused])
    # inventory
    for inc in _f(store, lambda r: r["field"] == "counts.included"):
        pid = inc["subject"]
        runs = _f(store, lambda r: r["subject"] == pid and r["field"].endswith(".n_structures"))
        exc = _f(store, lambda r: r["subject"] == pid and r["field"] == "counts.excluded")
        txt = "Project %s: {%s} structure(s) included" % (pid, inc["id"])
        if exc and exc[0]["value"]:
            txt += ", {%s} excluded (reasons in the records cited)" % exc[0]["id"]
        if runs:
            txt += "; runs: " + "; ".join("%s with {%s}" % (r["run"], r["id"]) for r in runs)
        des = _f(store, lambda r: r["subject"] == pid and r["field"].endswith(".designated"))
        if des:
            txt += ". Engine-designated structure per run: " + "; ".join("{%s}" % r["id"] for r in des)
        ids = [inc["id"]] + [r["id"] for r in runs + des + exc] + [r["id"] for r in _f(store, lambda r: r["subject"] == pid and ".verdict" in r["field"])]
        add("OBSERVATION", txt + ".", ids)
    # agreement
    for key in ("run_repeat_agreement", "repeat_agreement"):
        for e_rec in _f(store, lambda r: r["field"].startswith(key + ".") and r["field"].endswith(".surface_agreement")):
            base = e_rec["field"].rsplit(".", 1)[0]
            reg = _one(store, lambda r: r["field"] == base + ".register_agreement" and r["subject"] == e_rec["subject"])
            pose = _one(store, lambda r: r["field"] == base + ".rna_pose_difference_A" and r["subject"] == e_rec["subject"])
            what = "between the two runs (their engine-designated structures)" if key == "run_repeat_agreement" else "between the two structures"
            add("AGREEMENT_SUMMARY", "Agreement %s, project %s: binding-surface agreement {%s}, contact-register agreement {%s}, RNA pose difference {%s}."
                % (what, e_rec["subject"], e_rec["id"], reg["id"], pose["id"]), [e_rec["id"], reg["id"], pose["id"]])
            if reg["value"] < e_rec["value"]:
                add("AGREEMENT_SUMMARY", "Contact-register agreement ({%s}) is lower than binding-surface agreement ({%s}): the structures share more of the protein "
                    "surface than of the exact residue–nucleotide contact pairs." % (reg["id"], e_rec["id"]), [reg["id"], e_rec["id"]])
            else:
                add("AGREEMENT_SUMMARY", "Contact-register agreement ({%s}) is not lower than binding-surface agreement ({%s})." % (reg["id"], e_rec["id"]), [reg["id"], e_rec["id"]])
    for tot in _f(store, lambda r: r["field"].startswith("contacts.band.") and r["field"].endswith(".total")):
        b = tot["field"].rsplit(".", 1)[0]
        g = {k: _one(store, lambda r, k=k: r["field"] == b + "." + k and r["subject"] == tot["subject"]) for k in ("all", "half", "one")}
        den = _one(store, lambda r: r["field"] == "denominators.%s" % tot["engine"] and r["subject"] == tot["subject"])
        add("AGREEMENT_SUMMARY", "Across the {%s} %s structures of project %s, {%s} distinct residue–nucleotide contacts are proposed: {%s} appear in every structure, "
            "{%s} in at least half and {%s} in exactly one (these are counts of the supplied predictions)." % (den["id"], tot["engine"], tot["subject"], tot["id"], g["all"]["id"], g["half"]["id"], g["one"]["id"]),
            [den["id"], tot["id"], g["all"]["id"], g["half"]["id"], g["one"]["id"]])
        if den["value"] == 1:
            add("LIMITATION", "There is a single structure of this engine: its contacts describe that structure only and are not a consensus.", [den["id"]])
        pp = {k: _one(store, lambda r, k=k: r["field"] == "protein_positions.band.%s.%s" % (tot["engine"], k) and r["subject"] == tot["subject"]) for k in ("total", "all")}
        if pp["total"]:
            add("AGREEMENT_SUMMARY", "Protein surface: {%s} protein positions are in contact in at least one structure and {%s} in every structure." % (pp["total"]["id"], pp["all"]["id"]),
                [pp["total"]["id"], pp["all"]["id"]])
        top = _f(store, lambda r: r["field"].startswith("contacts[") and r["subject"] == tot["subject"] and r.get("engine") == tot["engine"])[:5]
        if top:
            add("AGREEMENT_SUMMARY", "Most frequent residue–nucleotide contacts (structures containing each): " + "; ".join("%s {%s}" % (r["item"], r["id"]) for r in top) + ".",
                [r["id"] for r in top])
    for r in _f(store, lambda r: r["field"] == "no_interface_contact"):
        add("OBSERVATION", "Structure %s contains both polymers but no protein–RNA contact." % r["value"], [r["id"]])
    for r in [x for x in store.records if x["state"] == "NOT_COMPUTED" and x["field"].startswith(("repeat_agreement", "run_repeat_agreement"))]:
        run_done = _one(store, lambda x: x["field"].startswith("run_repeat_agreement.%s." % r.get("engine")) and x["subject"] == r["subject"])
        if r["field"].startswith("repeat_agreement") and run_done:
            add("LIMITATION", "Report's pairwise agreement is defined for two structures, so it is not computed across all structures of this engine as one set; "
                "the between-run agreement above compares the engine-designated structure of each run, and the contact counts describe all structures. "
                "Not computed is not zero agreement.", [r["id"]])
        else:
            add("LIMITATION", "Pairwise repeat agreement was not computed for this configuration: it is defined for exactly two structures of an engine, or for exactly "
                "two runs. Not computed is not zero agreement; the contact counts above still apply.", [r["id"]])
    # region
    for r in _f(store, lambda r: r["tool"] == "region_contacts" and r["field"] != "region_label"):
        k, n = r["value"]
        word = "every supplied structure" if k == n else ("none of the supplied structures" if k == 0 else "some but not all of the supplied structures")
        lab = _one(store, lambda x: x["field"] == "region_label" and x["subject"] == r["subject"] and x.get("region") == r.get("region"))
        add("AGREEMENT_SUMMARY", "Requested region ({%s}), project %s: {%s} %s structures have at least one contact there, that is %s." % (
            lab["id"], r["subject"], r["id"], r["engine"], word), [lab["id"], r["id"]])
        add("LIMITATION", "Recurrence of a contact across predictions shows what the predictions propose; it is not evidence that the region binds in the real complex.", [])
    # 0.4 tools: region comparison, explain, Methods export, distinct proposals
    for lab in _f(store, lambda r: r["tool"] == "region_comparison" and r["field"].endswith(".label")):
        sub = lambda suf: _one(store, lambda r: r["tool"] == "region_comparison" and r["subject"] == lab["subject"] and r.get("region") == lab.get("region") and r["field"].endswith(suf))
        n, sh = sub(".n_contacts_in_range"), sub(".shared_by_all_runs")
        only = _f(store, lambda r: r["tool"] == "region_comparison" and r["subject"] == lab["subject"] and r.get("region") == lab.get("region") and ".only_in_run[" in r["field"])
        txt = "Region comparison ({%s}), project %s: {%s} distinct residue–nucleotide contacts are listed by at least one compared structure" % (lab["id"], lab["subject"], n["id"])
        ids = [lab["id"], n["id"]]
        if sh:
            txt += "; {%s} are shared by all compared runs" % sh["id"]; ids.append(sh["id"])
        for r in only:
            txt += "; found only in run %s: {%s}" % (r["run"], r["id"]); ids.append(r["id"])
        add("AGREEMENT_SUMMARY", txt + " (the contact labels are in the records cited).", ids)
        add("LIMITATION", "Shared and run-specific contacts are listings with counts, not an agreement score; recurrence among predictions is not evidence that a contact exists in the real complex.", [])
    ex = _f(store, lambda r: r["tool"] == "explain_evidence")
    for r in ex[:8]:
        add("DEFINITION", "Recorded explanation: {%s}." % r["id"], [r["id"]])
    for r in _f(store, lambda r: r["tool"] == "export_methods"):
        add("OBSERVATION", "A Methods draft and provenance manifest were written for author review: {%s}." % r["id"], [r["id"]])
    ng = _f(store, lambda r: r["tool"] == "show_distinct_proposals" and r["field"].endswith(".n_groups"))
    for g in ng:
        mem = _f(store, lambda r: r["tool"] == "show_distinct_proposals" and r["subject"] == g["subject"] and r["field"].endswith(".members"))
        add("AGREEMENT_SUMMARY", "Project %s: the structures make {%s} distinct binding proposals (protein surface, then contact register); structures per proposal, in the grouping's display order: %s." % (
            g["subject"], g["id"], "; ".join("{%s}" % r["id"] for r in mem)), [g["id"]] + [r["id"] for r in mem])
        add("LIMITATION", "Proposals are not ranked and none is selected; group size and recurrence are not evidence that a proposal matches the real complex.", [])
    # reference: evaluate
    for d in _f(store, lambda r: r["tool"] == "evaluate_against_reference" and r["field"].endswith(".dockq")):
        sid = d["structure"]
        g = {f: _one(store, lambda r, f=f: r["field"] == "evaluate[%s].%s" % (sid, f) and r["subject"] == d["subject"]) for f in ("dockq_class", "fnat", "irmsd", "lrmsd")}
        add("REFERENCE_COMPARISON", "Structure %s (run %s%s) against the supplied reference: DockQ {%s} ({%s}), fnat {%s}, iRMSD {%s}, LRMSD {%s}." % (
            sid, d.get("run"), ", engine-designated" if d.get("designated") else "", d["id"], g["dockq_class"]["id"], g["fnat"]["id"], g["irmsd"]["id"], g["lrmsd"]["id"]),
            [d["id"]] + [x["id"] for x in g.values()])
    for r in [x for x in store.records if x["tool"] == "evaluate_against_reference" and x["state"] == "METRIC_UNAVAILABLE"]:
        add("REFERENCE_COMPARISON", "One structure has no DockQ value; its named outcome is given in the record cited (not a score of zero).", [r["id"]] + [
            x["id"] for x in _f(store, lambda x: x["tool"] == "evaluate_against_reference")][:1])
    # reference: compare
    comp = _f(store, lambda r: r["tool"] == "compare_prediction_sets" and r["field"].endswith(".class"))
    if comp:
        cs = _one(store, lambda r: r["field"] == "compared_structures")
        add("OBSERVATION", "Compared structures (engine-designated in each set): {%s}." % cs["id"], [cs["id"]])
        for c in comp:
            m = c["field"].split(".")[0]
            vals = {f: _one(store, lambda r, f=f: r["field"] == "%s.%s" % (m, f) and r["subject"] == c["subject"]) for f in ("before", "after", "difference_after_minus_before")}
            name = {"dockq": "DockQ", "fnat": "fnat", "irmsd": "iRMSD", "lrmsd": "LRMSD"}[m]
            parts = ", ".join("%s {%s}" % (f.split("_")[0], vals[f]["id"]) for f in ("before", "after", "difference_after_minus_before") if vals[f])
            add("REFERENCE_COMPARISON", "%s: %s; change class {%s}." % (name, parts or "no value in either set", c["id"]), [c["id"]] + [v["id"] for v in vals.values() if v])
        cls = {c["value"] for c in comp}
        if cls & {"IMPROVED", "WORSENED"}:
            note = _one(store, lambda r: r["field"] == "change_class_note")
            add("LIMITATION", "IMPROVED and WORSENED give the direction of a change at the stated precision; no threshold of practical relevance is applied.", [note["id"]] if note else [])
        if "CORRESPONDENCE_CHANGED" in cls:
            add("LIMITATION", "The residue correspondence or chain mapping differs between the two sets, so the two values do not measure the same thing and are not pooled as a like-for-like change.", [])
        if "CONSTRUCT_CHANGED" in cls:
            add("LIMITATION", "The declared constructs differ between the two sets, so this is not a like-for-like comparison.", [])
    for r in [x for x in store.records if x["tool"] == "compare_prediction_sets" and x["state"] in ("IDENTITY_UNRESOLVED", "INPUT_REFUSED", "CALCULATION_FAILED")]:
        add("CLARIFICATION_REQUEST", "The comparison could not be made; the reason is in the record cited.", [r["id"]])
    # definitions
    for r in _f(store, lambda r: r["tool"] == "explain_metric"):
        add("DEFINITION", "Documented definition: {%s}." % r["id"], [r["id"]])
    # refusals
    caps = list(plan.get("requested_capabilities") or [])
    if "reference_accuracy" in caps and not plan.get("reference_supplied"):
        caps.append("reference_accuracy_without_reference")
    blocked_ids = {n["capability"]: [r["id"] for r in store.records if r["tool"] == "policy" and r["subject"] == n["capability"]] for n in notes}
    for cap in caps:
        if cap in CAP_TEXT and (cap in blocked_ids or cap == "reference_accuracy_without_reference" or (cap == "other" and goal == "UNSUPPORTED")):
            add("REFUSAL_WITH_ALTERNATIVE", CAP_TEXT[cap], blocked_ids.get(cap, []))
    if goal == "UNSUPPORTED" and not any(s["type"] == "REFUSAL_WITH_ALTERNATIVE" for s in S) and not q and not refused:
        add("REFUSAL_WITH_ALTERNATIVE", CAP_TEXT["other"], [])
    if any(s["type"] == "AGREEMENT_SUMMARY" for s in S):
        add("LIMITATION", "Agreement among predictions is not evidence that any structure is right: predictions can share the same error.", [])
    if not S:
        add("LIMITATION", "No analysis could be run for this request with the supplied inputs.", [])
    return {"statements": S}
