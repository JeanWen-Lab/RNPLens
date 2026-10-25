#!/bin/bash
# Pre-registered run of the nucleotide contact explorer checks (PREREG_NT_CONTACTS.md). Writes only under OUT.
# usage: bash run_nt.sh CLONE OUT PY CHROME PP BASE_DEMOS BASE_CHECKOUT      (OUT must not exist)
set -u
C="$1"; OUT="$2"; PY="$3"; CHROME="$4"; PP="$5"; BASE="$6"; QA="$7"
H="$C/records/viewer/nt_contacts"
[ -e "$OUT" ] && { echo "OUT exists: $OUT"; exit 2; }
mkdir -p "$OUT"/{demos,browser,checks,eval} && cd "$OUT"
export PYTHONDONTWRITEBYTECODE=1 RNPLENS_PY="$PY" PYTHONPATH="$C/src:$C/assistant" HOME="$OUT/home" TMPDIR="$OUT/tmp"; mkdir -p "$HOME" "$TMPDIR"
git -C "$C" rev-parse HEAD > source_head.txt; git -C "$C" status --short > source_status.txt
{ echo "chrome: $("$CHROME" --version 2>/dev/null)"; echo "node: $(node --version)"; echo "bwrap: $(bwrap --version)";
  echo "strace: $(strace -V | head -n 1)"; "$PY" -c "import gemmi, Bio, numpy; print('gemmi', gemmi.__version__, 'biopython', Bio.__version__, 'numpy', numpy.__version__)"; uname -a; } > environment.txt 2>&1
step() { local name="$1"; shift; "$@" > "logs_$name.txt" 2>&1; echo -e "$name\t$?" >> steps.tsv; }
# 1. demonstrations at the feature commit (same scripts and inputs as out/base_de66a96)
for d in 1_region_1VTM 1b_region_subrange 3_grouping_6BJG; do
  ( bash "$C/demos/$d/run.sh" "$OUT/demos/$d" > "demos/$d.out" 2>&1; echo "exit=$?" >> "demos/$d.out" ) &
done
wait
for d in 1_region_1VTM 1b_region_subrange 3_grouping_6BJG; do echo -e "demo_$d\t$(tail -n 1 demos/$d.out)" >> steps.tsv; done
( cd demos/3_grouping_6BJG && "$PY" -m rnplens view project --analysis analysis --representatives 0.5 ) > logs_view_6BJG_t05.txt 2>&1; echo -e "view_6BJG_t0.5\t$?" >> steps.tsv
J=demos/1b_region_subrange; V=demos/1_region_1VTM; G=demos/3_grouping_6BJG
# 2. Report outputs and existing page highlights, base vs feature
step compare_report "$PY" "$H/compare_outputs.py" checks/compare_report.json "$BASE" "$OUT/demos" \
  1_region_1VTM/analysis/report/contacts_by_output.json 1_region_1VTM/analysis/report/result.json \
  1b_region_subrange/analysis/report/contacts_by_output.json 1b_region_subrange/analysis/report/result.json \
  3_grouping_6BJG/analysis/report/contacts_by_output.json 3_grouping_6BJG/analysis/report/result.json \
  1_region_1VTM/analysis/viewer_1-3/viewer_manifest.json 1b_region_subrange/analysis/viewer_26-35/viewer_manifest.json \
  3_grouping_6BJG/analysis/viewer/viewer_manifest.json
# 3. Evaluate (bundled 7K9D example with reference), base checkout vs feature commit
EX="$C/examples"; RF="$EX/reference_free/report_7K9D"
for side in base feature; do
  if [ "$side" = base ]; then SRC="$QA"; else SRC="$C"; fi
  ( cd eval && mkdir -p "$side" && cd "$side" && PYTHONPATH="$SRC/src:$SRC/assistant" "$PY" -m rnplens import "$RF/exec_A" "$RF/exec_B" \
      --protein-seq "$EX/reference_based/7K9D_protein.fasta" --rna-seq "$EX/reference_based/7K9D_rna.fasta" --engine BOLTZ2 --case-id 7K9D_example --out p \
    && PYTHONPATH="$SRC/src:$SRC/assistant" "$PY" -m rnplens analyse p --out a --reference "$EX/reference_based/7K9D_reference.cif" ) > "logs_eval_$side.txt" 2>&1
  echo -e "eval_$side\t$?" >> steps.tsv
done
step compare_evaluate "$PY" "$H/compare_outputs.py" checks/compare_evaluate.json "$OUT/eval/base/a" "$OUT/eval/feature/a" \
  evaluate/s001/result.json evaluate/s001/result.csv evaluate/s001/summary.txt evaluate/s002/result.json evaluate/s002/result.csv \
  evaluate/s002/summary.txt report/contacts_by_output.json report/result.json
# 4. distance and correspondence parity (gemmi)
step parity "$PY" "$H/parity_check.py" checks/parity.json \
  "$J/analysis/viewer_26-35,$J/analysis,$J/project" "$V/analysis/viewer_1-3,$V/analysis,$V/project" \
  "$G/analysis/viewer,$G/analysis,$G/project" "$G/analysis/viewer_representatives_t0.5,$G/analysis,$G/project"
# 5. browser plans, offline; 2JEA repeated under strace
ln -sfn "$PP/node_modules" browser/node_modules; cp "$H/browser_nt.js" browser/
step plan_2JEA "$PY" "$H/make_plans.py" 2JEA "$J/analysis/viewer_26-35" "$J/project" "$J/analysis" browser/plan_2JEA.json
step plan_1VTM "$PY" "$H/make_plans.py" 1VTM "$V/analysis/viewer_1-3" "$V/project" "$V/analysis" browser/plan_1VTM.json
step plan_6BJG "$PY" "$H/make_plans.py" 6BJG_t0.5 "$G/analysis/viewer_representatives_t0.5" "$G/project" "$G/analysis" browser/plan_6BJG.json
for t in 2JEA 1VTM 6BJG; do
  ( cd browser && timeout 1500 bwrap --unshare-net --dev-bind / / --proc /proc -- node browser_nt.js "$CHROME" "plan_$t.json" "run_$t" ) > "logs_browser_$t.txt" 2>&1
  echo -e "browser_$t\t$?" >> steps.tsv
done
( cd browser && sed 's/"tag": "2JEA"/"tag": "2JEA_strace"/' plan_2JEA.json > plan_2JEA_strace.json && \
  timeout 1500 strace -f -e trace=connect,sendto -o ../checks/strace_2JEA.txt bwrap --unshare-net --dev-bind / / --proc /proc -- node browser_nt.js "$CHROME" plan_2JEA_strace.json run_2JEA_strace ) > logs_browser_2JEA_strace.txt 2>&1
echo -e "browser_2JEA_strace\t$?" >> steps.tsv
{ echo "connect_lines $(grep -c 'connect(' checks/strace_2JEA.txt)"; echo "inet_connect $(grep 'connect(' checks/strace_2JEA.txt | grep -c -E 'AF_INET6?[,}]')";
  echo "unix_connect $(grep 'connect(' checks/strace_2JEA.txt | grep -c AF_UNIX)"; } > checks/strace_summary.txt
# 6. checks against Report's records
step check_2JEA "$PY" "$H/check_nt.py" browser/plan_2JEA.json browser/run_2JEA/result_2JEA.json "$J/analysis/viewer_26-35" "$J/project" "$J/analysis" checks/check_2JEA.json
step check_2JEA_strace "$PY" "$H/check_nt.py" browser/plan_2JEA_strace.json browser/run_2JEA_strace/result_2JEA_strace.json "$J/analysis/viewer_26-35" "$J/project" "$J/analysis" checks/check_2JEA_strace.json
step check_1VTM "$PY" "$H/check_nt.py" browser/plan_1VTM.json browser/run_1VTM/result_1VTM.json "$V/analysis/viewer_1-3" "$V/project" "$V/analysis" checks/check_1VTM.json
step check_6BJG "$PY" "$H/check_nt.py" browser/plan_6BJG.json browser/run_6BJG/result_6BJG_t05.json "$G/analysis/viewer_representatives_t0.5" "$G/project" "$G/analysis" checks/check_6BJG.json
step doctor "$PY" -m rnplens doctor
echo DONE > DONE
