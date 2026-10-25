#!/bin/bash
# Viewer track r2, stage 2 (karyon). usage: bash r2_stage2.sh OWNER_SCREEN_CHECK_MD
# 1. package + zip; 2. fresh unzip; 3. the frozen driver run_all.sh on the unzipped pages (offline run in a
# network-less namespace; logged run under strace); 4. zip_check.py; 5. coverage C = coverage B with Mol*'s state from
# the unzipped pages. The index.html probe is run separately (see R2_PLAN.md).
set -u
S1=/home/jwen/projects/RNPBench/scratch_agent/v04/viewer-2
S2=/home/jwen/projects/RNPBench/scratch_agent/v04/viewer-r2
C=/home/jwen/projects/RNPBench/RNPLens_dev_0.4/tracks/viewer-2/RNPLens
H=$C/records/viewer/harness
PY=/home/jwen/projects/RNPBench/RNPLens_dev_0.3/venv/bin/python
export TMPDIR=$S2/tmp HOME=$S2/home CHROME=$S1/browsers/chrome-headless-shell/linux-155.0.8059.84/chrome-headless-shell-linux64/chrome-headless-shell PP=$S2/pp PY HARNESS=$H
P=$S2/package; U=$S2/unzip_fresh
for x in $P $U; do if [ -e "$x" ]; then echo "refused: $x exists"; exit 2; fi; done
mkdir -p $P $U $S2/pp; ln -sfn $S1/pp/node_modules $S2/pp/node_modules; cp $H/render.js $H/index_probe.js $S2/pp/
{ date -u +%FT%TZ; (cd $C && git rev-parse HEAD && git status --porcelain | wc -l); sha256sum $H/* $1 $S2/pp/render.js; } > $S2/stage2_start.txt
$PY $H/make_package.py $H/pages_r2_package.json $S2/coverage_B_package_pages.json $P "$(cd $C && git rev-parse HEAD)" "$1" > $S2/package.log 2>&1
cd $U && $PY -m zipfile -e $P/RNPLens_owner_screen_check.zip . && cd $S2
$PY -c "import json; e=json.load(open('$U/RNPLens_owner_screen_check/expected_highlights.json')); print(json.dumps([{'page_id': k, 'package': '$U/RNPLens_owner_screen_check', 'viewer_dir': 'pages/' + k} for k in sorted(e)]))" > $S2/pages_unzipped.json
bash $H/run_all.sh $S2/pages_unzipped.json $S2/results_zip > $S2/run_zip.log 2>&1
$PY $H/zip_check.py $U/RNPLens_owner_screen_check $S2/results_zip $S2/zip_check.json > $S2/zip_check.log 2>&1
$PY -c "
import json
pg=json.load(open('$H/pages_r2_package.json'))
sh={'demo1_1VTM_rna1-3':'1_1VTM_RNA_1-3','demo1b_2JEA_rna26-35':'1b_2JEA_RNA_26-35','demo3_6BJG_reps_t0.3':'3_6BJG_representatives_t0.3','demo3_6BJG_reps_t0.5':'3_6BJG_representatives_t0.5','demo3_6BJG_reps_t0.7':'3_6BJG_representatives_t0.7','demo3_6BJG_all50':'3_6BJG_all_50'}
for p in pg: p['molstar_result']='$S2/results_zip/'+sh[p['page_id']]+'/result_offline.json'
json.dump(pg, open('$S2/pages_coverage_C.json','w'))"
$PY $H/coverage.py $S2/pages_coverage_C.json $S2/coverage_C_package_pages_molstar.json > $S2/coverage_C.log 2>&1
echo DONE > $S2/stage2.DONE
