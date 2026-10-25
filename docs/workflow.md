# Working from engine output folders: `import`, `analyse`, `compare` (0.3 development)

**0.4 status.** `import` and `compare` are qualified operations in 0.4, and `analyse` is the qualified project run of
Report and (with a reference) Evaluate's DockQ route ([capabilities.md](capabilities.md)). Evaluate's four-axis
geometry is withheld, and **Diagnose is BLOCKED**: `analyse` never runs it, its summary records `DIAGNOSE_BLOCKED`
(`steps.diagnose_blocked`), and `--with-diagnose` is refused with exit code 5. The Diagnose descriptions below are
the rc3 behaviour, kept for reference. `import`'s input validation (file reading, chain typing, construct checks,
duplicates) is not the Diagnose workflow and never calls it.

These three commands sit on top of Evaluate, Report and Diagnose. They import, run and present; they do not
change any computation. Every number they show comes from one of those tools' own output files, and the
summary is refused if any number cannot be traced back to one.

> Contact and position frequencies count how often the supplied predictions contain a feature. They are not
> probabilities that the feature exists, and predictions from one model can agree on the same error.

## 1. `rnplens import`

```
rnplens import FOLDER [FOLDER ...] --protein-seq SEQ|FASTA --rna-seq SEQ|FASTA --out PROJECT
               [--case-id NAME] [--engine LABEL] [--resolve ANSWERS.json] [--accept-derived]
```

**Recognised layouts.**

| engine | files recognised | engine's ranking score read | designated structure |
|---|---|---|---|
| Boltz-2 | `boltz_results_<T>/predictions/<T>/<T>_model_<k>.pdb\|cif` | `confidence_score` in `confidence_<T>_model_<k>.json` | highest score |
| Boltz-2 (copied out of its folders) | `<T>_model_<k>.pdb\|cif` in any folder, **only** when `confidence_<T>_model_<k>.json` with a numeric `confidence_score` is beside it; the folder is the run | as above | highest score |
| Chai-1 | `pred.model_idx_<k>.cif` | `aggregate_score` in `scores.model_idx_<k>.npz` | highest score |
| AF3 / RF3 | `<T>/seed-<s>_sample-<k>/<T>_seed-<s>_sample-<k>_model.cif` | `ranking_score` in the sample's `summary_confidences.json` | highest score |
| RF2NA | `models/model_<k>.pdb` | none | the only model of the run; otherwise not determinable |

- **AF3 and RF3.** These engines write the same layout, so import asks which engine produced each such folder.
  You answer with `--engine` or in the resolution file. The engine's top-level `<T>/<T>_model.cif` is not imported
  as an extra candidate. It is checked to have the same coordinates as the designated sample, and the check is
  recorded.
- **Other layouts.** Files in any other layout are listed as unrecognised, and nothing is guessed about them.
  They are imported only when you name their engine with `--engine`: with `BOLTZ2`, a `confidence_<model>.json`
  beside each file is read for the ranking score; with `AF3`/`RF3`, the `*_summary_confidences.json`; with `OTHER`,
  no engine confidence is used. Import prints this hint whenever files were left unrecognised.
- **Nothing to import is a refusal.** When no structure can be included (none recognised, or all excluded),
  import exits with status 2, prints why, and writes nothing.
  `--engine LABEL` accepts them as structures of that engine: each folder is a run and each file a sample.
- **Run and execution labels.** A run is one output folder. In the Report contract that import writes, the
  execution label is `<run>#<sample>`, so each structure counts once within its engine.
- **Run names.** For the Boltz-2 layout the run is named after the folder that holds `boltz_results_<T>`
  (`exec_A/boltz_results_T` gives run `exec_A`; giving `boltz_results_T` itself gives the name of its parent folder).
  When one folder holds several `boltz_results_<T>` folders (several predictions written to one `--out_dir`), each
  of them is its own run, named after it. Two structures never share a `<run>#<sample>` label: if they would (for
  example `m.pdb` and `m.cif` of one model in one folder), import refuses with exit status 2 and writes nothing.

**Chain checks.** Every chain is typed exactly as Report types it, then compared with the construct you declare:

| status | meaning | what happens |
|---|---|---|
| `EXACT` | sequence equal, residues numbered 1..L | used as is |
| `RENUMBER` | sequence equal, numbered differently (the offset is reported when it is constant) | needs `--accept-derived` |
| `NONPOLYMER_CHAIN` / `+STRIP_RESIDUES` | ligand or ion chains, or non-polymer residues inside a polymer chain | needs `--accept-derived` |
| `TYPE_UNCERTAIN` | a chain typed as protein that contains many nucleotide residue names | import stops with a question |
| `SEQUENCE_DIFFERS` | substitution, insertion or truncation; the alignment is reported | the file is excluded (one project holds one construct) |

**Rules that always apply.**
- **Originals are never modified, moved or copied.** A derived copy is written only with `--accept-derived`.
  It keeps the original file name, its transformations are logged, and it is re-checked before use.
- **Ambiguity stops the import.** Import exits with status 3 and writes `QUESTIONS.json`. Fill in the answers
  and rerun with `--resolve` into a new `--out` folder.
- **Duplicates are counted once.** Byte-identical files are marked `DUPLICATE`.
- **Nothing is overwritten.** An existing `--out` is refused.

**Outputs.**
- `manifest.json`: every file, with its checksum, engine, run, sample, designated flag, chain checks, verdict and
  reasons.
  - `skipped_files`: every other file under the input folders (engine confidence files, compressed or `.ent`
    structure files, which import does not read, anything else) and every hidden folder, which is not searched,
    each with its reason; `counts.skipped_files` and `counts.skipped_structure_like` count them. Nothing is skipped
    silently.
  - per run, `designated_verdict`, `designated_included` and `designated_note`: the engine designates a structure
    among all of the run's files, so the designated structure can itself have been excluded (for example as a
    `DUPLICATE`). It is then reported everywhere as *excluded at import; not analysed*.
- `report_contract.json`: the exact rc3 Report contract, with checksums computed by import.
- `construct_*.fasta`: the declared construct sequences.
- `derived/`: derived copies, if any were accepted.

## 2. `rnplens analyse`

```
rnplens analyse PROJECT --out RESULTS [--reference REFERENCE.cif] [--nproc N]
```

**Exit status.** 0: the summary was accepted and every Report run produced a result. 1: a Report run did not
produce a result (for example, the structure files recorded by import are no longer there), or the summary was not
accepted (`TRACE_FAILED.txt`, `WORDING_AUDIT_FAILED.txt`); the summary is still written for inspection and
`summary.json` records the failed step under `steps.report`. 2: refused (existing `--out`, no included structure).
5: `--with-diagnose` (Diagnose is BLOCKED). Inside a managed project (`rnplens update`), 1 records the group as
FAILED and nothing failed is cached, and 6 (`PORTABILITY REFUSED`) means recorded input files are missing or
changed after a move ([project_state.md](project_state.md)).

**What runs.** Each tool runs unchanged through the `rnplens` command, writes its own output folder and run
record, and every command is logged in `commands.log`:
- **Report:** on every included structure.
- **Diagnose (rc3 behaviour; BLOCKED in 0.4, never run):** within each engine that has two or more structures. If two or more engines have a designated
  structure, it also runs across engines on those structures. Diagnose applies its own validated-domain check; a
  refusal is shown with Diagnose's own message and is never overridden.
- **Evaluate:** on every included structure, only with `--reference`. Its results appear in a separate,
  reference-based section.

**What `summary.html` and `summary.json` show.**
1. **Inventory.** What was imported, what was excluded and why, the runs, and each run's designated structure
   and the rule that chose it.
2. **Contacts.**
   - Each contact shows `k/n` for each engine: `k` of the engine's `n` eligible structures list the contact in
     Report's own `contacts_by_output.json`. The contributing structure ids are listed, along with Report's
     engine-weighted `contact_support`.
   - Weighting: for each engine, the fraction of its structures that list the contact, added over engines, so an
     engine contributes at most 1 however many structures it supplied.
   - The protein and RNA positions involved are counted the same way, and a contact map is drawn for each engine.
3. **Agreement between an engine's structures.**
   - With **exactly two** structures of an engine, Report's repeat agreement is shown: surface, register and RNA
     pose.
   - **Two runs of one engine** (for example 5 samples in one run and 1 in another): Report is run a second time,
     unchanged, on the engine-designated structure of each run, and its two-output repeat agreement is shown as the
     agreement *between runs*, with the two structures and the designation rule named. If either run has no
     determinable designated structure, it is stated as not computed. No other combination is computed.
   - With any other number, the summary states *"Pairwise repeat-agreement summary not computed for this
     candidate configuration."* This is not zero agreement. The rc3 Report computes repeat agreement only for two
     structures, and 0.3 does not add a substitute statistic under that name.
4. **Agreement between engines** (Report's engine pairs and engine groups).
5. **Diagnose (BLOCKED in 0.4; the section states DIAGNOSE_BLOCKED):** in rc3, validity classes, disagreement with band and percentile, applicability, and placement disagreement
   shown as "measured, not interpreted".
6. **Evaluate** (with `--reference`): DockQ, its class, fnat, iRMSD and LRMSD per structure, with the run, sample
   and whether the engine designated it. **The four-axis geometry values (protein-internal, RNA-internal and RNA
   placement RMSD) are withheld in this development version**: their residue correspondence has a known defect
   (a residue-correspondence defect found on 2026-10-14; see [limitations.md](limitations.md)) and the corrected implementation is not yet qualified here. iRMSD and LRMSD are DockQ's
   own quantities and are not a substitute for the RNA conformation/placement decomposition.
7. **What the summary does not establish.**

**Acceptance checks that run before the summary is accepted.**
- **Traceability.** Every count, denominator, contributing structure and value is re-derived from the tool output
  files, and the run fails (`TRACE_FAILED.txt`) if any one differs.
- **Wording audit.** The HTML is refused (`WORDING_AUDIT_FAILED.txt`) if it describes agreement as reliability,
  correctness, probability or "best".

## 3. `rnplens compare`

```
rnplens compare --before BEFORE.tsv --after AFTER.tsv --references REFS.tsv --out RESULTS [--jobs N]
```

**Inputs.**
- `BEFORE.tsv` and `AFTER.tsv`: columns `target_id`, `prediction`, `protein_sequence`, `rna_sequence`. A sequence
  may be given directly (letters only) or as a FASTA path.
- **Relative paths** (predictions, references, FASTA files) are resolved against the directory of the TSV that names
  them, never the working directory. Every file is checked before anything runs: a missing file is an input error
  (exit 2, nothing written), never a scientific class.
- `REFS.tsv`: columns `target_id` and `reference`, plus an optional `cluster` column. When it is present, the
  bootstrap resamples clusters rather than targets.

**What runs.** Each prediction is evaluated by the unchanged Evaluate. Every target and metric (DockQ, fnat,
iRMSD and LRMSD, all from the DockQ route) is placed in exactly one class. The geometry route is not compared in
this development version (see section 2, item 6).

| class | meaning |
|---|---|
| `CONSTRUCT_CHANGED` | the declared sequence differs between the two sets |
| `NOT_EVALUABLE_IN_BOTH` / `NEWLY_EVALUABLE` / `NEWLY_UNEVALUABLE` | the route had no value in one or both sets |
| `CORRESPONDENCE_CHANGED` | both have values, but the chain mapping or residue correspondence differs |
| `RUN_FAILED` | Evaluate refused or failed for this target; compare exits with status 1 and names the target |
| `IMPROVED` / `WORSENED` / `UNCHANGED` | like-for-like, compared at 3 decimal places. These give the direction of a change at that precision; no threshold of practical relevance is applied |

**Summary.**
- Only like-for-like targets enter the mean paired difference and its 95% bootstrap interval (5,000 resamples,
  fixed seed). With a single resampling unit no interval is reported ("n = 1 resampling unit: no interval").
- Everything else is counted and listed separately, never pooled.
- The rate of DockQ ≥ 0.23 is shown only for the same like-for-like targets, together with the other metrics.
- `fnat` is taken from the interface DockQ reports: the first in DockQ's order, which is the frozen convention.

**Outputs.**
- `comparison.tsv`: one row per target and metric.
- `comparison_summary.json` and `comparison_summary.txt`: counts per class, the paired summary and the targets in
  each class.
- `evaluate/before/<target>/` and `evaluate/after/<target>/`: the unchanged Evaluate outputs.

## Known limitations of this development version
- **Structure viewer.** `summary.html` itself has no structure viewer, and its contact maps are static images.
  `rnplens view` writes a separate offline Mol* page ([assist.md](assist.md); automatically tested, basic use
  confirmed manually on macOS, not fully visually qualified).
- **Single structures.** One structure per engine gives contact counts of 0 or 1. There is no agreement to
  describe.
- **Grouping** of the structures into binding proposals is a separate command, `rnplens group`, run on an
  analysis ([grouping.md](grouping.md)); `analyse` itself does not group.
