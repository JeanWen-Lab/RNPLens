# Replay requalification under DETERMINISM_CONTRACT_v1: report (step D)

Track `replay`, branch `track/replay`; retest on karyon on 16 Oct 2026, 20:29-20:32 UTC.

## Verdict

| test | rule | result |
|---|---|---|
| Original demonstration 2 replay check (24BR; `records/v04_integration/DEMOS_PLAN.md`) | byte-identical replay of every result JSON | **FAILED**, and it **remains FAILED**. It is not re-labelled. The trace (`REPLAY_DIFF_TRACE.md`) explains it and does not change it |
| Requalification on 4 new development cases (`DETERMINISM_CONTRACT_v1.md`, section 6) | (0) completed, (i) every canonical file byte-identical, (ii) scientific comparison equal | **PASS**, 4 of 4 cases |

What the PASS covers:
- **Byte identity** of the canonical artifacts named in contract section 3 (managed-project state history, decisions,
  cache keys, indices, before/after reports, contact records and construct sequences) for these four cases;
- **scientific equality** (no number, evidence record or interpretation differs) of every file the workflow wrote.

What it does **not** cover:
- byte identity of the non-canonical files listed in section 4 below, which still differ in bytes, all volatile-only;
- any other platform or RNPLens version.

## 1. Order of record (git, branch `track/replay`)

| commit | what | relation to the retest |
|---|---|---|
| `a775dfe` | step A trace of the original failure (`REPLAY_DIFF_TRACE.md`, `.json`, tools) | before |
| `7931f9a` | **pre-registration**: contract v1, canonical list, frozen `retest_case.sh`, `prepare_inputs.sh`, `check_pair.py`, smoke on 2QQP at `cf81acd` | before any code change |
| `4205b5e` | **Amendment 1**: derived structure copies `imports/v*/*/derived/*/*` made canonical (found by a step-C unit test) | before the retest |
| `98f8ba9` | step C implementation (`canonical.py`, `state.py`, `incremental.py`, `clarify.py`, `provenance.py`, tests, docs) | before |
| `01e0466` | process id removed from sidecars (found by a post-implementation smoke on 2QQP, which is not a case) | before |
| `891aeaf` | `run_retest.sh` (orchestration only, adds no rule) and the smoke records | **the retest ran this code** (`results/code_commit.txt` = `891aeaf3b1cb…`; `results/code_status.txt` empty, so the tree was clean) |
| this commit | results and this report | after |

The frozen files' sha256 values are listed in the messages of `7931f9a` and `4205b5e`, and in
`retest/FROZEN_SHA256.txt`. `check_pair.py`, `retest_case.sh` and `prepare_inputs.sh` were not changed after
`7931f9a`.

## 2. Execution

- **Inputs.** `prepare_inputs.sh` copied the four cases once. The sha256 of every prepared file is in
  `results/prepared_inputs.sha256` (72 files; the file itself has sha256 `33e52596…`).
- **What was opened.** Only `assistant_dev_tasks/d1_7K9D_agreement` and `d2_1VTM_agreement`, plus the 2JEA and 2Q66
  YAMLs and their `predictions/<T>/` model and confidence files under `pilot/boltz/exec_{A,B}`. No reference, audit,
  score or other target folder was opened.
- **Code.** `0.4.0.dev0` from the karyon track clone (`results/environment.txt`).

| case | first run (case root under `scratch_agent/v04/replay-2/retest/`) | start-end (UTC) | second run | start-end (UTC) |
|---|---|---|---|---|
| 1VTM | `1VTM/first_20261016T202927Z` | 20:29:27-20:29:30 | `1VTM/second_copy_20261016T203144Z` | 20:31:44-20:31:47 |
| 7K9D | `7K9D/first_20261016T202930Z` | 20:29:30-20:29:32 | `7K9D/second_copy_20261016T203147Z` | 20:31:47-20:31:50 |
| 2JEA | `2JEA/first_20261016T202932Z` | 20:29:32-20:29:36 | `2JEA/second_copy_20261016T203150Z` | 20:31:50-20:31:53 |
| 2Q66 | `2Q66/first_20261016T202936Z` | 20:29:36-20:29:39 | `2Q66/second_copy_20261016T203153Z` | 20:31:53-20:31:57 |

- **Timing.** The second runs started 125 s after the last first run ended.
- **Directories.** Every second run had a different absolute directory and a different working-directory name
  (`second_copy_…` rather than `first_…`), and its own `TMPDIR`. Every step of all 8 runs reached its expected exit
  code (14 steps each).
- **What each run did.** Every run produced 7 state versions (v0001-v0007, ending COMPLETE) and recorded the
  `exclude_run` answer. Removing run_C then invalidated that answer, as intended. Each run also wrote one region and
  one local follow-up.

| case | structures (BOLTZ2, 2 runs) | contact rows | region (rule of demo 1) | region contacts |
|---|---:|---:|---|---:|
| 1VTM | 10 | 53 | RNA 1-3 | 53 |
| 7K9D | 2 | 47 | RNA 14-59 | 47 |
| 2JEA | 10 | 66 | RNA 1-35 | 66 |
| 2Q66 | 10 | 50 | RNA 2-5 | 50 |

These values are the same in both runs of every case.

## 3. Per-case results under the frozen rule

| case | (0) completed | (i) canonical files byte-identical | (ii) files compared / byte-identical / differing (all VOLATILE_ONLY) | unpaired | evidence-hash recomputation | verdict |
|---|---|---|---|---|---|---|
| 1VTM | yes | **28 / 28** | 129 / 76 / 53 | 0 | equal, both runs | **PASS** |
| 7K9D | yes | **27 / 27** (one Report run directory fewer: one sample per run) | 100 / 49 / 51 | 0 | equal, both runs | **PASS** |
| 2JEA | yes | **28 / 28** | 129 / 75 / 54 | 0 | equal, both runs | **PASS** |
| 2Q66 | yes | **28 / 28** | 129 / 76 / 53 | 0 | equal, both runs | **PASS** |

Canonical files per case:
- `HEAD`;
- 7 state versions;
- 3 cache entries;
- 4 `index.json`;
- 3 `update_report.json` and 3 `.html`;
- 4 construct FASTA files;
- 1-2 `contacts_by_output.json`;
- 1 `region_contacts.tsv`.

No derived copy was produced, as expected.

The leaf classes in the differing non-canonical files are summed over the case's differing files; the bracketed
counts are for 1VTM:
- `ABS_PATH` (402)
- `HASH` (60), every one resolved to volatile-only bytes
- `TIMESTAMP` (47)
- text `VOLATILE_TEXT` (41) and `TEXT_WITH_HASH` (3)
- `COMPOSITE` (3)
- `DURATION` (1, Report's `wall_s`)

There is no `CONTENT`, `UNRESOLVED` or `DEMO_TOOLING`. The per-file details are in `results/check_<T>.json`; the
per-file canonical table is in the appendix.

| record | sha256 |
|---|---|
| `results/check_1VTM.json` | `1d7542800f7feeb2069a71e6b6ef415f9cd100e389adf98d7de9a72875fa42fd` |
| `results/check_7K9D.json` | `9478d9b7dc3d39ef94e105e4be0da2a9c286d757c4414b30a09756cbde520b2e` |
| `results/check_2JEA.json` | `3eaaa5ad06db9246dea036ce079ebe8e9bfce630baca7b135827fb70ca4b996e` |
| `results/check_2Q66.json` | `1a5d34f7206d3eb0cb5a56ce9223fdc9d40a9374c3ab4e7d9c7aa8fc6573ba6b` |
| `results/runs.tsv` / `verdicts.tsv` / `OVERALL` | `d2d09f74…` / `38fa578b…` / `c26de83a…` (`PASS`) |

## 4. What still differs in bytes (non-canonical by contract section 3)

Per case, 51-54 files differ between the two runs (53 / 51 / 54 / 53), 17 of them sidecars. All differences are volatile-only.

| group | files (per case) | why the bytes differ |
|---|---|---|
| sidecars `project/.rnplens/run/…` | 17 | time stamps, project root and working directory, raw hashes of non-canonical files. By design |
| importer, 0.3 route: `imports/v*/main/manifest.json`, `report_contract.json`, `main.log` | 6 | `created_utc`, absolute paths |
| analyse and Report, 0.3 route and frozen: `summary.json`, `report*/rnplens_run.json`, `run_repeat_inputs/report_contract_*.json`, `commands.log`, `main.log`; in 2JEA also `report_runs_BOLTZ2/result.json` (`wall_s` only) | 4-7 | `created_utc`, absolute paths, `wall_s` |
| other 0.4 modules: `region_*/region.json`, `explain/*` (4), `followup/fu_0001/*` (4), `methods/methods_sources.json`, `provenance_manifest.json` | 11 | `created_utc`, absolute paths, raw hashes of the importer manifest and summary. The follow-up `evidence_sha256` differs for this reason, as traced in step A |
| workflow logs and `region_rule.json` (outside the project) | 13 | absolute paths, time stamps |

These are the version-1 scope limits that contract section 3 lists. Making `region.json`, `explain/*`, `followup/*`,
`methods/*` and the consent record canonical needs changes in modules outside this track (section 7).

## 5. Deviations and caveats

1. **7K9D is not independent of development.** Its inputs (`d1_7K9D_agreement/run_A`, `run_B`) are byte copies of the
   bundled example `examples/reference_free/report_7K9D/exec_{A,B}` (sha256 checked). The step-C unit tests used that
   example while I developed the code. 1VTM, 2JEA and 2Q66 were never used during development. The contract named
   7K9D as a case before this was checked.
2. **Amendment 1, before the retest.** The canonical list gained `imports/v*/*/derived/*/*`. The retest produced no
   derived copy, so the amendment did not affect any retest file.
3. **Pre-retest smoke runs on 2QQP**, which is not a case:
   - at `cf81acd`: FAIL on (i), with 9 of 28 canonical files identical;
   - at `98f8ba9`: FAIL on (ii), because of the sidecar process id;
   - at `01e0466`: PASS.

   The `01e0466` fix (process id removed from the sidecar `execution` record) changed implementation, not contract.
   The smokes were development checks and are not evidence for the retest. Records:
   `retest/SMOKE_2QQP_cf81acd.md`, `retest/SMOKE_2QQP_post_implementation.md`.
4. **One host and one interpreter.** Both runs of every case ran on karyon with the same Python
   (`RNPLens_dev_0.3/venv`). Byte identity across hosts, Python versions or operating systems was **not tested**. The
   local macOS suite exercises relocation within macOS only (`tests/test_determinism.py`).
5. **No access audit by strace.** The contract did not require one, and the demo 1 and demo 2 audits were not
   repeated. The inputs read are those listed in section 2, by construction of `prepare_inputs.sh`.
6. **Demonstration 2 was not re-run** with the new code. Its replay failure stays a historical result. Re-running it
   is not part of this contract.
7. **One assertion changed in `tests/test_incremental.py`**, which is outside the `test_determinism*` files I own.
   Contract rule 4 requires `summary.json` inputs of the update report to carry `content_sha256` rather than a raw
   `sha256`, so the assertion now accepts either.

## 6. Paragraph for the release documentation (for the release-docs track)

> **Reproducibility of managed projects.** RNPLens 0.4 separates scientific reproducibility from byte-identical
> reproducibility (`records/replay/DETERMINISM_CONTRACT_v1.md`).
>
> *Scientific reproducibility* means the same numbers, evidence records and interpretations. It holds for every file
> when the same input files (in the same layout relative to the project), configuration, recorded answers and RNPLens
> version are replayed.
>
> *Byte-identical reproducibility* is promised only for a named set of **canonical** files:
> - the managed-project state history and recorded decisions (`.rnplens/HEAD`, `.rnplens/state/`);
> - cache entries, version indices and before/after update reports;
> - Report's per-structure contact records (`contacts_by_output.json`), region contact tables and construct
>   sequences.
>
> These files hold relative paths and no time stamp. Volatile execution metadata (times, source commit, absolute
> locations, raw hashes of non-canonical files) is kept in sidecars under `.rnplens/run/`.
>
> The pre-registered byte-identical replay check of the 24BR interactive demonstration **failed** before this change,
> and that result stands; tracing found no scientific difference. On four further development cases (1VTM, 7K9D,
> 2JEA, 2Q66), each replayed in another directory at another time on the tested Linux host, every canonical file was
> byte-identical and no scientific content differed. 7K9D is also the bundled test example.
>
> Other outputs remain non-canonical: importer manifests, `summary.json`, Report run records, `region.json`, explain,
> follow-up and Methods records. They may differ in bytes between runs, through time stamps, absolute paths and
> derived hashes, while their scientific content is identical. A follow-up's `evidence_sha256` changes when a project
> is moved or re-imported. Byte identity was tested on one Linux host and one Python version only.

## 7. What a contract version 2 would need

Writers outside this track would need these changes:
- `region.py`: project-relative `runs/*/structures/*/{path,used_path}` and provenance;
- `evidence_query.py`: statement roots and texts, and content hashes instead of raw file hashes;
- `rnplens_assistant/followup.py`: `evidence_sha256` over content hashes; `started_utc`, `wall_s` and the
  confirmation time moved to a sidecar;
- `consent.py`: an id not derived from time;
- `methods_export.py`.

The 0.3 routes (importer manifest, `summary.json`, Report records) would need either an owner decision to change
qualified-route outputs, or canonical companion views. Their readers (viewer, evidence lookup) would need to resolve
relative paths.

## Appendix: canonical files per case (both runs)

### 1VTM (28 canonical files; first `1VTM/first_20261016T202927Z`, second `1VTM/second_copy_20261016T203144Z`)

| canonical file (relative to `project/`) | result | sha256 (both runs) |
|---|---|---|
| `.rnplens/HEAD` | BYTE_IDENTICAL | `9c9327fadf1b2dc2…` |
| `.rnplens/cache/bdbe1875d2d56cbbbb0e4001cda9cb01104f33565e7132149072ec6928125aff.json` | BYTE_IDENTICAL | `b20638388442d663…` |
| `.rnplens/cache/d250f186762706b00d5ce53f2268555823514b6a36d191fd233f782b380ec4f8.json` | BYTE_IDENTICAL | `4a762bc3f67bf15b…` |
| `.rnplens/cache/e0f3facb9213a0f564f8065d8d1d830baca3d72d0437b4c87dc0517fbc6b2316.json` | BYTE_IDENTICAL | `1dadb250ca682b9b…` |
| `.rnplens/state/v0001.json` | BYTE_IDENTICAL | `93358ce50d8fc565…` |
| `.rnplens/state/v0002.json` | BYTE_IDENTICAL | `4d2473f242883efe…` |
| `.rnplens/state/v0003.json` | BYTE_IDENTICAL | `f8877ce35e0aa928…` |
| `.rnplens/state/v0004.json` | BYTE_IDENTICAL | `6b2ef4e687e1b64c…` |
| `.rnplens/state/v0005.json` | BYTE_IDENTICAL | `714a9974ef87912d…` |
| `.rnplens/state/v0006.json` | BYTE_IDENTICAL | `a95bb2aeced58a28…` |
| `.rnplens/state/v0007.json` | BYTE_IDENTICAL | `643fc58190f9e328…` |
| `analyses/v0004/index.json` | BYTE_IDENTICAL | `97b23a1c5e7c9af1…` |
| `analyses/v0004/main/region_1-3/region_contacts.tsv` | BYTE_IDENTICAL | `1109dbc1a7c544ae…` |
| `analyses/v0004/main/report/contacts_by_output.json` | BYTE_IDENTICAL | `7a9f4913d9d43a66…` |
| `analyses/v0004/main/report_runs_BOLTZ2/contacts_by_output.json` | BYTE_IDENTICAL | `08010105ff174d8d…` |
| `analyses/v0005/index.json` | BYTE_IDENTICAL | `cbc6e584e72bba33…` |
| `analyses/v0005/update_report.html` | BYTE_IDENTICAL | `2bc4427e8e3715f7…` |
| `analyses/v0005/update_report.json` | BYTE_IDENTICAL | `bc7aae99c12c6dc7…` |
| `analyses/v0006/index.json` | BYTE_IDENTICAL | `2164acf92afd7bf8…` |
| `analyses/v0006/update_report.html` | BYTE_IDENTICAL | `6e997ff0533b0d71…` |
| `analyses/v0006/update_report.json` | BYTE_IDENTICAL | `474adffd310797af…` |
| `analyses/v0007/index.json` | BYTE_IDENTICAL | `84e37f27ad2ed18e…` |
| `analyses/v0007/update_report.html` | BYTE_IDENTICAL | `20c4cc6a6168de68…` |
| `analyses/v0007/update_report.json` | BYTE_IDENTICAL | `479fab53a2680498…` |
| `imports/v0002/main/construct_protein.fasta` | BYTE_IDENTICAL | `6754b3dc7717782d…` |
| `imports/v0002/main/construct_rna.fasta` | BYTE_IDENTICAL | `09da3de3831d1dcf…` |
| `imports/v0004/main/construct_protein.fasta` | BYTE_IDENTICAL | `6754b3dc7717782d…` |
| `imports/v0004/main/construct_rna.fasta` | BYTE_IDENTICAL | `09da3de3831d1dcf…` |

Scientific comparison: 129 files in each run, 76 byte-identical. 53 differ; every one is VOLATILE_ONLY (0 not volatile). Files present in one run only: 0. Evidence-hash recomputations: first = True, second = True.

### 7K9D (27 canonical files; first `7K9D/first_20261016T202930Z`, second `7K9D/second_copy_20261016T203147Z`)

| canonical file (relative to `project/`) | result | sha256 (both runs) |
|---|---|---|
| `.rnplens/HEAD` | BYTE_IDENTICAL | `70e12ff7d5ce92bb…` |
| `.rnplens/cache/734a10cf7d3ab68c677c342c70f4efd0854ab0be123a8996bafaf730fc1116fe.json` | BYTE_IDENTICAL | `df99abc1d30885d6…` |
| `.rnplens/cache/9d45dec7648d17e6c539869fbe9ec99dbe0ba143663302ebcf1983ee26a1b6eb.json` | BYTE_IDENTICAL | `3ed430c2fdfa7f72…` |
| `.rnplens/cache/a9eb8ab486c409793f96a784c60e89842e5b866752688c941087a6dc31f327f8.json` | BYTE_IDENTICAL | `12b3b29534d3876c…` |
| `.rnplens/state/v0001.json` | BYTE_IDENTICAL | `9649f66035094bd9…` |
| `.rnplens/state/v0002.json` | BYTE_IDENTICAL | `0fcc06962d6e6a1d…` |
| `.rnplens/state/v0003.json` | BYTE_IDENTICAL | `9792988b4af0d295…` |
| `.rnplens/state/v0004.json` | BYTE_IDENTICAL | `2e4c1fb41c5241a6…` |
| `.rnplens/state/v0005.json` | BYTE_IDENTICAL | `506e56a09d76dd57…` |
| `.rnplens/state/v0006.json` | BYTE_IDENTICAL | `6ce921627a73e851…` |
| `.rnplens/state/v0007.json` | BYTE_IDENTICAL | `38e125eef60958b3…` |
| `analyses/v0004/index.json` | BYTE_IDENTICAL | `c273503423746742…` |
| `analyses/v0004/main/region_14-59/region_contacts.tsv` | BYTE_IDENTICAL | `e99b2ad7e909cc39…` |
| `analyses/v0004/main/report/contacts_by_output.json` | BYTE_IDENTICAL | `fc2c8db322d8b11e…` |
| `analyses/v0005/index.json` | BYTE_IDENTICAL | `adc742da678081a5…` |
| `analyses/v0005/update_report.html` | BYTE_IDENTICAL | `5539154ed54adbef…` |
| `analyses/v0005/update_report.json` | BYTE_IDENTICAL | `9624e71251d155af…` |
| `analyses/v0006/index.json` | BYTE_IDENTICAL | `afaac5dcbe770cac…` |
| `analyses/v0006/update_report.html` | BYTE_IDENTICAL | `b6a01bb32607ed91…` |
| `analyses/v0006/update_report.json` | BYTE_IDENTICAL | `987cd2b35abe03fe…` |
| `analyses/v0007/index.json` | BYTE_IDENTICAL | `7df10956b718f86d…` |
| `analyses/v0007/update_report.html` | BYTE_IDENTICAL | `e3e43fecb8d14314…` |
| `analyses/v0007/update_report.json` | BYTE_IDENTICAL | `cfc874177a105de8…` |
| `imports/v0002/main/construct_protein.fasta` | BYTE_IDENTICAL | `f3b0481fc1f9d342…` |
| `imports/v0002/main/construct_rna.fasta` | BYTE_IDENTICAL | `e765f214c978ef2a…` |
| `imports/v0004/main/construct_protein.fasta` | BYTE_IDENTICAL | `f3b0481fc1f9d342…` |
| `imports/v0004/main/construct_rna.fasta` | BYTE_IDENTICAL | `e765f214c978ef2a…` |

Scientific comparison: 100 files in each run, 49 byte-identical. 51 differ; every one is VOLATILE_ONLY (0 not volatile). Files present in one run only: 0. Evidence-hash recomputations: first = True, second = True.

### 2JEA (28 canonical files; first `2JEA/first_20261016T202932Z`, second `2JEA/second_copy_20261016T203150Z`)

| canonical file (relative to `project/`) | result | sha256 (both runs) |
|---|---|---|
| `.rnplens/HEAD` | BYTE_IDENTICAL | `28c53547ebe66646…` |
| `.rnplens/cache/86c962e9b02e9190df8ab5e1ea1ea1f0f80aef8068e82b240aefd2cc52786654.json` | BYTE_IDENTICAL | `bcbe72bc2b525658…` |
| `.rnplens/cache/b995c812cdbddd88781276e4eb05915d1c90b028519478519830cda02521135f.json` | BYTE_IDENTICAL | `09d59f64ff80c0ae…` |
| `.rnplens/cache/ba55ccd0f5e19426c7a24b5e017b064376d29fc4309e92ff4b0b600e89001a3e.json` | BYTE_IDENTICAL | `4bbb3e829cb7858a…` |
| `.rnplens/state/v0001.json` | BYTE_IDENTICAL | `5a6ee55d3eb546c2…` |
| `.rnplens/state/v0002.json` | BYTE_IDENTICAL | `3af4903b0af31528…` |
| `.rnplens/state/v0003.json` | BYTE_IDENTICAL | `ad51d2775102abc3…` |
| `.rnplens/state/v0004.json` | BYTE_IDENTICAL | `d8a8c39a65243415…` |
| `.rnplens/state/v0005.json` | BYTE_IDENTICAL | `d3d00e7969ce6983…` |
| `.rnplens/state/v0006.json` | BYTE_IDENTICAL | `da2def50d8b3f9c5…` |
| `.rnplens/state/v0007.json` | BYTE_IDENTICAL | `ad4995cb7d590dc4…` |
| `analyses/v0004/index.json` | BYTE_IDENTICAL | `3ef7cb0916ebe032…` |
| `analyses/v0004/main/region_1-35/region_contacts.tsv` | BYTE_IDENTICAL | `0ec319e2ca214910…` |
| `analyses/v0004/main/report/contacts_by_output.json` | BYTE_IDENTICAL | `d360b344a4bd3e0d…` |
| `analyses/v0004/main/report_runs_BOLTZ2/contacts_by_output.json` | BYTE_IDENTICAL | `1c3643a02cae40a8…` |
| `analyses/v0005/index.json` | BYTE_IDENTICAL | `deb4f76257c9b2ac…` |
| `analyses/v0005/update_report.html` | BYTE_IDENTICAL | `af6a5a3089b803ac…` |
| `analyses/v0005/update_report.json` | BYTE_IDENTICAL | `9761709e38702093…` |
| `analyses/v0006/index.json` | BYTE_IDENTICAL | `ba5688c14646d4c0…` |
| `analyses/v0006/update_report.html` | BYTE_IDENTICAL | `74b15050c7f0f2a0…` |
| `analyses/v0006/update_report.json` | BYTE_IDENTICAL | `133b47ed4a1cf292…` |
| `analyses/v0007/index.json` | BYTE_IDENTICAL | `6e7823db529466b6…` |
| `analyses/v0007/update_report.html` | BYTE_IDENTICAL | `b60e397459c4ce1f…` |
| `analyses/v0007/update_report.json` | BYTE_IDENTICAL | `1e420b112e1bfd27…` |
| `imports/v0002/main/construct_protein.fasta` | BYTE_IDENTICAL | `e36227b3c579d870…` |
| `imports/v0002/main/construct_rna.fasta` | BYTE_IDENTICAL | `4fcffb34aa71f661…` |
| `imports/v0004/main/construct_protein.fasta` | BYTE_IDENTICAL | `e36227b3c579d870…` |
| `imports/v0004/main/construct_rna.fasta` | BYTE_IDENTICAL | `4fcffb34aa71f661…` |

Scientific comparison: 129 files in each run, 75 byte-identical. 54 differ; every one is VOLATILE_ONLY (0 not volatile). Files present in one run only: 0. Evidence-hash recomputations: first = True, second = True.

### 2Q66 (28 canonical files; first `2Q66/first_20261016T202936Z`, second `2Q66/second_copy_20261016T203153Z`)

| canonical file (relative to `project/`) | result | sha256 (both runs) |
|---|---|---|
| `.rnplens/HEAD` | BYTE_IDENTICAL | `6eb6535db976b620…` |
| `.rnplens/cache/5f315380b704e2bae401ca218fdf2d8a46725d28545332aeaad4eb7c2d089587.json` | BYTE_IDENTICAL | `e9ed3213bd1f6fc8…` |
| `.rnplens/cache/93d7563d66ecc142d02111e329caefdf223b3af2d0061a223accdb3df0b294e6.json` | BYTE_IDENTICAL | `3efef91fa2c9d1ea…` |
| `.rnplens/cache/c7681408f595fddcf50a58c03413b5e81a72990cda2f9fe521b4fd6aec46eebc.json` | BYTE_IDENTICAL | `41e53245522156fc…` |
| `.rnplens/state/v0001.json` | BYTE_IDENTICAL | `d5a77f90573fbb61…` |
| `.rnplens/state/v0002.json` | BYTE_IDENTICAL | `c541ef7ed02ebc51…` |
| `.rnplens/state/v0003.json` | BYTE_IDENTICAL | `75218353ed601e47…` |
| `.rnplens/state/v0004.json` | BYTE_IDENTICAL | `4636eb9a77f9391f…` |
| `.rnplens/state/v0005.json` | BYTE_IDENTICAL | `f1329d6ca3bd3f1d…` |
| `.rnplens/state/v0006.json` | BYTE_IDENTICAL | `6541c4c569e83a49…` |
| `.rnplens/state/v0007.json` | BYTE_IDENTICAL | `bee4c9e479eff39e…` |
| `analyses/v0004/index.json` | BYTE_IDENTICAL | `8128c14135f21062…` |
| `analyses/v0004/main/region_2-5/region_contacts.tsv` | BYTE_IDENTICAL | `fc88a17f81ef79bf…` |
| `analyses/v0004/main/report/contacts_by_output.json` | BYTE_IDENTICAL | `c6aaa99f567fdcd8…` |
| `analyses/v0004/main/report_runs_BOLTZ2/contacts_by_output.json` | BYTE_IDENTICAL | `8b9f3722e72dadcd…` |
| `analyses/v0005/index.json` | BYTE_IDENTICAL | `7b3f0236d0f72edd…` |
| `analyses/v0005/update_report.html` | BYTE_IDENTICAL | `616e25e252c70f87…` |
| `analyses/v0005/update_report.json` | BYTE_IDENTICAL | `32f8bdfa01691936…` |
| `analyses/v0006/index.json` | BYTE_IDENTICAL | `2b26ad1fda276211…` |
| `analyses/v0006/update_report.html` | BYTE_IDENTICAL | `35efe35b3dc8e602…` |
| `analyses/v0006/update_report.json` | BYTE_IDENTICAL | `cfae8cb462c69ec0…` |
| `analyses/v0007/index.json` | BYTE_IDENTICAL | `32bdcf66f8c9077b…` |
| `analyses/v0007/update_report.html` | BYTE_IDENTICAL | `279c8026b899820b…` |
| `analyses/v0007/update_report.json` | BYTE_IDENTICAL | `5f337133387ddeab…` |
| `imports/v0002/main/construct_protein.fasta` | BYTE_IDENTICAL | `e6a6ba852c908873…` |
| `imports/v0002/main/construct_rna.fasta` | BYTE_IDENTICAL | `cdf833a9ab2e6ce1…` |
| `imports/v0004/main/construct_protein.fasta` | BYTE_IDENTICAL | `e6a6ba852c908873…` |
| `imports/v0004/main/construct_rna.fasta` | BYTE_IDENTICAL | `cdf833a9ab2e6ce1…` |

Scientific comparison: 129 files in each run, 76 byte-identical. 53 differ; every one is VOLATILE_ONLY (0 not volatile). Files present in one run only: 0. Evidence-hash recomputations: first = True, second = True.