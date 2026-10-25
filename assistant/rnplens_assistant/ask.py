"""S1-S8 orchestration for the RNPLens Assistant arm (R)."""
import copy
import datetime
import hashlib
import json
import os
import re
import time

from . import __version__, evidence as EV, gates, policy, redact as RD, render, templates, tools as T

HERE = os.path.dirname(os.path.abspath(__file__))
GOALS = ["AGREEMENT", "REGION_CLAIM", "COMPARE", "WHICH_ANALYSIS", "EXPLAIN_METRIC", "UNSUPPORTED"]
CAPS = ["contacts_agreement", "region_contacts", "reference_accuracy", "before_after_comparison", "metric_definition",
        "ranking_or_selection", "diagnose_disagreement", "geometry_decomposition", "new_prediction", "mutation_advice", "grouping", "other"]
ENGINE_TOKENS = ["Boltz-2", "BOLTZ2", "Chai-1", "CHAI1", "AF3", "RF3", "RF2NA", "RoseTTAFold2NA", "AlphaFold 3", "C4'", "C4′"]
NULLS = lambda t: {"type": [t, "null"]}
PLAN_SCHEMA = {"type": "object", "additionalProperties": False,
    "properties": {"goal": {"type": "string", "enum": GOALS}, "reference_supplied": {"type": "boolean"},
                   "requested_capabilities": {"type": "array", "items": {"type": "string", "enum": CAPS}},
                   "clarification_needed": NULLS("string"),
                   "steps": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {
                       "tool": {"type": "string", "enum": list(T.FUNCS)}, "project_id": NULLS("string"),
                       "folders": {"type": ["array", "null"], "items": {"type": "string"}}, "protein_fasta": NULLS("string"),
                       "rna_fasta": NULLS("string"), "engine": {"type": ["string", "null"], "enum": ["BOLTZ2", "CHAI1", "AF3", "RF3", "RF2NA", "OTHER", None]},
                       "accept_offsets": NULLS("boolean"), "before_project_id": NULLS("string"), "after_project_id": NULLS("string"),
                       "reference": NULLS("string"), "rna_start": NULLS("integer"), "rna_end": NULLS("integer"),
                       "protein_start": NULLS("integer"), "protein_end": NULLS("integer"), "metric_name": NULLS("string"),
                       "runs": {"type": ["array", "null"], "items": {"type": "string"}},
                       "query": {"type": ["string", "null"], "enum": ["evidence", "contact", "structures", "excluded", "count", "unavailable", "definitions", "limitations", None]},
                       "evidence_id": NULLS("string"), "contact": NULLS("string"),
                       "purpose": {"type": "string"}},
                       "required": ["tool", "project_id", "folders", "protein_fasta", "rna_fasta", "engine", "accept_offsets",
                                    "before_project_id", "after_project_id", "reference", "rna_start", "rna_end", "protein_start",
                                    "protein_end", "metric_name", "runs", "query", "evidence_id", "contact", "purpose"]}}},
    "required": ["goal", "reference_supplied", "requested_capabilities", "clarification_needed", "steps"]}
DRAFT_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {"statements": {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "properties": {
        "type": {"type": "string", "enum": list(gates.TYPES)}, "text": {"type": "string"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["type", "text", "evidence_ids"]}}},
    "required": ["statements"]}


def _read(name):
    return open(os.path.join(HERE, "prompts", name)).read()


AVAILABILITY_NOTE = ("# Availability in this evaluated version\n\n"
    "Available through the tools: import of prediction folders; reference-free Report analyses (contacts, protein and RNA "
    "positions, binding-surface and contact-register agreement, RNA pose difference); counts for a declared position range; "
    "Evaluate against a supplied reference limited to DockQ, DockQ class, fnat, iRMSD and LRMSD; matched before/after "
    "comparison of engine-designated structures with those metrics; metric definitions.\n"
    "Not available: Diagnose; Evaluate's four-axis geometry (protein-internal, RNA-internal and RNA placement RMSD), which "
    "has a known correspondence defect; candidate ranking or selection; grouping into binding hypotheses; structure "
    "prediction; mutation or experiment advice. The documentation below describes the full toolkit.\n\n")


def doc_text():
    """Shared context given identically to both arms: availability note + toolkit documentation."""
    return AVAILABILITY_NOTE + _doc()


def _doc():
    from .guide import guide_text      # packaged copy (Amendment 4); raises if missing
    return guide_text()


def listing(task_dir, limit=300):
    out = []
    for dp, dn, fn in os.walk(task_dir):
        dn[:] = sorted(d for d in dn if not d.startswith("."))
        for f in sorted(fn):
            if f == "task.json" or f.startswith("."):
                continue
            out.append(os.path.relpath(os.path.join(dp, f), task_dir))
    return out[:limit], len(out)


def load_task(task_dir):
    p = os.path.join(task_dir, "task.json")
    t = json.load(open(p)) if os.path.exists(p) else {}
    t.setdefault("reference_files", [])
    return t


def _evidence_view(store):
    return [{"id": r["id"], "what": r["label"], "value": EV.fmt(r), "class": r["class"], "level": r["level"], "state": r["state"]}
            for r in store.records]


def allowed_tokens(store, ws):
    toks = set(ENGINE_TOKENS)
    for pid, pr in ws.projects.items():
        toks.add(pid)
        for r in pr["manifest"]["runs"]:
            toks.add(r["run"]); toks.update(str(r["designated_execution"] or "").split("#"))
        for s in pr["manifest"]["structures"]:
            toks.update([s["id"], os.path.basename(s["path"]), str(s.get("execution", ""))])
    for r in store.records:
        if r.get("item"):
            toks.update([r["item"]] + r["item"].split("-"))
        for k in ("run", "structure"):
            if r.get(k):
                toks.add(str(r[k]))
    toks.discard("")
    return sorted(toks, key=len, reverse=True)


def execute(ws, store, admitted, log):
    """Run admitted steps in order; dependent steps of a failed import are skipped and recorded."""
    failed = set()
    for i, s, a in admitted:
        deps = {a.get(k) for k in ("project_id", "before_project_id", "after_project_id") if a.get(k)}
        if s["tool"] != "import_predictions" and deps & failed:
            log.append({"step": i, "tool": s["tool"], "args": a, "status": "SKIPPED_DEPENDENCY"})
            store.add([EV.missing(s["tool"], ",".join(sorted(deps)), s["tool"], "NOT_COMPUTED",
                                  "%s not run: project %s was not imported" % (s["tool"], ", ".join(sorted(deps & failed))))], i)
            continue
        t0 = time.time()
        status, res, recs = T.call(ws, s["tool"], a)
        recs = _scrub_model_text(recs, a)
        if s["tool"] == "import_predictions" and (status != "OK" or res.get("status") != "IMPORTED"):
            failed.add(a.get("project_id"))
        store.add(recs, i)
        log.append({"step": i, "tool": s["tool"], "args": a, "status": status if status != "OK" else res.get("status", "OK"),
                    "result": res, "n_records": len(recs), "wall_s": round(time.time() - t0, 2)})


def admit_redacted(plan, ptask, rmap):
    """Policy admission in identifier space (the model only ever saw identifiers), then the local translation of every
    admitted step's path arguments to the real task paths. An argument that is not an identifier from the listing is
    rejected (rule P9); its value is the model's own, so the rejection text carries no real name."""
    admitted0, rejected, notes = policy.admit(plan, ptask)
    admitted = []
    for i, s, a in admitted0:
        ra, bad = RD.planner_args_to_real(a, rmap)
        if bad:
            rejected.append((i, s, "P9", "%s is not an identifier from the task inputs listing" % ", ".join(repr(x) for x in bad)))
        else:
            admitted.append((i, s, ra))
    return admitted, sorted(rejected, key=lambda r: r[0]), notes


REFERENCE_CAPS = ("reference_accuracy", "before_after_comparison")


def declared_reference(plan, ptask):
    """QA fix #4: whether a reference is supplied is decided by the task (task.json reference_files), never by the
    model's claim. Returns the plan used for admission, templates and gates; the model's own plan stays in the record.
    Without a declared reference, a COMPARE goal or a reference-based capability always gets the 'needs a reference'
    refusal (reference_accuracy)."""
    eff = dict(plan)
    has = bool(ptask.get("reference_files"))
    eff["reference_supplied"] = has
    caps = list(plan.get("requested_capabilities") or [])
    if not has and (plan.get("goal") == "COMPARE" or any(c in caps for c in REFERENCE_CAPS)) and "reference_accuracy" not in caps:
        caps.append("reference_accuracy")
    eff["requested_capabilities"] = caps
    return eff


PID_KEYS = ("project_id", "before_project_id", "after_project_id")
MODEL_TEXT_ARGS = ("name", "contact", "evidence_id", "runs", "metric_name")


def local_project_ids(admitted):
    """QA fix #3: the model's project ids never reach the answer. After admission (the policy checks the model's own
    ids), every project id is replaced by a deterministic local id, project_1, project_2, ... in order of first use.
    -> (admitted with local ids, {model id: local id})."""
    m, out = {}, []
    for i, s, a in admitted:
        a = dict(a)
        for k in PID_KEYS:
            v = a.get(k)
            if v is not None:
                m.setdefault(v, "project_%d" % (len(m) + 1))
                a[k] = m[v]
        out.append((i, s, a))
    return out, m


def _scrub_model_text(recs, args):
    """QA fix #3: a refused step's message may echo a model-supplied string (an unknown metric name, contact label,
    evidence ID or run); it is replaced by a fixed placeholder in the record label, so no model text is rendered."""
    vals = []
    for k in MODEL_TEXT_ARGS:
        v = (args or {}).get(k)
        vals += [x for x in (v if isinstance(v, list) else [v]) if isinstance(x, str) and x]
    if not vals:
        return recs
    out = []
    for r in recs:
        if r.get("state") != "COMPUTED" and isinstance(r.get("label"), str):
            lab = r["label"]
            for v in sorted(set(vals), key=len, reverse=True):
                lab = lab.replace(v, "<model-supplied value>")
            r = dict(r, label=lab)
        out.append(r)
    return out


def run(task_dir, question, run_dir, llm, max_replans=1, max_redrafts=1, answer_mode="template"):
    """answer_mode 'template' (default, Codex protocol v2): deterministic evidence-linked statements, no second model
    call. 'draft' (protocol v1 only): a model-drafted answer checked by the gates."""
    t_start = time.time()
    os.makedirs(run_dir, exist_ok=True)
    task = load_task(task_dir)
    ws = T.Workspace(task_dir, run_dir)
    store = EV.Store()
    files, nfiles = listing(task_dir)
    rec = {"arm": "R", "assistant_version": __version__, "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "question": question, "task_id": task.get("task_id"), "registry_sha256": hashlib.sha256(open(os.path.join(HERE, "registry.json"), "rb").read()).hexdigest(),
           "prompt_sha256": {n: hashlib.sha256(_read(n).encode()).hexdigest() for n in ("planner.md", "drafter.md")},
           "llm_config": llm.config, "plans": [], "rejected_steps": [], "tool_log": [], "drafts": [], "gate_results": []}
    sysp = _read("planner.md") + "\n\n# RNPLens documentation (which analysis to use)\n\n" + doc_text()
    # 0.4 privacy: identifiers only (redact.py); the identifier map stays in the run folder and is never sent
    user, rmap = RD.planner_user(question, task_dir, task)
    rmap.write(os.path.join(run_dir, "redaction_map.json"), {"rule": "redact.py module docstring", "task_files_listed": nfiles})
    ptask = {"reference_files": sorted(i for i in rmap.to_real if i.startswith("reference_"))}
    rec["redaction"] = {"map": "redaction_map.json", "n_identifiers": len(rmap.to_real), "user_message_sha256": hashlib.sha256(user.encode("utf-8")).hexdigest(),
                        "question_redactions": rmap.question_redactions}
    viol = RD.payload_violations(rmap.question_sent, task_dir, rmap)    # QA fix #6: pre-send gate; nothing is sent on a finding
    if viol:
        return _privacy_refusal(rec, viol, question, run_dir, llm, t_start)
    plan = llm.structured("plan", sysp, user, "rnplens_plan", PLAN_SCHEMA)
    rec["plans"].append(plan)
    rec["reference_claims"] = [{"plan": 0, "model_reference_supplied": plan.get("reference_supplied"), "declared": bool(ptask["reference_files"])}]
    plan = declared_reference(plan, ptask)
    admitted, rejected, notes = admit_redacted(plan, ptask, rmap)
    for k in range(max_replans):
        if not rejected:
            break
        rec["rejected_steps"] += [{"plan": len(rec["plans"]) - 1, "step": i, "tool": s.get("tool"), "rule": rule, "reason": why} for i, s, rule, why in rejected]
        echo = RD.scrub_user_text(RD.plan_echo(rec["plans"][-1], rmap), task_dir, rmap)[0]
        lines = "\n".join("- step %d (%s): %s %s" % (i, s.get("tool"), rule, RD.scrub_user_text(rmap.text(why), task_dir, rmap)[0]) for i, s, rule, why in rejected)
        fb = user + "\n\nYour previous plan:\n%s\n\nThe policy rejected these steps:\n%s\nReturn a corrected plan." % (echo, lines)
        fviol = RD.payload_violations(echo + "\n" + lines, task_dir, rmap)
        if fviol:                       # QA fix #6: the replan is not sent; the first plan's admission stands
            rec["replan_privacy_refusal"] = fviol
            break
        plan = llm.structured("replan", sysp, fb, "rnplens_plan", PLAN_SCHEMA)
        rec["plans"].append(plan)
        rec["reference_claims"].append({"plan": len(rec["plans"]) - 1, "model_reference_supplied": plan.get("reference_supplied"),
                                        "declared": bool(ptask["reference_files"])})
        plan = declared_reference(plan, ptask)
        admitted, rejected, notes = admit_redacted(plan, ptask, rmap)
    rec["rejected_steps"] += [{"plan": len(rec["plans"]) - 1, "step": i, "tool": s.get("tool"), "rule": rule, "reason": why, "final": True} for i, s, rule, why in rejected]
    for n in notes:
        store.add([EV.missing("policy", n["capability"], n["capability"], n["status"] if n["status"] != "BLOCKED" else "TOOL_BLOCKED", n["reason"])], -1)
    admitted, pid_map = local_project_ids(admitted)
    rec["project_ids"] = {"rule": "model project ids replaced by local ids after admission (never rendered)",
                          "map": {local: model for model, local in pid_map.items()}}
    execute(ws, store, admitted, rec["tool_log"])
    final_plan = {"goal": plan["goal"], "reference_supplied": plan["reference_supplied"], "requested_capabilities": plan["requested_capabilities"],
                  "steps": [{"index": i, "tool": s["tool"], "args": a} for i, s, a in admitted]}
    json.dump(final_plan, open(os.path.join(run_dir, "plan.json"), "w"), indent=1)

    toks = allowed_tokens(store, ws)
    if answer_mode == "template":
        draft = templates.build(plan, store, notes)
        viol = gates.check(draft, store, plan["goal"], toks, plan["reference_supplied"])
        rec["gate_results"].append({"attempt": "template", "violations": viol})
        mode = "deterministic template"
        if viol:      # a template that fails its own checks is a defect: fall back to the minimal template and record it
            draft = render.template(plan["goal"], store, notes)
            rec["gate_results"].append({"attempt": "minimal template", "violations": gates.check(draft, store, plan["goal"], toks, plan["reference_supplied"])})
            mode = "minimal template (template defect recorded)"
        return _finish(rec, draft, store, notes, question, mode, final_plan, ws, llm, run_dir, t_start)
    dsys = _read("drafter.md")
    duser = ("Question:\n%s\n\nGoal: %s. Reference supplied: %s.\nAllowed identifier tokens (may be written as they are): %s\n\n"
             "Requested capabilities that are not available: %s\n\nEvidence records:\n%s\n" % (
                 question, plan["goal"], plan["reference_supplied"], ", ".join(toks[:200]),
                 json.dumps(notes) if notes else "none", json.dumps(_evidence_view(store), ensure_ascii=False)))
    duser = rmap.text(duser)           # 0.4 privacy: real names replaced by identifiers in the drafter payload too
    draft, mode = None, "drafted"
    for k in range(1 + max_redrafts):
        d = llm.structured("draft" if k == 0 else "redraft", dsys, duser if k == 0 else duser + rmap.text("\n\nYour previous draft:\n%s\n\nIt failed these checks:\n%s\nReturn a corrected draft." % (
            json.dumps(draft_try), "\n".join("- " + x for x in viol))), "rnplens_answer", DRAFT_SCHEMA)
        for st in (d.get("statements") or []) if isinstance(d, dict) else []:
            if isinstance(st.get("text"), str):          # identifiers back to the real names, locally
                st["text"] = re.sub(r"\b(?:run_\d{3}(?:/(?:candidate|file)_\d{3})?|(?:protein_|rna_)?sequence_\d{3}|reference_\d{3})\b",
                                    lambda x: os.path.basename(rmap.real(x.group(0))), st["text"])
        draft_try = d
        viol = gates.check(d, store, plan["goal"], toks, plan["reference_supplied"])
        rec["drafts"].append(d); rec["gate_results"].append({"attempt": k, "violations": viol})
        if not viol:
            draft = d; mode = "drafted" if k == 0 else "redrafted after gate failure"
            break
    if draft is None:
        draft = render.template(plan["goal"], store, notes)
        viol = gates.check(draft, store, plan["goal"], toks, plan["reference_supplied"])
        rec["gate_results"].append({"attempt": "template", "violations": viol})
        mode = "fixed template (drafts failed the checks)"
    return _finish(rec, draft, store, notes, question, mode, final_plan, ws, llm, run_dir, t_start)


def _privacy_refusal(rec, viol, question, run_dir, llm, t_start):
    """QA fix #6: the planner message failed the pre-send gate after redaction: no model call, a local answer only."""
    rec.update({"privacy_refusal": viol, "answer_mode": "not sent (pre-send privacy check)", "evidence_sha256": EV.Store().content_hash(),
                "llm_calls": llm.calls, "n_tool_calls": 0, "wall_s": round(time.time() - t_start, 2)})
    open(os.path.join(run_dir, "answer.md"), "w").write(
        "# RNPLens Assistant answer\n\n**Question.** %s\n\n- **Not sent.** After the automatic redaction, the message to Codex still "
        "contained %s, so nothing was sent and no language model was used. Rephrase the question without file paths or file "
        "names (the assistant already sees every task input by its identifier).\n" % (question, " and ".join(viol)))
    open(os.path.join(run_dir, "evidence.jsonl"), "w").close()
    json.dump(rec, open(os.path.join(run_dir, "run_record.json"), "w"), indent=1, default=str)
    return rec


def _finish(rec, draft, store, notes, question, mode, final_plan, ws, llm, run_dir, t_start):
    answer = render.render(draft, store, notes, question, mode)
    open(os.path.join(run_dir, "answer.md"), "w").write(answer)
    json.dump({"statements": draft["statements"], "rendered": [render.fill(s["text"], store) for s in draft["statements"]], "mode": mode},
              open(os.path.join(run_dir, "answer.json"), "w"), indent=1)
    store.write(os.path.join(run_dir, "evidence.jsonl"))
    rec.update({"answer_mode": mode, "evidence_sha256": store.content_hash(), "plan_sha256": hashlib.sha256(json.dumps(final_plan, sort_keys=True).encode()).hexdigest(),
                "n_tool_calls": ws.calls, "llm_calls": llm.calls, "wall_s": round(time.time() - t_start, 2)})
    json.dump(rec, open(os.path.join(run_dir, "run_record.json"), "w"), indent=1, default=str)
    return rec
