"""RNPBench Evaluate: the frozen RNPBench evaluation rules as a command-line tool.

Reference-based evaluation of a predicted protein-RNA complex against an experimental structure.
Development prototype; not yet a released or archived package.
"""
__version__ = "0.2.0.dev1"


# RNPLens 0.4: this package's own command line refuses verbs that would show a BLOCKED result (exit 5); importing
# the package from Python code is unaffected. See rnplens/legacy_routes.py and docs/capabilities.md.
from rnplens.legacy_routes import refuse_blocked_route as _refuse_blocked_route
_refuse_blocked_route()
del _refuse_blocked_route
