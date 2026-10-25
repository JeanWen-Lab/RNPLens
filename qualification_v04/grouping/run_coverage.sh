#!/bin/bash
# Retrospective coverage; run only after records/grouping/CODE_FREEZE.md is committed. Usage: bash run_coverage.sh CLONE OUT
set -u
CLONE=$1; OUT=$2
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH=$CLONE/src:$CLONE/assistant
export TMPDIR=/home/jwen/projects/RNPBench/scratch_agent/v04/grouping/tmp
PY=/home/jwen/projects/RNPBench/RNPLens_dev_0.3/venv/bin/python
for P in A B; do
  $PY $CLONE/qualification_v04/grouping/coverage.py --pool $P --qual "$OUT" --out "$OUT/coverage_pool$P.json" >> "$OUT/log_coverage.txt" 2>&1
done
date > "$OUT/DONE_COVERAGE"
