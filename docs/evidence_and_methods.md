# `rnplens explain` and `rnplens export-methods`

This page covers two commands in RNPLens 0.4 development. Both have status **DESCRIPTIVE**:

- **D. Explain a value.** `rnplens explain` traces a reported value back to the files, structures, definitions,
  versions and limitations it rests on.
- **F. Export Methods.** `rnplens export-methods` writes a Methods draft and a provenance manifest.

Both commands follow the same rules:

- They read **execution records only**.
- They recompute nothing and use no language model.
- They do not judge whether a value is right. A contact that recurs across predictions is not evidence of
  correctness.

## `rnplens explain`

```
rnplens explain [QUERY] [--id EVIDENCE_ID] [--contact K14-G20] [--region region_13-23]
                [--analysis A ...] [--project P] [--run-dir R ...] [--compare C ...] [--json] [--out DIR] [--no-write]
```

### Sources

Each source option names a directory, and `explain` reads only the files listed for it. The data-access test
checks this.

| option | what is read |
|---|---|
| `--analysis` | An `rnplens analyse` directory: `summary.json`, `report/*.json`, `region_*/region.json`, `groups/**.json`. Earlier `explain/` answers are never read back. |
| `--project` | The project's `manifest.json`. It is inferred from `report/rnplens_run.json` when this option is omitted. |
| `--run-dir` | An assistant run: `evidence.jsonl`, `run_record.json`, `plan.json`, plus the analyses inside the run, under `tools/analysis_*`. |
| `--compare` | An `rnplens compare` directory: `comparison_summary.json`, `comparison.tsv`, `evaluate_runs.json`. |

### Queries

| query | answers |
|---|---|
| `--id ID` (query `evidence`) | Takes one evidence ID: `<file>#<JSON pointer>`, for example `region_13-23/region.json#/contacts/0` or `summary.json#/contacts/rows/3`, or an assistant record id such as `E12`. Returns the value, the recorded source and definition, the tool version and code commit, the inputs with SHA-256, the command, the contributing structures, and the limitations recorded with that file. Each structure is listed with its id, engine, run, sample, designation, used file, SHA-256 and chain status. |
| `contact --contact K14-G20` | Which structures support the contact, read from Report's `contacts_by_output.json`. For each structure: id, run, sample, designation and file. Also which structures do not list the contact, the summary row, the region class (including "not observed" structures) and the contact definition. The residue letters are checked against the construct. |
| `structures`, `excluded` | Runs with their engine designation and rule. Included structures. Files excluded at import, with the verdict and the reasons quoted verbatim. Unrecognised files and top-level copies. Structures that Report found ineligible. Structures not compared in a region. |
| `count` | How many structures contributed at each stage: import counts, Report's eligible structures per engine, structures per region, and the assistant's inventory records. |
| `versions` | The RNPLens version of each record, the implementation, every recorded command (`rnplens_run.json`), Report's software environment, the provenance blocks (kind, version, code commit), and the assistant version and registry hash. |
| `definitions` | The contact and position definitions, the engine weighting, each provenance `definition`, and compare's notes. |
| `files` | Every output file, with its SHA-256. |
| `limitations` | The limits recorded with the summary, Report's own statement of meaning, the region and group limits, and compare's withheld metrics. |
| `unavailable` | Which metric or analysis was unavailable, and why. This covers: Report not run; repeat agreement not computed (with the reason); Diagnose refused or not run; Evaluate not run, or no DockQ value; withheld geometry values; a region figure that was not drawn; assistant records whose state is not `COMPUTED` (for example `TOOL_BLOCKED` or `METRIC_UNAVAILABLE`); rejected plan steps; compare's withheld metrics and unmatched targets. It also lists the capabilities that are never offered. |
| `correspondence` | The correspondence rule applied to each structure: chain status (`EXACT`, `RENUMBER`, `SEQUENCE_DIFFERS` with its alignment summary), file numbering and offsets, and derived-copy transformations. Also Evaluate's DockQ chain mapping and compare's `CORRESPONDENCE_CHANGED` targets. |
| `region_mapping` | How an RNA region was mapped: its numbering, the filtering definition, and each structure's coverage (`COMPLETE`, `PARTIAL` or `UNRESOLVED`, with its reason). Also the assistant's region records. |
| `not_like_for_like` | Why a comparison is not like-for-like. From compare: every target in `CONSTRUCT_CHANGED`, `NOT_EVALUABLE_IN_BOTH`, `NEWLY_EVALUABLE`, `NEWLY_UNEVALUABLE`, `CORRESPONDENCE_CHANGED` or `RUN_FAILED`, with the class meaning from `rnplens/compare.py`; the like-for-like count; and unmatched targets. From a project: runs that differ in size (the number of included structures each run contributes; files excluded at import are reported separately), designation rule or engine, and region runs with partial or unresolved coverage. |

### Output

Every statement carries:

- an `evidence_id`, relative to the root it came from (`root` gives that root);
- the template `text`, which passes the wording audit;
- a `quoted` field, holding text copied verbatim from the cited record field (tests check this). Quoted record text
  is exempt from the audit, as the fixed limits block is on the HTML pages.

Where available, statements also carry the `value` and structure fields.

For a line in `evidence.jsonl`, the pointer is the 0-based line number, and `record_id` holds the assistant's own
record id.

With `--analysis`, the answer is written to `A/explain/explain_<query>_<hash>.json` and `.txt`. The JSON includes a
provenance block that lists every record read, with its SHA-256. Use `--no-write` to print only.

### Worked example (bundled 7K9D example, after `rnplens region p r --rna 13-23`)

```
$ rnplens explain contact --contact K14-G20 --analysis r
- contact K14-G20 is listed by 2 of 2 structure(s) with Report contact lists = [2,2]  [report/contacts_by_output.json#/]
- BOLTZ2|exec_A#7K9D_model_0 lists K14-G20: s001, run exec_A, sample 7K9D_model_0, engine-designated, file ... (SHA-256 9c1a6659...)  [report/contacts_by_output.json#/BOLTZ2|exec_A#7K9D_model_0/0]
- BOLTZ2|exec_B#7K9D_model_0 lists K14-G20: s002, run exec_B, sample 7K9D_model_0, engine-designated, file ... (SHA-256 89f54c2a...)  [report/contacts_by_output.json#/BOLTZ2|exec_B#7K9D_model_0/0]
- analysis summary row for K14-G20  [summary.json#/contacts/rows/0]
- region_13-23: SHARED_BY_ALL_RUNS, present in run(s) exec_A, exec_B  [region_13-23/region.json#/contacts/0]
- contact definition "protein residue and RNA nucleotide with any heavy-atom pair within 5.0 A, in construct positions (Report's own contact lists)"  [summary.json#/contacts/definition]
```

## `rnplens export-methods`

```
rnplens export-methods ANALYSIS [--project P] [--run-dir R ...] [--out DIR]
```

### Files written

The command writes four files to `ANALYSIS/methods/`, or to `--out`:

| file | content |
|---|---|
| `methods.md` and `methods.txt` | A concise draft, marked **DRAFT FOR AUTHOR REVIEW**. Its sections are: structures analysed; input and construct identification; software; measures; agreement between runs; missing outputs and unresolved positions; reference-based and reference-free measures; assistant. Sentences whose record field is missing are listed under "Not stated". |
| `methods_sources.json` | Every sentence, with its id, its section and the record fields it was built from (record, file, JSON pointer, evidence ID, value). Also the omitted sentences, each marked `field_missing` or `not_applicable`, and `llm_used: false`. |
| `provenance_manifest.json` | Every input, with its SHA-256 now and as recorded. Inputs are the project files, the original and derived structure files, and the assistant records. Every output file of the analysis, with its SHA-256. Every command, from `rnplens_run.json`, `commands.log` and the region and group provenance. The versions. |

### How the draft is built

Every sentence comes from a template. Templates read records only through one accessor, which logs each field they
use; those logged fields become the sentence's sources. If a field is absent, the template stops, and the sentence is
omitted and listed.

A template that iterates over a record's keys checks those keys against an independent record field. For example,
the engines in `contacts.denominators` must equal `report.engines`. This means a removed key omits the sentence
rather than shortening it silently.

Nothing is invented. No condition, version, statistic or citation appears unless it is in a record. Version numbers
in the text are tested against their source values, and no citation is generated.

The draft covers:

- the structures analysed, the runs and the designation rule;
- how inputs and constructs were identified (engine-label source, SHA-256, chain status, derived copies, exclusions);
- the RNPLens version and Report's environment;
- the measures computed;
- how agreement was defined (region listings; no agreement score);
- how missing outputs were handled (Report-ineligible structures, not-computed measures, "not observed");
- which analyses needed a reference (Evaluate, and the withheld geometry values);
- which reference-free measures are descriptive.

### Example (bundled 7K9D example, two runs, region 13-23)

> A total of 2 predicted structures of one protein-RNA construct (protein, 98 residues; RNA, 60 nucleotides) were
> analysed. The structures came from 2 prediction runs of Boltz-2: exec_A, 1 structure; exec_B, 1 structure. ...
> Residue-nucleotide contacts were taken from the per-structure contact lists written by RNPLens Report; a contact
> was defined as a protein residue and RNA nucleotide with any heavy-atom pair within 5.0 A, in construct positions
> (Report's own contact lists). ...

## Interpretation limits

- Both commands report how a value was obtained and what it rests on. They do not show that the value is right, and
  a contact that recurs among predictions is not evidence of correctness.
- `explain` quotes records verbatim. A quotation is only as complete as the record it comes from: a field that was
  never written cannot be explained, and the answer says when a record is missing (`INPUT_MISSING`).
- The Methods draft restates what the records show was run. It does not describe the study design, the biological
  question or the prediction settings, because no RNPLens record holds them. The author must add these, together with
  every citation.
- Evidence IDs are relative to the directory they came from. Moving or editing a record after the fact breaks the
  link, and the SHA-256 values in the provenance blocks make such a change visible.

## Tests

| test file | what it covers |
|---|---|
| `tests/test_evidence_query.py` | Every statement of every query resolves to its record, and quotations are verbatim. Also: region and summary evidence IDs; contact support against `contacts_by_output.json`; excluded files; counts; versions; unavailable metrics (including assistant `TOOL_BLOCKED` records); correspondence and derived copies; region mapping; not-like-for-like from a real `rnplens compare` run (`CORRESPONDENCE_CHANGED`, `NEWLY_UNEVALUABLE`); assistant record lookup; malformed queries; determinism; LLM-free and offline operation; data access; CLI; capability registration. |
| `tests/test_methods_export.py` | Every sentence has sources that resolve. Removing any source field removes its sentence; this is checked over five record sets, including one with a reference, one with derived copies and exclusions, one with two runs of two samples, and one with an assistant run. Also: whole-record missing; refusal of a non-analysis directory; topic coverage; no invented versions; determinism; the provenance manifest; LLM-free and offline operation; wording-audit blocking; CLI; capability registration. |
