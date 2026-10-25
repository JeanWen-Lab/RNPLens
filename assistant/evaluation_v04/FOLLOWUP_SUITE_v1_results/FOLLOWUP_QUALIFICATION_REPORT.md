# Follow-up (Function 4): qualification report, FOLLOWUP_SUITE_v1 (2026-10-16, Canberra)

**Status of the capability: EXPERIMENTAL.** Part 2, the live Codex part, is frozen and has not run. No Codex or
other language-model call was made by this track.

## Timeline

1. The suite was written and frozen at 2026-10-16T12:04 UTC (23:04 AEDT), in commit `a87a0ef`, before any of it ran.
2. **Part 1, run 1** (local, macOS) scored 17 of 21. This was a runner defect: the relative `--out` left the fake
   jail unresolvable. P1-13 to P1-16 failed, and P1-12 passed for the wrong reason.
   Results: `part1_results_run1_local.json`.
3. **Amendment 1** made `--out` absolute in `run_part1.py`. No expectation changed. It was re-frozen in commit
   `def2418` before run 2.
4. **Part 1, run 2** (local, macOS, Python 3.11) scored **21 of 21**. Results: `part1_results_run2_local.json`. A
   manual check of the P1-12 record shows the scripted call error, "failed to connect to the model service".
5. **Part 1 on karyon** (Linux, Python 3.11.15, track clone at `dc9767a`) scored **21 of 21**. The frozen files are
   unchanged (FREEZE sha256 21c5ee2f…). The karyon result file is
   `RNPBench/scratch_agent/v04/followup/p1_karyon/part1_results.json`.
6. **Part 2 interlock.** `run_part2.py` without `--live` and without the confirmation variable refused with exit 3,
   created no output folder and called nothing. This was checked both locally and on karyon. Locally with `--live`,
   it also refused on the calls folder, the output folder, `doctor --agent` and the model catalog. Copy:
   `part2_interlock_refusal_local.txt`.

## What Part 1 establishes

The 21 scripted scenarios run on the bundled 7K9D example. With the scripted fake client, and with the real
`CodexClient` driving a fake codex in place of the jail, they show the following.
- An appropriate follow-up is approved, executed, traceable and replayable.
- Irrelevant follow-ups (F9), repeats (F5), circular plans (F6), blocked tools (F3), bad ids (F1), invalid arguments
  (F2) and malformed proposals (F8) are refused.
- Without consent, or after an opt-out, no client is created and no codex subprocess starts.
- A model rationale asserting correctness never reaches the answer.
- Subprocess error, timeout, usage guard and credit change each stop cleanly, with records. The credits baseline is
  unchanged.
- LLM-free execution replays to the same evidence hash, also in a moved copy of the analysis.
- An injected number (T1), an altered slot (T2) and an empty answer (T0) are detected.
- One planning round per question, the tool-call budget (F4) and confirmation before execution are enforced.

## What Part 1 does not establish

- Whether a live model proposes useful follow-ups (Part 2: C1 and C2).
- Whether the live jail path works with the real Codex CLI 0.159.3. The fake jail stands in for the jail script, and
  the doctor's READY check was scripted.
- Anything about scientific correctness. The follow-up adds listings and explanations of records only.

## Part 2 (frozen, not run)

> **Integrator's note (17 Oct 2026). Use this command, not the one below.** Run Part 2 from the **integration
> checkout** at `af1669c` or later, not from the track clone. The track clone still has the earlier jail, which is
> tied to one account; the portable jail and the doctor's self-probe exist only on the integration branch. The suite
> files in `FOLLOWUP_SUITE_v1/` are unchanged since their freeze. Set the jail explicitly:
>
> ```
> cd /home/jwen/projects/RNPBench/RNPLens_dev_0.4/RNPLens && \
> RNPLENS_CODEX_CALLS=/home/jwen/projects/RNPBench/scratch_agent/v04/codex_calls \
> RNPLENS_CODEX_JAIL=$PWD/assistant/rnplens_assistant/codex_adapter/codex_jail.sh \
> RNPLENS_FOLLOWUP_LIVE=I_CONFIRM_AUTO_RELOAD_OFF PYTHONPATH=$PWD/src:$PWD/assistant PATH=$HOME/.local/bin:$PATH \
> /home/jwen/projects/RNPBench/RNPLens_dev_0.3/venv/bin/python assistant/evaluation_v04/FOLLOWUP_SUITE_v1/run_part2.py --live \
>   --tasks /home/jwen/projects/RNPBench/scratch_agent/assistant_dev_tasks \
>   --out /home/jwen/projects/RNPBench/scratch_agent/v04/followup/part2_run1
> ```
>
> The command originally recorded below omitted `RNPLENS_CODEX_JAIL` and named the track clone.

**Exact command (on karyon, in the track clone):**

```
cd /home/jwen/projects/RNPBench/RNPLens_dev_0.4/tracks/followup/RNPLens && \
RNPLENS_CODEX_CALLS=/home/jwen/projects/RNPBench/scratch_agent/v04/codex_calls \
RNPLENS_FOLLOWUP_LIVE=I_CONFIRM_AUTO_RELOAD_OFF PYTHONPATH=$PWD/src:$PWD/assistant \
/home/jwen/projects/RNPBench/RNPLens_dev_0.3/venv/bin/python assistant/evaluation_v04/FOLLOWUP_SUITE_v1/run_part2.py --live \
  --tasks /home/jwen/projects/RNPBench/scratch_agent/assistant_dev_tasks \
  --out /home/jwen/projects/RNPBench/scratch_agent/v04/followup/part2_run1
```

- **Expected number of Codex calls:** 12 nominal (one planning call for each of the 12 scenarios). The minimum is 12
  and the maximum is 24, with at most one replan per scenario after a policy rejection.
- **Model:** gpt-6.1-sol, reasoning effort medium, through this checkout's jail.
- **Guards:**
  - stop on any change of the credit balance;
  - stop when weekly usage reaches 10 %;
  - strictly serial execution;
  - refuse to start between 2026-10-22T00:00 and 2026-10-25T00:00 Australia/Canberra.
- **Note for the operator:** the jail script hard-codes `/home/jwen/.codex`. RNPLens doctor reports the jail as
  ACTION unless `RNPLENS_CODEX_JAIL` is set, so export `RNPLENS_CODEX_JAIL=$PWD/assistant/codex_adapter/codex_jail.sh`
  as well. Otherwise the doctor guard refuses the run.

## Correction to the frozen SUITE.md

SUITE.md says that, at freeze time, the module had been smoke-tested by hand with "one local follow-up and its
replay". This understates what was done. SUITE.md was written before the last pre-freeze smoke checks, and the
complete list is the one in FREEZE.md, which was written at the freeze point:
- a local follow-up;
- the scripted-stub Codex path, including an F9 rejection, a replan and approval;
- the no-consent path;
- replay.

None of these checks used the suite's scenarios or its runner. SUITE.md is not edited because it is hash-locked;
this note is the record.
