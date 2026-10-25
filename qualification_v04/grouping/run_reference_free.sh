#!/bin/bash
# Detached reference-free qualification on karyon (Spec B v2 section 5; Amendment 3 A3.8).
# Usage: bash run_reference_free.sh CLONE OUT
set -u
CLONE=$1; OUT=$2
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH=$CLONE/src:$CLONE/assistant
export TMPDIR=/home/jwen/projects/RNPBench/scratch_agent/v04/grouping/tmp
mkdir -p "$TMPDIR" "$OUT"
PY=/home/jwen/projects/RNPBench/RNPLens_dev_0.3/venv/bin/python
Q=$CLONE/qualification_v04/grouping
$PY -c "import rnplens; assert rnplens.__version__ == '0.4.0.dev0', rnplens.__version__; print(rnplens.__file__)" || exit 3
git -C "$CLONE" rev-parse HEAD > "$OUT/code_commit.txt"
for P in A B; do
  $PY $Q/qualify.py --pool $P --out "$OUT" --workers 32 > "$OUT/log_pool$P.txt" 2>&1
done
for P in A B; do
  $PY $Q/contacts_parity.py --pool $P --qual "$OUT" --out "$OUT/contacts_parity_pool$P.json" >> "$OUT/log_parity.txt" 2>&1
done
date > "$OUT/DONE_REFERENCE_FREE"
