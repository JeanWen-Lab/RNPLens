#!/bin/bash
# Orchestrates the frozen DETERMINISM_CONTRACT_v2 retest (section 6); adds no rule.
# usage: bash run_retest_v2.sh RETEST_ROOT [CASES]     (RETEST_ROOT must not exist; default cases: 2QQP 2XGJ 24BR)
# env:   RNPLENS_PY python importing the RNPLens checkout under test (PYTHONPATH set by the caller)
set -u
ROOT="$1"; CASES="${2:-2QQP 2XGJ 24BR}"; HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; : "${RNPLENS_PY:=python}"
if [ -e "$ROOT" ]; then echo "refused: $ROOT exists" >&2; exit 2; fi
mkdir -p "$ROOT" && cd "$ROOT" || exit 2
git -C "$HERE" rev-parse HEAD > code_commit.txt; git -C "$HERE" status --porcelain -- ../../../src ../../../assistant > code_status.txt
"$RNPLENS_PY" -c "import rnplens; assert rnplens.__version__.startswith('0.4.0'); print(rnplens.__version__, rnplens.__file__)" > environment.txt || exit 2
MODE=cases; [ "$CASES" != "2QQP 2XGJ 24BR" ] && MODE=classification
bash "$HERE/prepare_inputs_v2.sh" "$ROOT/prepared" "$MODE" > prepare.log 2>&1 || { echo "input preparation failed" >&2; exit 1; }
printf 'case\trun\tcase_root\tstart_utc\tend_utc\texit\n' > runs.tsv
rec() { printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$@" >> runs.tsv; }
for T in $CASES; do                                   # first runs; the moved copy is taken right after the base workflow
  ts="$(date -u +%Y%m%dT%H%M%SZ)"; R1="$ROOT/$T/first_$ts"; M="$ROOT/moved_elsewhere/${T}_copy_$ts"; mkdir -p "$ROOT/$T" "$ROOT/moved_elsewhere"
  s="$(date -u +%FT%TZ)"; TMPDIR="$ROOT/tmp_${T}_first" bash -c "mkdir -p \$TMPDIR; bash '$HERE/retest_case_v2.sh' '$R1' '$T' '$ROOT/prepared/$T'" > "${T}_first.log" 2>&1; rc=$?; rec "$T" first "$R1" "$s" "$(date -u +%FT%TZ)" "$rc"
  s="$(date -u +%FT%TZ)"; cp -a "$R1" "$M"; rc=$?; rec "$T" copy "$M" "$s" "$(date -u +%FT%TZ)" "$rc"
  s="$(date -u +%FT%TZ)"; TMPDIR="$ROOT/tmp_${T}_first" bash "$HERE/continue_case_v2.sh" "$R1" > "${T}_first_cont.log" 2>&1; rc=$?; rec "$T" first_continuation "$R1" "$s" "$(date -u +%FT%TZ)" "$rc"
done
sleep 125
for T in $CASES; do                                   # second runs: other absolute directory, later time
  ts="$(date -u +%Y%m%dT%H%M%SZ)"; R2="$ROOT/$T/second_copy_$ts"
  s="$(date -u +%FT%TZ)"; TMPDIR="$ROOT/tmp_${T}_second" bash -c "mkdir -p \$TMPDIR; bash '$HERE/retest_case_v2.sh' '$R2' '$T' '$ROOT/prepared/$T'" > "${T}_second.log" 2>&1; rc=$?; rec "$T" second "$R2" "$s" "$(date -u +%FT%TZ)" "$rc"
  s="$(date -u +%FT%TZ)"; TMPDIR="$ROOT/tmp_${T}_second" bash "$HERE/continue_case_v2.sh" "$R2" > "${T}_second_cont.log" 2>&1; rc=$?; rec "$T" second_continuation "$R2" "$s" "$(date -u +%FT%TZ)" "$rc"
done
for T in $CASES; do                                   # moved copies continued last (latest time)
  M="$(awk -F'\t' -v t="$T" '$1==t && $2=="copy"{print $3}' runs.tsv)"
  s="$(date -u +%FT%TZ)"; mkdir -p "$ROOT/tmp_${T}_moved"; TMPDIR="$ROOT/tmp_${T}_moved" bash "$HERE/continue_case_v2.sh" "$M" > "${T}_moved_cont.log" 2>&1; rc=$?; rec "$T" moved_continuation "$M" "$s" "$(date -u +%FT%TZ)" "$rc"
done
printf 'case\tpair\tverdict\tcheck\n' > verdicts.tsv
for T in $CASES; do
  R1="$(awk -F'\t' -v t="$T" '$1==t && $2=="first"{print $3}' runs.tsv)"; R2="$(awk -F'\t' -v t="$T" '$1==t && $2=="second"{print $3}' runs.tsv)"
  M="$(awk -F'\t' -v t="$T" '$1==t && $2=="copy"{print $3}' runs.tsv)"
  "$RNPLENS_PY" "$HERE/check_pair_v2.py" "$R1" "$R2" "check_${T}_first_vs_second.json" > "check_${T}_first_vs_second.log" 2>&1; rc=$?
  printf '%s\tfirst_vs_second\t%s\t%s\n' "$T" "$([ $rc = 0 ] && echo PASS || echo FAIL)" "$(tail -1 "check_${T}_first_vs_second.log")" >> verdicts.tsv
  "$RNPLENS_PY" "$HERE/check_pair_v2.py" "$R1" "$M" "check_${T}_first_vs_moved.json" --moved > "check_${T}_first_vs_moved.log" 2>&1; rc=$?
  printf '%s\tfirst_vs_moved\t%s\t%s\n' "$T" "$([ $rc = 0 ] && echo PASS || echo FAIL)" "$(tail -1 "check_${T}_first_vs_moved.log")" >> verdicts.tsv
done
if awk -F'\t' 'NR>1 && $3!="PASS"{bad=1} END{exit bad}' verdicts.tsv; then echo PASS > OVERALL; else echo FAIL > OVERALL; fi
echo DONE > DONE
