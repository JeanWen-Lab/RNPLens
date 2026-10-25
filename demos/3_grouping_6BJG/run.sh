#!/bin/bash
# Demonstration 3: binding-hypothesis interpretation, pool A target 6BJG (Boltz-2, 50 samples). No DockQ label is read.
# usage: bash run.sh OUT_FOLDER        (OUT_FOLDER must not exist)
# env:   RNPLENS_PY;  POOLA  pool A folder (read only)
set -u
DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DEMO_DIR/../lib/common.sh"
POOLA="${POOLA:-/home/jwen/projects/PCfold3D-RNP/outputs/rnp/jpf/nscale}"
T=6BJG                               # target rule fixed in records/v04_integration/DEMOS_PLAN.md
start_package "$1"
mkdir -p inputs/boltz_out
# the only source files read: the Boltz input YAML and the 50 structures with their confidence files
cp "$POOLA/inputs/$T.yaml" inputs/
cp "$POOLA/boltz_out/boltz_results_$T/predictions/$T/${T}_model_"*.pdb inputs/boltz_out/
cp "$POOLA/boltz_out/boltz_results_$T/predictions/$T/confidence_${T}_model_"*.json inputs/boltz_out/
step 00_sequences 0 py "$DEMOS_LIB/boltz_yaml_to_fasta.py" "inputs/$T.yaml" inputs
step 00_hash_inputs 0 py "$DEMOS_LIB/hash_inputs.py" inputs logs/inputs_sha256.tsv
N="$(ls inputs/boltz_out/${T}_model_*.pdb | wc -l | tr -d ' ')"
step 01_import 0 rnplens import inputs/boltz_out --protein-seq inputs/protein.fasta --rna-seq inputs/rna.fasta --engine BOLTZ2 --case-id "$T" --out project
step 02_analyse 0 rnplens analyse project --out analysis --nproc 8
step 03_group 0 rnplens group project --analysis analysis
step 04_pick 0 py "$DEMOS_LIB/group_pick.py" analysis/groups/groups.json
read G H < <(tail -1 logs/04_pick.log)
step 05_group_diff 0 rnplens group-diff analysis "$G" "$H"
step 06_view 0 rnplens view project --analysis analysis
step 07_retention_check 0 py "$DEMOS_LIB/retention_check.py" project analysis/groups/groups.json "$N" retention_check.json
step 08_docs_parity 0 py "$DEMO_DIR/docs_parity.py" analysis "$G" "$H" docs_parity.json
sed "s/@G@/$G/g; s/@H@/$H/g; s/@N@/$N/g" "$DEMO_DIR/README.template.md" > README.md
step 09_results_section 0 py "$DEMO_DIR/results_section.py" analysis "$G" "$H" results.md
cat results.md >> README.md
source "$DEMOS_LIB/finish_package.sh"
mkdir -p checks
step 10_wording_scan 0 py "$DEMOS_LIB/wording_scan.py" . checks/wording_scan.json
echo "demo 3 complete: $OUT (groups $G and $H compared)"
