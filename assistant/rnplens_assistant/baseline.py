"""General-agent arm (G): the same model, the same typed tools, the same documentation, inputs, filesystem boundary and
budget, but no RNPLens planner prompt, no policy admission, no typed statements and no answer gates. Every attempted
call, including failed ones, is recorded."""
import datetime
import json
import os
import time

from . import ask, evidence as EV, tools as T

SYSTEM = ("You are an assistant that helps researchers analyse predicted protein-RNA complex structures with the tools "
          "provided. Use the tools as needed, then answer the user's question in a few clear paragraphs.\n\n"
          "# RNPLens documentation (which analysis to use)\n\n")
MAX_TOOL_CALLS, MAX_MODEL_CALLS = 10, 14


def tool_specs():
    out = []
    for name, s in T.SCHEMAS.items():
        out.append({"type": "function", "name": name, "description": s["description"], "strict": True,
                    "parameters": {"type": "object", "additionalProperties": False, "properties": s["properties"], "required": s["required"]}})
    return out


def run(task_dir, question, run_dir, llm):
    t0 = time.time()
    os.makedirs(run_dir, exist_ok=True)
    task = ask.load_task(task_dir)
    ws = T.Workspace(task_dir, run_dir)
    store = EV.Store()
    files, nfiles = ask.listing(task_dir)
    user = ("Question:\n%s\n\nTask inputs (%d files, paths relative to the task folder):\n%s\n\nExperimental reference files supplied with this task: %s\n"
            % (question, nfiles, "\n".join(files), ", ".join(task["reference_files"]) or "none"))
    items = [{"role": "system", "content": SYSTEM + ask.doc_text()}, {"role": "user", "content": user}]
    log, final, n_model = [], None, 0
    specs = tool_specs()
    while n_model < MAX_MODEL_CALLS:
        n_model += 1
        resp = llm.tool_loop_step("agent", items, specs if ws.calls < MAX_TOOL_CALLS else [])
        calls = [o for o in resp.output if getattr(o, "type", None) == "function_call"]
        items += [o.model_dump(exclude_none=True) if hasattr(o, "model_dump") else o for o in resp.output]
        if not calls:
            final = resp.output_text; break
        for c in calls:
            try:
                args = json.loads(c.arguments)
            except Exception:
                args = None
            if ws.calls >= MAX_TOOL_CALLS:
                status, res, recs = "BUDGET_EXHAUSTED", {"error": "tool-call budget exhausted"}, []
            elif args is None:
                status, res, recs = "INPUT_INVALID", {"error": "arguments are not valid JSON"}, []
            else:
                status, res, recs = T.call(ws, c.name, args)
            store.add(recs, len(log))
            log.append({"step": len(log), "tool": c.name, "args": args, "status": status if status != "OK" else res.get("status", "OK"), "result": res})
            view = {"result": res, "evidence": [{"id": r["id"], "what": r["label"], "value": EV.fmt(r), "state": r["state"]} for r in store.records if r["step"] == len(log) - 1]}
            items.append({"type": "function_call_output", "call_id": c.call_id, "output": json.dumps(view, ensure_ascii=False)[:60000]})
    if final is None:
        final = "(no final answer within the model-call budget)"
    open(os.path.join(run_dir, "answer.md"), "w").write("# General agent answer\n\n**Question.** %s\n\n%s\n" % (question, final))
    store.write(os.path.join(run_dir, "evidence.jsonl"))
    rec = {"arm": "G", "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "question": question,
           "task_id": task.get("task_id"), "llm_config": llm.config, "tool_log": log, "n_tool_calls": ws.calls, "n_model_calls": n_model,
           "llm_calls": llm.calls, "evidence_sha256": store.content_hash(), "wall_s": round(time.time() - t0, 2)}
    json.dump(rec, open(os.path.join(run_dir, "run_record.json"), "w"), indent=1, default=str)
    return rec
