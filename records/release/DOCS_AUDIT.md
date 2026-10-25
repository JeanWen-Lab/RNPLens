# Release documentation audit for RNPLens 0.4 (track release-docs, 16 Oct 2026)

**Scope.** README.md, CHANGELOG.md, docs/*.md (except `docs/reproducibility.md`, owned by the replay track), the
`rnplens --help` texts and the capability registry (`src/rnplens/capabilities.py`, as returned by
`capabilities.available()`), at base commit `cf81acd`. The authority is the owner's decision note of 16 Oct 2026.
0.4 remains a development candidate; nothing was merged, tagged, pushed or released.

**Rule applied.** Every user-facing capability appears in exactly one of four categories: (1) qualified tools,
(2) new descriptive functions, (3) experimental behaviour, (4) blocked or unsupported. The canonical table is the
new page `docs/capabilities.md`; README and CHANGELOG summarise it and link to it.

## 1. Registry as found (`capabilities.available()` at cf81acd)

| registry id | module | menu | status | category assigned |
|---|---|---|---|---|
| interface_overview | overview | A | QUALIFIED | 1 |
| region_contacts | region | B | DESCRIPTIVE | 2 |
| region_run_comparison | region | C | DESCRIPTIVE | 2 |
| explain_evidence | evidence_query | D | DESCRIPTIVE | 2 |
| export_methods | methods_export | F | DESCRIPTIVE | 2 |
| clarify_and_resume | clarify | - | DESCRIPTIVE | 2 |
| incremental_update | incremental | - | DESCRIPTIVE | 2 |
| hypothesis_grouping | grouping | E | DESCRIPTIVE | 2 |
| group_difference | grouping | - | DESCRIPTIVE | 2 |
| setup_check | doctor | - | DESCRIPTIVE | 2 |
| diagnose_interpretation | (BLOCKED) | - | UNAVAILABLE | 4 |
| geometry_four_axis | (BLOCKED) | - | UNAVAILABLE | 4 |
| rna_conformation_difference | (BLOCKED) | - | UNAVAILABLE | 4 |
| ranking | (BLOCKED) | - | UNAVAILABLE | 4 |
| structure_prediction | (BLOCKED) | - | UNAVAILABLE | 4 |
| mutation_advice | (BLOCKED) | - | UNAVAILABLE | 4 |

Every registry status maps to the category given to it in the documentation; no registry entry was found in a
different category in the edited documents. Capabilities that are **not registry entries** were placed as follows
(the registry describes menu functions only): Evaluate DockQ route, `import`, `analyse`, `compare`, `selftest`,
`provenance`, `example-contract` -> 1; the question menu `assist` -> 2; natural-language planner (`assist --nl`),
follow-up (`--followup local|codex`), grouping used as an inspection aid, `rnplens view` -> 3; snap-installed Codex,
language-model modes on macOS, Windows -> 4.

## 2. Mismatches found and changes made (documentation only)

| # | file | mismatch at cf81acd | change |
|---|---|---|---|
| D1 | docs/capabilities.md (new) | no single page placed each capability in one category | new canonical four-category page, with platform, replay and release status |
| D2 | README.md, status block | flat list of 0.4 commands; `rnplens view` presented as a working feature; only the follow-up flagged EXPERIMENTAL; no platform, replay or release-approval statement | replaced by the four categories, the retrospective (0.86 vs 0.94 at k = 5), "rendering verification pending; no working visual interface claimed", Linux as the tested interactive environment, macOS not fully qualified, replay failure with a PLACEHOLDER, "public release not approved" |
| D3 | README.md, Evaluate bullet and Example 1 | geometry route presented as a qualified output | states that only the DockQ route is qualified in 0.4 and the geometry route is blocked; Example 1 notes that the geometry lines are unchanged rc3 output |
| D4 | README.md, Diagnose bullet | no 0.4 status | states that Diagnose interpretation is not re-qualified and not offered by the menu |
| D5 | README.md, Quick start | "Linux or macOS" without 0.4 qualification status | Linux tested; macOS runs, not fully qualified |
| D6 | README.md, documentation index | no link to the category page | link added |
| D7 | CHANGELOG.md, 0.4 section | no categories; `view` without status; planner without status | category list, platform and replay paragraph (PLACEHOLDER), `view` EXPERIMENTAL (rendering not verified), planner and follow-up "not live-qualified" |
| D8 | docs/installation.md | "Linux or macOS ... the platforms on which this release candidate was qualified" read as a 0.4 claim | separated: rc3 qualified on both; for 0.4 Linux is the tested interactive environment, macOS not fully qualified (difference cited) |
| D9 | docs/limitations.md | platform bullet stated macOS as qualified; no viewer, replay or live-qualification limits | platform bullet split rc3 / 0.4; new bullets: viewer rendering not verified (PLACEHOLDER), byte-identical replay failed (PLACEHOLDER), language-model modes not live-qualified |
| D10 | docs/setup_and_privacy.md | macOS row "supported (qualified platform ...)"; Linux row "qualified platform"; viewer and planner rows without status | macOS "runs; not fully qualified for 0.4"; Linux "the tested interactive environment for 0.4"; viewer and planner rows marked EXPERIMENTAL. Phrases asserted by `tests/test_assist.py` kept verbatim |
| D11 | docs/assist.md | viewer section described as working; `--nl` section without status | viewer section and bullet marked EXPERIMENTAL with "on-screen rendering not verified" (PLACEHOLDER); `--nl` section marked EXPERIMENTAL, not live-qualified, differs from `f998830` |
| D12 | docs/evaluate.md | geometry route without 0.4 status | 0.4 status box: only the DockQ route qualified; geometry blocked; values printed by `evaluate run` are not results |
| D13 | docs/diagnose.md | no 0.4 status | 0.4 status box: interpretation not re-qualified; listed as blocked |
| D14 | docs/grouping.md | retrospective stated qualitatively only | numbers added (k = 5: 0.86 vs 0.94; k = 3: 0.84 vs 0.88; 50 targets; DockQ >= 0.23); "inspection aid, never an accuracy selector" |
| D15 | docs/workflow.md | no 0.4 status | qualified in 0.4; geometry withheld, Diagnose interpretation not re-qualified |
| D16 | docs/project_state.md | no replay status | byte-identical replay failure with PLACEHOLDER |
| D17 | docs/interpretation.md, docs/quickstart.md | geometry route described without 0.4 status | one-sentence 0.4 notes |

Each edited page was checked with `rnplens.trace.wording_audit`: no edit added a hit (counts before/after are equal
for every file; pages tested by the suite remain at 0). The full suite was rerun after the edits (see the hand-back
report).

**Placeholders.** Two kinds, both literally marked `[PLACEHOLDER - ...]`: the replay track's remediation and retest
result (README, CHANGELOG, capabilities, limitations, project_state) and the viewer track's on-screen verification
result (capabilities, limitations, assist). The integrator must replace each before any release candidate; a
search for `PLACEHOLDER` lists them.

## 3. Judgement calls J1-J7 (owner decision on the Round 2 results, 17 Oct 2026; applied in r3)

The owner accepted the J1-J7 classifications, with this wording for J5-J7 and with Diagnose and four-axis geometry
remaining blocked. As they now read in `docs/capabilities.md`, README and CHANGELOG (r3):

| # | capability | category | owner wording (r3) / status |
|---|---|---|---|
| J1 | offline viewer `rnplens view` | 2, New descriptive | automatically tested, awaiting manual visual confirmation; not fully visually qualified (the owner's Mol* screen check is still pending) |
| J2 | local follow-up `--followup local` | 3, Experimental | unchanged (the software labels it EXPERIMENTAL) |
| J3 | Diagnose (user-facing) | 4, Blocked | Remain blocked (commands exit 5; in the menu a blocked function now also exits 5, r3 B) |
| J4 | Evaluate four-axis geometry | 4, Blocked | Remain blocked; **r3: no public entry point shows the values** (`rnplens evaluate run` writes geometry status `BLOCKED`, code `GEOMETRY_BLOCKED_IN_0.4`; selftests mask them; `records/release/GEOMETRY_BLOCK_INVENTORY.md`) |
| J5 | `rnplens analyse` | 1, Qualified | "Qualified only for its tested, enabled analysis routes" |
| J6 | `rnplens doctor` and the question menu | 2, New descriptive | "New descriptive functionality; environment readiness does not qualify the scientific agent" |
| J7 | `selftest`, `provenance` and `example-contract` | 1, Qualified (infrastructure) | "Qualified as tested software infrastructure, not as independent evidence of structural accuracy" |

The r2 text of this section follows, kept for the record; where it says the geometry values are "still printed",
that described r2 and is superseded by r3.

### 3a. (r2 record) Judgement calls J1-J4, re-examined under the owner's category rules (r2, 17 Oct 2026)

Rules applied (owner decision note, 17 Oct 2026): **Qualified** = existing verified Report routes, approved
DockQ-family Evaluate metrics and the corresponding qualified import/compare operations; **New descriptive** =
region contacts, evidence lookup, Methods export, clarification/resume, incremental analysis and tested grouping
operations; **Experimental** = the Codex result-aware follow-up (and the natural-language planner) and scientific
claims about the usefulness of grouping; **Blocked** = four-axis geometry, affected RNA-conformation measurements,
Diagnose (user-facing) and accuracy-based candidate ranking. Viewer label: "automatically tested, awaiting manual
visual confirmation; not fully visually qualified".

| # | capability | round-1 placement (cf81acd..7d5d09b) | **r2 placement** | reason under the owner's rules |
|---|---|---|---|---|
| J1 | offline viewer `rnplens view` | 3, Experimental (separate heading) | **2, New descriptive**, with the owner's viewer label | Experimental is now reserved for the Codex follow-up, the planner and grouping-usefulness claims; the viewer shows Report's own per-structure contact records (descriptive) and is automatically tested, so it moves to 2 with the label that withholds full visual qualification |
| J2 | local follow-up `--followup local` (deterministic rules, no language model) | 3, Experimental | **3, Experimental** (unchanged) | under the rules it is not the Codex follow-up and would fit 2, but the software itself labels the whole follow-up feature EXPERIMENTAL in pinned sources (`assistant/rnplens_assistant/followup.py` record `"status": "EXPERIMENTAL"`; `src/rnplens/assist.py` `FOLLOWUP_HINT` and `--followup` help). The docs must not contradict what the user sees, so it stays in 3 until the integrator decides on the label (see section 4, R2-C2) |
| J3 | Diagnose as a whole (run, preflight, validity, interpretation; Diagnose inside analyse and update) | 4, Blocked (command retained) | **4, Blocked**, now enforced in code | owner: "Diagnose (user-facing)" is Blocked. r2 makes the public commands refuse (exit 5). Input validation in `import` is not the Diagnose workflow (it never loads the component; tested) and stays with import in 1; Diagnose's internal contract checks stay in `selftest` (software checks) |
| J4 | Evaluate four-axis geometry printed by `rnplens evaluate run` | 4, Blocked (printed but not a result) | **4, Blocked** (unchanged) | owner: four-axis geometry is Blocked. The rc3 Evaluate component is frozen, so the values are still printed; the docs say they are not results. Suppressing them in the public wrapper (as for Diagnose) is offered to the integrator (section 4, R2-C3) |

**The four rows as they now read in `docs/capabilities.md`** (verbatim):

J1 (category 2 table):
> | offline structure viewer: **automatically tested, awaiting manual visual confirmation; not fully visually qualified** | `rnplens view` | (not a registry entry) |

J2 (category 3 list):
> - **Codex result-aware follow-up** (`rnplens assist ... --followup codex`). The scripted part of FOLLOWUP_SUITE_v1
>   passed 21 of 21; no live call has been made, so it is **not live-qualified**. The local mode of the same feature
>   (`--followup local`, deterministic rules, no language model) is labelled EXPERIMENTAL by the software and is
>   listed here for that reason (see `records/release/DOCS_AUDIT.md`, J2).
> - **Natural-language planner with the 0.4 tools** (`rnplens assist --nl`). Not qualified live; it differs from the
>   assistant under the sealed evaluation (`f998830`). LLM-free replay of a recorded plan
>   (`python -m rnplens_assistant replay`) belongs to this feature.
> - **Scientific claims about the usefulness of grouping for researchers.** Group representatives are a way to *see*
>   the alternative binding proposals; they are never an accuracy selector. In the retrospective pool-A check (50
>   targets with an acceptable candidate, DockQ >= 0.23; frozen labels read only after the grouping code freeze), a
>   fixed set of k = 5 representatives contained an acceptable structure in **0.86** of the targets, against **0.94**
>   for the first five structures in engine-confidence order (k = 3: 0.84 against 0.88). Grouping did not retain
>   acceptable proposals more often than confidence order (`records/grouping/GROUPING_QUALIFICATION_REPORT.md`).
>   Whether grouping helps researchers is not established.

J3 (category 4 table):
> | **Diagnose (user-facing)**: `rnplens diagnose run`, `preflight` and `validity`, and Diagnose in `rnplens analyse` and `rnplens update` (`--with-diagnose`) | **BLOCKED** until re-qualification: the commands refuse with `DIAGNOSE_BLOCKED` and **exit code 5**, and read or write nothing; its statements and validated domain rest on evidence that is being recomputed under the corrected correspondence. The frozen rc3 component is unchanged |

J4 (category 4 table):
> | Evaluate four-axis geometry (protein-internal, RNA-internal and RNA-placement RMSD) | blocked: residue-correspondence defect found on 2026-10-14; withheld by `compare`, `analyse` and the menu; the standalone `rnplens evaluate run` still prints the rc3 values, which are not results in 0.4 |

**Further placements made in r2 that the owner may want to check** (not among J1-J4):
- **J5, `rnplens analyse` in 1, Qualified.** The owner's rule names import and compare; `analyse` is the project run
  of Report and Evaluate's DockQ route, and with Diagnose blocked it computes nothing else, so it is placed in 1 as
  "Report and Evaluate run on an imported project". If the owner prefers, it can move to 2.
- **J6, `rnplens doctor` and the question menu in 2.** Neither is named by the owner's rules; both are new, tested and
  produce no scientific result (registry: `setup_check` DESCRIPTIVE; the menu is the interface to category-2
  functions).
- **J7, `selftest`, `provenance`, `example-contract` in 1** as supporting commands of the qualified tools (software
  checks and records, no scientific output).

**Round-1 text (superseded, kept for the record).** J1: viewer in 3 because it "needs further evidence". J2: local
follow-up in 3 because the code labels it EXPERIMENTAL. J3: Diagnose as a whole in 4, command retained unchanged. J4:
geometry still printed, marked blocked.

## 4. Mismatches NOT fixed here (outside this track's files; proposed for the integrator)

| # | where | text at cf81acd | proposed change |
|---|---|---|---|
| C1 | `src/rnplens/doctor.py` (platform check) | `Darwin arm64 is a qualified platform` (READY) | "Darwin arm64: toolkit runs; not fully qualified for 0.4 (one known numerical parity difference)" |
| C2 | `src/rnplens/cli.py`, `rnplens --help` | `view` listed with the other interactive commands, no status | append "(EXPERIMENTAL: on-screen rendering not verified)" |
| C3 | `src/rnplens/cli.py`, `rnplens --help`; `rnplens evaluate --help` | "DockQ route and geometry route, reported separately" | add "geometry route blocked in 0.4 (correspondence defect)" |
| C4 | `src/rnplens/cli.py`, `rnplens --help` | `diagnose` listed under tools without status | add "interpretation not re-qualified in 0.4" |
| C5 | `src/rnplens/assist.py`, `--nl` help | "optionally hands a question to the Codex-backed assistant" | add "EXPERIMENTAL; not live-qualified" |
| C6 | `src/rnplens/capabilities.py` | no registry entries for `view`, the follow-up, the natural-language planner, snap Codex | optional: register them (EXPERIMENTAL or UNAVAILABLE) so that `assist --list` and `doctor` show the same four categories as the docs |
| C7 | `docs/which_analysis_should_i_use.md` | rc3 wording; no 0.4 status | **not edited deliberately**: it must stay byte-identical to the packaged guide evaluated in the sealed assistant study (`assistant/tests/test_guide_packaging.py`, EVALUATED_GUIDE sha256 `d1a45b57...`). Any change waits until after the sealed evaluation |
| C8 | `docs/reproducibility.md` | (owned by the replay track) | not audited here |
| C9 | `records/v04_integration/V04_IMPLEMENTATION_REPORT.md` | section 3b lists the local follow-up as descriptive and "offline loading ... verified" under descriptive functions | historical record; not edited. The release notes should use `docs/capabilities.md` instead of quoting section 3 verbatim (RELEASE_PLAN step updated accordingly) |

Pre-existing `wording_audit` hits in README.md (7), docs/interpretation.md (8), docs/workflow.md (4),
docs/diagnose.md (3), docs/limitations.md (3) and docs/quickstart.md (1) are rc3 negations such as "does not pick a
'best' structure" or quoted rc3 output ("best of 1 admissible"); they were left unchanged.

## 5. Added with the release tooling

- `docs/release_manifest.md`: page for the development tool `tools/release_manifest.py` (not a researcher-facing
  capability, so it is not in the four categories).
- `records/v04_integration/RELEASE_PLAN.md`: rewritten for the owner's decision note (development candidate; public
  release not approved; preconditions: replay retest, viewer verification with the owner's on-screen check, live Codex
  qualification only after auto-reload is confirmed off, all receipts at the release HEAD via the manifest tool,
  institutional approvals).

## 6. r2 (track release-docs-r2, base b3374e4): changes and items for the integrator

**Documentation changed in r2.** `docs/capabilities.md` (category rules table; categories rewritten under the owner's
rules; Diagnose BLOCKED row with exit code 5; exit-code list; viewer label; three-level reproducibility table; macOS
tolerance), README status block, Diagnose bullet, Example 2 (Diagnose section now shows the refusal) and image note;
CHANGELOG (r2 changes, categories, platforms, reproducibility, viewer); `docs/diagnose.md` (BLOCKED box, title),
`docs/workflow.md`, `docs/limitations.md`, `docs/project_state.md`, `docs/quickstart.md`, `docs/output_formats.md`,
`docs/installation.md`, `docs/setup_and_privacy.md`, `docs/assist.md`. No edit added a `wording_audit` hit.

**Code text that needs no change.** `src/rnplens/assist.py` and `src/rnplens/doctor.py` contain no Diagnose wording;
both render the registry. After r2 the menu's "Not available" list reads (verified with `rnplens assist --project P
--list`): "Diagnose (user-facing workflow: diagnose run, preflight, validity and its interpretation): BLOCKED in 0.4
until re-qualification (the commands refuse with exit 5): licensing evidence is being recomputed under the
corrected correspondence". The doctor still reports "offered: 1 QUALIFIED, 9 DESCRIPTIVE; not available: 6" and "all
8 frozen sources match their pinned SHA-256" (READY).

| # | where (pinned or outside this track) | exact text or behaviour at r2 | proposal |
|---|---|---|---|
| R2-C1 | `src/rnplens/cli.py` (edited in r2; not pinned) | `view` help now "(automatically tested, awaiting manual visual confirmation; not fully visually qualified)" | none; listed because `--help` output changed |
| R2-C2 | `src/rnplens/assist.py` (pinned) `FOLLOWUP_HINT = ("Follow-up (EXPERIMENTAL): type s for suggested follow-ups (local, nothing is sent)%s.")` and `--followup` help `"after the result, one bounded follow-up (EXPERIMENTAL; docs/followup.md)"`; `assistant/rnplens_assistant/followup.py` (pinned) record `"status": "EXPERIMENTAL"` | the local, LLM-free follow-up is labelled EXPERIMENTAL | only if the owner moves the local mode to category 2 (J2): change these three strings for local mode and re-pin; until then the docs keep it in 3 |
| R2-C3 | `src/rnplens/cli.py` | `rnplens evaluate run` still prints the blocked geometry values (frozen rc3 output) | **done in r3** (owner: release blocker): public wrapper `src/rnplens/geometry_block.py` |
| R2-C4 | `assistant/rnplens_assistant/followup.py` (pinned) | reads `summary.json#/steps/diagnose_skipped` and reports item `diagnose` as `NOT_COMPUTED` | optional: report `TOOL_BLOCKED` with `#/steps/diagnose_blocked` (needs a re-pin). `steps.diagnose_skipped` is kept `true` so the current code works unchanged |
| R2-C5 | live-qualification payloads | `summary.json` changed in r2 (one `limits` sentence now states DIAGNOSE_BLOCKED; new `steps.diagnose_blocked`) | the integrator should re-verify the exact Codex payload after merging r2 (the owner requires payload verification before any model call) |
| R2-C6 | `docs/which_analysis_should_i_use.md` (sealed guide, sha256-pinned) | still describes Diagnose as available | not editable before the sealed evaluation; update afterwards |
| R2-C7 | `docs/reproducibility.md` | not edited in r2 (replay track's page in round 1) | integrator: align with the three-level status used elsewhere |
| R2-C8 | menu path to `clarify_and_resume` | **corrected in r3: this r2 statement was wrong.** At b3374e4/589485b a `DiagnoseBlocked` raised inside a menu function was not caught (the menu ended in a traceback, not exit 4), and a result with status `BLOCKED` counted as success (exit 0). Also, `clarify_and_resume` has no menu letter, and its registry entry declares an input (`project_state`) that its function does not accept, so it cannot run through the menu at all (see section 7, R3-C2) | fixed in r3 B: block -> 5, refusal/failure -> 4 |
| R2-C9 | `examples/expected_output/B2_diagnose_7K9D/`, `B2_diagnose_validity.json` | rc3 expected outputs kept unchanged | kept as historical records (README says so); `examples/run_examples.sh` now writes `B2_diagnose_BLOCKED.txt` instead |

## 7. r3 (track release-docs-r3, base 589485b): changes and items for the integrator

**Code changed in r3.** `src/rnplens/geometry_block.py` (new) and `src/rnplens/cli.py`: `rnplens evaluate run`,
`rnplens evaluate selftest` and `rnplens selftest` go through the geometry block; `rnplens evaluate run`'s run record
now says its result files are filtered. `src/rnplens/assist.py` (pinned; sha256
2e504d658a0dd052791bb7a0fbb1bf98f031fb6efe22989849c09988dd68955a -> 03fda9de46f1b78d9b94eb0f15207403f768192aa3b427d71d45ea1b336c4507):
menu exit 5 for a blocked capability, 4 for a refusal or failure. No frozen source changed (doctor: all 8 frozen
sources match their pinned SHA-256, READY).

**Documentation changed in r3.** README (status block with J5-J7 wording, Evaluate bullet, Example 1 output and
reading, image caption), CHANGELOG (r3 changes, categories), `docs/capabilities.md` (J1-J7 table, analyse/J7 rows,
doctor and menu rows, geometry rows, exit codes), `docs/evaluate.md`, `docs/quickstart.md`, `docs/output_formats.md`,
`docs/limitations.md`, `docs/assist.md` (exit codes 4 and 5), `docs/images/README.md`, and
`docs/images/example_evaluate.png` (re-drawn from the r3 `summary.txt`, sha256
556eb465caecb0233975805c8ab951aada333fcd979c76cdb86ed97b22ed6488; drawn as monospaced text with matplotlib, not with
headless Firefox as the round-1 screenshots). No edit added a `wording_audit` hit.

| # | where | exact text or behaviour at r3 | proposal |
|---|---|---|---|
| R3-C1 | `docs/which_analysis_should_i_use.md` (sealed guide; sha256-pinned as `EVALUATED_GUIDE` in `assistant/tests/test_guide_packaging.py`) | still lists RNA internal C4' RMSD, RNA placement C4' RMSD and protein internal CA RMSD as Evaluate values, and `geometry.status` as `COMPUTED` / `NO_VALUE` | not editable while the frozen assistant's guide is pinned (an r3 edit was reverted when the packaging test failed); update after the sealed evaluation, together with R2-C6 |
| R3-C2 | capability registry entry `clarify_and_resume` | no menu letter; declares input `project_state`, but its function `clarify.capability_answer(project, question, option)` does not accept it (menu exit 3, "the registered function does not accept the input 'project_state'") | integrator: map `project_state` to `project` or fix the declared inputs if the function is ever offered in the menu; the r3 test exercises the real clarify -> resume -> Diagnose-block chain through the menu machinery with the project bound |
| R3-C3 | `rnplens selftest` output (Diagnose example regression) | prints an example Diagnose statement on bundled data, e.g. "The protein is variable across the candidates: disagreement 0.89 A, high relative to the frozen development reference (52th percentile of 65 development targets)." | **done (integrator follow-up, r3):** the public wrapper shows `Diagnose interpretation BLOCKED (checked, not shown)` in place of each statement in `rnplens selftest` and `rnplens diagnose selftest`; checks, verdict, exit code and `--out` record unchanged; the frozen component still prints them (`tests/test_diagnose_selftest_masked.py`) |
| R3-C4 | `rnplens evaluate selftest` (default reference profile) on macOS | exits 3 (bit-exact reference profile; DockQ deviation 8.76e-10 on one case, plus geometry lines, now masked as `<withheld>`); the portable profile passes (exit 0) | pre-existing platform behaviour (also before r3); the masking changes only what is printed |
| R3-C5 | rc3 records `examples/expected_output/A_evaluate_7K9D/` | still contain the four-axis geometry values | kept unchanged as historical records; README and `docs/limitations.md` say so |
| R3-C7 | `assistant/evaluation_v04/LIVE_QUALIFICATION_v1/scenarios.json` `pinned_sources` (not editable by this track) | still pins the 589485b `src/rnplens/assist.py`; `assistant/tests/test_live_qualification.py` has 21 failures, all the freeze refusal for that file (verified: 37 pass with only that file restored) | re-pin per `records/release/PINNED_SOURCE_AMENDMENT_R3_PROPOSAL.md`, combined with the other approved pinned-file change |
| R3-C6 | `docs/reproducibility.md`, `docs/workflow.md`, `docs/interpretation.md` | not edited in r3; their geometry text already says "withheld"/"blocked" and does not say the values are printed | none |

