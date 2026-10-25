"""Environment for the Diagnose contract checks (configuration only; no check is altered).

The original 0.2.1 checks ran with the project's frozen ``score_decomp`` on ``sys.path`` and with the
reference distributions next to the package directory. In the toolkit, ``prepare()`` supplies the same frozen
``score_decomp`` from rnpbench-core and points ``RNPD_REFERENCE`` at the distributions shipped inside the
installed package. Nothing else is configured.
"""
from rnpbench_diagnose._toolkit import prepare

prepare()
