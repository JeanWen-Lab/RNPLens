#!/bin/bash
# Input preparation of DETERMINISM_CONTRACT_v2: PREPARED/<T>/{run_A,run_B,protein.fasta,rna.fasta}.
# usage: bash prepare_inputs_v2.sh PREPARED_ROOT [cases|classification]   (read-only on every source)
set -eu
OUT="$1"; HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; LIB="$HERE/../../../demos/lib"; : "${RNPLENS_PY:=python}"
TASKS=/home/jwen/projects/RNPBench/scratch_agent/assistant_dev_tasks
PILOT=/home/jwen/projects/PCfold3D-RNP/outputs/rnpbench/pilot
mkdir -p "$OUT"
task() { mkdir "$OUT/$1"; cp -r "$TASKS/$2/run_A" "$TASKS/$2/run_B" "$TASKS/$2/protein.fasta" "$TASKS/$2/rna.fasta" "$OUT/$1/"; }
pilot() {
  mkdir -p "$OUT/$1/run_A" "$OUT/$1/run_B"
  cp "$PILOT/boltz/exec_A/$1/boltz_results_$1/predictions/$1/"{"$1"_model_*.pdb,confidence_"$1"_model_*.json} "$OUT/$1/run_A/"
  cp "$PILOT/boltz/exec_B/$1/boltz_results_$1/predictions/$1/"{"$1"_model_*.pdb,confidence_"$1"_model_*.json} "$OUT/$1/run_B/"
  "$RNPLENS_PY" "$LIB/boltz_yaml_to_fasta.py" "$PILOT/inputs/boltz/$1.yaml" "$OUT/$1"; }
case "${2:-cases}" in
  cases) pilot 2QQP; pilot 2XGJ; pilot 24BR ;;
  classification) task 1VTM d2_1VTM_agreement ;;
esac
( cd "$OUT" && find . -type f | sort | xargs sha256sum ) > "$OUT.sha256"
echo "prepared: $(ls "$OUT")"
