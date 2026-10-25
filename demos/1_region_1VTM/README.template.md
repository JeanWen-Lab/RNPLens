# Demonstration 1: RNA-region investigation (development task d2_1VTM_agreement)

**What the researcher asks.** "Which protein residues contact this RNA region, and which exact contacts differ
between my two prediction runs?"

**Data.** Development task `scratch_agent/assistant_dev_tasks/d2_1VTM_agreement` (1VTM, a development target, not an
excluded one): two Boltz-2 runs (`run_A`, `run_B`), 5 samples each, protein 158 residues, RNA `GAA` (3 nt). The source
folder is read only; it is copied into `inputs/` and hashed (`logs/inputs_sha256.tsv`) before anything runs.

**Region rule, fixed before any contact was looked at** (`records/v04_integration/DEMOS_PLAN.md`, committed before
this run): the RNA range spanned by the union of all RNA contact positions of the engine-designated structures, i.e.
`[min, max]`, read from Report's own `analysis/report/contacts_by_output.json`. Computed by
`scripts/lib/region_rule.py` into `region_rule.json`. Region used here: **RNA @RANGE@**.

## Commands (run from this folder; `rnplens` = `python -m rnplens` of RNPLens 0.4.0.dev0)

```
rnplens import inputs/run_A inputs/run_B --protein-seq inputs/protein.fasta --rna-seq inputs/rna.fasta --engine BOLTZ2 --case-id 1VTM_d2 --out project
rnplens analyse project --out analysis --nproc 4
python scripts/lib/region_rule.py project analysis region_rule.json          # prints @RANGE@
rnplens region project analysis --rna @RANGE@                                 # both runs (all runs of the project)
rnplens view project --analysis analysis --rna @RANGE@
rnplens explain structures --analysis analysis --project project
rnplens explain region_mapping --region region_@RANGE@ --analysis analysis --project project
python scripts/lib/region_answer.py analysis region_@RANGE@ answer.md answer.json
rnplens explain contact --contact <label> --analysis analysis --project project   # each differing contact (up to 3)
```

Every command, its expected and actual exit code is in `logs/steps.tsv`; each command's output is in `logs/<step>.log`.
`bash replay.sh` re-runs the whole workflow into a new folder and compares every result JSON (see the end).

## Outputs

| file | what it is |
|---|---|
| `analysis/region_@RANGE@/region.json` | the regional result: structures compared, coverage, every contact with per-run k of n, designated structure and additional samples, classes, evidence IDs |
| `analysis/region_@RANGE@/region_contacts.tsv` | the regional contact table, one row per contact and run |
| `analysis/region_@RANGE@/region.html` | the readable page of the same result |
| `analysis/region_@RANGE@/region_map.png` | protein x RNA contact map per run, region outlined |
| `analysis/viewer_@RANGE@/viewer.html` | offline Mol* page: every structure with its own Report contacts in RNA @RANGE@ highlighted (open from disk; no network) |
| `analysis/explain/explain_*.txt/.json` | traced explanations: included structures, region mapping, structures listing each differing contact |
| `answer.md`, `answer.json` | the template answer below, built only from `region.json`, each value with its evidence ID |
| `analysis/summary.json`, `analysis/summary.html`, `analysis/report/` | the whole-construct analysis (Report, Diagnose) the region filter reads |
| `checks/wording_scan.json`, `checks/replay_check.json` | wording scan of every text output; replay comparison |

## How to read the result
- **Protein residues that contact the region**: every protein residue that at least one compared structure lists in
  contact (any heavy-atom pair within 5.0 A) with a nucleotide of the region, from Report's per-structure lists.
- **Contacts that differ between runs**: a contact is *found only in run X* when run X lists it and every structure
  of the other run resolves both positions without listing it; *present in some runs* covers the other cases. For
  each, the table gives whether the run's engine-designated structure lists it, k of n structures of the run, k of
  n among the additional samples (the run's non-designated structures), and the structure ids that list it.
- **Designated vs additional samples**: the designated structure is the engine's own pick recorded at import
  (highest Boltz-2 `confidence_score`); the other four samples of each run are the additional samples.

## What these outputs do NOT mean
- A contact that recurs among the 10 predictions is not evidence that it exists in the real complex; the counts
  say how often these predictions list it.
- Samples from one model and one run are not independent; several can share one error.
- "Found only in one run" is a listing with counts. It is not a measure of how similar the runs are and does not
  say which run is right; no run, structure or contact is ranked or recommended.
- "Not observed" (a position without heavy atoms) is not "no contact".
- Nothing here estimates closeness to an experimental structure, affinity, or whether the molecules interact.
- The region comes from a rule applied to the designated structures; it is a presentation choice, not a binding
  site call. With a 3-nt RNA the region covers most or all of the construct.

