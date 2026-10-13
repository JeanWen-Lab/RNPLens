"""RNPBench Core: shared infrastructure for the RNPBench toolkit. It contains no scientific logic of its own.

Contents
  frozen/            the eight frozen RNPBench scoring sources, byte-for-byte, pinned in FROZEN_SOURCES.json
  frozen_loader.py   the qualified loader (unchanged from rnpbench-evaluate 0.1.1); it executes only the needed
                     definitions of the frozen sources and refuses if any host-dependent statement would run
  compat.py          supplies the frozen four-axis module to tools that import it as ``score_decomp``
  provenance.py      versions and hashes of the installed toolkit components

The DockQ route and the four-axis geometry route remain separate frozen routes; this package does not combine
them, and nothing here assigns a value to an unscoreable output.
"""
__version__ = "0.2.0.dev1"
