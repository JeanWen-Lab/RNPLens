# Demo 2 replay: byte-level trace of every difference (step A, track `replay`)

Written 16-17 Oct 2026 on branch `track/replay` (base `cf81acd`). This is a **post-hoc explanation** of a failed
pre-registered check. **It does not change that check's verdict.** The pre-registered byte-identical replay check of
demonstration 2 (rule in `records/v04_integration/DEMOS_PLAN.md`, "Replay check") **FAILED** in both runs and remains
**FAILED**.

## 1. What was traced

The output trees were all still present on karyon and were read without being changed. Nothing was re-run for this step.

| run | original package | replay package | pre-registered record (sha256) | verdict |
|---|---|---|---|---|
| `demo2_run1` | `RNPLens_dev_0.4/work/demos/2_interactive_24BR` | `scratch_agent/v04/demos/replay/2_interactive_24BR_replay_20261016T132129Z` | `checks/replay_check.json` (`26db9c8a3ad3b2ba…`, identical to artifact `demo2_replay_check.json`) | FAIL, 22 DIFFERENT |
| `demo2_at_bdd137f` | `RNPLens_dev_0.4/work/demos/2_interactive_24BR_at_bdd137f` | `scratch_agent/v04/demos/replay/2_interactive_24BR_at_bdd137f_replay_20261016T140117Z` | `checks/replay_check.json` (`97a50bf58065fd44…`, identical to artifact `demo2_at_bdd137f_replay_check.json`) | FAIL, 22 DIFFERENT |

The post-hoc classifications (`replay_diff_classification_posthoc.json`, `3e47de13…` and `7564a162…`) were used only
for comparison. The classifier `demos/lib/classify_replay_diffs.py` replaced every 64-hex string with `<HEX>` without
asking what the hash covers. That is the gap the owner pointed out, and this trace closes it.

**Tools.** Both tools are committed here and are read-only:
- `records/replay/trace_replay_diffs.py` (sha256 `2fa45548…`);
- `records/replay/summarise_trace.py` (`6677a3f5…`).

They ran on karyon with `PYTHONPATH=<track clone at cf81acd>/src:…/assistant`. The derived-hash recomputations use
that code. Every derived hash reported as resolved **equals the recorded value**, which confirms each derivation
independently of the code version.

**Method.**
1. Every regular file in both trees was compared byte for byte. This includes `inputs/`, `logs/`, `.html`, `.md` and
   `.png` files, not only the `*.json` files of the pre-registered rule.
2. Each differing JSON file was re-serialised with a pointer-tagging copy of `json.dumps`. All JSON files reproduced
   their exact bytes (formats detected: indent 1, sorted or unsorted keys, with or without a final newline). Every
   differing line therefore maps to the JSON pointer it encodes.
3. Each differing leaf was put into one class:
   - `TIMESTAMP`;
   - `ABS_PATH`: equal after replacing each side's package root;
   - `DURATION` (`wall_s`);
   - `ID`: consent record ids;
   - `HASH`: a 64-hex value;
   - `COMPOSITE`: a string equal after the replacements above and with its embedded hashes resolved;
   - `ORDER`;
   - `CONTENT`: anything else.
4. Every differing hash was resolved on **each** side against three kinds of target:
   - the SHA-256 of every file in that tree;
   - `sha256_json` of every JSON subtree in that tree;
   - recomputed derived objects: `manifest_view`, `correspondence`, `selection`, `clarify.run_hash`,
     `incremental._group_inputs`, the import configuration, and `followup.evidence_hash`. The last one was rebuilt
     exactly as the code builds it, and the recomputed value equals the recorded `evidence_sha256` in all 4 records.
5. The covered object was then compared between the two trees, recursively. A hash is `VOLATILE_ONLY` only when every
   difference in the bytes or object it covers is itself volatile. A hash with no target would be `UNRESOLVED`; none
   remained.
6. Differing text files were attributed by line range, after the same replacements.

## 2. Result

| | `demo2_run1` | `demo2_at_bdd137f` |
|---|---|---|
| files: original / replay | 181 / 176 | 156 / 153 |
| byte-identical | 88 | 79 |
| bytes differ (paired) | 88 (50 JSON, 38 text) | 74 (40 JSON, 34 text) |
| pre-registered DIFFERENT files, all traced | 22 / 22 | 22 / 22 |
| differing lines not attributed to a pointer or class | 0 | 0 |
| differing hash values not resolved | 0 | 0 |
| **scientific content differs** (`CONTENT`) | **no** | **no** |
| verdicts | 87 VOLATILE_ONLY, 1 DEMO_TOOLING | 74 VOLATILE_ONLY |

**No number, evidence record or interpretation differs.** The remediation therefore proceeds (step B). The files that
carry the numbers are byte-identical in both runs:
- `report/contacts_by_output.json` (the authoritative per-structure contact record);
- `report/result.json`;
- `report_runs_BOLTZ2/contacts_by_output.json`;
- `region_1-4/region_contacts.tsv`;
- `followup/fu_*/evidence_summary.json`;
- `methods/methods.md` and `methods.txt`;
- `summary.html`, `region.html` and `update_report.html`;
- the PNG contact maps.

`summary.json` differs **only** in `/created_utc` and in the 10 `/inventory/structures/N/path` values (absolute paths).

Leaf-class totals over all differing files:

| class | run1 | bdd137f |
|---|---:|---:|
| `ABS_PATH` | 1329 | 1178 |
| `HASH` (all `VOLATILE_ONLY`) | 176 | 157 |
| `TIMESTAMP` | 57 | 48 |
| `COMPOSITE` (all `VOLATILE_ONLY`) | 7 | 7 |
| `ID` | 3 | 3 |
| `DURATION` | 1 | 2 |
| `ORDER` | 1 | 1 |
| text: `VOLATILE_TEXT` / `TEXT_WITH_HASH:VOLATILE_ONLY` / `SCRIPT_LOCATION` | 70 / 19 / 10 | 61 / 19 / 10 |
| `DEMO_TOOLING` | 1 | 0 |

## 3. What every changed hash covers

Each row is one kind of hash target. Every listed hash differs because the bytes or object it covers differ. The last
column gives the only kinds of difference inside those covered bytes. The same rows were found in both runs; the
counts are from run1.

| hash target (what the 64-hex value is the SHA-256 of) | hash values | referenced from (examples) | differences inside the covered bytes |
|---|---:|---|---|
| file `demo/imports/vNNNN/main/manifest.json` | 25 | `state …/groups/main/manifest_sha256`; `explain_evidence_*.json /statements/N/value`, `/provenance/inputs/N/sha256`; `followup_answer.json /statements/N/slots/v/value`; `region.json`, `methods_sources.json`, `followup_record.json /provenance/inputs/N/sha256`; cache `/files/manifest.json` | `/created_utc`; absolute `/inputs/N`, `/structures/N/{path,used_path,confidence_dir}` |
| file `demo/analyses/vNNNN/main/summary.json` | 21 | `state /analyses/main/summary_sha256`; `explain_evidence_* /statements/N/value`; `update_report.json /provenance/inputs/N/sha256`; cache `/files/summary.json` | `/created_utc`; absolute `/inventory/structures/N/path` |
| file `…/main/region_1-4/region.json` | 9 | `explain_evidence_* /statements/N/file_sha256`, `/provenance/inputs/N/sha256`; `provenance_manifest.json` | `provenance.created_utc`; absolute `provenance.{inputs/N/path, project, analysis, command}`, `/runs/N/structures/N/{path,used_path}`; hashes of `manifest.json`, `summary.json` and `report/rnplens_run.json` |
| file `…/report/rnplens_run.json` (Report run record) | 13 | `explain_evidence_* /statements/N/value`; `methods_sources.json`; `provenance_manifest.json`; cache | `created_utc`, absolute command arguments, input paths, working directory; sha256 of `report_contract.json` |
| file `…/report_runs_BOLTZ2/rnplens_run.json` | 3 | `provenance_manifest.json`; cache | as above, plus the sha256 of `report_runs_BOLTZ2/result.json` |
| file `…/report_runs_BOLTZ2/result.json` | 3 | `report_runs_BOLTZ2/rnplens_run.json /outputs/2/sha256`; `provenance_manifest.json`; cache | **only `/wall_s`** (0.06 vs 0.07 s). The pre-registered rule ignored `wall_s` and called this file IDENTICAL, but its hash changed |
| files `imports/…/report_contract.json`, `run_repeat_inputs/report_contract_BOLTZ2.json` | 6 / 5 | `report/rnplens_run.json /inputs/0/sha256`; `provenance_manifest.json`; cache | absolute `structure_path`, `confidence_dir` |
| files `…/diagnose_within_BOLTZ2/rnplens_run.json`, `…/main/commands.log` | 3 / 3 | `provenance_manifest.json`; cache `/files/*` | absolute paths, time stamps |
| file `demo/.rnplens/state/vNNNN.json` | 8 | `HEAD /sha256`; `state /parent_sha256`; `update_report.json /provenance/inputs/N/sha256` | the state-file differences (rows below), time stamps |
| subtree `cache/<key>.json#/meta/components` = `state /analyses/main/components` or `/groups/main/import_components` (the **cache key**) | 20 | `state /analyses/main/key`, `/groups/main/import_key`; `index.json /groups/main/key`; `update_report.json /analyses/main/{before,after}/key`; cache file names and `/key` | only component hashes in the five rows below |
| derived `manifest_view(manifest.json)` → `components/inputs_sha256` (analyse key) | 5 | state, cache | absolute paths only |
| subtree `state /correspondence/main` → `components/correspondence_sha256` | 5 | state, cache | map keyed by **absolute** structure paths |
| derived `_group_inputs(…)` → import `components/inputs_sha256` | 5 | state, cache | map keyed by absolute input paths (file hashes equal) |
| derived import config `{engine, case_id, answers, files}` → import `components/config_sha256` | 8 | state, cache | absolute `files` |
| derived `clarify.run_hash(run root)` | 32 | `state /inputs/runs/<abs>/sha256`; `depends_on/run:<abs>` of the recorded answer and the pending question; `logs/03_clarify_json.log` | map keyed by absolute paths (file hashes equal) |
| subtree `state /inputs/files` | 3 | import components | map keyed by absolute paths |
| derived `followup.evidence_hash` (documented as "measured content") | 5 | `followup_plan.json`, `followup_record.json /evidence_sha256`; `followup_scripted.json`; `logs/14_replay_fu_*.log`; `README.md` and `results.md` | **3 statement slot values that are themselves the SHA-256 of `manifest.json`**. The statements and tool log are otherwise equal after `_norm`. The "measured content" hash therefore depends on time and location through a file hash |

The cache-key chain is the main way volatile bytes reach scientific bookkeeping. An absolute path or a time stamp
changes four things in turn:
1. the hash of `manifest.json` or `summary.json`;
2. the component hashes;
3. the cache key;
4. the cache entry's file name, `index.json`, the state files, `HEAD` and the update report.

None of the covered differences is a number, evidence value or interpretation.

## 4. Root causes in the 0.4 code

| # | cause | where it is written |
|---|---|---|
| R1 | **absolute paths** in recorded content | `provenance.block` (`os.path.abspath` of every input); `importer` manifest `inputs`, `path`, `used_path`, `confidence_dir`; Report contract `structure_path`/`confidence_dir`; `summary.json /inventory`; managed-project state (`declared.inputs`, `inputs.files` keys, `correspondence` keys, `structure_files`, clarification ids `construct_mismatch:<abs root>`, `depends_on` keys, `exclusions`); `region.json provenance.{project,analysis,command}`; `explain_evidence` `roots`/`statements/N/root`/`text`; follow-up `slots/t/value` (texts carrying paths); consent `project`; Report `rnplens_run.json` command and working directory |
| R2 | **time stamps** inside content files | `provenance.block created_utc`; state `created_utc`, `recorded_utc`; cache `stored_utc`; importer and summary `created_utc`; consent `timestamp_utc`; follow-up `started_utc` and `user_confirmation.timestamp_utc`; time-stamped file names `cache/invalid/<key>.<YYYYmmddHHMMSS0000>.json` |
| R3 | **durations** | Report `result.json /wall_s` (`report_runs_BOLTZ2`); follow-up `tool_log/N/wall_s` (bdd137f run) |
| R4 | **hashes over R1-R3 bytes**: file hashes of files carrying R1/R2/R3, and `sha256_json` of objects keyed by absolute paths | section 3 |
| R5 | **ids derived from volatile records** | consent id `consent-NNNN-<first 8 hex of sha256(record)>`; the record contains `timestamp_utc` and the absolute project path |
| R6 | **order following hash-named files** | `checks/wording_scan.json /files` (demo tooling) lists files in walk order of `cache/<key>.json` names |
| R7 | **demonstration tooling** (not RNPLens output) | log lines naming the absolute folder of the driver scripts (`SCRIPT_LOCATION`, 10 lines: the original ran the scripts from `tracks/demos/RNPLens/demos/lib`, the replay from `<original>/scripts/lib`); in run1, `scripts/lib/replay.sh` of the original package was edited **after** the replay (the post-hoc classifier call was added; commit `7421948`), and the original holds 5 files (run1) / 3 files (bdd137f) added after the replay: `checks/*`, `scripts/lib/access_audit.py`, `classify_replay_diffs.py`, and one `.pyc` |

## 5. How this differs from the post-hoc classifier

The classifier's conclusion ("only timestamps, ids and hashes") turns out to be correct for these two runs. It was not
**shown**, because it treated every hash as harmless by pattern. This trace resolves every hash to the bytes it covers.
It also finds two things the pre-registered rule and the classifier did not surface:
1. **`report_runs_BOLTZ2/result.json`** was called IDENTICAL (with `wall_s` ignored), yet its bytes differ. Three hashes
   of it propagate into `rnplens_run.json`, `provenance_manifest.json` and the cache. A duration inside a canonical
   result file is enough to break byte identity.
2. **`followup.evidence_hash`** is documented as excluding run-time fields. It nevertheless covers statement slots
   whose values are the SHA-256 of `manifest.json`, so it changes whenever the project is moved or re-imported at
   another time.

## 6. Consequence for the remediation

Byte identity requires all of the following:
- R1: relative paths in canonical files;
- R2, R3 and R5: no time stamps, durations or time-derived ids inside canonical files, with these moved to a sidecar;
- R4: every hash inside a canonical file covers only canonical bytes, or is a hash of an input's own bytes;
- deterministic names and order: no time stamp in a file name in the canonical tree.

These requirements are frozen in `DETERMINISM_CONTRACT_v1.md` before any code change.

## 7. Files

| file | sha256 |
|---|---|
| `REPLAY_DIFF_TRACE.json` (per-run, per-file rows, hash families, byte-identical lists) | `1ba94a060ba2d3d199b18c10a374f386d1cbe70d44209432d7f111bdb6b5eca8` |
| `trace_full_demo2_run1.json.gz` (every leaf, every hash resolution, byte ranges) | `23f2627675d34d59e12fa210dc4b796dc1b2288480e48592221dd926b00484eb` |
| `trace_full_demo2_at_bdd137f.json.gz` | `13e321dc0027371954235d6ec1052a46f4fc745c6328b88b311daacac29845c1` |
| `trace_replay_diffs.py` | `2fa455488ed5c23158423cf246d07dae77834eb3ddcb9001d8872aefbb47c824` |
| `summarise_trace.py` | `6677a3f5ae1609361244f957469cafe88e830d7a5bd1b4b45dcae51cdb2cdafc` |

**Limits.**
- Classification is by explicit rules: root replacement, time-stamp patterns, a duration key list and hash
  resolution. A volatile field of a kind not listed would surface as `CONTENT`; none did.
- Text files are attributed by line range, not by pointer.
- The `SCRIPT_LOCATION` and `DEMO_TOOLING` classes apply only to demonstration logs and copied scripts, never to an
  RNPLens output.
