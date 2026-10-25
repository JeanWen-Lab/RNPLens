#!/bin/bash
# Demonstration 1b: RNA sub-range investigation on a stress-cohort development target with RNA >= 20 nt
# (target and 10-nt window rules fixed in records/v04_integration/DEMOS_PLAN.md, "Demo 1b").
# usage: bash run.sh OUT_FOLDER        (OUT_FOLDER must not exist)
# env:   RNPLENS_PY;  PILOT  pilot folder (read only);  POOLA  pool A folder (fallback only)
set -u
DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DEMO_DIR/../lib/common.sh"
PILOT="${PILOT:-/home/jwen/projects/PCfold3D-RNP/outputs/rnpbench/pilot}"
POOLA="${POOLA:-/home/jwen/projects/PCfold3D-RNP/outputs/rnp/jpf/nscale}"
start_package "$1"
step 00_select_target 0 py "$DEMOS_LIB/select_target.py" "$PILOT" target_rule.json
T="$(tail -1 logs/00_select_target.log)"
if [ "$T" = "6BJG_PARITY_FALLBACK" ]; then
  # fallback stated in DEMOS_PLAN.md: pool-A 6BJG split into two pseudo-runs by sample index parity
  T=6BJG; RUNS="exec_even exec_odd"; mkdir -p inputs/exec_even inputs/exec_odd
  cp "$POOLA/inputs/6BJG.yaml" inputs/target.yaml
  for f in "$POOLA/boltz_out/boltz_results_6BJG/predictions/6BJG/6BJG_model_"*.pdb; do
    i="$(basename "$f" .pdb)"; i="${i##*_}"; r=exec_even; [ $((i % 2)) = 1 ] && r=exec_odd
    cp "$f" "$POOLA/boltz_out/boltz_results_6BJG/predictions/6BJG/confidence_6BJG_model_$i.json" "inputs/$r/"
  done
else
  RUNS="exec_A exec_B"
  cp "$PILOT/inputs/boltz/$T.yaml" inputs/target.yaml
  for E in exec_A exec_B; do
    mkdir -p "inputs/$E"
    D="$PILOT/boltz/$E/$T/boltz_results_$T/predictions/$T"
    cp "$D/${T}_model_"*.pdb "$D/confidence_${T}_model_"*.json "inputs/$E/"
  done
fi
step 00_sequences 0 py "$DEMOS_LIB/boltz_yaml_to_fasta.py" inputs/target.yaml inputs
step 00_hash_inputs 0 py "$DEMOS_LIB/hash_inputs.py" inputs logs/inputs_sha256.tsv
set -- $RUNS
step 01_import  0 rnplens import "inputs/$1" "inputs/$2" --protein-seq inputs/protein.fasta --rna-seq inputs/rna.fasta --engine BOLTZ2 --case-id "${T}_pilot" --out project
step 02_analyse 0 rnplens analyse project --out analysis --nproc 4
# 10-nt window rule fixed in DEMOS_PLAN.md before any contact was looked at
step 03_region_rule 0 py "$DEMOS_LIB/region_window_rule.py" project analysis region_rule.json
RANGE="$(tail -1 logs/03_region_rule.log)"
step 04_region  0 rnplens region project analysis --rna "$RANGE"
step 05_view    0 rnplens view project --analysis analysis --rna "$RANGE"
step 06_explain_structures 0 rnplens explain structures --analysis analysis --project project
step 07_explain_region_mapping 0 rnplens explain region_mapping --region "region_$RANGE" --analysis analysis --project project
step 08_answer  0 py "$DEMOS_LIB/region_answer.py" analysis "region_$RANGE" answer.md answer.json
# every contact of the region that is not shared by all runs
N=0
for LAB in $(py -c "import json;print(' '.join(d['label'] for d in json.load(open('answer.json'))['differing_contacts']))"); do
  step "09_explain_contact_$LAB" 0 rnplens explain contact --contact "$LAB" --analysis analysis --project project; N=$((N+1))
done
printf '{"target": "%s", "runs": "%s", "region": "%s", "explained_contacts": %d}\n' "$T" "$RUNS" "$RANGE" "$N" > demo_summary.json
sed "s/@RANGE@/$RANGE/g; s/@T@/$T/g; s/@RUNS@/$RUNS/g" "$DEMO_DIR/README.template.md" > README.md && cat answer.md >> README.md
source "$DEMOS_LIB/finish_package.sh"
mkdir -p checks
step 10_wording_scan 0 py "$DEMOS_LIB/wording_scan.py" . checks/wording_scan.json
echo "demo 1b complete: $OUT (target $T, region RNA $RANGE, $N contact(s) explained)"
