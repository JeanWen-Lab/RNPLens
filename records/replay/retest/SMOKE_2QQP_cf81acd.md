# Smoke test of the frozen retest workflow (not part of the retest)

- **Purpose.** Check that every step of `retest_case.sh` reaches its expected exit code before the workflow is frozen.
- **Target.** 2QQP: development target, stress cohort, **not** a retest case.
- **Code.** Unchanged `cf81acd`, on karyon, 16 Oct 2026 about 20:04 UTC, in `scratch_agent/v04/replay-2/smoke/`.
- **Inputs.** `prepare_inputs.sh ... smoke`; `prepared.sha256` has sha256 `81f16741...`.

| run | steps 00-13 | result |
|---|---|---|
| `2QQP_a_20261016T200416Z` | every exit code as expected (01 and 02: 3; all others: 0) | COMPLETE |
| `2QQP_second_20261016T200423Z` | every exit code as expected | COMPLETE |

`check_pair.py` at `cf81acd` (`check.json` sha256 `0199d6b9...`) returned **FAIL**:
- (0) completed: true;
- (i) canonical byte-identical: **false**. 9 of 28 canonical files were byte-identical: `region_contacts.tsv`, both
  `contacts_by_output.json`, two `update_report.html` and four construct FASTA files. These differed: `HEAD`, 7 state
  versions, 4 `index.json`, 3 `update_report.json` and one `update_report.html`. The 3 + 3 cache entries were named by
  different keys;
- (ii) scientific equal: true. Of 112 files, 55 differed, all volatile-only, and both evidence-hash recomputations were
  equal.

This is the behaviour the remediation must change. It is not evidence for the retest. The case and the two runs are
not reused.
