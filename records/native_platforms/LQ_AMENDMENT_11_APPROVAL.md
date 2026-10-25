# LIVE_QUALIFICATION_v1 Amendment 11 — owner approval record

**Decision: APPROVED** by the owner (Jean Wen), 2026-10-24 (AEDT). The agent recorded it from the owner's written
instruction "RNPLens 0.4 — Owner Approval of Amendment 11". This is a recorded written approval, the same procedure
as Amendments 9 and 10. No cryptographic signature is involved.

| item | value |
|---|---|
| approved base commit | `53711d496bd7cc6c6b7dfac308f8ba345d4a1df4` (the qualified candidate) |
| approved source correction | R3 fail-closed Codex installation-location restriction, `staging/r3-installation-folder-rule`, R3 content at `0ebc6781f4925aa49b204081c9a144a9cf54c9b0` |
| approved amendment text | `AMENDMENT_11.md`, sha256 `c1a87826b2daa9cd9e2734e2a70f9e47221e0b0b9ec9691a27dd7723ebae7242`, 6,430 bytes, 85 lines |
| approved freeze record | `FREEZE.md`, sha256 `f7c55b5d585696e35f490bc691260624bb686f906fa7526d66f985785c025ff9`, 10,927 bytes, 63 lines, 22 hash rows (was 21) |
| re-pinned | `assistant/rnplens_assistant/codex_adapter/codex_jail.sh` → `8365baeeec004e4cd96370677c823d08b6eb4d9b019f34e3061f10576c9e6853` (was `2a88313b4829fde9c6e56b230ca7bddc5f5c35227a402923b7409ac4a1c8c2be`), pin 20 of 23 |
| other 22 pins | unchanged |
| source copy of the jail | `assistant/codex_adapter/codex_jail.sh`, same new hash, byte-identical to the packaged copy |
| `AUTH_KEYS` bindings | `jail_sha256` (computed from `JAIL_REL` = the packaged copy) and `freeze_sha256`, among 18 mandatory keys |
| signing instructions reviewed | `AMENDMENT_11_SIGNING_INSTRUCTIONS.md`, sha256 `ff22deadcbd2bed50e3bb1bbdf8c88b5ac38a33cee9caa5fddccc88d56b567c8` |
| owner instruction (verbatim text) | sha256 `347e45d013d0300346b33224ff247a49b2c01f748280cd824ce10713a28f921b`, 2,382 bytes |
| review folder (karyon) | `RNPLens_dev_0.4/release_prep_20261023T0530Z/amendment11/` |

**Pre-adoption verification, run 2026-10-24T12:41:00+11:00 before any change was made.** All five hashes above were
recomputed and matched: the amendment text, the proposed `FREEZE.md`, both new jail copies and the candidate's old
jail hash. `JAIL_REL` was confirmed to resolve to the packaged copy, `jail_sha256` and `freeze_sha256` were confirmed
present in `AUTH_KEYS`, and the replacement `FREEZE.md` was confirmed to carry the amendment's own hash as a row, so
the freeze chain closes on itself. The owner's standing condition — *any source or hash mismatch is a STOP* — was not
triggered.

**Scope.** Adopt this freeze amendment, integrate the R3 correction into a new development integration candidate, and
perform the required Linux and macOS qualification at the resulting commit.

It is **not** approval to:
- perform live model inference;
- create or pre-sign a live-qualification confirmation record;
- publicly release;
- merge into `rc/0.4-candidate` without final review;
- change the frozen A9 evaluation or `manuscript/current`.

**What it does not assert.** It does not assert that Linux G5 has passed — G5 has no verdict and remains the owner's
own run — nor that production security clearance is granted, which remains BLOCKED on both platforms for a separate
reason.

**Preserved.** The qualified candidate `53711d49` and the release candidate `8e57aead59e7b17e882af131298b1cb91c4d5ae3`
are unchanged by this approval.
