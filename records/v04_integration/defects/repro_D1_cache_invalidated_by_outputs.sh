#!/bin/bash
# Minimal reproduction, defect D1 (RNPLens 0.4.0.dev0, commit 5caccec): writing any 0.4 output into a managed
# project's current analysis folder (here `rnplens region`) makes the next `rnplens update`, with no input change,
# recompute the analysis (computation RECOMPUTED, key_components_changed []), instead of "reused".
# usage: bash repro_D1_cache_invalidated_by_outputs.sh RNPLENS_SOURCE_CHECKOUT WORKDIR   (WORKDIR must not exist)
set -eu
SRC="$(cd "$1" && pwd)"; mkdir "$2"; cd "$2"
rnplens() { python -m rnplens "$@"; }
E="$SRC/examples"
mkdir in && cp -r "$E/reference_free/report_7K9D/exec_A" "$E/reference_free/report_7K9D/exec_B" in/
rnplens update demo --init in/exec_A in/exec_B --protein-seq "$E/reference_based/7K9D_protein.fasta" --rna-seq "$E/reference_based/7K9D_rna.fasta" --engine BOLTZ2 --case-id x
rnplens update demo                                     # expected and observed: "(reused from v0002)"
read IMP ANA < <(python -c "from rnplens import state; a=state.Project('demo').head()['analyses']['main']; print(a['import_dir'], a['dir'])")
rnplens region "demo/$IMP" "demo/$ANA" --rna 13-23       # writes demo/$ANA/region_13-23/ (and appends to commands.log, if any)
rnplens update demo                                     # observed: a new analyses/vNNNN/main, i.e. recomputed
python - <<'PY'
import json, glob
from rnplens import state
P = state.Project("demo"); h = P.head()
rep = sorted(glob.glob("demo/analyses/v*/update_report.json"))[-1]
a = json.load(open(rep))["analyses"]["main"]
print("last update:", rep, "computation:", a["computation"], "key_components_changed:", a["key_components_changed"],
      "same key:", a["before"]["key"] == a["after"]["key"])
print("DEFECT REPRODUCED" if a["computation"] == "RECOMPUTED" and not a["key_components_changed"] else "not reproduced")
PY
