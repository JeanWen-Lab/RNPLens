# RNPLens 0.4 determinism contract, version 1 (pre-registered)

Track `replay`, branch `track/replay`. This contract was written and committed **before any code change** for the
replay remediation, and before any retest run. The commit order on the branch is the record of that.

It governs:
- the implementation in step C;
- the requalification retest in step D, which is reported in `REPLAY_REQUALIFICATION_REPORT.md`.

Changes after the freeze are made only as numbered amendments at the end. Each amendment states whether it came
before or after the retest.

## 0. Status of the original check (unchanged)

The pre-registered byte-identical replay check of demonstration 2 (24BR interactive managed project; rule in
`records/v04_integration/DEMOS_PLAN.md`) **FAILED**:
- 22 of 43 files differed at the original run;
- 22 files differed again at the `bdd137f` rerun.

That verdict stands and is **not re-labelled** by this contract, by the trace (`REPLAY_DIFF_TRACE.md`), or by any
later result. The requalification below is a **new** test on **new** cases, under a **new** rule.

## 1. Two properties, defined separately

**(S) Scientific reproducibility.** Two runs must produce the same of each of the following, given the same inputs
(same file bytes, in the same layout relative to the project), the same configuration, the same recorded answers and
the same RNPLens version:
- **Numerical results**: contact rows and per-engine counts, per-structure contact lists, agreement and
  repeat-agreement values, region summaries and counts, and update-report counts.
- **Evidence records**: evidence IDs, explained statements, follow-up statements, and the citations they make.
- **Scientific interpretations**: every researcher-facing statement and limit text.

**(B) Byte-identical reproducibility.** Every file in the named list of canonical artifacts (section 3) has exactly the
same bytes in both runs.

(B) implies (S) for the canonical files only. (S) is checked for every file the workflow writes.

## 2. What is volatile

These items are **volatile execution metadata**. They may differ between runs without any scientific difference:
- wall-clock time stamps: `created_utc`, `recorded_utc`, `status_utc`, `stored_utc`, `since_utc`, `timestamp_utc`,
  `started_utc`, and time stamps in file names;
- measured durations (`wall_s`);
- the absolute location of the project and its inputs: absolute paths, the working directory, the host;
- the source-tree commit of the running code (`code_commit`, including `+dirty`);
- identifiers derived from any of these, such as consent record ids built from a hash of a time-stamped record.

The RNPLens version (`tool_version`, `rnplens_version`) is **not** volatile: it is part of every cache key.

A canonical file never contains a volatile item. Volatile items of a canonical file are written to its **sidecar**:
- location: `<project>/.rnplens/run/<path of the canonical file relative to the project>`;
- content: a JSON object `{schema, canonical_file, canonical_sha256, volatile: {<JSON pointer>: value}, execution: {...}}`;
- everything under `<project>/.rnplens/run/` is excluded from the byte rule.

Losing or deleting a sidecar never changes a scientific result. Without its sidecar, a reader shows times as unknown
and treats an unverifiable cache entry as a miss, which means the work is recomputed.

## 3. Canonical artifacts (the byte rule applies to these files only)

Paths are relative to the managed project directory. The machine-readable copy is
`records/replay/retest/canonical_artifacts_v1.json`; the retest uses that copy.

| pattern | written by | how it is made deterministic |
|---|---|---|
| `.rnplens/HEAD` | `state.py` | SHA-256 of a canonical state file |
| `.rnplens/state/v*.json` | `state.py`, `incremental.py`, `clarify.py` | the rules in section 4 |
| `.rnplens/cache/*.json`, `.rnplens/cache/invalid/*.json` | `state.py` | key, relative output folder, key components and tool version; the tamper-detection file hashes and `stored_utc` go to the sidecar; superseded entries are named `<key>.<n>.json` (a counter, not a time stamp) |
| `analyses/v*/index.json` | `incremental.py` | relative paths, canonical keys, no time stamp or commit |
| `analyses/v*/update_report.json`, `.html`, `analyses/reports/*.json`, `*.html` | `incremental.py` | relative paths, content hashes (section 4), answers listed with the version they were recorded in instead of a time |
| `imports/v*/*/construct_protein.fasta`, `construct_rna.fasta` | importer (0.3 route, unchanged) | already written from the sequences only |
| `imports/v*/*/derived/*/*` (Amendment 1) | importer (0.3 route, unchanged) | derived structure copies, written from an input by a fixed transformation |
| `analyses/v*/*/report/contacts_by_output.json`, `analyses/v*/*/report_runs_*/contacts_by_output.json` | Report (frozen, unchanged) | already written from the contact lists only |
| `analyses/v*/*/region_*/region_contacts.tsv` | `region.py` (unchanged) | already written from contact rows only |

**Not canonical in version 1.** The byte rule does not apply to these files; the scientific comparison of section 6
does.

1. **Records of the qualified 0.3 routes**, which 0.4 must not change:
   - the importer's `manifest.json` and `report_contract.json`;
   - `summary.json` and its HTML;
   - the analysis and import `.log` files;
   - Report's `rnplens_run.json` and `result.json` (which contain `created_utc`, absolute paths and `wall_s`), and its
     HTML reports.
2. **0.4 outputs written by modules outside this track**: `region.json`, `region.html` and maps; `explain/*`;
   `followup/*`; the consent record; `methods/*`; `groups/*`; viewer outputs; `run_repeat_inputs/*`.
   - Their bodies carry absolute paths that the viewer and the evidence lookup read today.
   - Several of them embed raw SHA-256 values of the files in item 1, which is the cause traced in
     `REPLAY_DIFF_TRACE.md` section 3.
   - Making them canonical needs changes in `region.py`, `evidence_query.py`, `methods_export.py`,
     `rnplens_assistant/followup.py` and `consent.py`. That is left to a later contract version.
3. **Logs, demonstration files, and anything outside the project directory.**

Version 1 therefore promises byte identity for:
- the managed-project record (state history, recorded decisions, cache keys, indices, before/after reports);
- the contact records and sequences listed above.

It does **not** promise byte identity for every output. The release documentation must say so.

## 4. Rules for canonical files

1. **Serialisation.**
   - JSON is `json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=True, default=str) + "\n"`.
   - Floats keep Python `repr`, the formatting Report already uses.
   - The order of lists is defined by sorted keys or by the pipeline order, never by file-system or hash order.
2. **Paths.**
   - An absolute path under the project directory is written as `./<relative path>`. The project directory itself is
     written as `.`.
   - An absolute path elsewhere is written relative to the project directory (for example `../in/run_A`) when it lies
     under a declared input, the reference, or the common parent folder of the project and its inputs.
   - This applies to values, to map keys, inside identifiers of the form `<kind>:<path>` (question ids, dependency
     keys, effects, importer answers), and inside free text.
   - Readers turn `./…` and `../…` values back into absolute paths against the project directory.
3. **No volatile item** (section 2). Volatile items go to the sidecar.
4. **Hashes cover canonical bytes only.** Every 64-hex value in a canonical file is one of the following:
   - (a) the SHA-256 of the bytes of a declared input file;
   - (b) the SHA-256 of the bytes of a canonical file;
   - (c) `sha256_json` of an object built only from canonical content. This includes key components, cache keys,
     relative-path maps, and run hashes, which are now computed over paths **relative to the run folder**;
   - (d) a **content hash** of a non-canonical file, stored under a field name ending in `content_sha256`. It is
     `sha256_json` of the file's canonical view: the parsed JSON with the section-2 keys removed at every depth and its
     paths rewritten by rule 2.

   Raw SHA-256 values of non-canonical files go to the sidecar only.
5. **Cache keys** (`state.analysis_key`, import and analysis keys) are computed over the canonical forms of their
   components. A relocated copy of a project therefore keeps its keys.
6. **Names.** No canonical file name contains a time stamp, a process id or a random value.

## 5. Backward compatibility

- Readers accept projects written by 0.4 before this change: state schema `rnplens-project-state-1` and cache schema
  `rnplens-cache-entry-1`, which have absolute paths and inline time stamps. A history may mix both schemas.
- The parent-hash chain stays valid.
- A recorded answer whose dependency hash was computed by the earlier run-hash formula is still recognised as
  unchanged when its files are unchanged.
- Because keys are now computed over canonical components, the first `rnplens update` of an old project after the
  change may recompute an analysis. The result is a new version, and the update report lists which key components
  changed. Old directories are never rewritten.
- A test builds an old-format project with the pre-change writer behaviour and reads, verifies and updates it with the
  new code.

## 6. Requalification retest (frozen)

**Cases.** There are four independent development cases. None is 24BR or an excluded target.

| case | source (read only) | runs |
|---|---|---|
| 1VTM | `scratch_agent/assistant_dev_tasks/d2_1VTM_agreement/{run_A,run_B,protein.fasta,rna.fasta}` | 2 runs x 5 Boltz-2 samples |
| 7K9D | `scratch_agent/assistant_dev_tasks/d1_7K9D_agreement/{run_A,run_B,protein.fasta,rna.fasta}` | 2 runs x 1 sample |
| 2JEA | `PCfold3D-RNP/outputs/rnpbench/pilot/boltz/exec_{A,B}/2JEA/boltz_results_2JEA/predictions/2JEA/{2JEA_model_*.pdb,confidence_2JEA_model_*.json}`; FASTA from `pilot/inputs/boltz/2JEA.yaml` | 2 x 5 |
| 2Q66 | the same layout for 2Q66 | 2 x 5 |

- Inputs are prepared once by `records/replay/retest/prepare_inputs.sh`, which also lists their sha256.
- Nothing under `pilot/references`, `pilot/audit`, any score folder, or any other target is opened.

**Workflow.** `records/replay/retest/retest_case.sh` runs the managed-project lifecycle in this order:
1. creating the project with an ambiguous third run (a truncated-RNA copy of run_B; expected exit 3);
2. listing the clarification request;
3. recording the answer `exclude_run`;
4. a no-change update;
5. the region rule of demonstration 1 and `rnplens region`;
6. `export-methods`;
7. `explain structures`;
8. menu item C with the local, deterministic follow-up;
9. an update after the 0.4 outputs (defect D1 path);
10. removing the ambiguous run;
11. `--versions` and `--status`.

Every step must end with its listed exit code, or the run is INCOMPLETE. No language model is called.

**Two independent runs per case**, both on karyon, with the code at the step-C implementation commit (its hash is
recorded in the report):
- **first run**: case root `scratch_agent/v04/replay-2/retest/<T>/first_<UTC>/`;
- **second run**: case root `scratch_agent/v04/replay-2/retest/<T>/second_copy_<UTC>/`, with a different absolute
  directory and a different working-directory name.

The second runs of all cases start after the first runs of all cases have finished, and at least 120 s after the last
of them. Both runs use the project directory name `project` and the inputs directory `in/`, so the relative layout is
the same. Each run has its own `TMPDIR`.

**Pass rule** (implemented in `records/replay/retest/check_pair.py`, frozen with this contract). A case **PASSES** if
and only if all three criteria hold:
- **(0)** both runs completed, with every step at its expected exit code;
- **(i)** the set of canonical files (section 3 patterns) is non-empty and equal in both runs, and every canonical file
  is byte-identical;
- **(ii)** the scientific comparison is equal. `records/replay/trace_replay_diffs.py`, run over the two case roots,
  must find:
  - no file with verdict `CONTENT`, `UNRESOLVED` or `DEMO_TOOLING`;
  - no file present in only one run;
  - every recorded follow-up evidence hash equal to its recomputation.

The requalification **PASSES** only if **all four cases** pass.
- Any failure is reported as a failure, per case and per file.
- A case is never re-run to change a completed result.
- A run that stops for an infrastructure reason (lost connection, full disk) may be repeated once, from scratch, in new
  directories, and the incident is reported.
- If the retest fails, the failure is the result. A fix and a further retest would need a new pre-registration
  (contract amendment or version 2).

**Smoke test (not part of the retest).** Before this freeze, the workflow script was run twice on the development
target 2QQP, which is not a retest case, with the unchanged `cf81acd` code. This confirmed that every step reaches its
expected exit code. Its outputs are not evidence for either property. The record is
`records/replay/retest/SMOKE_2QQP_cf81acd.md`.

## 7. Frozen files (sha256 at the freeze commit)

The commit that adds this contract lists them in its message. The sha256 values are in
`records/replay/retest/FROZEN_SHA256.txt`.

## Amendments

**Amendment 1 (16-17 Oct 2026, before the retest; after the step-C development tests, before any retest run).**

**Finding.** The step-C unit test of contract rule 4 (`tests/test_determinism.py`) found one hash in canonical state
files that covers a file outside the section-3 list:
- the field is `correspondence/<group>/<structure>/used_sha256`;
- the file it covers is a **derived structure copy**, `imports/v*/<group>/derived/<id>/<file>`, which the importer
  writes when an answer accepts a chain mapping or renumbering.

The copy is computed from an input file by a fixed transformation. It was byte-identical after relocation in the
test.

**Change.** The pattern `imports/v*/*/derived/*/*` is added to the canonical list (section 3, and
`retest/canonical_artifacts_v1.json`). Its writer is the importer, a 0.3 route, unchanged; it already writes these
copies deterministically.

**Unchanged.** Nothing else changes: the cases, the workflow, the pass rule, and `check_pair.py`, which reads the list
from the JSON file. The retest workflow answers only a construct question, so it is not expected to produce derived
copies. New sha256 values are in `retest/FROZEN_SHA256.txt`.

**Amendment 2 (17 Oct 2026, after the 66d186c retest FAILED; before any re-run).**

**Made after a failure.** This amendment was written **after** the frozen retest at integration HEAD `66d186c`
had been run and had **FAILED**. It is not a pre-registration. The failing results are recorded as found in
`records/replay/retest/results_66d186c/` (see `AS_FOUND.md` there) and are not changed. Those runs are not repeated to change their result. The earlier
PASS records are unchanged (the step-D retest at `891aeaf` and its later repeats), as is the FAILED demo-2 check.

**Observed failure.** The v1 retest (`retest/run_retest.sh`, 4 cases) gave FAIL 0/4. In every case, criterion (0) held, and all canonical files were byte-identical (criterion (i)). Only criterion (ii) failed. In it, `evidence_hash_recomputation_equal` was false for every
follow-up record. All other parts of (ii) held: no `CONTENT`, `UNRESOLVED` or `DEMO_TOOLING` file and no unpaired
file.

**Cause, from the records.** Round 3 (track/replay-r3, merged before `66d186c`) gave follow-up records a version
field, `evidence_hash_version`. New records declare `rnplens.followup.evidence.2`, the location-independent
definition of `PORTABILITY_TEST_v1.md` section 3. The tracer `trace_replay_diffs.py` recomputes every evidence hash
with the definition-1 rule, so it cannot reproduce a definition-2 hash.

`r3b/confirm_evidence_definition.py` checked the 26 follow-up records of the v1 and v2 trees at `66d186c`. Its output
is `r3b/evidence_definition_66d186c.json`:
- all 26 declare `rnplens.followup.evidence.2`;
- the definition-1 recomputation equals 0 of 26;
- `rnplens_assistant.followup.evidence_hash` under the declared definition equals 26 of 26;
- each record's plan carries the same hash.

**Change.** The single change is to the clause "every recorded follow-up evidence hash equal to its recomputation" of
criterion (ii). The checker now recomputes each follow-up's evidence hash **under the definition the record declares**
in `evidence_hash_version`:
- **Field absent:** definition 1, the earlier inline rule, unchanged.
- **Field present:** `followup.evidence_hash(statements, tool_log, P, A, version=<declared>)`, where:
  - the statements come from the sibling `followup_answer.json`;
  - the tool log is the record's;
  - P and A are the import and analysis directories of the state version whose analysis `main` is the record's
    analysis.
- **A definition that cannot be computed**, for example an unknown one, is unequal.

The code change is in `records/replay/trace_replay_diffs.py` (`Tree._declared_evidence_hash`, and a `definition`
entry in each `derived_check` row). `tests/test_portability.py::test_tracer_recomputes_under_the_declared_definition`
tests it.

**Unchanged.** No other criterion, file list, pattern, tolerance, case, workflow script, orchestrator or timing
changes; `check_pair.py` and `canonical_artifacts_v1.json` are unchanged.

**New sha256.** `trace_replay_diffs.py` changes from `2fa455488ed5c23158423cf246d07dae77834eb3ddcb9001d8872aefbb47c824` to `67ffb447880ceb006bd1bd78cfc98f63fee45485e36f7485183ae5562abb5e9c`. The new value is in `retest/FROZEN_SHA256.txt`; the contract file's own entry there changes with this amendment. The re-runs made
after this amendment are labelled **post-amendment retests**.
