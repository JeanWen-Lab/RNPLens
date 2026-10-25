# Security policy

RNPLens reads structure files and JSON supplied by its users and writes JSON, text and HTML reports. Please report
any way in which an input file, identifier or label can

- write or overwrite a file outside the chosen output directory,
- overwrite an existing result (RNPLens is designed never to do this),
- inject markup or script into a generated HTML report, or
- crash a parser in a way that could be exploited,

by **private vulnerability report** through this repository's GitHub Security tab ("Report a vulnerability"),
not through a public issue. Include the RNPLens version (`rnplens --version`), the command, and a minimal input
that reproduces the problem.

## Supported versions

Security fixes are made on the latest release. RNPLens is a release candidate (`0.2.0rcN`) until the first
release.

## What is already checked

The test suite includes hostile identifiers and file names (HTML escaping of Report and Diagnose pages), case
identifiers that are paths (refused), and refusal to write into existing output directories.
