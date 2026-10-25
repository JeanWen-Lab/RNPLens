# PORTABILITY_REPORT_v1

Results of the pre-registered test `records/replay/PORTABILITY_TEST_v1.md`. It covers owner item 3B (copied
projects) and item 4, follow-up hash part. RNPLens 0.4 remains a development candidate. This report qualifies one
behaviour, the handling of copied and moved managed projects, on two development cases. It makes no claim about
structural accuracy.

## Verdict

**PASS.** 2QQP: 80 checks, 0 failed. 2XGJ: 80 checks, 0 failed (`records/replay/portability/results/v1_6ea4519/OVERALL`, `verdicts.tsv`).

| item | value |
|---|---|
| pre-registration | `36e6d31` (PORTABILITY_TEST_v1.md sha256 9558e05d…, FROZEN_SHA256.txt 6b5c574c…) |
| amendment | Amendment 1 at `cea804a`, before any code change or run (every RELINKED file raises `NOT SELF-CONTAINED`) |
| code under test | `6ea45197ac8114fce93a64a4896822e80c4b8367` on track/replay-r3, clean tree (`code_commit.txt`, `code_status.txt`) |
| frozen files | all 10 entries of `FROZEN_SHA256.txt` OK at the start of the run (`run_stdout.txt`); unchanged since `cea804a` |
| machine | karyon, karyon checkout of track/replay-r3, `RNPLens_dev_0.3/venv` interpreter, rnplens 0.4.0.dev0 |
| run root | `scratch_agent/v04/replay-3/portability_v1_6ea4519`; R1 = `2QQP/orig_20261017T074303Z`, `2XGJ/orig_20261017T074314Z` |
| repetitions | none. The run was made once and completed. |

The records are in `records/replay/portability/results/v1_6ea4519/`: checker output `check_<case>.json/.log`, driver records `<case>/portability_run.json`,
per-command logs `<case>/plogs/`, and base/driver/prepare logs.

## Checks per scenario (both cases identical)

| group | checks | failed |
|---|---|---|
| infra (no driver error, original restored, S4 file restored) | 1 | 0 |
| S0 R1 in place (control) | 11 | 0 |
| B1 follow-up record and plan carry `rnplens.followup.evidence.2` | 4 | 0 |
| S1 whole-case copy, original away | 11 | 0 |
| S2 project-only copy, originals away | 11 | 0 |
| S2b same copy after `relink --search R1.away/in` | 10 | 0 |
| S3 project-only copy, original present | 10 | 0 |
| S4 project-only copy, one original's bytes changed | 11 | 0 |
| S5 project-only copy, a different same-name file at the original path | 11 | 0 |

## Exit codes and notices per command

Read from the driver records. Exit 6 is the portability refusal.
**2QQP** (exit code; R = `PORTABILITY REFUSED`, N = `NOT SELF-CONTAINED`, W = `PORTABILITY WARNING`)

| scenario | analyse | explain | group | methods | region | replay_fu_0001 | replay_fu_0002 | update | view |
|---|---|---|---|---|---|---|---|---|---|
| S0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| S3 | 0 N | 0 N | 0 N | 0 N | 0 N | 0 N | 0 N | 6 R | 0 N |
| S4 | 6 R | 0 NW | 6 R | 6 R | 6 R | 6 R | 6 R | 6 R | 6 R |
| S1 | 6 R | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| S2 | 6 R | 0 W | 6 R | 6 R | 6 R | 6 R | 6 R | 6 R | 6 R |
| S2_relink | relink exit 0 |  |  |  |  |  |  |  |  |
| S2b | 6 R | 0 N | 0 N | 0 N | 0 N | 0 N | 0 N | 0 | 0 N |
| S5 | 6 R | 0 W | 6 R | 6 R | 6 R | 6 R | 6 R | 6 R | 6 R |
| S5_relink | relink exit 6; rejected listed |  |  |  |  |  |  |  |  |

**2XGJ** (exit code; R = `PORTABILITY REFUSED`, N = `NOT SELF-CONTAINED`, W = `PORTABILITY WARNING`)

| scenario | analyse | explain | group | methods | region | replay_fu_0001 | replay_fu_0002 | update | view |
|---|---|---|---|---|---|---|---|---|---|
| S0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| S3 | 0 N | 0 N | 0 N | 0 N | 0 N | 0 N | 0 N | 6 R | 0 N |
| S4 | 6 R | 0 NW | 6 R | 6 R | 6 R | 6 R | 6 R | 6 R | 6 R |
| S1 | 6 R | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| S2 | 6 R | 0 W | 6 R | 6 R | 6 R | 6 R | 6 R | 6 R | 6 R |
| S2_relink | relink exit 0 |  |  |  |  |  |  |  |  |
| S2b | 6 R | 0 N | 0 N | 0 N | 0 N | 0 N | 0 N | 0 | 0 N |
| S5 | 6 R | 0 W | 6 R | 6 R | 6 R | 6 R | 6 R | 6 R | 6 R |
| S5_relink | relink exit 6; rejected listed |  |  |  |  |  |  |  |  |

How to read these tables:
- **S1.** The whole-case copy is self-contained. Every reader works silently, and both follow-ups replay and match.
  Plain `analyse` on the recorded import refuses, because the recorded paths name R1. Its message advises
  `rnplens update`.
- **S2 and S4.** Every command that reads structure bytes refuses and names the file and `rnplens relink`; this
  includes both replays and `update`. `explain` only reports, so it prints `PORTABILITY WARNING`. The checker
  verified that nothing was written apart from explain outputs and the projection index.
- **S2b.** After relink, `update` succeeds. The readers and replays succeed with `NOT SELF-CONTAINED` (Amendment 1).
  `region_contacts.tsv` is byte-identical to R1's.
- **S3.** The readers succeed with `NOT SELF-CONTAINED`, naming R1. `update` refuses: the copy's declared inputs are
  missing, and it refuses before any lock or write.
- **S5.** The planted same-name file is refused as `MISMATCH`. `relink` exits 6, lists it as
  `rejected (same name, different SHA-256)` and records no file.

## Follow-up evidence hash (Task B)

- New follow-ups write `evidence_hash_version = rnplens.followup.evidence.2` in record and plan (B1, 4/4 per case).
  Definition 2 replaces a raw SHA-256 of a project JSON/text record by the hash of its canonical projection.
- Replays recompute the hash under the definition the plan records. Plans without the field are definition 1.
- In S1 (whole-case copy at a new absolute path, original gone) and S2b (relinked project-only copy), both
  follow-ups replay to the recorded `evidence_sha256`. This is the moved-project follow-up replay.
- Unit tests in `tests/test_portability.py`:
  - `test_followup_records_definition_2_and_replays`;
  - `test_definition_2_is_location_independent`, managed and unmanaged;
  - `test_old_record_without_version_replays_under_definition_1`.

## Measured, not gating

Files written or changed in the S1 copy whose bytes name R1's location:
- 2QQP: `analyses/v0004/main/explain/explain_evidence_41322a28.json`, `explain_evidence_44cda09b.json`,
  `analyses/v0004/main/methods/provenance_manifest.json`;
- 2XGJ: `explain_evidence_0485732d.json`, `explain_evidence_70a54c6a.json`, `methods/provenance_manifest.json`.

These are report records that quote the recorded provenance. They do not read from R1, because R1 was renamed
away during S1.

## Before the change (`589485b`, pre-registration section 7)

The same harness on 1VTM at `589485b` gave FAIL, 80 checks, 51 failed.
- With the originals gone, `export-methods`, `group` and `analyse` exited 0, and the replays verified.
- `update` exited 1, after committing a state version.
- With one original changed, `view`, `export-methods`, `group` and `analyse` exited 0.

## Development runs (disclosed; not evidence)

Two runs on 1VTM, which is not a portability case, before the frozen run:
- At `78e7334`: FAIL, 80 checks, 21 failed. The causes were fixed before `401771f`, with no change to frozen files:
  - region reuse was refused in copies;
  - the refusal text was longer than the driver's 3000-character tail;
  - follow-up replays reused records without checking the recorded files.
- At `401771f`: PASS, 80 checks, 0 failed.

## Test suites at `6ea4519`

| where | result | baseline at `589485b` |
|---|---|---|
| local (macOS) | 635 passed, 21 failed, 27 skipped | 648 passed, 27 skipped |
| karyon | 648 passed, 23 failed, 12 skipped | 663 passed, 12 skipped |

`tests/test_portability.py` adds 8 tests, so the totals are 683 local and 683 karyon.

**All failures are in `assistant/tests/test_live_qualification.py` and have one cause.** The live-qualification
freeze check reports `pinned source changed since the freeze: assistant/rnplens_assistant/followup.py`. Task B
changes that pinned file. `assistant/evaluation_v04/LIVE_QUALIFICATION_v1/` was not edited, as instructed; the
Codex-harness track re-pins it in Amendment 5.

The cause was confirmed in throwaway copies, which were then deleted. In each copy only the `followup.py` pin in
`scenarios.json` and the `scenarios.json` row in `FREEZE.md` were changed:
- local: 37 passed, 2 skipped (the karyon-only tests);
- karyon: 39 passed. On karyon the edit was committed in a scratch clone, because two tests require a clean git tree.

`rnplens doctor`: `Qualified components READY; all 8 frozen sources match their pinned SHA-256`.

## Deviations and limits

1. **Pinned file changed.** `assistant/rnplens_assistant/followup.py` changed from sha256
   `b97e4820faddbc9e021b794d1a0d773c2bdc771bfcf2a53045572a49430e4e5f` to
   `af54f0a3b1eedb6d918c1a4ad2348513c363311843a07c24a2515b708789cfa7`. It must be re-pinned (Amendment 5) before any
   live run. No other pinned source changed.
2. **Scope.** The behaviour applies to managed projects (`.rnplens/HEAD`). Plain import or analysis folders keep
   their 0.3 behaviour and are not covered.
3. **Declared inputs count as the project's location.** A declared input folder at an absolute path outside the
   project resolves as LOCAL and raises no notice. A project that declares absolute external inputs is therefore not
   reported as NOT SELF-CONTAINED for them.
4. **Raw files are unchanged.** The 0.3 importer manifest and other raw records of a copy still hold the original
   absolute paths. They are resolved through the hash-verified order and are not rewritten.
5. **Plain `analyse` on a moved or relinked import refuses** (S1, S2b). It reads the recorded paths, and the message
   advises `rnplens update`. This is the pre-registered behaviour.
6. **Refusal messages list at most 6 files**, changed ones first, and end with a summary line. Longer lists are
   counted, not listed.
7. **Relink keys.** `relink.json` keys each entry by the recorded path. Paths written by the import manifest are
   absolute; in S2 there were 15 such keys. Project-relative state paths are resolved at the copy; there were 20.
8. **Trace tool.** The round-2 diagnostic tracer (`records/replay/trace_replay_diffs.py`, unchanged) recomputes a
   follow-up's evidence hash inline under the definition-1 rule. For records written under definition 2, its
   `derived_check` therefore reports "not equal". The tracer is diagnostic and is not part of any pass rule; the
   replay check uses the recorded definition.
9. **Earlier records unchanged.** The v1/v2 contract records and their verdicts are unchanged, including the demo-2
   byte-identity check, which stays FAILED. The statement in `docs/reproducibility.md` that a copied project reads
   the original location is replaced by the new behaviour; the v1/v2 sections are kept.
