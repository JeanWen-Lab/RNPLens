#!/bin/bash
# Amendment 1: regenerate the six governed viewer pages with the checkout's viewer.py (after the F1 fix) into new
# folders (*_a1), with the same arguments as run 1. The demo projects and analyses are not changed.
# usage: bash regen_a1.sh DEMOS_DIR      env: PY (python), PYTHONPATH (checkout src:assistant)
set -eu
D="$1"
cd "$D/1_region_1VTM";      R="$(tail -n 1 logs/03_region_rule.log)"; "$PY" -m rnplens view project --analysis analysis --rna "$R" --out "analysis/viewer_${R}_a1"
cd "$D/1b_region_subrange"; R="$(tail -n 1 logs/03_region_rule.log)"; "$PY" -m rnplens view project --analysis analysis --rna "$R" --out "analysis/viewer_${R}_a1"
cd "$D/3_grouping_6BJG"
for t in 0.3 0.5 0.7; do
  IDS=$("$PY" -c "import json; d=json.load(open('analysis/groups/groups.json')); print(','.join(g['representative']['id'] for g in d['thresholds']['$t']['groups']))")
  "$PY" -m rnplens view project --analysis analysis --ids "$IDS" --out "analysis/viewer_representatives_t${t}_a1"
done
"$PY" -m rnplens view project --analysis analysis --out analysis/viewer_a1
