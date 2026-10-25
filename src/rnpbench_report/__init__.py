"""RNPBench Predict -- reference-free interpretation of protein-RNA structure predictions.

Reads only prediction outputs declared in an input contract. Opens no reference structure and computes no
accuracy. Agreement is descriptive evidence about convergence of predicted interface hypotheses; it is not a
probability of structural correctness.
"""
from .agreement import VERSION, run, write  # noqa: F401
from .contract import ContractError, SCHEMA_VERSION, load, validate  # noqa: F401
