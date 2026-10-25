"""General-agent arm (G) on the Codex backend: the same Codex model and settings, inside the same jail, with the same
six typed tools (via MCP), the same documentation and inputs, and the same tool-call budget and time limit. It has no
RNPLens planner prompt, no policy admission and no evidence-linked templates; it writes its own answer and declares
its action class in a minimal JSON envelope (needed for deterministic scoring)."""
import datetime
import json
import os
import time

from . import ask, codex_llm, evidence as EV, mcp_server, tools as T

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_TOOL_CALLS = 10
ACTIONS = ["ANSWER", "ANSWER_WITH_LIMITATION", "CLARIFY", "REFUSE_WITH_ALTERNATIVE"]
SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "action": {"type": "string", "enum": ACTIONS}, "answer": {"type": "string"}}, "required": ["action", "answer"]}
SYSTEM = ("You are an assistant that helps researchers analyse predicted protein-RNA complex structures. The task input files "
          "are not in your working directory; use the tools of the 'rnplens' MCP server, which read them (paths relative to the "
          "task inputs listed below). Use the tools as needed (at most %d calls), then answer the user's question in a few clear "
          "paragraphs. Return JSON: `answer` is your answer; `action` is ANSWER (you answered), ANSWER_WITH_LIMITATION (you answered "
          "and stated an important limitation), CLARIFY (you need information from the user first) or REFUSE_WITH_ALTERNATIVE "
          "(the request cannot be done; you say what can be done instead).\n\n# RNPLens documentation (which analysis to use)\n\n") % MAX_TOOL_CALLS


def run(task_dir, question, run_dir, client):
    t0 = time.time()
    os.makedirs(run_dir, exist_ok=True)
    task = ask.load_task(task_dir)
    ws = T.Workspace(task_dir, run_dir)
    store = EV.Store()
    files, nfiles = ask.listing(task_dir)
    user = ("Question:\n%s\n\nTask inputs (%d files, paths relative to the task folder):\n%s\n\nExperimental reference files supplied with this task: %s\n"
            % (question, nfiles, "\n".join(files), ", ".join(task["reference_files"]) or "none"))
    prompt = SYSTEM + ask.doc_text() + "\n\n---\n\n" + user
    cd = client.new_call_dir("agent")
    sp = os.path.join(cd, "tools.sock")
    srv = mcp_server.Server(sp, ws, store, MAX_TOOL_CALLS)
    extra = ["-c", 'mcp_servers.rnplens.command="/usr/bin/python3"', "-c", 'mcp_servers.rnplens.args=["/work/mcp_relay.py"]',
             "-c", "mcp_servers.rnplens.tool_timeout_sec=1800", "-c", "mcp_servers.rnplens.startup_timeout_sec=60",
             "-c", 'mcp_servers.rnplens.default_tools_approval_mode="approve"']
    out, err = None, None
    try:
        out = client.run("agent", prompt, SCHEMA, extra_args=extra, call_dir=cd,
                         call_files={"mcp_relay.py": os.path.join(HERE, "mcp_relay.py")})
    except codex_llm.UsageGuard:
        raise
    except Exception as ex:
        err = "%s: %s" % (type(ex).__name__, str(ex)[:400])
    finally:
        srv.close()
    final = out or {"action": None, "answer": "(no final answer: %s)" % err}
    open(os.path.join(run_dir, "answer.md"), "w").write("# General agent answer\n\n**Question.** %s\n\n**Declared action.** %s\n\n%s\n" % (
        question, final["action"], final["answer"]))
    json.dump(final, open(os.path.join(run_dir, "answer.json"), "w"), indent=1)
    store.write(os.path.join(run_dir, "evidence.jsonl"))
    rec = {"arm": "G", "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "question": question,
           "task_id": task.get("task_id"), "llm_config": client.config, "tool_log": srv.log, "n_tool_calls": len(srv.log),
           "llm_calls": client.calls, "error": err, "evidence_sha256": store.content_hash(), "wall_s": round(time.time() - t0, 2)}
    json.dump(rec, open(os.path.join(run_dir, "run_record.json"), "w"), indent=1, default=str)
    return rec
