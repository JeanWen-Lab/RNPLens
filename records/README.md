# Development and qualification records

This folder holds the records that document how RNPLens 0.4 was specified, tested and qualified: pre-registrations,
amendments, qualification reports, replay and determinism tests, viewer checks, platform runs and integration
reports. They are evidence, and are kept **unchanged** after they were written. Code comments, tests and documents
cite them by path, so they are not moved or edited.

Many records describe pre-release versions (`0.2.0rc*`, `0.4.0.dev0`) and the state of the work on the date they
were written. For what applies to the current release, see [docs/capabilities.md](../docs/capabilities.md),
[docs/limitations.md](../docs/limitations.md) and [docs/reproducibility.md](../docs/reproducibility.md).

| folder | content |
|---|---|
| `release/` | release-preparation records: documentation audits, the geometry-block inventory, tolerance policy, macOS numerical differences, demonstration runs |
| `replay/` | determinism contracts, replay and portability tests of managed projects |
| `viewer/` | automated visual verification of the Mol\* viewer and the nucleotide contact explorer |
| `grouping/` | specification, amendments and qualification of binding-proposal grouping |
| `native_platforms/` | Linux and macOS native-platform qualification runs and amendments |
| `v04_integration/` | integration, clean-install and demonstration plans and reports for 0.4 |
