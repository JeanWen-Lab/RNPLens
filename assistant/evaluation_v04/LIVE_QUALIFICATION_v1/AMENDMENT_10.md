# Amendment 10 to LIVE_QUALIFICATION_v1: re-pin three sources after the launch-boundary and replay-integrity corrections

Approved by the owner. The approval, its date and the exact patch it approves (by sha256) are recorded outside this
folder in `records/native_platforms/LQ_AMENDMENT_10_APPROVAL.md`. Applied on branch `dev/0.4-integration` on top of `db464e774fb31d09b531fb25ed9ebb8dce0eb433` (the integration head after the
replay-integrity correction); nothing changes on
`rc/0.4-candidate`. Frozen **before any run of this suite at this head, mocked or live**. No Codex or other
language-model call has been made for RNPLens 0.4.

## Why

The release audit found that the Assistant's launch boundary trusted the caller's environment: `RNPLENS_CODEX_JAIL`
could name any script as the jail, and the jail wrapper inherited `PATH`, `BASH_ENV` and exported shell functions.
The owner-approved correction (reviewed commit `5ed6808`, integrated on `dev/0.4-integration`) edits two pinned
sources, and the replay-integrity correction (`c803b77` and `db464e7`, reviewed separately) edits a third:
- `codex_llm.py`: the jail is always the one shipped with this installation. `RNPLENS_CODEX_JAIL` naming another script
  is refused (`JailRefused`) before any folder is created and before every call, and a missing jail is refused. The
  shipped jail is started with only `HOME`, `CODEX_HOME`, `RNPLENS_CODEX_BIN` and `PATH=/usr/bin:/bin`. The Codex
  argument list and the hardening list are unchanged.
- `doctor.py`: the jail check applies the same rule and runs the jail's self-probe with the same environment.
- `replay.py`: a saved plan is replayed only if it is the plan its run recorded (`run_record.json` `plan_sha256`) and
  its steps are re-admitted by the policy (tool allowlist, step budget, relative paths and reference rules; the
  sequencing rules are not re-applied) with exactly the saved arguments; a follow-up plan only if it carries exactly
  the approved choice and evidence hash of its `followup_record.json`. A refused replay runs and writes nothing. A plan
  without a record replays and is reported `NOT_VERIFIED`. Evidence formats and hashes are unchanged.

Before this amendment, `freeze_refusals()` reported exactly these three files. On the integration head,
`assistant/tests/test_live_qualification.py` gives 22 failures, each the driver refusing at the freeze check before any
run starts. With this amendment applied it gives 0 failed (verification report recorded with the approval).

## 1. Pinned sources (scenarios.json `pinned_sources`)

| file | pinned before (Amendment 9) | after |
|---|---|---|
| `assistant/rnplens_assistant/codex_llm.py` | `a6671a4c4a1259b74123d0e132d250274a8f9a0bc09e5f49dc11dbb1b7d51013` | `d35580d3c0e2d7dc63753cf6d579e9dace5c78a17206847c37826094a9809ac3` |
| `src/rnplens/doctor.py` | `b4715079810078fa3e8a13e781f34d13a03dadf55c01c11fce95360745eff729` | `508babc693882d2175a25d116d2396466335f6046ed27f4934d8b8997e7da3ae` |
| `assistant/rnplens_assistant/replay.py` | `4827daed51ebebd66f8683003c13d7a4c2e06429bb3c3a42e7c13aab985da826` | `7bf4709f8ff52b124d857e7298490697f23d4be9aa698a4febd369d70b50b361` |

The other 20 pinned sources are byte-identical to `b8230fc0048294e9cfeb5c2330164538bb77f08c`, and their pins are unchanged. They include
`confine.py`, the planner, drafter and follow-up prompts, the tool registry, `policy.py`, `tools.py`, `gates.py`,
`evidence.py`, `followup.py`, `ask.py` and `codex_jail.sh`.

scenarios.json: `5486cf7c5fcc30c4d1d37672c81d9e8b770f50d2131468da37b5e96fbce8a9f4` before, `03a75fb0ade768e30e8c71141a2f2d3af2eace1e1ea32f69b9ad5fd396bb282a` after.

## 2. What does not change

- The scenarios, the call budget and the ledger cap.
- The privacy gate, the confirmation and authorisation rules (Amendment 8), and the scoring.
- The driver files of this folder and Amendments 1-9.
- The Linux jail, the macOS Seatbelt wrapper and profile, and `confine.py`.

The suite remains a Linux (karyon) suite. A macOS live smoke test is a separate proposal and needs its own
authorisation.
