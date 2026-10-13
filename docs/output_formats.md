# Output formats

Every `run` command writes into a new directory and refuses one that already holds its outputs. All JSON is UTF-8.

## Evaluate (`rnplens evaluate run --out DIR`)

| file | content |
|---|---|
| `result.json` | `rnpbench_evaluate_version`, `created_utc`, `target_id`, `input` (prediction, reference and construct, with SHA-256), `dockq` (configuration, status, value, unrounded value, class, reported statistic, selected mapping, admissible candidates, per-interface DockQ/fnat/iRMSD/LRMSD, correspondence counts, failure stage/reason/detail, model numbering), `geometry` (status, the three RMSDs with aligned/pose/native counts, chains used, configuration, correspondence note), `validity`, `provenance` (dependency versions, platform, SHA-256 of each frozen scorer file) |
| `result.csv` | one row; columns `target_id, prediction_sha256, reference_sha256, engine, dockq_status, dockq, dockq_unrounded, dockq_class, fnat, irmsd, lrmsd, selected_mapping, n_admissible_candidates, n_interfaces, pairs_in_frame, pairs_out_of_frame, pairs_indeterminate, dockq_failure_stage, dockq_failure_reason, geometry_status, protein_internal_ca_rmsd, rna_internal_c4_rmsd, rna_placement_c4_rmsd, n_protein_pairs, n_rna_pairs, geometry_exclusion`; NO VALUE fields are empty |
| `summary.txt` | human-readable summary |

## Report (`rnplens report run CONTRACT --out DIR`)

| file | content |
|---|---|
| `result.json` | `schema_version` (`rnpbench-predict-result-1`), `package_version` (`rnpbench-predict-1.0.0`), `summary` (case-level agreement, hypotheses at each threshold, repeat agreement, flags `NO_REFERENCE_STRUCTURE_IS_READ`, `NO_ACCURACY_IS_COMPUTED`, `SEMANTICS`), `per_output` (state, chain lengths, confidence and its kind, contacts, surface size), `engine_pairs`, `contact_support` (`"residue,nucleotide": support`), `environment`, `wall_s` |
| `contacts_by_output.json` | the residue–nucleotide contacts of each output |
| `report_<case_id>.html` | self-contained page (figures need the `html` extra; omitted with `--no-report`) |

## Diagnose (`rnplens diagnose run ... --out DIR`)

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
