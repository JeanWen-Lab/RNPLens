# Historical internal identifiers

**RNPLens** is the only name of this software, its command and its distribution. Before the public name was
adopted, the project used the internal identifier **RNPBench**. That identifier is still present inside RNPLens
in the places listed below. It is kept there **only** because changing it would alter frozen, hash-verified or
schema-level content against which RNPLens's numerical behaviour was qualified. It does not refer to a separate
project, package or command, and nothing in this list needs to be used by name.

| kind | identifiers | why it is kept |
|---|---|---|
| frozen scorer sources | the eight files under `src/rnpbench_core/frozen/` (for example `canonical/rnpbench_score_v2.py`) | their SHA-256 is verified at run time; any edit would stop the scorer from loading |
| internal Python module names | `rnpbench`, `rnpbench_core`, `rnpbench_evaluate`, `rnpbench_report`, `rnpbench_diagnose` (the earlier import alias `rnpbench_predict` was removed in 0.2.0rc3; it was used by no RNPLens tool) | the frozen loader binds the scorer modules by name; these modules are not a public Python API (the interface is the `rnplens` command) |
| input contracts and output schemas | `RNPBENCH_EVALUATE_INPUT_V1`; `rnpbench-predict-contract-1`; `rnpbench-predict-result-1` | written into and checked against every contract and result file |
| scoring configurations | `RNPBENCH_SCORING_V3_CONSTRUCT_POSITION_DOCKQ_2_1_3`, `RNPBENCH_FOUR_AXIS_DECOMPOSITION_SCORE_DECOMP_V1` | name the frozen configuration recorded in each Evaluate result |
| analysis-implementation version | `rnpbench-predict-1.0.0` (Report) | recorded in each Report result; the self-test requires it |
| machine-readable field names | `rnpbench_evaluate_version` (Evaluate `result.json`), `rnpbench_diagnose_version` (Diagnose `report.json`); `tool` and `versions.rnpbench-report` in Report's self-test record | changing a key would change every output file |
| frozen specifications and profiles | `RNPBENCH_TOOLKIT_EXAMPLE_REGRESSION_PROFILE_V1`, `RNPBENCH_REPORT_PUBLIC_SELFTEST_SPEC_V1`, `RNPBENCH_EVALUATE_PORTABLE_NUMERICAL_PROFILE_V1`, fixture-rule and audit identifiers in `src/*/fixtures`, `profiles` and `selftest_data` | frozen before the results they govern; the example-regression profile is SHA-256-verified |
| environment variables (optional) | `RNPBENCH_INTERNAL_FIXTURES`, `RNPBENCH_PREDICT_NPROC`; `RNPBENCH_PROFILE` (tests) | read by the frozen components |
| validation records | the files in [validation/](validation/) | historical documents kept verbatim |

Everything a user reads is named RNPLens: the command and its help, error messages, self-test lines, and the
titles and headings of `summary.txt` and of the Report and Diagnose HTML pages. The display names were changed in
0.2.0rc2 by an enumerated, exact-match table that touches no computation (see [reproducibility.md](reproducibility.md)).
