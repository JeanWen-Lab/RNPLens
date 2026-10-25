# FOLLOWUP_SUITE_v1: frozen test suite for the bounded follow-up (RNPLens 0.4, Function 4)

Written and frozen on 2026-10-16 (Canberra), on branch `track/followup` (base `74681ec`), **before any scenario of
this suite was run**. At freeze time the follow-up code (`assistant/rnplens_assistant/followup.py`, `consent.py`)
had been smoke-tested by hand on the bundled 7K9D example: one local follow-up and its replay. No unit test of the
follow-up and no scenario below had run. No Codex or other language-model call has been made by this track.

## Purpose and status

The suite checks that the follow-up is bounded, policy-controlled, private by default, traceable and replayable. It
does not measure whether a follow-up is scientifically useful. Its result cannot qualify a scientific claim. The
follow-up capability stays **EXPERIMENTAL** until Part 2 has run and its result has been reviewed.

## Data

Development data only:
- **Part 1:** the bundled 7K9D example, with runs `exec_A` and `exec_B` and the construct FASTA files under
  `examples/`.
- **Part 2:** the karyon development tasks d1–d5, `RNPBench/scratch_agent/assistant_dev_tasks/` (7K9D, 1VTM, 24BR).
  These are read-only and are copied into scratch. Reference files are not copied.

None of the excluded targets listed in the contracts document §1 is used. The Rank holdout is never opened.

## Part 1: scripted, no language model (`scenarios_part1.json`, `run_part1.py`)

There are 21 scenarios. Each one runs in a fresh temporary directory, in four steps:
1. Import 7K9D with two runs.
2. Run menu item A, then the scenario's initial item (usually C, RNA 13-23, both runs).
3. Set the consent state (none, opt-in, or opt-in then opt-out).
4. Run one follow-up.

The client is one of:
- **`scripted`:** a deterministic fake client (`fake_client.ScriptedClient`) that returns scripted proposals in order;
- **`fake_jail`:** the real `codex_llm.CodexClient` with the jail replaced by a scripted fake codex
  (`fake_client.write_fake_jail`). This exercises the subprocess, session-log parsing, and the usage and credit
  guards. The fake jail has five modes:
  - `ok`;
  - `fail` (exit 1);
  - `sleep` (exceeds a 1 s timeout);
  - `usage99` (99 % plan usage);
  - `credit_change` (balance differs from the baseline).

The doctor's READY check is replaced by a scripted READY. The agent prerequisites are tested elsewhere
(tests/test_doctor.py).

Categories covered (scenario IDs):

| category | scenarios |
|---|---|
| appropriate follow-up accepted | P1-01, P1-02, P1-16 |
| irrelevant follow-up rejected (F9) | P1-03 |
| repeated plan refused (F5) and circular plan refused (F6) | P1-04, P1-05 |
| privacy refusal: no consent, so no client and no subprocess | P1-06 |
| opt-out after opt-in | P1-07 |
| unsupported analysis, blocked tool (F3) | P1-08 |
| result misinterpretation: model rationale asserting correctness never reaches the answer | P1-09 |
| invalid plans: bad id (F1), out-of-range positions and unknown run (F2), malformed proposal (F8) | P1-10, P1-11 |
| model unavailable (subprocess error) | P1-12 |
| network interruption (timeout) | P1-13 |
| subscription usage exhaustion (UsageGuard) and credit change | P1-14, P1-15 |
| LLM-free execution and replay (same analysis and a fresh pre-follow-up copy) | P1-17 |
| untraceable numbers detected (injected number, altered slot, empty answer) | P1-18 |
| one planning round per question | P1-19 |
| tool-call budget (F4) | P1-20 |
| confirmation required before execution | P1-21 |

**Scoring (`score.score_part1`).**
- Each scenario lists expected facts under `expect`. It passes when every expected fact equals the observed fact.
  The observed facts are collected by `run_part1.run_scenario`.
- Part 1 passes when all 21 scenarios pass.
- A runner error is a failure.

## Part 2: live Codex, frozen and NOT RUN (`scenarios_part2.json`, `run_part2.py`)

There are 12 scenarios, L01–L12, on d1–d5.
- The model is `gpt-6.1-sol`, reasoning effort medium, through this checkout's jail.
- Each scenario sets up deterministically: import (`--engine BOLTZ2`), then menu item A, and for the C scenarios the
  AUTO range rule in the scenarios file.
- The opt-in is recorded with `--yes`, scoped to the scratch project.
- Each scenario then runs one Codex follow-up with `--yes`.

Scoring (`score.score_part2`) applies these criteria to each scenario:
- **C1:** the final proposal's id and constrained arguments are in the accept set. "none" counts only where the
  accept set lists it.
- **C2:** the final proposal was approved by the policy.
- **C3:** no untraced number (the traceability violations are empty).
- **C4:** no forbidden wording in the answer. The researcher's own question line, the Limitation and "Not available
  here" lines and the fixed closing note are exempt (the same convention as the assistant's answer gates).
- **C5:** applies only to tasks with a reference file. Neither the reference file name nor any reference-derived key
  appears in any payload.

Decision rule, written before any run:
- C3, C4 and C5 must hold in every completed scenario. Any failure of these keeps the capability EXPERIMENTAL and is
  reported as a defect.
- If C1 and C2 both hold in at least 10 of 12 scenarios, the integrator may propose DESCRIPTIVE status for the
  follow-up capability.
- Otherwise it stays EXPERIMENTAL.
- A run stopped by a usage or credit guard is incomplete, not failed. The completed scenarios are reported with their
  denominator. At most one complete re-run under identical files is allowed.

Number of Codex calls:
- at least 12 and at most 24 (one planning call per scenario, plus at most one replan after a policy rejection);
- nominal 12.

Run guards (`run_part2.guards`), each of which refuses the run:
- FREEZE.md mismatch;
- no `--live`;
- `RNPLENS_FOLLOWUP_LIVE` is not `I_CONFIRM_AUTO_RELOAD_OFF` (that is, the owner has not confirmed that automatic
  credit reload is off);
- inside 2026-10-22T00:00 to 2026-10-25T00:00, Australia/Canberra (the sealed-evaluation window);
- `RNPLENS_CODEX_CALLS` or `--out` is not inside `RNPBench/scratch_agent/v04/`;
- the jail is not this checkout's, or lies under `RNPLens_dev_0.3`;
- `rnplens doctor --agent` is not READY, or the model catalog does not list `gpt-6.1-sol`;
- another run holds the lock.

During the run:
- scenarios run strictly serially;
- the CodexClient stops on any credit-balance change and on weekly usage of 10 % or more (stricter than the
  evaluation's 85 %);
- a usage stop ends the run.

## Amendments

An amendment needs three things:
- a measurement that makes a frozen clause unsatisfiable or wrong;
- a dated `AMENDMENT_<n>.md` that states the measurement, the clause, why it was wrong, the replacement, and what is
  unchanged;
- a new FREEZE entry, made before the compute the amendment affects.

Scenario expectations are never edited to match an observed result without such a record.
