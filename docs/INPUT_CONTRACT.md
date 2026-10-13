# Input contract of RNPLens Evaluate (`RNPBENCH_EVALUATE_INPUT_V1`)

The contract identifier is historical and unchanged since it was frozen (see [identifiers.md](identifiers.md)).

**Record notes.**
- In v0.1.0.dev0 this contract was implemented before it was documented; that order is disclosed in the record.
- For 0.1.1, the document was revised to describe the implementation and then frozen. Its agreement with the implementation is checked automatically by `tests/test_contract_document.py`: every command-line option, input field and no-value reason named below must exist in the code, and every command-line option in the code must be named here.

## What the tool does and does not do

1. **It scores one user-supplied prediction at a time** against one experimental reference: one protein entity and one RNA entity, in any copy number.
2. **It does not run structure prediction.**
3. **It does not select a designated output from a pool of candidates.** The user chooses which engine output to evaluate. `prediction.designated_output` only *records* that choice in the report and is never used to choose.
4. **It uses two separate frozen evaluation routes**, reported separately and never merged:
   - **DockQ route** (`RNPBENCH_SCORING_V3_CONSTRUCT_POSITION_DOCKQ_2_1_3`): residue correspondence by **construct position**, over all admissible chain mappings.
   - **Geometry route** (frozen four-axis decomposition): residue correspondence by **sequence alignment**, on the contacting protein–RNA chain pair.

   Because the correspondences differ, one route can return a value where the other gives NO VALUE.
5. **It preserves no-value results.** It never assigns zero to a missing or unscoreable result.
6. **It reports non-standard construct/reference/prediction correspondence and never corrects it.** For example, in the bundled 7K9D example the reference RNA begins with a 5′-triphosphate guanosine (GTP), while the construct records G at position 1. The report states `rna construct differs from the reference entity at 1 G/X`.

## JSON input

```json
{
  "contract": "RNPBENCH_EVALUATE_INPUT_V1",
  "target_id": "7K9D",
  "prediction": {"path": "7K9D_prediction.pdb", "sha256": "optional", "engine": "optional label",
                 "designated_output": {"optional": "free-form record of which engine output this is"}},
  "reference":  {"path": "7K9D_reference.cif", "sha256": "optional"},
  "construct":  {"protein_sequence": "...", "rna_sequence": "..."},
  "options":    {"tolerance": 0}
}
```

Relative paths are resolved against the directory containing the JSON file.

| field | requirement | meaning |
|---|---|---|
| `contract` | must equal `RNPBENCH_EVALUATE_INPUT_V1` | version of this contract |
| `target_id` | 1–64 characters of `[A-Za-z0-9_.-]` | label used in the report |
| `prediction.path` | `.pdb` or `.cif`; residues in each chain numbered 1..L along the construct | the DockQ route reads residue numbers as construct positions. Usability is checked and reported (`dockq.model_numbering`) and never repaired |
| `prediction.sha256` | optional; if given, must match | input identity |
| `prediction.engine`, `prediction.designated_output` | optional | recorded only |
| `reference.path` | mmCIF with `_atom_site.label_seq_id` | the reference's construct positions are its `label_seq_id` values |
| `reference.sha256` | optional; if given, must match | input identity |
| `construct.protein_sequence` | 20 standard amino acids, plus `X` | protein construct |
| `construct.rna_sequence` | `A C G U`, plus `X` for a non-standard nucleotide | RNA construct. The frozen benchmark key uses `X`, and the frozen pipeline scores such targets |
| `options.tolerance` | non-negative integer; frozen default 0 | DockQ chain-grouping tolerance. It is never escalated to obtain a number |

## Command-line form

`rnplens evaluate run` accepts these options. A sequence option takes either a string or a FASTA file.

| option | meaning |
|---|---|
| `--input` | the JSON above |
| `--prediction`, `--reference`, `--protein-seq`, `--rna-seq`, `--target-id` | the fields above, instead of `--input` |
| `--engine` | `prediction.engine` |
| `--tolerance` | `options.tolerance` |
| `--out` | output directory; must not already hold results |
| `--workdir` | directory for temporary staging files (default: the system temporary directory) |
| `--allow-unpinned` | run with a DockQ version other than 2.1.3. The result is labelled as outside the frozen configuration |

Other commands:
- `rnplens evaluate validate --input` checks an input without scoring it.
- `rnplens evaluate selftest [--profile] [--internal-fixtures] [--out]` runs the regression fixtures.
- `rnplens evaluate provenance [--full]` reports the pinned frozen sources and every statement executed from them.

**Configurable dependencies and paths.** No path is built in. DockQ is used as a pinned Python package rather than through a binary path. Staging uses `--workdir`, or else the system temporary directory, which follows `TMPDIR`. Internal fixtures are found through `--internal-fixtures` or `RNPBENCH_INTERNAL_FIXTURES`.

## Refusals (exit status 2; nothing is written)

An input is refused for any of these:
- wrong contract identifier or `target_id`;
- a missing file;
- a sha256 mismatch;
- a missing sequence, or one with letters outside its alphabet;
- a prediction that is not `.pdb`/`.cif`;
- a reference that is not readable mmCIF or lacks `label_seq_id`;
- a negative or non-integer tolerance;
- an output directory that already holds results.

## No-value states (never DockQ = 0)

| route | `failure_stage` / `exclusion` | meaning |
|---|---|---|
| DockQ | `candidate_enumeration` / `METRIC_REFUSED_THE_INPUT_BEFORE_ANY_CANDIDATE` | DockQ could not group or map the chains of this input |
| DockQ | `adapter_application` / `ADAPTER_NOT_APPLIED_NO_NUMBERS_REPORTED` | the construct-position correspondence could not be applied |
| DockQ | `candidate_evaluation` / `NO_ADMISSIBLE_CANDIDATE_SCORED` | no admissible mapping produced a score |
| geometry | the `exclusion` string from the frozen four-axis code | geometry could not be computed |

In `result.json` a missing value is `null`, and in `result.csv` it is `NO_VALUE`, always with its stage and reason. The summary prints `NO VALUE (not zero)`.

## Correspondence reporting (descriptive; never used in scoring)

- **Chain mapping.** Every admissible candidate is listed with its outcome. The released convention reports the first interface of the candidate with the highest total DockQ.
- **Residue correspondence.** The report gives counts of residue pairs in frame, out of frame and indeterminate.
- **Construct against reference.** Whether each construct sequence equals a reference entity sequence, and the positions where it differs (`X` marks a parenthesised modified residue). When the reference has no `_entity_poly` sequence, the check is reported as not assessable (`null`), not as False.
- **Prediction against construct.** For each prediction chain: the number of residues, how many match the construct letter at their residue number, and how many are numbered outside the construct.
