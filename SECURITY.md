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

Security fixes are made on the latest release of the 0.4 series (the toolkit `rnplens` 0.4.x and the optional
`rnplens-assistant` 0.1.x). Earlier release candidates (`0.2.0rcN`, `0.4.0-rcN`) are not supported.

The optional Assistant runs a language-model process inside an operating-system jail (bubblewrap on Linux,
Seatbelt on macOS). Its confinement is **not yet security-qualified** ([assistant/README.md](assistant/README.md)).
Please also report, privately, any way in which that process can read files, reach network destinations or
receive environment variables beyond what [docs/setup_and_privacy.md](docs/setup_and_privacy.md) states.

## What is already checked

The test suite includes hostile identifiers and file names (HTML escaping of Report and Diagnose pages), case
identifiers that are paths (refused), and refusal to write into existing output directories.
