# Quick start

All commands below were run from a clean installation (see [installation.md](installation.md)); their complete
outputs are in [`examples/expected_output/`](../examples/expected_output/). `bash examples/run_examples.sh OUT`
runs examples 1 and 2 and records that Diagnose refuses.

Every `run` command refuses an output directory that already holds results and changes nothing in it.

## 1. Evaluate one prediction against an experimental structure

```bash
cd examples/reference_based
rnplens evaluate validate --input example_input.json
rnplens evaluate run --input example_input.json --out OUT/A_evaluate_7K9D
```

`example_input.json` names the prediction, the reference mmCIF and the construct sequences (see
[INPUT_CONTRACT.md](INPUT_CONTRACT.md)). The same run without a JSON file:

```bash
rnplens evaluate run --prediction 7K9D_prediction.pdb --reference 7K9D_reference.cif \
    --protein-seq 7K9D_protein.fasta --rna-seq 7K9D_rna.fasta --target-id 7K9D --engine Boltz-2 --out OUT/A2
```

| file | content |
|---|---|
| `summary.txt` | human-readable summary (shown in the README) |
| `result.json` | full record: DockQ route, geometry route, correspondence, validity, provenance |
| `result.csv` | one row with the headline values and statuses |

Key fields of `result.csv` for this example: `dockq_status SCORED`, `dockq 0.936`, `dockq_class high`,
`fnat 0.927`, `irmsd 0.434`, `lrmsd 1.780`, `selected_mapping AB:AB`, `geometry_status BLOCKED`,
`geometry_exclusion GEOMETRY_BLOCKED_IN_0.4`, and empty `rna_internal_c4_rmsd`, `rna_placement_c4_rmsd`,
`protein_internal_ca_rmsd`, `n_protein_pairs` and `n_rna_pairs`: in 0.4 the four-axis geometry is blocked by a
residue-correspondence defect and no value is shown ([limitations.md](limitations.md)). The DockQ values do not
replace it.
An unscoreable output would instead have `dockq_status NO_VALUE` with `dockq_failure_stage` and
`dockq_failure_reason` filled and every value empty — never 0.

## 2. Agreement among predictions, without a reference

```bash
rnplens example-contract examples/reference_free --out OUT/B1_report_contract.json
rnplens report validate OUT/B1_report_contract.json
rnplens report run OUT/B1_report_contract.json --out OUT/B1_report_7K9D
```

A Report contract lists the construct and every output (engine, execution, absolute structure path, optionally a
confidence file); see [report.md](report.md). Outputs: `result.json`, `contacts_by_output.json` and
`report_7K9D_example.html`.

For the two Boltz-2 runs of 7K9D, `summary.repeat_agreement.BOLTZ2` gives surface agreement 0.882, register
agreement 0.894 and RNA pose difference 0.957 Å. Cross-engine fields are `null` because only one engine was given.
`summary.SEMANTICS` states: "agreement is descriptive evidence about convergence of predicted interface hypotheses;
it is not a probability of structural correctness".

## 3. Diagnose (not available in RNPLens 0.4)

Diagnose is not available in this release. Its commands refuse with `DIAGNOSE_BLOCKED` and exit code 5, and write
nothing; `examples/run_examples.sh` records this refusal. The 0.2.0rc3 command examples are kept for reference in
[diagnose.md](diagnose.md#reference-020rc3-command-examples-refused-in-rnplens-04).

## Reading the Evaluate summary

`summary.txt` for the 7K9D example (RNPLens 0.4):

```text
DockQ (frozen RNPLens scoring configuration, construct-position correspondence)
  DockQ 0.936  [high]   fnat 0.927   iRMSD 0.434 A   LRMSD 1.780 A
  chain mapping AB:AB (best of 1 admissible); residue pairs in frame 148, out of frame 0, indeterminate 0

Structural geometry: BLOCKED in RNPLens 0.4 (residue-correspondence defect, 2026-10-14); no value is shown.
...
  rna construct differs from the reference entity at 1 G/X (X = modified residue in the reference); reported, not corrected
```

- **DockQ** summarises interface accuracy; **fnat** is the fraction of native residue–nucleotide contacts that the
  prediction reproduces.
- **The geometry route is blocked in 0.4.** It covers RNA shape, RNA placement on the protein and protein Cα RMSD.
  In `result.json` its status is `BLOCKED`, with the code `GEOMETRY_BLOCKED_IN_0.4` and the list of withheld fields;
  in `result.csv` its value columns are empty. The DockQ-family values do not replace it.
- **Missing positions.** Positions missing from the experimental structure are unknown, not confirmed
  non-contacts.
- **The G/X line.** The bundled reference is a reduced copy of PDB 7K9D. Its RNA sequence record lists the
  5′-triphosphate guanosine as X, so the construct–reference difference is reported and left uncorrected. With the
  full RCSB file, the canonical sequence record lists the residue as G, the construct then equals the reference
  entity, and the scores are identical. Evaluate compares against `_entity_poly.pdbx_seq_one_letter_code_can` when
  the file has it.
- **Accuracy, not confidence.** These values measure the accuracy of one prediction; they are not a confidence
  estimate.

## Run records

Every run also writes `rnplens_run.json` next to its results. It records the RNPLens release, the command, and the
SHA-256 of every input and output file.

## Historical expected outputs

The rc3 expected outputs in `examples/expected_output/` are kept unchanged as historical records:

- `B2_diagnose_7K9D/` is the 0.2.0rc3 Diagnose output, not a 0.4 result.
- The rc3 Evaluate output still contains the four-axis geometry values that 0.4 withholds.
- `docs/images/example_diagnose.png` and `docs/images/example_report.png` were rendered from these rc3 pages.

