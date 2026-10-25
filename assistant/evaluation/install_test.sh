#!/bin/bash
# Independent installation test (protocol v2 §7.5): a fresh environment, following assistant/README.md only.
# Writes INSTALL_TEST.json in the test folder. Usage: install_test.sh REPO_DIR TEST_ROOT DEV_TASK DEV_PLAN EXPECT_HASH
set +e
REPO=$1; ROOT=$2; TASK=$3; PLAN=$4; EXPECT=$5
T=$ROOT/install_test_$(date +%Y%m%dT%H%M%S); mkdir -p $T; cd $T
PY311=$(command -v python3.11 || echo /home/jwen/miniforge3/envs/pcfold3d-rnp/bin/python)
res(){ echo "\"$1\": $2," >> $T/steps.part; }
$PY311 -m venv VENV > venv.log 2>&1; res venv $?
VENV/bin/pip install -q "$REPO" > pip_toolkit.log 2>&1; res pip_toolkit $?
VENV/bin/pip install -q "$REPO/assistant" > pip_assistant.log 2>&1; res pip_assistant $?
VENV/bin/rnplens selftest > selftest.log 2>&1; res selftest $?
PATH=$HOME/.local/bin:$PATH codex login status 2>&1 | grep -q "Logged in using ChatGPT"; res codex_chatgpt_login $?
export RNPLENS_CODEX_JAIL=$REPO/assistant/codex_adapter/codex_jail.sh RNPLENS_CODEX_CALLS=$T/codex_calls
unset OPENAI_API_KEY CODEX_API_KEY PYTHONPATH
mkdir -p $T/codex_calls
# keep comparing against the credits balance recorded before any evaluation call (no fresh baseline)
cp /home/jwen/projects/RNPBench/scratch_agent/codex_calls/credits_baseline.json $T/codex_calls/ 2>/dev/null; res credits_baseline_present $?
export PATH=$HOME/.local/bin:$PATH
cd /tmp 2>/dev/null; cd $T
VENV/bin/python -m rnplens_assistant replay "$PLAN" --task "$TASK" --out $T/replay --expect "$EXPECT" > replay.log 2>&1; res replay_hash_match $?
VENV/bin/python -m rnplens_assistant ask "These are two Boltz-2 runs for the same construct. Do they support the same binding surface and the same residue-nucleotide contacts?" --task "$TASK" --out $T/ask > ask.log 2>&1; res codex_ask $?
test -s $T/ask/answer.md; res answer_written $?
VENV/bin/python -c "import rnplens_assistant,rnplens,sys;print(rnplens_assistant.__file__, rnplens.__file__)" > installed_from.log 2>&1
grep -q "$T/VENV" installed_from.log; res imports_from_fresh_venv $?
# Amendment 4: the installed assistant gives the arms exactly the evaluated prompt context and guide
VENV/bin/python -c "import hashlib,sys; from rnplens_assistant import ask, tools; t=hashlib.sha256(ask.doc_text().encode()).hexdigest(); r,_=tools.explain_metric(None,'fnat'); e=hashlib.sha256(repr(r).encode()).hexdigest()[:16]; print(t, e); sys.exit(0 if (t=='a79637fdf4cb1e1317ab9a72194d9a047e356fa665f1f9f145a089e1ce1dea97' and e=='1615052ac88cf3f8') else 1)" > guide_check.log 2>&1; res installed_prompt_equals_evaluated $?
python3 - $T <<'PYEOF'
import json, sys
T = sys.argv[1]
steps = json.loads("{" + open(T + "/steps.part").read().rstrip().rstrip(",") + "}")
json.dump({"steps": {k: (v == 0) for k, v in steps.items()}, "passed": all(v == 0 for v in steps.values()), "folder": T},
          open(T + "/INSTALL_TEST.json", "w"), indent=1)
print(json.dumps(json.load(open(T + "/INSTALL_TEST.json"))))
PYEOF
