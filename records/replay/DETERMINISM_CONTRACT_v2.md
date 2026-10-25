# RNPLens 0.4 determinism contract, version 2 (pre-registered)

Track `replay`, branch `track/replay-r2`, base `b3374e4`. This contract was written and committed **before any code
change** of round 2, and before any v2 retest run. The commit order on the branch shows this.

It governs:
- the round-2 implementation;
- the v2 retest, reported in `REPLAY_REQUALIFICATION_v2_REPORT.md`.

**What it leaves unchanged:**
- `DETERMINISM_CONTRACT_v1.md`, its amendment and its records are unchanged. **v1's PASS on 1VTM, 7K9D, 2JEA and 2Q66
  stands exactly as recorded**, for the v1 canonical files only.
- **The original demonstration 2 replay check remains FAILED.** Nothing here re-labels it.

Changes after the freeze are made only as numbered amendments at the end. Each amendment states whether it came
before or after the retest.

## 1. Release status levels (owner, 17 Oct 2026)

| level | meaning | evidence |
|---|---|---|
| L1 numerical and evidence reproducibility | same numbers, evidence records and interpretations | v1 retest, all files; v2 retest criterion (ii) |
| L2 canonical-file byte reproducibility | the promised files are byte-identical | v1: the v1 canonical files on 4 cases. v2: the PROMISED set of section 3 on the v2 cases, including a moved project |
| L3 complete managed-project byte reproducibility | **every** file of the managed project is byte-identical | **not claimed by v2**. v2 promises every scientifically meaningful field byte-identically through projections, but raw files that carry volatile fields are not byte-identical. Their count is measured and reported |

## 2. Field classes (from `NONCANONICAL_FIELD_CLASSIFICATION.md`)

| class | meaning |
|---|---|
| (a) | volatile execution metadata |
| (b) | derived from volatile metadata |
| (c) | scientifically meaningful |

**Owner's rule:** a (c) field is never excluded from the promised set because determinism is inconvenient. Every (c)
field of every output inside the managed project must lie in a promised file.

## 3. The promised set (v2)

For a managed project directory `project/`:

> **PROMISED** = every regular file under `project/` except
> 1. sidecars, i.e. files under `project/.rnplens/run/`;
> 2. any file `F` that has a canonical projection `F.canonical.json` or `F.canonical.txt`. The projection is promised
>    instead of `F`.

This includes:
- the v1 canonical files;
- every projection;
- figures (`contact_map.png`, `region_map.png`);
- viewer structure copies and bundled Mol* assets;
- derived structure copies;
- every JSON or text output that needs no projection.

**Projection coverage.** Every file under `project/` must have its projection if all of these hold:
- its extension is `.json`, `.md`, `.txt`, `.html`, `.tsv`, `.svg` or `.log`;
- it is not under `project/.rnplens/`;
- it is not a v1 canonical file;
- it is not itself a projection.

The projection of `F.json` is `F.json.canonical.json`; that of any other such file is `F.canonical.txt`.

**Sidecars** are the only exclusion. The classification found no (c) field in them.

## 4. Canonical projection (the transform)

### 4.1 Writing projections

Projections are written for every file inside a managed project, meaning a directory whose nearest ancestor holds
`.rnplens/HEAD`, apart from files under that ancestor's `.rnplens/`, v1 canonical files and projections. Two places
write them:
1. `rnplens.provenance.atomic_write_json` and `atomic_write_text`, whenever they write such a file. These are the
   writers of region, explain, follow-up, consent, Methods, groups and the viewer. Their code is **not** edited.
2. The managed pipeline (`incremental.py`), after every import and every analysis, for every eligible file of the new
   directory. These are the 0.3-route files: importer manifest and contract, `summary.json`, Report and Diagnose
   records, HTML and logs.

### 4.2 JSON projection

`P(F)` is the canonical JSON text (`indent=1`, sorted keys, ASCII, trailing newline) of `F`'s object, with these steps
applied in order:
1. **Paths.** Absolute paths are written project-relative, by v1 rule 2. In addition, paths under a **former** location
   of the project are written as if they were under the current one. A former location is any `execution.project_root`
   recorded in the project's state sidecars that differs from the current root. The parent folder of a former location
   is treated the same way.
2. **Volatile keys are removed at every depth.** These are the v1 volatile keys plus `command`, `argv`,
   `working_directory`, `cwd`, `pid`, `hostname`, `host`, `project_root`, `platform`, `python` and `executable`.
3. **Consent ids** `consent-NNNN-<8 hex>` become `consent-NNNN`, the record counter.
4. **Hashes over volatile bytes.** Any 64-hex value, alone or inside a string, that equals the raw SHA-256 of a
   projected file `G` inside the project becomes `projection-sha256:<SHA-256 of P(G)>`. `G` is projected if it has, or
   would have, a projection. The match is against `G`'s current bytes, or any earlier version of `G` recorded in the
   projection index (4.5). The new value can be checked with `sha256sum G.canonical.*` for a current `G`. Hashes of
   inputs and of promised files are unchanged.
5. **Follow-up evidence hash.** `evidence_sha256` is removed. In the projection of a `followup_record.json`, the key
   `evidence_content_sha256` is added:
   - it is `sha256_json({"statements": S, "tool_log": T})`;
   - `S` is the `statements` list of the sibling `followup_answer.json` projection;
   - `T` is the record projection's `tool_log`, with each entry reduced to `tool`, `call`, `status`, `outputs` and
     `message`.

   This is the location-independent evidence hash. The raw `evidence_sha256` remains (b) in the raw file. It is written
   by `rnplens_assistant/followup.py`, which LIVE_QUALIFICATION_v1 pins, so the integrator must make that change
   (section 7).

### 4.3 Text projection

The same transform is applied to the text, as substrings: paths, consent ids and hashes. In addition, ISO-8601 time
stamps and compact `YYYYmmddTHHMMSSZ` stamps become `<time>`.

### 4.4 Keys of a moved project

The cache keys of the managed pipeline are computed with the same path rule 4.2.1. A copy of a project at another
absolute path therefore keeps its keys and reuses its work.

### 4.5 Projection index (sidecar)

Each time a projection is written, the projector adds `raw SHA-256 of F → SHA-256 of P(F)` to
`<project>/.rnplens/run/projection_index.json`:
- the file has the form `{"raw_to_projection": {...}}`;
- entries are only added, never removed;
- it is a sidecar, so it is not promised.

A file can be rewritten after another file recorded its hash. This was observed at `b3374e4` on 1VTM: the continuation
`view` rewrote `viewer_1-3/viewer_manifest.json` after `export-methods` had recorded its hash in
`provenance_manifest.json`. The recorded hash still maps to the projection of the version that was hashed. Projections
are computed when their file is written, as a snapshot.

## 5. Not changed in round 2

- No qualified number and no frozen scientific value changes.
- No file that LIVE_QUALIFICATION_v1 pins is edited: `assist.py`, `doctor.py`, and the assistant sources including
  `followup.py`, `consent.py` and `evidence.py`.
- Raw outputs keep their formats. Readers that need absolute paths keep getting them, from the raw files and from the
  in-memory forms.

## 6. Retest v2 (frozen)

### Cases

There are three development cases. None was a v1 retest case, and none is an excluded target.

| case | source (read only) | note |
|---|---|---|
| 2QQP | `PCfold3D-RNP/outputs/rnpbench/pilot/boltz/exec_{A,B}/2QQP/boltz_results_2QQP/predictions/2QQP/{2QQP_model_*.pdb, confidence_2QQP_model_*.json}`; FASTA from `pilot/inputs/boltz/2QQP.yaml` | in v1 a smoke-test target only (records `retest/SMOKE_*.md`) |
| 2XGJ | the same layout for 2XGJ | never used before |
| 24BR | the same layout for 24BR | **24BR was demonstration 2's target.** Its inputs there were the development task `d4_24BR_compare` built from the same pilot runs. The demonstration's failed check is not re-run or re-labelled by this case |

Inputs are prepared once by `records/replay/v2/prepare_inputs_v2.sh cases`, which lists their sha256.

### Workflow

The base workflow is `records/replay/v2/retest_case_v2.sh`:
- the v1 lifecycle;
- `explain evidence`;
- `view`;
- `group`, and `group-diff` when an engine-pick group has a next group (otherwise recorded as skipped);
- the scripted Codex follow-up path, with a stub client, no model and no Codex process;
- the update after outputs, the removal of run_C, `--versions` and `--status`.

The continuation is `records/replay/v2/continue_case_v2.sh`:
- a no-change update;
- a region over the whole RNA;
- `explain region_mapping`;
- `export-methods`;
- `view` over the whole RNA;
- `update --report`;
- `--status`.

No language model is called.

### Trees per case

The orchestrator is `records/replay/v2/run_retest_v2.sh`; it adds no rule. Each case produces three trees on karyon,
with the code at the round-2 implementation commit:
- **R1**: `retest/<T>/first_<UTC>/`, the base workflow. Right after it, R1 is copied with `cp -a` to M. Then R1 runs the
  continuation.
- **R2**: `retest/<T>/second_copy_<UTC>/`, the base workflow and the continuation. It starts at least 120 s after the
  last R1 continuation, in another absolute directory with another working-directory name.
- **M**: `retest/moved_elsewhere/<T>_copy_<UTC>/`. This is the **moved-project replay**: R1's project and inputs copied
  to another absolute path after its base workflow, then continued there, after all R2 runs. R1 stays in place.

Each run has its own `TMPDIR`.

### Pass rule

The rule is implemented in `records/replay/v2/check_pair_v2.py`, which is frozen with this contract. A case **PASSES**
if and only if both pairs (R1, R2) and (R1, M, `--moved`) satisfy all four criteria:
- **(0)** both trees completed: every base and continuation step reached its expected exit code, and the skipped steps
  are the same in both;
- **(i)** the PROMISED sets (section 3) are equal and non-empty, and every promised file is byte-identical;
- **(i-b)** projection coverage holds in both trees;
- **(ii)** scientific equality holds. The step-A trace runs over the two case roots, with two v2 rules:
  - with `--moved`, R1's root is also recognised in M;
  - a hash that has no common target in the two trees, i.e. a former version of an overwritten file, is resolved when
    both trees' projection indexes map it to the same projection hash.

  The trace must report:
  - no file `CONTENT`, `UNRESOLVED` or `DEMO_TOOLING`;
  - no unpaired file;
  - every follow-up evidence hash equal to its recomputation.

  This criterion covers all files, including logs and raw files. A moved project that recomputes where the original
  reuses therefore fails here, as observed at `b3374e4`.

**Measured and reported, not criteria:**
- **(iii)** in M, the files under `project/` outside the sidecars whose bytes contain R1's absolute root, split into
  promised and non-promised files.
  - A promised file with R1's root would already fail (i).
  - Non-promised raw files are expected to keep R1's root. The 0.3 importer manifest records absolute paths, and v2
    leaves raw formats unchanged (section 5). M's continuation therefore still **reads** structure files from R1's
    location while R1 exists. This is a known limitation, stated before the run. It is not hidden by the projections.
- **raw files:** the number of non-promised raw files that differ in bytes between the two trees. This is the L3 status.

**The v2 retest PASSES only if all three cases pass.**
- Any failure is reported as a failure, per case, pair and file.
- A completed result is never re-run to change it.
- An infrastructure stop may be repeated once, from scratch, in new directories, and the repetition is reported.

### Development checks before the retest

The classification runs on 1VTM at `b3374e4`, which is not a v2 case, already ran the workflow; every step reached its
expected exit code. `check_pair_v2.py` was run on those trees before the freeze, to check that it runs; nothing was
tuned to pass.
- **first vs second: FAIL.** No projections exist yet: 57 files miss their projection, and 38 of 117 promised files
  differ. One hash is unresolved, the viewer-manifest case of 4.5.
- **first vs moved: FAIL.** The moved copy recomputed its analysis. 19 files are not volatile, the unpaired counts are
  2 and 54, and 43 promised files reference the original root. Post-implementation smoke runs, if any, are made on 1VTM only and are reported. They are not
evidence for the retest.

## 7. For the integrator (pinned files)

**Not done in round 2,** because `assistant/rnplens_assistant/followup.py` is pinned by `LIVE_QUALIFICATION_v1`. The
change that would make the raw follow-up `evidence_sha256` location-independent is in `followup.evidence_hash`:
- before hashing, replace every statement slot value that is the SHA-256 of a file inside the managed project by that
  file's projection hash, i.e. `rnplens.canonical` `projection-sha256:…`;
- equivalently, hash the record's canonical projection, as in 4.2.5.

This needs a re-pin of LIVE_QUALIFICATION_v1 before any live run. Until then, `evidence_content_sha256` in the record's
projection is the location-independent value.

## 8. Frozen files

The sha256 values are in `records/replay/v2/FROZEN_SHA256_v2.txt` and in the message of the commit that adds this
contract.

## Amendments

### Amendment 1 (before the retest; no v2 case had been run)

**Context.** The first post-implementation development smoke ran on 1VTM, which is not a v2 case, at code
`7ab9657`, in `scratch_agent/v04/replay-2/smoke_v2_1VTM_7ab9657`. Both pairs FAILED.
- **Moved pair.** All 117/117 promised files were byte-identical, and the analysis was reused. The one failure was
  criterion (ii) on the new sidecar `projection_index.json`: its keys are raw hashes, and the tracer reads a changed
  map key as content.
- **First vs second.** 115 of 117 promised files were identical.
  - The follow-up record projection kept an ISO time inside a JSON string value: `"detail": "opted in (<ISO time>,
    --yes)"`. Rule 4.2 masked times only in text files (4.3).
  - The Methods provenance manifest recorded that projection's hash, so it differed as a consequence.

**Changes.**
1. **Rule 4.2** gains a step after step 3. ISO-8601 and compact `YYYYmmddTHHMMSSZ` time stamps inside JSON string
   values (and keys) become `<time>`, exactly as in 4.3.
2. **The projection index of 4.5** becomes `{"schema": "rnplens-projection-index-2", "entries": [{"file",
   "raw_sha256", "projection_sha256"}, ...], "errors": [...]}`.
   - It is a list in write order, and the latest entry for a raw hash wins.
   - The tracer resolves each `raw_sha256` like any other hash.
   - `check_pair_v2.py` reads `entries`, or the earlier map if present. This is its only change.

**Unchanged.** Criteria (0), (i), (i-b) and (ii), the measured items, the cases, the workflow scripts, the
orchestrator and the timing. The smoke results above are development checks, not retest evidence. A second
development smoke on 1VTM after this amendment is reported in the v2 report.

### Amendment 2 (17 Oct 2026, after the 66d186c retest FAILED; before any re-run)

**Made after a failure.** This amendment was written **after** the frozen retest at integration HEAD `66d186c`
had been run and had **FAILED**. It is not a pre-registration. The failing results are recorded as found in
`records/replay/v2/results_66d186c/` (see `AS_FOUND.md` there) and are not changed. Those runs are not repeated to change their result. The earlier
PASS records are unchanged (the v2 retest at `3df760d` and the `589485b` repeats), as is the FAILED demo-2 check.

**Observed failure.** The v2 retest (`v2/run_retest_v2.sh`, 3 cases x 2 pairs) gave FAIL 0/6. In every pair, criteria (0), (i) and (i-b) held: all promised files were byte-identical, and projection coverage was complete. Only criterion (ii) failed. In it, `evidence_hash_recomputation_equal` was false for every
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
changes; `check_pair_v2.py`, `canonical_artifacts_v2.json` and the measured items (iii) and raw files are unchanged.

**New sha256.** `trace_replay_diffs.py` changes from `2fa455488ed5c23158423cf246d07dae77834eb3ddcb9001d8872aefbb47c824` to `67ffb447880ceb006bd1bd78cfc98f63fee45485e36f7485183ae5562abb5e9c`. The new value is in `v2/FROZEN_SHA256_v2.txt`; the contract file's own entry there changes with this amendment. The re-runs made
after this amendment are labelled **post-amendment retests**.
