# Demos & installs track: report (RNPLens 0.4.0.dev0, 16 Oct 2026)

Branch `track/demos`, based on `5caccec`. This track adds files under `demos/` and `records/v04_integration/` only;
no source, test or docs file was changed. Rules were fixed in advance in `DEMOS_PLAN.md`, committed as `da5f6cb`
before any demonstration output existed. The demonstration packages were produced on karyon with the track clone
at `8dfc54f`. That commit holds the same RNPLens source as `5caccec`; the provenance blocks record it as
`code_commit`. No Codex or other language-model call was made by this track.

## Summary of every check

| check | result |
|---|---|
| A. clean install, wheel venv: version, selftest, doctor, Mol* hashes, menu A-F, view, region, group, export-methods, update (add run), replay-followup | all exit 0 (see `CLEAN_INSTALL_LINUX.md`) |
| A. clean install, sdist venv: same | all exit 0 |
| A. `rnplens doctor --agent` (packaged jail), both venvs | exit 1: 17 READY, 4 ACTION REQUIRED, 0 UNSUPPORTED. The packaged jail self-probe passed; ACTION REQUIRED: Codex CLI 0.114.0 untested (snap), not signed in, model not verified, language-model functions disabled |
| A. full suite against installed wheel (tests from the clone, PYTHONPATH unset, cwd outside src) | 543 passed, 1 failed (D3), 12 skipped; no `.pyc` written under the source tree |
| A. full suite against installed sdist | 543 passed, 1 failed (D3), 12 skipped; no `.pyc` written under the source tree |
| A. Mol* assets in site-packages vs `VERSION.json` (wheel and sdist) | LICENSE, molstar.css, molstar.js: sha256 and size MATCH; Mol* 5.13.1 |
| A. region 13-23 of the bundled example vs `docs/region.md` (both venvs) | equal: 36 contacts, 32 shared, R18-A21 only in exec_A, R16-U14, D39-U15, R45-U15 only in exec_B |
| A. groups of menu E (Report records) vs `rnplens group --out` (Report's routine), both venvs | equal |
| A. `python -m rnplens_assistant replay-followup` of a FOLLOWUP_SUITE_v1 Part 1 plan (copied) | `matches: true`, both venvs |
| Demo 1: steps with the expected exit code | 13 of 13 |
| Demo 2: steps with the expected exit code | 22 of 22 (4 expected non-zero: update --init 3, clarify list 3, clarify --json 3, contradicting answer 2) |
| Demo 3: steps with the expected exit code | 12 of 12 |
| Demo 3: every candidate retained (groups + no-interface + ineligible == 50, ids equal the manifest's, no duplicates) | PASS at t = 0.3, 0.5, 0.7 (50 + 0 + 0 = 50 each) |
| Demo 3: documented 6BJG numbers of `docs/grouping.md` reproduced | PASS, 19 of 19 checks equal |
| Wording scan (all text outputs; `trace.wording_audit` + `grouping.FORBIDDEN`) | PASS in all three packages: no forbidden phrase and no affirmative audit hit in any 0.4 output (details below) |
| Replay, pre-registered check (only `created_utc`, `wall_s` ignored; root-path and hash-of-passing-file classes reported separately) | demo 1 PASS (23 JSON files); demo 3 PASS (17); **demo 2 FAIL** (22 of 57 files differ beyond those classes; 5 cache files present on one side only) |
| Replay, strict (byte-equal JSON after removing `created_utc`/`wall_s`) | FAIL in all three: absolute paths and hashes of timestamped files are recorded in outputs |
| Replay, post-hoc classification (not pre-registered) | all three NO_OTHER_DIFFERENCE. In demo 2 the 27 differing or one-side files differ only in timestamps under other key names, time-derived ids and hashes |
| Data access (whole workflow under `strace -f`, open/openat/openat2/execve) | PASS in all three: 0 forbidden paths. Demo 3 read under PCfold3D-RNP only `inputs/6BJG.yaml` and `predictions/6BJG/` (`6BJG_model_*.pdb`, `confidence_6BJG_model_*.json`); demos 1 and 2 read no PCfold3D-RNP path |
| Full suite, local (macOS arm64, track branch at `8dfc54f` and again at `7421948`) | 538 passed, 1 failed (the known `test_report_numbers_equal_the_rc3_expected_output` last-digit difference), 17 skipped. A PATH shim provides the `rnplens` command, which the local conda env lacks (see O4) |
| Full suite, karyon track clone (at `8dfc54f` and again at `7421948`) | 544 passed, 0 failed, 12 skipped |

The commit after `7421948` changes only this report, recording the test counts above.

After the runs, the `scripts/lib/` copy inside each package was refreshed from `7421948`. That commit adds
`classify_replay_diffs.py` and `access_audit.py`, and makes `replay.sh` call the post-hoc classifier. The run
scripts (`demos/<n>/`) are identical between `8dfc54f` and `7421948`.

## Part A: clean installs on Linux
Details, every command and exit code are in `CLEAN_INSTALL_LINUX.md`. That file is generated from the logs by
`demos/clean_install/make_record.py`. Script: `demos/clean_install/clean_install_linux.sh`. Folder on karyon:
`scratch_agent/v04/clean_install_20261016T131711Z/`.

## Part B: the three demonstrations
The packages are on karyon under `RNPLens_dev_0.4/work/demos/`. Each holds a README with the question, the exact
commands, the meaning of the outputs and their limits, all outputs, `scripts/` (a copy of the scripts that made
it), `replay.sh` and `checks/`.

1. **`1_region_1VTM`** (d2_1VTM_agreement; two Boltz-2 runs, 5 samples each). Region rule:
   `[min, max]` of the RNA positions in the designated structures' Report contacts. The result is RNA 1-3, which
   is the whole 3-nt RNA `GAA`.
   - 25 protein residues contact the region.
   - 53 contacts are listed: 30 shared by both runs, 8 found only in run_A, 15 found only in run_B, 0 present in
     some runs, 0 not determined.
   - Coverage is COMPLETE in all 10 structures. The designated structures are s001 (run_A) and s006 (run_B).
   - Outputs: the regional table, the designated / k of n / additional-sample columns for every contact, the
     region map, `view --rna 1-3`, and `explain` of the structures, the region mapping and three run-specific
     contacts.
2. **`2_interactive_24BR`** (d4_24BR_compare; reference not used). The input `run_C_other_construct` is run_B
   truncated by 2 nt.
   - `update --init` raised a typed `construct_mismatch` request with three options (exit 3). The answer was
     `exclude_run`, with the researcher's words, and the pipeline resumed to COMPLETE.
   - A contradicting answer was refused with the documented message (exit 2). A no-change update reused v0004.
   - Region RNA 1-4 (the whole 4-nt RNA): 32 contacts, 28 shared, 2 only in run_A, 2 only in run_B.
   - Then: export-methods; explain of `region_1-4/region.json#/contacts/0`; menu item C with `--followup local
     --yes` (rule L4, `inspect_existing_comparison` of `only_in_run/run_A`).
   - **SCRIPTED** Codex-path demonstration (docs/followup.md worked example; stand-in client
     `rnplens_assistant.llm.Stub`, no model, no Codex process). Proposal 1, `export_table_or_methods`, was refused
     with F9. The replan, `inspect_existing_comparison` of `only_in_run/run_B`, was approved. The stored
     over-claiming rationale did not appear in the answer, and there were 0 traceability violations.
   - Both follow-up plans replayed without any model (`matches: true`).
   - The live Codex follow-up awaits the owner's confirmation. FOLLOWUP_SUITE_v1 Part 2 covers it; that part is
     frozen and was not run.
   - The final no-change update recomputed the analysis (v0004 to v0006, same key); see D1.
3. **`3_grouping_6BJG`** (pool A, 50 Boltz-2 samples; target rule: the docs/grouping.md worked example).
   - Groups at t = 0.3 / 0.5 / 0.7: 2 / 5 / 18.
   - At t = 0.5 the sizes in display order are 26, 19, 2, 1, 2. The representatives are s013, s033, s016, s039
     and s020. The designated s001 is a member of group 1.
   - `group-diff 1 2` (the engine-pick group and the next in display order): 14 contacts frequent in both, 4 in
     group 1 only (W39-C18, E41-U21, N46-U21, L53-U21) and 4 in group 2 only (W39-G3, W39-A4, W39-A5, R43-G3).
     38 are frequent in neither. No member has an unresolved position.
   - `rnplens view` covers all 50 structures. Retention and docs-parity checks: PASS. No DockQ label was opened
     (see the access audit).

### Wording scan details
`demos/lib/wording_scan.py` scans HTML, MD, TSV, TXT, SVG and LOG files whole, and every string value of JSON
files. It lists every hit with its sentence.
- Hit classes in 0.4 outputs:
  - demo 1: NEGATED 8, IDENTIFIER 1;
  - demo 2: NEGATED 28, IDENTIFIER 2, plus 7 stored-rationale values that were not scanned (the scripted client's
    rationale, which the record stores and never shows);
  - demo 3: NEGATED 2, IDENTIFIER 1.
- In each package, the frozen Diagnose report (`diagnose_within_BOLTZ2/report.html`/`.json`, an rc3 component)
  holds the sentence "...while the best candidate present improves by about 21." This gives the
  frozen-component AFFIRMATIVE / forbidden-phrase hits (2 / 2 per analysis folder; demo 2 has two analysis
  folders). See O2.
- No 0.4 output in any package names a group, structure or run as best, correct or most likely.
- **Refinement after the first demo-1 run (declared).** The first karyon run of demo 1 stopped at the scan on
  exactly these Diagnose hits, and on the token `probability_of_correctness`. That token is the name of a refused
  statement in Diagnose's `refused_statements` list, which `summary.json` copies. The scanner was then changed:
  outputs of frozen components (`report/`, `diagnose_*`, `evaluate*`) are listed but non-failing, and a hit inside
  a whitespace-free JSON string is classed IDENTIFIER. All three packages were then rebuilt from scratch with the
  final scanner. The failed first runs are kept under `scratch_agent/v04/demos/old_runs/`.

### Replay details
`replay.sh` re-runs the workflow into `scratch_agent/v04/demos/replay/<name>_replay_<utc>` and writes
`checks/replay_check.json`. Two classes are reported separately from strict identity:
- `IDENTICAL_AFTER_ROOT_PATH_NORMALISATION`: outputs record absolute paths;
- `IDENTICAL_EXCEPT_HASHES_OF_PASSING_FILES`: provenance records the SHA-256 of upstream files that carry
  `created_utc` or paths.

Demos 1 and 3 have no other difference. Demo 2 (managed project) also differs in four ways. The post-hoc
classifier `classify_replay_diffs.py` shows these are the only differences:
- timestamps under other key names (`recorded_utc`, `timestamp_utc`, `started_utc`);
- consent record ids, which hash the record including its timestamp;
- analysis and import cache keys and state hashes, which depend on the absolute input paths recorded in the import
  manifest;
- follow-up evidence hashes, which cover statements quoting file hashes.

The pre-registered verdict for demo 2 stays FAIL. See O1.

## Demonstration 1b: RNA sub-range on real data (added at the integrator's request)
The rules were recorded in `DEMOS_PLAN.md` ("Demo 1b") and committed as `9688f57` before any stress-cohort sequence,
structure or contact was read. The scripts are in commit `5871eb8`. Package: `RNPLens_dev_0.4/work/demos/1b_region_subrange/`.

| check | result |
|---|---|
| Target rule (`target_rule.json`) | 1VTM: 1 protein + 1 RNA, 3 nt, does not qualify. 24BR: 4 nt, does not qualify. **2JEA**: 1 protein + 1 RNA, 35 nt, 5 + 5 structures and 5 + 5 confidence files, qualifies. No fallback was needed. |
| Region rule (`region_rule.json`) | 26 windows evaluated; the union of the designated structures (s001 exec_A, s006 exec_B) has 44 distinct contacts; maximum 31 in one window, reached only by **RNA 26-35** (`AAAAAAAAAA`, the 3' end) |
| Steps with the expected exit code | 26 of 26 |
| `rnplens region` (both runs) | 44 contacts in range: 30 shared by both runs; 6 found only in exec_A (R4-A34, R4-A35, E5-A33, D91-A35, R100-A33, R141-A34); 8 found only in exec_B (G1-A33, G1-A34, H2-A31, H2-A32, H2-A33, R82-A27, P96-A29, S140-A35); 0 present in some runs; 0 not determined; coverage COMPLETE in 10 of 10 structures; 28 protein residues contact the window |
| `rnplens explain contact` | run for all 14 run-specific contacts (every contact not shared by both runs) |
| `rnplens view --rna 26-35`, `explain structures`, `explain region_mapping` | exit 0 |
| Wording scan | PASS (90 files; 0.4 outputs: NEGATED 8, IDENTIFIER 1; the only other hits are in the frozen Diagnose report, see O2) |
| Replay (pre-registered) | PASS: 36 JSON files; 9 IDENTICAL, 6 IDENTICAL_AFTER_ROOT_PATH_NORMALISATION, 21 IDENTICAL_EXCEPT_HASHES_OF_PASSING_FILES; 0 missing on either side. Strict: FAIL (paths and hashes, as for demos 1 and 3). Post-hoc: NO_OTHER_DIFFERENCE |
| Data access (**the package run itself** under `strace -f`, with the allow-list from `target_rule.json`) | PASS: 0 forbidden paths, 0 PCfold3D-RNP paths outside the allow-list. Read only `pilot/inputs/boltz/{1VTM,24BR,2JEA}.yaml` and the two `predictions/2JEA/` folders; nothing under `pilot/references`, `pilot/audit`, any score folder or `exec_A_retry1` |

Full suites at `5871eb8`: local 538 passed, 1 failed (the known macOS last-digit test), 17 skipped; karyon track
clone 544 passed, 0 failed, 12 skipped. The commit that adds this section changes only this report.

How to read this:
- Most run-specific contacts are listed by a single non-designated sample. For example, five of exec_B's eight
  come from s008 alone.
- The largest run-specific counts are R100-A33 (3 of 5 exec_A structures, none of exec_B) and P96-A29 (3 of 5
  exec_B structures, including the designated s006, none of exec_A).
- These are listings of what the supplied predictions contain. They are not evidence about the real complex.
- The selected window is a homopolymeric A stretch at the 3' end of the RNA. Contacts there are not tied to a
  sequence-specific nucleotide identity, and a shift of the RNA register along the poly(A) would change which
  positions are listed. Read the window as a placement description, not a site.

## Re-run at bdd137f (Integration 4; integrator's request)
The integration checkout on karyon is at `bdd137f` (clean `git status`). Nothing here changed the pre-registered rules.

**Part A, clean installs at `bdd137f`** (`scratch_agent/v04/clean_install_20261016T140040Z/`; full record:
`CLEAN_INSTALL_LINUX.md`, section "At bdd137f"). The run used fresh venvs, `PYTHONPATH` unset and a working
directory outside the source tree. The wheel and sdist venvs were installed as before. A third **docs** venv was
installed exactly as `docs/installation.md` says: `python -m pip install ".[html,test]"` in the clone, then
`python -m pip install ./assistant`.

| check | wheel | sdist | docs |
|---|---|---|---|
| `rnplens --version` 0.4.0.dev0; `selftest` | PASS | PASS | PASS |
| `doctor` | 12 READY | 12 READY | 12 READY |
| `doctor --agent` (packaged jail) | 17 READY, 4 ACTION REQUIRED (exit 1, as at 5caccec) | same | same |
| Mol* assets vs `VERSION.json` | ALL MATCH | ALL MATCH | ALL MATCH |
| menu A-F, view, region, group, export-methods, update (add run); region 13-23 = docs/region.md; menu E = group --out | all exit 0 | all exit 0 | all exit 0 |
| `rnplens assist --item C --rna 13-23 --runs exec_A,exec_B --followup local --yes` (no model) | exit 0; local rule L4, `inspect_existing_comparison` | same | same |
| `python -m rnplens_assistant replay-followup` of that follow-up | `matches: true` | `matches: true` | `matches: true` |
| `replay-followup` of the FOLLOWUP_SUITE_v1 Part 1 plan (copied) | `matches: true` | `matches: true` | `matches: true` |
| full suite against the installed packages | **547 passed, 0 failed, 12 skipped** | 547 / 0 / 12 | 547 / 0 / 12 |
| no `.pyc` under the source tree after pytest | 0 files | 0 files | 0 files |
| `--followup local` **before** `pip install ./assistant` | n/a | n/a | exit 3: "follow-ups need the RNPLens assistant package, which is not installed. Install it with 'pip install ./assistant' ... Nothing was run." |

The docs-venv exit-3 check behaves as documented. Observation O7: menu item C itself ran and wrote `region_13-23/`
before the follow-up was refused. "Nothing was run" therefore refers only to the follow-up, which a reader could
misread.

**Defect status at `bdd137f`:**
- **D1, fixed.** The reproduction script, run with the installed wheel, reports `computation: REUSED`,
  `key_components_changed: []` and the same key (`not reproduced`). In demo 2 at `bdd137f`, the final no-change
  update after the region, Methods, explain and follow-up outputs reports `analyses/v0004/main (reused from v0004)`.
- **D2, fixed.** The scripted follow-up answer now reads "proposed by a scripted test client (Stub), not a language
  model, approved by the RNPLens policy".
- **D3, fixed.** The installed-package suite has 0 failures in all three venvs.
- **D4, fixed.** `rnplens group-diff analysis 1 2` was re-run at `bdd137f` on a scratch copy of demo 3's analysis
  (`scratch_agent/v04/demos/d4check/`; the demo 3 package was not changed). `overlay.svg` is 580 px wide, and the
  legend labels start at x = 74, 244 and 414.

**Demo 2 at `bdd137f`** (new package `RNPLens_dev_0.4/work/demos/2_interactive_24BR_at_bdd137f/`). The demo scripts
were unchanged; the source was a fresh clone at `bdd137f` (`scratch_agent/v04/demos/src_bdd137f`), on `PYTHONPATH`
for the dev venv, as for the original runs. The original package at `5caccec` is kept unchanged.
- 22 of 22 steps had the expected exit code. Diagnose is now off by default in `rnplens update`, so the analysis has
  no Diagnose report.
- Wording scan: PASS on 90 files. Hits in 0.4 outputs: NEGATED 22. Hits in frozen components: NEGATED 3. The earlier
  frozen-Diagnose "best candidate" hits are gone with Diagnose off.
- **Pre-registered replay check: FAIL, reported as is.** Of 43 JSON files, 9 are IDENTICAL, 7 IDENTICAL_AFTER_ROOT_PATH_NORMALISATION,
  5 IDENTICAL_EXCEPT_HASHES_OF_PASSING_FILES and 22 DIFFERENT; 3 files exist only in the original and 3 only in
  the replay. Strict: FAIL.
- **Post-hoc classification, reported separately (not pre-registered): NO_OTHER_DIFFERENCE.** All 25 differing or
  one-side files differ only in timestamps under other key names, time-derived ids (consent record ids) and hashes
  or keys. As at `5caccec`, those depend on absolute input paths and timestamped files (O1, unchanged).

## Defects found (reported with a minimal reproduction; not fixed by this track): D1-D4 (all four fixed at `bdd137f`, see above)

**D1. Writing 0.4 outputs into a managed project's analysis folder invalidates its cache (medium).**
- `rnplens.state.Project.cache_lookup` accepts an entry only if `tree_hashes(dir) == entry["files"]`. Any new file
  in the folder therefore invalidates it, for example `region_*/`, `methods/`, `explain/` or `followup/`, which
  the other 0.4 commands write there by design.
- The next `rnplens update`, with no input change, recomputes the analysis into a new `analyses/vNNNN/`. The
  update report shows `RECOMPUTED` with `key_components_changed: []` and the same key.
- The earlier region, Methods and follow-up outputs stay behind in the older folder.
- `docs/project_state.md` says a cache entry is reused "only if every file it recorded still has its recorded
  SHA-256", which suggests extra files do not matter.
- Reproduction: `records/v04_integration/defects/repro_D1_cache_invalidated_by_outputs.sh <checkout> <workdir>`
  (bundled 7K9D example: update --init; update reuses; region; update recomputes). Reproduced locally, and in
  demo 2 (v0004 to v0006).
- Possible fixes (owner's choice): compare only the recorded files, or keep derived 0.4 outputs outside the cached
  folder.

**D2. A follow-up answer says "proposed by Codex" when the planner is not Codex (low).**
- With `followup.run(..., mode="codex", client_factory=<stub>)`, `followup_answer.md` reads "`inspect_existing_comparison`
  (proposed by Codex, approved by the RNPLens policy)".
- The record's `model_config` says `model: stub`, but also `provider: openai`, because `llm.Stub` copies the default
  `CONFIG`.
- This is reachable only through the Python API with an injected client (tests and scripted demonstrations), not
  from the CLI.
- Reproduction: demo 2 `demo/analyses/v0004/main/followup/fu_0002/`, or `assistant/tests/test_followup.py::_codex`
  with any approved proposal.
- Suggested: render the proposer from `model_config`, and give the stub its own provider label.

**D3. One assistant test assumes a source-tree install (low; test defect).**
- `assistant/tests/test_followup_codex_defaults.py::test_defaults_never_point_into_the_frozen_evaluation` asserts
  that the default jail's real path lies under `<checkout>/assistant/`.
- With the packages installed from wheel or sdist, the default is the packaged copy in site-packages, which is
  correct and present (the doctor's jail self-probe passed). The test therefore fails in both installed venvs.
- Reproduction: `bash demos/clean_install/clean_install_linux.sh`, then see `logs/50_wheel_pytest.log`. Or install
  the wheels into a fresh venv and run that test from the clone with `PYTHONPATH` unset.
- Suggested: accept `os.path.dirname(rnplens_assistant.__file__)` as the packaged location.

**D4. The group-difference overlay SVG clips its own legend (cosmetic).**
- `groups/diff_1_2/overlay.svg` in demo 3 is declared `width='154' height='256'`. Its three legend labels sit at
  x = 74 ("frequent in both"), x = 244 ("frequent in group 1 only") and x = 414 ("frequent in group 2 only").
- Only the first is inside the drawing, so the legend for the two group-specific colours is not visible.
- The width appears to follow the contact grid, not the legend.
- Reproduction: demo 3 package, or any `rnplens group-diff` whose grid has fewer than about 40 RNA columns. Check
  with `grep -o "<text x='[0-9]*' y='223'>[^<]*" overlay.svg` against the `width` attribute.

## Observations (no defect claimed)
- **O1.** Managed-project keys, state hashes and import manifests record absolute input paths, so a moved project
  or moved inputs produce different keys. Several timestamp fields are not named `created_utc`. The demo-2 replay
  is therefore not comparable under the pre-registered rule, although only timestamps, ids and hashes differ.
- **O2.** The frozen rc3 Diagnose report, written into every analysis folder, contains "best candidate" wording.
  This is outside 0.4 control, but a researcher sees it next to 0.4 pages. This is for the integrator to note in the
  publication-boundary material.
- **O3.** Both development tasks used for regions have very short RNAs (1VTM: 3 nt, 24BR: 4 nt). The fixed rule
  therefore selected the whole RNA in demos 1 and 2. Demonstration 1b closes this gap: 2JEA has 35 nt and the
  region is RNA 26-35.
- **O4.** The baseline in the task (201 passed + 1 + 12 skipped) is out of date at `5caccec`. In the local `rnplens`
  conda env there is no `rnplens` console script, so `tests/test_output_schemas.py::test_fresh_outputs_match_schema`
  fails for environmental reasons unless such a command is on PATH. The local runs used a shim that calls
  `rnplens.cli.main` with the checkout on `PYTHONPATH`.
- **O5.** The karyon dev venv (`RNPLens_dev_0.3/venv`) has `RNPLens_dev_0.3/RNPLens/src` on `sys.path`, and the
  access audit shows it is opened read-only. `PYTHONPATH` takes precedence, and every package's
  `logs/environment.json` records `rnplens.__file__` in the track clone with version `0.4.0.dev0`.
- **O6.** karyon's Codex CLI is the snap 0.114.0. `codex debug models` does not exist in that version, and the
  doctor reports the resulting error text in the model line.
