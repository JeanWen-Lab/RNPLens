#!/bin/bash
# Frozen replay-requalification workflow (DETERMINISM_CONTRACT_v1.md, section 6). One run of one case.
# usage: bash retest_case.sh CASE_ROOT CASE_ID PREPARED_INPUTS
#   CASE_ROOT        new folder (must not exist); every command runs with CASE_ROOT as working directory
#   PREPARED_INPUTS  folder with run_A/ run_B/ protein.fasta rna.fasta (read only; copied to CASE_ROOT/in)
# env: RNPLENS_PY python that imports the RNPLens checkout under test. No language model is called.
set -u
CASE_ROOT="$1"; CID="$2"; SRC="$3"
: "${RNPLENS_PY:=python}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; REPO="$(cd "$HERE/../../.." && pwd)"; LIB="$REPO/demos/lib"
if [ -e "$CASE_ROOT" ]; then echo "refused: $CASE_ROOT exists" >&2; exit 2; fi
mkdir -p "$CASE_ROOT/logs" && cd "$CASE_ROOT" || exit 2
rnplens() { "$RNPLENS_PY" -m rnplens "$@"; }
py() { "$RNPLENS_PY" "$@"; }
printf 'step\texpected_exit\texit\tcommand\n' > logs/steps.tsv
step() {
  local name="$1" exp="$2"; shift 2
  printf '$ %s\n' "$*" > "logs/$name.log"
  "$@" >> "logs/$name.log" 2>&1
  local rc=$?
  printf '%s\t%s\t%s\t%s\n' "$name" "$exp" "$rc" "$*" >> logs/steps.tsv
  if [ "$rc" != "$exp" ]; then echo "STEP $name: exit $rc, expected $exp" >&2; tail -20 "logs/$name.log" >&2; echo INCOMPLETE > logs/RESULT; exit 1; fi
}
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
step 10_update_after_outputs 0 rnplens update project
step 11_remove_run_C 0 rnplens update project --remove-input in/run_C_other_construct
step 12_versions 0 rnplens update project --versions
step 13_status 0 rnplens update project --status
echo COMPLETE > logs/RESULT
