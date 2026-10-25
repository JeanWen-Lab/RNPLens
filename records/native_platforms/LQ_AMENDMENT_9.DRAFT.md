# DRAFT: Amendment 9 to LIVE_QUALIFICATION_v1 (2026-10-22, Canberra): re-pin two sources after the native-platforms change

**Status: PROPOSED. Not owner-approved. Applies only on branch `dev/0.4-native-platforms`; it changes nothing on
`rc/0.4-candidate`.** Frozen, once approved, **before any run of this suite at this head, mocked or live**. No Codex or
other language-model call has been made for RNPLens 0.4.

## Why

The native-platforms change (single-computer Assistant on Linux and macOS) edits two pinned sources and adds one module
that the first imports:
- `codex_llm.py` takes the jail from `confine.py`, and passes the call-folder paths that the jail reports.
  On Linux these are `/work/schema.json` and `/work/last.json`, as before (test
  `test_linux_codex_arguments_identical_to_the_candidate`).
- `doctor.py` gains the macOS Seatbelt check. Its Linux checks and messages are unchanged.

Without this amendment, `freeze_refusals()` reports exactly these two files. All 22 failures of
`assistant/tests/test_live_qualification.py` on the branch come from that one refusal (Linux, karyon: 22 of the 24 suite
failures of qualification run `Linux_20261022T093237Z`; macOS: the same 22 tests).

## 1. Changed pinned sources (scenarios.json `pinned_sources`)

| file | pinned (Amendment 7/8) | after |
|---|---|---|
| `assistant/rnplens_assistant/codex_llm.py` | `15c9167f6e928f8b4b295710fca6142b9ed0735d223daa983308a0c988063e8f` | `a6671a4c4a1259b74123d0e132d250274a8f9a0bc09e5f49dc11dbb1b7d51013` |
| `src/rnplens/doctor.py` | `548bf968539c284a76c977a2442048c08237e97035e1319550d0b5cd82d08014` | `b4715079810078fa3e8a13e781f34d13a03dadf55c01c11fce95360745eff729` |
| `assistant/rnplens_assistant/confine.py` (new pin) | — | `01d8976a20891d9a427591cc69990489126469495bf6ef572726885e6f6f43c1` |

The other 20 pinned sources are byte-identical to `8e57aea`. They include the planner and drafter prompts, the tool
registry, `policy.py`, `tools.py`, `gates.py`, `evidence.py`, `replay.py`, `ask.py` and `codex_jail.sh`.

scenarios.json: `5c957e334e53c1962e735964ac1507d15285afd1a4050db984c388d587957a5e` before, `5486cf7c5fcc30c4d1d37672c81d9e8b770f50d2131468da37b5e96fbce8a9f4` after.

## 2. What does not change

- The scenarios, call budget and ledger cap.
- The privacy gate, the confirmation and authorisation rules (Amendment 8), and the scoring.
- The Linux jail.

The suite remains a Linux (karyon) suite. A macOS live smoke test is a separate proposal and needs its own authorisation.

Apply after owner approval: `patch -p1 < records/native_platforms/LQ_AMENDMENT_9.DRAFT.patch` (from the repository root).
