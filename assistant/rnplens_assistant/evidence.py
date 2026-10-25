"""Evidence records: every value an answer may state, with its source, statement class and evidence level.

States: COMPUTED, INPUT_MISSING, INPUT_INVALID, INPUT_REFUSED, ACCESS_REFUSED, IDENTITY_UNRESOLVED, METRIC_UNAVAILABLE,
TOOL_UNSUPPORTED, TOOL_BLOCKED, CALCULATION_FAILED, NOT_COMPUTED. Only COMPUTED records can fill a number slot.
Classes: observed, descriptive, reference_based, documentation, not_computed.
Levels: INVENTORY, PROTEIN_SURFACE, RNA_REGION, PLACEMENT, EXACT_CONTACT, REFERENCE, DOC, NONE.
Frequency bands (all structures / at least half / exactly one) are presentation cut-points declared here; they are
counts, not reliability."""
import hashlib
import json

BANDS_NOTE = ("frequency bands are presentation cut-points: present in every structure, in at least half, in exactly "
              "one; they count how often the supplied predictions contain a feature")
TOP_K = 12


def rec(tool, subject, field, label, value, unit, cls, level, source, state="COMPUTED", **extra):
    r = {"tool": tool, "subject": subject, "field": field, "label": label, "value": value, "unit": unit,
         "class": cls, "level": level, "source": source, "state": state}
    r.update(extra)
    return r


def missing(tool, subject, field, state, message):
    return rec(tool, subject, field, message, None, None, "not_computed", "NONE", None, state=state)


class Store:
    def __init__(self):
        self.records = []

    def add(self, recs, step):
        out = []
        for r in recs:
            r = dict(r, id="E%d" % (len(self.records) + 1), step=step)
            self.records.append(r); out.append(r)
        return out

    def get(self, rid):
        return next((r for r in self.records if r["id"] == rid), None)

    def write(self, path):
        with open(path, "w") as fh:
            for r in self.records:
                fh.write(json.dumps(r, sort_keys=True) + "\n")

    def content_hash(self):
        """Hash of the measured content (run-time and path fields excluded): replay must reproduce it."""
        keep = ("tool", "subject", "field", "value", "unit", "class", "level", "state")
        h = hashlib.sha256()
        for r in self.records:
            h.update(json.dumps({k: r.get(k) for k in keep}, sort_keys=True).encode())
        return h.hexdigest()


def fmt(r):
    v, u = r["value"], r["unit"]
    if v is None:
        return "not computed"
    if u == "fraction_kn":
        return "%d of %d" % (v[0], v[1])
    if isinstance(v, float):
        s = "%.3f" % v
    else:
        s = str(v)
    return s + {"A": " Å", None: "", "count": "", "label": "", "text": ""}.get(u, " " + str(u))


# ---------------------------------------------------------------- builders
def from_questions(pid, q, src):
    return [rec("import_predictions", pid, "question", x["question"], x["question"], "text", "not_computed", "NONE", src,
                state="IDENTITY_UNRESOLVED", options=x.get("options")) for x in q["questions"]]


def from_manifest(pid, man, src):
    c = man["counts"]
    R = [rec("import_predictions", pid, "counts.included", "structures included in project %s" % pid, c["included"], "count", "observed", "INVENTORY", src),
         rec("import_predictions", pid, "counts.found", "structure files found for project %s" % pid, c["found"], "count", "observed", "INVENTORY", src),
         rec("import_predictions", pid, "counts.excluded", "structures excluded in project %s" % pid, c["excluded"], "count", "observed", "INVENTORY", src),
         rec("import_predictions", pid, "counts.unrecognised", "files in no recognised layout (project %s)" % pid, c["unrecognised"], "count", "observed", "INVENTORY", src),
         rec("import_predictions", pid, "construct.protein_length", "protein construct length (project %s)" % pid, man["construct"]["protein_length"], "residues", "observed", "INVENTORY", src),
         rec("import_predictions", pid, "construct.rna_length", "RNA construct length (project %s)" % pid, man["construct"]["rna_length"], "nt", "observed", "INVENTORY", src)]
    for r in man["runs"]:
        R.append(rec("import_predictions", pid, "runs[%s].n_structures" % r["run"], "structures in run %s (%s)" % (r["run"], r["engine"]),
                     r["n_structures"], "count", "observed", "INVENTORY", src, run=r["run"], engine=r["engine"]))
        R.append(rec("import_predictions", pid, "runs[%s].designated" % r["run"], "engine-designated structure of run %s" % r["run"],
                     r["designated_execution"] or "not determinable", "label", "observed", "INVENTORY", src, rule=r["designated_rule"]))
    for s in man["structures"]:
        if s["verdict"] != "INCLUDED":
            R.append(rec("import_predictions", pid, "structures[%s].verdict" % s["path"].split("/")[-1],
                         "excluded %s: %s" % (s["path"].split("/")[-1], "; ".join(s["reasons"])[:300]), s["verdict"], "label",
                         "observed", "INVENTORY", src))
        if s.get("derived"):
            R.append(rec("import_predictions", pid, "structures[%s].derived" % s["id"], "derived copy used for %s: %s" % (
                s["id"], "; ".join(s["derived"]["transformations"])[:300]), "derived copy", "label", "observed", "INVENTORY", src))
    for f in man["unrecognised_files"][:20]:
        R.append(rec("import_predictions", pid, "unrecognised", "file in no recognised layout: %s" % f.split("/")[-1], f.split("/")[-1],
                     "label", "observed", "INVENTORY", src))
    return R


def _band_counts(rows, den):
    """rows: summary rows with per_engine counts. Counts per declared band, per engine."""
    out = {}
    for e, n in den.items():
        ks = [r["per_engine"].get(e, {}).get("count", 0) for r in rows]
        ks = [k for k in ks if k > 0]
        out[e] = {"total": len(ks), "all": sum(k == n for k in ks), "half": sum(2 * k >= n for k in ks), "one": sum(k == 1 for k in ks), "n": n}
    return out


def from_summary(pid, S, man, src):
    R = []
    if S.get("report", {}).get("status") != "RAN":
        return [missing("analyse_predictions", pid, "report", "CALCULATION_FAILED", "Report did not produce a result")]
    den = S["contacts"]["denominators"]
    for e, n in den.items():
        R.append(rec("analyse_predictions", pid, "denominators.%s" % e, "eligible %s structures in project %s" % (e, pid), n, "count", "observed", "INVENTORY", src, engine=e))
    for x in S["report"]["no_interface_contact"]:
        R.append(rec("analyse_predictions", pid, "no_interface_contact", "structure %s has both polymers but no protein-RNA contact" % x, x, "label", "observed", "EXACT_CONTACT", src))
    for kind, level, what in (("contacts", "EXACT_CONTACT", "residue-nucleotide contacts"), ("protein_positions", "PROTEIN_SURFACE", "protein positions in contact"),
                              ("rna_positions", "RNA_REGION", "RNA positions in contact")):
        bc = _band_counts(S[kind]["rows"], den)
        for e, b in bc.items():
            for k, lab in (("total", "distinct %s proposed by at least one %s structure"), ("all", "%s present in every one of the %s structures"),
                           ("half", "%s present in at least half of the %s structures"), ("one", "%s present in exactly one %s structure")):
                R.append(rec("analyse_predictions", pid, "%s.band.%s.%s" % (kind, e, k), lab % (what, e) + " (project %s)" % pid, b[k], "count",
                             "descriptive", level, src, engine=e, note=BANDS_NOTE))
        # top rows by count (ties by position), each as one record with its k/n
        for e, n in den.items():
            rows = [r for r in S[kind]["rows"] if r["per_engine"].get(e, {}).get("count", 0) > 0]
            rows.sort(key=lambda r: (-r["per_engine"][e]["count"], r.get("protein_position", r.get("position")), r.get("rna_position", 0)))
            for r in rows[:TOP_K]:
                lab = ("%s%d-%s%d" % (r["protein_residue"], r["protein_position"], r["rna_nucleotide"], r["rna_position"])) if kind == "contacts" \
                    else "%s%d" % (r["residue"], r["position"])
                R.append(rec("analyse_predictions", pid, "%s[%s].%s" % (kind, lab, e), "%s %s: %s structures containing it" % (what[:-1] if kind != "contacts" else "contact", lab, e),
                             [r["per_engine"][e]["count"], n], "fraction_kn", "descriptive", level, src, engine=e, item=lab))
    for scope, key in (("engine", "repeat_agreement"), ("runs", "run_repeat_agreement")):
        for e, v in (S.get(key) or {}).items():
            if v["status"] == "COMPUTED_BY_REPORT":
                what = "between the two %s structures" % e if scope == "engine" else "between runs %s and %s (designated structures %s, %s)" % (
                    v["runs"][0], v["runs"][1], v["structures"][0], v["structures"][1])
                for f, lab, lev, unit in (("surface_agreement", "binding-surface agreement", "PROTEIN_SURFACE", None),
                                          ("register_agreement", "contact-register agreement", "EXACT_CONTACT", None),
                                          ("rna_pose_difference_A", "RNA pose difference (RNA C4' RMSD after protein superposition)", "PLACEMENT", "A")):
                    R.append(rec("analyse_predictions", pid, "%s.%s.%s" % (key, e, f), "%s %s (project %s)" % (lab, what, pid), v[f], unit,
                                 "descriptive", lev, src + ":" + key, engine=e, scope=scope))
            else:
                R.append(rec("analyse_predictions", pid, "%s.%s" % (key, e), "repeat agreement (%s) for %s: not computed. %s" % (
                    scope, e, v.get("reason") or v.get("text") or ""), None, None, "not_computed", "NONE", src, state="NOT_COMPUTED", engine=e))
    ep = S.get("engine_pairs") or {}
    for x in ep.get("pairs", []) or []:
        for f, lab, lev, unit in (("surface_agreement", "binding-surface agreement", "PROTEIN_SURFACE", None), ("register_agreement", "contact-register agreement", "EXACT_CONTACT", None),
                                  ("rna_pose_difference_A", "RNA pose difference", "PLACEMENT", "A")):
            R.append(rec("analyse_predictions", pid, "engine_pairs.%s_%s.%s" % (x["engine_a"], x["engine_b"], f), "%s between engines %s and %s (project %s)" % (
                lab, x["engine_a"], x["engine_b"], pid), x[f], unit, "descriptive", lev, src))
    R.append(rec("analyse_predictions", pid, "diagnose", "Diagnose is not available in this assistant version (requalification against corrected evidence pending)",
                 None, None, "not_computed", "NONE", None, state="TOOL_BLOCKED"))
    return R


def region_counts(pid, man, rr, cbo, rng, src):
    ids = {(s["engine"], s["execution"]): s["id"] for s in man["structures"]}
    elig = [(o["engine"], o["execution"]) for o in rr["per_output"] if o["state"] == "ELIGIBLE"]
    R = []
    desc = " and ".join("%s positions %d-%d" % (k, a, b) for k, (a, b) in rng.items())
    R.append(rec("region_contacts", pid, "region_label", "requested region", desc, "label", "observed", "INVENTORY", src, region=desc))
    for e in sorted({x for x, _ in elig}):
        n = sum(1 for x, _ in elig if x == e)
        hit = []
        for (ee, x) in elig:
            if ee != e:
                continue
            cl = cbo.get("%s|%s" % (ee, x), [])
            ok = any((("rna" not in rng) or rng["rna"][0] <= j <= rng["rna"][1]) and (("protein" not in rng) or rng["protein"][0] <= i <= rng["protein"][1]) for i, j in cl)
            if ok:
                hit.append(ids.get((ee, x), x))
        lev = "EXACT_CONTACT" if len(rng) == 2 else ("RNA_REGION" if "rna" in rng else "PROTEIN_SURFACE")
        R.append(rec("region_contacts", pid, "region[%s].%s" % (desc, e), "%s structures with at least one contact involving %s (project %s)" % (e, desc, pid),
                     [len(hit), n], "fraction_kn", "descriptive", lev, src, engine=e, structures=sorted(hit), region=desc))
    return R


def from_evaluate(pid, S, src, out):
    R = []
    for e in S["evaluate"]:
        sid = e["structure"]
        if e.get("status") == "NO_RESULT":
            R.append(missing("evaluate_against_reference", pid, "evaluate[%s]" % sid, "CALCULATION_FAILED", "Evaluate gave no result for %s" % sid)); continue
        lab = "%s (run %s, sample %s%s)" % (sid, e.get("run"), e.get("sample"), ", engine-designated" if e.get("designated") else "")
        if e["dockq_status"] != "SCORED":
            R.append(rec("evaluate_against_reference", pid, "evaluate[%s].dockq" % sid, "DockQ for %s: %s (a named outcome, not a score of zero)" % (lab, e["dockq_status"]),
                         None, None, "not_computed", "NONE", src, state="METRIC_UNAVAILABLE")); continue
        first = lambda d: next(iter((d or {}).values()), None)
        for f, v, unit in (("dockq", e["dockq"], None), ("fnat", first(e.get("fnat_per_interface")), None),
                           ("irmsd", first(e.get("irmsd_per_interface")), "A"), ("lrmsd", first(e.get("lrmsd_per_interface")), "A")):
            R.append(rec("evaluate_against_reference", pid, "evaluate[%s].%s" % (sid, f), "%s of %s against the supplied reference" % (
                {"dockq": "DockQ", "fnat": "fnat", "irmsd": "iRMSD", "lrmsd": "LRMSD"}[f], lab), v, unit, "reference_based", "REFERENCE", src, structure=sid))
        R.append(rec("evaluate_against_reference", pid, "evaluate[%s].dockq_class" % sid, "DockQ class of %s" % lab, e.get("dockq_class"), "label",
                     "reference_based", "REFERENCE", src, structure=sid))
        for r_ in R[-5:]:
            r_.update(run=e.get("run"), designated=bool(e.get("designated")))
    R.append(rec("evaluate_against_reference", pid, "geometry", "Evaluate's four-axis geometry (protein-internal, RNA-internal, RNA placement RMSD) is withheld: known correspondence defect; corrected implementation not yet qualified",
                 None, None, "not_computed", "NONE", None, state="TOOL_BLOCKED"))
    return R


def from_compare(bp, ap, summ, trows, which, src):
    R = []
    subj = "%s->%s" % (bp, ap)
    R.append(rec("compare_prediction_sets", subj, "compared_structures", "structures compared: before %s; after %s" % (which["before"], which["after"]),
                 "%s | %s" % (which["before"], which["after"]), "label", "observed", "REFERENCE", src))
    for r in trows:
        m = r["metric"]
        name = {"dockq": "DockQ", "fnat": "fnat", "irmsd": "iRMSD", "lrmsd": "LRMSD"}.get(m, m)
        unit = "A" if m in ("irmsd", "lrmsd") else None
        R.append(rec("compare_prediction_sets", subj, "%s.class" % m, "change class for %s (before -> after)" % name, r["class"], "label", "reference_based", "REFERENCE", src))
        for f in ("before", "after", "difference_after_minus_before"):
            v = r[f]
            if v not in ("", None):
                R.append(rec("compare_prediction_sets", subj, "%s.%s" % (m, f), "%s %s" % (name, f.replace("_", " ")), float(v), unit, "reference_based", "REFERENCE", src))
    R.append(rec("compare_prediction_sets", subj, "change_class_note", summ["change_class_note"], summ["change_class_note"], "text", "documentation", "DOC", src))
    for k, v in summ["unmatched"].items():
        if v:
            R.append(missing("compare_prediction_sets", subj, "unmatched.%s" % k, "NOT_COMPUTED", "%s: %s" % (k, ", ".join(v))))
    if summ.get("evaluate_run_failures"):
        R.append(missing("compare_prediction_sets", subj, "run_failures", "CALCULATION_FAILED", "Evaluate refused or failed for the compared structures"))
    R.append(rec("compare_prediction_sets", subj, "withheld", summ["withheld"]["reason"], None, None, "not_computed", "NONE", None, state="TOOL_BLOCKED"))
    return R


def doc_record(name, row):
    return rec("explain_metric", name, "doc", row.replace("|", " ").strip()[:400], row, "text", "documentation", "DOC", "docs/which_analysis_should_i_use.md")
