# Amendment 1 to FOLLOWUP_SUITE_v1 (2026-10-16, Canberra): absolute output path in run_part1.py

## Measurement

Run 1 of Part 1 was made locally on macOS with `--out ../p1run`, a relative path. It scored 17 of 21. Its results
are kept in `FOLLOWUP_SUITE_v1_results/part1_results_run1_local.json`.

P1-13, P1-14, P1-15 and P1-16 failed, each with the recorded stop
`RuntimeError: FileNotFoundError: ... '../p1run/work/P1-1x_.../fake_jail.sh'`.

## Clause broken, and why the original was wrong

`run_part1.py` built the scenario directories, and so the fake-jail path, from `--out` as given.
`codex_llm.CodexClient.run` starts the jail with `cwd` set to the per-call directory. A relative jail path therefore
does not resolve, and the fake codex never ran. This is my error in the runner: the documented call
`--out RESULTS_DIR` accepts a relative path. It is not a defect of the follow-up module.

P1-12 (model unavailable) **passed for the wrong reason** in run 1. Its expected stop, MODEL_UNAVAILABLE, came from
the file-not-found error, not from the scripted exit 1. So its run-1 pass is not evidence.

## Replacement

`run_part1.py`, `main()`: `a.out = os.path.abspath(a.out)` before anything else runs. This is a one-line change.

## Unchanged

- every scenario and every expected fact (`scenarios_part1.json`);
- `score.py`, `fake_client.py`, `SUITE.md`, Part 2 (`scenarios_part2.json`, `run_part2.py`);
- the pass rule: all 21 must pass.

Part 1 is re-run once, in full, after this amendment is frozen. For P1-12, the run-2 record is also checked by hand
to confirm that the call error is the scripted one ("failed to connect"). That check is reported, not scored.
