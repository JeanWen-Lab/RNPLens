# Freeze-record addendum: Amendment 4 (16 October 2026, Canberra), before any sealed trial

**Frozen code.** The assistant code is frozen at the commit that adds this file. Its parent is `c0c6813` (the
Amendment 4 change). This replaces `a7bf44c` as the frozen commit.

**Unchanged.** The checksums recorded in `FREEZE_RECORD_SCORING_2026-10-16.md` are unchanged, and the launch wrapper
re-verifies them before every trial. The sealed manifest is unchanged:
`330c9d28d63be78b6b0ad2fc2c14b87a8f664a176a421b3afc8546a1cc57edcf`.

## Files added or changed by Amendment 4 (sha256)

| file | sha256 |
|---|---|
| evaluation/AMENDMENT_4_2026-10-16.md | 4e985dcaad40d2f510ae1ff28775ead623c3b6a4e99d8c953d8fb67ca4f254f7 |
| evaluation/install_test.sh | 85683995da986597fbe9c68beffcd5877c8ad5f8ab0f33eb82a97acf99774e13 |
| rnplens_assistant/guide.py | 5258a0ec93ad74166de486ccc4afded8bb2e6159f5721f265da863ca79c0c1b8 |
| rnplens_assistant/ask.py | 396795c116605396a33ba18abf92e2c49cab503076b6fac80be7a0ec8b95da61 |
| rnplens_assistant/tools.py | 10f4a035a7946c5895f1aa3b96c1935bdfe5446fe12e1f7179a9cdafe04bab6b |
| rnplens_assistant/docs/which_analysis_should_i_use.md | d1a45b574de90df9c732ccb1bb7471da2a9f49120782e975ec094ef3db204257 |

## Verification on karyon (16 Oct, 19:33–19:34, folder `scratch_agent/verify_a4_20261016T193325`)
- **pytest:** 198 passed, 11 skipped.
- **Replay:** all 15 development R replays matched after the change.
- **Fresh installation test** (`scratch_agent/install_test_20261016T193415`): passed all 11 steps, including
  `installed_prompt_equals_evaluated`. The installed `doc_text()` has sha256 `a79637fd…ea97` and `explain_metric`
  gives `1615052ac88cf3f8`, both identical to the evaluated values.
- **Its single Codex call:** credit balance 62,500 (unchanged); weekly plan usage 3.0% (it was 2.0% earlier in the
  day); model `gpt-6.1-sol`.
