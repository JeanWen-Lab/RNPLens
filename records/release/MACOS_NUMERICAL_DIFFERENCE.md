# The known macOS numerical difference in `test_report_numbers_equal_the_rc3_expected_output`

Track release-docs, 16 Oct 2026, base commit `cf81acd`. Neither the test nor the rc3 expected outputs were changed.
Evidence files are in `records/release/macos_probe/`; the probe script is `records/release/macos_float_probe.py`.
Both are read-only diagnostics and change no file of the repository.

## 1. Which value differs, and by how much

The test (`tests/test_workflow_analyse.py`) imports the bundled 7K9D example (two Boltz-2 runs, `exec_A` and `exec_B`),
runs `rnplens analyse`, and compares Report's `result.json` with the rc3 expected output
`examples/expected_output/B1_report_7K9D/result.json`, which was produced on the Linux x86-64 reference platform.
It asserts exact equality of `contact_support`, `summary.repeat_agreement` and the per-output contact counts.

Exactly **one value** differs: `summary.repeat_agreement.BOLTZ2.rna_pose_difference_A`, the RNA C4' RMSD (Å)
between the two runs' designated structures after superposing their protein Cα atoms.

| | value (`repr`) | `%.17g` |
|---|---|---|
| rc3 expected (Linux x86-64) | `0.957383346052161` | `0.95738334605216102` |
| karyon, Linux x86-64, at cf81acd | `0.957383346052161` (bit-identical to expected) | `0.95738334605216102` |
| macOS arm64, local, at cf81acd | `0.9573833460521571` | `0.95738334605215714` |

- Absolute difference: **3.886 × 10⁻¹⁵ Å**; relative difference 4.06 × 10⁻¹⁵.
- In units in the last place: **35 ULP** (the float64 spacing at this magnitude is 1.11 × 10⁻¹⁶).
- First differing digit: the **15th significant digit** (0.95738334605215**7** against 0.95738334605216**1** at 15
  significant digits). Every printed form of this value is identical on both platforms: `0.957` in the analysis
  summary (`%.3f`), `0.96 Å` in the README and `0.9`/`1` in Report's HTML table (`%.1f`, `%.0f`).

**Everything else is identical.** A deep comparison of the whole `result.json` (`macos_probe/result_deepdiff.py`,
outputs in `macos_probe/deepdiff_outputs.txt`) found 59 floats in each file. Of the 58 scientific floats (all but
`wall_s`), 57 are bit-identical on macOS and 58 on karyon. Every integer, contact list, residue list, count and
string is identical on both platforms, apart from the platform and Python version records, `wall_s`, and the
`execution` labels that `analyse` writes (`exec_A#7K9D_model_0`; identical on both platforms). In particular
`surface_agreement` (0.8823529411764706) and `register_agreement` (0.8936170212765957), which are ratios of integer
counts, are bit-identical.

## 2. Why it differs

The value is computed by Report's frozen `rnpbench_report.geometry.kabsch_rmsd`: centroids, the 3 × 3 covariance
`H = (P − Pc)ᵀ (Q − Qc)` (a BLAS matrix product), `numpy.linalg.svd(H)` (LAPACK `dgesdd`), a determinant sign,
the rotation `Rm = Vᵀ diag(1, 1, d) Uᵀ`, then the RMSD of 60 C4' pairs. The probe recorded every intermediate bit-exactly
(`float.hex`) on both platforms:

| step | macOS vs karyon |
|---|---|
| input coordinates (98 Cα pairs, 60 C4' pairs, parsed by Biopython 1.84 from float32 PDB fields) | bit-identical (equal SHA-256 of the float64 arrays) |
| centroids `Pc`, `Qc` | bit-identical |
| covariance `H` (BLAS product) | bit-identical |
| singular values `S` (7873.097, 5281.066, 3348.549) | differ by 3, −1 and 0 ULP (≤ 2.7 × 10⁻¹² absolute) |
| `U`, `Vt` | differ by up to 17 ULP in `U` and 142 ULP in one small `Vt` element (−0.00405); every element ≤ 4.4 × 10⁻¹⁶ absolute |
| determinant sign `d` | identical (+1) |
| rotation `Rm` | differs by up to 15 ULP (≤ 2.2 × 10⁻¹⁶) |
| final RMSD | differs by 35 ULP (3.9 × 10⁻¹⁵ Å) |

**Decisive check.** When the karyon SVD factors (`U`, `S`, `Vt`) are substituted into the macOS computation, macOS
produces `Rm` and the final value **bit-identical** to karyon (`0.957383346052161`). The SVD is therefore the only
source of the difference; the BLAS products, numpy's reductions, `sqrt` and Python are not.

**Why the SVD differs.** `numpy.linalg.svd` calls LAPACK `dgesdd` from the linear-algebra library that numpy is
linked against, and the two installations use different builds:

| | macOS arm64 (local conda env `rnplens`) | karyon (venv `RNPLens_dev_0.3/venv`) |
|---|---|---|
| numpy | 1.26.4, conda-forge build `py311h7125741_0` | 1.26.4, PyPI wheel |
| BLAS/LAPACK | conda-forge `libopenblas` **0.3.34** (OpenMP build) via `libblas`/`liblapack` 3.11.0 | bundled `libopenblas64_p` **0.3.23.dev** (DYNAMIC_ARCH, 64-bit integers) |
| CPU kernels | Apple arm64 (NEON) | AMD EPYC 9555 (x86-64, AVX2/AVX-512) |
| Python | 3.11.17 | 3.11.15 |

Different OpenBLAS versions and CPU-specific kernels (vector width, fused multiply-add, blocking) round the
intermediate steps of the SVD (Householder bidiagonalisation and the divide-and-conquer iteration) differently. Both
results are correct to within the backward-stable error of the algorithm: the covariance matrix is well conditioned
(singular values 7873, 5281, 3349).

**Neither platform is exact.** A 60-digit recomputation of the same formula from the same float inputs
(`macos_probe/high_precision_reference.py`, mpmath) gives 0.95738334605216198. The karyon value is 9.6 × 10⁻¹⁶ Å
below it (8.6 ULP) and the macOS value 4.8 × 10⁻¹⁵ Å below it (43.6 ULP). The rc3 expected value is the reference
platform's rounding, not a truer value. Rearranging the same arithmetic on one platform moves the result by a
similar amount (BLAS-free `einsum` variants give 0.957383346052157 on macOS and 0.9573833460521597 on karyon).

**Not the cause.** The input parsing (bit-identical inputs), numpy summation order (the covariance and all
reductions are bit-identical once the SVD factors agree), libm (`sqrt` is correctly rounded), the Python version,
and RNPLens code (unchanged frozen component).

**Side observation (environment, not the cause).** The local conda env `rnplens` has scipy **1.17.1**, not the
pinned 1.13.1 (karyon has 1.13.1). SciPy is not on this code path (`numpy.linalg` only), but a macOS qualification
run should use an environment that satisfies every pin.

**Not done.** Only this one example was characterised, because it is the only failing test. No other macOS machine,
no Apple Accelerate build of numpy and no other OpenBLAS version was tried. The earlier rc3 statement that macOS
Evaluate values differ by up to 1.4 × 10⁻⁶ Å in LRMSD (`examples/expected_output/README.md`) was not re-measured
here.

## 3. PROPOSAL - NOT ADOPTED: a numerical tolerance policy for cross-platform parity

This is a proposal for the owner. It is **not adopted**, nothing in the code or tests applies it, and macOS stays
"not fully qualified" until the owner decides. Linux x86-64 stays the bit-exact reference platform.

**P1. Outputs that must be exact on every platform.** Equality of value and type, no tolerance:
- counts of every kind (contacts, structures, runs, positions, groups, evidence records, files);
- residue, nucleotide and contact lists, protein surfaces, binding-proposal memberships and representatives;
- categorical results: statuses (`SCORED`, `NO_VALUE`, `COMPUTED_BY_REPORT`, `NOT_COMPUTED`, `VALID`, ...),
  DockQ class, refusals and their reasons, exit codes, menu availability, labels, verdicts;
- identifiers and hashes: evidence IDs, input SHA-256, frozen-source SHA-256;
- values that are ratios of integer counts and computed by one division of exactly summed integers (for example
  surface agreement, contact-register agreement, fnat, contact frequencies);
- every **printed** value (summary text, HTML tables, Methods drafts, menu output) at its printed precision.

**P2. Outputs that may differ within a stated tolerance.** Unrounded floats produced by coordinate linear algebra:
superpositions, RMSDs, the RNA pose difference, iRMSD, LRMSD, unrounded DockQ, and statistics derived from them
(for example medians of pose differences). Proposed rule for these fields, identified by JSON pointer in a frozen
list, against the reference-platform value `r`:

    |x − r| <= max(1e-9 × |r|, 1e-12 Å)

This allows differences only beyond the **9th significant digit**. The observed macOS difference
(relative 4.1 × 10⁻¹⁵, at the 15th significant digit) is about 250,000 times smaller than the limit. Evaluate's
existing frozen portable self-test profile (10⁻⁵ Å, rc3) is unchanged by this proposal; it covers Evaluate's
own regression fixtures only.

**P3. Boundary rule.** A P2 value whose tolerance interval contains a rounding boundary of its printed precision, or
a decision threshold (for example the register cuts 0.3, 0.5 and 0.7 that define interface hypotheses, or DockQ
class boundaries), is reported as **BOUNDARY**, not as a pass. The P1 outputs that depend on it must still be
identical. A BOUNDARY needs a human decision.

**P4. How it would be applied (not implemented).** A platform-parity test would compare P1 fields exactly and P2
fields with the rule above, would name every field it compared under tolerance, and would print the largest
observed difference in ULP and in significant digits. The tolerance list and limits would be frozen in a record
before the first macOS qualification run that uses them. The existing exact test would stay as the Linux reference
check.

**What adoption would change.** Under P1 to P3, `test_report_numbers_equal_the_rc3_expected_output` would pass on
macOS: every P1 field is identical and the single P2 field differs by 4.1 × 10⁻¹⁵ relative, far from any printed
rounding boundary (0.957 at three decimals). A complete macOS qualification would also need the scipy pin fixed and
the full suite run on macOS under the adopted policy.
