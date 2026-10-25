# Amendment 11 to LIVE_QUALIFICATION_v1: re-pin the Linux jail after the installation-folder correction (R3)

Approved by the owner. The approval, its date and the exact patch it approves (by sha256) are recorded outside this
folder in `records/native_platforms/LQ_AMENDMENT_11_APPROVAL.md`. Applied on branch
`staging/r3-installation-folder-rule` on top of `53711d496bd7cc6c6b7dfac308f8ba345d4a1df4` (the RNPLens 0.4
qualification candidate); nothing changes on `rc/0.4-candidate`. Frozen **before any run of this suite at this head,
mocked or live**. No Codex or other language-model call has been made for RNPLens 0.4.

## Why

Release defect R3. Both confinement wrappers derive the Codex package folder from the binary's own location
(`PKG = dirname(realpath(BIN))`) and then grant that whole folder to the confined Codex process:
`--ro-bind "$PKG" "$PKG"` on Linux, and `(allow file-read* (subpath "@PKG@"))` together with
`(allow process-exec (subpath "@PKG@"))` on macOS. An operator who set `RNPLENS_CODEX_BIN=$HOME/codex` therefore
made the entire home directory readable by that process. The documented installation
(`~/.codex/packages/standalone/current`) was never affected, and on Linux a binary under `/usr/` was never affected
because `/usr` is already bound read-only in full.

The correction (staging commit `e958a75e0de4aa67f799c09f832985d5026c313c`) adds one identical rule block
(`check_pkg_folder`) to both wrappers, immediately after `PKG` is resolved and before the executable check, the
login-file check, any folder creation, any profile rendering and any process start. An installation folder that is
not one program's own is refused with exit status 64 - the configuration-refusal status both wrappers already use -
and nothing is started. The rule can only turn a start into a refusal: it never widens access, never narrows a grant
silently, and cannot change any hash, evidence record or scientific output. `codex_seatbelt.sb` is unchanged.

## 1. Pinned sources (scenarios.json `pinned_sources`)

| file | pinned before (Amendment 10) | after |
|---|---|---|
| `assistant/rnplens_assistant/codex_adapter/codex_jail.sh` | `2a88313b4829fde9c6e56b230ca7bddc5f5c35227a402923b7409ac4a1c8c2be` | `8365baeeec004e4cd96370677c823d08b6eb4d9b019f34e3061f10576c9e6853` |

The other 22 pinned sources are byte-identical to the candidate `53711d496bd7cc6c6b7dfac308f8ba345d4a1df4` and their
pins are unchanged; they include `confine.py`, `codex_llm.py`, `doctor.py`, `policy.py`, `tools.py`, `gates.py`,
`replay.py` and the three prompts. Measured, not assumed: at the staging head before this amendment
(`0ebc6781f4925aa49b204081c9a144a9cf54c9b0`), `run_live.freeze_refusals()` returns exactly one entry,
`pinned source changed since the freeze: assistant/rnplens_assistant/codex_adapter/codex_jail.sh`, and with this
amendment applied it returns none.

scenarios.json: `03a75fb0ade768e30e8c71141a2f2d3af2eace1e1ea32f69b9ad5fd396bb282a` before,
`f21785c9a1b6e19c88a4cfeb26dfb425287f8e3bd8168e3e72ec43a72d738266` after.

## 2. What else this amendment must update

- `FREEZE.md`: the `scenarios.json` row (above), and a new row for this file, because `freeze_refusals()` also
  refuses any file in the suite folder that `FREEZE.md` does not list.
- Outside the suite folder, in the same patch: `assistant/tests/test_confine.py` carries the candidate's jail
  sha256 in `LINUX_JAIL_SHA256` and asserts the shipped jail still has it. It is a test, not a pin, but it binds the
  same file and must move with it: `146ec1682fce57cf016c5d798e8aceba3b8748715b8bb0ec6d04be742bb4d2b8` before,
  `82c80a0be475b1d63a3d0e1af326d27dc65da2e4d079d35269c1b3ce0bcb3fb7` after.
- `run_live.authorisation_values()` records `jail_sha256`, the sha256 of
  `assistant/rnplens_assistant/codex_adapter/codex_jail.sh` computed at run time from `JAIL_REL` (run_live.py line
  69), and `freeze_sha256`, the sha256 of this folder's `FREEZE.md` computed at run time (run_live.py line 256).
  Both are members of `AUTH_KEYS` (run_live.py lines 192-194), and `authorisation_refusals()` (run_live.py line 262)
  refuses the run when the owner's confirmation file states a value that differs. Both values change with this
  amendment. The new `jail_sha256` is `8365baeeec004e4cd96370677c823d08b6eb4d9b019f34e3061f10576c9e6853`; the new
  `freeze_sha256` is the sha256 of the amended `FREEZE.md` and is recorded with the approval, because `FREEZE.md`
  carries this file's own row and so cannot be hashed until this file is final.

## 3. What does not change

- The scenarios, the call budget, the ledger cap and the order of the suite.
- The privacy gate, the confirmation and authorisation **rules** (Amendment 8), and the scoring.
- The driver files of this folder and Amendments 1-10.
- `confine.py` (`01d8976a20891d9a427591cc69990489126469495bf6ef572726885e6f6f43c1`), `codex_llm.py`, `doctor.py` and
  every other pinned source.
- `codex_seatbelt.sb` (`096a2bd68756125a62b0e89818659503eb7ca42147ddf3bdcb4f539df3abc7fd`, both copies) and the
  Seatbelt profile text; the macOS wrapper is not pinned by this suite.
- `run_live.runtime_hashes()`, which hashes only the Codex binary, bubblewrap and the interpreter
  (`codex_sha256`, `bwrap_sha256`, `python_sha256`) and never the jail script.
- The 8 frozen scientific sources (`FROZEN_SOURCES.json`,
  `3d1cb00b9b39a003cbe16f96bef8842648fcc2b4cb9d9684d87c0584691e7c91`) and the doctor frozen-source check:
  `frozen_loader.verify_sources()` passes for all 8 at the amended head.
- `tools/release_manifest.py` (`7ddca10c5b4593bf71d5c9f06f39ae606104b58ec2bd9e200bd6295ced59019f`): it embeds no
  sha256 literal and never names the wrappers; it recomputes every hash.

The suite remains a Linux (karyon) suite.

## 4. Requalification this amendment requires

A confinement file changed on both platforms, so the qualification cannot be inherited from
`53711d496bd7cc6c6b7dfac308f8ba345d4a1df4`: G1-G6 must be re-run on Linux and on macOS at the amended head. Linux
G5_confinement is blocked by the standing owner restriction on `assistant/tests/test_confine_linux.py`, which must
not be run, reimplemented or circumvented by any agent; macOS G5_confinement is the only in-sandbox measurement
available for this correction. See `AMENDMENT_11_APPROVAL_PACKAGE.md` and `R3_CORRECTION_RECORD.md` for the scope,
the evidence the owner needs, and what requalification can and cannot establish on Linux.
