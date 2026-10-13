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

## The contract

```json
{
  "schema_version": "rnpbench-predict-contract-1",
  "case_id": "MY_CASE",
  "construct": {"protein_length": 191, "rna_length": 8,
                "protein_sequence": "optional, checked against the length", "rna_sequence": "optional"},
  "outputs": [
    {"engine": "AF3", "execution": "run_1", "structure_path": "/abs/path/model.cif", "sha256": "<optional digest>"}
  ]
}
```

- `protein_length` and `rna_length` are the construct you asked for; they are required and never inferred from
  the outputs.
- `structure_path` must be absolute. A `sha256` given in the contract is re-verified before the file is parsed.
- Engines with a built-in confidence parser: `AF3`, `BOLTZ2`, `CHAI1`, `RF3` (ipTM) and `RF2NA` (negated mean
  inter-chain PAE). For anything else use `"engine": "OTHER"` and declare `native_confidence` and
  `native_confidence_kind`, or `null`. Confidences are shown per engine and never compared across engines.

## What it measures

1. **Binding surface** — do the outputs use the same protein surface?
2. **Contact register** — do they pair the same protein residues with the same nucleotides?
3. **RNA pose** — C4′ RMSD of the RNA after superposing the proteins.

Across engines, **support** for a contact is a count of engines; an engine that ran several times contributes the
fraction of its own executions, so it cannot outweigh an engine that ran once (equal engine weighting). Outputs
are grouped into **interface hypotheses** at three thresholds (0.3, 0.5, 0.7; primary 0.5); hypotheses are listed,
never averaged, and the largest group is not implied to be correct. With a single engine, Report gives **repeat
agreement** between that engine's runs only.

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

Component reference: [components/report/README.md](components/report/README.md).
