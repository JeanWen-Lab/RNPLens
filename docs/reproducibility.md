# Reproducibility and relationship to the qualified implementation

## Versions

| item | identifier |
|---|---|
| RNPLens release candidate | `0.2.0rc1` (distribution `rnplens`) |
| implementation distributed | RNPBench toolkit `0.2.0.dev1` (internally qualified 2026-10-10; never released) |
| components inside it | `rnpbench_core` 0.2.0.dev1, `rnpbench_evaluate` 0.2.0.dev1 (contract `RNPBENCH_EVALUATE_INPUT_V1`, scoring configuration `RNPBENCH_SCORING_V3_CONSTRUCT_POSITION_DOCKQ_2_1_3`), `rnpbench_report` (analysis `rnpbench-predict-1.0.0`, contract `rnpbench-predict-contract-1`), `rnpbench_diagnose` 0.2.1 |
| manuscript evidence build | a separate identifier of the study's frozen evidence; it is **not** a software version and is not changed by any software release |

`rnplens provenance` prints all of these together with the dependency versions and the SHA-256 of each of the
eight frozen scorer files, which the code verifies at run time.

## What changed from the qualified toolkit

- **Packaging only.** The five internal distributions became one distribution, `rnplens`, with a new
  dispatch-only `rnplens` command. The 93 files of the six component import packages in the RNPLens wheel are
  byte-identical to those of the five qualified 0.2.0.dev1 wheels.
- **One recorded difference.** Because the components are no longer separate distributions, version fields that
  the components look up by distribution name are now `null`: the `distribution_version` entries of
  `rnpbench toolkit provenance` and the `versions.rnpbench-report` entry of Report's self-test record. No analysis
  output (Evaluate `result.*`, Report `result.json`, Diagnose `report.json`, HTML pages) contains these fields.
  `rnplens provenance` records the component versions by module.

## Release-candidate qualification (2026-10-13)

On the reference platform (Linux x86-64), each from a clean environment built with only the wheel or sdist:

| check | result |
|---|---|
| build | sdist and wheel built from the clean repository |
| install | Python 3.10.22, 3.11.17, 3.12.15 from the wheel, and 3.11 from the sdist; `pip check` clean |
| self-test, reference profile (bit-identical), with the four internal engine fixtures | PASS on all four installations |
| self-test, portable profile | PASS on all four |
| test suite (including the internal-fixture tests) | 99 passed on all four |
| both worked examples | complete on all four; Python 3.10 and 3.12 outputs equal 3.11 apart from the recorded Python version |
| wheel vs sdist installation | identical outputs |
| determinism (same examples twice) | identical apart from run time |
| Report internal acceptance suite through `rnplens` | 888 / 888 checks, `ACCEPTANCE_PASS` |
| Report full-cohort reproduction through the RNPLens installation | `FULL_COHORT_REPRODUCTION_PASS` |

**Parity with the qualified toolkit** (same interpreter, same inputs, identical third-party package versions):
the two worked examples, the Diagnose validity record, Evaluate's 13 regression fixtures (9 public, 4 internal:
AlphaFold 3, Chai-1, RF2NA, RF3), Report's and Diagnose's self-tests, and an internal five-engine Report and
four-engine cross-engine Diagnose on 7K9D were run through `rnplens` and through the qualified `rnpbench`
command and compared after removing run time and output paths. All analysis outputs were identical; the only
other differences were the input paths inside each installation's own site-packages, the names of temporary
directories, and the Report self-test version field described above.

On macOS arm64 (CPython 3.11, clean installation from the same wheel): portable self-test PASS; test suite 88
passed, 11 skipped (the internal-fixture tests, whose fixtures are not distributed); both examples complete.
Against the reference outputs, 13 unrounded values differ, by at most 1.4 × 10⁻⁶ Å; every rounded value, status,
class and label is identical. The earlier internal qualification of 0.2.0.dev1 on a clean macOS arm64
installation found the same behaviour.

The complete qualification records are kept with the release-preparation records; they are not part of the
repository because they reference internal fixtures and the benchmark's development store.
