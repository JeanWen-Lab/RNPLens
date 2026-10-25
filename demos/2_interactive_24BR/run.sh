#!/bin/bash
# Demonstration 2: interactive analysis with an ambiguous input (development task d4_24BR_compare, reference unused).
# usage: bash run.sh OUT_FOLDER        (OUT_FOLDER must not exist)
# env:   RNPLENS_PY  python importing RNPLens 0.4.0.dev0 (and rnplens_assistant);  SRC_TASK  source task (read only)
set -u
DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DEMO_DIR/../lib/common.sh"
SRC_TASK="${SRC_TASK:-/home/jwen/projects/RNPBench/scratch_agent/assistant_dev_tasks/d4_24BR_compare}"
start_package "$1"
mkdir -p inputs/in
cp -r "$SRC_TASK/run_A" "$SRC_TASK/run_B" inputs/in/ && cp "$SRC_TASK/protein.fasta" "$SRC_TASK/rna.fasta" inputs/   # reference.cif is not copied
step 00_make_ambiguous_input 0 py "$DEMOS_LIB/truncate_rna.py" inputs/in/run_B inputs/in/run_C_other_construct 2
step 00_hash_inputs 0 py "$DEMOS_LIB/hash_inputs.py" inputs logs/inputs_sha256.tsv
# 1. managed project: the third folder is from another construct -> a typed clarification request (exit 3)
step 01_update_init 3 rnplens update demo --init inputs/in/run_A inputs/in/run_B inputs/in/run_C_other_construct --protein-seq inputs/protein.fasta --rna-seq inputs/rna.fasta --engine BOLTZ2 --case-id 24BR_d4
step 02_clarify_list 3 rnplens clarify demo
step 03_clarify_json 3 rnplens clarify demo --json
# 2. the researcher's answer (fixed in DEMOS_PLAN.md), recorded with their words; the pipeline resumes to completion
step 04_clarify_answer 0 rnplens clarify demo --answer 1 exclude_run --text "run_C was copied in from a truncated-RNA construct by mistake"
# 3. a contradicting answer to the same question (full question id) is refused (exit 2); the recorded answer stands
QID="$(py -c "from rnplens import state; print(sorted(state.Project('demo').decisions())[0])")"
step 05_clarify_contradiction 2 rnplens clarify demo --answer "$QID" use_as_reference_set
step 06_clarify_history 0 rnplens clarify demo --history
step 07_status 0 rnplens update demo --status
step 07b_update_no_change 0 rnplens update demo        # nothing changed: expected "reused", nothing asked again
read IMP ANA < <(py "$DEMOS_LIB/managed_dirs.py" demo)
P="demo/$IMP"; A="demo/$ANA"
printf '{"project": "%s", "analysis": "%s"}\n' "$P" "$A" > managed_dirs.json
# 4. region (rule of demo 1, applied to this project's designated structures), Methods export, one explained value
step 08_region_rule 0 py "$DEMOS_LIB/region_rule.py" "$P" "$A" region_rule.json
RANGE="$(tail -1 logs/08_region_rule.log)"
step 09_region 0 rnplens region "$P" "$A" --rna "$RANGE"
step 10_export_methods 0 rnplens export-methods "$A" --project "$P"
step 11_explain_value 0 rnplens explain evidence --id "region_$RANGE/region.json#/contacts/0" --analysis "$A" --project "$P"
# 5. menu item C with a local (deterministic, no model) follow-up, confirmed with --yes
Q="Which contacts in RNA $RANGE are found in only one run, and which structures list them?"
step 12_menu_C_followup_local 0 rnplens assist --project "$P" --analysis "$A" --item C --rna "$RANGE" --runs run_A,run_B --followup local --question "$Q" --yes
# 6. SCRIPTED demonstration of the Codex follow-up path (no model, no Codex process; see followup_scripted.py)
step 13_followup_SCRIPTED 0 py "$DEMOS_LIB/followup_scripted.py" "$P" "$A" "$Q" "region_$RANGE/region.json#/summary/only_in_run/run_B" followup_scripted.json
# 7. replay of every saved follow-up plan without any language model
for PLAN in $(cd "$A" && ls -d followup/fu_*/followup_plan.json 2>/dev/null); do
  step "14_replay_$(basename "$(dirname "$PLAN")")" 0 py -m rnplens_assistant replay-followup "$A/$PLAN" --project "$P" --analysis "$A"
done
# 8. no input change, but 0.4 outputs now sit in the analysis folder: shows defect D1 (recomputed, key unchanged)
step 15_update_after_outputs 0 rnplens update demo
read IMP2 ANA2 < <(py "$DEMOS_LIB/managed_dirs.py" demo)
printf '{"analysis_before": "%s", "analysis_after": "%s", "reused": %s}\n' "$ANA" "$ANA2" "$([ "$ANA" = "$ANA2" ] && echo true || echo false)" > update_after_outputs.json
step 16_versions 0 rnplens update demo --versions
step 16b_results_section 0 py "$DEMOS_LIB/interactive_summary.py" results.md
sed "s/@RANGE@/$RANGE/g; s#@P@#$P#g; s#@A@#$A#g" "$DEMO_DIR/README.template.md" > README.md && cat results.md >> README.md
source "$DEMOS_LIB/finish_package.sh"
mkdir -p checks
step 17_wording_scan 0 py "$DEMOS_LIB/wording_scan.py" . checks/wording_scan.json
echo "demo 2 complete: $OUT (region RNA $RANGE; project $P; analysis $A)"
