# Demonstration 3: binding-hypothesis interpretation (pool A development target 6BJG, Boltz-2, @N@ samples)

**What the researcher asks.** "I have @N@ Boltz-2 samples of one complex. Which distinct binding proposals do they
contain, and which contacts distinguish the proposal that holds the engine's own pick from the next one?"

**Target rule, fixed in advance** (`records/v04_integration/DEMOS_PLAN.md`, committed before this run): 6BJG, the
worked example of `docs/grouping.md`. The demonstration therefore also checks that the documented numbers are
reproduced. 6BJG is a pool-A development target. It is not an excluded target, and pool A is disjoint from the Rank
holdout.

**Data read.** Only `PCfold3D-RNP/outputs/rnp/jpf/nscale/inputs/6BJG.yaml` (sequences) and
`boltz_out/boltz_results_6BJG/predictions/6BJG/` (the @N@ `6BJG_model_*.pdb` files with their
`confidence_*.json`). They are copied into `inputs/` and hashed (`logs/inputs_sha256.tsv`). **No DockQ label file
was opened** (not `nscale_sample_dockq.tsv`, not `reranker_consensus.tsv`), and nothing under `RNPLens-Rank/`.

## Commands (run from this folder; `rnplens` = `python -m rnplens` of RNPLens 0.4.0.dev0)

```
python scripts/lib/boltz_yaml_to_fasta.py inputs/6BJG.yaml inputs
rnplens import inputs/boltz_out --protein-seq inputs/protein.fasta --rna-seq inputs/rna.fasta --engine BOLTZ2 --case-id 6BJG --out project
rnplens analyse project --out analysis --nproc 8
rnplens group project --analysis analysis
python scripts/lib/group_pick.py analysis/groups/groups.json          # -> @G@ @H@ (engine-pick group, next in display order)
rnplens group-diff analysis @G@ @H@
rnplens view project --analysis analysis
python scripts/lib/retention_check.py project analysis/groups/groups.json @N@ retention_check.json
python scripts/3_grouping_6BJG/docs_parity.py analysis @G@ @H@ docs_parity.json
python scripts/lib/wording_scan.py . checks/wording_scan.json
```

## Outputs

| file | what it is |
|---|---|
| `analysis/groups/groups.json`, `groups.html`, `groups.tsv` | groups at t = 0.3, 0.5 (primary) and 0.7: members, representatives, the designated structure, engine-weighted sizes, P spread, provenance and evidence IDs |
| `analysis/groups/dendrogram.json`, `pairwise.json` | full merge sequences; R, U and P for every pair |
| `analysis/groups/diff_@G@_@H@/diff.json`, `diff.tsv`, `diff.html`, `overlay.svg` | contacts frequent in both groups, in group @G@ only, in group @H@ only; per-member presence and unresolved positions |
| `analysis/viewer/viewer.html` | offline Mol* page of all @N@ structures, each with its own Report contacts highlighted |
| `analysis/summary.json`, `summary.html`, `report/` | the whole-construct analysis |
| `retention_check.json` | the candidate-retention check |
| `docs_parity.json` | the documented 6BJG numbers compared with this run |
| `checks/wording_scan.json` | wording scan of every text output |

## How to read the result
- A *group* is a binding proposal: the structures that share a protein surface (level 1, U) and a contact register
  (level 2, R), merged by average linkage while the mean agreement is at least t. All three cuts are always shown
  because the number of groups depends strongly on the cut.
- Groups are listed with the group holding the engine-designated structure first, then by smallest canonical key.
  They are **never** listed by size. Group numbers are display positions, not ranks.
- The *representative* is the member with the highest mean R to the other members. It is a reading aid for the
  group, not a pick among the @N@ structures.
- The *difference map* lists the contacts that distinguish two groups. Each is a candidate observation for expert
  review.

## What these outputs do NOT mean
- Group size says how often these @N@ samples of one model produced a proposal. Samples of one model are not
  independent, so a larger group is not more supported. No group or structure is named as the one that matches the
  real complex.
- The engine-designated structure is the engine's own pick. Showing it first is a display rule, not an endorsement.
- In a retrospective development check (`records/grouping/GROUPING_QUALIFICATION_REPORT.md`), an inspection set
  built from group representatives did not retain an acceptable structure more often than the same number of
  structures taken by engine confidence. Grouping is not a selection method.
- A contact that distinguishes two groups does not establish a biological contact, recommend a mutation or predict
  an effect.
- P (RNA pose difference) is descriptive. A wide spread inside a group is not a defect of any member.

