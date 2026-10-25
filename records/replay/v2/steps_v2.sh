# Sourced by retest_case_v2.sh and continue_case_v2.sh: step runner (logs/<name>.log, logs/steps.tsv).
rnplens() { "$RNPLENS_PY" -m rnplens "$@"; }
py() { "$RNPLENS_PY" "$@"; }
step() {
  local name="$1" exp="$2"; shift 2
  printf '$ %s\n' "$*" > "logs/$name.log"
  "$@" >> "logs/$name.log" 2>&1
  local rc=$?
  printf '%s\t%s\t%s\t%s\n' "$name" "$exp" "$rc" "$*" >> logs/steps.tsv
  if [ "$rc" != "$exp" ]; then echo "STEP $name: exit $rc, expected $exp" >&2; tail -20 "logs/$name.log" >&2; echo INCOMPLETE > logs/RESULT; exit 1; fi
}
