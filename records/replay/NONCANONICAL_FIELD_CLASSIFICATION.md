# Field-by-field classification of the non-canonical outputs (round 2, step 1)

Track `replay`, branch `track/replay-r2`, base `b3374e4`. This is the step that the owner's item 5 asks for: every output
that `DETERMINISM_CONTRACT_v1` left non-canonical is classified **field by field**, and the classification decides what
`DETERMINISM_CONTRACT_v2` must cover. Nothing in the v1 records changes. **The original demonstration 2 replay check
remains FAILED**, and v1's PASS on its four cases stands exactly as recorded: it covers the v1 canonical files only.

## Classes and rules

| class | meaning | canonical form in v2 |
|---|---|---|
| **a** | volatile execution metadata: wall-clock times, durations, commands as typed, working directory, host and interpreter, the source commit | not in any promised file (sidecar or execution record) |
| **b** | derived from volatile metadata: SHA-256 values of files whose bytes contain (a) items; ids built from a time-stamped record (consent ids); the follow-up `evidence_sha256`, which covers such hashes | replaced by a value computed from canonical content (the SHA-256 of the covered file's canonical projection; the consent record counter; `evidence_content_sha256`) |
| **c** | scientifically meaningful: numbers, contact and evidence records, interpretations and limits, selections and decisions, inputs identity (by content hash and by **project-relative** location) | kept, byte-identical; absolute paths written project-relative |

**Rules, first match wins.** These are implemented in `records/replay/v2/classify_fields.py`.

1. **Volatile keys are (a).** These are the keys `created_utc`, `recorded_utc`, `status_utc`, `stored_utc`,
   `since_utc`, `timestamp_utc`, `started_utc`, `wall_s`, `code_commit`, `working_directory`, `cwd`, `pid`,
   `hostname`, `host`, `project_root`, `platform` and `python`.
2. **Commands as typed are (a).** This covers any field under a `command` or `argv` key.
3. **Ids derived from a volatile record are (b).** This applies to any field observed to change as an id.
4. **Time stamps and durations are (a).** This applies to any field whose observed changes are only time stamps or
   durations.
5. **Hashes over volatile bytes are (b).** A hash is (b) when it was observed to change because the bytes it covers
   changed in a volatile way. The step-A resolver traced every such hash to its target.
6. **Path identities are (c).** These are absolute paths that identify inputs, structures and records. Only the
   project-relative location is meaningful; the absolute prefix is (a).
7. **Everything else is (c).** **No field is put into (a) or (b) because making it deterministic is inconvenient.** A
   field becomes (a) or (b) only through rules 1-5.

A field pattern is (c) if **any** of its instances is (c). This happens, for example, with `provenance/inputs/*/sha256`.
That field is (c) when it hashes an input or a canonical file, and (b) when it hashes a file that carries its own
creation time. In v2 each instance is canonicalised on its own. Another mixed case is `followup_record.json /consent_record_id`. It is
null for the local follow-up (`fu_0001`) and a consent id (b) for the scripted Codex path (`fu_0002`). Both share the
pattern `fu_NNNN`, so the pattern reports (c); the set value is (b).

**Sidecars** (`project/.rnplens/run/**`) are volatile by design and were checked to contain no (c) field. Logs and text
files are classified by line: lines that change only through paths, time stamps or resolved hashes carry (a) or (b)
tokens, and every other line is (c).

## How the classification was observed

The workflow is `records/replay/v2/retest_case_v2.sh`. It is the v1 lifecycle plus:
- `explain evidence`;
- the offline viewer;
- `group` and `group-diff`;
- the **scripted** Codex follow-up path, with a stub client, no model and no Codex process. It writes a consent record.

It ran on karyon at the unchanged `b3374e4` on the development case 1VTM. 1VTM is a v1 case, so it is not used in the
v2 retest. Three trees were produced:
- **first**: the base workflow followed by `records/replay/v2/continue_case_v2.sh`;
- **second**: an independent run in another absolute directory, 8 s later, then the continuation;
- **moved**: a byte copy of **first**, taken right after its base workflow, at another absolute path
  (`moved_elsewhere/…`), then the continuation.

Every step of all three reached its expected exit code. `observed` in the JSON record gives each field's trace class
for first vs second and for first vs moved; `equal` means no difference. All 1829 JSON field patterns, the 64 text
files and the 29 binary files are in `NONCANONICAL_FIELD_CLASSIFICATION.json`.

Two observations at `b3374e4` (v1 code) bear on the contract:
1. **A moved project recomputes.** In **moved**, `rnplens update` recomputed the analysis (new `analyses/v0008`)
   where **first** reused `v0004`. The copied importer manifest holds the original absolute paths, and the v1 cache key
   over `manifest_view` changes with them. The continuation logs show it (`c1`, `c2`, `c7`). The same applies to the
   region step and the status output.
2. **A moved project still points at the original location.** 33 JSON files in **moved**, outside the sidecars, contain
   the absolute root of **first**. Readers of the 0.3 importer manifest (`used_path`) therefore keep reading the
   original location's structure files while it exists.

## Per-file result (outputs only; prepared input copies are listed in the JSON)

Counts are field patterns. "(c) fields" groups the (c) patterns by top-level key, with counts.

### `followup_scripted.json`

- category: workflow file outside the managed project; field patterns: a=3, b=1, c=106; v2 coverage: outside the managed project: not covered (see text)
- (a): `/provenance/code_commit`, `/provenance/created_utc`, `/user_confirmation/timestamp_utc`
- (b): `/evidence_sha256` (HASH)
- (c): `chosen` (19), `dir` (1), `label` (1), `mode` (1), `model_calls_made` (1), `model_config` (6), `proposals` (20), `proposals_raw` (31), `provenance` (20), `rationale_shown_in_answer` (1), `stop` (1), `traceability_violations` (1), `user_confirmation` (2), `wording_audit` (1)

### `project/analyses/vNNNN/main/explain/explain_evidence_<id>.json`

- category: JSON output; field patterns: a=2, b=2, c=77; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/provenance/code_commit`, `/provenance/created_utc`
- (b): `/provenance/inputs/*/sha256` (HASH), `/statements/*/file_sha256` (HASH)
- (c): `n_statements` (1), `note` (1), `provenance` (8), `query` (3), `roots` (4), `statements` (60)

### `project/analyses/vNNNN/main/explain/explain_region_mapping_<id>.json`

- category: JSON output; field patterns: a=2, b=1, c=22; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/provenance/code_commit`, `/provenance/created_utc`
- (b): `/provenance/inputs/*/sha256` (HASH)
- (c): `n_statements` (1), `note` (1), `provenance` (8), `query` (3), `roots` (4), `statements` (5)

### `project/analyses/vNNNN/main/explain/explain_structures_<id>.json`

- category: JSON output; field patterns: a=2, b=1, c=29; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/provenance/code_commit`, `/provenance/created_utc`
- (b): `/provenance/inputs/*/sha256` (HASH)
- (c): `n_statements` (1), `note` (1), `provenance` (8), `query` (3), `roots` (4), `statements` (12)

### `project/analyses/vNNNN/main/followup/fu_NNNN/evidence_summary.json`

- category: JSON output; field patterns: c=98; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): none
- (b): none
- (c): `agreement` (9), `analyses_run` (8), `categories_version` (1), `construct` (4), `contact_bands` (15), `initial_result` (3), `inventory` (18), `reference_derived` (2), `region_outputs` (18), `rna_positions_in_contact` (3), `schema` (1), `single_structure_contacts` (11), `unavailable` (5)

### `project/analyses/vNNNN/main/followup/fu_NNNN/followup_answer.json`

- category: JSON output; field patterns: c=26; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): none
- (b): none
- (c): `rendered` (1), `statements` (24), `traceability_violations` (1)

### `project/analyses/vNNNN/main/followup/fu_NNNN/followup_plan.json`

- category: JSON output; field patterns: b=1, c=23; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): none
- (b): `/evidence_sha256` (HASH)
- (c): `args` (10), `executed` (1), `follow_up` (1), `question_sha256` (1), `rule` (1), `rule_slots` (4), `schema` (1), `source` (1), `tool_calls` (3)

### `project/analyses/vNNNN/main/followup/fu_NNNN/followup_record.json`

- category: JSON output; field patterns: a=6, b=2, c=164; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/created_utc`, `/provenance/code_commit`, `/provenance/created_utc`, `/tool_log/*/started_utc`, `/tool_log/*/wall_s`, `/user_confirmation/timestamp_utc`
- (b): `/evidence_sha256` (HASH), `/provenance/inputs/*/sha256` (HASH)
- (c): `allowlist` (1), `chosen` (23), `client_class` (1), `consent` (3), `consent_record_id` (1), `constants` (1), `dir` (1), `initial_result` (3), `limits` (7), `local_suggestions` (23), `mode` (1), `mode_requested` (1), `model_calls` (10), `model_calls_made` (1), `model_config` (7), `n_tool_calls` (1), `outputs` (4), `payloads` (6), `proposals` (32), `provenance` (16), `question` (1), `question_sha256` (1), `schema` (1), `status` (1), `stop` (1), `summary` (5), `tool_log` (7), `traceability_violations` (1), `user_confirmation` (2), `wording_audit` (1)

### `project/analyses/vNNNN/main/groups/dendrogram.json`

- category: JSON output; field patterns: a=2, c=51; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/provenance/code_commit`, `/provenance/created_utc`
- (b): none
- (c): `kind` (1), `level1` (8), `level2` (27), `note` (1), `provenance` (14)

### `project/analyses/vNNNN/main/groups/diff_<g>_<h>/diff.json`

- category: JSON output; field patterns: a=2, c=53; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/provenance/code_commit`, `/provenance/created_utc`
- (b): none
- (c): `caveat` (1), `counts` (4), `frequent_cut_point` (1), `frequent_definition` (1), `group_A` (1), `group_B` (1), `kind` (1), `members_A` (1), `members_B` (1), `notes` (1), `provenance` (10), `rna_conformation_difference` (1), `rows` (27), `status` (1), `threshold` (1)

### `project/analyses/vNNNN/main/groups/groups.json`

- category: JSON output; field patterns: a=2, c=174; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/provenance/code_commit`, `/provenance/created_utc`
- (b): none
- (c): `construct` (4), `definition` (1), `display_order` (1), `eligible_per_engine` (1), `ineligible` (1), `kind` (1), `limits` (1), `n_eligible` (1), `n_interface` (1), `n_no_interface` (1), `n_structures` (1), `not_imported` (1), `notes` (1), `placement_note` (1), `primary_threshold` (1), `provenance` (14), `rna_conformation_difference` (1), `size_note` (1), `source` (1), `status` (1), `structures` (11), `thresholds` (126), `thresholds_reported` (1)

### `project/analyses/vNNNN/main/groups/pairwise.json`

- category: JSON output; field patterns: a=2, c=26; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/provenance/code_commit`, `/provenance/created_utc`
- (b): none
- (c): `definition` (1), `kind` (1), `pairs` (10), `provenance` (14)

### `project/analyses/vNNNN/main/methods/methods_sources.json`

- category: JSON output; field patterns: a=2, c=24; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/provenance/code_commit`, `/provenance/created_utc`
- (b): none
- (c): `draft_note` (1), `fixed_text` (2), `llm_used` (1), `omitted` (4), `provenance` (8), `sentences` (8)

### `project/analyses/vNNNN/main/methods/provenance_manifest.json`

- category: JSON output; field patterns: a=7, c=26; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/manifest/commands/*/command`, `/manifest/commands/*/command/*`, `/manifest/commands/*/created_utc`, `/manifest/versions/report_environment/platform`, `/manifest/versions/report_environment/python`, `/provenance/code_commit`, `/provenance/created_utc`
- (b): none
- (c): `manifest` (18), `provenance` (8)

### `project/analyses/vNNNN/main/region_<a>-<b>/region.json`

- category: JSON output; field patterns: a=3, c=165; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/provenance/code_commit`, `/provenance/command/*`, `/provenance/created_utc`
- (b): none
- (c): `contact_definition` (5), `contacts` (46), `figure` (2), `limits` (1), `provenance` (12), `region` (12), `runs` (35), `schema` (1), `summary` (51)

### `project/analyses/vNNNN/main/report/result.json`

- category: JSON output; field patterns: a=3, c=103; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/environment/platform`, `/environment/python`, `/wall_s`
- (b): none
- (c): `contact_support` (53), `engine_pairs` (1), `environment` (4), `package_version` (1), `per_output` (17), `schema_version` (1), `summary` (26)

### `project/analyses/vNNNN/main/report/rnplens_run.json`

- category: JSON output; field patterns: a=3, c=8; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/command/*`, `/created_utc`, `/working_directory`
- (b): none
- (c): `implementation` (1), `inputs` (2), `note` (1), `outputs` (2), `record` (1), `rnplens_version` (1)

### `project/analyses/vNNNN/main/report_runs_BOLTZ2/result.json`

- category: JSON output; field patterns: a=3, c=81; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/environment/platform`, `/environment/python`, `/wall_s`
- (b): none
- (c): `contact_support` (28), `engine_pairs` (1), `environment` (4), `package_version` (1), `per_output` (17), `schema_version` (1), `summary` (29)

### `project/analyses/vNNNN/main/report_runs_BOLTZ2/rnplens_run.json`

- category: JSON output; field patterns: a=3, c=8; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/command/*`, `/created_utc`, `/working_directory`
- (b): none
- (c): `implementation` (1), `inputs` (2), `note` (1), `outputs` (2), `record` (1), `rnplens_version` (1)

### `project/analyses/vNNNN/main/run_repeat_inputs/report_contract_BOLTZ2.json`

- category: JSON output; field patterns: c=11; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): none
- (b): none
- (c): `case_id` (1), `construct` (4), `outputs` (5), `schema_version` (1)

### `project/analyses/vNNNN/main/summary.json`

- category: JSON output; field patterns: a=1, c=105; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/created_utc`
- (b): none
- (c): `case_id` (1), `construct` (2), `contacts` (13), `diagnose` (1), `engine_pairs` (2), `evaluate` (1), `evaluate_reference` (1), `evaluate_withheld` (1), `inventory` (24), `limits` (1), `protein_positions` (8), `repeat_agreement` (4), `report` (7), `rna_positions` (8), `rnplens_version` (1), `run_repeat_agreement` (11), `statement_classes` (5), `steps` (13), `summary` (1)

### `project/analyses/vNNNN/main/viewer_<a>-<b>/assets/VERSION.molstar.json`

- category: software asset copy (bundled Mol* files); field patterns: c=26; v2 coverage: the file itself (v2)
- (a): none
- (b): none
- (c): `copyright` (1), `files` (9), `homepage` (1), `license` (1), `license_file` (1), `not_included` (1), `package` (1), `record` (1), `source` (8), `use` (1), `version` (1)

### `project/analyses/vNNNN/main/viewer_<a>-<b>/viewer_manifest.json`

- category: JSON output; field patterns: a=2, c=35; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/provenance/code_commit`, `/provenance/created_utc`
- (b): none
- (c): `files` (4), `highlighted` (6), `limits` (1), `page` (1), `provenance` (17), `structures` (6)

### `project/imports/vNNNN/main/.rnplens/consent.json`

- category: JSON output; field patterns: a=3, b=2, c=17; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/provenance/code_commit`, `/provenance/created_utc`, `/records/*/timestamp_utc`
- (b): `/current` (ID), `/records/*/id` (ID)
- (c): `provenance` (7), `records` (9), `schema` (1)

### `project/imports/vNNNN/main/manifest.json`

- category: JSON output; field patterns: a=1, c=54; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): `/created_utc`
- (b): none
- (c): `accepted_derived_copies` (1), `case_id` (1), `construct` (4), `counts` (6), `decisions` (1), `inputs` (1), `manifest` (1), `resolution_answers` (1), `rnplens_version` (1), `runs` (5), `structures` (31), `unrecognised_files` (1)

### `project/imports/vNNNN/main/report_contract.json`

- category: JSON output; field patterns: c=11; v2 coverage: projection `<file>.canonical.json` (v2)
- (a): none
- (b): none
- (c): `case_id` (1), `construct` (4), `outputs` (5), `schema_version` (1)

### `region_rule.json`

- category: workflow file outside the managed project; field patterns: a=2, c=20; v2 coverage: outside the managed project: not covered (see text)
- (a): `/provenance/code_commit`, `/provenance/created_utc`
- (b): none
- (c): `designated` (6), `provenance` (8), `region` (3), `rna_length` (1), `rna_positions_S` (1), `rule` (1)

## Sidecars (volatile by design)

- `project/.rnplens/run/.rnplens/cache/<key>.json`: a=12, b=5; no (c) field
- `project/.rnplens/run/.rnplens/state/vNNNN.json`: a=6, b=2; no (c) field
- `project/.rnplens/run/analyses/reports/update_vNNNN_vNNNN.json`: a=6, b=2; no (c) field
- `project/.rnplens/run/analyses/vNNNN/index.json`: a=7, b=1; no (c) field
- `project/.rnplens/run/analyses/vNNNN/update_report.json`: a=6, b=2; no (c) field

## Text, log and binary outputs inside the project

| file | category | differing lines, first vs second / first vs moved | v2 coverage |
|---|---|---|---|
| `project/analyses/vNNNN/main.log` | execution log inside the project | {'VOLATILE_TEXT': 1} / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/commands.log` | execution log inside the project | {'VOLATILE_TEXT': 4} / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/explain/explain_evidence_<id>.txt` | text output | {'TEXT_WITH_HASH:VOLATILE_ONLY': 3} / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/explain/explain_region_mapping_<id>.txt` | text output | none / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/explain/explain_structures_<id>.txt` | text output | {'VOLATILE_TEXT': 1} / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/followup/fu_NNNN/followup_answer.md` | text output | {'TEXT_WITH_HASH:VOLATILE_ONLY': 2} / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/groups/diff_<g>_<h>/diff.html` | text output | none / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/groups/diff_<g>_<h>/diff.tsv` | text output | none / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/groups/diff_<g>_<h>/overlay.svg` | text output | none / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/groups/groups.html` | text output | none / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/groups/groups.tsv` | text output | none / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/methods/methods.md` | text output | none / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/methods/methods.txt` | text output | none / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/region_<a>-<b>/region.html` | text output | none / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/report/report_1VTM_retest.html` | text output | none / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/report_runs_BOLTZ2/report_1VTM_retest.html` | text output | none / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/summary.html` | text output | none / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/assets/LICENSE.molstar.txt` | software asset copy (bundled Mol* files) | none / none | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/assets/molstar.css` | software asset copy (bundled Mol* files) | none / none | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/assets/molstar.js` | software asset copy (bundled Mol* files) | none / none | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/01_sNNN_run_A_1VTM_model_0.pdb.js` | structure copy (viewer) | none / none | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/02_sNNN_run_A_1VTM_model_1.pdb.js` | structure copy (viewer) | none / none | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/03_sNNN_run_A_1VTM_model_2.pdb.js` | structure copy (viewer) | none / none | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/04_sNNN_run_A_1VTM_model_3.pdb.js` | structure copy (viewer) | none / none | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/05_sNNN_run_A_1VTM_model_4.pdb.js` | structure copy (viewer) | none / none | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/06_sNNN_run_B_1VTM_model_0.pdb.js` | structure copy (viewer) | none / none | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/07_sNNN_run_B_1VTM_model_1.pdb.js` | structure copy (viewer) | none / none | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/08_sNNN_run_B_1VTM_model_2.pdb.js` | structure copy (viewer) | none / none | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/09_sNNN_run_B_1VTM_model_3.pdb.js` | structure copy (viewer) | none / none | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/10_sNNN_run_B_1VTM_model_4.pdb.js` | structure copy (viewer) | none / none | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/view.mvsj` | text output | none / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/view_data.js` | text output | none / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/viewer.html` | text output | none / none | projection `<file>.canonical.txt` (v2) |
| `project/imports/vNNNN/main.log` | execution log inside the project | {'VOLATILE_TEXT': 3} / none | projection `<file>.canonical.txt` (v2) |
| `project/analyses/vNNNN/main/contact_map.png` | figure | byte-identical: [True] / [True] | the file itself (v2) |
| `project/analyses/vNNNN/main/region_<a>-<b>/region_map.png` | figure | byte-identical: [True] / [True] | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/01_sNNN_run_A_1VTM_model_0.pdb` | structure copy (viewer) | byte-identical: [True] / [True] | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/02_sNNN_run_A_1VTM_model_1.pdb` | structure copy (viewer) | byte-identical: [True] / [True] | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/03_sNNN_run_A_1VTM_model_2.pdb` | structure copy (viewer) | byte-identical: [True] / [True] | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/04_sNNN_run_A_1VTM_model_3.pdb` | structure copy (viewer) | byte-identical: [True] / [True] | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/05_sNNN_run_A_1VTM_model_4.pdb` | structure copy (viewer) | byte-identical: [True] / [True] | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/06_sNNN_run_B_1VTM_model_0.pdb` | structure copy (viewer) | byte-identical: [True] / [True] | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/07_sNNN_run_B_1VTM_model_1.pdb` | structure copy (viewer) | byte-identical: [True] / [True] | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/08_sNNN_run_B_1VTM_model_2.pdb` | structure copy (viewer) | byte-identical: [True] / [True] | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/09_sNNN_run_B_1VTM_model_3.pdb` | structure copy (viewer) | byte-identical: [True] / [True] | the file itself (v2) |
| `project/analyses/vNNNN/main/viewer_<a>-<b>/structures/10_sNNN_run_B_1VTM_model_4.pdb` | structure copy (viewer) | byte-identical: [True] / [True] | the file itself (v2) |

## Files outside the managed project

The workflow writes these files in the case root; they are not RNPLens outputs of the managed project:
- `logs/*.log`, `logs/steps.tsv`, `logs/RESULT*`: the step runner's records.
- `region_rule.json`: the demonstration region rule.
- `followup_scripted.json`: the scripted-demo summary.

Their (c) content duplicates records inside the project (the follow-up record and plan, the region). They are not
covered by the byte rule in v2. In **moved**, the continuation logs differ in content: they report a recomputed
analysis instead of a reused one. That is observation 1 above. It is a scientific-equality failure of the v1 code
under a moved-project replay.

## Consequences for DETERMINISM_CONTRACT_v2

- **Every (c) field** of every JSON, text or log output inside the managed project must be in a promised file. Each
  file is promised either directly (its own bytes) or through a canonical projection written next to it.
- **Figures, viewer structure copies and bundled assets** are promised directly. They hold no (a) or (b) item.
- **(b) hashes** in projections are replaced by the SHA-256 of the covered file's projection. The bytes of that value
  can be checked with `sha256sum`.
- **The follow-up evidence hash** gets a location-independent counterpart, `evidence_content_sha256`. The raw
  `evidence_sha256` is written by `rnplens_assistant/followup.py`, which is pinned by LIVE_QUALIFICATION_v1, and stays
  (b) there.
- **A moved project** must keep its cache keys. Paths recorded under a former project location are canonicalised as
  if they were under the current one, and this is tested by the moved-project replay. That absolute paths in
  non-canonical files still point at the former location is measured and reported. It is not hidden.
