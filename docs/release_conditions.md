# Release status (RNPLens 0.4)

What is established for this source tree, and which qualifications have not been performed. Nothing here claims
a qualification, approval or publication that has not happened.

| item | status |
|---|---|
| Public releases | 0.4.0 (with RNPLens Assistant 0.1.0): Git tag `v0.4.0`, commit `859d0c09cd11f03166a3a2fceac1edc073cb29f7`, public on GitHub since 2026-10-31. 0.4.1 (with Assistant 0.1.1): this version; corrections to documentation, continuous integration and tests; no computation changed |
| Software DOI | none issued |
| Licence | MIT for the core toolkit and the optional Assistant ([LICENSE](../LICENSE), `assistant/LICENSE`); copyright: The RNPLens authors |
| Authorship and affiliations | recorded in `CITATION.cff` and both `pyproject.toml` files; ORCIDs are not recorded |
| Bundled data | origin, terms, checksum and attribution of every bundled data file in [examples/DATA_PROVENANCE.tsv](../examples/DATA_PROVENANCE.tsv); summary in [example_data_provenance.md](example_data_provenance.md) |
| Live qualification of the Assistant | not performed: no live Codex call has been qualified for RNPLens 0.4 |
| Sealed evaluation of the Assistant | not performed for the released implementation: a sealed-evaluation protocol exists for an earlier, frozen assistant (`f998830`, `assistant/evaluation/`); no result of it is reported here, and it would not qualify the released 0.1.0 implementation |
| Manual visual checks of the viewer | partially performed: basic display and interaction confirmed by the owner on macOS (2026-10-18); switching between binding-proposal representatives and offline use not yet confirmed by a person; automatically tested |
| Diagnose (user-facing) | blocked by design in 0.4, pending re-qualification under the corrected residue correspondence |
| Evaluate four-axis geometry | blocked by design in 0.4, for the same reason |
