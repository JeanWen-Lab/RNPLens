# Output schemas

JSON Schemas (draft 2020-12) of the machine-readable files RNPLens writes.

| file written | schema | identifies itself by |
|---|---|---|
| Evaluate `result.json` | [evaluate_result.schema.json](evaluate_result.schema.json) | `rnpbench_evaluate_version`, `dockq.configuration` |
| Report `result.json` | [report_result.schema.json](report_result.schema.json) | `schema_version` (`rnpbench-predict-result-1`), `package_version` |
| Diagnose `report.json` | [diagnose_report.schema.json](diagnose_report.schema.json) | `rnpbench_diagnose_version` |
| `rnplens_run.json` (every `run`, 0.2.0rc3 and later) | [rnplens_run_record.schema.json](rnplens_run_record.schema.json) | `record` (`rnplens-run-record-1`) |

The schemas were derived from the outputs RNPLens actually writes, merged over every regression fixture,
no-value case, worked example and an engine-coverage set (AlphaFold 3, Boltz-2, Chai-1, RF3, RoseTTAFold2NA). A key
is required when it appeared in every such output; additional keys are allowed, so later releases can add fields.
The test suite validates the outputs of the worked examples against them (`tests/test_output_schemas.py`).
Schemas are documentation and a test; RNPLens does not validate its own output at run time.

What a pipeline can rely on:

- **Missing values.** A value that could not be computed is `null`, with a status (`NO_VALUE`, a named Report
  outcome, or a Diagnose refusal) and a reason. It is never `0`.
- **Inputs.** Evaluate and Report record the SHA-256 of their input structures; `rnplens_run.json` records the
  SHA-256 of every input and output file, the command and the RNPLens release, for all three tools.
- **Versions.** Each result file records its component version and configuration identifiers;
  `rnplens_run.json` and `rnplens provenance` record the RNPLens release. Historical key names are explained in
  [../identifiers.md](../identifiers.md).
