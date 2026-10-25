#!/bin/bash
# Demonstration 1: RNA-region investigation on development task d2_1VTM_agreement (Boltz-2, two runs x 5 samples).
# usage: bash run.sh OUT_FOLDER        (OUT_FOLDER must not exist)
# env:   RNPLENS_PY  python importing RNPLens 0.4.0.dev0;  SRC_TASK  source task folder (read only, copied)
set -u
DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DEMO_DIR/../lib/common.sh"
SRC_TASK="${SRC_TASK:-/home/jwen/projects/RNPBench/scratch_agent/assistant_dev_tasks/d2_1VTM_agreement}"
start_package "$1"
cp -r "$SRC_TASK/run_A" "$SRC_TASK/run_B" "$SRC_TASK/protein.fasta" "$SRC_TASK/rna.fasta" "$SRC_TASK/task.json" inputs/
step 00_hash_inputs 0 py "$DEMOS_LIB/hash_inputs.py" inputs logs/inputs_sha256.tsv
step 01_import  0 rnplens import inputs/run_A inputs/run_B --protein-seq inputs/protein.fasta --rna-seq inputs/rna.fasta --engine BOLTZ2 --case-id 1VTM_d2 --out project
step 02_analyse 0 rnplens analyse project --out analysis --nproc 4
# region rule fixed in records/v04_integration/DEMOS_PLAN.md before any contact was looked at
step 03_region_rule 0 py "$DEMOS_LIB/region_rule.py" project analysis region_rule.json
RANGE="$(tail -1 logs/03_region_rule.log)"
step 04_region  0 rnplens region project analysis --rna "$RANGE"
step 05_view    0 rnplens view project --analysis analysis --rna "$RANGE"
step 06_explain_structures 0 rnplens explain structures --analysis analysis --project project
step 07_explain_region_mapping 0 rnplens explain region_mapping --region "region_$RANGE" --analysis analysis --project project
step 08_answer  0 py "$DEMOS_LIB/region_answer.py" analysis "region_$RANGE" answer.md answer.json
# every structure that lists a contact differing between runs: rnplens explain contact (first three, region.json order)
for LAB in $(py -c "import json;print(' '.join(d['label'] for d in json.load(open('answer.json'))['differing_contacts'][:3]))"); do
  step "09_explain_contact_$LAB" 0 rnplens explain contact --contact "$LAB" --analysis analysis --project project
done
sed "s/@RANGE@/$RANGE/g" "$DEMO_DIR/README.template.md" > README.md && cat answer.md >> README.md
source "$DEMOS_LIB/finish_package.sh"
mkdir -p checks
step 10_wording_scan 0 py "$DEMOS_LIB/wording_scan.py" . checks/wording_scan.json
echo "demo 1 complete: $OUT (region RNA $RANGE)"
