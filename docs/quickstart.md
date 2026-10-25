# Quick start

All commands below were run from a clean installation (see [installation.md](installation.md)); their complete
outputs are in [`examples/expected_output/`](../examples/expected_output/). `bash examples/run_examples.sh OUT`
runs all of them.

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

## 3. Validity and candidate disagreement, without a reference (Diagnose: BLOCKED in 0.4)

Diagnose is blocked in the public 0.4 interface until it is re-qualified ([diagnose.md](diagnose.md)). The commands
below refuse with `DIAGNOSE_BLOCKED` and exit code 5, and write nothing. What follows them describes the rc3 tool,
for reference only.

```bash
rnplens diagnose validity examples/reference_free/diagnose_7K9D/*.pdb > OUT/B2_diagnose_validity.json   # 0.4: exit 5; the shell redirect leaves an empty file
rnplens diagnose run examples/reference_free/diagnose_7K9D/*.pdb --mode within_engine --engine BOLTZ2 --target 7K9D --out OUT/B2_diagnose_7K9D
```

`validity` classifies each file as `VALID`, `TECHNICAL_FAILURE` or `STRUCTURAL_FAILURE` (here 5 of 5 `VALID`).
`run` writes `report.json` and `report.html` with the protein-side and RNA-side disagreement, where each sits in the
frozen benchmark reference, the statements it refuses to make, and its limits (see [diagnose.md](diagnose.md)).

For the cross-engine mode give one structure per engine and an `--engine` label for each, in order:

```bash
rnplens diagnose run boltz.pdb chai.cif rf3.cif rf2na.pdb --mode cross_engine --target MYTARGET \
    --engine BOLTZ2 --engine CHAI1 --engine RF3 --engine RF2NA --out OUT/cross
```
