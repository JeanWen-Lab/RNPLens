# Toolkit examples (public candidates; redistribution pending)

All files are existing RNPBench Boltz-2 predictions of PDB 7K9D, the same target as the Evaluate worked example. No new prediction was made.

- `report_7K9D/`: the rank-0 output of two independent Boltz-2 executions (`exec_A`, `exec_B`), each with its engine confidence file, and `contract_template.json`. Report requires absolute paths: `rnpbench toolkit example-contract DIR` writes a filled-in copy. With one engine, Report describes **repeat agreement** only. Cross-engine agreement needs outputs from several engines.
- `diagnose_7K9D/`: the five samples of one Boltz-2 execution, for `rnpbench diagnose run --mode within_engine`.
