#!/bin/bash
# Clean installs of RNPLens 0.4.0.dev0 and rnplens-assistant on Linux (karyon), from a fresh clone at a fixed commit.
# Builds wheel and sdist of both packages, installs each format into its own fresh venv, and verifies everything from
# the installed packages only (PYTHONPATH unset, working directory outside the source tree).
# KINDS="wheel sdist docs" (env) adds a third venv installed exactly as docs/installation.md says
# (python -m pip install "<clone>[html,test]", then python -m pip install ./assistant), checking first that
# `rnplens assist --followup local` without the assistant package exits 3.
# usage: bash clean_install_linux.sh [ROOT]      default ROOT: $RNPBENCH/scratch_agent/v04/clean_install_<utc>
# Every command, its exit code and its output are recorded in ROOT/results.tsv and ROOT/logs/.
set -u
RNPBENCH="${RNPBENCH:-/home/jwen/projects/RNPBench}"
PY311="${PY311:-/home/jwen/miniforge3/envs/pcfold3d-rnp/bin/python}"
SRCREPO="${SRCREPO:-$RNPBENCH/RNPLens_dev_0.4/RNPLens}"
COMMIT="${COMMIT:-5caccec}"
P1WORK="${P1WORK:-$RNPBENCH/scratch_agent/v04/followup/p1_karyon/work}"
D="${1:-$RNPBENCH/scratch_agent/v04/clean_install_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$D/logs" "$D/tmp" && cd "$D" || exit 2
unset PYTHONPATH RNPLENS_CODEX_JAIL
ORIG_PATH="$PATH"
export TMPDIR="$D/tmp" PIP_DISABLE_PIP_VERSION_CHECK=1 MPLBACKEND=Agg
printf 'step\texit\tcwd\tcommand\n' > "$D/results.tsv"
run() {   # run NAME CMD...  (records; never stops)
  local name="$1"; shift
  { printf '$ %s\n' "$*"; } > "$D/logs/$name.log"
  "$@" >> "$D/logs/$name.log" 2>&1
  local rc=$?
  printf '%s\t%s\t%s\t%s\n' "$name" "$rc" "$PWD" "$*" >> "$D/results.tsv"
  return $rc
}
# ---------------------------------------------------------------- 1. fresh clone and builds
run 01_clone git clone -q "$SRCREPO" "$D/src"
run 02_checkout git -C "$D/src" checkout -q "$COMMIT"
run 03_head git -C "$D/src" log -1 --format='%H %s'
run 04_status git -C "$D/src" status --porcelain
run 05_venv_build "$PY311" -m venv "$D/venv_build"
run 06_pip_build "$D/venv_build/bin/pip" install -q build
run 07_build_toolkit "$D/venv_build/bin/python" -m build --outdir "$D/dist" "$D/src"
run 08_build_assistant "$D/venv_build/bin/python" -m build --outdir "$D/dist" "$D/src/assistant"
run 09_dist_list ls -l "$D/dist"
run 10_dist_sha256 sha256sum "$D"/dist/*
WHL_T=$(ls "$D"/dist/rnplens-*.whl | head -1); SD_T=$(ls "$D"/dist/rnplens-*.tar.gz | head -1)
WHL_A=$(ls "$D"/dist/rnplens_assistant-*.whl | head -1); SD_A=$(ls "$D"/dist/rnplens_assistant-*.tar.gz | head -1)
run 11_wheel_contents_molstar_jail python3 -c "import zipfile,sys; [print(n) for w in sys.argv[1:] for n in zipfile.ZipFile(w).namelist() if 'molstar' in n or n.endswith('.sh') or 'registry.json' in n]" "$WHL_T" "$WHL_A"
run 12_sdist_contents_counts python3 -c "import tarfile,sys; [print(s, len(tarfile.open(s).getnames()), sum(1 for n in tarfile.open(s).getnames() if 'molstar' in n or n.endswith('codex_jail.sh'))) for s in sys.argv[1:]]" "$SD_T" "$SD_A"
# ---------------------------------------------------------------- 2. per format: install and verify
for KIND in ${KINDS:-wheel sdist}; do
  if [ "$KIND" = wheel ]; then T="$WHL_T"; A="$WHL_A"; elif [ "$KIND" = sdist ]; then T="$SD_T"; A="$SD_A"; fi
  V="$D/venv_$KIND"; W="$D/work_$KIND"
  cd "$D"
  run "20_${KIND}_venv" "$PY311" -m venv "$V"
  if [ "$KIND" = docs ]; then
    # docs/installation.md: toolkit from the source folder, then (optional) the assistant package from ./assistant
    run "21_${KIND}_install_toolkit" bash -c "cd '$D/src' && '$V/bin/python' -m pip install -q '.[html,test]'"
    mkdir -p "$W/noasst" && cd "$W/noasst" && export PATH="$V/bin:$ORIG_PATH" && hash -r
    mkdir -p ex && cp -r "$D/src/examples/reference_free/report_7K9D/exec_A" "$D/src/examples/reference_free/report_7K9D/exec_B" ex/ \
      && cp "$D/src/examples/reference_based/7K9D_protein.fasta" "$D/src/examples/reference_based/7K9D_rna.fasta" ex/
    run "21_${KIND}_noasst_import" rnplens import ex/exec_A ex/exec_B --protein-seq ex/7K9D_protein.fasta --rna-seq ex/7K9D_rna.fasta --engine BOLTZ2 --case-id 7K9D_example --out p
    run "21_${KIND}_noasst_analyse" rnplens analyse p --out a
    run "21_${KIND}_noasst_followup_expect_exit3" rnplens assist --project p --analysis a --item C --rna 13-23 --runs exec_A,exec_B --followup local --yes
    run "21_${KIND}_install_assistant" bash -c "cd '$D/src' && '$V/bin/python' -m pip install -q ./assistant"
    cd "$D"
  else
    run "21_${KIND}_install" "$V/bin/pip" install -q "rnplens[html,test] @ file://$T" "rnplens-assistant @ file://$A"
  fi
  run "22_${KIND}_pip_freeze" "$V/bin/pip" freeze
  mkdir -p "$W" && cd "$W" || continue
  export PATH="$V/bin:$ORIG_PATH"     # venv first; the rest (incl. any Codex CLI) unchanged
  hash -r
  run "23_${KIND}_which" bash -c 'command -v python rnplens; python -c "import sys, rnplens, rnplens_assistant; print(sys.prefix); print(rnplens.__version__, rnplens.__file__); print(rnplens_assistant.__file__); assert \"site-packages\" in rnplens.__file__ and \"site-packages\" in rnplens_assistant.__file__; assert rnplens.__version__ == \"0.4.0.dev0\""'
  run "24_${KIND}_version" rnplens --version
  run "25_${KIND}_selftest" rnplens selftest
  run "26_${KIND}_doctor" rnplens doctor
  run "27_${KIND}_doctor_json" rnplens doctor --json
  run "28_${KIND}_molstar_hashes" python - <<'PY'
import hashlib, json, os, rnplens
d = os.path.join(os.path.dirname(rnplens.__file__), "vendor", "molstar")
v = json.load(open(os.path.join(d, "VERSION.json")))
ok = True
for f, m in sorted(v["files"].items()):
    p = os.path.join(d, f)
    h = hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None
    good = h == m["sha256"] and os.path.getsize(p) == m["bytes"]
    ok &= good
    print("%-12s %s %s bytes=%s %s" % (f, h, "MATCH" if good else "MISMATCH", os.path.getsize(p) if h else None, p))
print("Mol* version", v["version"], "ALL MATCH" if ok else "MISMATCH")
raise SystemExit(0 if ok else 1)
PY
  # bundled 7K9D example, copied from the source tree
  mkdir -p ex && cp -r "$D/src/examples/reference_free/report_7K9D/exec_A" "$D/src/examples/reference_free/report_7K9D/exec_B" ex/ \
    && cp "$D/src/examples/reference_based/7K9D_protein.fasta" "$D/src/examples/reference_based/7K9D_rna.fasta" ex/
  run "30_${KIND}_import" rnplens import ex/exec_A ex/exec_B --protein-seq ex/7K9D_protein.fasta --rna-seq ex/7K9D_rna.fasta --engine BOLTZ2 --case-id 7K9D_example --out p
  run "31_${KIND}_analyse" rnplens analyse p --out a
  run "32_${KIND}_doctor_agent" rnplens doctor --agent --project p
  run "33_${KIND}_doctor_agent_json" rnplens doctor --agent --project p --json
  run "34_${KIND}_assist_list" rnplens assist --project p --analysis a --list
  run "35_${KIND}_assist_A" rnplens assist --project p --analysis a --item A --json
  run "35_${KIND}_assist_B" rnplens assist --project p --analysis a --item B --rna 13-23 --json
  run "35_${KIND}_assist_C" rnplens assist --project p --analysis a --item C --rna 13-23 --runs exec_A,exec_B --json
  run "35_${KIND}_assist_D" rnplens assist --project p --analysis a --item D --evidence 'region_13-23/region.json#/contacts/0' --json
  run "35_${KIND}_assist_E" rnplens assist --project p --analysis a --item E --json
  run "35_${KIND}_assist_F" rnplens assist --project p --analysis a --item F --json
  run "36_${KIND}_view" rnplens view p --analysis a --rna 13-23
  run "36_${KIND}_view_all" rnplens view p --analysis a
  run "37_${KIND}_region" rnplens region p a --rna 40-60
  run "38_${KIND}_region_docs_numbers" python - <<'PY'
import json
r = json.load(open("a/region_13-23/region.json"))["summary"]
obs = (r["n_contacts_in_range"]["count"], r["shared_by_all_runs"]["count"], r["only_in_run"]["exec_A"]["contacts"], r["only_in_run"]["exec_B"]["contacts"])
exp = (36, 32, ["R18-A21"], ["R16-U14", "D39-U15", "R45-U15"])          # docs/region.md worked example
print("observed", obs); print("documented", exp); raise SystemExit(0 if obs == exp else 1)
PY
  run "39_${KIND}_group_out" rnplens group p --out grp
  run "39_${KIND}_group_equal_menu" python - <<'PY'
import json
a = json.load(open("a/groups/groups.json")); b = json.load(open("grp/groups/groups.json"))
f = lambda g: {t: [(x["members"], x["representative"]["id"]) for x in T["groups"]] for t, T in g["thresholds"].items()}
print("menu E (Report records):", f(a)); print("group --out (Report routine):", f(b)); raise SystemExit(0 if f(a) == f(b) else 1)
PY
  run "40_${KIND}_export_methods" rnplens export-methods a --project p --out methods_cli
  # managed project and an added run (docs/project_state.md)
  mkdir -p ex/exec_C && cp ex/exec_B/7K9D_model_0.pdb ex/exec_C/7K9D_model_1.pdb
  run "41_${KIND}_update_init" rnplens update m --init ex/exec_A ex/exec_B --protein-seq ex/7K9D_protein.fasta --rna-seq ex/7K9D_rna.fasta --engine BOLTZ2 --case-id 7K9D_example
  run "42_${KIND}_update_add_run" rnplens update m ex/exec_C
  run "43_${KIND}_update_versions" rnplens update m --versions
  run "44_${KIND}_update_report_check" python - <<'PY'
import glob, json
rep = json.load(open(sorted(glob.glob("m/analyses/v*/update_report.json"))[-1]))
print(json.dumps(rep["analyses"], indent=1)[:800]); print(json.dumps(rep.get("i_candidate_composition"), indent=1)[:800])
PY
  # LLM-free replay of a saved follow-up plan from FOLLOWUP_SUITE_v1 Part 1 (copied; the source is read only)
  FIRST=$(ls -d "$P1WORK"/P1-*/ 2>/dev/null | while read x; do [ -f "$x/a/followup/fu_0001/followup_plan.json" ] && echo "$x" && break; done)
  if [ -n "$FIRST" ]; then
    mkdir -p p1 && cp -r "$FIRST/p" "$FIRST/a" p1/ && echo "$FIRST" > p1/SOURCE.txt
    run "45_${KIND}_replay_followup" python -m rnplens_assistant replay-followup p1/a/followup/fu_0001/followup_plan.json --project p1/p --analysis p1/a
  fi
  # LLM-free follow-up from the installed packages, and its replay
  run "46_${KIND}_assist_followup_local" rnplens assist --project p --analysis a --item C --rna 13-23 --runs exec_A,exec_B --followup local --yes
  FU=$(ls -d a/followup/fu_*/followup_plan.json 2>/dev/null | tail -1)
  run "47_${KIND}_replay_own_followup" python -m rnplens_assistant replay-followup "$FU" --project p --analysis a
  # full test suite against the installed packages: tests from the clone, PYTHONPATH unset, cwd outside the source tree
  find "$D/src/src" "$D/src/assistant/rnplens_assistant" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
  run "50_${KIND}_pytest" python -m pytest -q "$D/src/tests" "$D/src/assistant/tests" -p no:cacheprovider --basetemp="$D/pytest_$KIND" -rfs
  run "51_${KIND}_source_not_imported" bash -c "n=\$(find '$D/src/src' '$D/src/assistant/rnplens_assistant' -name '*.pyc' | wc -l); echo \"pyc files under the source tree after pytest: \$n\"; [ \"\$n\" = 0 ]"
  export PATH="$ORIG_PATH"
done
cd "$D"
# defect D1 reproduction, run with the installed wheel (examples from the clone; writes only under $D/d1_repro)
if [ -n "${D1_REPRO:-}" ] && [ -x "$D/venv_wheel/bin/python" ]; then
  export PATH="$D/venv_wheel/bin:$ORIG_PATH"; hash -r
  run 60_D1_repro bash "$D1_REPRO" "$D/src" "$D/d1_repro"
  export PATH="$ORIG_PATH"
fi
run 99_summary cut -f1,2 "$D/results.tsv"
echo DONE > "$D/DONE"
