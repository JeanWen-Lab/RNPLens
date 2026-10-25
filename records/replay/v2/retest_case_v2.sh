#!/bin/bash
# Workflow of DETERMINISM_CONTRACT_v2 (one base run of one case): the v1 lifecycle plus explain evidence, the
# offline viewer, binding-hypothesis grouping, and the SCRIPTED Codex follow-up path (stub client; no model, no
# Codex process), which writes a consent record. No language model is called.
# usage: bash retest_case_v2.sh CASE_ROOT CASE_ID PREPARED_INPUTS      (CASE_ROOT must not exist)
set -u
CASE_ROOT="$1"; CID="$2"; SRC="$3"
: "${RNPLENS_PY:=python}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; REPO="$(cd "$HERE/../../.." && pwd)"; LIB="$REPO/demos/lib"
if [ -e "$CASE_ROOT" ]; then echo "refused: $CASE_ROOT exists" >&2; exit 2; fi
mkdir -p "$CASE_ROOT/logs" && cd "$CASE_ROOT" || exit 2
source "$HERE/steps_v2.sh"
printf 'step\texpected_exit\texit\tcommand\n' > logs/steps.tsv
cp -r "$SRC" in
step 00_truncate 0 py "$LIB/truncate_rna.py" in/run_B in/run_C_other_construct 2
step 01_init 3 rnplens update project --init in/run_A in/run_B in/run_C_other_construct --protein-seq in/protein.fasta --rna-seq in/rna.fasta --engine BOLTZ2 --case-id "${CID}_retest"
step 02_clarify_json 3 rnplens clarify project --json
step 03_answer 0 rnplens clarify project --answer 1 exclude_run --text "run_C is a truncated-RNA copy made for the replay retest"
step 04_update_no_change 0 rnplens update project
read IMP ANA < <(py "$LIB/managed_dirs.py" project)
step 05_region_rule 0 py "$LIB/region_rule.py" "project/$IMP" "project/$ANA" region_rule.json
RANGE="$(tail -1 logs/05_region_rule.log)"
step 06_region 0 rnplens region "project/$IMP" "project/$ANA" --rna "$RANGE"
step 07_export_methods 0 rnplens export-methods "project/$ANA" --project "project/$IMP"
step 08_explain_structures 0 rnplens explain structures --analysis "project/$ANA" --project "project/$IMP"
step 09_menu_C_followup_local 0 rnplens assist --project "project/$IMP" --analysis "project/$ANA" --item C --rna "$RANGE" --runs run_A,run_B --followup local --question "Which contacts in RNA $RANGE are found in only one run, and which structures list them?" --yes
step 10_explain_evidence 0 rnplens explain evidence --id "region_$RANGE/region.json#/contacts/0" --analysis "project/$ANA" --project "project/$IMP"
step 11_view 0 rnplens view "project/$IMP" --analysis "project/$ANA" --rna "$RANGE"
step 12_group 0 rnplens group "project/$IMP" --analysis "project/$ANA"
if py "$LIB/group_pick.py" "project/$ANA/groups/groups.json" > logs/13_group_pick.log 2>&1; then
  read G H < <(tail -1 logs/13_group_pick.log)
  step 13_group_diff 0 rnplens group-diff "project/$ANA" "$G" "$H"
else
  printf '13_group_diff\tskipped\tskipped\tno engine-pick group with a next group\n' >> logs/steps.tsv
fi
step 14_followup_SCRIPTED 0 py "$LIB/followup_scripted.py" "project/$IMP" "project/$ANA" "Which contacts in RNA $RANGE are found in only one run?" "region_$RANGE/region.json#/summary/only_in_run/run_B" followup_scripted.json
step 15_update_after_outputs 0 rnplens update project
step 16_remove_run_C 0 rnplens update project --remove-input in/run_C_other_construct
step 17_versions 0 rnplens update project --versions
step 18_status 0 rnplens update project --status
echo COMPLETE > logs/RESULT
