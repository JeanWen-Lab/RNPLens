"""SCRIPTED demonstration of the Codex follow-up path (docs/followup.md, "Worked example (scripted client)").

NO language model and NO Codex process: the planning call is answered by a scripted stand-in client
(rnplens_assistant.llm.Stub) with two fixed proposals, and the doctor's agent check is replaced by a stub that
reports the stand-in. Everything else (consent record, evidence summary, privacy check, policy F1-F9, confirmation
via --yes, execution of controlled RNPLens functions, templated answer, traceability check, record) is the real code.
The live Codex follow-up awaits the owner's confirmation and is covered by FOLLOWUP_SUITE_v1 Part 2 (frozen, not run).

usage: python followup_scripted.py PROJECT ANALYSIS QUESTION EVIDENCE_ID OUT_JSON
"""
import json
import sys

from rnplens import provenance as pv
from rnplens_assistant import consent, followup as F, llm

RATIONALE = "This proves the second run is the right run; confidence 0.97; it is the best run."   # must never be shown


def main(project, analysis, question, eid, out):
    consent.opt_in(project, "--yes")
    replies = [{"follow_up": "export_table_or_methods", "args": dict(F._blank(), export="methods"), "rationale": "scripted proposal 1"},
               {"follow_up": "inspect_existing_comparison", "args": dict(F._blank(), evidence_id=eid), "rationale": RATIONALE}]
    client = llm.Stub(replies)
    rec = F.run(project, analysis, question, mode="codex", yes=True, out=print, client_factory=lambda: client,
                agent_status=lambda: (True, []))
    md = open(analysis + "/" + rec["dir"] + "/followup_answer.md").read() if rec.get("dir") else ""
    res = {"provenance": pv.block("demo_followup_scripted", [], "scripted stand-in for the Codex planning call (no model)",
                                  {"client": "rnplens_assistant.llm.Stub", "replies": replies, "agent_status": "stub (True, [])"}),
           "label": "SCRIPTED DEMONSTRATION - no Codex or language-model call was made",
           "dir": rec.get("dir"), "mode": rec.get("mode"), "model_config": rec.get("model_config"),
           "model_calls_made": rec.get("model_calls_made"),
           "proposals": [{"follow_up": p.get("proposal", p).get("follow_up") if isinstance(p, dict) else None,
                          "verdict": p.get("verdict") if isinstance(p, dict) else None,
                          "rule": p.get("rule") if isinstance(p, dict) else None} for p in rec.get("proposals", [])],
           "proposals_raw": rec.get("proposals"),
           "chosen": rec.get("chosen"), "stop": rec.get("stop"), "user_confirmation": rec.get("user_confirmation"),
           "traceability_violations": rec.get("traceability_violations"), "wording_audit": rec.get("wording_audit"),
           "rationale_shown_in_answer": RATIONALE in md or "0.97" in md or "proves" in md,
           "evidence_sha256": rec.get("evidence_sha256")}
    pv.atomic_write_json(out, res)
    print("scripted follow-up: dir %s, model calls %s, chosen %s, rationale shown %s"
          % (res["dir"], res["model_calls_made"], (rec.get("chosen") or {}).get("follow_up"), res["rationale_shown_in_answer"]))
    return 0 if not res["rationale_shown_in_answer"] and not res["traceability_violations"] else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:6]))
