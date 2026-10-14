# RNPLens Report — reference-free agreement among predictions

Report compares several predictions of the **same** complex — repeated runs of one engine, or outputs of several
engines — without any experimental structure. It opens no reference and computes no accuracy.

> **Agreement among predicted structures is descriptive evidence, not a calibrated probability of structural
> correctness.** Engines can agree and still be wrong. Report is not a predictor of the correct interface.

```
rnplens report run      contract.json --out DIR [--nproc N] [--no-report]
rnplens report validate contract.json [--no-verify-digests]
rnplens report selftest [--profile portable|reference]
rnplens example-contract EXAMPLES_DIR --out contract.json      # the bundled example with absolute paths
```

`--out` and `--outdir` are the same option (the verb's own help lists `--outdir`). The output directory must not
exist; Report refuses an existing one.

## The contract

```json
{
  "schema_version": "rnpbench-predict-contract-1",
  "case_id": "MY_CASE",
  "construct": {"protein_length": 191, "rna_length": 8,
                "protein_sequence": "optional, checked against the length", "rna_sequence": "optional"},
  "outputs": [
    {"engine": "AF3", "execution": "run_1", "structure_path": "/abs/path/model.cif", "sha256": "<SHA-256 of the file, required>"}
  ]
}
```

- `protein_length` and `rna_length` are the construct you asked for; they are required and never inferred from
  the outputs.
- Each output needs `engine`, `execution`, `structure_path` and `sha256`. `structure_path` must be absolute.
  `sha256` is the digest of the structure file as you registered it (`shasum -a 256 FILE` on macOS,
  `sha256sum FILE` on Linux); it is re-verified before the file is parsed, so a report never describes a file
  that changed afterwards. `--no-verify-digests` skips that re-verification only; the field is still required.
  `rnplens example-contract` shows a complete contract with digests filled in.
- Use one contract per complex and at least **two** eligible outputs. With a single output, Report runs but no
  agreement can be computed (`repeat_agreement` is empty).
- `engine` must be exactly one of `AF3`, `BOLTZ2`, `CHAI1`, `RF3`, `RF2NA` or `OTHER` (upper case, no hyphen;
  `Boltz-2` is refused, write `BOLTZ2`). The first five have a built-in confidence parser; for any other engine
  use `OTHER` and declare `native_confidence` and `native_confidence_kind` yourself, or `null`. Confidences are
  shown per engine and never compared across engines.
- **Where the confidence is read from.** In the directory of the structure file, or in `confidence_dir` if you
  give one for that output:

  | engine | file | value |
  |---|---|---|
  | `AF3` | the single `*_summary_confidences.json` | `iptm` |
  | `BOLTZ2` | `confidence_<model file stem>.json` (for `6DCB_model_0.pdb`: `confidence_6DCB_model_0.json`) | `iptm` |
  | `CHAI1` | `scores.model_idx_<N>.npz`, N taken from the model file name | `iptm` |
  | `RF3` | `<name>_summary_confidences.json` beside `<name>_model.cif` | `iptm` |
  | `RF2NA` | the `.npz` beside the model | negated mean inter-chain PAE |

  A missing file is reported as `UNAVAILABLE` with the reason; it never stops the agreement analysis.

## What it measures

1. **Binding surface** — do the outputs use the same protein surface?
2. **Contact register** — do they pair the same protein residues with the same nucleotides?
3. **RNA pose** — C4′ RMSD of the RNA after superposing the proteins.

Across engines, **support** for a contact is a count of engines; an engine that ran several times contributes the
fraction of its own executions, so it cannot outweigh an engine that ran once (equal engine weighting). Outputs
are grouped into **interface hypotheses** at three thresholds (0.3, 0.5, 0.7; primary 0.5); hypotheses are listed,
never averaged, and the largest group is not implied to be correct.

**Hypotheses group engines, not individual outputs.** Two engines fall in the same hypothesis when their
register agreement reaches the threshold. With a **single engine** there is always exactly one hypothesis, whatever
the agreement between its runs, so `n_hypotheses_at_primary_threshold = 1` then carries no information. Read
`summary.repeat_agreement` instead: surface agreement, register agreement and RNA pose difference between the
engine's runs. The cross-engine medians (`median_pairwise_…`) are `null` with one engine.

**Contact support** is the number of engines proposing a contact, with each engine weighted equally across its
runs: a contact proposed in one of two runs of the same engine has support 0.5. `n_contacts_proposed_by_any_engine`
counts every contact with support above 0. `contact_support_histogram` counts contacts with support of at least
1, 2, … whole engines, so contacts proposed by only some runs of one engine (support below 1) are in the total but
not in the histogram.

## Named outcomes instead of degraded numbers

| outcome | meaning |
|---|---|
| `ELIGIBLE` | both polymers present; every chain matches the declared construct |
| `INELIGIBLE_POLYMER_ABSENT` | a polymer is missing — not a low-confidence prediction of the complex, not a prediction of it |
| `INDEXING_UNVERIFIED` | a chain length disagrees with the contract, so input numbering cannot be used |
| `CHECKSUM_MISMATCH` | the file changed after the contract registered it |
| `ERROR` | parsing or computation failed; the exception is recorded |

An eligible output with no protein–RNA contact within 5 Å is flagged `no_interface_contact: true`; it must never
read as agreement. A contract with no outputs is refused by `validate`.

## Outputs

`result.json` (schema `rnpbench-predict-result-1`; `summary` holds the case-level values, `per_output` one
record per output, `engine_pairs` the cross-engine comparisons, `contact_support` the support of each
residue–nucleotide contact), `contacts_by_output.json`, and a self-contained HTML page (figures need the `html`
extra). The same contract run twice gives a byte-identical `result.json` apart from the timing field.

The schema identifiers above are historical and unchanged ([identifiers.md](identifiers.md)).
