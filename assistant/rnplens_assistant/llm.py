"""Language-model access. One pinned configuration; every call is recorded (model ID returned by the API, usage,
latency, prompt hash). The API key comes from the environment (OPENAI_API_KEY) and is never written anywhere."""
import hashlib
import json
import os
import time

CONFIG = {"provider": "openai", "api": "responses", "model": "gpt-5.4-2026-03-05", "reasoning_effort": "medium",
          "store": False, "max_output_tokens": 6000}


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


class Client:
    """Thin wrapper; `calls` keeps the per-call record that goes into the run record."""
    def __init__(self, config=None):
        self.config = dict(CONFIG, **(config or {}))
        self.calls = []
        from openai import OpenAI
        self.api = OpenAI()

    def _record(self, kind, prompt_hash, resp, t0, error=None):
        u = getattr(resp, "usage", None)
        self.calls.append({"kind": kind, "prompt_sha256": prompt_hash, "model_requested": self.config["model"],
                           "model_returned": getattr(resp, "model", None), "latency_s": round(time.time() - t0, 3),
                           "input_tokens": getattr(u, "input_tokens", None), "output_tokens": getattr(u, "output_tokens", None),
                           "reasoning_tokens": getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", None),
                           "error": error})

    def structured(self, kind, system, user, schema_name, schema):
        t0 = time.time(); ph = sha(system + "\n\x00\n" + user + json.dumps(schema, sort_keys=True))
        try:
            resp = self.api.responses.create(
                model=self.config["model"], reasoning={"effort": self.config["reasoning_effort"]}, store=self.config["store"],
                max_output_tokens=self.config["max_output_tokens"],
                input=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                text={"format": {"type": "json_schema", "name": schema_name, "schema": schema, "strict": True}})
        except Exception as ex:
            self._record(kind, ph, None, t0, error="%s: %s" % (type(ex).__name__, str(ex)[:300])); raise
        self._record(kind, ph, resp, t0)
        return json.loads(resp.output_text)

    def tool_loop_step(self, kind, items, tools):
        """One Responses call in a function-calling loop (used by the general-agent arm)."""
        t0 = time.time(); ph = sha(json.dumps(items[:2], sort_keys=True, default=str))
        try:
            resp = self.api.responses.create(
                model=self.config["model"], reasoning={"effort": self.config["reasoning_effort"]}, store=self.config["store"],
                max_output_tokens=self.config["max_output_tokens"], include=["reasoning.encrypted_content"],
                input=items, tools=tools, parallel_tool_calls=False)
        except Exception as ex:
            self._record(kind, ph, None, t0, error="%s: %s" % (type(ex).__name__, str(ex)[:300])); raise
        self._record(kind, ph, resp, t0)
        return resp


class Stub:
    """Deterministic stand-in for development tests without network access: returns canned objects in order."""
    def __init__(self, replies):
        self.replies, self.calls, self.config = list(replies), [], dict(CONFIG, model="stub")

    def structured(self, kind, system, user, schema_name, schema):
        r = self.replies.pop(0)
        self.calls.append({"kind": kind, "prompt_sha256": sha(system + user), "model_requested": "stub", "model_returned": "stub",
                           "latency_s": 0, "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "error": None})
        return r(user) if callable(r) else r
