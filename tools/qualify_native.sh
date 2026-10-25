#!/bin/bash
# RNPLens 0.4 native platforms: independent qualification on ONE computer (Linux or macOS). No model call is made.
#   usage: bash tools/qualify_native.sh [OUT]        run from the source checkout, as your own user (never root)
#   OUT default: $HOME/projects/RNPBench/RNPLens_native_qualification/<system>_<utc>   (must not exist)
#   env:  PY   a Python 3.10-3.12 interpreter (default: python3.11, else python3)
# Gates (each PASS or FAIL in OUT/QUALIFICATION.json and QUALIFICATION.md):
#   G1 install      wheels of rnplens and rnplens-assistant built from this checkout and installed into a fresh venv,
#                   without administrator rights
#   G2 doctor       `rnplens doctor --agent` from the installed packages: every check READY (needs Codex 0.159.3,
#                   ChatGPT sign-in, the tested model and the confinement of this system)
#   G3 selftest     `rnplens selftest`
#   G4 examples     reference-based (Evaluate) and reference-free (Report) worked examples
#   G5 confinement  this system's real confinement tests against the INSTALLED package: none may fail or be skipped
#                   (Linux: test_confine_linux.py; macOS: test_confine_macos.py incl. the installed Codex binary)
#   G6 suite        full test suite from the checkout (tests + assistant/tests): plan acceptance and rejection, tools,
#                   evidence integrity, deterministic replay, doctor, confinement interface; no failures
set -u
SRC=$(cd "$(dirname "$0")/.." && pwd -P)
SYS=$(uname -s); ARCH=$(uname -m)
[ "$(id -u)" != 0 ] || { echo "refused: run as your own user, not root" >&2; exit 2; }
case "$SYS" in Linux) CONF=test_confine_linux.py; REQ=RNPLENS_REQUIRE_BWRAP;; Darwin) CONF=test_confine_macos.py; REQ=RNPLENS_REQUIRE_SEATBELT;;
  *) echo "refused: $SYS is not supported" >&2; exit 2;; esac
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT=${1:-$HOME/projects/RNPBench/RNPLens_native_qualification/${SYS}_$STAMP}
[ ! -e "$OUT" ] || { echo "refused: $OUT exists" >&2; exit 2; }
mkdir -p "$OUT/logs" "$OUT/tmp" "$OUT/work" && OUT=$(cd "$OUT" && pwd -P)
PY=${PY:-$(command -v python3.11 || command -v python3)}
unset PYTHONPATH RNPLENS_CODEX_JAIL
export TMPDIR="$OUT/tmp/" PIP_DISABLE_PIP_VERSION_CHECK=1 MPLBACKEND=Agg
printf 'step\texit\tcommand\n' > "$OUT/results.tsv"
run() { local n=$1; shift; printf '$ %s\n' "$*" > "$OUT/logs/$n.log"; "$@" >> "$OUT/logs/$n.log" 2>&1; local rc=$?
        printf '%s\t%s\t%s\n' "$n" "$rc" "$*" >> "$OUT/results.tsv"; return $rc; }
G() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$OUT/gates.tsv"; echo "$1 $2  $3"; }
: > "$OUT/gates.tsv"
{ echo "system=$SYS arch=$ARCH"; [ "$SYS" = Darwin ] && sw_vers; [ "$SYS" = Linux ] && grep -E '^(PRETTY_NAME)=' /etc/os-release
  echo "python=$("$PY" -c 'import sys;print(sys.version.split()[0])')"; echo "uid=$(id -u)"
  echo "commit=$(git -C "$SRC" rev-parse HEAD 2>/dev/null) dirty_files=$(git -C "$SRC" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"; } > "$OUT/platform.txt"
cat "$OUT/platform.txt"

# G1 install (no root): build wheels from this checkout, install into a fresh venv
ok=1
run 01_venv_build "$PY" -m venv "$OUT/venv_build" || ok=0
run 02_wheels "$OUT/venv_build/bin/python" -m pip wheel -q --no-deps -w "$OUT/dist" "$SRC" "$SRC/assistant" || ok=0
run 03_venv "$PY" -m venv "$OUT/venv" || ok=0
W1=$(ls "$OUT"/dist/rnplens-*.whl 2>/dev/null | head -1); W2=$(ls "$OUT"/dist/rnplens_assistant-*.whl 2>/dev/null | head -1)
run 04_install "$OUT/venv/bin/python" -m pip install -q "$W1[html,test]" "$W2" || ok=0
run 05_installed "$OUT/venv/bin/python" -c "import rnplens, rnplens_assistant, os; print(rnplens.__version__, os.path.dirname(rnplens_assistant.__file__))" || ok=0
grep -q "site-packages" "$OUT/logs/05_installed.log" || ok=0
[ $ok = 1 ] && G G1_install PASS "wheels installed into a fresh venv as uid $(id -u)" || G G1_install FAIL "see logs/0[1-5]_*.log"
R="$OUT/venv/bin/rnplens"; VPY="$OUT/venv/bin/python"
cd "$OUT/work" || exit 2

# G2 doctor (installed packages only)
mkdir -p "$OUT/doctor"; run 10_doctor "$R" doctor --agent --json --save --out "$OUT/doctor"
"$VPY" - "$OUT/doctor/doctor.json" > "$OUT/logs/10_doctor_summary.txt" 2>&1 <<'EOF'
import json, sys
d = json.load(open(sys.argv[1])); bad = [c for c in d["checks"] if c["status"] != "READY"]
for c in d["checks"]:
    print("%-20s %-16s %s" % (c["id"], c["status"], c.get("detail", "")[:150]))
sys.exit(1 if bad else 0)
EOF
[ $? = 0 ] && G G2_doctor PASS "every check READY" || G G2_doctor FAIL "$(grep -v ' READY ' "$OUT/logs/10_doctor_summary.txt" | awk '{print $1}' | tr '\n' ' ')"

# G3 selftest, G4 examples
run 20_selftest "$R" selftest && G G3_selftest PASS "rnplens selftest" || G G3_selftest FAIL "logs/20_selftest.log"
run 30_examples env PATH="$OUT/venv/bin:$PATH" bash "$SRC/examples/run_examples.sh" "$OUT/examples" \
  && G G4_examples PASS "reference-based and reference-free examples" || G G4_examples FAIL "logs/30_examples.log"

# G5 confinement of THIS system, against the installed package; skips are failures
mkdir -p "$OUT/conftests" && cp "$SRC/assistant/tests/$CONF" "$SRC/assistant/tests/test_confine.py" "$OUT/conftests/"
run 40_confinement env "$REQ=1" RNPLENS_TEST_REAL_CODEX=1 "$VPY" -m pytest -q -p no:cacheprovider -rs "$OUT/conftests"
S=$(grep -E "passed|failed" "$OUT/logs/40_confinement.log" | tail -1)
if grep -q " failed\| error" <<<"$S"; then G G5_confinement FAIL "$S"
elif grep "^SKIPPED" "$OUT/logs/40_confinement.log" | grep -q "$CONF"; then G G5_confinement FAIL "skipped tests in $CONF: $S"
else G G5_confinement PASS "$S"; fi

# diagnostics only (no gate): on macOS, the Seatbelt denials of the last 20 minutes (operation and path names only)
if [ "$SYS" = Darwin ]; then
  /usr/bin/log show --last 20m --style compact --predicate 'sender == "Sandbox" AND eventMessage CONTAINS "deny("' 2>&1 \
    | grep -E "codex|bash" | sed -E 's/^[0-9: .-]+//' | sort | uniq -c | sort -rn | head -200 > "$OUT/logs/41_seatbelt_denials.log"
fi

# G6 full suite from the checkout (editable install in its own venv)
run 50_venv_src "$PY" -m venv "$OUT/venv_src"
run 51_install_src "$OUT/venv_src/bin/python" -m pip install -q -e "$SRC[html,test]" -e "$SRC/assistant"
( cd "$SRC" && run 52_suite env "$REQ=1" RNPLENS_TEST_REAL_CODEX=1 "$OUT/venv_src/bin/python" -m pytest -q -p no:cacheprovider -rfs tests assistant/tests )
S=$(grep -E "passed|failed" "$OUT/logs/52_suite.log" | tail -1)
if [ -z "$S" ]; then G G6_suite FAIL "no result"
elif ! grep -q " failed\| error" <<<"$S"; then G G6_suite PASS "$S"
else
  # The only accepted failure: LIVE_QUALIFICATION_v1 refusing the two sources re-pinned by the proposed Amendment 9
  # (records/native_platforms/LQ_AMENDMENT_9.DRAFT.md). Any other failing test, or any other refusal, is a FAIL.
  other=$(grep -E "^(FAILED|ERROR) " "$OUT/logs/52_suite.log" | grep -v "^FAILED assistant/tests/test_live_qualification.py::" | wc -l | tr -d ' ')
  refused=$(grep -o "pinned source changed since the freeze: [^ ']*" "$OUT/logs/52_suite.log" | sed 's/.*: //' | sort -u | tr '\n' ' ')
  if [ "$other" = 0 ] && [ "$refused" = "assistant/rnplens_assistant/codex_llm.py src/rnplens/doctor.py " ] \
     && ! grep -q "FREEZE mismatch\|unfrozen file\|FOLLOWUP_SUITE_v1 file changed" "$OUT/logs/52_suite.log"; then
    G G6_suite CONDITIONAL "$S; every failure is the LIVE_QUALIFICATION_v1 pin refusal of codex_llm.py and doctor.py (pending Amendment 9)"
  else G G6_suite FAIL "$S; other failing tests: $other; refused pins: $refused"; fi
fi
[ -z "$(git -C "$SRC" status --porcelain 2>/dev/null)" ] || echo "note: the source checkout has local changes (see platform.txt)" >> "$OUT/platform.txt"

# summary (no secrets: doctor output is redacted by the doctor itself)
"$VPY" - "$OUT" <<'EOF'
import json, os, sys
out = sys.argv[1]; g = [l.rstrip("\n").split("\t") for l in open(os.path.join(out, "gates.tsv")) if l.strip()]
res = {"platform": open(os.path.join(out, "platform.txt")).read().splitlines(), "gates": [{"gate": a, "result": b, "detail": c} for a, b, c in g]}
res["qualified"] = all(x["result"] == "PASS" for x in res["gates"])
res["qualified_pending_amendment_9"] = (not res["qualified"]) and all(x["result"] in ("PASS", "CONDITIONAL") for x in res["gates"])
json.dump(res, open(os.path.join(out, "QUALIFICATION.json"), "w"), indent=1)
md = ["# RNPLens native-platform qualification", "", "```"] + res["platform"] + ["```", "", "| gate | result | detail |", "|---|---|---|"]
md += ["| %s | %s | %s |" % (x["gate"], x["result"], x["detail"].replace("|", "/")) for x in res["gates"]]
verdict = "YES" if res["qualified"] else ("YES, CONDITIONAL on owner approval of LIVE_QUALIFICATION_v1 Amendment 9" if res["qualified_pending_amendment_9"] else "NO")
md += ["", "**Qualified: %s**" % verdict, "", "Logs: logs/; results.tsv; doctor/doctor.json."]
open(os.path.join(out, "QUALIFICATION.md"), "w").write("\n".join(md) + "\n")
print("\n".join(md))
EOF
echo "written: $OUT"
