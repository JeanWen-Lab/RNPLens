"""RNPLens Assistant (bounded manuscript companion, gate-1 development version).

A natural-language front end over qualified RNPLens functions. The language model proposes a plan and drafts typed
statements; deterministic code checks the plan against the tool registry, executes qualified RNPLens commands inside a
path allowlist, records every measurement in an evidence store, renders every number from that store, and checks the
draft before an answer is accepted. Diagnose and Evaluate's four-axis geometry route are not available in this
version.
"""
__version__ = "0.1.0.dev0"
