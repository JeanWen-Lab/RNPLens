# PORTABILITY_TEST_v1 (pre-registered)

- **Track and base.** Track `replay`, branch `track/replay-r3`, base `589485b`.
- **Owner items.** 3B (copied projects must not silently depend on the original folder) and 4 (the follow-up hash
  part).
- **Commit order.** This document and the frozen tools of section 6 are committed **before any code change** of round
  3, and before the run they govern.
- **Unchanged.** `DETERMINISM_CONTRACT_v1`, `DETERMINISM_CONTRACT_v2` and their records and verdicts are not changed.
  Their statement that a copied project's raw files still name and read the original location described the code
  under those contracts. This test establishes, or fails to establish, the new behaviour separately.

## 1. Terms

- **Managed project.** A directory with `.rnplens/HEAD`, made by `rnplens update --init`.
  - Plain `rnplens import` directories outside a managed project keep their 0.3 behaviour; this is stated as a scope
    limit.
- **Current location of a managed project.** Its directory, plus its declared inputs and declared reference as they
  resolve from that directory.
- **Former location.** An earlier absolute location of the project directory, recorded in its state sidecars (v2,
  `canonical.former_roots`). Its parent folder is treated the same way.
- **Recorded file.** A structure file named by an import directory's `manifest.json`: `path` with `original_sha256`,
  and `used_path` with `used_sha256`.
  - **Required** recorded files are both of these for every INCLUDED structure.
  - **Optional** ones are those of excluded structures; commands only list them.
  - The importer's computation and its `manifest.json` / `report_contract.json` are **not changed**. The check and
    relink layer sits around them.

## 2. Required behaviour (what the implementation must do)

### 2.1 Resolving one recorded file

Resolving a recorded file `(p, h)` is done in this order:
1. **RELINKED.** A mapping for `p` recorded by `rnplens relink` (section 2.4), say to `q`.
2. **LOCAL.** `p` lies in the current location, so `q = p`.
3. **MAPPED.** `p` lies under a former location or its parent folder. Then `q` is the same relative place in the current
   location. If no file is there, resolution falls back to step 4.
4. **EXTERNAL.** Otherwise `q = p`, the recorded absolute path.

Then `q` must exist and `sha256(q)` must equal `h`. Otherwise the result is:
- **MISSING**, if no file is at `q`;
- **MISMATCH**, if a file is at `q` with a different SHA-256.

A file whose bytes differ is **never** used. When step 3 finds a file with a different hash, the original at `p` is
not tried either: a conflicting file in the copy's own location is a MISMATCH.

### 2.2 Commands

**Commands that read structure bytes.** These are `region`, `view`, `group`, `export-methods`, the controlled tools of
`replay-followup`, and the managed analysis.
- They use the resolved paths `q`.
- If any required file is MISSING or MISMATCH, they stop before writing anything. They exit **6** and print on stderr
  a block starting **`PORTABILITY REFUSED`**. The block lists each such file: recorded path, recorded SHA-256, what was
  found (`missing:` or `MISMATCH:` with the found SHA-256). It then says how to restore the files, or how to run
  **`rnplens relink`** with `--search DIR` or `--map OLD=NEW`.
- If every required file resolves, but some resolve EXTERNAL or RELINKED to a place outside the current location, the
  command runs. It prints on stderr a block starting **`NOT SELF-CONTAINED`**, which names those files' location and
  says how to make the project self-contained (copy the inputs next to it, then `rnplens relink`).
- LOCAL and MAPPED files raise no notice; the project is self-contained.

**Commands that only report records.** These are `explain` (all queries) and `update --status` / `--versions`.
- They never refuse.
- With a MISSING or MISMATCH required file they print a stderr block starting **`PORTABILITY WARNING`**, with the same
  listing and advice.
- With an EXTERNAL or RELINKED file they print the `NOT SELF-CONTAINED` block.
- What they report names the resolved paths.

**Plain `rnplens analyse IMPORT_DIR --out OUT`** inside a managed project runs the 0.3 analysis on the paths recorded by
the import, unchanged. It therefore runs only when every required file is LOCAL or EXTERNAL **at its recorded path**
(EXTERNAL with the `NOT SELF-CONTAINED` notice). Otherwise it exits 6 with `PORTABILITY REFUSED`, and its advice
includes `rnplens update`. That covers MAPPED, RELINKED, MISSING and MISMATCH.

**`rnplens update`.**
1. **Missing declared input in a moved project.** In a project with a former location, if a declared input is missing
   at the current location, `update` refuses **before any lock, write or state version**. It exits 6 with
   `PORTABILITY REFUSED`, naming each missing input, whether it exists at the former location (with that path), and the
   remedies:
   - copy the inputs to the shown place;
   - `rnplens relink`;
   - `rnplens update --remove-input` to drop an input deliberately.

   A project that never moved keeps the qualified behaviour: a missing input folder is a removed run
   (`tests/test_incremental.py::test_missing_input_folder_is_a_removed_run`).
2. **Re-analysis needed.** When an analysis must be recomputed, `update` checks the reused import directory. If any
   required file is not LOCAL at its recorded path, `update` re-imports from the current inputs into a new import
   directory before analysing. A reused analysis needs no structure bytes.
3. **Relinked declared inputs.** Declared inputs relinked by `rnplens relink` are replaced by their new location in the
   state version that `update` writes.
4. **Reporting.** `update` reports the head import's resolution, as in the reporting rules.

### 2.3 Exit code

Exit code **6** means "refused for portability". It is new and used for nothing else.

### 2.4 `rnplens relink PROJECT [--search DIR]... [--map OLD=NEW]... [--dry-run]`

**What it covers.** Every required and optional recorded file of every import directory of the project, and every file
recorded in the head state's `inputs.files`.

**Candidates.** For each file that is not LOCAL or MAPPED-and-verified, relink looks for candidates:
- from `--map`: the recorded path with prefix `OLD` replaced by `NEW`;
- from `--search`: every file under `DIR` with the same base name, in sorted walk order.

**Acceptance.**
- The first candidate whose SHA-256 equals the recorded one is accepted.
- A candidate with the same name and another SHA-256 is **never** accepted. It is reported as **`rejected (same name,
  different SHA-256)`** with its path and hash.

**Declared inputs.** A declared input whose recorded files were all relinked under one consistent new folder is mapped
to that folder.

**Record.** The mappings are written to `<project>/.rnplens/relink.json`:
- the file has the form `{"schema": "rnplens-relink-1", "files": [...], "inputs": [...]}`;
- paths are absolute, because the record is location-specific;
- it is merged with earlier relinks;
- it is not written with `--dry-run`.

**Exit.** 0 if afterwards every required file of every import directory resolves. Otherwise 6, listing what remains
unresolved and every rejected candidate.

## 3. Follow-up evidence hash, definition 2 (owner item 4, follow-up hash part)

**What changes.** `rnplens_assistant.followup.evidence_hash` gains a definition version. Definition
`rnplens.followup.evidence.1` is the current one: it hashes statements and the tool log, with absolute paths reduced to
their last component. Definition `rnplens.followup.evidence.2` is the same object, with one difference: every 64-hex
value in a statement slot or tool-log message that equals the raw SHA-256 of a JSON or text file of the analysis or
project is replaced by its location-independent form.
- Inside a managed project, that form is `projection-sha256:<SHA-256 of the file's v2 canonical projection>`.
- Outside one, it is the same projection computed in memory, relative to the common folder of the project and the
  analysis. Nothing is written.

**Where the version is recorded.** New follow-ups record `evidence_hash_version: "rnplens.followup.evidence.2"` in
`followup_record.json` and `followup_plan.json`.

**Replay.** `replay-followup` recomputes under the version recorded in the plan. A plan without the field is replayed
under definition 1, so older records still replay and verify under their own definition. The v1/v2 tracer
(`records/replay/trace_replay_diffs.py`, frozen) recomputes definition 1 only, which is stated as a limitation.

**Location independence.** Definition 2 is location-independent where definition 1 is not. At `3df760d`, the same
follow-up in two locations hashed three different slot values: the raw hashes of `report/rnplens_run.json`,
`summary.json` and the importer `manifest.json`.

**Pinned file.** `followup.py` is pinned by LIVE_QUALIFICATION_v1. Its before and after sha256 are listed in the
hand-back; the re-pin is the Codex-harness track's Amendment 5.

## 4. Test procedure (frozen; `records/replay/portability/`)

**Cases.** Development cases **2QQP** and **2XGJ**: pilot Boltz-2 `exec_A`/`exec_B` runs, prepared by
`v2/prepare_inputs_v2.sh cases`. No excluded target is read.

**Run.** `run_portability.sh ROOT` on karyon, with the code at the round-3 implementation commit, runs these steps for
each case `T`:
1. `v2/retest_case_v2.sh` builds R1 = `ROOT/T/orig_<UTC>`. This is the full base workflow: lifecycle, region, view,
   group, the local follow-up `fu_0001` and the scripted follow-up `fu_0002` (stub client, no model).
2. `portability_case.py` makes five copies of R1:
   - `copies/case_copy`: the whole case folder, so project and inputs;
   - `copies/project_only_S2` to `copies/project_only_S5`: only `project/`.

   It then runs the scenarios below.
3. `check_portability.py` applies section 5.

**Command set.** Each scenario runs the same commands from the case root, with IMP and AN the head import and analysis
directories and REGION the base region `a-b` from `region_rule.json`:
- `update project`
- `region IMP AN --rna REGION`
- `view IMP --analysis AN --rna REGION`
- `explain structures --analysis AN --project IMP`
- `export-methods AN --project IMP`
- `group IMP --analysis AN`
- `rnplens_assistant replay-followup` for `fu_0001` and for `fu_0002`
- `analyse IMP --out <outside the copy>`

**Scenarios, in this order.**

| scenario | setting | what is done |
|---|---|---|
| S0 | R1 in place | the command set (control) |
| S3 | project-only copy, original present | the command set |
| S4 | project-only copy; the original of the first INCLUDED structure has bytes appended | the command set, then the original file is restored |
| (step) | R1 is renamed to `R1.away` | the original becomes unavailable |
| S1 | whole-case copy | the command set |
| S2 | project-only copy | the command set; then `relink project --search R1.away/in`; then the command set again as **S2b** |
| S5 | project-only copy, originals away; a **different file with the same name** is placed at the first INCLUDED structure's original path | the command set; then `relink project --search R1/in` |
| (cleanup) | the planted tree is removed and `R1.away` is renamed back | |

## 5. Pass rule (`check_portability.py`)

A case **PASSES** if and only if every named check holds. Overall **PASS** requires both cases to pass. In brief:

| scenario | checks |
|---|---|
| infra | no driver error; original restored; S4 file restored |
| S0 | all 10 commands exit 0 with no portability text; both replays match |
| B1 | R1's follow-up record and plan carry `evidence_hash_version = rnplens.followup.evidence.2` |
| S1 | update, region, view, explain, export-methods and group exit 0 with **no** `NOT SELF-CONTAINED` / `PORTABILITY REFUSED`; both replays exit 0 and match; plain analyse exit 6; `region_contacts.tsv` byte-identical to R1's; `region.json` records no unresolved structure file |
| S2 | update exit 6; region, view, export-methods, group and analyse exit 6, naming the first missing file and `rnplens relink`; explain exit 0 with `PORTABILITY WARNING`; both replays exit ≠ 0; nothing written except explain outputs and the projection index |
| S2 relink | exit 0; `relink.json` records file mappings |
| S2b | update exit 0; region, view, export-methods and group exit 0 **with** `NOT SELF-CONTAINED`; explain exit 0; replays exit 0 and match; analyse exit 6; `region_contacts.tsv` byte-identical to R1's |
| S3 | update exit 6, naming the original location and `rnplens relink`; region, view, export-methods, group and explain exit 0 with `NOT SELF-CONTAINED` naming R1's location; replays exit 0 and match; analyse: see below; `region_contacts.tsv` byte-identical |
| S4 | update exit 6; region, view, export-methods, group and analyse exit 6 with `MISMATCH` naming the changed file; explain exit 0 with `PORTABILITY WARNING`; replays exit ≠ 0; nothing written except explain outputs and the projection index |
| S5 | readers and analyse exit 6 with `MISMATCH` naming the planted file; replays exit ≠ 0; relink exit 6 reporting `rejected (same name, different SHA-256)` for it; `relink.json` does not record it; nothing written except explain outputs, the projection index and `relink.json` |

**S3 analyse.** It must exit 0 with `NOT SELF-CONTAINED` if every INCLUDED structure is non-derived and used at its
original path. Otherwise it must exit 6.

**Measured, not gating.** Files written or changed in the S1 copy whose bytes name R1's location.

**Reporting.**
- Failures are reported as failures.
- A completed run is not repeated to change its result.
- An infrastructure stop may be repeated once, from scratch, in a new ROOT; the repetition is reported.

## 6. Frozen files

- `records/replay/PORTABILITY_TEST_v1.md`
- `records/replay/portability/portability_case.py`
- `records/replay/portability/check_portability.py`
- `records/replay/portability/run_portability.sh`

The run also uses the v2 files `v2/retest_case_v2.sh`, `v2/steps_v2.sh`, `v2/prepare_inputs_v2.sh` and
`demos/lib/{followup_scripted,region_rule,truncate_rna}.py`.

The sha256 of all of these are in `records/replay/portability/FROZEN_SHA256.txt` and in the commit message.

## 7. Development checks

The harness was run on 1VTM, which is not a portability case, at `589485b` before the freeze, to check its mechanics.
The run is in `scratch_agent/v04/replay-3/smoke_port_1VTM_589485b`.
- **Result.** FAIL, as expected: 80 checks, 51 failed.
- **Harness defect found.** The driver recorded `sys.exit` as a driver error. This was fixed before the freeze.
- **Behaviour observed at `589485b`**, recorded here as the "before" state:
  - **S2** (project-only copy, originals gone): `export-methods`, `group` and plain `analyse` exit 0, and both
    follow-up replays verify. `update` exits 1 and commits a state version.
  - **S4** (one original file's bytes changed): `view`, `export-methods`, `group` and `analyse` exit 0.
  - **S1** (whole-case copy, original gone): `region` and `view` exit 2.

After the implementation, development runs on 1VTM may be made and are reported. They are not evidence.

## Amendments

### Amendment 1 (before any code change and before any run)

**The conflict.** Checking the frozen checker against section 2.2 showed one conflict, in scenario S2b. After
`relink`, the first command, `update`, records the relinked folder as the project's declared inputs. By the wording of
section 2.2, the old import's relinked files then lie "inside the current location", and no notice would be printed.
The frozen checker expects `NOT SELF-CONTAINED`.

**Resolution.** The checker's expectation is kept, and section 2.2 is clarified:
- A command that uses any **RELINKED** file prints the `NOT SELF-CONTAINED` block, wherever the relink target lies.
  Such a file is, by construction, not at the place the project's records give for it.
- The block names the relinked and external locations.
- An import made by `update` from the relinked declared inputs records those paths itself. Its files are LOCAL, and
  they raise no notice.

The checker, the driver and the cases are unchanged.
