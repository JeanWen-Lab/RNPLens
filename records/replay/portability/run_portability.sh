#!/bin/bash
# Orchestrates PORTABILITY_TEST_v1 (records/replay/PORTABILITY_TEST_v1.md); adds no rule.
# usage: bash run_portability.sh ROOT [CASES]   (ROOT must not exist; default cases: 2QQP 2XGJ)
# env:   RNPLENS_PY python importing the RNPLens checkout under test (PYTHONPATH set by the caller)
set -u
ROOT="$1"; CASES="${2:-2QQP 2XGJ}"; HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; V2="$HERE/../v2"; : "${RNPLENS_PY:=python}"
if [ -e "$ROOT" ]; then echo "refused: $ROOT exists" >&2; exit 2; fi
mkdir -p "$ROOT" && cd "$ROOT" || exit 2
git -C "$HERE" rev-parse HEAD > code_commit.txt; git -C "$HERE" status --porcelain -- ../../../src ../../../assistant > code_status.txt
"$RNPLENS_PY" -c "import rnplens; assert rnplens.__version__.startswith('0.4.0'); print(rnplens.__version__, rnplens.__file__)" > environment.txt || exit 2
MODE=cases; case "$CASES" in *1VTM*) MODE=classification;; esac
bash "$V2/prepare_inputs_v2.sh" "$ROOT/prepared" "$MODE" > prepare.log 2>&1 || { echo "input preparation failed" >&2; exit 1; }
printf 'case\tverdict\tcheck\n' > verdicts.tsv
for T in $CASES; do
  ts="$(date -u +%Y%m%dT%H%M%SZ)"; R1="$ROOT/$T/orig_$ts"; mkdir -p "$ROOT/$T" "$ROOT/tmp_$T"
  TMPDIR="$ROOT/tmp_$T" bash "$V2/retest_case_v2.sh" "$R1" "$T" "$ROOT/prepared/$T" > "${T}_base.log" 2>&1; rc=$?
  echo "$T base exit $rc" >> base_exits.txt
  if [ $rc != 0 ]; then printf '%s\tFAIL\tbase workflow exit %s\n' "$T" "$rc" >> verdicts.tsv; continue; fi
  TMPDIR="$ROOT/tmp_$T" "$RNPLENS_PY" "$HERE/portability_case.py" "$ROOT" "$T" "$R1" > "${T}_driver.log" 2>&1; echo "$T driver exit $?" >> base_exits.txt
  "$RNPLENS_PY" "$HERE/check_portability.py" "$ROOT/$T/portability_run.json" "check_$T.json" > "check_$T.log" 2>&1; rc=$?
  printf '%s\t%s\t%s\n' "$T" "$([ $rc = 0 ] && echo PASS || echo FAIL)" "$(head -1 "check_$T.log")" >> verdicts.tsv
done
if awk -F'\t' 'NR>1 && $2!="PASS"{bad=1} END{exit bad}' verdicts.tsv; then echo PASS > OVERALL; else echo FAIL > OVERALL; fi
echo DONE > DONE
