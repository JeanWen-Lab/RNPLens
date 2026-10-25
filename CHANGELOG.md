# Changelog

## 0.4.0.dev0 — interactive workflow (branch `dev/0.4-interactive`; not merged, not released)

Built on `0.3.0.dev0` plus the Gate-1 fixes (frozen assistant commit `f998830`). No computation of Evaluate, Report or
Diagnose changed. Every new output carries a provenance block and evidence IDs. 0.4 is a development candidate; a
public release is not approved.

**Release-candidate preparation (owner programme of 18 Oct 2026, section 10; nothing published):**
- `docs/platforms.md` (supported-platform matrix; RNPLens Standard and Assistant; exact macOS-to-Linux SSH commands;
  native macOS AI unsupported), `docs/model_and_privacy.md`, `docs/example_data_provenance.md` (redistribution
  status per file group, with the open and unknown permissions named), `docs/release_conditions.md` (why the release
  manifest stays FAIL), `docs/code_availability.md` (draft with placeholders). `CITATION.cff`: version 0.4.0.dev0;
  authors, affiliations and DOI are owner placeholders. `rnplens-assistant` no longer offers the unused `llm`
  (openai) extra. `tests/test_release_prep.py`.

**RC changes (branch `rc/0.4-candidate`, owner programme of 18 Oct 2026, section 6):**
- **Controlled input errors.** A missing or wrong input path (Evaluate/Report contracts, analyse projects and
  references, compare tables, example-contract folder, export-methods `--project`/`--run-dir`, update `--reference`,
  FASTA paths) is refused with exit code 2 and `refused: ... (nothing was run)` before anything runs; before, 12 such
  cases ended in a Python traceback and `analyse --reference <missing>` / `export-methods --project <missing>` exited 0.
  A missing required package gives the exact install command (exit code 3) instead of a `ModuleNotFoundError`
  traceback; `rnplens doctor` still runs. `tests/test_input_errors.py`.
- **Result links.** The question menu (items A, B, C, E) and the natural-language mode list the contact tables
  (`report/contacts_by_output.json`, `report/result.json`, `region_*/region_contacts.tsv`) and the offline Mol* page;
  the page is written with the unchanged `rnplens view` when the analysis has none (`rnplens.result_links`; the
  NL run folder also gets `result_links.json`). `tests/test_result_links.py`.

**RC changes (branch `rc/0.4-candidate`, owner decisions of 18 Oct 2026):**
- **Component command lines refuse blocked routes (F1).** The component packages' own command lines
  (`python -m rnpbench evaluate run|selftest`, `python -m rnpbench selftest`, `python -m rnpbench toolkit selftest`,
  `python -m rnpbench diagnose …`, `python -m rnpbench_evaluate[.cli] evaluate|selftest`, `python -m rnpbench_diagnose…`,
  `python -m rnpbench_core…`, other component submodules and the same packages run by path) bypassed the 0.4 blocks.
  They now refuse with `LEGACY_ROUTE_REFUSED` and exit code 5 before anything runs, naming the `rnplens` command to use
  (`rnplens/legacy_routes.py`, one call in each component `__init__.py`; `tests/test_legacy_route_refusal.py`).
  `validate`, `provenance`, help, `--version`, Report and the Python API are unchanged; the frozen sources and every
  computation are byte-identical.
- **Edited inputs name their continuation (C7-11).** SHA-256 protection is unchanged: `rnplens relink` accepts a
  moved file only with its recorded SHA-256 and refuses an edited one. The refusals (`relink`, `update` in a moved
  project, and every `PORTABILITY REFUSED` message) now say that an edited file is a new input version and name the
  existing workflow: `rnplens update PROJECT` (edited in place) or the exact
  `rnplens update PROJECT NEW_FOLDER --remove-input OLD_FOLDER` (edited copy elsewhere). No new command; earlier
  versions stay byte-identical (`tests/test_relink_edited_input.py`; docs/project_state.md, "Edited input files").
- **Viewer wording.** The page no longer says it "computes no contacts": contacts are taken from Report's record, and
  their distances are recomputed from the structure file when the page is written and shown only where the
  recomputed contacts equal Report's record.
- **Viewer status (owner report, 18 Oct 2026).** Basic display and interaction were confirmed manually by the owner on
  macOS (2JEA page; records/viewer/MOLSTAR_VISUAL_VERIFICATION.md). The label now names the two checks still pending
  (switching between binding-hypothesis representatives; offline operation); the viewer remains not fully visually
  qualified.

**r3 changes (track release-docs-r3, owner decision on the Round 2 results, 17 Oct 2026):**
- **Four-axis geometry blocked in every public output (release blocker).** `rnplens evaluate run` no longer shows
  or writes Evaluate's four-axis geometry values (protein-internal Cα RMSD, RNA-internal C4′ RMSD, RNA placement C4′
  RMSD and their aligned-position counts). The frozen component runs unchanged into a private temporary directory;
  the public command publishes its output filtered: `result.json` `geometry.status` `BLOCKED` with `blocked_code`
  `GEOMETRY_BLOCKED_IN_0.4`, `blocked_reason` and `fields_withheld`, plus `rnplens_public_output` (SHA-256 of the files
  before filtering); `result.csv` `geometry_status` `BLOCKED`, `geometry_exclusion` `GEOMETRY_BLOCKED_IN_0.4` and empty
  value columns; `summary.txt` and the terminal output state the block. The unfiltered copy is deleted.
  `rnplens selftest` and `rnplens evaluate selftest` mask the geometry values in what they print (checks, verdict and
  exit code unchanged). Every entry point is listed in `records/release/GEOMETRY_BLOCK_INVENTORY.md` and tested
  (`tests/test_geometry_blocked.py`). DockQ, DockQ class, fnat, iRMSD and LRMSD are numerically unchanged from rc3 and
  are not a replacement for the geometry decomposition. The run record of `evaluate run` states that its result
  files are filtered. The rc3 records in `examples/expected_output/` are unchanged (historical).
- **Diagnose example statements masked in the self-tests.** `rnplens selftest` and `rnplens diagnose selftest`
  still run Diagnose's contract checks and example regression on bundled data, but show
  `Diagnose interpretation BLOCKED (checked, not shown)` in place of each interpretation statement (protein-side and RNA-side
  disagreement with band and percentile, an unavailable statement, an applicability warning) that the frozen
  Diagnose command prints. Checks, verdict, exit code and the `--out` record are unchanged; the frozen component still
  prints the statements (`tests/test_diagnose_selftest_masked.py`).
- **Menu exit status.** In `rnplens assist`, a blocked capability (a function that raises `DIAGNOSE_BLOCKED`, or
  returns the status `BLOCKED`) now exits **5**; a function's refusal or failure, including a refusal of an answer it
  cannot accept, exits **4**. Before, a raised block ended in an uncaught error and a `BLOCKED` result counted as
  success. The interactive menu prints `BLOCKED:` and stays open (`tests/test_assist_blocked_exit.py`).
- **Capability classifications J5-J7 (owner wording).** `analyse`: qualified only for its tested, enabled analysis
  routes. `doctor` and the menu: new descriptive functionality; environment readiness does not qualify the
  scientific agent. `selftest`, `provenance` and `example-contract`: qualified as tested software infrastructure, not
  as independent evidence of structural accuracy. Diagnose and four-axis geometry remain blocked.
- README Example 1 and `docs/images/example_evaluate.png` show the 0.4 Evaluate output.

**r2 changes (track release-docs-r2, owner decision of 17 Oct 2026):**
- **Diagnose BLOCKED in the public interface** until re-qualification. `rnplens diagnose run | preflight | validity`
  and `--with-diagnose` (`analyse`, `update`) refuse with `DIAGNOSE_BLOCKED` and **exit code 5**, and read or write
  nothing. `rnplens analyse` never runs Diagnose and records `steps.diagnose_blocked` in its summary
  (`--without-diagnose` is still accepted, as a no-op). A managed project whose contract still asks for Diagnose is
  refused (exit 5) until it is declared off with `rnplens update P --without-diagnose`. `rnplens selftest` still
  runs Diagnose's internal contract checks. The frozen rc3 component is unchanged.
- **Diagnose out-of-sample figure (documentation only; release-blocker track diagnose_docs, 2026-10-23).** rc3's
  ρ 0.525 [0.450, 0.593] on 807 targets / 456 protein clusters is historical: it used the superseded residue
  correspondence (`SCORE_DECOMP_V1`). The corrected figure is ρ 0.530 [0.455, 0.598] on 761 targets / 435 protein
  clusters (`CONSTRUCT_POSITION_V2`, rule revision R2; 807 admitted less 46 without a construct-position protein
  correspondence), research evidence and not a re-qualification. Updated: `docs/diagnose.md`, `docs/limitations.md`,
  and banners on `docs/validation/OOS_VALIDATION_RESULTS.md` and `docs/validation/CAMPAIGN_SCOPE_REVISION.md`.
  Unchanged as historical records: the frozen rc3 Diagnose component, its expected outputs and contract tests
  (still 0.525). Not changed: the pinned guide `docs/which_analysis_should_i_use.md` and its assistant copy (still
  0.525; its correction needs a LIVE_QUALIFICATION amendment and an EVALUATED_GUIDE re-pin and is deferred until
  after the sealed evaluation). Diagnose remains BLOCKED.
- **macOS numerical tolerance (Amendment 1).** In `test_report_numbers_equal_the_rc3_expected_output` only,
  `rna_pose_difference_A` is compared with an absolute tolerance of 1e-12 A; everything else stays exact, and the rc3
  expected values are unchanged (`records/release/TOLERANCE_POLICY_AMENDMENT_1.md`).

**Capability categories** (owner rules; each capability in exactly one; full table in `docs/capabilities.md`):
1. **Qualified:** verified Report routes; Evaluate's DockQ-family metrics (DockQ, DockQ class, fnat, iRMSD, LRMSD);
   `import` and `compare`; `analyse`, qualified only for its tested, enabled analysis routes; `selftest`,
   `provenance` and `example-contract`, qualified as tested software infrastructure, not as independent evidence of
   structural accuracy.
2. **New descriptive functionality:** region contacts, evidence lookup, Methods export, clarification and resume,
   incremental analysis, tested grouping operations (`group`, `group-diff`), `doctor` and the question menu `assist`
   (environment readiness does not qualify the scientific agent),
   and the offline viewer `view` (automatically tested, awaiting manual visual confirmation; not fully visually
   qualified).
3. **Experimental:** the Codex result-aware follow-up (with its local mode, which the software labels EXPERIMENTAL)
   and the natural-language planner, neither live-qualified; scientific claims about the usefulness of grouping
   for researchers (retrospective pool A, k = 5: 0.86 of cases with an acceptable structure among the
   representatives, against 0.94 for confidence order; grouping is never an accuracy selector).
4. **Blocked:** four-axis geometry (no public output shows its values), the affected RNA-conformation measurements, Diagnose (user-facing), accuracy-based
   candidate ranking; also unavailable or unsupported: structure prediction, mutation advice, a snap-installed Codex,
   Windows.

**Platforms.** Linux x86-64 is the tested interactive environment. On macOS arm64 the toolkit runs; the one known
numerical parity difference is covered by the narrowly scoped tolerance above; the language-model modes are
unsupported on macOS.

**Reproducibility.** Numerical/evidence reproducibility: supported by the reported tests. Canonical-file byte
reproducibility: passed in four development cases (1VTM, 7K9D, 2JEA, 2Q66) under the new contract
(records/replay/DETERMINISM_CONTRACT_v1.md, records/replay/REPLAY_REQUALIFICATION_REPORT.md). Complete
managed-project byte reproducibility: not yet established. The original pre-registered byte-identical replay check
failed (22 of 43 files), and that verdict stands.

**Viewer.** Highlighted residues are now coloured on the cartoon ribbon as well as in ball-and-stick (the previous
coincident highlight cartoon did not render in Mol* 5.13.1). Automatically tested in headless Chrome 155 with
software WebGL (records/viewer/MOLSTAR_VISUAL_VERIFICATION.md); awaiting manual visual confirmation on a real screen.

**Commands.** Each new function also appears in the `rnplens assist` menu, items A–F:
- `rnplens region`: contacts in a declared RNA (and protein) range from Report's per-structure records. It lists:
  - contacts shared by all runs, and those found in only one run;
  - designated structures versus additional samples;
  - coverage-checked missingness ("not observed" is not "no contact");
  - TSV, JSON, HTML and PNG outputs.
- `rnplens explain`: deterministic evidence lookups (structures, files, definitions, versions, exclusions, unavailable
  metrics, correspondence, region mapping).
- `rnplens export-methods`: a Methods draft in which every sentence traces to a record field, plus a provenance
  manifest.
- `rnplens update` and `rnplens clarify`: a versioned, atomic project state with typed clarifications and resume.
  - Recomputation is driven by cache keys (input hashes, construct, correspondence, tool version, configuration,
    selection rules).
  - A before/after report separates candidate, correspondence and contract changes.
- `rnplens group` and `rnplens group-diff`: binding-proposal grouping per frozen Specification B v2 (surface, then
  contact register; exact UPGMA; order-invariant).
  - The engine pick is shown first. Groups are never ordered by size.
  - RNA conformation difference Q is unavailable (blocked correspondence route).
- `rnplens view`: an offline Mol* 5.13.1 page with Report's contacts highlighted (vendored, MIT; no network access).
  Automatically tested, awaiting manual visual confirmation; not fully visually qualified.
- `rnplens doctor`: READY / ACTION REQUIRED / UNSUPPORTED checks. With `--agent` it adds Codex CLI, sign-in,
  model, bubblewrap and a jail self-probe. It changes nothing.
- `rnplens assist`: the question menu (no language model). The `--nl` option uses the bounded planner
  (EXPERIMENTAL; not live-qualified), and an EXPERIMENTAL follow-up (local rules always; Codex only with recorded
  consent; not live-qualified) is offered afterwards.

**Assistant (successor of the frozen `f998830`):**
- The Codex adapter defaults now point to this installation's own jail. The calls folder defaults to
  `~/.rnplens/codex_calls`.
- The jail is portable (`CODEX_HOME` and `HOME`; standalone install or `RNPLENS_CODEX_BIN`) and has a no-model
  self-probe.
- New tools are registered (region comparison, explain, export). Blocked tools stay blocked.

**Fixes found during integration:**
- The menu now reports refused or failed results as such (exit 4); before, they were reported as success.
- Region ranges are accepted as text or as a pair, and verified identical results are reused.
- The difference map prints unreduced fractions.

**Qualification records:** `records/grouping/` (Spec B v2 amendments 1–4, code freeze, descriptive development-pool
report), `assistant/evaluation_v04/FOLLOWUP_SUITE_v1/` (Part 1 21/21; Part 2 frozen, not run) and the project-state
qualification report.

## Gate-1 fixes on 0.3.0.dev0 (branch gate1/assistant-companion; not merged, not released)

Fixes for the 0.3.0.dev0 first-use test (6DCB). No computation of Evaluate, Report or Diagnose changed.
- **M1, m9 (import).** Boltz-2 output copied out of its folders is recognised when Boltz-2's own
  `confidence_<model>.json` (with `confidence_score`) is beside each file. An import with nothing includable is
  refused (exit 2, nothing written), and unrecognised files trigger an `--engine` hint.
- **M2 (compare).** Relative paths resolve against each TSV's own directory; all inputs are checked first; a
  missing file is an input error (exit 2). An Evaluate refusal is `RUN_FAILED` with exit 1, never
  `NOT_EVALUABLE_IN_BOTH`.
- **M3, m5, m6 (compare).** No bootstrap interval from one resampling unit; the direction-only meaning of
  IMPROVED/WORSENED is printed; `targets_by_class` lists every class including UNCHANGED; LF line endings.
- **M4 (analyse).** Two runs of one engine: Report's own two-output repeat agreement on the designated structure of
  each run, labelled as between runs and traced.
- **Geometry route withheld.** `compare` and the `analyse` summary no longer show the four-axis geometry values
  (known correspondence defect, stop report 2026-10-14). `compare` adds DockQ's iRMSD and LRMSD.
- **m1–m3 (summary).** Neutral section headings; the "not closest to the reference" limit is replaced when Evaluate
  ran; the Evaluate table names run, sample and engine designation.
- **Not addressed here:** M5 (Diagnose pooling of runs) and the Diagnose requalification against CP-V2.

## 0.3.0.dev0 — development (branch dev/0.3.0; not released)

- **New workflow commands.** `rnplens import`, `rnplens analyse` and `rnplens compare` (see
  [docs/workflow.md](docs/workflow.md)). They import engine output folders, run the unchanged tools and present
  their outputs; no computation of Evaluate, Report or Diagnose changed.
- **Unchanged components.** Every file of the qualified components is byte-identical to 0.2.0rc3.
- **Known limitation carried from rc3 and now stated.** Report computes repeat agreement only for an engine with
  exactly two eligible structures. `analyse` states "not computed" for any other number, never zero.

## 0.2.0rc3 — release candidate (not released)

- **Diagnose applicability domain enforced.** Each run is checked against the conditions under which its
  statements were validated: Boltz-2 candidates, 5–50 per target, for `within_engine`; designated outputs of
  three or more of Boltz-2, Chai-1, RF3 and RoseTTAFold2NA for `cross_engine`; one protein chain and one RNA
  chain per structure for both. Outside these conditions Diagnose refuses with the reasons, unless
  `--allow-outside-validated-domain` is given; the report then records and displays that it is outside the
  validated domain. `within_engine` now takes `--engine`. No computed value changed. `report.json` gains
  `applicability`; the Diagnose example-regression reference gained exactly that key and the declared engine.
- **Run record.** Every `run` writes `rnplens_run.json`: RNPLens release, command, and SHA-256 of every input and
  output file.
- **Output schemas.** JSON Schemas for Evaluate, Report, Diagnose and the run record (`docs/schemas/`), with tests.
- **Security.** A Report `case_id` that is a path (contains `/`, `\`, a control character, or starts with `.`) is
  refused; previously it could make Report fail after writing part of its output. Tests check that hostile
  identifiers and file names are escaped in the HTML pages. New `SECURITY.md` and an issue template.
- **Removed** the import alias `rnpbench_predict`, which no RNPLens tool used.
- **Documentation.** New `docs/which_analysis_should_i_use.md` (choosing a tool, a table of every reported value,
  Diagnose's validated conditions), `docs/paper_reproducibility.md`, `examples/DATA_PROVENANCE.tsv` and screenshots
  of genuine outputs in the README.

## 0.2.0rc2 — release candidate (not released)

- **One public name.** All human-readable text now uses RNPLens: the help and error messages of every command and
  verb, self-test lines, the heading of Evaluate's `summary.txt`, and the titles, headings and provenance line of
  the Report and Diagnose HTML pages. The change was made by an enumerated table of exact-match text replacements;
  no computation, JSON key, schema, contract or configuration identifier, or frozen scorer file changed. Report's
  stored example page received the same three replacements. Remaining historical identifiers are listed in
  `docs/identifiers.md`.
- **Commands.** Only `rnplens` is installed. The compatibility commands `rnpbench`, `rnpbench-evaluate`,
  `rnpbench-report` and `rnpbench-diagnose` were removed; the same operations are `rnplens evaluate|report|diagnose`.
- **Licence.** MIT (`LICENSE`).
- **Documentation.** The verbatim component READMEs and tutorial were replaced by the RNPLens guides; the frozen
  validation records moved to `docs/validation/`. New `docs/identifiers.md`.
- **Expected outputs** of the worked examples regenerated; they differ from rc1 only in the display strings above.

## 0.2.0rc1 — release candidate (not released)

First distribution candidate of RNPLens.

- **Distribution.** One installable Python distribution, `rnplens`, replacing the five internal component
  distributions of the qualified component set 0.2.0.dev1.
- **Command.** New `rnplens` command (`evaluate`, `report`, `diagnose`, `selftest`, `provenance`,
  `example-contract`, `--version`), a dispatch-only wrapper.
- **Implementation unchanged.** The six component import packages were byte-identical to the qualified
  0.2.0.dev1 set, including the eight hash-verified frozen scorer files, the regression fixtures and the expected
  outputs.
- **Documentation and examples.** README, user guides, two end-to-end examples with expected outputs, and a
  GitHub Actions workflow (Ubuntu and macOS; Python 3.10–3.12).
- **Not included.** Internal fixtures of AlphaFold 3, Chai-1, RF2NA and RF3 outputs, Report's internal acceptance
  suite and benchmark adapter, the benchmark resource itself, and qualification records.

## History of the implementation (internal, before the public name)

- Component set 0.2.0.dev1 (2026-10-10, internal identifier "RNPBench toolkit"): internally qualified on Linux
  x86-64 (Python 3.10–3.12) and on a clean macOS arm64 installation; not released.
- Its components: Evaluate 0.1.1, Report 1.0.0 (first called Predict), Diagnose 0.2.1.
