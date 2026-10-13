> **Toolkit note (rnpbench-report 0.2.0.dev1, candidate).** RNPBench Predict has been renamed **RNPBench Report**, because it predicts no structures.
> - The Python module is `rnpbench_report`; `rnpbench_predict` and `python -m rnpbench_predict` remain as compatibility aliases. Within the toolkit, the command is `rnpbench report run|validate|selftest`.
> - The analysis code is byte-identical to RNPBench Predict 1.0.0. Results therefore still record `package_version: rnpbench-predict-1.0.0` and the contract identifier `rnpbench-predict-contract-1`.
> - **Self-test (0.2.0.dev1).** `rnpbench-report selftest`, `python -m rnpbench_report selftest`, `python -m rnpbench_predict selftest` and `rnpbench report selftest` all run the same public self-test. It checks installation, contract validation (one valid and eleven invalid contracts) and the bundled 7K9D example against the original Predict 1.0.0 outputs, and confirms that an existing output directory is refused and left unchanged. It needs no internal file. The benchmark-store adapter and the 888-check acceptance suite remain internal qualification tools, run only with `--acceptance-store DIR --overlay DIR`; they are not part of this distribution.
> - **Output protection (0.2.0.dev1).** `run` refuses if `--outdir` already exists (exit status 2) and changes nothing. There is no overwrite option.
> - Agreement is descriptive. It is not a calibrated probability that an interface is correct.

# RNPBench Predict

Reference-free interpretation of protein-RNA structure predictions. It reads prediction outputs only: no
experimental structure is opened and no accuracy metric is computed anywhere in this package.

**Agreement is descriptive evidence about convergence of predicted interface hypotheses. It is not a
probability of structural correctness.** Engines can agree and still be wrong. Every report shows the actual
per-engine contributions before any aggregate, and the package never emits a single derived reliability score
in their place.

## What it answers

Three questions, kept separate and never collapsed into one number:

1. **Binding surface** - do the engines use the same protein surface?
2. **RNA pose** - do they place the RNA in the same position, measured as C4' RMSD after superposing the protein?
3. **Contact register** - do they pair the same protein residues with the same nucleotides?

Cross-engine support is a **count of eligible engines**, not a fraction and not a probability. An engine that
ran twice contributes the fraction of its own executions, so it cannot outweigh an engine that ran once.
Interface hypotheses are groups of engines listed separately at three thresholds, and are never averaged.

## Install

    conda env create -f environment.yml
    conda activate rnpbench-predict

## Use

    python -m rnpbench_predict validate my_case.json
    python -m rnpbench_predict run      my_case.json --outdir out/
    python -m rnpbench_predict selftest --outdir selftest/

`run` writes `result.json` (machine-readable), `contacts_by_output.json` and `report_<case>.html`.

## The input contract

    {
      "schema_version": "rnpbench-predict-contract-1",
      "case_id": "MY_CASE",
      "construct": {"protein_length": 191, "rna_length": 8,
                    "protein_sequence": "optional, checked against the length",
                    "rna_sequence": "optional"},
      "outputs": [
        {"engine": "AF3", "execution": "run_1",
         "structure_path": "/abs/path/model.cif",
         "sha256": "<digest of that file>"}
      ]
    }

`protein_length` and `rna_length` are the construct you **asked for**. They are mandatory and are never
inferred from the outputs: comparison happens in input numbering, and letting a truncated prediction define
its own question would silently rescale the comparison. `sha256` is re-verified before the file is parsed, so a
report can never describe a file that changed after it was registered.

Engines with a confidence parser: `AF3`, `BOLTZ2`, `CHAI1`, `RF3` (ipTM) and `RF2NA` (negated mean inter-chain
PAE from its own matrix). For anything else use `"engine": "OTHER"` and declare `native_confidence` and
`native_confidence_kind` yourself, or `null` to state that none exists. **Confidences are shown per engine and
are never compared across engines** - ipTM and a PAE mean are different quantities on different scales.

## Outcomes, each a named result rather than a degraded number

| outcome | meaning |
|---|---|
| `ELIGIBLE` | both polymers present, every chain matches the declared construct |
| `INELIGIBLE_POLYMER_ABSENT` | a polymer is missing. Not a low-confidence prediction of the complex - not a prediction of it |
| `INDEXING_UNVERIFIED` | a chain length disagrees with the contract, so input numbering cannot be used |
| `CHECKSUM_MISMATCH` | the file changed after the contract registered it |
| `ERROR` | parsing or computation failed; the exception class and message are recorded |

An `ELIGIBLE` output with no protein-RNA contact inside 5 A additionally carries `no_interface_contact: true`
and is flagged in the report. It predicted two polymers and no interface, which must never read as agreement.

## Determinism

The same contract run twice on the same package gives byte-identical `result.json`, and a parallel run equals a
serial one. Contacts are sorted, weighted-Jaccard keys are sorted before summation, and engines and pairs are
iterated in sorted order. The acceptance suite checks all three.

## Verified environments

Measured, not asserted. The acceptance suite and the reproduction below pass on two environments that differ by
a numpy major version and a biopython minor version, producing identical values to 1e-12:

| python | numpy | biopython | matplotlib | result |
|---|---|---|---|---|
| 3.11.15 | 2.4.6 | 1.87 | 3.11.1 | acceptance 888/888; full-cohort reproduction 9,108/9,108 checks over 72 cases |
| 3.11.15 | 1.26.4 | 1.84 | not installed | cross-environment reproduction passes |

`matplotlib` is optional: the core writes JSON without it and only the HTML report needs it.

## Acceptance suite

`selftest` runs four groups and writes `acceptance.json`:

- **A. Contract negative controls** - eleven malformed contracts, each of which must be refused with an error
  naming the offending field.
- **B. Reproduction** - driven through the benchmark adapter, the package must reproduce every value in the
  frozen development result: states, counts, native confidences, repeat agreement, cross-engine support, all
  pairwise agreements, hypothesis groups and support histograms. Integers and states exactly; floats to 1e-12.
  Fields the hardened package **adds** are listed in the output rather than ignored.
- **C. Determinism** - repeat and parallel runs.
- **Full-cohort reproduction** (`tools/reproduce_frozen_store.py`, beyond the suite) - the same comparison over
  every case in the frozen store rather than the seven-case subset: 9,108 checks, 0 failures.
- **D. First-class failures** - a missing polymer, an absent interface and a wrong declared length must each
  surface as a named outcome, and the report must render in every case with the semantic sentence present and
  no accuracy metric anywhere. The frozen store contains no failing output, so these three paths run on
  synthetic fixtures derived from a real output and labelled as synthetic; neither fixture is a prediction.

## What this package deliberately does not do

- compute or report any accuracy metric, or open any reference structure;
- convert agreement into a probability, a calibrated confidence or a single reliability score;
- average interface hypotheses, or imply that the largest group is the correct one;
- compare one engine's confidence against another's;
- claim that it has been validated on a prospective case. It has not.
