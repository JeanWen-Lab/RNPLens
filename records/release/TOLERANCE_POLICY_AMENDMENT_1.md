# Tolerance Policy Amendment 1: one numerical tolerance in one rc3 parity test

**Status: APPROVED** by the owner (decision note of 17 Oct 2026, item 4: "Approve a narrowly scoped tolerance
correction, with regression testing"). This amendment adopts **only** what is written here. The broader proposal in
`records/release/MACOS_NUMERICAL_DIFFERENCE.md` section 3 (P1-P4) remains **PROPOSAL - NOT ADOPTED** for everything else.

**Commit order.** This policy text is committed on `track/release-docs-r2` **before** the test is changed. Its
SHA-256 (of the text above the line "## Results (appended after the runs)") is stated in the message of the commit
that changes the test, and the results are appended below that line afterwards, without changing the policy text.

## 1. Policy

In `tests/test_workflow_analyse.py::test_report_numbers_equal_the_rc3_expected_output` **only**:

- the field `summary.repeat_agreement.<engine>.rna_pose_difference_A` of Report's `result.json` is compared with the rc3
  expected value with an **absolute tolerance of 1e-12 A**: the test passes for this field if and only if both values
  are floats and `|got - expected| <= 1e-12`, or both are `null` (`None`);
- **every other compared value stays exact**, with equal types:
  - `contact_support`: the same 47 keys and the same values;
  - `summary.repeat_agreement`: the same engines, the same field names, and exact `surface_agreement`,
    `register_agreement` and `rna_pose_copy_permutation_capped`;
  - per-output `n_contacts`: the same list.

**Not affected by this amendment:** every other test, every byte-identity and hash check (frozen-source SHA-256,
canonical-file replay checks, run records), every count, list and categorical result, and the rc3 expected outputs,
which are not changed (`examples/expected_output/B1_report_7K9D/result.json`, sha256 `b51664dbbcbf4e198b33a0d2d5ba916c4b67a9a29570b93172277b7027868ba2`). No global
tolerance is introduced, and no frozen scientific value is modified.

## 2. Scope: which compared floats share the affected computation

The test compares four groups of values. Only one float passes through the SVD step that differs between platforms:

| compared value | how Report computes it | SVD path? | rule |
|---|---|---|---|
| `summary.repeat_agreement.BOLTZ2.rna_pose_difference_A` | `rnpbench_report.geometry.rna_pose_difference` -> `kabsch_rmsd` -> `numpy.linalg.svd` (LAPACK `dgesdd`) | **yes** | tolerance 1e-12 A |
| `summary.repeat_agreement.BOLTZ2.surface_agreement`, `register_agreement` | `geometry.weighted_jaccard` over integer occupancy maps (one division of exact sums) | no | exact |
| `summary.repeat_agreement.BOLTZ2.rna_pose_copy_permutation_capped` | boolean | no | exact |
| `contact_support` (47 values, each 0.5 or 1.0) | sums of occupancy fractions (count / number of outputs) | no | exact |
| `per_output[*].n_contacts` | integer counts | no | exact |

No other float in the compared fields is computed through the SVD, so no other field receives a tolerance.

## 3. Justification

`records/release/MACOS_NUMERICAL_DIFFERENCE.md`: on macOS arm64 the value is 0.9573833460521571 against the rc3
expected 0.957383346052161 (karyon, Linux x86-64, reproduces the expected value bit-for-bit). The difference is
3.886e-15 A (35 ULP), and its sole source is LAPACK `dgesdd` in different OpenBLAS builds (conda-forge OpenBLAS
0.3.34 on arm64 against the wheel-bundled OpenBLAS 0.3.23.dev on x86-64). With karyon's SVD factors substituted, macOS
reproduces karyon bit-for-bit, and a 60-digit recomputation shows that neither platform's value is exact (karyon -8.6
ULP, macOS -43.6 ULP).

1e-12 A is about 257 times the observed difference and many orders of magnitude below any scientifically meaningful
structural difference: the value is printed as 0.957 (summary) and 0.96 A (README). A difference of 1e-9 A or more
in this field still fails.

## 4. Regression requirement

The test module gains tests showing that, against the unchanged rc3 expected record:
- a difference of 1e-9 A in `rna_pose_difference_A` **fails**; 1e-12 A passes; a difference just above 1e-12 fails;
  a `null` against a float fails;
- a change in **any other** compared field **fails**, even by one ULP or for an equal value of another type (each
  `contact_support` value, an added or removed key, `surface_agreement` and `register_agreement` by one ULP, the
  `capped` flag, any `n_contacts`, an added or removed engine or field).

Base: `tests/test_workflow_analyse.py` at the policy commit has sha256 `bb909f05edcf63fda2b089ff1feddd6ea82d0e06778db30c299b13a62c741a1e`.

## Results (appended after the runs)

Appended after the runs, on 17 Oct 2026. The policy text above this section is unchanged since commit `defa5c7`
(sha256 of the text above the "## Results" line: `5ec1788f47f69bf7d83d85a7c00a4b03b1fa90916fc4fbce91905d240aa05cff`).

**Commit order, as recorded in git.** `defa5c7` (this policy) comes before `35257a5` (test change and regression
tests; its commit message states the policy-text sha256), and both come after `0ca9490`/`51378a4` (r2 docs and
the Diagnose block) on `track/release-docs-r2`, which is based on `b3374e4`.

**Full suite at `35257a5`** (`python -m pytest -q tests assistant/tests -p no:cacheprovider`):

| platform | where | result | the parity test |
|---|---|---|---|
| macOS arm64 (macOS 27.0.1, Python 3.11.17, conda-forge numpy 1.26.4 + OpenBLAS 0.3.34) | local clone | **630 passed, 0 failed, 19 skipped**; tree clean afterwards | passes under the amendment |
| Linux x86-64 (karyon, Python 3.11.15, PyPI numpy 1.26.4 + OpenBLAS 0.3.23.dev) | track clone `RNPLens_dev_0.4/tracks/release-docs-2/RNPLens` | **637 passed, 0 failed, 12 skipped**; tree clean afterwards | passes (bit-identical value) |

For comparison, at `b3374e4` macOS gave 604 passed, 1 failed (this test), 19 skipped (recorded figure). The r2
branch adds 13 tests for the Diagnose block and 12 regression tests for this amendment (25 in total); the macOS
total of collected tests went from 624 to 649.

**The compared value on each platform** (`records/release/macos_probe/result_deepdiff.py`, fresh analysis of the
bundled 7K9D example at `35257a5`):

| platform | `rna_pose_difference_A` | difference from the rc3 expected 0.957383346052161 | within 1e-12 A |
|---|---|---|---|
| macOS arm64 | 0.9573833460521571 | 3.886e-15 A (35 ULP) | yes |
| Linux x86-64 (karyon) | 0.957383346052161 | 0 (bit-identical) | yes |

On both platforms every other compared value was identical. Across the whole `result.json`, the only other
differences were platform, Python version, wall time and the `execution` labels written by `analyse`; the test
does not compare these.

**Regression tests (all passed on both platforms).** A pose difference of ±1e-9, ±1.1e-12, 1e-6 or 1e-3 A fails;
a `null`, `NaN`, an integer or a string in place of the value fails; ±0.9e-12 A and the observed macOS value
pass. Each of the 47 `contact_support` values changed by one ULP, changed in type or removed fails, and so does an
added key. `surface_agreement` and `register_agreement` changed by ±1 ULP or by 1e-15 fail (no tolerance outside
the pose field). Flipping `capped`, or giving it as an integer, fails. A removed or extra field fails, as does an
added or removed engine. Each `n_contacts` changed by one, or given as a float, fails, and so does an extra output.
The rc3 expected outputs were not changed: `git diff b3374e4 -- examples/expected_output` is empty.
