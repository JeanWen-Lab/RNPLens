# Demonstration 1b: RNA sub-range investigation (stress-cohort development target @T@, two Boltz-2 runs)

**What the researcher asks.** "Which protein residues contact this 10-nt stretch of my RNA, and which exact contacts
differ between my two prediction runs?"

**Why this demonstration exists.** In demonstrations 1 and 2 the fixed region rule selected the whole RNA (3 nt
and 4 nt). Here the RNA is at least 20 nt long, so the region is a proper sub-range of real data.

**Rules fixed in advance** (`records/v04_integration/DEMOS_PLAN.md`, "Demo 1b"; committed before any sequence or
contact of these targets was read):
- *Target*: the first of 1VTM, 24BR, 2JEA, 2Q66, 2QQP, 2XGJ whose pilot Boltz input declares one protein and one
  RNA of at least 20 nt, with 5 structures and 5 confidence files in each of exec_A and exec_B. The selection is
  `target_rule.json` (every target examined, with the reason). Selected: **@T@** (runs @RUNS@).
- *Region*: the 10-nt window with the most distinct contacts in the union of the engine-designated structures'
  Report contact lists; ties go to the lowest start. `region_rule.json` holds the count for every window. Region:
  **RNA @RANGE@**.

**Data read.** Only `pilot/inputs/boltz/<T>.yaml` for the targets examined in order, and the selected target's
`pilot/boltz/exec_A|exec_B/@T@/boltz_results_@T@/predictions/@T@/` (`*_model_*.pdb`, `confidence_*.json`). These
are copied into `inputs/` and hashed. The whole package run was traced (`checks/access_audit.json`). No reference
structure, score or DockQ file was opened.

## Commands (run from this folder; `rnplens` = `python -m rnplens` of RNPLens 0.4.0.dev0)

```
python scripts/lib/select_target.py <pilot> target_rule.json                       # -> @T@
python scripts/lib/boltz_yaml_to_fasta.py inputs/target.yaml inputs
rnplens import inputs/exec_A inputs/exec_B --protein-seq inputs/protein.fasta --rna-seq inputs/rna.fasta --engine BOLTZ2 --case-id @T@_pilot --out project
rnplens analyse project --out analysis --nproc 4
python scripts/lib/region_window_rule.py project analysis region_rule.json      # -> @RANGE@
rnplens region project analysis --rna @RANGE@                                     # both runs
rnplens view project --analysis analysis --rna @RANGE@
rnplens explain structures --analysis analysis --project project
rnplens explain region_mapping --region region_@RANGE@ --analysis analysis --project project
python scripts/lib/region_answer.py analysis region_@RANGE@ answer.md answer.json
rnplens explain contact --contact <label> --analysis analysis --project project   # every contact not shared by both runs
```

`logs/steps.tsv` lists every command with its expected and actual exit code. `bash replay.sh` re-runs everything
into a new folder and compares every result JSON.

## Outputs

| file | what it is |
|---|---|
| `analysis/region_@RANGE@/region.json`, `.tsv`, `.html`, `region_map.png` | the regional result, contact table, page and contact map (region outlined) |
| `analysis/viewer_@RANGE@/viewer.html` | offline Mol* page; each structure's Report contacts in RNA @RANGE@ highlighted |
| `analysis/explain/explain_contact_*.txt/.json` | for every contact that differs between runs: the structures, runs, samples and designation behind it |
| `analysis/explain/explain_structures_*`, `explain_region_mapping_*` | included structures; how the region was mapped (numbering, coverage) |
| `answer.md`, `answer.json` | the template answer below, built only from `region.json`, every value with its evidence ID |
| `target_rule.json`, `region_rule.json` | the two fixed rules as applied |
| `checks/` | wording scan, replay check, post-hoc replay classification, data-access audit |

## What these outputs do NOT mean
- A contact that recurs among the 10 predictions is not evidence that it exists in the real complex. Samples of
  one model and one run are not independent.
- "Found only in one run" is a listing with counts. It is not a measure of how similar the runs are, and it does
  not say which run is right. No run, structure or contact is ranked or recommended.
- The window is a presentation choice made by a fixed rule (the most listed contacts). It is not a binding-site call.
- "Not observed" (a position without heavy atoms) is not "no contact".
- Nothing here estimates closeness to an experimental structure, affinity, or whether the molecules interact.

