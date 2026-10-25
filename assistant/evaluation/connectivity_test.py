"""Development-only access and compatibility test for the pinned model configuration (no sealed task is used).
Runs one R run and one G run on the bundled 7K9D example and records model ID returned, SDK version, settings,
latency and token use. Usage: OPENAI_API_KEY must be set in the environment; nothing is written that contains it."""
import json
import os
import shutil
import sys
import tempfile

import openai

from rnplens_assistant import ask, baseline, llm

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EX = os.path.join(ROOT, "examples")


def dev_task(d):
    t = os.path.join(d, "task")
    shutil.copytree(os.path.join(EX, "reference_free", "report_7K9D", "exec_A"), os.path.join(t, "runA"))
    shutil.copytree(os.path.join(EX, "reference_free", "report_7K9D", "exec_B"), os.path.join(t, "runB"))
    for f in ("7K9D_protein.fasta", "7K9D_rna.fasta"):
        shutil.copy(os.path.join(EX, "reference_based", f), os.path.join(t, f.replace("7K9D_", "")))
    json.dump({"task_id": "dev-connectivity", "reference_files": []}, open(os.path.join(t, "task.json"), "w"))
    return t


def main(out):
    os.makedirs(out, exist_ok=True)
    q = "These are two Boltz-2 runs for the same construct. Do they support the same binding surface and the same residue-nucleotide contacts?"
    res = {"openai_sdk": openai.__version__, "config": llm.CONFIG, "runs": {}}
    with tempfile.TemporaryDirectory() as d:
        t = dev_task(d)
        for arm, fn in (("R", ask.run), ("G", baseline.run)):
            cl = llm.Client()
            try:
                rec = fn(t, q, os.path.join(out, arm), cl)
                res["runs"][arm] = {"ok": True, "answer_mode": rec.get("answer_mode"), "n_tool_calls": rec.get("n_tool_calls"),
                                    "wall_s": rec.get("wall_s"), "llm_calls": cl.calls}
            except Exception as ex:
                res["runs"][arm] = {"ok": False, "error": "%s: %s" % (type(ex).__name__, str(ex)[:400]), "llm_calls": cl.calls}
    toks = [(c.get("input_tokens") or 0, c.get("output_tokens") or 0) for r in res["runs"].values() for c in r["llm_calls"]]
    res["models_returned"] = sorted({c.get("model_returned") for r in res["runs"].values() for c in r["llm_calls"] if c.get("model_returned")})
    res["tokens_in_out_total"] = [sum(a for a, _ in toks), sum(b for _, b in toks)]
    json.dump(res, open(os.path.join(out, "connectivity.json"), "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in res.items() if k != "runs"}, indent=1, default=str))
    for arm, r in res["runs"].items():
        print(arm, r.get("ok"), r.get("answer_mode"), r.get("error", ""), "calls:", len(r["llm_calls"]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "connectivity_out")
