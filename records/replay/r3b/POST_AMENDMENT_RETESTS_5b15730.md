# Post-amendment retests at 5b15730 (contracts v1 and v2, Amendment 2)

Branch `track/replay-r3b`, started from integration HEAD `66d186c455f52568c920616c1e7400b0d5d5a921`. No model call was
made. No pinned file and nothing in `LIVE_QUALIFICATION_v1/` was edited.

## Sequence

1. **`66d186c`, frozen retests (integrator run): v1 FAIL 0/4, v2 FAIL 0/6.** Recorded as found in
   `retest/results_66d186c/` and `v2/results_66d186c/` (commit `eef563e`).
   - In every case, the only false criterion is (ii), through `evidence_hash_recomputation_equal`.
   - **Cause, confirmed from the records.** `r3b/confirm_evidence_definition.py` checked the 26 follow-up records of
     those trees; its output is `r3b/evidence_definition_66d186c.json`. All 26 declare `rnplens.followup.evidence.2`.
     The tracer's definition-1 recomputation equals 0 of 26. Recomputation under the declared definition equals 26 of
     26, and each plan carries the same hash.
   - **Count.** The checks list 32 entries; the 4 v2 first trees are counted in both of their pairs. The distinct
     records are 26: v1 has 4 cases x 2 runs x `fu_0001`, and v2 has 3 cases x 3 trees x `fu_0001`/`fu_0002`. The
     integrator's message gave 20.
2. **Amendment 2 to both contracts** (commit `5b15730`, before any re-run). It was written after observing the
   failure. The checker recomputes each follow-up evidence hash under the record's `evidence_hash_version`; an absent
   field means definition 1, with the inline rule unchanged. Nothing else changes. The tracer
   `trace_replay_diffs.py` goes from `2fa45548…` to `67ffb447…`, and both FROZEN lists were updated and verified.
3. **Post-amendment retests at `5b15730`**, on karyon, in new roots, each run once. The results are below.

## v1 post-amendment retest: **PASS** (4/4)

| case | verdict | check |
|---|---|---|
| 1VTM | PASS | PASS: canonical 28/28 files, 28 byte-identical; scientific: 55 differing files, 0 not volatile, unpaired 0/0 |
| 7K9D | PASS | PASS: canonical 27/27 files, 27 byte-identical; scientific: 51 differing files, 0 not volatile, unpaired 0/0 |
| 2JEA | PASS | PASS: canonical 28/28 files, 28 byte-identical; scientific: 54 differing files, 0 not volatile, unpaired 0/0 |
| 2Q66 | PASS | PASS: canonical 28/28 files, 28 byte-identical; scientific: 53 differing files, 0 not volatile, unpaired 0/0 |

Evidence-hash checks: 8 of 8 equal.

## v2 post-amendment retest: **FAIL** (5 of 6 pairs pass)

| case | pair | verdict | check |
|---|---|---|---|
| 2QQP | first_vs_second | FAIL | FAIL: promised 121/121 (61 projections), 121 byte-identical; missing projections 0/0; scientific: 81 differing, 1 not volatile, unpaired 0/0 |
| 2QQP | first_vs_moved | PASS | PASS: promised 121/121 (61 projections), 121 byte-identical; missing projections 0/0; scientific: 15 differing, 0 not volatile, unpaired 0/0; moved: 0 promised / 33 non-promised files reference the original root |
| 2XGJ | first_vs_second | PASS | PASS: promised 117/117 (57 projections), 117 byte-identical; missing projections 0/0; scientific: 81 differing, 0 not volatile, unpaired 0/0 |
| 2XGJ | first_vs_moved | PASS | PASS: promised 117/117 (57 projections), 117 byte-identical; missing projections 0/0; scientific: 15 differing, 0 not volatile, unpaired 0/0; moved: 0 promised / 32 non-promised files reference the original root |
| 24BR | first_vs_second | PASS | PASS: promised 117/117 (57 projections), 117 byte-identical; missing projections 0/0; scientific: 81 differing, 0 not volatile, unpaired 0/0 |
| 24BR | first_vs_moved | PASS | PASS: promised 117/117 (57 projections), 117 byte-identical; missing projections 0/0; scientific: 15 differing, 0 not volatile, unpaired 0/0; moved: 0 promised / 32 non-promised files reference the original root |

Evidence-hash checks: 24 of 24 equal. **Amendment 2 removed the failure it addressed.**

**The remaining failure is new and unrelated to the evidence hash.** In 2QQP first vs second, criterion (ii) fails on one
file, `logs/10_explain_evidence.log`. The verdict is `CONTENT`: 2 `TEXT_CONTENT` lines and 1 hash line that resolves
as volatile. Both logs contain the same lines, but in a different order:
- `rnplens explain evidence` prints its two `  written: …explain_evidence_c06b1267.json/.txt` lines to stderr
  (`rnplens/evidence_query.py`, line 844) and the body to stdout.
- The step runner appends both to one log (`>> log 2>&1`).
- In the first tree the `written:` lines come right after the command line; in the second they come last.
- The written files themselves agree: their projections are byte-identical.

**The order is deterministic. It is not a timing race.** CPython block-buffers a redirected stdout in 8192-byte
blocks, and stderr is written at once:
- if the stdout body is 8192 bytes or less, it is flushed at exit, after the stderr lines;
- if it is longer, a block is flushed first.

The body holds absolute paths, so its length depends on the location. For 2QQP at this root:
- the first tree's body is 8142 bytes, so the `written:` lines come early;
- the second tree's body (`second_copy_…`, a longer path) is 8262 bytes, so they come late.

Earlier 2QQP runs had shorter roots and stayed below 8192 bytes in both trees. That is why the effect was not seen
before. `r3b/explain_log_order.py`, with output `r3b/explain_log_order.json`, checks this on all 27
`10_explain_evidence.log` files of the 5b15730, 66d186c and 3df760d v2 runs: the order equals
(body ≤ 8192 bytes) in every one. (The v1 retest has no such step.)

**What this means.**
- The failure stands as a failure under the amended rule; this run is not repeated to change it.
- It is a location dependence of line order in a raw step log. No scientific value is involved.
- It could be removed in two ways, each needing your decision and, for the contract, a further numbered amendment
  before a re-run:
  1. a code change, so that `rnplens explain` writes the `written:` lines to stdout or flushes stdout before them;
  2. a contract rule that compares step logs as unordered sets of lines.
- Neither was made here.

## Earlier records unchanged

The step-D v1 PASS at `891aeaf`, the v2 PASS at `3df760d`, the `589485b` repeats and the FAILED demo-2 check are
unchanged, as are the `66d186c` results as found.

## Test suites at `5b15730`

| where | passed | failed | skipped |
|---|---|---|---|
| local (macOS) | 685 | 0 | 27 |
| karyon (track/replay-r3b checkout) | 700 | 0 | 12 |

These totals include the new test `tests/test_portability.py::test_tracer_recomputes_under_the_declared_definition`.
The 21/23 live-qualification failures of round 3 are gone, because Amendment 5 (`66d186c`) re-pinned `followup.py`.
