"""RNPBench toolkit meta-package: the unified ``rnpbench`` command over three separately qualified tools.

  rnpbench evaluate  run|validate|selftest|provenance   reference-based structural accuracy (RNPBench Evaluate)
  rnpbench report    run|validate|selftest              reference-free, descriptive cross-engine interface agreement (RNPBench Report)
  rnpbench diagnose  run|preflight|validity|selftest    reference-free validity and component-disagreement diagnostics (RNPBench Diagnose)
  rnpbench toolkit   version|provenance|selftest        the installed components, their hashes, every tool's self-test

This package contains dispatch only. Each verb calls the tool's own, unchanged command line; nothing is
computed here and no output of one tool is combined with another's.
"""
__version__ = "0.2.0.dev1"
