# What RNPLens 0.4 offers, in four categories (release `0.4.0`)

RNPLens analyses protein-RNA structures that were **already predicted** by other methods. It does not predict
structures, it does not rank or select candidates, and agreement or recurrence among predictions is never reported as
confidence. RNPLens 0.4 is a **development candidate**: it is not merged, tagged or released.

Every user-facing capability is listed in exactly one of the four categories below. The machine-readable source
for the menu functions is the capability registry (`rnplens.capabilities`; `rnplens assist --project P --list`
prints it for your installation). Where this page and the registry differ, the registry decides what the menu
offers, and the difference is a documentation defect to report.

## Category rules (owner decision, 17 Oct 2026)

| category | what belongs there |
|---|---|
| 1. Qualified | existing verified Report routes, approved DockQ-family Evaluate metrics and the corresponding qualified import and compare operations |
| 2. New descriptive functionality | region contacts, evidence lookup, Methods export, clarification and resume, incremental analysis and tested grouping operations |
| 3. Experimental | the Codex result-aware follow-up (and the natural-language planner), and scientific claims about the usefulness of grouping for researchers |
| 4. Blocked | four-axis geometry, the affected RNA-conformation measurements, Diagnose (user-facing) and accuracy-based candidate ranking |

## Capability classifications J1-J7 (owner decision on the Round 2 results, 17 Oct 2026)

The accepted J1-J7 classifications are retained (`records/release/DOCS_AUDIT.md`, section 3). The owner's wording
for the three classifications that needed it:

| item | decision |
|---|---|
| J5: analyse | Qualified only for its tested, enabled analysis routes |
| J6: doctor and menu | New descriptive functionality; environment readiness does not qualify the scientific agent |
| J7: selftest, provenance and example contract | Qualified as tested software infrastructure, not as independent evidence of structural accuracy |
| Diagnose and four-axis geometry | Remain blocked |

## 1. Qualified (routes qualified before 0.4, computation unchanged)

| capability | command | registry |
|---|---|---|
| **Report**, reference-free: binding surfaces, residue-nucleotide contacts, surface and contact-register agreement, RNA pose difference, interface hypotheses | `rnplens report`; menu item A (`interface_overview`) | QUALIFIED |
| **Evaluate, DockQ-family metrics only**: DockQ, DockQ class, fnat, iRMSD and LRMSD | `rnplens evaluate` | (not a menu function) |
| **import** (with its input validation: file reading, chain typing by Report's own `split_chains`, construct checks, duplicate detection) and **compare** (matched before/after Evaluate DockQ route) | `rnplens import`, `rnplens compare` | (not menu functions) |
| **analyse (J5): qualified only for its tested, enabled analysis routes**, i.e. Report and Evaluate's DockQ route run on an imported project, with one traced summary (Diagnose is never run; the summary records `DIAGNOSE_BLOCKED`; the geometry values are withheld) | `rnplens analyse` | (not a menu function) |
| **selftest, provenance and example contract (J7): qualified as tested software infrastructure, not as independent evidence of structural accuracy** | `rnplens selftest`, `rnplens provenance`, `rnplens example-contract` | (not menu functions) |

Qualified here means that the computation reuses a route qualified before 0.4, unchanged. It does not mean that a
value is evidence that a structure matches the real complex.

- Evaluate's four-axis geometry values are **not** part of this category (see category 4). The public
  `rnplens evaluate run` does not show them: it records the geometry status `BLOCKED` (code
  `GEOMETRY_BLOCKED_IN_0.4`) in `result.json`, `result.csv` and `summary.txt` and leaves every geometry value empty.
  The DockQ-family values in the same output are unchanged from rc3; they are not a replacement for the four-axis
  geometry decomposition.
- `import`'s input validation is not the Diagnose workflow: it never calls the Diagnose component (a test checks
  this), and its verdicts (`INCLUDED`, `INCOMPATIBLE`, `UNREADABLE`, `DUPLICATE`, ...) only decide which files enter
  a project.
- `rnplens selftest` (and `rnplens diagnose selftest`) still run Diagnose's 18 internal contract checks and its
  example regression on bundled data. They are software checks that print PASS or FAIL; they make no statement about
  your structures. `rnplens selftest` and `rnplens evaluate selftest` show the geometry status as `BLOCKED` and
  mask geometry values in their check lines. `rnplens selftest` and `rnplens diagnose selftest` show
  `Diagnose interpretation BLOCKED (checked, not shown)` in place of each interpretation statement that Diagnose's example regression prints
  (protein-side and RNA-side disagreement with band and percentile). The checks themselves, their verdict, exit code
  and the `--out` self-test record are unchanged.

## 2. New descriptive functionality (new in 0.4, tested, descriptive output)

| capability | command; menu item | registry id, status |
|---|---|---|
| contacts in an RNA region (optionally a protein range) | `rnplens region`; B | `region_contacts`, DESCRIPTIVE |
| comparison of runs within an RNA region | `rnplens region`; C | `region_run_comparison`, DESCRIPTIVE |
| evidence lookup for a reported value | `rnplens explain`; D | `explain_evidence`, DESCRIPTIVE |
| Methods draft and provenance manifest | `rnplens export-methods`; F | `export_methods`, DESCRIPTIVE |
| clarification and resume | `rnplens clarify` | `clarify_and_resume`, DESCRIPTIVE |
| incremental analysis (add, change or remove runs) | `rnplens update` | `incremental_update`, DESCRIPTIVE |
| grouping operations: binding-proposal groups (never ranked, never ordered by size) and shared and group-specific contacts between two groups | `rnplens group`; E, and `rnplens group-diff` | `hypothesis_grouping`, `group_difference`, DESCRIPTIVE |
| setup check (J6; environment readiness does not qualify the scientific agent) | `rnplens doctor` | `setup_check`, DESCRIPTIVE |
| the question menu itself (J6; no language model) | `rnplens assist --project P` | (the menu; not a registry entry) |
| offline structure viewer: **automatically tested; basic display and interaction confirmed manually by the owner on macOS (2026-10-18); switching between binding-hypothesis representatives and offline operation not yet confirmed manually; not fully visually qualified** | `rnplens view` | (not a registry entry) |

Descriptive means new, tested (unit, parity with Report's own records, malformed input, determinism, missingness,
data access, worked example) and descriptive: these outputs list and count what the supplied predictions contain.

**Viewer status.** `rnplens view` writes an offline Mol* 5.13.1 page with Report's contacts highlighted. Automated
check (`records/viewer/MOLSTAR_VISUAL_VERIFICATION.md`): on the tested Linux host, six demonstration pages were
rendered in headless Chrome for Testing 155 with software WebGL, with networking disabled and every request logged;
only `file:` and `data:` requests were made, and the intended chains, construct positions, Report contact highlights
and group representatives were shown. A highlighted residue is one that Report's per-structure contact records list
for that structure; an unhighlighted residue inside a requested range is not by itself a viewer defect (for 2JEA RNA
26-35, the highlighted chain-B nucleotides are 27-29 and 31-35; 26 and 30 are not highlighted). The owner's manual
test on macOS (2026-10-18) confirmed basic display and interaction on the 2JEA page (structures shown, rotation and
zoom, nucleotide clicks, different selections highlight different regions). Switching between binding-hypothesis
representatives and operation with the network disconnected have not yet been confirmed by a person, so the viewer
is **not fully visually qualified**.

## 3. Experimental (needs further evidence)

- **Codex result-aware follow-up** (`rnplens assist ... --followup codex`). The scripted part of FOLLOWUP_SUITE_v1
  passed 21 of 21; no live call has been made, so it is **not live-qualified**. The local mode of the same feature
  (`--followup local`, deterministic rules, no language model) is labelled EXPERIMENTAL by the software and is
  listed here for that reason (see `records/release/DOCS_AUDIT.md`, J2).
- **Natural-language planner with the 0.4 tools** (`rnplens assist --nl`). Not qualified live; it differs from the
  assistant under the sealed evaluation (`f998830`). LLM-free replay of a recorded plan
  (`python -m rnplens_assistant replay`) belongs to this feature.
- **Scientific claims about the usefulness of grouping for researchers.** Group representatives are a way to *see*
  the alternative binding proposals; they are never an accuracy selector. In the retrospective pool-A check (50
  targets with an acceptable candidate, DockQ >= 0.23; frozen labels read only after the grouping code freeze), a
  fixed set of k = 5 representatives contained an acceptable structure in **0.86** of the targets, against **0.94**
  for the first five structures in engine-confidence order (k = 3: 0.84 against 0.88). Grouping did not retain
  acceptable proposals more often than confidence order (`records/grouping/GROUPING_QUALIFICATION_REPORT.md`).
  Whether grouping helps researchers is not established.

## 4. Blocked (never offered as a result) and unsupported

| capability | status and reason |
|---|---|
| Evaluate four-axis geometry (protein-internal, RNA-internal and RNA-placement RMSD) | blocked: residue-correspondence defect found on 2026-10-14. No public entry point shows the values: `rnplens evaluate run` records the geometry status `BLOCKED` (code `GEOMETRY_BLOCKED_IN_0.4`) with empty value fields, the selftests mask them, and `compare`, `analyse` and the menu withhold them; the components' own command lines (`python -m rnpbench evaluate run`, `python -m rnpbench_evaluate evaluate`, …) refuse with `LEGACY_ROUTE_REFUSED` and exit code 5 ([installation.md](installation.md#commands-installed)). The frozen rc3 component is unchanged |
| affected RNA-conformation measurements: the RNA conformation difference between candidates (Specification B "Q"; Evaluate's RNA-internal C4' RMSD is part of the four-axis row above) | blocked: it uses the same correspondence route as the blocked geometry |
| **Diagnose (user-facing)**: `rnplens diagnose run`, `preflight` and `validity`, and Diagnose in `rnplens analyse` and `rnplens update` (`--with-diagnose`) | **BLOCKED** until re-qualification: the commands refuse with `DIAGNOSE_BLOCKED` and **exit code 5**, and read or write nothing; so do the components' own Diagnose command lines (`python -m rnpbench diagnose …`, `python -m rnpbench_diagnose …`: `LEGACY_ROUTE_REFUSED`, exit code 5). Its statements and validated domain rest on evidence that is being recomputed under the corrected correspondence. The frozen rc3 component is unchanged |
| accuracy-based candidate ranking, or selection of a structure, run or group as the right one (including grouping used as a selector) | unavailable: RNPLens Rank closed with outcome STOP (2026-10-14) |
| new structure prediction | unavailable: RNPLens does not predict structures |
| mutation or experiment advice | unavailable: outside the evidence RNPLens computes |
| a snap-installed Codex inside the jail | unsupported: the snap wrapper cannot run inside the bubblewrap jail |
| the natural-language planner and Codex follow-up inside another sandbox on macOS (Seatbelt cannot be nested); anything on Windows | unsupported (refused) |

**Exit codes of the public commands.** 0 done; 1 a run failed; 2 an input error (including a missing or wrong input path, refused before anything runs); 3 unavailable in this installation (including a missing required package, with the install command)
(menu item or optional package); 4 a menu function ran and refused or failed (including an answer or request the
function refuses); **5 a blocked capability**: `DIAGNOSE_BLOCKED` from a command, `LEGACY_ROUTE_REFUSED` from a component's own
command line, or a menu function that reports or raises a 0.4 block; 6 `PORTABILITY REFUSED`: a copied or moved managed project whose recorded input files are missing
or changed (record where they are with `rnplens relink`; [project_state.md](project_state.md)). A refusal is never
reported as a block, and a block never as a refusal. `rnplens evaluate run`
exits 0 when its DockQ route ran, with the geometry status `BLOCKED` recorded in its output.

## Platforms

- **Linux x86-64 is the tested interactive environment** (full suite, clean wheel, sdist and documented installs,
  the question menu, local follow-ups and the jail).
- **macOS arm64:** the toolkit runs. The one known numerical parity difference (3.9e-15 A in one unrounded RNA pose
  difference, from the LAPACK `dgesdd` routine of a different OpenBLAS build) is covered by an approved, narrowly
  scoped tolerance of 1e-12 A on that single value (`records/release/TOLERANCE_POLICY_AMENDMENT_1.md`); every other
  value stays exact. The language-model modes run natively on macOS under a Seatbelt jail (new in the native-platforms
  change; confinement qualification in `records/native_platforms/`); they are not live-qualified on either system.
- Windows is unsupported.

## Reproducibility status

| level | status |
|---|---|
| Numerical/evidence reproducibility | supported by the reported tests |
| Canonical-file byte reproducibility | passed in four development cases (1VTM, 7K9D, 2JEA, 2Q66) under the new contract (`records/replay/DETERMINISM_CONTRACT_v1.md`; `records/replay/REPLAY_REQUALIFICATION_REPORT.md`) |
| Complete managed-project byte reproducibility | not yet established |

The original pre-registered byte-identical managed-project replay check **failed** (22 of 43 files differed), and that
verdict stands. Outputs outside the canonical set (importer manifests, `summary.json`, Report run records, region,
explain, follow-up and Methods records) are not byte-identical between runs and still need to be classified
individually; byte identity was tested on one Linux host and one Python version only.

## Release status

0.4 remains a development candidate. A public release is not approved; its preconditions are listed in
`records/v04_integration/RELEASE_PLAN.md`.
