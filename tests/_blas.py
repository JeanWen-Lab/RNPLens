"""The OpenBLAS kernel numpy uses, and whether it is one of the kernels verified to reproduce the frozen reference
values bit for bit (records/release/BLAS_KERNEL_NUMERICAL_DIFFERENCE.md).

On Linux x86-64, OpenBLAS selects its kernel from the CPU (or from ``OPENBLAS_CORETYPE``). The frozen reference
values were produced with the Cooperlake kernel. Cooperlake and SkylakeX reproduce them bit for bit; the AVX2
kernels (Haswell, Zen) give last-digit differences within the portable profile. Bit-exact assertions therefore
apply only where a reference kernel is in use, and the portable-profile assertions apply everywhere.
"""
import ctypes
import glob
import os
import platform

import numpy

#: kernels verified on the reference host (2026-10-31) to reproduce every frozen reference value bit for bit
REFERENCE_KERNELS = ("Cooperlake", "SkylakeX")


def openblas_core():
    """Name of the OpenBLAS kernel in use (for example ``"SkylakeX"``), or None if numpy does not use OpenBLAS."""
    d = os.path.dirname(numpy.__file__)
    libs = sorted(glob.glob(os.path.join(d, os.pardir, "numpy.libs", "libopenblas*"))
                  + glob.glob(os.path.join(d, ".dylibs", "libopenblas*")))
    for path in libs:
        try:
            lib = ctypes.CDLL(path)
        except OSError:
            continue
        for symbol in ("openblas_get_corename64_", "openblas_get_corename"):
            f = getattr(lib, symbol, None)
            if f is not None:
                f.restype = ctypes.c_char_p
                return f().decode()
    return None


def bit_exact_expected():
    """True where the frozen reference values are expected to be reproduced bit for bit."""
    return platform.system() == "Linux" and platform.machine() == "x86_64" and openblas_core() in REFERENCE_KERNELS
