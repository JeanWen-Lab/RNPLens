# Reproducibility and relationship to the qualified implementation

## Versions

| item | identifier |
|---|---|
| RNPLens release candidate | `0.2.0rc2` (distribution `rnplens`) |
| qualified component set | `0.2.0.dev1` (internally qualified 2026-10-10 under the internal identifier "RNPBench toolkit"; never released) |
| components inside it | `rnpbench_core` 0.2.0.dev1, `rnpbench_evaluate` 0.2.0.dev1 (contract `RNPBENCH_EVALUATE_INPUT_V1`, scoring configuration `RNPBENCH_SCORING_V3_CONSTRUCT_POSITION_DOCKQ_2_1_3`), `rnpbench_report` (analysis `rnpbench-predict-1.0.0`, contract `rnpbench-predict-contract-1`), `rnpbench_diagnose` 0.2.1 |
| manuscript evidence build | a separate identifier of the study's frozen evidence; it is **not** a software version and is not changed by any software release |

`rnplens provenance` prints all of these together with the dependency versions and the SHA-256 of each of the
eight frozen scorer files, which the code verifies at run time.

## What changed from the qualified component set

- **Packaging (0.2.0rc1).** The five internal distributions became one distribution, `rnplens`, with a
  dispatch-only `rnplens` command; in 0.2.0rc1 the 93 files of the six component import packages were
  byte-identical to those of the five qualified 0.2.0.dev1 wheels.
- **Public name (0.2.0rc2).** Human-readable text was changed to the name RNPLens by an enumerated table of 33
  exact-match replacements in 11 component files and 2 in the `rnplens` wrapper, plus the same three replacements
  in Report's stored example page
  (`selftest_data/expected/report_7K9D_example.html`). It covers command names in help and messages, self-test
  lines, the first two lines of Evaluate's `summary.txt`, one text value in Evaluate's `result.json`
  (`provenance.frozen_execution_record`, which names the provenance command), and the titles, headings and
  provenance line of the Report and Diagnose HTML pages. No computation, JSON key, identifier or frozen file
  changed. The compatibility commands `rnpbench`, `rnpbench-evaluate`, `rnpbench-report` and
  `rnpbench-diagnose` are no longer installed.
- **One recorded difference.** Because the components are no longer separate distributions, version fields that
  the components look up by distribution name are now `null`: the `distribution_version` entries of
  the internal component provenance record and the `versions.rnpbench-report` entry of Report's self-test record. No analysis
  output (Evaluate `result.*`, Report `result.json`, Diagnose `report.json`, HTML pages) contains these fields.
  `rnplens provenance` records the component versions by module.

## Release-candidate 1 qualification (2026-10-13)

On the reference platform (Linux x86-64), each from a clean environment built with only the wheel or sdist:

| check | result |
|---|---|
| build | sdist and wheel built from the clean repository |
| install | Python 3.10.22, 3.11.17, 3.12.15 from the wheel, and 3.11 from the sdist; `pip check` clean |
| self-test, reference profile (bit-identical), with the four internal engine fixtures | PASS on all four installations |
| self-test, portable profile | PASS on all four |
| test suite (including the internal-fixture tests) | 99 passed on all four |
| both worked examples | complete on all four; Python 3.10 and 3.12 outputs equal 3.11 apart from the recorded Python version |
| wheel vs sdist installation | identical outputs |
| determinism (same examples twice) | identical apart from run time |
| Report internal acceptance suite through `rnplens` | 888 / 888 checks, `ACCEPTANCE_PASS` |
| Report full-cohort reproduction through the RNPLens installation | `FULL_COHORT_REPRODUCTION_PASS` |

**Parity with the qualified toolkit** (same interpreter, same inputs, identical third-party package versions):
the two worked examples, the Diagnose validity record, Evaluate's 13 regression fixtures (9 public, 4 internal:
AlphaFold 3, Chai-1, RF2NA, RF3), Report's and Diagnose's self-tests, and an internal five-engine Report and
four-engine cross-engine Diagnose on 7K9D were run through `rnplens` and through the qualified internal
command and compared after removing run time and output paths. All analysis outputs were identical; the only
other differences were the input paths inside each installation's own site-packages, the names of temporary
directories, and the Report self-test version field described above.

On macOS arm64 (CPython 3.11, clean installation from the same wheel): portable self-test PASS; test suite 88
passed, 11 skipped (the internal-fixture tests, whose fixtures are not distributed); both examples complete.
Against the reference outputs, 13 unrounded values differ, by at most 1.4 × 10⁻⁶ Å; every rounded value, status,
class and label is identical. The earlier internal qualification of 0.2.0.dev1 on a clean macOS arm64
installation found the same behaviour.

The complete qualification records are kept with the release-preparation records; they are not part of the
repository because they reference internal fixtures and the benchmark's development store.

## Release-candidate 2 parity (display names)

The rc2 outputs were compared with rc1 outputs from the same inputs; the record is kept with the release-preparation
records. Result: every number, status, class, count, label and JSON key is identical; the only differences are the
display strings of the table above.

## Managed projects (0.4): scientific and byte-identical reproducibility

RNPLens separates two properties. The contract is `records/replay/DETERMINISM_CONTRACT_v1.md`.

**Scientific reproducibility.** Replaying a project gives the same numbers, evidence records and interpretations,
provided it uses:
- the same input files, in the same layout relative to the project;
- the same configuration;
- the same recorded answers;
- the same RNPLens version.

The numbers include contact rows, per-structure contact lists, agreement values, region counts and update-report
counts. This property is checked for every file a workflow writes.

**Byte-identical reproducibility.** A named list of **canonical** files has exactly the same bytes in such a replay,
wherever the project lives and whenever it runs.

### Canonical files (version 1)

Paths are relative to the managed project.
- `.rnplens/HEAD`, `.rnplens/state/v*.json`: the version history, recorded decisions and clarification requests.
- `.rnplens/cache/*.json`, `.rnplens/cache/invalid/*.json`: cache keys, with superseded entries numbered `.1`, `.2`, …
  rather than time-stamped.
- `analyses/v*/index.json`, `analyses/v*/update_report.json` and `.html`, `analyses/reports/*`.
- `imports/v*/*/construct_protein.fasta` and `construct_rna.fasta`, and the derived structure copies `imports/v*/*/derived/*/*`.
- `analyses/v*/*/report/contacts_by_output.json`, `analyses/v*/*/report_runs_*/contacts_by_output.json`.
- `analyses/v*/*/region_*/region_contacts.tsv`.

What makes these files canonical:
- **Paths** are relative to the project. A path inside the project is written `./…`; an input folder beside the
  project is written `../…`.
- **Keys** are sorted.
- **No volatile metadata** appears in them: no time stamp, duration or source commit.
- **Every hash covers canonical bytes only.** A hash of a file that is not canonical (the importer's `manifest.json`,
  `summary.json`) is a **content hash** (`*_content_sha256`). It covers that file with its creation time removed and
  its paths made relative.
- **Cache keys** are computed over these canonical forms, so a copied or moved project keeps its keys.

### The sidecar

Volatile execution metadata of each canonical file goes to its sidecar,
`<project>/.rnplens/run/<same relative path>`. The metadata is:
- time stamps;
- the source commit;
- the raw byte hashes of non-canonical files;
- the tamper-detection hashes of cache entries;
- the absolute project root, the working directory and the Python version.

RNPLens reads the sidecar back, so `rnplens clarify --history` and `rnplens update --versions` still show times.
Deleting the sidecars changes no result:
- times show as unknown;
- cache entries can no longer be verified, so the work is recomputed.

### Files that are not canonical in version 1

The byte rule does not apply to the files below. The scientific comparison does.
- **Qualified 0.3 routes, which 0.4 leaves unchanged**: the importer's `manifest.json` and `report_contract.json`,
  `summary.json`, Report's `rnplens_run.json` and `result.json`, the HTML reports, and the logs. These records contain
  their own creation time, absolute paths and (`result.json`) run durations.
- **Other 0.4 outputs**: `region.json`, `explain/*`, `followup/*`, the consent record, `methods/*`, `groups/*` and
  viewer outputs. Their bodies still hold absolute paths, and some embed raw hashes of the files above. A follow-up
  recorded under evidence-hash definition 1 therefore has an `evidence_sha256` that changes when the project is moved
  or re-imported, even though its statements do not. Follow-ups recorded under definition 2 do not have this
  dependence (see *Follow-up evidence hash* below).

### Projects written before this change

Earlier 0.4 projects are read, verified and updated unchanged. These are projects with state schema
`rnplens-project-state-1`, which has absolute paths and inline times. The first update with the new code may
recompute an analysis, because keys are now computed over canonical components. The update report lists the changed
key components. Recorded answers keep applying while their input files are unchanged.

### Limits

- Byte identity needs the same relative layout of project and inputs, and the same RNPLens version.
- An absolute path outside the project, its declared inputs, the reference and their common parent folder stays
  absolute. Such a path makes a file differ between locations.
- The byte rule covers only the files listed above.
- The pre-registered byte-identical replay check of demonstration 2 (24BR) **FAILED** before this change, and that
  verdict stands. The requalification on independent cases is reported in
  `records/replay/REPLAY_REQUALIFICATION_REPORT.md`.

### Canonical projections (version 2)

`records/replay/DETERMINISM_CONTRACT_v2.md` extends the promised files to every scientifically meaningful field.

**Which files get a projection.** Every JSON or text output `F` of a managed project, if it is not a v1 canonical
file. The extensions are `.json`, `.md`, `.txt`, `.html`, `.tsv`, `.svg` and `.log`. This includes all the files
listed above.

**Where the projection is.** It is written next to `F`:
- `F.json.canonical.json` for a JSON file;
- `F.<ext>.canonical.txt` for a text file.

**What the projection changes.**
- Paths are relative to the project.
- Time stamps, durations, command lines, host and interpreter details are removed.
- Consent ids are reduced to their counter, e.g. `consent-0001`.
- A hash of a file that has a projection becomes `projection-sha256:<hash of that file's projection>`.
- In a follow-up record, `evidence_sha256` is replaced by `evidence_content_sha256`, which depends only on the
  statements and the tool log.

**What it leaves unchanged.** `F` itself is never changed, and readers keep using it. Projections do not change any
number.

**Projection index.** `<project>/.rnplens/run/projection_index.json` maps each raw hash ever written to its
projection's hash. A hash recorded for an earlier version of a rewritten file therefore still has a stable
projection form.

**Promised set.** It is every file of the project except two kinds:
- the sidecars under `.rnplens/run/`;
- the raw files that have a projection. The projection is promised in their place.

**Moved projects.** The project remembers its earlier locations from its state sidecars. A copy at another absolute
path therefore keeps its canonical forms and cache keys, and an update there reuses the earlier work.

**Raw paths.** Raw files of a moved copy still hold the original absolute paths. The 0.3 importer manifest is one
of them. Earlier 0.4 code read structure files from the original location through these paths, without saying so.
The next section replaces that behaviour.

### Copied and moved projects (portability)

`records/replay/PORTABILITY_TEST_v1.md` pre-registers the behaviour below; the results are in
`records/replay/PORTABILITY_REPORT_v1.md`. It applies to managed projects (a folder with `.rnplens/HEAD`). A plain
import or analysis folder outside a managed project keeps its 0.3 behaviour.

**Resolving a recorded file.** Every structure file a command reads is a recorded pair (path, SHA-256). RNPLens
looks for it in this order and uses it only if its SHA-256 matches the record:
1. **RELINKED**: a mapping recorded by `rnplens relink` in `<project>/.rnplens/relink.json`.
2. **LOCAL**: the path lies in the project's current location (the project, its declared inputs or the reference).
3. **MAPPED**: the path lies under a former location of the project or its parent folder, translated to the
   same place under the current location.
4. **EXTERNAL**: the recorded absolute path itself, outside the current location.

A file found nowhere is **MISSING**. A file whose bytes differ from the record is **MISMATCH**. A file with the
same name and different bytes is never used.

**What commands do.**
- Commands that read structure bytes (`analyse`, `update`, `region`, `view`, `group`, `export-methods`,
  follow-up replay) refuse with exit status 6 and the line `PORTABILITY REFUSED` when a required file is MISSING or
  MISMATCH. The message lists the files (changed ones first) and names `rnplens relink`. `update` refuses before it
  takes the project lock or writes anything.
- When a command uses an EXTERNAL or RELINKED file it says `NOT SELF-CONTAINED`: the copy still depends on files
  outside its own folder.
- Commands that only report records (`explain`, the evidence query) never refuse. They print `PORTABILITY WARNING`
  when the records name files that are not available here.
- A project that was never moved keeps the earlier behaviour: an input folder that disappears is a removed run.

**Relinking.** `rnplens relink PROJECT --search DIR` looks under `DIR` for files with the recorded names and
records only candidates whose SHA-256 matches. Same-name files with different bytes are listed as
`rejected (same name, different SHA-256)`. When byte-identical copies exist in several runs, the candidate with the
longest common path tail is chosen. `--map OLD=NEW` replaces a path prefix; `--dry-run` records nothing. Recorded
answers for declared inputs carry over to the relinked paths. A same-name file with different bytes is an edited file,
a new input version: the refusal names the exact `rnplens update PROJECT NEW_FOLDER --remove-input OLD_FOLDER`
command that analyses it as a new project version, leaving every earlier version byte-identical
([project_state.md](project_state.md#edited-input-files-a-new-input-version)).

**Follow-up evidence hash.** Each follow-up record and plan stores `evidence_hash_version`.
- `rnplens.followup.evidence.1` (definition 1; records without the field): absolute paths are reduced to their last
  component; raw SHA-256 values of project records are hashed as written.
- `rnplens.followup.evidence.2` (definition 2, written by new follow-ups): in addition, a raw SHA-256 of a JSON or
  text record of the project is replaced by the hash of that record's canonical projection. The hash then does not
  depend on where the project is.
- A replay recomputes the hash under the definition recorded in the plan. Older records therefore still replay and
  verify, and a project moved after the follow-up replays it with the same `evidence_sha256` under definition 2.

**What is and is not claimed.**
- Complete byte identity of every raw file of a managed project is **not** claimed. The raw files carry volatile
  fields by design.
- Byte identity is promised for the v1 canonical files and the projections.
- The results of the v2 retest are in `records/replay/REPLAY_REQUALIFICATION_v2_REPORT.md`.
