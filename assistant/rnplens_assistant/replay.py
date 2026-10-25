"""Replay a saved plan without any language model: S4-S6 only. The evidence content hash must match the original.

Replay integrity (0.4 release audit): before anything is executed or written, a saved plan must be the plan its run
recorded and must pass the policy again.
* Plan identity: if the plan's folder holds the run's run_record.json with a plan_sha256, the plan must hash to it
  (PLAN_CHANGED otherwise). Without such a record (a historical or relocated plan) the replay still runs and reports
  plan_identity NOT_VERIFIED; it is never reported as verified.
* Saved steps are re-admitted by policy.admit with the plan's own reference declaration: a step refused by the tool
  allowlist (P1), the step budget (P4), the relative-path rule (P7) or a reference rule (P2) (STEP_REJECTED), or a step
  whose arguments are not exactly the admitted arguments (STEP_ARGS_CHANGED), refuses the replay. The sequencing rules
  (P3, P6) are not re-applied (see check_plan).
* A follow-up plan must carry exactly the approved choice and evidence_sha256 of its followup_record.json, not only
  agree with the hash the plan file states about itself.
These checks establish consistency with the saved run record. They are not signatures: someone who rewrites both the
plan and its record consistently is not detected."""
import hashlib
import json
import os

from . import ask, evidence as EV, tools as T

VERIFIED, NOT_VERIFIED = "VERIFIED", "NOT_VERIFIED"


class ReplayRefused(Exception):
    """A saved plan that may not be replayed: nothing was executed or written."""
    def __init__(self, code, message):
        super().__init__("%s: %s" % (code, message))
        self.code, self.message = code, message


def plan_sha256(plan):
    """The run record's plan hash (ask.run: sha256 of the plan serialised with sorted keys)."""
    return hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()


def _sibling_record(plan_path, name):
    p = os.path.join(os.path.dirname(os.path.abspath(plan_path)), name)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def check_plan(plan, task, record=None):
    """-> (plan_identity, policy notes). Raises ReplayRefused for a plan that is not the recorded plan or whose saved
    steps the policy does not admit with exactly the saved arguments."""
    steps = plan.get("steps") if isinstance(plan, dict) else None
    if not isinstance(steps, list) or not all(isinstance(s, dict) for s in steps):
        raise ReplayRefused("PLAN_INVALID", "the saved plan has no list of steps")
    identity = NOT_VERIFIED
    if record is not None and record.get("plan_sha256"):
        got = plan_sha256(plan)
        if got != record["plan_sha256"]:
            raise ReplayRefused("PLAN_CHANGED", "the plan differs from the plan recorded in run_record.json "
                                "(plan_sha256 %s, recorded %s)" % (got, record["plan_sha256"]))
        identity = VERIFIED
    idx = [s.get("index") for s in steps]
    if not all(isinstance(i, int) for i in idx) or idx != sorted(set(idx)):
        raise ReplayRefused("PLAN_INVALID", "step indices must be distinct increasing integers: %r" % idx)
    flat = []
    for s in steps:
        a = s.get("args") if isinstance(s.get("args"), dict) else {}
        f = dict(a, tool=s.get("tool"))
        if s.get("tool") == "explain_metric":
            f["metric_name"] = a.get("name")
        flat.append(f)
    from . import policy
    admitted, rejected, notes = policy.admit({"steps": flat, "reference_supplied": plan.get("reference_supplied"),
                                              "requested_capabilities": plan.get("requested_capabilities")}, task)
    # Sequencing rules (P3, P6) are not re-applied: the original run admitted its steps in the context of steps that a
    # later identifier check (P9) may have removed from the saved plan, and a step on a project that was not imported
    # can only fail as a recorded tool error. policy.admit checks P1, P7 and P2 before them, so a step refused only for
    # sequencing has passed those; an import refused as "imported twice" skipped one P2 check, which is applied here.
    refs = set(task.get("reference_files") or [])
    args_of = {i: a for i, _s, a in admitted}
    for i, s, rule, why in rejected:
        seq = rule in ("P3", "P6")
        if seq and s.get("tool") == "import_predictions" and any(f in refs for f in (s.get("folders") or [])):
            seq, rule, why = False, "P2", "a reference structure cannot be imported as a prediction"
        if not seq:
            raise ReplayRefused("STEP_REJECTED", "saved step %s (%s) is refused by the policy (%s: %s)" % (idx[i], s.get("tool"), rule, why))
        args_of[i] = policy.step_args(s)
    for i, s in enumerate(steps):
        a = args_of.get(i)
        if a != (s.get("args") or {}):
            raise ReplayRefused("STEP_ARGS_CHANGED", "saved step %s (%s): arguments %s are not the admitted arguments %s"
                                % (s.get("index"), s.get("tool"), json.dumps(s.get("args"), sort_keys=True)[:200],
                                   json.dumps(a, sort_keys=True)[:200]))
    return identity, notes


def run_checked(plan_path, task_dir, run_dir, record=None):
    """-> (evidence hash, tool log, plan_identity, recorded evidence_sha256 or None). Raises ReplayRefused before
    anything is executed or written."""
    with open(plan_path, encoding="utf-8") as fh:
        plan = json.load(fh)
    rec = record if record is not None else _sibling_record(plan_path, "run_record.json")
    identity, notes = check_plan(plan, ask.load_task(task_dir), rec)
    ws = T.Workspace(task_dir, run_dir)
    store = EV.Store()
    for n in notes:
        store.add([EV.missing("policy", n["capability"], n["capability"], n["status"] if n["status"] != "BLOCKED" else "TOOL_BLOCKED", n["reason"])], -1)
    log = []
    ask.execute(ws, store, [(s["index"], {"tool": s["tool"]}, s["args"]) for s in plan["steps"]], log)
    store.write(os.path.join(run_dir, "evidence.jsonl"))
    return store.content_hash(), log, identity, (rec or {}).get("evidence_sha256")


def run(plan_path, task_dir, run_dir):
    """-> (evidence hash, tool log), as before; raises ReplayRefused for a plan that may not be replayed."""
    h, log, _identity, _recorded = run_checked(plan_path, task_dir, run_dir)
    return h, log


def followup_plan_fields(rec):
    """The followup_plan.json fields that followup.run derives from its record: the approved choice (its id, arguments,
    rule, slots and the policy verdict's tool calls), the question, the evidence-hash definition and the evidence hash."""
    ch = rec.get("chosen") or {}
    return {"question_sha256": rec.get("question_sha256"), "source": ch.get("source"),
            "evidence_hash_version": rec.get("evidence_hash_version"), "follow_up": ch.get("id"), "args": ch.get("args"),
            "rule": ch.get("rule"), "rule_slots": ch.get("rule_slots"),
            "tool_calls": (ch.get("policy_verdict") or {}).get("tool_calls") or [],
            "executed": bool(rec.get("tool_log")), "evidence_sha256": rec.get("evidence_sha256")}


def run_followup_checked(plan_path, project, analysis):
    """-> (evidence hash, tool log, matches, plan_identity). With its followup_record.json present the plan must carry
    exactly the record's approved choice and evidence hash (PLAN_CHANGED otherwise); without it the plan's own hash is
    the expectation and plan_identity is NOT_VERIFIED."""
    from . import followup
    with open(plan_path, encoding="utf-8") as fh:
        expect = json.load(fh).get("evidence_sha256")
    with open(plan_path, encoding="utf-8") as fh:
        plan = json.load(fh)
    rec = _sibling_record(plan_path, "followup_record.json")
    identity = NOT_VERIFIED
    if rec is not None and rec.get("evidence_sha256"):
        changed = [k for k, v in followup_plan_fields(rec).items() if plan.get(k) != v]
        if changed:
            raise ReplayRefused("PLAN_CHANGED", "the follow-up plan differs from its followup_record.json in %s"
                                % ", ".join(changed))
        identity = VERIFIED
    h, log = followup.replay_plan(plan_path, project, analysis)
    return h, log, h == expect, identity


def run_followup(plan_path, project, analysis):
    """Replay a saved follow-up plan (followup_plan.json) without any language model. -> (evidence hash, tool log,
    matches). The hash must equal the record's evidence_sha256."""
    h, log, ok, _identity = run_followup_checked(plan_path, project, analysis)
    return h, log, ok
