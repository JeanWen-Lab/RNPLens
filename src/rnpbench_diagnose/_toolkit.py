"""Toolkit integration for RNPBench Diagnose (packaging only; no diagnostic logic).

``prepare()`` does two things before the unchanged Diagnose code runs:
  1. it supplies the frozen four-axis module ``score_decomp`` from rnpbench-core (hash-verified, the same
     bytes Evaluate uses), so Diagnose no longer needs that file on ``sys.path`` or the development host;
  2. if ``RNPD_REFERENCE`` is unset, it points it at the benchmark reference distributions shipped inside
     this package (``rnpbench_diagnose/reference/``). The unchanged code's default location is the parent of
     the package directory, which in an installed environment is site-packages itself.
"""
import os

REFERENCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference")


def prepare():
    from rnpbench_core.compat import provide_score_decomp
    prov = provide_score_decomp()
    os.environ.setdefault("RNPD_REFERENCE", REFERENCE_DIR)
    return {"score_decomp": prov, "RNPD_REFERENCE": os.environ["RNPD_REFERENCE"]}


def entry(argv=None):
    """Console entry point ``rnpbench-diagnose``: prepare, then the unchanged Diagnose command line."""
    prepare()
    from .cli import main
    return main(argv)
