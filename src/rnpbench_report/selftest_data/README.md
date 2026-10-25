Bundled data for the RNPBench Report public self-test (`rnpbench-report selftest`). Distributable test data only; no internal file.

- `report_7K9D/`: two independent Boltz-2 executions of 7K9D (rank-0 outputs) and the contract template. Byte-identical to the toolkit example `rnpbench/examples/report_7K9D/`.
- `expected/`: outputs of the ORIGINAL RNPBench Predict 1.0.0, generated 2026-10-10 on karyon (Linux x86-64, CPython 3.11.17) before the self-test specification was frozen.
  - `report_7K9D_result.json` and `report_7K9D_contacts_by_output.json`: the example path is normalised to `<EXAMPLES>`; `result.json` has `wall_s` and `environment` removed, as frozen in the regression profile.
  - `report_7K9D_example.html`: unmodified.
- `profiles/`:
  - `toolkit_example_regression_profile_v1.json` (frozen 2026-10-10T10:11Z, unchanged);
  - `report_public_selftest_spec_v1.json` and `report_output_protection_rule_v1.json` (frozen 2026-10-10T11:33Z, before this code first ran).
