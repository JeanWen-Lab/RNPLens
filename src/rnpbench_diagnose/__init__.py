"""RNPBench-Diagnose: reference-free diagnostics for a predicted protein-RNA complex.

What this package does
----------------------
Given candidate structures that already exist, it reports (a) whether each output is a valid, evaluable
complex, separating technical failure from structural failure, and (b) which SIDE of the complex the
candidates disagree about.

What it deliberately does not do
--------------------------------
It launches no prediction. It emits no probability of correctness. It does not attribute error to RNA
placement as something distinct from RNA shape -- that attribution was measured and did not hold, so the
API refuses it rather than reporting it weakly.

Every diagnostic statement it makes corresponds to a measured, pre-registered result; see README.md for the
correlation and interval behind each one.
"""
__version__ = "0.2.1"
LICENSED_STATEMENTS = ("protein_side", "rna_side")
REFUSED_STATEMENTS = ("placement_attribution", "probability_of_correctness", "best_engine_recommendation")


# RNPLens 0.4: this package's own command line refuses verbs that would show a BLOCKED result (exit 5); importing
# the package from Python code is unaffected. See rnplens/legacy_routes.py and docs/capabilities.md.
from rnplens.legacy_routes import refuse_blocked_route as _refuse_blocked_route
_refuse_blocked_route()
del _refuse_blocked_route
