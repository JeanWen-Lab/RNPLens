# Amendment 9 to LIVE_QUALIFICATION_v1: re-pin two sources and pin one new module after the native-platforms change

Approved by the owner. The approval, its date and the exact patch it approves (by sha256) are recorded outside this
folder in `records/native_platforms/LQ_AMENDMENT_9_APPROVAL.md`. Applied on branch `dev/0.4-native-platforms` on top of `4f448612d983a5c799bb2a14e93b88c62b3d1534`; nothing changes on
`rc/0.4-candidate`. Frozen **before any run of this suite at this head, mocked or live**. No Codex or other
language-model call has been made for RNPLens 0.4.

## Why

The native-platforms change (single-computer Assistant on Linux and macOS) edits two pinned sources and adds one
module that the first imports:
- `codex_llm.py` takes the jail from `confine.py`, and passes the call-folder paths that the jail reports. On Linux
  these are `/work/schema.json` and `/work/last.json`, as before (test `test_linux_codex_arguments_identical_to_the_candidate`).
- `doctor.py` gains the macOS Seatbelt check. Its Linux checks and messages are unchanged.

Before this amendment, `freeze_refusals()` reported exactly these two files. All 22 failures of
`assistant/tests/test_live_qualification.py` on the branch came from that one refusal (Linux qualification run
`Linux_20261022T103258Z` at `46f6664`; the same 22 tests on macOS). On the final development head (this
amendment's base) the same file gives 22 failed, 39 passed, 2 skipped on Linux; each failure is the driver refusing at
the freeze check before any run starts. With this amendment applied it gives 0 failed (verification report recorded
with the approval). The macOS Seatbelt correction (`07aeca8`: the profile may read the root directory `/` itself,
nonrecursively) changes no pinned source.

## 1. Pinned sources (scenarios.json `pinned_sources`)

| file | pinned before (Amendments 6-8) | after |
|---|---|---|
| `assistant/rnplens_assistant/codex_llm.py` | `15c9167f6e928f8b4b295710fca6142b9ed0735d223daa983308a0c988063e8f` | `a6671a4c4a1259b74123d0e132d250274a8f9a0bc09e5f49dc11dbb1b7d51013` |
| `src/rnplens/doctor.py` | `548bf968539c284a76c977a2442048c08237e97035e1319550d0b5cd82d08014` | `b4715079810078fa3e8a13e781f34d13a03dadf55c01c11fce95360745eff729` |
| `assistant/rnplens_assistant/confine.py` (new pin) | none | `01d8976a20891d9a427591cc69990489126469495bf6ef572726885e6f6f43c1` |

The other 20 pinned sources are byte-identical to `8e57aead59e7b17e882af131298b1cb91c4d5ae3`, and their pins are unchanged. They include the planner,
drafter and follow-up prompts, the tool registry, `policy.py`, `tools.py`, `gates.py`, `evidence.py`, `replay.py`,
`ask.py` and `codex_jail.sh`.

scenarios.json: `5c957e334e53c1962e735964ac1507d15285afd1a4050db984c388d587957a5e` before, `5486cf7c5fcc30c4d1d37672c81d9e8b770f50d2131468da37b5e96fbce8a9f4` after.

## 2. What does not change

- The scenarios, the call budget and the ledger cap.
- The privacy gate, the confirmation and authorisation rules (Amendment 8), and the scoring.
- The driver files of this folder.
- The Linux jail.

The suite remains a Linux (karyon) suite. A macOS live smoke test is a separate proposal and needs its own
authorisation.
