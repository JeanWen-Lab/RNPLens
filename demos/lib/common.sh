# Sourced by the demonstration scripts. Deterministic RNPLens commands only; no language model is called.
#   RNPLENS_PY   python interpreter that imports the RNPLens checkout under test (default: python)
#   OUT          package folder (set by the caller before sourcing)
: "${RNPLENS_PY:=python}"
DEMOS_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rnplens() { "$RNPLENS_PY" -m rnplens "$@"; }
py() { "$RNPLENS_PY" "$@"; }
# step NAME EXPECTED_EXIT COMMAND...   runs COMMAND in $OUT, logs it to logs/NAME.log and logs/steps.tsv,
# and stops the demonstration if the exit code is not the expected one.
step() {
  local name="$1" exp="$2"; shift 2
  local log="logs/$name.log"
  printf '$ %s\n' "$*" > "$log"
  "$@" >> "$log" 2>&1
  local rc=$?
  printf '%s\t%s\t%s\t%s\n' "$name" "$exp" "$rc" "$*" >> logs/steps.tsv
  if [ "$rc" != "$exp" ]; then
    echo "STEP $name: exit $rc, expected $exp (see $OUT/$log)" >&2
    tail -20 "$log" >&2
    exit 1
  fi
}
start_package() {   # start_package OUT : create the package folder (must not exist) and cd into it
  OUT="$1"
  if [ -e "$OUT" ]; then echo "refused: $OUT exists" >&2; exit 2; fi
  mkdir -p "$OUT/logs" "$OUT/inputs" && cd "$OUT" || exit 2
  printf 'step\texpected_exit\texit\tcommand\n' > logs/steps.tsv
  "$RNPLENS_PY" - <<'PYEOF' > logs/environment.json
import json, platform, sys, rnplens
assert rnplens.__version__ == "0.4.0.dev0", rnplens.__version__
print(json.dumps({"rnplens_version": rnplens.__version__, "rnplens_file": rnplens.__file__,
                  "python": sys.version.split()[0], "platform": platform.platform()}, indent=1))
PYEOF
}
