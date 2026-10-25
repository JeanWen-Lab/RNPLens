"""A FAKE Codex CLI for the LIVE_QUALIFICATION_v1 mocked tests. It is never a language model and opens no network
connection: it answers --version, 'login status' and 'debug models', and for 'exec' it reads the prompt from stdin,
picks the first scripted rule whose 'match' strings all occur in the prompt, writes the scripted reply to the -o file
and a Codex-style session log (turn_context model, token_count with rate_limits: plan usage and credits balance).

write_fake_codex(dir, script, python)  -> path of an executable 'codex' (put fake_script.json next to it)
write_fake_jail(path, fake_bin)        -> a pass-through jail for machines without bubblewrap (macOS tests only)

Rule fields: match [str], reply {...}, fill {"args.evidence_id": regex with one group, taken from the prompt},
balance (string or None), credits (dict or None: replaces the credits object), weekly, primary (percent),
model_returned, effort_returned, omit_rate_limits, reached, exit + stderr (a failing call)."""
import json
import os
import stat

FAKE = r'''#!%(python)s
import json, os, re, sys
HERE = os.path.dirname(os.path.realpath(__file__))
S = json.load(open(os.path.join(HERE, "fake_script.json")))
a = sys.argv[1:]
if a[:1] == ["--version"]:
    print("codex-cli %%s" %% S.get("version", "0.159.3")); sys.exit(0)
if a[:2] == ["login", "status"]:
    print(S.get("login", "Logged in using ChatGPT")); sys.exit(0)
if a[:2] == ["debug", "models"]:
    print("\n".join(S.get("models", ["gpt-6.1-sol", "gpt-6.1-sol-mini"]))); sys.exit(0)
if a[:1] != ["exec"]:
    print("fake codex: unsupported arguments %%r" %% a[:3], file=sys.stderr); sys.exit(2)
work = os.environ.get("FAKE_WORK") or "/work"
wp = lambda p: os.path.join(work, p[len("/work/"):]) if p.startswith("/work/") else p
prompt = sys.stdin.read()
open(os.path.join(work, "fake_stdin.txt"), "w").write(prompt)
model = a[a.index("-m") + 1] if "-m" in a else None
rule = next((r for r in S.get("rules", []) if all(m in prompt for m in r.get("match", []))), S.get("default"))
if rule is None:
    print("fake codex: no scripted rule matches", file=sys.stderr); sys.exit(3)
if rule.get("exit"):
    print(rule.get("stderr", "error: failed to connect to the model service"), file=sys.stderr); sys.exit(rule["exit"])
reply = json.loads(json.dumps(rule.get("reply", {})))
for path, rx in (rule.get("fill") or {}).items():
    m = re.search(rx, prompt)
    o = reply
    ks = path.split(".")
    for k in ks[:-1]:
        o = o[k]
    o[ks[-1]] = m.group(1) if m else None
U = dict(S.get("usage_default", {}), **{k: v for k, v in rule.items() if k in ("balance", "credits", "weekly", "primary", "reached", "omit_rate_limits")})
rl = {"primary": {"used_percent": U.get("primary", 3.0), "window_minutes": 300},
      "secondary": {"used_percent": U.get("weekly", 20.0), "window_minutes": 10080},
      "credits": {"has_credits": True, "unlimited": False, "balance": U.get("balance", "12.50")}, "plan_type": "pro"}
if "credits" in U:
    rl["credits"] = U["credits"]
if U.get("reached"):
    rl["rate_limit_reached_type"] = U["reached"]
sess = os.environ.get("FAKE_SESSIONS") or os.path.join(os.environ.get("CODEX_HOME", "/nonexistent"), "sessions")
d = os.path.join(sess, "2026", "10", "17"); os.makedirs(d, exist_ok=True)
ev = [{"type": "session_meta", "payload": {"cli_version": S.get("version", "0.159.3")}},
      {"type": "turn_context", "payload": {"model": rule.get("model_returned", model), "effort": rule.get("effort_returned", "medium")}},
      {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": len(prompt) // 4, "output_tokens": 50}},
                                         "rate_limits": None if U.get("omit_rate_limits") else rl}}]
with open(os.path.join(d, "rollout-fake.jsonl"), "w") as fh:
    for e in ev:
        fh.write(json.dumps(e) + "\n")
json.dump(reply, open(wp(a[a.index("-o") + 1]), "w"))
print(json.dumps({"type": "turn.completed"}))
'''

JAIL = r'''#!/bin/bash
# pass-through stand-in for codex_jail.sh on machines without bubblewrap (mocked tests only)
CALL=$(cd "$1" && pwd); shift; [ "${1:-}" = "--" ] && shift
mkdir -p "$CALL/.codex_sessions"
if [ "${RNPLENS_JAIL_PROBE:-}" = 1 ]; then echo JAIL_OK; exit 0; fi
cd "$CALL" && exec env -u OPENAI_API_KEY -u CODEX_API_KEY FAKE_WORK="$CALL" FAKE_SESSIONS="$CALL/.codex_sessions" "%(bin)s" "$@"
'''


def _x(path):
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def write_fake_codex(directory, script, python="/usr/bin/python3"):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "fake_script.json"), "w") as fh:
        json.dump(script, fh, indent=1)
    p = os.path.join(directory, "codex")
    with open(p, "w") as fh:
        fh.write(FAKE % {"python": python})
    return _x(p)


def set_script(directory, script):
    with open(os.path.join(directory, "fake_script.json"), "w") as fh:
        json.dump(script, fh, indent=1)


def write_fake_jail(path, fake_bin):
    with open(path, "w") as fh:
        fh.write(JAIL % {"bin": fake_bin})
    return _x(path)
