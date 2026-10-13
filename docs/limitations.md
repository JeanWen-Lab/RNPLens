# Limitations

- **Scope.** RNPLens assesses existing predictions of complexes with one protein entity and one RNA entity (any
  copy number). DNA-containing or multi-entity assemblies are outside the qualified scope.
- **No calibrated probabilities.** No output of Report or Diagnose is a probability that a structure or an interface
  is correct, and none should be converted into one.
- **Development-cohort evidence.** Diagnose's reference distributions and the correlations behind its statements
  come from cohorts used in the benchmark's development. The protein-side statement passed a preregistered
  out-of-sample test at a smaller effect; the RNA-side statement has not been tested out of sample. The band
  boundaries were deliberately not recalibrated.
- **Variance, not bias.** Disagreement among candidates cannot detect errors that all candidates share.
- **Validated applicability of Diagnose.** Its statements were validated for Boltz-2 candidates (5–50 per
  target) and for designated outputs of Boltz-2, Chai-1, RF3 and RoseTTAFold2NA, on one-protein-chain,
  one-RNA-chain complexes. Diagnose checks the declared engines, the number of structures and the chain
  composition and refuses otherwise; it cannot check that the declared labels are true, engine versions or
  sampling settings. See [which_analysis_should_i_use.md](which_analysis_should_i_use.md#when-is-a-diagnose-statement-validated).
- **Overlap with engine confidence.** The protein-side disagreement signal overlaps substantially with protein pTM
  and pLDDT.
- **Placement attribution refused.** Diagnose does not attribute error to RNA placement separately from RNA shape;
  that attribution did not hold when measured.
- **Single-engine Report.** With one engine, Report describes repeat agreement only.
- **Reference dependence.** Evaluate's values depend on the reference chosen (model, ensemble member, chain copy).
- **Exact dependency pins.** The frozen scorer depends on DockQ 2.1.3 internals; other DockQ versions are refused
  by default.
- **Platforms.** Qualified on Linux x86-64 (reference platform, bit-identical) and macOS arm64 (portable profile).
  Windows is untested. Python 3.13 is not supported by the pinned numpy/scipy.
- **Historical identifiers in machine-readable fields.** Schema, contract and configuration identifiers and two
  version keys in the output files keep the project's earlier internal prefix (`RNPBENCH_…`, `rnpbench-…`,
  `rnpbench_…_version`); they are listed in [identifiers.md](identifiers.md). Output files record component
  versions; `rnplens_run.json` and `rnplens provenance` record the RNPLens release.
- **Known cosmetic issue.** Diagnose prints ordinal percentiles as, for example, "52th"; the text is part of the
  qualified output and is unchanged in this release.
