# Release conditions (RNPLens 0.4 release candidate)

The release manifest stays **FAIL** until each condition below is resolved by the owner. None is claimed as resolved
here. The verifier is `tools/release_manifest.py` ([release_manifest.md](release_manifest.md)).

| condition | status | what is needed |
|---|---|---|
| Institutional IP clearance (ANU) | OPEN | written clearance for releasing the code, records and bundled data |
| Licence | CLOSED | MIT, decided by the project owner for both the core toolkit and the Assistant. The copyright line reads "The RNPLens authors"; institutional IP clearance is tracked separately above and is not a gate on this prerelease. |
| Authorship and affiliations | CLOSED | author list and affiliations supplied by the project owner from the authoritative manuscript and recorded in `CITATION.cff` and both `pyproject.toml` files. ORCIDs are not yet recorded. |
| Redistribution of bundled data | OPEN | decisions listed in [example_data_provenance.md](example_data_provenance.md) (fixtures of evaluation-excluded targets 4PMI and 6E4P; values derived from RoseTTAFold2NA outputs - note the RF2NA *software* licence is settled as MIT, while rights in generated outputs remain the open part; publication of `records/`) |
| Live qualification of the Assistant | OPEN | LIVE_QUALIFICATION_v1 is prepared, not run; it needs the owner's authorisation of the Codex call budget (and Amendment 7 for the 0.4 RC re-pin of `src/rnplens/assist.py`, drafted, not applied) |
| Sealed evaluation of the Assistant | OPEN | final evaluation freeze and the frozen assistant-versus-general-agent comparison (owner gates A and B) |
| Owner visual checks of the viewer | OPEN | switching between binding-hypothesis representatives and offline operation on the owner's Mac (`MAC_REMAINING_VIEWER_CHECKS.md`) |
| Diagnose (user-facing) | BLOCKED by design in 0.4 | re-qualification under the corrected correspondence (not a release condition of 0.4; documented as blocked) |
| Evaluate four-axis geometry | BLOCKED by design in 0.4 | as above |
| Publication actions (tag, push, Zenodo deposit) | NOT AUTHORISED | explicit owner authorisation |
