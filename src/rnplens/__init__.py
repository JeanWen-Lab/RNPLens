"""RNPLens: evaluation and diagnostic tools for protein-RNA complex predictions.

RNPLens assesses protein-RNA complex structures that have already been predicted by other methods. It does not
predict structures. The command is ``rnplens``::

    rnplens evaluate  run | validate | selftest | provenance   reference-based structural accuracy (needs an experimental structure)
    rnplens report    run | validate | selftest                reference-free, descriptive agreement among predictions
    rnplens diagnose  run | preflight | validity | selftest    reference-free validity and candidate-disagreement diagnostics

This package contains the public command and version only. The three tools are the internally qualified
RNPBench toolkit 0.2.0.dev1 implementation, distributed unchanged as the import packages ``rnpbench_core``,
``rnpbench_evaluate``, ``rnpbench_report``, ``rnpbench_diagnose`` and ``rnpbench``;
their Python APIs are those packages' own.
"""
__version__ = "0.4.0"

# The implementation this release distributes, byte-for-byte (see docs/reproducibility.md).
IMPLEMENTATION = "qualified component set 0.2.0.dev1 (internal identifier: RNPBench toolkit 0.2.0.dev1)"
