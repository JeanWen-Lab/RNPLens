#!/usr/bin/env bash
# Run both RNPLens worked examples from a clean installation.
#   usage: bash examples/run_examples.sh OUT_DIR        (OUT_DIR must not exist; nothing is overwritten)
# Example A (reference-based): RNPLens Evaluate on one Boltz-2 prediction of PDB 7K9D against the deposited structure.
# Example B (reference-free):  RNPLens Report on two independent Boltz-2 runs of 7K9D, and RNPLens Diagnose on the
#                              five samples of one Boltz-2 run. No experimental structure is read in example B.
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

echo "== Example B2: reference-free validity and candidate disagreement (rnplens diagnose)"
rnplens diagnose validity "$EX"/reference_free/diagnose_7K9D/*.pdb > "$OUT/B2_diagnose_validity.json"
rnplens diagnose run "$EX"/reference_free/diagnose_7K9D/*.pdb --mode within_engine --engine BOLTZ2 --target 7K9D --out "$OUT/B2_diagnose_7K9D"

echo "== done: outputs in $OUT"
