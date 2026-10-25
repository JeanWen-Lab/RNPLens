"""Premise check r2 (Amendment 4; not part of the scored suite): the exact payloads of the redacted planner and
follow-up on the real development tasks, without any language model.

For every Part P/Z task: the planner's first-call payload as the assistant builds it (scripted capture client through
ask.run), compared byte for byte with run_live.expected_nl_payload (independent reconstruction of the declared rule);
a replan payload (first scripted plan names a real path, so the policy refuses it with P9). For the three Part F tasks:
the follow-up payload and a replan payload (first scripted proposal names the real run folders, so it repeats an
existing comparison or is refused). Each payload is checked by the suite's pre-send gate (privacy.gate with the real
names forbidden), by followup.privacy_check, and by a scan for real names; its sha256, size and an excerpt are recorded.
No Codex subprocess is started.

    python premise_check_r2.py TASKS OUT.json SCRATCH"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import privacy  # noqa: E402
import run_live as R  # noqa: E402


class Capture:
    def __init__(self, replies):
        self.replies, self.payloads, self.calls = list(replies), [], []
        self.config = {"model": "premise-capture (no model)", "reasoning_effort": None}

    def structured(self, kind, system, user, schema_name, schema):
        self.payloads.append((kind, system, system + "\n\n---\n\n" + user))
        self.calls.append({"kind": kind})
        r = self.replies.pop(0)
        return r(user) if callable(r) else r


def step(tool, **kw):
    s = {k: None for k in ("project_id", "folders", "protein_fasta", "rna_fasta", "engine", "accept_offsets", "before_project_id",
                           "after_project_id", "reference", "rna_start", "rna_end", "protein_start", "protein_end", "metric_name",
                           "runs", "query", "evidence_id", "contact")}
    s.update(tool=tool, purpose="premise", **kw)
    return s


def judge(payload, system, names, task_dir, project=None, extra=()):
    from rnplens_assistant import followup as F
    ctx = R.privacy_ctx(task_dir, system, list(extra) + [R.RNPBENCH, os.path.expanduser("~") + "/"], names)
    leaked = sorted(n for n in names if n in payload and n not in system)
    return {"sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(), "bytes": len(payload.encode("utf-8")),
            "gate_findings": privacy.gate(payload, **ctx), "followup_privacy_check": F.privacy_check(payload, project or task_dir),
            "real_names_found": leaked, "n_names_checked": len(names)}


def main(tasks, out, scratch):
    from rnplens import assist
    from rnplens_assistant import ask, consent, followup as F
    S = R.load_scenarios()
    fu = R.load_followup_suite()
    res = {"schema": "lq1.premise_check_r2", "planner": {}, "followup": {}}
    imp = step("import_predictions", project_id="p", folders=["run_001", "run_002"], protein_fasta="protein_sequence_001",
               rna_fasta="rna_sequence_001", accept_offsets=False)
    for s in S["part_Z"] + S["part_P"]:
        tmp = tempfile.mkdtemp(dir=scratch)
        tn = os.path.join(tmp, "task_nl")
        shutil.copytree(os.path.join(tasks, s["task"]), tn)
        names = R.real_names(tn) | {s["task"]}
        refd = bool(json.load(open(os.path.join(tn, "task.json"), encoding="utf-8")).get("reference_files"))
        bad = {"goal": "AGREEMENT", "reference_supplied": refd, "requested_capabilities": [], "clarification_needed": None,
               "steps": [dict(imp, folders=["run_A", "run_B"])]}
        good = {"goal": "AGREEMENT", "reference_supplied": refd, "requested_capabilities": [], "clarification_needed": None,
                "steps": [imp, step("analyse_predictions", project_id="p")]}
        cl = Capture([bad, good])
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            ask.run(tn, s["question"], os.path.join(tmp, "nl"), cl)
        system, user = R.expected_nl_payload(s["question"], tn)
        first = cl.payloads[0][2]
        e = {"reconstruction_equals_assistant_payload": first == system + "\n\n---\n\n" + user,
             "calls": [k for k, _, _ in cl.payloads],
             "first_call": judge(first, cl.payloads[0][1], names, tn, extra=[tmp]),
             "replan": judge(cl.payloads[1][2], cl.payloads[1][1], names, tn, extra=[tmp]),
             "excerpt_user_message": user[:700],
             "replan_feedback_excerpt": cl.payloads[1][2].split("Your previous plan:", 1)[-1][:500]}
        res["planner"][s["id"]] = e
    S2 = json.load(open(os.path.join(R.ROOT, S["part_F"]["source"]), encoding="utf-8"))
    for lid in S["part_F"]["ids"]:
        s = next(x for x in S2["scenarios"] if x["id"] == lid)
        work = tempfile.mkdtemp(dir=scratch)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            P, A = fu["run_part2"].setup_task(os.path.join(tasks, s["task"]), work)
            initial = {"kind": "menu_item", "capability": "interface_overview"}
            if s["initial"]["item"] == "C":
                rr = fu["run_part2"]._auto_range(A)
                assert assist.main(["--project", P, "--analysis", A, "--item", "C", "--rna", rr, "--runs", "run_A,run_B", "--json"], out=lambda *x: None) == 0
                initial = {"kind": "menu_item", "capability": "region_run_comparison"}
        consent.opt_in(P, "--yes")
        blank = {k: None for k in F.ARGS}
        first = {"follow_up": "compare_runs_in_region", "args": dict(blank, rna_start=1, rna_end=2, runs=["run_A", "run_B"]), "rationale": "premise"}
        cl = Capture([first, {"follow_up": "none", "args": blank, "rationale": "premise"}])
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rec = F.run(P, A, s["question"], mode="codex", initial=initial, yes=True, ask=None, out=lambda *x: None,
                        client_factory=lambda: cl, agent_status=lambda: (True, []))
        names = (R.real_names(os.path.join(work, "task")) | R.manifest_names(P) | {s["task"], "summary.json", "region.json"}
                 | {d for d in os.listdir(A) if d.startswith("region_")})
        e = {"calls": [k for k, _, _ in cl.payloads], "stop": (rec.get("stop") or {}).get("kind"),
             "proposal_rules": [p["verdict"]["rule"] for p in rec.get("proposals") or []],
             "payloads_equal_record": [hashlib.sha256(p[2].encode()).hexdigest() for p in cl.payloads] == [p["sha256"] for p in rec["payloads"]]}
        for i, (kind, system, payload) in enumerate(cl.payloads):
            e[kind] = judge(payload, system, names, os.path.join(work, "task"), P, extra=[work])
        e["excerpt_summary_sent"] = rec["summary"]["text"][:600]
        if len(cl.payloads) > 1:
            e["replan_feedback_excerpt"] = cl.payloads[1][2].split("Your previous proposal:", 1)[-1][:400]
        res["followup"][lid] = e
    flat = [x for v in res["planner"].values() for x in (v["first_call"], v["replan"])] + \
           [v[k] for v in res["followup"].values() for k in ("followup", "followup_replan") if k in v]
    res["summary"] = {"payloads_checked": len(flat),
                      "all_reconstructions_equal": all(v["reconstruction_equals_assistant_payload"] for v in res["planner"].values()),
                      "gate_findings": sum(len(x["gate_findings"]) for x in flat),
                      "followup_privacy_check_findings": sum(len(x["followup_privacy_check"]) for x in flat),
                      "real_names_found": sum(len(x["real_names_found"]) for x in flat)}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    print(json.dumps(res["summary"]))


if __name__ == "__main__":
    main(*sys.argv[1:4])
