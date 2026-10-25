"""Scripted stand-ins for the Codex planning call (FOLLOWUP_SUITE_v1). No network, no language model.

ScriptedClient  returns scripted proposals in order (the deterministic fake client of Part 1).
write_fake_jail writes an executable script used IN PLACE OF codex_adapter/codex_jail.sh, so that the real
                codex_llm.CodexClient runs end to end (subprocess, session log, usage and credit guard) against a scripted
                'codex': modes ok | fail | sleep | usage99 | credit_change."""
import json
import os
import stat


class ScriptedClient:
    def __init__(self, replies, model="scripted-fake"):
        self.replies, self.calls = list(replies), []
        self.config = {"provider": "scripted fake (FOLLOWUP_SUITE_v1)", "model": model, "reasoning_effort": None}

    def structured(self, kind, system, user, schema_name, schema):
        import hashlib
        self.calls.append({"kind": kind, "prompt_sha256": hashlib.sha256((system + "\n\n---\n\n" + user).encode()).hexdigest(),
                           "model_requested": self.config["model"], "model_returned": self.config["model"], "error": None})
        if not self.replies:
            raise RuntimeError("scripted client has no reply left")
        r = self.replies.pop(0)
        if isinstance(r, dict) and r.get("__raise__"):
            raise RuntimeError(r["__raise__"])
        return r


FAKE_JAIL = r'''#!/bin/bash
# Fake jail for FOLLOWUP_SUITE_v1: behaves like codex_jail.sh + codex exec, scripted by environment variables.
CALL="$1"; shift; [ "$1" = "--" ] && shift
cat > /dev/null                                   # the prompt arrives on stdin
mkdir -p "$CALL/.codex_sessions/x"
MODE="${FAKE_CODEX_MODE:-ok}"
if [ "$MODE" = "fail" ]; then echo "error: failed to connect to the model service" >&2; exit 1; fi
if [ "$MODE" = "sleep" ]; then sleep "${FAKE_CODEX_SLEEP:-5}"; fi
USED="${FAKE_CODEX_USED:-3.0}"; BAL="${FAKE_CODEX_BALANCE:-0}"
[ "$MODE" = "usage99" ] && USED=99.0
[ "$MODE" = "credit_change" ] && BAL=5
cat > "$CALL/.codex_sessions/x/rollout.jsonl" <<EOT
{"type":"session_meta","payload":{"cli_version":"fake-0"}}
{"type":"turn_context","payload":{"model":"gpt-6.1-sol","effort":"medium"}}
{"type":"event_msg","payload":{"type":"token_count","info":{"total_token_usage":{"input_tokens":10,"output_tokens":5}},"rate_limits":{"primary":{"used_percent":$USED,"window_minutes":300},"secondary":{"used_percent":1.0,"window_minutes":10080},"credits":{"balance":"$BAL"},"plan_type":"fake"}}}
EOT
cp "$FAKE_CODEX_REPLY" "$CALL/last.json"
echo '{"type":"done"}'
'''


def write_fake_jail(path):
    with open(path, "w") as fh:
        fh.write(FAKE_JAIL)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def write_reply(path, reply):
    with open(path, "w") as fh:
        json.dump(reply, fh)
    return path
