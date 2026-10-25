# Output formats

Every `run` command writes into a new directory and refuses one that already holds its outputs. All JSON is UTF-8.

## Evaluate (`rnplens evaluate run --out DIR`)

| file | content |
|---|---|
| `result.json` | `rnpbench_evaluate_version`, `created_utc`, `target_id`, `input` (prediction, reference and construct, with SHA-256), `dockq` (`configuration`, `status`, `dockq`, `dockq_unrounded`, `dockq_class`, `reported_statistic`, `selected_mapping`, `n_admissible_candidates`, `per_interface` (DockQ, fnat, iRMSD, LRMSD per chain pair), `correspondence` counts, `failure_stage`/`failure_reason`/`failure_detail`, `model_numbering`), `geometry` (status, the three RMSDs with aligned/pose/native counts, chains used, configuration, correspondence note), `validity`, `provenance` (dependency versions, platform, SHA-256 of each frozen scorer file) |
| `result.csv` | one row; columns `target_id, prediction_sha256, reference_sha256, engine, dockq_status, dockq, dockq_unrounded, dockq_class, fnat, irmsd, lrmsd, selected_mapping, n_admissible_candidates, n_interfaces, pairs_in_frame, pairs_out_of_frame, pairs_indeterminate, dockq_failure_stage, dockq_failure_reason, geometry_status, protein_internal_ca_rmsd, rna_internal_c4_rmsd, rna_placement_c4_rmsd, n_protein_pairs, n_rna_pairs, geometry_exclusion`; NO VALUE fields are empty |
| `summary.txt` | human-readable summary |

## Report (`rnplens report run CONTRACT --out DIR`)

| file | content |
|---|---|
| `result.json` | `schema_version` (`rnpbench-predict-result-1`), `package_version` (`rnpbench-predict-1.0.0`), `summary` (case-level agreement, hypotheses at each threshold, repeat agreement, flags `NO_REFERENCE_STRUCTURE_IS_READ`, `NO_ACCURACY_IS_COMPUTED`, `SEMANTICS`), `per_output` (state, chain lengths, confidence and its kind, contacts, surface size), `engine_pairs`, `contact_support` (`"residue,nucleotide": support`), `environment`, `wall_s` |
| `contacts_by_output.json` | the residue–nucleotide contacts of each output |
| `report_<case_id>.html` | self-contained page (figures need the `html` extra; omitted with `--no-report`) |

## Diagnose (`rnplens diagnose run ... --out DIR`; rc3 format, kept for reference: BLOCKED in 0.4)

| file | content |
|---|---|
| `report.json` | `target`, `engines`, `preflight` (receipt if `--request` given), `validity` (counts per class, `n_total`, `n_valid`, details), `disagreement` (median pairwise value per axis, pairs used, usable structures, exclusions, refusals), `diagnosis` (`statements` with value, band, percentile, reference and evidence; `refused_statements`; `measured_but_not_attributed`), `applicability` (0.2.0rc3: `status` inside or outside the validated domain, `reasons_outside`, `validated_domain`, `outside_domain_accepted_by_user`), `limits`, `sampling_budget_note`, `rnpbench_diagnose_version` |
| `report.html` | self-contained page |

`rnplens diagnose validity` prints its JSON (`per_structure`, `summary`) to standard output.

## Run record (`rnplens_run.json`, every `run`)

Written by the `rnplens` command into the output directory after the tool finishes: `record`
(`rnplens-run-record-1`), `rnplens_version`, `implementation`, `created_utc`, `command`, `working_directory`,
`inputs` (path and SHA-256 of every input file named on the command line or in a contract) and `outputs` (every
file the tool wrote, with SHA-256). It is never written over an existing record.

JSON Schemas of all four files are in [schemas/](schemas/).

## Self-tests

`rnplens selftest`, and each tool's `selftest`, print one line per check and end with `PASS` or `FAIL`; with `--out`
they also write a JSON record.

## Evaluate: terms used in the output

- **Geometry status in 0.4.** The public `rnplens evaluate run` always writes `geometry.status` `BLOCKED` (with
  `blocked_code` `GEOMETRY_BLOCKED_IN_0.4`, `blocked_reason` and `fields_withheld`; the geometry value and count
  fields are absent), `geometry_status` `BLOCKED` and `geometry_exclusion` `GEOMETRY_BLOCKED_IN_0.4` with empty value
  columns in `result.csv`, and a one-line block statement in `summary.txt`. `result.json` also carries
  `rnplens_public_output`: the filter applied and, for each file the frozen component wrote before filtering,
  `content_sha256` (deterministic: the hash of the JSON with volatile keys such as `created_utc` removed, the byte hash
  for other files; equal between identical runs) and `raw_file_sha256` (the byte hash, volatile because the frozen
  `result.json` carries its own creation time). The same record is written by `rnplens evaluate selftest --out`. The
  `COMPUTED` / `NO_VALUE` statuses below describe the frozen component (rc3 records, such as
  `examples/expected_output/`).
- **Statuses.** `dockq.status` is `SCORED` or `NO_VALUE`; `geometry.status` is `COMPUTED` or `NO_VALUE`. With
  `NO_VALUE` the value fields are `null` in `result.json`, empty in `result.csv`, and `summary.txt` prints
  `NO VALUE (not zero)`; the failing stage and reason are recorded.
- **Chain mapping** (`selected_mapping`, for example `BA:BA`). The chain pair of the model, then the chain pair of
  the reference it was mapped to (`model:reference`). The order of the two letters within a pair is DockQ 2.1.3's
  own and does not indicate which chain is the protein; `AB:AB` and `BA:BA` are both a one-to-one mapping of the
  model's chains onto the reference chains with the same identifiers. `per_interface` is keyed the same way.
- **Position counts of the geometry route.** `n_*_pose`: positions present in the prediction; `n_*_native`:
  positions resolved in the experimental structure; `n_*_aligned`: positions matched between the two by the frozen
  sequence alignment and used in the RMSD. Aligned can be well below native when the experimental structure covers
  a different part of the construct, or when the alignment leaves positions unpaired; the RMSD is over the aligned
  positions only, and `summary.txt` states that count (`over 166 residues`).
- **Construct–reference comparison.** The construct sequences are compared with the reference's
  `_entity_poly.pdbx_seq_one_letter_code_can` (canonical) record when present, otherwise with
  `pdbx_seq_one_letter_code`. A modified residue is therefore reported as a difference only when the file's
  sequence record shows it as such (for example `X`); files downloaded from RCSB carry the canonical record, in which
  most modified nucleotides appear as their parent base. Coordinates are never edited either way.
