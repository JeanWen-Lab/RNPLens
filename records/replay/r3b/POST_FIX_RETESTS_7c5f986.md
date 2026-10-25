# Post-fix retests at 7c5f986 (after the 5b15730 v2 failure)

Branch `track/replay-r3b`. No model call was made. No pinned file, nothing in `LIVE_QUALIFICATION_v1/`, no frozen rc3
component and no frozen harness file was edited.

## The 5b15730 result, as found

The v2 post-amendment retest at `5b15730` gave **FAIL, 5/6**. It is recorded in `v2/results_postam_5b15730/` (commit
`6a70bfb`) and is unchanged. Its analysis is in `r3b/POST_AMENDMENT_RETESTS_5b15730.md`.

## The fix (commit `7c5f986`; integrator decision: fix the code, not the contract)

- **`src/rnplens/ordered_output.py` (new).** `install()` makes stdout and stderr line-buffered and replaces
  `sys.stderr` with a proxy. The proxy flushes stdout before every stderr write, and flushes itself after. A combined
  log (`cmd >> log 2>&1`) therefore keeps the order in which the program wrote, whatever the text lengths. Nothing
  written to either stream changes.
- **Installed only by the process entry points:**
  - `rnplens.cli.main` when it is called without `argv`. This covers the console script `rnplens` and
    `python -m rnplens`, which the step runners use.
  - `rnplens_assistant.__main__.main` when it is called without `argv`, i.e. `python -m rnplens_assistant`.
  - In-process callers that pass `argv` (tests) are unaffected.
- **Files changed:** `src/rnplens/ordered_output.py` (new), `src/rnplens/cli.py` (+3 lines),
  `assistant/rnplens_assistant/__main__.py` (+3 lines). None of them is pinned.
- **`tests/test_output_order.py` (new, 4 tests).**
  - The boundary case: it builds the test-fixture case twice, under a short root and under a root long enough to
    move the `explain evidence` stdout body from at most 8192 bytes to more than 8192 bytes (calibrated, and asserted
    to straddle). It requires the combined logs to be identical after masking roots and SHA-256 values.
  - **Before the fix this test failed:** the short-root log began with the `written:` lines and the long-root log
    with the body. After the fix it passes.
  - The other tests check program order through the helper (a 16 KB stdout body, then stderr, then stdout, including
    a partial stderr line) and check that both entry points install it.

## Audit of the other runner commands

`r3b/output_stream_audit.py` has two parts:
- a static count of stdout and stderr writes per module;
- every runner command run on the test fixture with separate pipes.

Records: `r3b/output_stream_audit_local.json` and `r3b/output_stream_audit_karyon.json`.
- **Commands checked:** update, clarify, region, export-methods, explain structures / evidence / region_mapping,
  view, group, assist menu C (local follow-up), replay-followup, relink `--dry-run`, update `--report`,
  `--versions` and `--status`.
- **Which commands write both streams.** In normal runs only the three `explain` queries do; that is the pattern of
  the 5b15730 failure. Others write to stderr only on refusals. For example, `view` exits 2 on this fixture, a
  structure with two protein chains, and writes nothing to stdout.
- **All 15 commands ran with the ordered output installed by their entry point**, on both machines. This includes
  the paths through pinned files (`src/rnplens/assist.py`, `assistant/rnplens_assistant/followup.py`,
  `replay.py`); they are covered without being edited.
- **Pinned files that would need a re-pin: none.**
- **Not routed through an entry point:** the frozen v2 harness script `demos/lib/followup_scripted.py`
  (step 14_followup_SCRIPTED). It writes to stdout only, and the follow-up code it runs writes nothing to stderr, so
  the pattern does not occur. It is listed here and was not edited.

## Post-fix retests at 7c5f986 (karyon, new roots, each run once)

### v1 retest (Amendment-2 rule): PASS

| case | verdict | check |
|---|---|---|
| 1VTM | PASS | PASS: canonical 28/28 files, 28 byte-identical; scientific: 54 differing files, 0 not volatile, unpaired 0/0 |
| 7K9D | PASS | PASS: canonical 27/27 files, 27 byte-identical; scientific: 51 differing files, 0 not volatile, unpaired 0/0 |
| 2JEA | PASS | PASS: canonical 28/28 files, 28 byte-identical; scientific: 54 differing files, 0 not volatile, unpaired 0/0 |
| 2Q66 | PASS | PASS: canonical 28/28 files, 28 byte-identical; scientific: 55 differing files, 0 not volatile, unpaired 0/0 |

Evidence-hash checks: 8 of 8 equal.

### v2 retest (Amendment-2 rule): PASS

| case | pair | verdict | check |
|---|---|---|---|
| 2QQP | first_vs_second | PASS | PASS: promised 121/121 (61 projections), 121 byte-identical; missing projections 0/0; scientific: 81 differing, 0 not volatile, unpaired 0/0 |
| 2QQP | first_vs_moved | PASS | PASS: promised 121/121 (61 projections), 121 byte-identical; missing projections 0/0; scientific: 15 differing, 0 not volatile, unpaired 0/0; moved: 0 promised / 33 non-promised files reference the original root |
| 2XGJ | first_vs_second | PASS | PASS: promised 117/117 (57 projections), 117 byte-identical; missing projections 0/0; scientific: 81 differing, 0 not volatile, unpaired 0/0 |
| 2XGJ | first_vs_moved | PASS | PASS: promised 117/117 (57 projections), 117 byte-identical; missing projections 0/0; scientific: 15 differing, 0 not volatile, unpaired 0/0; moved: 0 promised / 32 non-promised files reference the original root |
| 24BR | first_vs_second | PASS | PASS: promised 117/117 (57 projections), 117 byte-identical; missing projections 0/0; scientific: 82 differing, 0 not volatile, unpaired 0/0 |
| 24BR | first_vs_moved | PASS | PASS: promised 117/117 (57 projections), 117 byte-identical; missing projections 0/0; scientific: 15 differing, 0 not volatile, unpaired 0/0; moved: 0 promised / 32 non-promised files reference the original root |

Evidence-hash checks: 24 of 24 equal.

**This retest crossed the 8192-byte boundary again, and the order held.** Body sizes of `logs/10_explain_evidence.log`
(`r3b/explain_log_order_postfix_7c5f986.json`):

| tree | stdout body bytes | `written:` lines |
|---|---|---|
| `24BR/first_20261017T092102Z` | 11152 | late (program order) |
| `24BR/second_copy_20261017T092322Z` | 11314 | late (program order) |
| `2QQP/first_20261017T092051Z` | 8162 | late (program order) |
| `2QQP/second_copy_20261017T092311Z` | 8282 | late (program order) |
| `2XGJ/first_20261017T092055Z` | 11152 | late (program order) |
| `2XGJ/second_copy_20261017T092316Z` | 11314 | late (program order) |
| `moved_elsewhere/24BR_copy_20261017T092102Z` | 11152 | late (program order) |
| `moved_elsewhere/2QQP_copy_20261017T092051Z` | 8162 | late (program order) |
| `moved_elsewhere/2XGJ_copy_20261017T092055Z` | 11152 | late (program order) |

The 2QQP first tree (8162 bytes) and second tree (8282 bytes) lie on either side of 8192, as in the 5b15730 failure.
Both logs now carry the `written:` lines in program order. The diagnostic's earlier rule, order = (body ≤ 8192),
therefore no longer holds, which is the intended effect of the fix.

### PORTABILITY_TEST_v1 (unchanged frozen harness): PASS

| case | verdict | check |
|---|---|---|
| 2QQP | PASS | 2QQP PASS: 80 checks, 0 failed |
| 2XGJ | PASS | 2XGJ PASS: 80 checks, 0 failed |

Its 10 frozen files were verified OK on karyon at this commit just before the run.

## Test suites at 7c5f986

| where | passed | failed | skipped |
|---|---|---|---|
| local (macOS) | 689 | 0 | 27 |
| karyon (track/replay-r3b checkout) | 704 | 0 | 12 |

The +4 tests on each machine are `tests/test_output_order.py`. `rnplens doctor` reports
`Qualified components READY; all 8 frozen sources match their pinned SHA-256`.

## Records unchanged

The step-D v1 PASS at `891aeaf`, the v2 PASS at `3df760d`, the `589485b` repeats and the FAILED demo-2 check are
unchanged. So are the `66d186c` results as found and the `5b15730` post-amendment results (v1 PASS 4/4, v2 FAIL 5/6).
