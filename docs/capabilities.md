# RNPLens capabilities

## 1. Overview

RNPLens assesses protein–RNA complex structures that have **already been predicted** by other methods (for example
AlphaFold 3, Boltz-2, Chai-1, the RoseTTAFold family or docking). It answers two kinds of question:

- **With an experimental structure:** how accurate is a prediction's protein–RNA interface?
- **Without one:** do several predictions propose the same interface, and where do they differ?

It does not predict structures, rank or select candidates, or report agreement among predictions as confidence. Its
outputs are machine-readable, record the SHA-256 of every input and output, and keep separate quantities that are
easily conflated ([interpretation.md](interpretation.md)).

| Scientific question | Command | Main outputs |
|---|---|---|
| How accurate is this prediction's interface, compared with the experimental structure? | `rnplens evaluate run` | `result.json`, `result.csv`, `summary.txt`: DockQ, DockQ class, fnat, iRMSD, LRMSD |
| Do several predictions propose the same binding surface, contacts and RNA pose? | `rnplens report run` | `result.json`, `contacts_by_output.json`, an HTML page |
| What do the predictions in my engine output folders contain, and how do two sets of runs compare? | `rnplens import`, `rnplens analyse`, `rnplens compare` | a managed project with a traced summary |
| Which contacts fall in a given RNA region, and do two runs agree there? | `rnplens region` | contact tables and a region comparison |
| Which alternative binding proposals are present among many structures? | `rnplens group`, `rnplens group-diff` | binding-proposal groups and their shared and group-specific contacts |
| Where does a reported value come from, and how do I describe the analysis in Methods? | `rnplens explain`, `rnplens export-methods` | evidence lookup; a Methods draft with a provenance manifest |
| What do the predicted contacts look like on the structure? | `rnplens view` | an offline Mol\* page with a nucleotide contact explorer |
| Can I ask a question in natural language? (optional, experimental) | `python -m rnplens_assistant ask`, `rnplens assist --nl` | an evidence-linked answer, its plan and a replayable run record |

The machine-readable list of the menu functions is the capability registry (`rnplens.capabilities`);
`rnplens assist --project P --list` prints it for your installation. If this page and the registry disagree, the
registry decides what the menu offers, and the difference is a documentation defect.

## 2. Reference-based structural evaluation

`rnplens evaluate run` scores one predicted complex against one experimental structure on the **DockQ route**:

- the metrics are DockQ, DockQ class, fnat, iRMSD and LRMSD;
- the DockQ classes are incorrect < 0.23 ≤ acceptable < 0.49 ≤ medium < 0.80 ≤ high;
- model and reference residues are paired by **construct position**, checked against the declared construct
  sequences, and every admissible chain mapping is scored.

The scoring configuration is frozen (DockQ 2.1.3). Its source files are verified by SHA-256 at run time, and other
DockQ versions are refused by default.

- **Interpretation.** These values measure the interface accuracy of one prediction against the reference you chose
  (model, ensemble member, chain copy). They are not a confidence estimate.
- **Missing values.** An output that cannot be scored is reported as `NO_VALUE`, with the failing stage and reason,
  never as 0.
- **Missing positions.** Positions missing from the experimental structure are unknown, not confirmed non-contacts.
- **Assumptions.** The complex has one protein entity and one RNA entity (any copy number). The construct sequences
  are those used for the prediction.

Evaluate's separate geometry route is not available in 0.4.0 (see [section 7](#7-scope-of-v040)).
`result.json` records its status as `BLOCKED`, and its value fields are empty. Details:
[evaluate.md](evaluate.md), [INPUT_CONTRACT.md](INPUT_CONTRACT.md), [output_formats.md](output_formats.md).

## 3. Reference-free interface comparison

`rnplens report run` compares two or more predictions of the same complex, from one engine or several, without any
experimental structure:

- **Binding surface:** which protein residues each prediction places at the interface.
- **Contact register:** which protein residue contacts which nucleotide, counted within 5 Å over heavy atoms.
- **RNA pose:** the C4′ RMSD of the RNA after superposing the protein.
- **Agreement measure:** a weighted Jaccard index from 0 (none) to 1 (identical).
- **Interface hypotheses:** engines are grouped when their register agreement reaches a threshold (0.3, the primary
  0.5, or 0.7). The groups are listed separately and never averaged.
- **Repeat agreement:** when an engine has several runs, Report gives its agreement between its own runs. This
  bounds how much of the cross-engine disagreement can be attributed to the engines rather than to run-to-run
  variation.

**Interpretation.** Agreement is descriptive evidence about convergence of predicted interfaces. It is **not** a
probability that a structure or an interface is correct: engines can agree and still be wrong, and the largest group
is not implied to be correct. With a single engine, Report describes only repeat agreement. Details:
[report.md](report.md).

## 4. Interactive structure exploration

`rnplens view` writes a self-contained, offline Mol\* 5.13.1 page. It highlights Report's per-structure contacts
and adds a nucleotide contact explorer: select a nucleotide or a protein residue to see its contacts in each
structure. A highlighted residue is one that Report lists as a contact for that structure. The page makes no network
request.

**Verification status.**
- **Automated check.** The six demonstration pages were rendered in headless Chrome with networking disabled. Only
  `file:` and `data:` requests were made, and the intended chains, positions, highlights and group representatives
  were shown (`records/viewer/MOLSTAR_VISUAL_VERIFICATION.md`).
- **Manual check, 18 Oct 2026, macOS.** The owner confirmed basic display and interaction on the 2JEA page:
  - the structures are shown;
  - rotation and zoom work;
  - nucleotide clicks respond, and different selections highlight different regions.
- **Not yet confirmed by a person.** Two checks remain: switching between binding-proposal representatives, and use
  with the network disconnected.

The viewer is therefore **not yet fully visually qualified**. Details: [viewer.md](viewer.md).

## 5. Analysis and reproducibility workflows

These commands work from the output folders of prediction engines. They produce **descriptive** records: they list
and count what the supplied predictions contain, and every value carries an evidence identifier.

| Command | What it does |
|---|---|
| `rnplens import`, `analyse`, `compare` | build a managed project from engine folders, with input validation (readable files, chain typing, construct checks, duplicates). Then run Report and Evaluate's DockQ route on it, and compare before/after Evaluate results |
| `rnplens region` | contacts in an RNA region (optionally a protein range), and a comparison of runs within that region |
| `rnplens group`, `group-diff` | binding-proposal groups among many structures, never ranked or ordered by size; shared and group-specific contacts between two groups |
| `rnplens explain`, `export-methods` | trace a reported value to its evidence; write a Methods draft and a provenance manifest |
| `rnplens clarify`, `update`, `relink` | record clarifications, add, change or remove runs, and re-locate a copied project |
| `rnplens assist --project P` | a question menu over a project, which runs deterministic functions without a language model |
| `rnplens doctor`, `selftest`, `provenance` | check the installation and reproduce the bundled reference values (software checks, not evidence about your structures) |

- **Grouping is not an accuracy selector.** In a retrospective check (pool A: 50 targets with an acceptable
  candidate, DockQ ≥ 0.23; labels read only after the grouping code was frozen), a fixed set of k = 5
  representatives contained an acceptable structure in 0.86 of targets. The first five structures in
  engine-confidence order did so in 0.94 (for k = 3: 0.84 against 0.88). Whether grouping helps researchers is
  therefore not established (`records/grouping/GROUPING_QUALIFICATION_REPORT.md`).
- **Import validation is not Diagnose.** `import`'s input validation never calls Diagnose; its verdicts (`INCLUDED`,
  `INCOMPATIBLE`, `UNREADABLE`, `DUPLICATE`, ...) only decide which files enter a project.
- **Scope of `analyse`.** It runs only its tested routes, Report and Evaluate's DockQ route. Its summary records that
  Diagnose was not run.

Details:
- [workflow.md](workflow.md)
- [region.md](region.md)
- [grouping.md](grouping.md)
- [evidence_and_methods.md](evidence_and_methods.md)
- [project_state.md](project_state.md)
- [assist.md](assist.md)

## 6. RNPLens Assistant

The RNPLens Assistant is a separate, optional package (`rnplens-assistant`). Every capability above works without
it and without any language model. Its workflow:

1. **Question.** You ask a scientific question in natural language about a task folder of predictions.
2. **Plan.** A language model (Codex CLI, with your own ChatGPT sign-in) proposes a plan made only of supported
   RNPLens operations.
3. **Admission.** Deterministic code admits or refuses the plan (tool allowlist, step budget, argument and reference
   rules). An operation the toolkit cannot perform is **refused**, not approximated.
4. **Execution.** The admitted plan runs with the same RNPLens functions as above.
5. **Answer.** The answer is written from the evidence records those functions produced, with an evidence table and
   a list of what was not computed.
6. **Record and replay.** The plan, the evidence and a run record are saved. `python -m rnplens_assistant replay`
   re-runs the recorded plan without any language model and checks that the evidence hash matches.

**Status: experimental research functionality.**
- **What has been tested.** The automated tests exercise the released implementation with a scripted stand-in for
  Codex, plus replay and paths that make no model call. The scripted part of the follow-up suite passed 21 of 21.
- **What has not.** No live model call has been made for RNPLens 0.4, so the Assistant's model-dependent operation
  is not live-qualified. Its native confinement (bubblewrap on Linux, Seatbelt on macOS) is not security-qualified
  for this release.
- **The earlier implementation.** The sealed-evaluation protocol in `assistant/evaluation/` concerns an earlier,
  frozen assistant (`f998830`). Its development results and any evaluation of it do not qualify the released 0.1.0
  implementation, and this repository reports no sealed-evaluation result.

Requirements, privacy and the full limitations: [assistant/README.md](../assistant/README.md),
[setup_and_privacy.md](setup_and_privacy.md), [model_and_privacy.md](model_and_privacy.md).

## 7. Scope of v0.4.0

RNPLens v0.4.0 supports reference-based interface evaluation and reference-free structural comparison. Four-axis
geometry assessment and Diagnose are not available in this release; their scientific qualification is ongoing.

### Not available in 0.4.0 (blocked in 0.4)

| Capability | Status and reason |
|---|---|
| Evaluate's four-axis geometry (protein-internal Cα RMSD, RNA-internal C4′ RMSD, RNA-placement C4′ RMSD), and the RNA-conformation difference between candidates that uses the same correspondence | **Blocked.** A residue-correspondence defect was found on 2026-10-14. No public command shows these values: `rnplens evaluate run` records the status `BLOCKED` (code `GEOMETRY_BLOCKED_IN_0.4`) and leaves the value fields empty. The DockQ-family values use a different, qualified correspondence and are unaffected. |
| Diagnose (`rnplens diagnose run`, `preflight`, `validity`; `--with-diagnose` in `analyse` and `update`) | **Blocked** until re-qualification against the corrected correspondence. The commands refuse with `DIAGNOSE_BLOCKED` (exit code 5) and write nothing. `rnplens selftest` still runs Diagnose's internal contract checks as software checks. |
| Accuracy-based ranking, or selection of a structure, run or group as the right one | not offered |
| Structure prediction; mutation or experiment advice | not offered |
| A snap-installed Codex inside the jail; the Assistant inside another sandbox on macOS; Windows | unsupported (refused) |

Technical details of the defect and of the withheld values: [limitations.md](limitations.md) and
[diagnose.md](diagnose.md).

**Exit codes of the public commands.**

| Code | Meaning |
|---|---|
| 0 | done |
| 1 | a run failed |
| 2 | an input error, including a missing or wrong input path, refused before anything runs |
| 3 | unavailable in this installation, for example a missing optional package |
| 4 | a menu function ran and refused or failed |
| 5 | a blocked capability: `DIAGNOSE_BLOCKED`, or `LEGACY_ROUTE_REFUSED` from a component's own command line |
| 6 | `PORTABILITY REFUSED`: a copied or moved managed project whose recorded inputs are missing or changed (use `rnplens relink`; [project_state.md](project_state.md)) |

A refusal is never reported as a block, and a block never as a refusal. `rnplens evaluate run` exits 0 when its
DockQ route ran, and records the geometry status `BLOCKED` in its output.

## 8. Validation and reproducibility

- **Tests of the 0.4.0 release**, run from a clean checkout on Linux x86-64:
  - core test suite: 713 passed, 13 skipped;
  - `rnplens selftest`: PASS, with 213/213 Evaluate checks and 296 Report values reproduced;
  - the Assistant's automated suite: 268 passed, 34 skipped.

  These tests establish that the software reproduces its frozen reference values and behaves as specified. They do
  not, by themselves, establish the scientific accuracy of predictions or the security of the Assistant.
- **Platforms:**
  - **Linux x86-64** is the reference platform. Bit-exact reproduction is established for the OpenBLAS kernels
    Cooperlake and SkylakeX. With the AVX2 kernels (Haswell, Zen), unrounded values differ in trailing digits (up to
    3.9 × 10⁻⁶ Å) within the portable profile (`records/release/BLAS_KERNEL_NUMERICAL_DIFFERENCE.md`).
  - **macOS arm64:** every status, class, count and rounded value is reproduced. One unrounded RNA pose difference
    differs by 3.9 × 10⁻¹⁵ Å (a different OpenBLAS build of LAPACK `dgesdd`); a narrowly scoped tolerance of
    10⁻¹² Å covers that single value (`records/release/TOLERANCE_POLICY_AMENDMENT_1.md`). The macOS checks were run
    on an earlier 0.4 commit.
  - **Windows** is unsupported.

| Reproducibility level | Status |
|---|---|
| Numerical and evidence reproducibility | supported by the tests above |
| Canonical-file byte reproducibility | passed in four development cases (1VTM, 7K9D, 2JEA, 2Q66) under the determinism contract (`records/replay/DETERMINISM_CONTRACT_v1.md`) |
| Complete managed-project byte reproducibility | **not established.** The original pre-registered byte-identical replay check failed (22 of 43 files differed), and that verdict stands. |

**Software versus study.** The toolkit reproduces its own reference values from the bundled public data. It does
not reproduce the accompanying study's benchmark analyses, which use a benchmark dataset that is not part of this
repository ([paper_reproducibility.md](paper_reproducibility.md)). Details: [reproducibility.md](reproducibility.md).

## 9. Further documentation

- [Which analysis should I use?](which_analysis_should_i_use.md). This guide is also the Assistant's frozen
  reference text, and it still describes Diagnose, which is not available in 0.4.0.
- [Quick start](quickstart.md) · [Interpretation](interpretation.md) · [Limitations](limitations.md)
- [Release status](release_conditions.md) · [Documentation index](README.md)
- Development and qualification records: `records/` ([index](../records/README.md))
