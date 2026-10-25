# LIVE_QUALIFICATION_v1 Amendment 9 — owner approval record

**Decision: APPROVED** by the owner (Jean Wen), 2026-10-23 (AEDT). The agent recorded it from the owner's written instruction "RNPLens 0.4 — Final Amendment 9 Approval and Qualification".

| item | value |
|---|---|
| approved base commit | `4f448612d983a5c799bb2a14e93b88c62b3d1534` (`dev/0.4-native-platforms`) |
| approved patch | `LQ_AMENDMENT_9.patch`, sha256 `363591444fd217cfc341705585304c87236f71653fe8607bd5d4abfb1200efdb` |
| files changed by the patch | `assistant/evaluation_v04/LIVE_QUALIFICATION_v1/AMENDMENT_9.md` (new), `FREEZE.md`, `scenarios.json` |
| re-pinned | `assistant/rnplens_assistant/codex_llm.py` → `a6671a4c4a1259b74123d0e132d250274a8f9a0bc09e5f49dc11dbb1b7d51013`; `src/rnplens/doctor.py` → `b4715079810078fa3e8a13e781f34d13a03dadf55c01c11fce95360745eff729` |
| new pin | `assistant/rnplens_assistant/confine.py` `01d8976a20891d9a427591cc69990489126469495bf6ef572726885e6f6f43c1` |
| other 20 pins | unchanged |
| approval request reviewed | `LQ_AMENDMENT_9_APPROVAL_4f44861.md`, sha256 `fda46c12dc0e1a341dad50bea8084d0a2a8411a1e55c765ba1c281897dcfc729` |
| owner instruction (verbatim text) | sha256 `b724411ee45e732f1d60c41acb6ebec84ffa2330cd967d10621716b9687a4289` |
| review folder (karyon) | `RNPLens_dev_0.4/native_platforms/lq9_review_final_4f44861_20261022T200823Z/` |

**Scope.** Adopt this freeze amendment and perform final Linux and macOS qualification at the resulting commit. **Not** approval to merge into `rc/0.4-candidate`, to release or publish, to make model-inference calls, or to run the macOS live smoke test.

**Superseded, never applied, preserved:** patch `ec2bb62aed2b886762fdd891f36bdbcb3dcded9b37026eb2fda1b4eaf23fae64` (base `404e7e8`) and its approval `2cf8b42c1e9d7b9996875ae758e997ae324b117f00110519ad3083c3abc98e08`, in `lq9_review_20261022T111404Z/`.
