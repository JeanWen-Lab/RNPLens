"""Re-export of the qualified frozen loader, which now lives in rnpbench-core.

rnpbench-evaluate 0.2 keeps no copy of the frozen scoring sources or of the loader. Every name that
engine.py, cli.py and the tests use (``load``, ``verify_sources``, ``FROZEN``, ``MANIFEST``, ``SPEC``,
``FrozenIntegrityError``, ...) is the core module's own object.
"""
from rnpbench_core.frozen_loader import *  # noqa: F401,F403
from rnpbench_core.frozen_loader import FROZEN, MANIFEST, SPEC, ORDER, FrozenIntegrityError, load, verify_sources  # noqa: F401
