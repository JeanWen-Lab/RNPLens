"""Typed RNPLens tools shared by both evaluation arms. Every tool runs an unchanged RNPLens command (or counts over
its output files) inside a path allowlist and returns (result_dict, evidence_records). Nothing here calls a language
model, and no tool computes a new statistic."""
import csv
import json
import os
import re
import subprocess
import sys

from . import evidence as EV

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = json.load(open(os.path.join(HERE, "registry.json")))
TIMEOUT_S = 1800


class ToolError(Exception):
    """A refused or failed tool call. `state` is one of the evidence missingness states."""
    def __init__(self, state, message):
        super().__init__(message)
        self.state, self.message = state, message


class Workspace:
    """The only paths a tool may read (task inputs) or write (the run directory)."""
    def __init__(self, task_dir, run_dir):
        self.task_dir = os.path.realpath(task_dir)
        self.run_dir = os.path.realpath(run_dir)
        os.makedirs(os.path.join(self.run_dir, "tools"), exist_ok=True)
        self.projects = {}          # project_id -> {"dir", "manifest"}
        self.analyses = {}          # project_id -> results dir (reference-free)
        self.calls = 0

    def readable(self, rel):
        """Resolve a task-relative path; refuse anything outside the task directory."""
        if rel is None:
            return None
        p = os.path.realpath(os.path.join(self.task_dir, rel))
        if not (p == self.task_dir or p.startswith(self.task_dir + os.sep)):
            raise ToolError("ACCESS_REFUSED", "path outside the task inputs: %s" % rel)
        if not os.path.exists(p):
            raise ToolError("INPUT_MISSING", "not found in the task inputs: %s" % rel)
        return p

    def out(self, *parts):
        return os.path.join(self.run_dir, "tools", *parts)

    def rel(self, p):
        return os.path.relpath(p, self.run_dir)


def _rn(ws, args, log_name):
    cmd = [sys.executable, "-m", "rnplens"] + args
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S,
                           env=dict(os.environ, MPLBACKEND="Agg"), cwd=ws.run_dir)
    except subprocess.TimeoutExpired:
        raise ToolError("CALCULATION_FAILED", "rnplens %s exceeded %d s" % (args[0], TIMEOUT_S))
    with open(ws.out(log_name), "w") as fh:
        fh.write("$ rnplens %s\nexit %d\n--- stdout\n%s\n--- stderr\n%s\n" % (" ".join(args), p.returncode, p.stdout, p.stderr))
    return p.returncode, p.stdout, p.stderr


def _pid(ws, project_id):
    if project_id not in ws.projects:
        raise ToolError("INPUT_MISSING", "unknown project_id %r; import the predictions first" % project_id)
    return ws.projects[project_id]


_ID = re.compile(r"^[A-Za-z0-9_]{1,24}$")


def _symlinks(ws, paths):
    """Every symbolic link (file or folder) under the given folders -> [(task-relative path, target inside the task?)]."""
    out = []
    for p in paths:
        for dp, dn, fn in os.walk(p):
            dn[:] = sorted(dn)
            for x in sorted(dn) + sorted(fn):
                q = os.path.join(dp, x)
                if os.path.islink(q):
                    t = os.path.realpath(q)
                    out.append((os.path.relpath(q, ws.task_dir), t == ws.task_dir or t.startswith(ws.task_dir + os.sep)))
    return out


def _task_relative(obj, ws):
    """QA fix #5: absolute task and run-folder paths inside import questions become task-relative ('run_B/x.pdb'), so
    the evidence (and its content hash, which a replay must reproduce) does not depend on where the task is."""
    roots = sorted({ws.task_dir, ws.run_dir}, key=len, reverse=True)
    if isinstance(obj, dict):
        return {k: _task_relative(v, ws) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_task_relative(v, ws) for v in obj]
    if isinstance(obj, str):
        for r in roots:
            obj = obj.replace(r + os.sep, "").replace(r, ".")
        return obj
    return obj


# ---------------------------------------------------------------- tools
def import_predictions(ws, project_id, folders, protein_fasta, rna_fasta, engine=None, accept_offsets=False,
                       resolve=None):
    if not _ID.match(project_id or ""):
        raise ToolError("INPUT_INVALID", "project_id must be 1-24 letters, digits or _")
    if project_id in ws.projects:
        raise ToolError("INPUT_INVALID", "project_id %r already used" % project_id)
    if not folders:
        raise ToolError("INPUT_MISSING", "no prediction folder given")
    paths = [ws.readable(f) for f in folders]
    pf, rf = ws.readable(protein_fasta), ws.readable(rna_fasta)
    links = _symlinks(ws, paths)
    outside = [rel for rel, inside in links if not inside]
    if outside:          # QA fix: a link out of the task inputs is never followed (refused, nothing imported)
        raise ToolError("ACCESS_REFUSED", "symbolic link(s) inside the folders point outside the task inputs and are not "
                        "followed: %s" % ", ".join(outside[:10]))
    out = ws.out("project_" + project_id)
    args = ["import"] + paths + ["--protein-seq", pf, "--rna-seq", rf, "--out", out, "--case-id", project_id]
    if engine:
        args += ["--engine", engine]
    if accept_offsets:
        args += ["--accept-derived"]
    if resolve:
        rp = ws.out("resolve_%s.json" % project_id)
        json.dump({"answers": resolve}, open(rp, "w"))
        args += ["--resolve", rp]
    code, so, se = _rn(ws, args, "import_%s.log" % project_id)
    if code == 3:
        q = _task_relative(json.load(open(os.path.join(out, "QUESTIONS.json"))), ws)
        recs = EV.from_questions(project_id, q, ws.rel(os.path.join(out, "QUESTIONS.json")))
        return {"status": "NEEDS_CONFIRMATION", "questions": [x["question"] for x in q["questions"]]}, recs
    if code != 0:
        msg = (se or so).strip().splitlines()
        recs = [EV.missing("import_predictions", project_id, "import", "INPUT_REFUSED", " | ".join(msg[:6])[:900])]
        return {"status": "REFUSED", "message": " | ".join(msg[:6])[:900]}, recs
    man = json.load(open(os.path.join(out, "manifest.json")))
    ws.projects[project_id] = {"dir": out, "manifest": man}
    recs = EV.from_manifest(project_id, man, ws.rel(os.path.join(out, "manifest.json")))
    res = {"status": "IMPORTED", "counts": man["counts"],
           "runs": [{k: r[k] for k in ("run", "engine", "n_structures", "designated_execution", "designated_rule")} for r in man["runs"]]}
    if links:            # reported, never silent: links that stay inside the task inputs
        res["symbolic_links_inside_task"] = [rel for rel, _ in links]
        recs.append(EV.rec("import_predictions", project_id, "symbolic_links", "symbolic links inside the task inputs, read through "
                           "the link: %s" % ", ".join(rel for rel, _ in links[:10]), len(links), "count", "observed", "INVENTORY",
                           ws.rel(os.path.join(out, "manifest.json"))))
    return res, recs


def analyse_predictions(ws, project_id):
    pr = _pid(ws, project_id)
    out = ws.out("analysis_" + project_id)
    if os.path.exists(out):
        return {"status": "ALREADY_ANALYSED"}, []
    code, so, se = _rn(ws, ["analyse", pr["dir"], "--out", out, "--without-diagnose", "--nproc", "2"], "analyse_%s.log" % project_id)
    if code != 0:
        raise ToolError("CALCULATION_FAILED", ("rnplens analyse: " + (se or so).strip())[-900:])
    ws.analyses[project_id] = out
    S = json.load(open(os.path.join(out, "summary.json")))
    recs = EV.from_summary(project_id, S, pr["manifest"], ws.rel(os.path.join(out, "summary.json")))
    return {"status": "ANALYSED", "n_records": len(recs)}, recs


def region_contacts(ws, project_id, rna_start=None, rna_end=None, protein_start=None, protein_end=None):
    pr = _pid(ws, project_id)
    if project_id not in ws.analyses:
        raise ToolError("INPUT_MISSING", "analyse_predictions must run on %r first" % project_id)
    man = pr["manifest"]
    L = {"rna": man["construct"]["rna_length"], "protein": man["construct"]["protein_length"]}
    rng = {}
    for kind, a, b in (("rna", rna_start, rna_end), ("protein", protein_start, protein_end)):
        if a is None and b is None:
            continue
        if a is None or b is None or not (1 <= int(a) <= int(b) <= L[kind]):
            raise ToolError("INPUT_INVALID", "%s range %s-%s is not within construct positions 1-%d" % (kind, a, b, L[kind]))
        rng[kind] = (int(a), int(b))
    if not rng:
        raise ToolError("INPUT_INVALID", "give an RNA and/or protein position range")
    cbo_p = os.path.join(ws.analyses[project_id], "report", "contacts_by_output.json")
    rr = json.load(open(os.path.join(ws.analyses[project_id], "report", "result.json")))
    recs = EV.region_counts(project_id, man, rr, json.load(open(cbo_p)), rng, ws.rel(cbo_p))
    return {"status": "COUNTED", "ranges": rng}, recs


def evaluate_against_reference(ws, project_id, reference):
    pr = _pid(ws, project_id)
    ref = ws.readable(reference)
    out = ws.out("evaluation_" + project_id)
    if os.path.exists(out):
        return {"status": "ALREADY_EVALUATED"}, []
    code, so, se = _rn(ws, ["analyse", pr["dir"], "--out", out, "--reference", ref, "--without-diagnose"], "evaluate_%s.log" % project_id)
    if code != 0:
        raise ToolError("CALCULATION_FAILED", ("rnplens analyse --reference: " + (se or so).strip())[-900:])
    S = json.load(open(os.path.join(out, "summary.json")))
    return {"status": "EVALUATED"}, EV.from_evaluate(project_id, S, ws.rel(os.path.join(out, "summary.json")), out)


def compare_prediction_sets(ws, before_project_id, after_project_id, reference):
    """Matched before/after Evaluate of the engine-designated structure of each set (one target)."""
    b, a = _pid(ws, before_project_id), _pid(ws, after_project_id)
    ref = ws.readable(reference)
    rows = {}
    for tag, pr in (("before", b), ("after", a)):
        man = pr["manifest"]
        des = [s for s in man["structures"] if s.get("designated") and s["verdict"] == "INCLUDED"]
        if len(des) != 1:
            raise ToolError("IDENTITY_UNRESOLVED", "%s set: exactly one engine-designated included structure is needed "
                            "(found %d; runs: %s)" % (tag, len(des), "; ".join("%s: %s" % (r["run"], r["designated_rule"]) for r in man["runs"])))
        rows[tag] = (des[0], man["construct"])
    d = ws.out("compare_%s_vs_%s" % (before_project_id, after_project_id))
    os.makedirs(d + "_inputs", exist_ok=True)
    for tag in ("before", "after"):
        s, con = rows[tag]
        with open(os.path.join(d + "_inputs", tag + ".tsv"), "w", newline="") as fh:
            w = csv.writer(fh, delimiter="\t", lineterminator="\n")
            w.writerow(["target_id", "prediction", "protein_sequence", "rna_sequence"])
            w.writerow(["target", s["used_path"], con["protein_sequence"], con["rna_sequence"]])
    with open(os.path.join(d + "_inputs", "references.tsv"), "w") as fh:
        fh.write("target_id\treference\ntarget\t%s\n" % ref)
    code, so, se = _rn(ws, ["compare", "--before", os.path.join(d + "_inputs", "before.tsv"), "--after",
                            os.path.join(d + "_inputs", "after.tsv"), "--references", os.path.join(d + "_inputs", "references.tsv"),
                            "--out", d], "compare_%s_%s.log" % (before_project_id, after_project_id))
    if code == 2:
        raise ToolError("INPUT_REFUSED", ("rnplens compare: " + (se or so).strip())[-900:])
    summ = json.load(open(os.path.join(d, "comparison_summary.json")))
    trows = list(csv.DictReader(open(os.path.join(d, "comparison.tsv")), delimiter="\t"))
    recs = EV.from_compare(before_project_id, after_project_id, summ, trows,
                           {t: rows[t][0]["id"] + " (" + rows[t][0]["execution"] + ")" for t in rows},
                           ws.rel(os.path.join(d, "comparison_summary.json")))
    return {"status": "COMPARED" if code == 0 else "RUN_FAILED"}, recs


METRIC_DOC = None


def explain_metric(ws, name):
    global METRIC_DOC
    if METRIC_DOC is None:
        from .guide import guide_text  # packaged copy (Amendment 4); raises if missing
        METRIC_DOC = guide_text()
    rows = [l for l in METRIC_DOC.splitlines() if l.startswith("| ") and name.lower() in l.lower().split("|")[1]]
    if not rows:
        raise ToolError("METRIC_UNAVAILABLE", "no documented RNPLens metric named %r" % name)
    return {"status": "EXPLAINED", "rows": rows[:3]}, [EV.doc_record(name, r) for r in rows[:3]]


# ---------------------------------------------------------------- 0.4 functions registered as assistant tools
# Statuses mirror rnplens.capabilities (registry.json "capability"): DESCRIPTIVE routes, called through their capability
# entry points on the analysis written by analyse_predictions. Nothing here ranks, selects or recomputes.
def _analysis_of(ws, project_id):
    pr = _pid(ws, project_id)
    if project_id not in ws.analyses:
        raise ToolError("INPUT_MISSING", "analyse_predictions must run on %r first" % project_id)
    return pr, ws.analyses[project_id]


def _refused(res, what):
    st = str((res or {}).get("status", "")).upper()
    if st in ("REFUSED", "FAILED", "ERROR", "UNAVAILABLE", "NEEDS_CLARIFICATION", "STOPPED", ""):
        raise ToolError("INPUT_INVALID" if st == "REFUSED" else "CALCULATION_FAILED", ("%s: %s" % (what, (res or {}).get("message")))[:900])


def region_comparison(ws, project_id, rna_start, rna_end, protein_start=None, protein_end=None, runs=None):
    pr, A = _analysis_of(ws, project_id)
    from rnplens import region
    for a, b, kind in ((rna_start, rna_end, "rna"), (protein_start, protein_end, "protein")):
        if (a is None) != (b is None) or (a is not None and not (isinstance(a, int) and isinstance(b, int))):
            raise ToolError("INPUT_INVALID", "%s range needs integer start and end" % kind)
    if rna_start is None:
        raise ToolError("INPUT_INVALID", "give an RNA position range")
    res = region.capability_run(pr["dir"], A, "%d-%d" % (rna_start, rna_end),
                                ("%d-%d" % (protein_start, protein_end)) if protein_start is not None else None, runs or None)
    _refused(res, "rnplens region")
    rj = next(o for o in res["outputs"] if o.endswith("region.json"))
    doc = json.load(open(rj)); sm = doc["summary"]; src = ws.rel(rj)
    desc = doc["region"]["rna"]["label"] + ((" / protein %d-%d" % (doc["region"]["protein"]["start"], doc["region"]["protein"]["end"])) if doc["region"].get("protein") else "")
    R = [EV.rec("region_comparison", project_id, "region[%s].label" % desc, "requested region", desc, "label", "observed", "INVENTORY", src, region=desc),
         EV.rec("region_comparison", project_id, "region[%s].n_contacts_in_range" % desc, "distinct residue-nucleotide contacts listed in %s by at least one compared structure" % desc,
                sm["n_contacts_in_range"]["count"], "count", "descriptive", "EXACT_CONTACT", src + "#/summary/n_contacts_in_range", region=desc)]
    if len(sm.get("runs_compared") or []) >= 2:
        R.append(EV.rec("region_comparison", project_id, "region[%s].shared_by_all_runs" % desc, "contacts in %s shared by all compared runs (%s)" % (desc, ", ".join(sm["runs_compared"])),
                        sm["shared_by_all_runs"]["count"], "count", "descriptive", "EXACT_CONTACT", src + "#/summary/shared_by_all_runs", region=desc))
        for run, x in sorted((sm.get("only_in_run") or {}).items()):
            R.append(EV.rec("region_comparison", project_id, "region[%s].only_in_run[%s]" % (desc, run), "contacts in %s found only in run %s" % (desc, run),
                            x["count"], "count", "descriptive", "EXACT_CONTACT", src + "#/summary/only_in_run/" + run, region=desc, run=run,
                            items=list(x.get("contacts") or [])))
    return {"status": "COMPARED", "region": desc}, R


def explain_evidence(ws, project_id, query, evidence_id=None, contact=None):
    pr, A = _analysis_of(ws, project_id)
    if query not in ("evidence", "contact", "structures", "excluded", "count", "unavailable", "definitions", "limitations"):
        raise ToolError("INPUT_INVALID", "query %r is not offered" % query)
    from rnplens import evidence_query as EQ
    kw = {k: v for k, v in (("evidence_id", evidence_id), ("contact", contact)) if v}
    res = EQ.capability_run(analysis=A, project=pr["dir"], query=query, **kw)
    _refused(res, "rnplens explain")
    src = ws.rel(next(o for o in res["outputs"] if o.endswith(".json")))
    R = [EV.rec("explain_evidence", project_id, "explain[%s].statements[%d]" % (query, i), st["text"][:400], st["text"][:400], "text",
                "documentation", "DOC", "%s#/statements/%d" % (src, i)) for i, st in enumerate((res.get("statements") or [])[:20])]
    return {"status": "EXPLAINED", "n_statements": len(res.get("statements") or [])}, R


def export_methods(ws, project_id):
    pr, A = _analysis_of(ws, project_id)
    from rnplens import methods_export as ME
    res = ME.capability_run(A, pr["dir"])
    _refused(res, "rnplens export-methods")
    md = next(o for o in res["outputs"] if o.endswith("methods.md"))
    return {"status": "EXPORTED"}, [EV.rec("export_methods", project_id, "methods_md", "Methods draft and provenance manifest written (for author review)",
                                           ws.rel(md), "label", "observed", "INVENTORY", ws.rel(md))]


def show_distinct_proposals(ws, project_id):
    """Grouping offered only as 'show distinct proposals': members per group in the grouping's own display order
    (never by size); no representative, ranking or selection is reported."""
    pr, A = _analysis_of(ws, project_id)
    from rnplens import grouping
    res = grouping.run_capability(pr["dir"], A)
    _refused(res, "rnplens group")
    gj = os.path.join(A, "groups", "groups.json")
    G = json.load(open(gj)); t = G["primary_threshold"]; src = ws.rel(gj)
    R = [EV.rec("show_distinct_proposals", project_id, "groups[%s].n_groups" % t, "distinct binding proposals at the primary cut (groups are not ranked)",
                G["thresholds"][t]["n_groups"], "count", "descriptive", "EXACT_CONTACT", "%s#/thresholds/%s/n_groups" % (src, t))]
    for i, g in enumerate(G["thresholds"][t]["groups"]):
        R.append(EV.rec("show_distinct_proposals", project_id, "groups[%s][%d].members" % (t, i), "structures in proposal %s" % g.get("label", g.get("group")),
                        ", ".join(g["members"]), "label", "descriptive", "EXACT_CONTACT", "%s#/thresholds/%s/groups/%d/members" % (src, t, i)))
    return {"status": "GROUPED", "display_order": G.get("display_order")}, R


FUNCS = {"import_predictions": import_predictions, "analyse_predictions": analyse_predictions,
         "region_contacts": region_contacts, "evaluate_against_reference": evaluate_against_reference,
         "compare_prediction_sets": compare_prediction_sets, "explain_metric": explain_metric,
         "region_comparison": region_comparison, "explain_evidence": explain_evidence, "export_methods": export_methods,
         "show_distinct_proposals": show_distinct_proposals}

# JSON schemas shared by both arms (the general agent receives them as function tools)
SCHEMAS = {
    "import_predictions": {"description": "Import predicted protein-RNA structures from folders (relative to the task inputs) into one project and check every chain against the declared construct sequences. Stops with questions when anything is ambiguous. All folders imported into one project are analysed together: agreement between runs or structures is computed within a project, so import runs of the same construct that should be compared with each other into the same project. Use separate projects only for a before/after comparison against a reference.",
        "properties": {"project_id": {"type": "string", "description": "a short name you choose, e.g. run_a"},
                       "folders": {"type": "array", "items": {"type": "string"}},
                       "protein_fasta": {"type": "string"}, "rna_fasta": {"type": "string"},
                       "engine": {"type": ["string", "null"], "enum": ["BOLTZ2", "CHAI1", "AF3", "RF3", "RF2NA", "OTHER", None]},
                       "accept_offsets": {"type": "boolean", "description": "accept renumbered derived copies when chain numbering is offset"},
                       "resolve": {"type": ["object", "null"], "description": "answers to questions from a previous import", "additionalProperties": {"type": "string"}}},
        "required": ["project_id", "folders", "protein_fasta", "rna_fasta", "engine", "accept_offsets", "resolve"]},
    "analyse_predictions": {"description": "Reference-free analysis of an imported project: contacts and positions proposed by the structures, binding-surface and contact-register agreement, RNA pose difference.",
        "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]},
    "region_contacts": {"description": "Count the structures with at least one contact in a declared RNA and/or protein position range (construct numbering). Requires analyse_predictions.",
        "properties": {"project_id": {"type": "string"}, "rna_start": {"type": ["integer", "null"]}, "rna_end": {"type": ["integer", "null"]},
                       "protein_start": {"type": ["integer", "null"]}, "protein_end": {"type": ["integer", "null"]}},
        "required": ["project_id", "rna_start", "rna_end", "protein_start", "protein_end"]},
    "evaluate_against_reference": {"description": "Evaluate each structure of a project against an experimental reference structure (mmCIF in the task inputs): DockQ, fnat, iRMSD, LRMSD.",
        "properties": {"project_id": {"type": "string"}, "reference": {"type": "string"}}, "required": ["project_id", "reference"]},
    "compare_prediction_sets": {"description": "Matched before/after comparison against one experimental reference, using the engine-designated structure of each project: DockQ, fnat, iRMSD, LRMSD, with correspondence and evaluability changes reported separately.",
        "properties": {"before_project_id": {"type": "string"}, "after_project_id": {"type": "string"}, "reference": {"type": "string"}},
        "required": ["before_project_id", "after_project_id", "reference"]},
    "explain_metric": {"description": "The documented definition of an RNPLens value (e.g. DockQ, fnat, register agreement).",
        "properties": {"name": {"type": "string"}}, "required": ["name"]},
    "region_comparison": {"description": "0.4 region comparison (DESCRIPTIVE): residue-nucleotide contacts in a declared RNA (and optional protein) range listed from Report's own contact records; with runs, the contacts shared by the runs and those found in only one run. Requires analyse_predictions.",
        "properties": {"project_id": {"type": "string"}, "rna_start": {"type": "integer"}, "rna_end": {"type": "integer"},
                       "protein_start": {"type": ["integer", "null"]}, "protein_end": {"type": ["integer", "null"]},
                       "runs": {"type": ["array", "null"], "items": {"type": "string"}}},
        "required": ["project_id", "rna_start", "rna_end", "protein_start", "protein_end", "runs"]},
    "explain_evidence": {"description": "0.4 explain (DESCRIPTIVE): read from the execution records how a value was obtained (query evidence with evidence_id, contact with a contact label like K14-G20, structures, excluded, count, unavailable, definitions, limitations). Requires analyse_predictions.",
        "properties": {"project_id": {"type": "string"}, "query": {"type": "string", "enum": ["evidence", "contact", "structures", "excluded", "count", "unavailable", "definitions", "limitations"]},
                       "evidence_id": {"type": ["string", "null"]}, "contact": {"type": ["string", "null"]}},
        "required": ["project_id", "query", "evidence_id", "contact"]},
    "export_methods": {"description": "0.4 Methods export (DESCRIPTIVE): a Methods draft and provenance manifest generated only from the execution records. Requires analyse_predictions.",
        "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]},
    "show_distinct_proposals": {"description": "0.4 grouping, offered only as 'show distinct proposals' (DESCRIPTIVE): which structures make the same binding proposal (protein surface, then contact register). Groups are not ranked and none is selected. Requires analyse_predictions.",
        "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]},
}


def call(ws, name, args):
    """Execute one tool call. Returns (status, result, records). Never raises for tool-level refusals."""
    ws.calls += 1
    if name not in FUNCS:
        return "UNKNOWN_TOOL", {"error": "no tool named %r" % name}, []
    try:
        res, recs = FUNCS[name](ws, **{k: v for k, v in (args or {}).items()})
        return "OK", res, recs
    except ToolError as ex:
        rec = EV.missing(name, json.dumps(args, sort_keys=True)[:200], name, ex.state, ex.message)
        return ex.state, {"error": ex.message, "state": ex.state}, [rec]
    except TypeError as ex:
        return "INPUT_INVALID", {"error": "bad arguments: %s" % ex}, []
