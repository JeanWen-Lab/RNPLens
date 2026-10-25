# Track `replay`, round 2: hand-back

- **Base and branch.** Base `b3374e4`; branch `track/replay-r2`, in the local clone and the karyon track clone.
- **Not done.** No merge into protected branches, no tag, no push, no release. 0.4 remains a **development
  candidate**.
- **Delivery.** `git bundle create track_replay-r2.bundle b3374e4..track/replay-r2`. Its sha256 is given with the
  artifact.

## Commits (in order)

| commit | content |
|---|---|
| `0bb1c67` | Step 1: field-by-field classification of every non-canonical output, observed at `b3374e4` on 1VTM (first, second, moved copy). Files: `NONCANONICAL_FIELD_CLASSIFICATION.md` and `.json`, plus `v2/classify_fields.py` and the workflow scripts |
| `3e13000` | Step 2: `DETERMINISM_CONTRACT_v2.md` pre-registered **before any code change**, with the frozen tools `v2/check_pair_v2.py`, `v2/run_retest_v2.sh`, `v2/canonical_artifacts_v2.json` and `v2/FROZEN_SHA256_v2.txt`. Contract sha256 `e7fa4a59…`, as stated in the commit message |
| `7ab9657` | Step 3: implementation. New `src/rnplens/projection.py`; former-location aliasing in `canonical.Paths`; `provenance` hook; pipeline sweeps in `incremental`; `tests/test_determinism_v2.py`; `docs/reproducibility.md` section |
| `3df760d` | Contract Amendment 1, made before the retest after development smoke 1 on 1VTM failed: times inside JSON strings masked; projection index as a list. Matching `projection.py` and checker changes. Contract sha256 `3fc0fd7b…` |
| `3a6d6cd` | Step 4: v2 retest records (`v2/results/`) and `REPLAY_REQUALIFICATION_v2_REPORT.md` |
| (this file) | hand-back |

## Result

The v2 retest **PASSES** by the frozen rule: 3 cases (2QQP, 2XGJ, 24BR) × 2 pairs (first vs second, first vs moved).
All promised files are byte-identical (117 / 113 / 113 per tree), and no file shows a non-volatile difference.

| level | status |
|---|---|
| L1 numerical and evidence reproducibility | **supported** |
| L2 canonical-file byte reproducibility | **passed**: v1 on 4 cases; v2 on 3 cases including moved-project replay |
| L3 complete managed-project byte reproducibility | **not established**: raw files still differ, by design |

**Unchanged:** the original demonstration 2 check remains **FAILED**, and v1's records are unchanged.

## Test suites

| where | code | result |
|---|---|---|
| macOS | `b3374e4` | 604 passed, 1 failed (known: `test_workflow_analyse.py::test_report_numbers_equal_the_rc3_expected_output`), 19 skipped |
| macOS | `3df760d` | 612 passed, 1 failed (same known test), 19 skipped |
| karyon | `3e13000` (code = `b3374e4`) | 612 passed, 12 skipped |
| karyon | `3df760d` | 620 passed, 12 skipped |

No existing test was edited. `tests/test_determinism_v2.py` (8 tests) was added. The final commits (`3a6d6cd` and
this file) change only `records/`.

## Files changed outside `records/` (vs `b3374e4`)

- `src/rnplens/projection.py`: new.
- `src/rnplens/canonical.py`: `former_roots()`; `Paths(..., former=None)` aliasing. Behaviour is identical when the
  project never moved.
- `src/rnplens/provenance.py`: `atomic_write_json` and `atomic_write_text` call `projection.after_write`, which never
  raises.
- `src/rnplens/incremental.py`: `projection.sweep` after each import and analysis.
- `tests/test_determinism_v2.py`: new.
- `docs/reproducibility.md`: new section "Canonical projections (version 2)".

Not edited: `region.py`, `evidence_query.py`, `methods_export.py`, the importer, and every file pinned by
LIVE_QUALIFICATION_v1, including `assist.py`, `doctor.py` and `followup.py`. No qualified number changed.

## For the integrator

1. **Pinned-file change, not made.** The location-independent raw follow-up evidence hash would need a change in
   `assistant/rnplens_assistant/followup.py` `evidence_hash`, which is pinned. It should hash projection or content
   hashes instead of raw file hashes in statement slots (contract section 7). That needs a LIVE_QUALIFICATION_v1
   re-pin. Until then, use `evidence_content_sha256` in `followup_record.json.canonical.json`.
2. **Live qualification.** The provenance hook adds `*.canonical.*` files inside managed projects, including
   `followup/fu_NNNN/` and next to `imports/vNNNN/main/.rnplens/consent.json`. It also adds
   `.rnplens/run/projection_index.json`. `export-methods` then lists the projection files as outputs. Any live
   expectation that counts files in those directories must allow for them.
3. **Moved projects.** These now keep their keys and reuse work. Their raw files still point at the original
   location, through the 0.3 importer manifest's absolute paths. Running after deleting the original location was
   not tested.

## Deviations (complete)

See `REPLAY_REQUALIFICATION_v2_REPORT.md` section 7. In summary:
- L3 is not established.
- The moved copy reads the original location.
- The raw `evidence_sha256` is location-dependent (pinned file).
- New projection files appear in project directories.
- Older projects are only partly covered.
- The RNAs are short, so the continuation region equals the base region; `group-diff` ran only for 2QQP.
- 24BR is demo 2's target, run from pilot data.
- Amendment 1 was made after development smoke 1. It is disclosed, and was made before the retest.
- A tar duplicate-entry packaging note.
- `.mvsj` is not projected; frozen list followed, and the files are byte-identical raw.
- Two macOS runs at `b3374e4` in this session printed 603 and 604 passed (each 1 failed, 19 skipped). One local test is unstable and not yet identified.

## Proposed release-docs paragraph

> **Reproducibility of managed projects (0.4 development candidate).** Re-running the same inputs, answers and
> RNPLens version elsewhere, or later, reproduces every number and evidence record. This was checked on 7
> development cases: four for the v1 canonical files, three for v2. The canonical project records, and a canonical projection of every JSON and text output
> (`<file>.canonical.json` / `.canonical.txt`), are byte-identical. This holds also when a project folder is copied
> to another location and continued there; the copy reuses its earlier work. RNPLens does **not** promise that every
> raw file of a project is byte-identical. Raw outputs record when and where they were written. A copied project's raw
> files still name, and read, the original location's structure files. The earlier byte-identical replay check of
> demonstration 2 failed, and that result stands.
