#!/bin/bash
# Frozen input preparation (DETERMINISM_CONTRACT_v1.md, section 6): PREPARED/<T>/{run_A,run_B,protein.fasta,rna.fasta}
# usage: bash prepare_inputs.sh PREPARED_ROOT        (read-only on every source; never opens references or scores)
set -eu
OUT="$1"; HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; LIB="$HERE/../../../demos/lib"; : "${RNPLENS_PY:=python}"
TASKS=/home/jwen/projects/RNPBench/scratch_agent/assistant_dev_tasks
PILOT=/home/jwen/projects/PCfold3D-RNP/outputs/rnpbench/pilot
mkdir -p "$OUT"
task() {  # development task folder: run_A run_B protein.fasta rna.fasta copied unchanged
  mkdir "$OUT/$1"; cp -r "$TASKS/$2/run_A" "$TASKS/$2/run_B" "$TASKS/$2/protein.fasta" "$TASKS/$2/rna.fasta" "$OUT/$1/"; }
pilot() { # stress-cohort target: Boltz-2 predictions folders of exec_A / exec_B, FASTA from the input YAML
  mkdir -p "$OUT/$1/run_A" "$OUT/$1/run_B"
  cp "$PILOT/boltz/exec_A/$1/boltz_results_$1/predictions/$1/"{"$1"_model_*.pdb,confidence_"$1"_model_*.json} "$OUT/$1/run_A/"
  cp "$PILOT/boltz/exec_B/$1/boltz_results_$1/predictions/$1/"{"$1"_model_*.pdb,confidence_"$1"_model_*.json} "$OUT/$1/run_B/"
  "$RNPLENS_PY" "$LIB/boltz_yaml_to_fasta.py" "$PILOT/inputs/boltz/$1.yaml" "$OUT/$1"; }
case "${2:-cases}" in
  cases) task 1VTM d2_1VTM_agreement; task 7K9D d1_7K9D_agreement; pilot 2JEA; pilot 2Q66 ;;
  smoke) pilot 2QQP ;;
esac
( cd "$OUT" && find . -type f | sort | xargs sha256sum ) > "$OUT.sha256"
echo "prepared: $(ls "$OUT")"
