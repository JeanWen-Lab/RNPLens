# Post-implementation smoke tests on 2QQP (not part of the retest)

These are development checks of the step-C code with the frozen workflow and checker, on the development target 2QQP,
which is **not** a retest case. They ran on karyon on 16-17 Oct 2026, in `scratch_agent/v04/replay-2/smoke2/` and
`smoke3/`, using the inputs of the first smoke. They come before any retest run.

| smoke | code | (0) completed | (i) canonical byte-identical | (ii) scientific equal | verdict |
|---|---|---|---|---|---|
| smoke2 | `98f8ba9` | yes | **yes**, 28/28 | **no** | FAIL |
| smoke3 | `01e0466` | yes | yes, 28/28 | yes: 53 differing non-canonical files, all volatile-only | PASS |

In smoke2, 17 sidecar files carried the writing process id (`execution.pid`). The frozen comparator has no class for
that number, so it counts it as CONTENT. The id adds nothing to the record and was removed in `01e0466`; the contract
did not change.

At `cf81acd` (first smoke, `SMOKE_2QQP_cf81acd.md`), only 9 of 28 canonical files were byte-identical.

The full test suite at `01e0466` on karyon: 558 passed, 12 skipped.
