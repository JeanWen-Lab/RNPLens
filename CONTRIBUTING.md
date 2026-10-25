# Contributing

RNPLens accompanies a scientific study, and its numerical behaviour is fixed by the qualified implementation.
Contributions are welcome under these rules.

- **Numerical behaviour is frozen.** The scorer files under `src/rnpbench_core/frozen/` are verified by SHA-256 at
  run time; do not edit them. A change that alters any reported value, status, class or label needs a new
  version, a documented reason and an independent qualification against the regression references.
- **Run the tests** before opening a pull request:

  ```bash
  python -m pip install -e ".[html,test]"
  rnplens selftest
  python -m pytest
  ```

- **No zero for missing values.** Unscoreable outputs must stay named outcomes (NO VALUE, `INELIGIBLE_…`,
  `TECHNICAL_FAILURE`, …).
- **Interpretation language.** Agreement and disagreement are descriptive; do not add wording or outputs that
  present them as probabilities of correctness, as selectors of the best structure, or as independent validation.
- **Data.** Do not add structure files unless their redistribution terms are documented.

Bug reports: please include `rnplens provenance` output, the platform, and a minimal input that reproduces the
problem.
