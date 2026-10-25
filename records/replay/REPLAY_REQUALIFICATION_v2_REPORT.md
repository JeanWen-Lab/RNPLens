# Replay requalification v2: report (track `replay`, round 2)

- **Contract.** `records/replay/DETERMINISM_CONTRACT_v2.md`. It was pre-registered at `3e13000`, before any round-2
  code change. Amendment 1 was added at `3df760d`, before the retest.
- **Code under test.** `3df760d62ece77e3855e3bc5457edfa5c4f21b24`, branch `track/replay-r2` on base `b3374e4`, with a
  clean working tree (`results/code_status.txt` is empty).
- **Machine.** karyon, RNPLens `0.4.0.dev0`.
- **Frozen files.** All 13 files of `v2/FROZEN_SHA256_v2.txt` verified OK before the run (`results/frozen_check.txt`).
- **Raw records.** Everything is in `records/replay/v2/results/`.

## 1. Status (owner's three levels)

| level | status |
|---|---|
| **L1 Numerical / evidence reproducibility** | **Supported.** v1: 4 cases. v2: 3 new cases × 2 pairs, including a moved project. Every file of every pair has only volatile differences: no `CONTENT`, no `UNRESOLVED`, no unpaired file. All 24 follow-up evidence-hash recomputations (4 per pair) are equal; they cover 18 distinct records, 2 per tree |
| **L2 Canonical-file byte reproducibility** | **PASSED.** v1: the v1 canonical files on 4 cases (unchanged). v2: the PROMISED set (v1 canonical files, the canonical projections of every JSON/text output, figures, viewer copies and assets) is byte-identical in all 6 pairs. This holds for 3 cases, both later replay elsewhere and **moved-project replay**. The moved copy reused its analysis and recomputed nothing |
| **L3 Complete managed-project byte reproducibility** | **NOT established, and not claimed.** Raw outputs still carry volatile fields by design. 38–39 of 53–57 raw files differ in bytes between first and second runs, and 4 differ in each moved pair (section 4). Every scientifically meaningful field of those files is promised through their projections |

**Unchanged by this report:**
- **The original demonstration 2 replay check (24BR) remains FAILED.** The 24BR case here is a new run on the pilot
  data and does not re-label that check.
- v1's PASS records are unchanged.

## 2. What was run

| case | inputs (read only) | protein / RNA | note |
|---|---|---|---|
| 2QQP | pilot `exec_A`/`exec_B` Boltz-2, 5 + 5 models (`results/prepared.sha256`) | 75 aa / 4 nt | v1 used it only for a smoke test |
| 2XGJ | the same layout | 1010 aa / 5 nt | never used before |
| 24BR | the same layout | 327 aa / 4 nt | **demonstration 2's target.** Its inputs come from the same pilot runs as the demo's task, not from the demo's files |

Each case ran the frozen workflow (`retest_case_v2.sh`, then `continue_case_v2.sh`, through `run_retest_v2.sh`).
No language model was called; the scripted follow-up used the stub client.

**Run timeline (`results/runs.tsv`):**
- **R1:** 01:10:22–01:10:37Z, base workflow then continuation. The moved copy M was taken with `cp -a` right after
  each base workflow.
- **R2:** started 01:12:42Z, which is 125 s after the last R1 continuation, in `second_copy_*` directories.
- **M continuations:** 01:12:57–01:12:59Z, in `moved_elsewhere/<T>_copy_*`.

All 18 runs, copies and continuations exited 0, and every step reached its expected exit code. `13_group_diff` was
skipped, as the frozen script provides, for 2XGJ and 24BR: no engine-pick group had a next group. It ran for 2QQP.
The skipped steps are the same in each pair.

**Disclosed property of these cases.** All three RNAs are short (4, 5 and 4 nt). The region rule therefore chose
the whole RNA (1–L), so the continuation's "whole-RNA" region and view were the same as the base region. They
**rewrote** `region_1-L/` and `viewer_1-L/` after `export-methods` had hashed them. This exercised the
projection-index path of contract 4.5 (a hash of an earlier version of a rewritten file). A case with a longer RNA
would have exercised a new region directory instead.

## 3. Results per case and pair (frozen pass rule, `check_pair_v2.py`)

| case | pair | (0) completed | (i) promised byte-identical | (i-b) coverage | (ii) scientific | verdict |
|---|---|---|---|---|---|---|
| 2QQP | first vs second | ✓ | 117/117 (57 projections) | 0 / 0 missing | 83 differing files, all VOLATILE_ONLY; 0 unpaired | **PASS** |
| 2QQP | first vs moved | ✓ | 117/117 | 0 / 0 | 15 differing, all VOLATILE_ONLY; 0 unpaired | **PASS** |
| 2XGJ | first vs second | ✓ | 113/113 (53 projections) | 0 / 0 | 84 differing, all VOLATILE_ONLY; 0 unpaired | **PASS** |
| 2XGJ | first vs moved | ✓ | 113/113 | 0 / 0 | 15 differing, all VOLATILE_ONLY; 0 unpaired | **PASS** |
| 24BR | first vs second | ✓ | 113/113 (53 projections) | 0 / 0 | 83 differing, all VOLATILE_ONLY; 0 unpaired | **PASS** |
| 24BR | first vs moved | ✓ | 113/113 | 0 / 0 | 15 differing, all VOLATILE_ONLY; 0 unpaired | **PASS** |

**Overall: PASS** (`results/OVERALL`).

**Scientific trace.** The two trees hold 261/261 files for 2QQP and 252/252 for 2XGJ and 24BR. Byte-identical files:

| case | first vs second | first vs moved |
|---|---|---|
| 2QQP | 178 | 246 |
| 2XGJ | 168 | 237 |
| 24BR | 169 | 237 |

The leaf classes of the differing files are `ABS_PATH`, `TIMESTAMP`, `DURATION`, `ID`, `HASH:VOLATILE_ONLY`,
`TEXT_WITH_HASH:VOLATILE_ONLY`, `COMPOSITE:VOLATILE_ONLY` and `VOLATILE_TEXT`. Counts are in
`results/summary_details.json`.

**Per-file results.** `v2/results/promised_files_v2.tsv` has one row per promised file, case and pair: 686 rows,
all `BYTE_IDENTICAL`. The full records are in `v2/results/check_<case>_<pair>.json`. For 2QQP, the 117 promised files
are:
- 57 projections;
- 34 v1 canonical files;
- 22 viewer structure copies and Mol* assets;
- 2 figures;
- 2 JSON/text outputs with no projection extension: `view.mvsj` and `view_data.js`, which are byte-identical
  themselves.

**Moved project.** In all three cases M's head state records `analyses/v0004/main` as reused (computed in `v0004`).
M has exactly one analysis directory. At `b3374e4` the moved copy recomputed (`v0008`); that no longer happens.
Former-location aliasing (contract 4.2.1 / 4.4) keeps the keys.

## 4. Measured, not gating (contract section 6)

| case | raw files that differ in bytes, first vs second | raw files that differ, first vs moved | (iii) M files outside sidecars that reference R1's root: promised / non-promised |
|---|---|---|---|
| 2QQP | 38 of 57 | 4 of 57 | 0 / 34 |
| 2XGJ | 39 of 53 | 4 of 53 | 0 / 33 |
| 24BR | 38 of 53 | 4 of 53 | 0 / 33 |

- **Raw files are why L3 is not established.** These are raw files that have a projection; each differs only in
  volatile items, as criterion (ii) shows.
- **(iii)** Most of the root-referencing files in M are byte copies inherited from R1 before the move: logs, importer
  `manifest.json` and `report_contract.json`, `summary.json`, Report records, explain and follow-up outputs. The files
  M rewrote, for example `region.json`, `viewer_manifest.json` and `provenance_manifest.json`, still name R1's
  structure paths, because the copied 0.3 importer manifest records absolute paths.

  **M's continuation therefore read structure files at R1's location while R1 existed.** This limitation was stated
  before the run. Its scientific outputs are the same as R1's (criterion ii), but a moved project whose original
  location is deleted was **not** tested. No promised file references R1's root.

## 5. Development history before the retest (disclosed; not evidence)

All development checks ran on 1VTM, which is not a v2 case.

| when | code | result |
|---|---|---|
| before the freeze | `b3374e4` | `check_pair_v2.py` run on the step-1 classification trees, only to confirm it runs. FAIL: no projections existed, and the moved copy recomputed |
| smoke 1 | `7ab9657` | **FAIL**, both pairs. (a) The tracer read the new `projection_index.json` sidecar (hash-keyed map) as content. (b) A time stamp inside a JSON string (`"detail": "opted in (<ISO>, --yes)"`) stayed in the follow-up record projection; the provenance manifest differed as a consequence. This led to **Amendment 1**: time stamps masked inside JSON strings, and the index stored as a list in write order |
| smoke 2 | `3df760d` | **PASS**, both pairs (117/117 promised byte-identical; 0 not volatile; moved: 0 promised / 34 non-promised root references) |

Nothing was re-run after the retest. The retest ran once, from scratch, in `scratch_agent/v04/replay-2/retest_v2_3df760d`.

## 6. Test suites

| where | code | result |
|---|---|---|
| macOS (local) | `b3374e4` baseline | 604 passed, 1 failed, 19 skipped (= owner's record). The failure is the known `tests/test_workflow_analyse.py::test_report_numbers_equal_the_rc3_expected_output` |
| macOS (local) | `3df760d` | **612 passed, 1 failed (the same known test), 19 skipped** (+8 = `tests/test_determinism_v2.py`) |
| karyon | `3e13000` (code identical to `b3374e4`) | 612 passed, 12 skipped |
| karyon | `3df760d` | **620 passed, 12 skipped** |

No existing test was edited. One test file was added.

## 7. Deviations and limitations (complete list)

1. **L3 not established**: raw files differ (section 4). Only the promised set is byte-identical.
2. **The moved copy reads the original location's structure files** while that location exists (section 4, (iii)).
   Deleting the original before continuing was not tested.
3. **The raw follow-up `evidence_sha256` is still location-dependent.** `assistant/rnplens_assistant/followup.py` is
   pinned by LIVE_QUALIFICATION_v1 and was not edited. The location-independent value is `evidence_content_sha256`
   in `followup_record.json.canonical.json`. The required pinned-file change is listed in contract section 7.
4. **New files appear inside managed projects.** These are the `*.canonical.json` / `*.canonical.txt` projections,
   including in `followup/fu_NNNN/` and next to `imports/vNNNN/main/.rnplens/consent.json`, plus the sidecar
   `.rnplens/run/projection_index.json`. `export-methods` lists the projection files among the outputs in
   `provenance_manifest.json`, because it lists the analysis directory. Any live-qualification expectation that counts
   files in those directories must allow for them. No pinned file was edited.
5. **Projects written before v2** get projections only for files written after the upgrade, and for new import and
   analysis directories. Projection coverage (i-b) is not claimed for older outputs.
6. **Case properties.** The RNAs are short, so the whole-RNA continuation region equals the base region (section 2).
   `group-diff` ran only for 2QQP.
7. **24BR is demonstration 2's target.** It was run here from the pilot data. The demo's FAILED check stands.
8. **Archive packaging.** In the result archive, three `check_*_first_vs_second.log` files matched two tar globs and
   were stored twice. On extraction the duplicates were skipped; the files are intact.
9. **`.mvsj` is not a projection extension.** An unfrozen design note written before the contract listed `.mvsj`
   among the text projection extensions. The frozen contract (`3e13000`, section 3) and the frozen checker list only
   `.json .md .txt .html .tsv .svg .log`, and the implementation follows the frozen list. As a result,
   `viewer_*/view.mvsj` and `view_data.js` are promised as raw files. They were byte-identical in all 6 pairs,
   including the moved pair (`promised_files_v2.tsv`).
10. **macOS baseline count is not stable.** Two runs of the full local suite at `b3374e4`, both in **this session**
    on the same checkout, gave different counts:
    - an earlier run: `1 failed, 603 passed, 19 skipped`;
    - the baseline run used here: `1 failed, 604 passed, 19 skipped`, which matches the owner's record.

    One local test therefore passes or is collected inconsistently at the exact commit being qualified. It was not
    identified in this round. The round-2 comparison (604 → 612, +8 new tests, same known failure) uses the runs
    reported in section 6. Section 6's baseline row should be read with this note.
