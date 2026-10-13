# Component reference documentation

These files are the reference documentation of the three internally qualified components that RNPLens distributes
unchanged (RNPBench toolkit 0.2.0.dev1). They are copied verbatim, so they use the component names (RNPBench
Evaluate, RNPBench Report — formerly RNPBench Predict — and RNPBench Diagnose) and the component command forms
(`rnpbench ...`, `rnpbench-evaluate ...`, `python -m rnpbench_diagnose.cli ...`). Every component command remains
installed and works; the RNPLens equivalents are given in the user guides one level up
([evaluate.md](../evaluate.md), [report.md](../report.md), [diagnose.md](../diagnose.md)).

One edit was made to these copies: the internal build host name in `evaluate/PORTABLE_QUALIFICATION_CONTRACT.md` was replaced by "the reference build host". Where a component document describes an internal path, an internal fixture or an installation from internal
wheels, it records how the component was qualified; it is not something an RNPLens user needs.

| file | content |
|---|---|
| `evaluate/README.md`, `evaluate/TUTORIAL.md` | Evaluate overview and tutorial |
| `evaluate/PORTABLE_QUALIFICATION_CONTRACT.md` | the frozen per-quantity tolerances used off the reference platform |
| `report/README.md` | Report (formerly Predict) design, contract format, agreement definitions |
| `diagnose/README.md` | Diagnose stages, modes, frozen references, statement rules |
| `diagnose/OOS_VALIDATION_PROTOCOL.md`, `OOS_VALIDATION_RESULTS.md`, `PREREGISTRATION.json`, `CAMPAIGN_SCOPE_REVISION.md` | the preregistered out-of-sample evaluation of the protein-side disagreement statement and its results |
