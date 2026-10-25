"""Development-only pilot on karyon (no sealed task): both arms through Codex on five tasks built from development
targets, LLM-free replay of every assistant plan, and plan-usage measurement for the full-evaluation estimate."""
import csv
import glob
import json
import os
import shutil
import sys
import time

from rnplens_assistant import ask, baseline_codex, codex_llm, replay

B = "/home/jwen/projects/RNPBench"
W = B + "/RNPLens_dev_0.3/assistant_2026-10-16"
PILOT = "/home/jwen/projects/PCfold3D-RNP/outputs/rnpbench/pilot/boltz"
SP = B + "/RNPLens_dev_0.3/work/sp_in"
TASKS = B + "/scratch_agent/assistant_dev_tasks"
EX = W + "/RNPLens/examples"


def copy_run(src, dst):
    os.makedirs(dst)
    for f in sorted(os.listdir(src)):
        if f.endswith((".pdb", ".cif")) or (f.startswith("confidence_") and f.endswith(".json")):
            shutil.copy(os.path.join(src, f), dst)


def seqs(T, d):
    r = {x["target_id"]: x for x in csv.DictReader(open(SP + "/before.tsv"), delimiter="\t")}[T]
    open(d + "/protein.fasta", "w").write(">protein\n%s\n" % r["protein_sequence"])
    open(d + "/rna.fasta", "w").write(">rna\n%s\n" % r["rna_sequence"])
    return {x["target_id"]: x for x in csv.DictReader(open(SP + "/references.tsv"), delimiter="\t")}[T]["reference"]


def build():
    if os.path.exists(TASKS):
        shutil.rmtree(TASKS)
    T = {}
    d = TASKS + "/d1_7K9D_agreement"; os.makedirs(d)
    shutil.copytree(EX + "/reference_free/report_7K9D/exec_A", d + "/run_A"); shutil.copytree(EX + "/reference_free/report_7K9D/exec_B", d + "/run_B")
    shutil.copy(EX + "/reference_based/7K9D_protein.fasta", d + "/protein.fasta"); shutil.copy(EX + "/reference_based/7K9D_rna.fasta", d + "/rna.fasta")
    T["d1_7K9D_agreement"] = ("These are two Boltz-2 runs for the same construct. Do they support the same binding surface and the same residue-nucleotide contacts?", [])
    for name, tgt, q, ref in (
            ("d2_1VTM_agreement", "1VTM", "These are two Boltz-2 runs (five samples each) for the same construct. Do they support the same binding surface and the same residue-nucleotide contacts?", False),
            ("d3_1VTM_accuracy", "1VTM", "Which of these two runs is more accurate?", False),
            ("d4_24BR_compare", "24BR", "Compare run A with run B against this experimental structure.", True),
            ("d5_24BR_geometry", "24BR", "Compare run A with run B against this experimental structure, and tell me which changes concern RNA conformation versus placement.", True)):
        d = TASKS + "/" + name; os.makedirs(d)
        copy_run("%s/exec_A/%s/boltz_results_%s/predictions/%s" % (PILOT, tgt, tgt, tgt), d + "/run_A")
        copy_run("%s/exec_B/%s/boltz_results_%s/predictions/%s" % (PILOT, tgt, tgt, tgt), d + "/run_B")
        refp = seqs(tgt, d)
        refs = []
        if ref:
            shutil.copy(refp, d + "/reference.cif"); refs = ["reference.cif"]
        T[name] = (q, refs)
    for name, (q, refs) in T.items():
        json.dump({"task_id": name, "reference_files": refs, "development_only": True}, open(TASKS + "/%s/task.json" % name, "w"))
    return T


SURFACE_Q = "List the exact names of every tool or function you are able to call in this session (including built-in ones). Do not call any tool."
SURFACE_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {"tools": {"type": "array", "items": {"type": "string"}}}, "required": ["tools"]}


def surface(tag):
    """Model-reported tool surface per arm configuration (self-report; recorded as such)."""
    from rnplens_assistant import evidence as EV, mcp_server, tools as T
    res = {}
    cl = codex_llm.CodexClient("surface_%s_R" % tag)
    res["R"] = cl.run("surface", SURFACE_Q, SURFACE_SCHEMA)["tools"]
    cl = codex_llm.CodexClient("surface_%s_G" % tag); cd = cl.new_call_dir("surface")
    srv = mcp_server.Server(cd + "/tools.sock", T.Workspace(TASKS + "/d1_7K9D_agreement", cd + "/ws"), EV.Store(), 0)
    try:
        res["G"] = cl.run("surface", SURFACE_Q, SURFACE_SCHEMA, call_dir=cd, call_files={"mcp_relay.py": os.path.dirname(baseline_codex.__file__) + "/mcp_relay.py"},
                          extra_args=["-c", 'mcp_servers.rnplens.command="/usr/bin/python3"', "-c", 'mcp_servers.rnplens.args=["/work/mcp_relay.py"]',
                                      "-c", 'mcp_servers.rnplens.default_tools_approval_mode="approve"'])["tools"]
    finally:
        srv.close()
    return res


def main(out):
    T = build()
    os.makedirs(out, exist_ok=True)
    json.dump(surface(time.strftime("%H%M%S")), open(os.path.join(out, "tool_surface.json"), "w"), indent=1)
    os.makedirs(out, exist_ok=True)
    rows = []
    for name, (q, refs) in T.items():
        for arm in ("R", "G"):
            rd = os.path.join(out, name, arm)
            cl = codex_llm.CodexClient("pilot_%s_%s" % (name.split("_")[0], arm))
            t0 = time.time()
            try:
                rec = ask.run(TASKS + "/" + name, q, rd, cl) if arm == "R" else baseline_codex.run(TASKS + "/" + name, q, rd, cl)
                ok, err = True, rec.get("error")
            except codex_llm.UsageGuard as ex:
                rows.append({"task": name, "arm": arm, "ok": False, "error": "USAGE GUARD: %s" % ex}); break
            except Exception as ex:
                ok, err, rec = False, "%s: %s" % (type(ex).__name__, str(ex)[:300]), {}
            row = {"task": name, "arm": arm, "ok": ok, "error": err, "wall_s": round(time.time() - t0, 1),
                   "answer_mode": rec.get("answer_mode"), "n_tool_calls": rec.get("n_tool_calls"),
                   "tool_statuses": [x.get("status") for x in rec.get("tool_log", [])],
                   "rejected_steps": rec.get("rejected_steps"), "llm_calls": cl.calls}
            if arm == "R" and ok and os.path.exists(rd + "/plan.json"):
                h, _ = replay.run(rd + "/plan.json", TASKS + "/" + name, rd + "_replay")
                row["replay_hash_equal"] = h == rec["evidence_sha256"]
            if os.path.exists(rd + "/answer.json"):
                row["answer"] = json.load(open(rd + "/answer.json"))
            rows.append(row)
            json.dump(rows, open(os.path.join(out, "pilot_rows.json"), "w"), indent=1, default=str)
    calls = [c for r in rows for c in r.get("llm_calls", [])]
    up = [c["plan_used_percent"] for c in calls if c.get("plan_used_percent") is not None]
    summ = {"n_runs": len(rows), "n_ok": sum(r["ok"] for r in rows), "n_codex_calls": len(calls),
            "models_returned": sorted({c["model_returned"] for c in calls if c.get("model_returned")}),
            "efforts_returned": sorted({c["effort_returned"] for c in calls if c.get("effort_returned")}),
            "cli_versions": sorted({c["cli_version"] for c in calls if c.get("cli_version")}),
            "tokens_input": sum(c.get("input_tokens") or 0 for c in calls), "tokens_cached": sum(c.get("cached_input_tokens") or 0 for c in calls),
            "tokens_output": sum(c.get("output_tokens") or 0 for c in calls),
            "plan_used_percent_first_last": [up[0], up[-1]] if up else None, "plan_window_minutes": calls[0].get("plan_window_minutes") if calls else None,
            "credits_balance_first_last": [calls[0].get("credits_balance"), calls[-1].get("credits_balance")] if calls else None,
            "replay_all_equal": all(r.get("replay_hash_equal", True) for r in rows if r["arm"] == "R" and r["ok"]),
            "per_arm": {a: {"tokens_input": sum(c.get("input_tokens") or 0 for r in rows if r["arm"] == a for c in r.get("llm_calls", [])),
                            "tokens_output": sum(c.get("output_tokens") or 0 for r in rows if r["arm"] == a for c in r.get("llm_calls", [])),
                            "wall_s": sum(r.get("wall_s") or 0 for r in rows if r["arm"] == a), "n": sum(1 for r in rows if r["arm"] == a)} for a in ("R", "G")}}
    json.dump(summ, open(os.path.join(out, "pilot_summary.json"), "w"), indent=1, default=str)
    print(json.dumps(summ, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1])
