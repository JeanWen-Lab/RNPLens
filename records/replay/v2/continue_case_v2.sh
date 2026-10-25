#!/bin/bash
# Continuation of DETERMINISM_CONTRACT_v2 (moved-project replay): the same commands run in a completed case root and
# in a copy of it at another absolute path. usage: bash continue_case_v2.sh CASE_ROOT
set -u
CASE_ROOT="$1"
: "${RNPLENS_PY:=python}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; REPO="$(cd "$HERE/../../.." && pwd)"; LIB="$REPO/demos/lib"
cd "$CASE_ROOT" || exit 2
grep -q COMPLETE logs/RESULT || { echo "refused: base run not complete" >&2; exit 2; }
source "$HERE/steps_v2.sh"
read IMP ANA < <(py "$LIB/managed_dirs.py" project)
L="$(py -c "import json; print(json.load(open('region_rule.json'))['rna_length'])")"
step c1_update_no_change 0 rnplens update project
read IMP ANA < <(py "$LIB/managed_dirs.py" project)
step c2_region_whole_rna 0 rnplens region "project/$IMP" "project/$ANA" --rna "1-$L"
step c3_explain_region_mapping 0 rnplens explain region_mapping --region "region_1-$L" --analysis "project/$ANA" --project "project/$IMP"
step c4_export_methods 0 rnplens export-methods "project/$ANA" --project "project/$IMP"
step c5_view_whole_rna 0 rnplens view "project/$IMP" --analysis "project/$ANA" --rna "1-$L"
FIRST="$(py -c "from rnplens import state as S; print(next(v['version'] for v in S.Project('project').versions() if v['status']=='COMPLETE'))")"
HEADV="$(py -c "from rnplens import state as S; print(S.Project('project').head_id())")"
step c6_update_report 0 rnplens update project --report "$FIRST" "$HEADV"
step c7_status 0 rnplens update project --status
echo CONTINUED > logs/RESULT_CONTINUATION
