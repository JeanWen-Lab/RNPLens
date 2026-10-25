"""S4: deterministic admission of a proposed plan. The language model proposes; this module decides.
Every rejected step is kept in the run record (attempted invalid actions are evaluation data)."""
import os

from .tools import REGISTRY, SCHEMAS

MAX_STEPS = 8
ADMITTED_STATUSES = ("QUALIFIED", "DESCRIPTIVE")      # 0.4: DESCRIPTIVE routes are admitted; EXPERIMENTAL and blocked are not
AFTER_ANALYSE = ("region_comparison", "explain_evidence", "export_methods", "show_distinct_proposals")
TOOL_ARGS = {t: list(s["properties"]) for t, s in SCHEMAS.items()}
UNAVAILABLE_CAPS = {"ranking_or_selection": "ranking", "diagnose_disagreement": "diagnose",
                    "geometry_decomposition": "geometry_decomposition", "new_prediction": "new_predictions",
                    "mutation_advice": "mutation_advice", "grouping": "grouping"}


def step_args(step):
    """Map the flat plan step (all fields nullable) to the tool's own arguments."""
    t = step["tool"]
    a = {k: step.get(k) for k in TOOL_ARGS.get(t, [])}
    if t == "explain_metric":
        a["name"] = step.get("metric_name")
    if t == "import_predictions":
        a["accept_offsets"] = bool(a.get("accept_offsets"))
        a["resolve"] = None
    return a


def admit(plan, task):
    """-> (admitted [(i, step, args)], rejected [(i, step, rule, reason)], notes)."""
    admitted, rejected, notes = [], [], []
    refs = set(task.get("reference_files") or [])
    imported, analysed = set(), set()
    steps = plan.get("steps") or []
    if len(steps) > MAX_STEPS:
        rejected += [(i, s, "P4", "plan exceeds %d steps" % MAX_STEPS) for i, s in enumerate(steps[MAX_STEPS:], MAX_STEPS)]
        steps = steps[:MAX_STEPS]
    for cap in plan.get("requested_capabilities") or []:
        if cap in UNAVAILABLE_CAPS:
            u = REGISTRY["unavailable"][UNAVAILABLE_CAPS[cap]]
            notes.append({"capability": cap, "status": u["status"], "reason": u["reason"]})
    for i, s in enumerate(steps):
        t = s.get("tool")
        reg = REGISTRY["tools"].get(t)
        if reg is None or reg["status"] not in ADMITTED_STATUSES:
            rejected.append((i, s, "P1", "tool %r is not a qualified or descriptive tool" % t)); continue
        a = step_args(s)
        bad = None
        for k in ("folders", "protein_fasta", "rna_fasta", "reference"):
            vals = a.get(k) if isinstance(a.get(k), list) else [a.get(k)]
            for v in vals:
                if v and (os.path.isabs(v) or ".." in v.split("/")):
                    bad = ("P7", "path %r must be relative to the task inputs" % v)
        if bad:
            rejected.append((i, s) + bad); continue
        if reg["needs_reference"]:
            if not plan.get("reference_supplied"):
                rejected.append((i, s, "P2", "reference-based tool in a plan that declares no reference")); continue
            if a.get("reference") not in refs:
                rejected.append((i, s, "P2", "%r is not an experimental reference supplied with this task" % a.get("reference"))); continue
        if t == "import_predictions":
            if a.get("project_id") in imported:
                rejected.append((i, s, "P3", "project_id %r imported twice" % a.get("project_id"))); continue
            if any(f in refs for f in (a.get("folders") or [])):
                rejected.append((i, s, "P2", "a reference structure cannot be imported as a prediction")); continue
            imported.add(a.get("project_id"))
        elif t in ("analyse_predictions", "evaluate_against_reference", "region_contacts") + AFTER_ANALYSE:
            if a.get("project_id") not in imported:
                rejected.append((i, s, "P3", "project %r is not imported by an earlier step" % a.get("project_id"))); continue
            if (t == "region_contacts" or t in AFTER_ANALYSE) and a.get("project_id") not in analysed:
                rejected.append((i, s, "P3", "%s needs analyse_predictions on %r first" % (t, a.get("project_id")))); continue
            if t == "analyse_predictions":
                analysed.add(a.get("project_id"))
        elif t == "compare_prediction_sets":
            b, af = a.get("before_project_id"), a.get("after_project_id")
            if b not in imported or af not in imported or b == af:
                rejected.append((i, s, "P6", "compare needs two different projects imported by earlier steps")); continue
        admitted.append((i, s, a))
    return admitted, rejected, notes
