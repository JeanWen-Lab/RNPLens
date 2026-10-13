"""``python -m rnpbench_diagnose``: the unchanged Diagnose command line, prepared for the toolkit
(frozen four-axis code from rnpbench-core; packaged reference distributions)."""
import sys

from rnpbench_diagnose._toolkit import entry

sys.exit(entry())
