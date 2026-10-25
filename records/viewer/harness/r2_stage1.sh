#!/bin/bash
# Viewer track r2, stage 1 (karyon). usage: bash r2_stage1.sh
# 1. demos 1, 1b and 3 at this checkout into $S2/demos_r2 (fresh); 2. the three representative pages of demo 3;
# 3. coverage A on the governed run-2 pages (with Mol*'s state from run 2); 4. coverage B on the fresh pages.
set -u
S1=/home/jwen/projects/RNPBench/scratch_agent/v04/viewer-2
S2=/home/jwen/projects/RNPBench/scratch_agent/v04/viewer-r2
C=/home/jwen/projects/RNPBench/RNPLens_dev_0.4/tracks/viewer-2/RNPLens
H=$C/records/viewer/harness
export RNPLENS_PY=/home/jwen/projects/RNPBench/RNPLens_dev_0.3/venv/bin/python PYTHONPATH=$C/src:$C/assistant TMPDIR=$S2/tmp
PY=$RNPLENS_PY
D=$S2/demos_r2
if [ -e "$D" ]; then echo "refused: $D exists"; exit 2; fi
mkdir -p $D
{ date -u +%FT%TZ; (cd $C && git rev-parse HEAD && git status --porcelain | wc -l); sha256sum $H/*; } > $S2/stage1_start.txt
for d in 1_region_1VTM 1b_region_subrange 3_grouping_6BJG; do
  ( cd $D && bash $C/demos/$d/run.sh $D/$d > $D/$d.out 2>&1; echo "exit=$?" >> $D/$d.out ) &
done
wait
cd $D/3_grouping_6BJG
for t in 0.3 0.5 0.7; do
  IDS=$($PY -c "import json; d=json.load(open('analysis/groups/groups.json')); print(','.join(g['representative']['id'] for g in d['thresholds']['$t']['groups']))")
  $PY -m rnplens view project --analysis analysis --ids "$IDS" --out analysis/viewer_representatives_t$t > logs/view_reps_t$t.log 2>&1
  echo "t=$t exit=$? ids=$IDS" >> $D/reps.log
done
cd $S2
$PY $H/coverage.py $H/pages_r2_governed_run2.json $S2/coverage_A_run2_pages.json > $S2/coverage_A.log 2>&1; echo "exit=$?" >> $S2/coverage_A.log
$PY $H/coverage.py $H/pages_r2_package.json $S2/coverage_B_package_pages.json > $S2/coverage_B.log 2>&1; echo "exit=$?" >> $S2/coverage_B.log
echo DONE > $S2/stage1.DONE
