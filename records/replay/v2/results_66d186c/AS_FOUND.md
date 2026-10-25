# Retest v2 (DETERMINISM_CONTRACT_v2, records/replay/v2/run_retest_v2.sh) at 66d186c: as found

- **Result: FAIL.** 0 passed out of 3 cases x 2 pairs; see `OVERALL` and `verdicts.tsv`.
- **Run by the integrator** at integration HEAD `66d186c455f52568c920616c1e7400b0d5d5a921`, on karyon.
- **Copied unchanged** from `scratch_agent/v04/final_66d186c/replay_v2` (read only):
  - every top-level file of the run root;
  - every tree's `logs/`;
  - not copied: the trees themselves, `prepared/` and `tmp_*`.
- **These files are not changed after this commit.**

**Only failing criterion: `ii_scientific_equal`, in every case.**
- `scientific.evidence_hash_recomputation_equal` is false for every follow-up record.
- Criteria (0) and the byte-identity criteria hold, projection coverage holds where it applies, and no file is
  non-volatile or unpaired.

**Cause, confirmed from the records.** See `records/replay/r3b/evidence_definition_66d186c.json` and
`records/replay/r3b/confirm_evidence_definition.py`.
- Round 3 made new follow-ups record `evidence_hash_version = rnplens.followup.evidence.2`.
- The frozen tracer `records/replay/trace_replay_diffs.py` recomputes every follow-up evidence hash with the
  definition-1 rule.
- Of the 26 follow-up records in the v1 and v2 trees:
  - all 26 declare `rnplens.followup.evidence.2`;
  - the definition-1 recomputation equals 0 of 26;
  - recomputation under the declared definition equals 26 of 26.
