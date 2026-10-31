# Software availability versus reproducibility of the study

RNPLens is the software of the accompanying study. Two different things need to be available, and they are kept
apart on purpose.

| | what it lets a reader do | where |
|---|---|---|
| **The software (this repository)** | run Evaluate's DockQ route, Report and the analysis workflows on their own predicted complexes; reproduce the bundled examples and regression references exactly | this repository, release `v0.4.0` (no DOI issued) |
| **The study's evidence** | reproduce the study's numbers, figures and tables | a separate research-data archive, not part of this repository |

## What this repository reproduces

- The behaviour of Evaluate, Report and Diagnose's internal contract checks, under frozen scoring rules whose source files are verified by SHA-256 at run
  time, on the bundled examples and regression fixtures (`rnplens selftest`, `python -m pytest`,
  `examples/run_examples.sh` against `examples/expected_output/`).
- Numerical parity of the releases with the internally qualified implementation, documented in
  [reproducibility.md](reproducibility.md).

## What it does not reproduce

- The benchmark itself: its 1,442 complexes, family-disjoint partitions, the predictions of the engines compared in the study and the score
  stores.
- The study's benchmark analyses, statistics, figures and tables, including measurements that use the four-axis
  geometry route or Diagnose, which are not available in 0.4.0, and the frozen protocols that governed them, apart
  from the validation records in [validation/](validation/) that define Diagnose's statements.
- Predictions of any engine other than the Boltz-2 examples listed in `examples/DATA_PROVENANCE.tsv`.

## Planned research-data archive

The following belong in the study's research-data archive, not in this repository. Its location, licence and
identifier will be added here when the archive exists.

- The benchmark resource: entries, partitions and cluster assignments, with the acquisition records.
- Predicted structures and score stores, where each engine's terms permit redistribution; where they do not, the
  identifiers and checksums needed to regenerate them.
- The evidence manifest and source data behind every figure and table, identified by the manuscript's evidence
  build identifier (`08a8ab3098f48716` for the current manuscript build). That identifier is not a software
  version and does not change with RNPLens releases.
- The figure and table builders and the manuscript build, with the frozen pre-registered protocols and their
  results.

## How the two are linked

The study uses RNPLens 0.4.0 (Git tag `v0.4.0`). No DOI has been issued for the software. The research-data archive
will be linked here when it exists; until then this page records the separation only.

## In brief

`rnplens selftest` reproduces the project's full reference set from the bundled public data. It is **not** a
reproduction of the private benchmark study: the RNPLens-Rank corpus, its label files and its holdouts are not in
this repository and are not published here. Users must acquire or regenerate any benchmark inputs beyond the
bundled examples. The Boltz-2 commands that produced the bundled predictions are recorded per file in
`examples/DATA_PROVENANCE.tsv`.

