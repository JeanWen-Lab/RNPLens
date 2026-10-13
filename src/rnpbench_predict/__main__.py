"""``python -m rnpbench_predict`` (compatibility) runs the RNPBench Report command line unchanged."""
import sys

from rnpbench_report.cli import main

sys.exit(main())
