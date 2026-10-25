# Pinned-source change in r3 and the re-pin it needs (PROPOSAL for the integrator)

Track release-docs-r3, base `589485b8e2234be92d1050a2def57fb7f82a0669`. Status: **proposal**. This track may edit
pinned sources but must not edit anything in `assistant/evaluation_v04/LIVE_QUALIFICATION_v1/`, so the re-pin
itself is left to the integrator (owner note, 17 Oct 2026: "Record a new amendment, repin changed source hashes and
rerun affected tests before any live Codex call").

## The one pinned file changed

| file | sha256 at 589485b (pinned in `scenarios.json` `pinned_sources`) | sha256 after r3 | commit | reason |
|---|---|---|---|---|
| `src/rnplens/assist.py` | `2e504d658a0dd052791bb7a0fbb1bf98f031fb6efe22989849c09988dd68955a` | `03fda9de46f1b78d9b94eb0f15207403f768192aa3b427d71d45ea1b336c4507` | `5c04c00` | owner-approved fix of the menu exit status: a blocked capability exits 5, a function's refusal or failure exits 4 (before: a raised `DiagnoseBlocked` was uncaught; a `BLOCKED` result counted as success) |

No other file listed in `pinned_sources` changed in r3. No frozen scorer source changed (`rnplens doctor`: all 8
frozen sources match their pinned SHA-256, READY).

## Effect until the re-pin

`assistant/tests/test_live_qualification.py`: 21 tests fail, every one on the freeze refusal
"pinned source changed since the freeze: src/rnplens/assist.py". Check made in a separate worktree at the r3 head
`138b7e2`: with only `src/rnplens/assist.py` restored to its 589485b content, the file passes (37 passed, 2
skipped); with the r3 file, 21 fail. The live harness therefore refuses to start, which is the intended behaviour of
the freeze while the pin is stale. No live call was made.

## Re-pin steps (integrator, after merging this and any other pinned-file change)

1. Combine with the other approved pinned-file change of this round (the relocation-dependent follow-up hash,
   another track) into one amendment record, so the live suite is re-pinned once.
2. In `assistant/evaluation_v04/LIVE_QUALIFICATION_v1/scenarios.json`, set
   `pinned_sources["src/rnplens/assist.py"]` to `03fda9de46f1b78d9b94eb0f15207403f768192aa3b427d71d45ea1b336c4507`
   (and the other track's new hash).
3. Update the `scenarios.json` row in `LIVE_QUALIFICATION_v1/FREEZE.md` to the new sha256 of `scenarios.json`.
4. Rerun `assistant/tests/test_live_qualification.py` and the full suite; verify the exact Codex payloads again
   before any live call (the menu exit status does not change a payload, but the owner requires the check).
