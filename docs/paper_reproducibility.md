# Software availability versus reproducibility of the study

RNPLens accompanies a manuscript in preparation. Two different things need to be available, and they are kept
apart on purpose.

| | what it lets a reader do | where |
|---|---|---|
| **The software (this repository)** | run Evaluate, Report and Diagnose on their own predicted complexes; reproduce the bundled examples and regression references exactly | this repository and its archived release (DOI to be added at release) |
| **The study's evidence** | reproduce the numbers, figures and tables of the manuscript | a separate research-data archive (location and DOI to be added at publication) |

## What this repository reproduces

- The behaviour of the three tools, under frozen scoring rules whose source files are verified by SHA-256 at run
  time, on the bundled examples and regression fixtures (`rnplens selftest`, `python -m pytest`,
  `examples/run_examples.sh` against `examples/expected_output/`).
- Numerical parity of each release candidate with the internally qualified implementation, documented in
  [reproducibility.md](reproducibility.md).

## What it does not reproduce

- The benchmark itself: its 1,442 complexes, family-disjoint partitions, the predictions of the engines compared in the study and the score
  stores.
- The manuscript's analyses, statistics, figures and tables, and the frozen protocols that governed them, apart
  from the validation records in [validation/](validation/) that define Diagnose's statements.
- Predictions of any engine other than the Boltz-2 examples listed in `examples/DATA_PROVENANCE.tsv`.

## Planned research-data archive

The following belong in the research-data archive linked from the manuscript, not in this repository. Location,
licence and DOI will be added here when they exist.

- The benchmark resource: entries, partitions and cluster assignments, with the acquisition records.
- Predicted structures and score stores, where each engine's terms permit redistribution; where they do not, the
  identifiers and checksums needed to regenerate them.
- The evidence manifest and source data behind every figure and table, identified by the manuscript's evidence
  build identifier (`08a8ab3098f48716` for the current manuscript build). That identifier is not a software
  version and does not change with RNPLens releases.
- The figure and table builders and the manuscript build, with the frozen pre-registered protocols and their
  results.

## How the two are linked

The manuscript will cite the RNPLens release used (version and DOI) and the research-data archive (DOI). This file
will be updated with both identifiers; until then it records the separation only.

## In brief

`rnplens selftest` reproduces the project's full reference set from the bundled public data. It is **not** a
reproduction of the private benchmark study: the RNPLens-Rank corpus, its label files and its holdouts are not in
this repository and are not published here. Users must acquire or regenerate any benchmark inputs beyond the
bundled examples. The Boltz-2 commands that produced the bundled predictions are recorded per file in
`examples/DATA_PROVENANCE.tsv`.

