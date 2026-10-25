# Amendment 7 to LIVE_QUALIFICATION_v1 (2026-10-19, Canberra): re-pin src/rnplens/assist.py after the RC usability fix

Approved by the owner on 2026-10-19 for offline application and requalification (owner decisions of 19 October 2026,
section 1: "Apply the proposed pin update for the changed assist.py source after verifying its actual diff").
Applied on branch `rc/0.4-candidate` (karyon), on top of RC head `c5422ba`, from the RC track's draft
(`AMENDMENT_7.DRAFT.md` / `.patch`). The edits are exactly those of the draft's section 4. This text replaces the
draft's DRAFT heading and "Not applied" paragraph, and adds the verification below.

Frozen **before any run of this suite at this head, mocked or live**. No Codex or other language-model call has
been made for RNPLens 0.4 (readiness: PREPARED, NOT RUN). The failed pre-amendment results are kept unchanged:
- the RC track's QF_78b942f runs: wheel, sdist and no-matplotlib 21 failed; source 23 failed;
- this round's baseline at `c5422ba`: `assistant/tests/test_live_qualification.py`, 23 failed, 16 passed
  (`rc/out/lq-amendment7/logs/pre_lq_src.log`, sha256
  `0e9eec5382a602e76bae6c1801aa6a67d77ba55c8a7de043368eafb23b748344`).

All of those failures come from the one pin refusal for `src/rnplens/assist.py`.

## 1. Changed pinned source (scenarios.json `pinned_sources`)

| file | pinned (Amendment 6) | after |
|---|---|---|
| `src/rnplens/assist.py` | `994d1fa8ca3278e7058af3f5da90e500f158e71a7376c2baeb4c4dd7d66e0f2b` | `2254b16cba460b603b1137a3ca596b3c0aabac2efa01f4d5ecabd392a18f7794` |

The other 21 pinned sources are unchanged at `c5422ba`: `freeze_refusals()` listed only this file, and 21 of 22
hashes matched. The previous hash of scenarios.json was `58b0a40b3b6b08bd8636872012d7f5e6e26e9b22eb0d8bda45ad1d7e54871dce`.

## 2. The change, as verified (not taken from the draft)

- `git log b5ec0eb..c5422ba -- src/rnplens/assist.py` lists exactly one commit, `414b5e4` ("usability: the question
  menu and the natural-language mode link the contact tables and the Mol* page"). `b5ec0eb` is the commit that
  produced the pinned `994d1fa8…0f2b`.
- `git diff b5ec0eb c5422ba -- src/rnplens/assist.py`: 19 insertions, 2 deletions; diff sha256
  `fb435d9db0701649d6246b56bd50e052cdecf14768795a19c396ba0ccc10675c`. Three hunks:
  1. `from . import capabilities, result_links, trace`.
  2. `show_result`, menu items in `result_links.CONTACT_ITEMS`, not on a failed or blocked result: the `--json`
     output gains `result_links`, and the text output appends `result_links.text(links)` after the evidence IDs.
  3. `natural_language`: after the answer, run-record and evidence-ID lines, it locates the produced analysis
     (`followup.from_assistant_run(run_dir)`), prints the same links and writes `RUN/result_links.json`.
- **Model-visible payloads.**
  - Hunk 3 runs only after `ask.run` has returned, so after the planner's call and its replan. It writes only local
    files.
  - Hunk 2 runs in the menu, where no model is involved. It may write the offline viewer page into the analysis
    folder.
  - The follow-up summary is built from that folder, so the premise check was rerun (section 3).
- **Not pinned.** `rnplens/result_links.py` is new and unpinned, as are the other `src/` modules the pinned files
  import (`rnplens.projection`, `rnplens.portability`). Its effect on the payloads is covered by the unchanged payload
  bytes.

## 3. Payload premise and privacy check (karyon, real d1–d5, no model)

`premise_check_r2.py` was run unchanged at `c5422ba`, the code of this amendment's head. Its record
(`rc/out/lq-amendment7/premise/premise_c5422ba.json`) is **byte-identical** to the frozen
`premise_check_a6_karyon.json` (sha256 `f71be2eae0cacebff3f4169361169a10ded57ba1d58eb44eb9b6728a8b129a89`).
- All 26 payload sha256 values equal the Amendment 6 expected table. That table is therefore unchanged; there was
  nothing to regenerate.
- Gate findings 0, `followup.privacy_check` findings 0, real names found 0; reconstruction equal for 11 of 11 planner
  tasks.

## 4. Unchanged

- **Expectations.** No scenario, question, allowed-tool list, require entry, threshold, guard value, budget (max 24
  live calls, nominal 12), scoring or decision rule changed.
- **Recorded output.** `run_live.py` records `output_tail` (the last lines of `assist.main`), which now shows the
  links. `output_tail` is recorded and not scored.
- **Suite files.** DESIGN.md, run_live.py, score_live.py, privacy.py, fake_codex.py, premise_check.py,
  premise_check_r2.py, the three premise records, AMENDMENT_1–6 and FOLLOWUP_SUITE_v1.
- **Outcome.** The suites and the fake-Codex end-to-end run follow this freeze. Their outcome is recorded in
  results/LIVE_QUALIFICATION_READINESS.md, not here.
