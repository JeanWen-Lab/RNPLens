# Portable qualification contract (rnpbench-evaluate 0.1.1)

The profile file `rnpbench_evaluate/profiles/portable_numerical_profile_v1.json` (`RNPBENCH_EVALUATE_PORTABLE_NUMERICAL_PROFILE_V1`, sha256 `91d29c96ab0edee7…`) was frozen on **2026-10-10T08:56:35Z**, before any v0.1.1 test run and before the AlphaFold 3, Chai-1 and RF2NA fixtures were chosen. A copy was filed read-only on the development host at that time. The self-test refuses to run if the file's hash differs.

| profile | where | rule |
|---|---|---|
| `reference` | the reference build host (Linux x86-64), the platform that produced the frozen values | every compared value bit-identical |
| `portable` | any other platform | the exceptions below; everything else exact |

**Toleranced quantities (absolute):**
- **RMSD, 1e-5 Å:** per-interface iRMSD and LRMSD, and the three geometry RMSDs.
- **DockQ, 1e-7:** unrounded DockQ, adapter total DockQ and per-interface DockQ.

No other floating-point quantity is toleranced. In particular, fnat and fnonnat are ratios of exact integer contact counts and are compared exactly.

**Always exact:**
- displayed values: DockQ, fnat, iRMSD and LRMSD to 3 decimals, geometry to 2;
- DockQ class;
- status, failure stage and reason, and geometry exclusion;
- chain mapping, number of admissible candidates and number of interfaces;
- residue-correspondence counts and all integer counts;
- input SHA-256 values.

**History.** The v0.1.0.dev0 macOS self-test failed under its predeclared bound of 1e-6 (two LRMSD checks: 1.4e-6 Å and 4.5e-6 Å). That record is kept unchanged as `qualification_v0.1.0.dev0/selftest_record_macos_arm64.json` and is **not** re-graded by this profile.

**If a portable run fails,** the failure is reported and work stops for review. Tolerances are not widened after seeing results.
