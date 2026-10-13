# Changelog

## 0.2.0rc1 — release candidate (not released)

First public-distribution candidate of RNPLens.

- **Distribution.** One installable Python distribution, `rnplens`, replacing the five internal distributions of the
  RNPBench toolkit 0.2.0.dev1 (`rnpbench`, `rnpbench-core`, `rnpbench-evaluate`, `rnpbench-report`,
  `rnpbench-diagnose`). Install with `python -m pip install -e .` from a clone.
- **Command.** New `rnplens` command (`evaluate`, `report`, `diagnose`, `selftest`, `provenance`,
  `example-contract`, `--version`), a dispatch-only wrapper over the qualified `rnpbench` command. The previous
  commands (`rnpbench`, `rnpbench-evaluate`, `rnpbench-report`, `rnpbench-diagnose`, `python -m …`) remain.
- **Implementation unchanged.** The import packages `rnpbench`, `rnpbench_core`, `rnpbench_evaluate`,
  `rnpbench_report`, `rnpbench_predict` and `rnpbench_diagnose` are byte-identical to RNPBench toolkit
  0.2.0.dev1, including the eight hash-verified frozen scorer files, the regression fixtures and the expected
  outputs. Numerical parity with the qualified toolkit is documented in `docs/reproducibility.md`.
- **Documentation and examples.** New README, user guides, two end-to-end examples with expected outputs, and
  a GitHub Actions workflow (Ubuntu and macOS; Python 3.10–3.12).
- **Not included.** Internal fixtures of AlphaFold 3, Chai-1, RF2NA and RF3 outputs, Report's internal
  acceptance suite and benchmark adapter, the RNPBench benchmark resource, and qualification records.

## History of the implementation (before RNPLens)

- RNPBench toolkit 0.2.0.dev1 (2026-10-10): internally qualified on Linux x86-64 (Python 3.10–3.12) and on a clean
  macOS arm64 installation; not released.
- RNPBench Evaluate 0.1.1, RNPBench Predict 1.0.0 (renamed Report), RNPBench Diagnose 0.2.1: the component versions
  integrated into that toolkit.
