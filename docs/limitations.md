# Limitations

- **Scope.** RNPLens assesses existing predictions of complexes with one protein entity and one RNA entity (any
  copy number). DNA-containing or multi-entity assemblies are outside the qualified scope.
- **No calibrated probabilities.** No output of Report or Diagnose is a probability that a structure or an interface
  is correct, and none should be converted into one.
- **Development-cohort evidence.** Diagnose's reference distributions and the correlations behind its statements
  come from cohorts used in the benchmark's development. The protein-side statement passed a preregistered
  out-of-sample test at a smaller effect. The test's reported ρ 0.525 [0.450, 0.593] on 807 targets (historical)
  used the superseded residue correspondence (`SCORE_DECOMP_V1`); recomputed with the corrected one
  (`CONSTRUCT_POSITION_V2`), the value is ρ 0.530 [0.455, 0.598] on 761 targets (435 protein clusters; the 807
  admitted targets less 46 without a construct-position protein correspondence). Under the corrected values the
  band separation and the comparison with the engine's own confidence are much weaker than rc3 states
  ([diagnose.md](diagnose.md)); this is research evidence, not a re-qualification. The RNA-side statement has not
  been tested out of sample. The band boundaries were deliberately not recalibrated.
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
- **Platforms.** rc3 was qualified on Linux x86-64 (reference platform, bit-identical) and macOS arm64 (portable
  profile). For 0.4, Linux x86-64 is the tested interactive environment. On macOS arm64 the toolkit runs; its one
  known numerical parity difference is covered by an approved tolerance on a single value
  (`records/release/TOLERANCE_POLICY_AMENDMENT_1.md`). The language-model modes run natively on both systems with
  different confinement (Linux: bubblewrap, shared network; macOS: Seatbelt, HTTPS only, no private mount namespace;
  `docs/platforms.md`). On macOS they cannot run inside another sandbox.
  Windows is untested. Python 3.13 is not supported by the pinned numpy/scipy.
- **Historical identifiers in machine-readable fields.** Schema, contract and configuration identifiers and two
  version keys in the output files keep the project's earlier internal prefix (`RNPBENCH_…`, `rnpbench-…`,
  `rnpbench_…_version`); they are listed in [identifiers.md](identifiers.md). Output files record component
  versions; `rnplens_run.json` and `rnplens provenance` record the RNPLens release.
- **Known cosmetic issue.** Diagnose prints ordinal percentiles as, for example, "52th"; the text is part of the
  qualified output and is unchanged in this release.

## Known defect and re-qualification status (0.4)

- **Four-axis geometry (Evaluate) is withheld.** On 2026-10-14 a residue-correspondence defect was found in the
  letter-matching step that pairs model and reference residues before Evaluate's four-axis geometry
  (protein-internal, RNA-internal and RNA-placement RMSD) is computed. DockQ, fnat, iRMSD and LRMSD use a different,
  qualified correspondence and are unaffected.
- **Withheld in 0.4.** No public entry point shows the geometry values: `rnplens evaluate run` records the geometry
  status `BLOCKED` (code `GEOMETRY_BLOCKED_IN_0.4`) with empty value fields, `rnplens selftest` and
  `rnplens evaluate selftest` mask them, and `compare`, the `analyse` summary and the menu withhold them. The frozen
  component is unchanged; the rc3 records in `examples/expected_output/` still contain the values as a historical
  record, not as 0.4 results. The components' own command lines (`python -m rnpbench evaluate run`,
  `python -m rnpbench_evaluate evaluate`, `python -m rnpbench diagnose …`, `python -m rnpbench_diagnose …` and the
  other aliases listed in [installation.md](installation.md#commands-installed)) refuse with `LEGACY_ROUTE_REFUSED`
  and exit code 5. Not blocked, by design: the packages' Python API (`import rnpbench_evaluate` …), which `rnplens`
  itself uses; and the eight frozen sources run directly by file path (`python …/rnpbench_core/frozen/…/*.py`):
  their bytes are pinned (SHA-256, checked by `rnplens doctor`), so they cannot carry the check, and their
  `__main__` blocks are the study's research batch drivers, which read and write fixed paths on the study's
  development host. Run elsewhere (checked with the RC wheel in a sandbox without the study data), seven stop with an
  error before computing anything; `canonical/pos_adapter.py` finds no inputs, prints empty check counts (0/0) and
  writes `/tmp/pos_adapter_controls.json` (control status only, no values), or with `--stage population` tries to
  write an empty file under the study's fixed path. None of them shows a blocked measurement. They are not commands
  of RNPLens; on the study's development host they would overwrite research files
  (records/release/GEOMETRY_BLOCK_INVENTORY.md, E21). The grouping does not use
  the RNA conformation difference that depends on the same route.
- **Diagnose is BLOCKED in the public 0.4 interface.** Diagnose's statements about association with error and its
  validated domain rest on evidence that was recomputed under the corrected residue correspondence
  (`CONSTRUCT_POSITION_V2`, records of 2026-10-15); the statements have not been re-qualified against it. In 0.4:
  - `rnplens diagnose run`, `preflight` and `validity` refuse with `DIAGNOSE_BLOCKED` and exit code 5, and write
    nothing;
  - `rnplens analyse` never runs Diagnose and records `DIAGNOSE_BLOCKED` in its summary; `--with-diagnose`
    (`analyse`, `update`) is refused with exit code 5;
  - `rnplens selftest` and `rnplens diagnose selftest` still run Diagnose's internal contract checks (software
    checks, not interpretation); the example statements of its bundled regression are shown only as
    `Diagnose interpretation BLOCKED (checked, not shown)`.
- **Structure viewer: automatically tested; basic display and interaction confirmed manually by the owner on macOS (2026-10-18); switching between binding-hypothesis representatives and offline operation not yet confirmed manually; not fully visually qualified.**
  Automated check (records/viewer/MOLSTAR_VISUAL_VERIFICATION.md): on the tested Linux host, the six demonstration pages (1VTM RNA 1-3, 2JEA RNA 26-35, 6BJG group representatives at 0.3/0.5/0.7 and all 50 6BJG structures) were rendered in headless Chrome for Testing 155 with software WebGL (SwiftShader), with networking disabled and with every request logged: only file: and data: requests were made, and the intended chains, construct positions, Report contact highlights and group representatives were shown (checked through the Mol* API and by inspection of the screenshots). One defect found by this check (highlight colour not visible on the ribbon) was fixed. This is software-rendered headless evidence inspected by an agent. Owner-reported manual test on macOS (2026-10-18; records/viewer/MOLSTAR_VISUAL_VERIFICATION.md): the 2JEA page opened, displayed the structures, rotated and zoomed, responded to nucleotide clicks, and different selections highlighted different regions. Not yet confirmed by a person: switching between binding-hypothesis representatives (6BJG) and operation with the network disconnected; the viewer is therefore not fully visually qualified. Known limits: Mol* panels name structures by an in-memory arcp:// URI (the snapshot title and side table carry the readable name), and the sequence panel does not colour highlighted positions.
- **Reproducibility status.** Numerical/evidence reproducibility: supported by the reported tests. Canonical-file
  byte reproducibility: passed in four development cases under the new contract. Complete managed-project byte
  reproducibility: not yet established. The original byte-identical replay check failed its pre-registered test
  (22 of 43 files differed); that verdict stands. Remediation (records/replay/DETERMINISM_CONTRACT_v1.md): canonical managed-project files now hold relative paths and no time stamps, and volatile execution metadata moved to sidecars under .rnplens/run/. In the pre-registered retest on four further development cases (1VTM, 7K9D, 2JEA, 2Q66), each replayed in another directory at another time on the tested Linux host, every canonical file was byte-identical and no scientific content differed (records/replay/REPLAY_REQUALIFICATION_REPORT.md). Other outputs (importer manifests, summary.json, Report run records, region, explain, follow-up and Methods records) are not byte-identical between runs; a follow-up's evidence_sha256 changes when a project is moved. Byte identity was tested on one Linux host and one Python version only.
- **Language-model modes are not live-qualified.** The natural-language planner with the 0.4 tools and the Codex
  follow-up are EXPERIMENTAL (see [capabilities.md](capabilities.md)).
- **Scientific usefulness of grouping is not established.** Claims that grouping helps researchers are EXPERIMENTAL;
  grouping is never an accuracy selector.
