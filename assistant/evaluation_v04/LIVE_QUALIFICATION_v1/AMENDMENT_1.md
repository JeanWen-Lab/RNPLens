# Amendment 1 to LIVE_QUALIFICATION_v1 (2026-10-17, Canberra): the first call's "before" reading

## Measurement

First mocked run of the suite's tests (local, macOS, fake Codex only; frozen commit `206d7d7`), 35 tests: 15 failed.
Fourteen failures share one stop: every first call was refused before sending with
`USAGE_UNREADABLE: pre-call reading: no rate-limit snapshot in the Codex session log` (for example
`test_privacy_gate_refuses_before_sending` stopped with USAGE_UNREADABLE instead of PRIVACY_GATE). No fake call was
made in those runs. The fifteenth failure (`test_refuses_bad_run_id_existing_run_lock_ledger_and_unacknowledged_abort`)
is a defect of the test itself (it creates the run folder it then asserts to be absent) and was fixed in the test;
tests are not frozen.

## Clause broken, and why the original was wrong

DESIGN.md, Guards: "before: the latest reading, for call 1 the owner's stated values". `Guard.__init__` used the bare
`baseline` record (`balance`, `weekly_used_percent`, `source`) as the first "before" reading. `reading_problems`
requires `rate_limits_present` and `model_returned`, so the owner's stated values could never pass and no live call
could ever be made. This is my error in the driver; the guard rule itself is unchanged.

## Replacement

`run_live.py`, `Guard.__init__`: when the run has no call yet, the first "before" reading is the baseline with
`rate_limits_present=True`, `windows={}` and `model_returned=gpt-6.1-sol` (the same shape as `baseline_reading`).
Five lines.

## Unchanged

DESIGN.md, scenarios.json, score_live.py, privacy.py, fake_codex.py, the decision rule, the budget, every guard
threshold, and the premise check. The original hash of run_live.py was
239a0fb68a37af548522b8c8271da6f486d7479ee1b05a6fdc19e5eed5be6a3d. The tests are re-run in full after this amendment
is committed.
