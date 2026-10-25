#!/usr/bin/env bash
# Run both RNPLens worked examples from a clean installation.
#   usage: bash examples/run_examples.sh OUT_DIR        (OUT_DIR must not exist; nothing is overwritten)
# Example A (reference-based): RNPLens Evaluate on one Boltz-2 prediction of PDB 7K9D against the deposited structure.
# Example B (reference-free):  RNPLens Report on two independent Boltz-2 runs of 7K9D. No experimental structure is
#                              read in example B. Diagnose is BLOCKED in RNPLens 0.4 (until re-qualification): B2 only
#                              shows that 'rnplens diagnose run' refuses (exit 5) and writes nothing.
set -euo pipefail
OUT="${1:?usage: run_examples.sh OUT_DIR}"
[ -e "$OUT" ] && { echo "refused: $OUT exists" >&2; exit 2; }
EX="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
export MPLBACKEND="${MPLBACKEND:-Agg}"

echo "== Example A: reference-based evaluation (rnplens evaluate)"
cd "$EX/reference_based"
rnplens evaluate validate --input example_input.json
rnplens evaluate run --input example_input.json --out "$OUT/A_evaluate_7K9D"

echo "== Example B1: reference-free agreement (rnplens report)"
rnplens example-contract "$EX/reference_free" --out "$OUT/B1_report_contract.json"
rnplens report validate "$OUT/B1_report_contract.json"
rnplens report run "$OUT/B1_report_contract.json" --out "$OUT/B1_report_7K9D"

echo "== Example B2: Diagnose is BLOCKED in RNPLens 0.4 (expected: exit 5, nothing written)"
set +e
rnplens diagnose run "$EX"/reference_free/diagnose_7K9D/*.pdb --mode within_engine --engine BOLTZ2 --target 7K9D \
  --out "$OUT/B2_diagnose_7K9D" 2> "$OUT/B2_diagnose_BLOCKED.txt"
rc=$?
set -e
cat "$OUT/B2_diagnose_BLOCKED.txt"
if [ "$rc" -ne 5 ] || [ -e "$OUT/B2_diagnose_7K9D" ]; then echo "unexpected: diagnose exit $rc" >&2; exit 1; fi

echo "== done: outputs in $OUT"
