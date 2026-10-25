# LIVE_QUALIFICATION_v1 Amendment 10 (revision 2) — owner approval record

**Decision: APPROVED** by the owner (Jean Wen), 2026-10-23 (AEDT). The agent recorded it from the owner's written instruction "RNPLens 0.4 — Approve Replay Correction and Amendment 10 r2". This is a recorded written approval, the same procedure as Amendment 9. No cryptographic signature is involved.

| item | value |
|---|---|
| approved base commit | `db464e774fb31d09b531fb25ed9ebb8dce0eb433` (`dev/0.4-replay-integrity`: `5024746` + `c803b77` + `db464e7`) |
| approved source correction | replay integrity `c803b77` (initial) and `db464e7` (corrected implementation, superseding the initial version) |
| approved patch | `LQ_AMENDMENT_10.patch` (revision 2), sha256 `83b5c4ae3b4c81dbfcf20a28b96a6b6f5de8faab9f945f9f462f53a62d726ec8` |
| files changed by the patch | `assistant/evaluation_v04/LIVE_QUALIFICATION_v1/AMENDMENT_10.md` (new), `FREEZE.md`, `scenarios.json` |
| re-pinned | `assistant/rnplens_assistant/codex_llm.py` → `d35580d3c0e2d7dc63753cf6d579e9dace5c78a17206847c37826094a9809ac3`; `src/rnplens/doctor.py` → `508babc693882d2175a25d116d2396466335f6046ed27f4934d8b8997e7da3ae`; `assistant/rnplens_assistant/replay.py` → `7bf4709f8ff52b124d857e7298490697f23d4be9aa698a4febd369d70b50b361` |
| other 20 pins | unchanged |
| approval request reviewed | `LQ_AMENDMENT_10_r2_APPROVAL_REQUEST_db464e7.md`, sha256 `446b4c44b82cb96a68ff96f339777a6f27b490f1e99aa86d79c0775ccaa2ce02` |
| owner instruction (verbatim text) | sha256 `3a748db2107b3979c0dcb92f5baa2d5ea2d9e8237542eb99fe24c52d9f936d03` |
| review folder (karyon) | `RNPLens_dev_0.4/release_blockers_20261023/replay_integrity/` (`amendment10_r2_20261023T012615Z/`) |

**Scope.** Adopt this freeze amendment and perform final Linux and macOS qualification at the resulting commit. It also covers one fresh, dedicated, isolated, file-based macOS Codex login, for authentication and no-inference diagnostics only.

It is **not** approval to:
- merge into `rc/0.4-candidate`, publish or distribute;
- make a live Assistant model call;
- run the three-call macOS live smoke test.

The credential and network architecture is approved for controlled internal qualification only. This is not public-release acceptance.

**Superseded, never applied, preserved:**
- revision 1, `0a37d4a99041cc80aab123c344098cec9a4b0193b8bacc490ec5be37aae5ca48` (base `5024746`);
- the parallel review's patch `df3e36f0fe122b8c58f585ce28395dc9a6d0def535588d914b7ab935e06ce68b` (base `c803b77`), in `final_integration_a10_review_20261023T011846Z/`.
