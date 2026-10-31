# Numerical difference between OpenBLAS kernels on Linux x86-64 (2026-10-31)

New record, written for the review branch `docs/public-revision-2026-10-31`. No frozen record was changed.

## Finding

On Linux x86-64, numpy's bundled OpenBLAS (numpy 1.26.4, `libopenblas64_p-r0-0cf96a72.3.23.dev.so`) selects its
compute kernel from the CPU at run time; `OPENBLAS_CORETYPE` overrides the choice. The frozen reference values were
produced on the reference host (AMD EPYC 9555, glibc 2.43, CPython 3.11.15), where OpenBLAS selects **Cooperlake**.

GitHub's Linux runners have varying CPUs. On runners whose OpenBLAS kernel is not a reference kernel, the
reference-profile self-test (bit-exact) fails and two tests that assumed "Linux x86-64 means bit-exact" fail. The
portable-profile self-test passes. The failures therefore depended on which hardware a CI job ran on.

## Measurements on the reference host (forcing the kernel with `OPENBLAS_CORETYPE`)

| Kernel | Evaluate reference profile (bit-exact) | Evaluate unrounded floats bit-exact | Evaluate exactly-required checks | Report values bit-identical | Portable-profile self-test |
|---|---|---|---|---|---|
| Cooperlake (automatic choice) | PASS 213/213 | 57/57 | 172/172 | 296/296 | PASS |
| SkylakeX | PASS 213/213 | 57/57 | 172/172 | 296/296 | PASS |
| Haswell (AVX2) | FAIL (exit 3) | 30/57 | 172/172 | 295/296 (max deviation 2.2 × 10⁻¹⁶) | PASS |
| Zen (AVX2) | FAIL (exit 3) | 30/57 | 172/172 | 295/296 | PASS |

The largest Evaluate deviation under the AVX2 kernels was 3.88 × 10⁻⁶ Å (an LRMSD of the `partial_reference`
fixture), against the frozen portable tolerance of 10⁻⁵ Å. Every rounded value, status, class, count and label was
identical, and so was every printed summary line (for example `DockQ 0.936 [high] fnat 0.927 iRMSD 0.434 A
LRMSD 1.780 A`).

With the Haswell kernel, the core test suite gave 711 passed and 2 failed:
- `tests/test_geometry_blocked.py::test_dockq_family_is_unchanged`;
- `tests/test_qa_selftest_out_geometry.py::test_evaluate_selftest_out_writes_no_geometry_value`.

Both asserted bit-exactness for any Linux x86-64 machine. No other test depends on the kernel.

## Consequence

- Bit-exact reproduction of the frozen reference values is established on Linux x86-64 with the **Cooperlake**
  and **SkylakeX** kernels. With other kernels, the frozen portable profile applies. This mirrors macOS arm64
  (`MACOS_NUMERICAL_DIFFERENCE.md`).
- The two tests now assert bit-exactness only where a reference kernel is in use (`tests/_blas.py`). They keep
  every portable-profile assertion and the requirement that the public wrapper returns the frozen self-test's own
  exit code.
- The CI workflow selects SkylakeX on runners whose CPU supports AVX-512, so that the bit-exact checks run there,
  and records each runner's CPU and kernel.
- No computation, tolerance or frozen file changed.
