"""Diagnostic for the 66d186c retest failure (not part of any frozen contract).

usage: python confirm_evidence_definition.py OUT_JSON RECORD_JSON...

For each followup_record.json (inside <tree>/project/analyses/.../followup/fu_NNNN/):
  recorded   evidence_sha256 and evidence_hash_version of the record (and of the sibling followup_plan.json);
  tracer_d1  the hash as records/replay/trace_replay_diffs.py recomputes it (definition-1 rule, inline);
  declared   rnplens_assistant.followup.evidence_hash(statements, tool_log, P, A, version=<declared>) with
             P, A = the tree's head import and analysis directories of group 'main' (rnplens.state), statements
             from the sibling followup_answer.json, tool_log from the record (absent version = definition 1).
"""
import hashlib
import json
import os
import sys

from rnplens import state
from rnplens_assistant import followup as F


def tracer_d1(rec, ans):
    # verbatim rule of trace_replay_diffs.Tree derive (lines 218-227 at 66d186c)
    keep = [{"type": st["type"], "text": st["text"],
             "slots": {n: {k: F._norm(x, None, None) for k, x in s.items()} for n, s in sorted(st["slots"].items())},
             "cites": st["cites"]} for st in ans.get("statements") or []]
    log = [{"tool": e["tool"], "call": e["call"], "status": e["status"], "outputs": e.get("outputs"),
            "message": F._norm(e.get("message"), None, None)} for e in rec.get("tool_log") or []]
    return hashlib.sha256(json.dumps({"statements": keep, "tool_log": log}, sort_keys=True, default=str).encode()).hexdigest()


def one(path):
    path = os.path.abspath(path)
    fdir = os.path.dirname(path)
    proj = path[:path.index("/project/") + len("/project")]
    rec = json.load(open(path, encoding="utf-8"))
    ans = json.load(open(os.path.join(fdir, "followup_answer.json"), encoding="utf-8"))
    plan = json.load(open(os.path.join(fdir, "followup_plan.json"), encoding="utf-8"))
    head = state.Project(proj).head()["analyses"]["main"]
    P, A = os.path.join(proj, head["import_dir"]), os.path.join(proj, head["dir"])
    ver = rec.get("evidence_hash_version")
    d1 = tracer_d1(rec, ans)
    dec = F.evidence_hash(ans.get("statements") or [], rec.get("tool_log") or [], P, A, version=ver)
    return {"record": path, "tree": proj[:-len("/project")], "import_dir": head["import_dir"], "analysis_dir": head["dir"],
            "record_in_head_analysis": fdir.startswith(A + os.sep),
            "recorded_evidence_sha256": rec.get("evidence_sha256"), "evidence_hash_version": ver,
            "plan_evidence_sha256": plan.get("evidence_sha256"), "plan_evidence_hash_version": plan.get("evidence_hash_version"),
            "tracer_definition_1_sha256": d1, "tracer_definition_1_equal": d1 == rec.get("evidence_sha256"),
            "declared_definition_sha256": dec, "declared_definition_equal": dec == rec.get("evidence_sha256")}


def main(out, *recs):
    rows = [one(p) for p in recs]
    summ = {"n_records": len(rows),
            "versions": sorted({str(r["evidence_hash_version"]) for r in rows}),
            "n_tracer_definition_1_equal": sum(r["tracer_definition_1_equal"] for r in rows),
            "n_declared_definition_equal": sum(r["declared_definition_equal"] for r in rows),
            "n_plan_hash_equal_record": sum(r["plan_evidence_sha256"] == r["recorded_evidence_sha256"] for r in rows),
            "n_record_in_head_analysis": sum(r["record_in_head_analysis"] for r in rows)}
    json.dump({"summary": summ, "records": rows}, open(out, "w"), indent=1, sort_keys=True)
    open(out, "a").write("\n")
    print(json.dumps(summ, sort_keys=True))
    return 0 if summ["n_declared_definition_equal"] == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
