#!/bin/bash
# Orchestrates the frozen requalification retest (DETERMINISM_CONTRACT_v1.md section 6): it adds no rule.
# usage: bash run_retest.sh RETEST_ROOT        (RETEST_ROOT must not exist)
# env:   RNPLENS_PY python importing the RNPLens checkout under test (PYTHONPATH set by the caller)
set -u
ROOT="$1"; HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; : "${RNPLENS_PY:=python}"
CASES="1VTM 7K9D 2JEA 2Q66"
if [ -e "$ROOT" ]; then echo "refused: $ROOT exists" >&2; exit 2; fi
mkdir -p "$ROOT" && cd "$ROOT" || exit 2
git -C "$HERE" rev-parse HEAD > code_commit.txt; git -C "$HERE" status --porcelain -- ../../../src ../../../assistant > code_status.txt
"$RNPLENS_PY" -c "import rnplens; assert rnplens.__version__.startswith('0.4.0'); print(rnplens.__version__, rnplens.__file__)" > environment.txt || exit 2
bash "$HERE/prepare_inputs.sh" "$ROOT/prepared" cases > prepare.log 2>&1 || { echo "input preparation failed" >&2; exit 1; }
printf 'case\trun\tcase_root\tstart_utc\tend_utc\texit\n' > runs.tsv
run() {  # run CASE WHICH
  local T="$1" W="$2" ts dir s e rc
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  if [ "$W" = first ]; then dir="$ROOT/$T/first_$ts"; else dir="$ROOT/$T/second_copy_$ts"; fi
  mkdir -p "$ROOT/$T"; mkdir -p "$ROOT/tmp_${T}_$W"
  s="$(date -u +%FT%TZ)"
  TMPDIR="$ROOT/tmp_${T}_$W" bash "$HERE/retest_case.sh" "$dir" "$T" "$ROOT/prepared/$T" > "$ROOT/${T}_$W.log" 2>&1; rc=$?
  e="$(date -u +%FT%TZ)"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$T" "$W" "$dir" "$s" "$e" "$rc" >> runs.tsv
}
for T in $CASES; do run "$T" first; done
sleep 125
for T in $CASES; do run "$T" second; done
printf 'case\tverdict\tcheck\n' > verdicts.tsv
for T in $CASES; do
  A="$(awk -F'\t' -v t="$T" '$1==t && $2=="first"{print $3}' runs.tsv)"; B="$(awk -F'\t' -v t="$T" '$1==t && $2=="second"{print $3}' runs.tsv)"
  "$RNPLENS_PY" "$HERE/check_pair.py" "$A" "$B" "check_$T.json" > "check_$T.log" 2>&1; rc=$?
  printf '%s\t%s\t%s\n' "$T" "$([ $rc = 0 ] && echo PASS || echo FAIL)" "$(tail -1 "check_$T.log")" >> verdicts.tsv
done
if awk -F'\t' 'NR>1 && $2!="PASS"{bad=1} END{exit bad}' verdicts.tsv; then echo PASS > OVERALL; else echo FAIL > OVERALL; fi
echo DONE > DONE
