# Amendment 6 to LIVE_QUALIFICATION_v1 (2026-10-18, Canberra): re-pin seven sources after the QA round of RNPLens 0.4

Cause: the independent QA round of RNPLens 0.4 on karyon (baseline `80a2afb`). Its fixes are merged in the QA checkout
`qa/0.4-karyon` at `0d6fe84`.
- The agent-security fix round changed six pinned sources (QA_agent-security.md, section 9).
- Three further pinned-file changes were written up by the QA tracks but not applied (P3, U3, O1). They are applied on
  branch `qa/lq-amendment6` (from `0d6fe84`), each in its own commit with a test.

This amendment is written and frozen **before any run of this suite at this head, mocked or live**. No Codex or other
language-model call has been made; the real `codex` binary has only been run as `codex --version`.

## 1. Changed pinned sources (scenarios.json `pinned_sources`)

| source | before (Amendment 5) | after |
|---|---|---|
| assistant/rnplens_assistant/ask.py | `11dcfcfb7b6954309e4662ceae9b519e116124c5aaa445575f6dd2674bd5a3df` | `dfd1dadfa693287509e51cdc1295559202282f08ed0eafda0374c7b837e00191` |
| assistant/rnplens_assistant/followup.py | `af54f0a3b1eedb6d918c1a4ad2348513c363311843a07c24a2515b708789cfa7` | `a941bedcd21dc823d4c5d0ae03d94fad3ee23953aad4c80fa4b5897a75a62fba` |
| assistant/rnplens_assistant/tools.py | `54ae5bca3147507921e259805296862371d00ec0d2fe520be6077e673375cd35` | `cb87bff2eacdfd31fe4aa20ec88d7233b968440ac9b0d8b345f4a58520295536` |
| assistant/rnplens_assistant/docs/which_analysis_should_i_use.md | `d1a45b574de90df9c732ccb1bb7471da2a9f49120782e975ec094ef3db204257` | `9b302bc7db6232ba6a463f3b60f8f3388ecb12017ad7a13cc678953862c9283f` |
| src/rnplens/assist.py | `03fda9de46f1b78d9b94eb0f15207403f768192aa3b427d71d45ea1b336c4507` | `994d1fa8ca3278e7058af3f5da90e500f158e71a7376c2baeb4c4dd7d66e0f2b` |
| src/rnplens/doctor.py | `9fd702196b20239f90daba58b95dd1eb2e36ae46b65c549dfedb5156b140b85a` | `548bf968539c284a76c977a2442048c08237e97035e1319550d0b5cd82d08014` |
| assistant/rnplens_assistant/redact.py | `b1cc5f7b1b9dc8040196b556509b78e6dfc785a53bc5385634a3d22ffc8e66a2` | `def5d6b83ce0d953de60f308ed1e8be11a3c780dbc8a6efd815d72f84fa455f4` |

These 7 of the 22 pins change; the other 15 are unchanged (section 5). Two files changed twice:
- `src/rnplens/assist.py`: `03fda9de…4507` → `f53571c3…5271` (QA `d26a47d`) → `994d1fa8…0f2b` (U3, `b5ec0eb`);
- `src/rnplens/doctor.py`: `9fd70219…b85a` → `ea08bf64…7c21` (QA `b71c76d`) → `548bf968…8014` (O1, `e190d41`).

The previous hash of scenarios.json was `fed98b0d1f1f743bf0966ff1971641ae3da28be6a192e666a3a962529ecf7f06`.

## 2. The QA fixes (agent-security fix round; precise summaries)

The QA report's per-commit file hashes were checked against git at `0d6fe84`, with 0 mismatches. Diff sha256 values
are of `git diff fe337f9 0d6fe84 -- <file>`.

```
 assistant/rnplens_assistant/ask.py      | 95 +++++++++++++++++++++++++++++++-
 assistant/rnplens_assistant/followup.py | 17 ++++--
 assistant/rnplens_assistant/redact.py   | 97 ++++++++++++++++++++++++++++++++-
 assistant/rnplens_assistant/tools.py    | 48 ++++++++++++++--
 src/rnplens/assist.py                   |  8 ++-
 src/rnplens/doctor.py                   | 27 ++++++---
 6 files changed, 268 insertions(+), 24 deletions(-)
```

- **`973e3fd`**, followup.py (`af54f0a3` → `ed82eeca`). An interrupted Codex follow-up round is recorded:
  `followup_record.json` gets state `MODEL_CALL_IN_PROGRESS` before the call and is counted by `_round_used()`;
  finished records are `COMPLETE`.
- **`80e8629`**, ask.py (`11dcfcfb` → `3bdf549f`).
  - After admission, model project ids are replaced by local ids `project_1…`; the policy still checks the model's own
    ids.
  - Model-supplied strings echoed in refused-step labels become `<model-supplied value>`.
- **`1076287`**, ask.py (`3bdf549f` → `00cd854b`).
  - `reference_supplied` is decided by the task's declared references (task.json), never by the model's claim.
  - Without a declared reference, a COMPARE goal or a reference capability always gets the reference refusal.
  - The model's claims are recorded in `reference_claims`.
- **`3b3baac`**, tools.py (`54ae5bca` → `3544e638`). Import clarification questions are made task-relative before
  they become evidence (portable replay).
- **`d26a47d`**, ask.py (`00cd854b` → `dfd1dadf`), followup.py (`ed82eeca` → `a941bedc`), redact.py (`b1cc5f7b` →
  `def5d6b8`), src/rnplens/assist.py (`03fda9de` → `f53571c3`). Pre-send **redact, then verify, refuse on residue**
  for user-typed text: the planner question and replan echo or reasons, and the follow-up question.
  - The redaction covers absolute paths, real names in any letter case, and the names and name-like stems of
    undisclosed top-level files.
  - On a finding: no model call, a local "Not sent" answer and `privacy_refusal`; a replan with a finding is not sent.
  - `NL_PRIVACY` and the privacy docs are updated.
- **`b71c76d`**, src/rnplens/doctor.py (`9fd70219` → `ea08bf64`). `doctor --agent` checks the binary the jail runs:
  `RNPLENS_CODEX_BIN`, else `$CODEX_HOME/packages/standalone/current/bin/codex`, never PATH. It names any differing
  PATH `codex`.
- **`0377f8d`**, tools.py (`3544e638` → `cb87bff2`). The assistant import tool refuses symbolic links out of the task
  (ACCESS_REFUSED, nothing imported) and reports links inside it.
- Not pinned but in the same round: `fd57ce4` (`python -m rnplens_assistant ask --arm G` refused in 0.4) and
  `f47debb` (an existing `--out` is refused).

Diff sha256 per file:
- ask.py `beefbc033fd4fba3964fb046e3574f57badd48c5754fdeffe946c7fbb5f1ebfa`
- followup.py `2bc43f50da8ee7c183ac693d3c5afdbef313d1464c75ae189f70d77b1adc8eb1`
- redact.py `f8dbd3ea7ddc5e2768eb1f9f5478e7cd849efd3bf7e879ed6b6a40c562ad9dd3`
- tools.py `cd42fe51715cc05bd5fd733c580be90ba77ea3b58b3efba3d5f1011c628e4a38`
- assist.py `84c9bb1826b56285496d678170bfd0d1cd3d7f0c441219d810825ea29bfe186b`
- doctor.py `50d6a322076b97c43656f7c0b2458ff697e446a1c705a028306ab2afd9c99917`

**Review.** None of these changes weakens a guard, a privacy rule or the construction of a payload.
- They add a pre-send check in the product and record more state.
- They take the reference decision away from the model and keep model text out of rendered answers.
- The suite's own pre-send gate (privacy.py, run_live.py) is unchanged.
- The planner replan echo is still built from the model's last plan, so the suite's replan check is unchanged.

## 3. The three changes applied here (exact diffs below)

- **P3**, `4419b0e`: both byte-identical guide copies (`docs/` and `assistant/rnplens_assistant/docs/`).
  - The guide now states that Evaluate's four-axis geometry route is blocked (residue-correspondence defect,
    2026-10-14), and that DockQ, DockQ class, fnat, iRMSD and LRMSD remain available under their own definitions and
    are not replacements for the four-axis decomposition.
  - The wording is that of evaluation protocol v3, change (iii), edits 1–4. `geometry.status` also lists `BLOCKED`,
    the status 0.4 writes.
  - QA P3's proposed additions to the "Exit status" table are not made (minimal change; see the readiness report).
  - Tests: new `tests/test_guide_geometry_blocked.py` (2 fail before, 2 pass after). `test_guide_packaging.py` takes
    the new guide and prompt-text hashes; its previous values encode the superseded text.
- **U3**, `b5ec0eb`: `src/rnplens/assist.py`. The menu's RNA-range prompt example is `1-min(L, 20)` from the
  construct length, instead of the fixed "e.g. 40-60". Test: `tests/test_menu_rna_prompt_example.py`; the main test
  fails before, and the control (other prompts unchanged) passes.
- **O1**, `e190d41` (+ `db7dc63`): `src/rnplens/doctor.py`.
  - A missing OPTIONAL component (matplotlib) is shown, with ACTION REQUIRED, its remedy, `"optional": true` and
    `summary.optional_not_ready`. It never makes the exit status non-zero; every required check still does.
  - The QA patch (sha256 `d9fc105af327c6dc581eac08ddf2456a021e4af0b562e888d1114db08cfb81a8`) was applied as written.
    Its test's first exit-status assertion was tautological and is tightened to `== 0`.
  - The docs are updated. The QA docs test that asserted the old exit-1 wording now encodes O1 (`db7dc63`).
  - The doctor's exit status is not used by this suite. The driver uses `doctor.agent_status()` (READY or not), which
    O1 does not change.

## 4. Payload bytes (premise check, karyon, real d1–d5, no model)

`premise_check_r2.py` was run unchanged, twice.
- **At `0d6fe84` (QA fixes only):** the record is byte-identical to the frozen `premise_check_r2_karyon.json`
  (sha256 `358ae79c…894a`). The six QA fixes change none of the 26 payloads.
- **At this amendment's code (`db7dc63`):** record `premise_check_a6_karyon.json`, sha256 `f71be2eae0cacebff3f4169361169a10ded57ba1d58eb44eb9b6728a8b129a89`.
  - 26 payloads; reconstruction equal for all 11 planner tasks; gate findings 0, `followup.privacy_check` findings 0,
    real names found 0.
  - The 4 follow-up payloads (L01 first call and replan, L09, L11) are byte-identical.
  - All 22 planner payloads (Z1, Z2, P01–P09; first call and replan) are 1,008 bytes longer.

Byte-by-byte account. Full payload texts were kept by a helper that reruns `premise_check_r2.main` unchanged in both
trees; the comparison ran on karyon.
- For every one of the 22 planner payloads, the payload at `db7dc63` equals the payload at `0d6fe84` with the old guide
  text replaced by the new one. The old guide occurs exactly once in each base payload, and the bytes before and after
  the guide are identical.
- The guide grows from 12,009 to 13,017 bytes (+1,008) in exactly three places:
  - line 11, the "Start here" Evaluate row: 264 → 346 bytes (+82);
  - lines 34–37, the three geometry rows and the `dockq.status`/`geometry.status` row: 573 → 959 bytes (+386);
  - new lines 51–56, a blank line and the five-line "Four-axis geometry is blocked." paragraph: +540 bytes (539 plus
    one line break).
- The question, the identifier listing, the reference line, the availability note and the replan feedback are
  unchanged.

**New expected payload table.** It replaces the Amendment 4/5 table in results/LIVE_QUALIFICATION_READINESS.md. The
gate is not changed.

| scenario | payload | bytes (Amendment 4/5 → 6) | previous sha256 | sha256 after Amendment 6 |
|---|---|---|---|---|
| Z1 | planner, first call | 17,846 → 18,854 | `00c44d0842561472…` | `f6a0b56983887f34cd07930cc4526e986fb77f416bafd8af323b68d8dc546590` |
| Z1 | planner, replan (scripted P9) | 18,616 → 19,624 | `68cbff3b66ee1e9e…` | `d62b9a38eb512223b7f2c50c00c2b04157274f35516373b178a6f93852402303` |
| Z2 | planner, first call | 17,846 → 18,854 | `6f6be02fba6eac9c…` | `e540a93281ed3ef15079e5c49f146594f3330e3d2fff7392a9b6c7d5bfd9e503` |
| Z2 | planner, replan (scripted P9) | 18,616 → 19,624 | `7f186a3d349c4ff6…` | `0393e3fa8b2e59886aca4d94d8bb69282d3fc62c11abb5caea12921658be978b` |
| P01 | planner, first call | 17,846 → 18,854 | `00c44d0842561472…` | `f6a0b56983887f34cd07930cc4526e986fb77f416bafd8af323b68d8dc546590` |
| P01 | planner, replan (scripted P9) | 18,616 → 19,624 | `68cbff3b66ee1e9e…` | `d62b9a38eb512223b7f2c50c00c2b04157274f35516373b178a6f93852402303` |
| P02 | planner, first call | 17,930 → 18,938 | `40b310292fd7662a…` | `b770f57fe3f0c121aa2a26d7ab8980b0daaaa13a986f201b97bb339c7f501def` |
| P02 | planner, replan (scripted P9) | 18,700 → 19,708 | `42fddd7e3c7a997a…` | `297a0388ee89c42a54f7a52f43c3df57cc2731bdd1066caab1945977cd23079d` |
| P03 | planner, first call | 18,184 → 19,192 | `fafb4dc4d1031ff7…` | `fbc499429414a8bcda35a228ec1941b3e5637da1eb2ab76b7b3785b5839f561f` |
| P03 | planner, replan (scripted P9) | 18,954 → 19,962 | `54dfe9880b86cc1c…` | `9f0560897b50ea6fa4514408f1bf77c0b9a5a1ddcf2ce29670921b35f6582e60` |
| P04 | planner, first call | 18,268 → 19,276 | `8cadc5698a1392b4…` | `32549b422ae2ef4eb53e762a7c429a5674d8363a4287f5bb9a62bbb8ddf013dc` |
| P04 | planner, replan (scripted P9) | 19,037 → 20,045 | `812f4f1eb14ed300…` | `60083e3b4308ad5e4aadf7c89803f07c08ff98e1a6a54bc782774d273763c07c` |
| P05 | planner, first call | 18,187 → 19,195 | `546976c876b273b5…` | `a4296f5b08703eb982448eb064a0df8d451c53845a5e05d0df6ff427185a2ce5` |
| P05 | planner, replan (scripted P9) | 18,957 → 19,965 | `986d1b09f38880b2…` | `60bc568e6ec661dc12d34a6a71f5965cb584cbec459a53a1f81f56797958cf14` |
| P06 | planner, first call | 18,297 → 19,305 | `9da5ef45d60575ff…` | `0f274f365646ffd5b391e7830c552059ec67b51984062839bcf6a871245c7b2b` |
| P06 | planner, replan (scripted P9) | 19,066 → 20,074 | `ee2514c8f76276b7…` | `69472751dbb883e7d334719d811f4c688dd546b85af80b0fc6220192274db613` |
| P07 | planner, first call | 18,171 → 19,179 | `0439a3fe6e39b3e4…` | `2d547b0628d3fcc613bdec8eeba6da3f2a38353ed56244652ada1861c90f4b1b` |
| P07 | planner, replan (scripted P9) | 18,941 → 19,949 | `0af6369e7ebd606c…` | `ffe4b209ff5c66a07dedc6b3369d4d9108bcc6ed5c28622d5488e77ab027459d` |
| P08 | planner, first call | 18,203 → 19,211 | `d59e71d01d73289a…` | `64a1ee6c2de2507801fa557b20c457ccbe0d5fde8b59f08eb5cda7e771e22a4a` |
| P08 | planner, replan (scripted P9) | 18,973 → 19,981 | `f041a24ab14d9ce9…` | `6f822d3ddadbfefd8f7a0bb47e74dbf9fe3a58f22bf2f3414750f9c21cef9ecb` |
| P09 | planner, first call | 17,917 → 18,925 | `9ed401758494522b…` | `48a843cccf908a81e0cef0cec13bf419d09e1c3585d57be8d5805ae42c39fd39` |
| P09 | planner, replan (scripted P9) | 18,687 → 19,695 | `3ba10d032d04e1c1…` | `f573f9b06c7d07b1748b512be73abec8676b907d7c20aa9329010cc5c5e4c06e` |
| L01 | follow-up | 7,866 → 7,866 | `0efe1e6a92b9123c…` | `0efe1e6a92b9123c3f3de2b443292387ef5f758f2cc6ba98b96f2703921d60f1` |
| L01 | follow-up replan | 8,257 → 8,257 | `393dbed3ea78fab4…` | `393dbed3ea78fab49c9740a363ede4a9cafd8be1215936e4db5bda5aa031c379` |
| L09 | follow-up | 7,258 → 7,258 | `2f2520876abfa086…` | `2f2520876abfa08621e285da8ec260b45b264e2887e382437ad8b799d92928a0` |
| L11 | follow-up | 7,296 → 7,296 | `399ac702a3e1fb0d…` | `399ac702a3e1fb0dd57caefcb661fa8aceae9720387d8523c04ee4337b99beda` |

## 5. Unchanged

- **Pins.** The other 15 of the 22 are unchanged: consent.py, codex_llm.py, policy.py, templates.py, gates.py,
  render.py, evidence.py, replay.py, llm.py, guide.py, registry.json, the three prompts and the jail.
- **Expectations.** No scenario, question, allowed-tool list, require entry, threshold, guard value, budget (max 24
  live calls, nominal 12), scoring or decision rule changed.
- **Suite files.** DESIGN.md, run_live.py, score_live.py, privacy.py, fake_codex.py, premise_check.py,
  premise_check_r2.py, both earlier premise records, AMENDMENT_1–5 and FOLLOWUP_SUITE_v1.
- **After the freeze.** The fake-Codex end-to-end runs (macOS, and karyon's real jail in a neutral-path clone) and the
  full suites run after this freeze. Their outcome is recorded in the readiness report, not here. An expectation that
  fails is reported, not edited in this amendment.

## Exact diffs of the three changes applied here (pinned files only; tests and docs are in the commits)

```diff
diff --git a/assistant/rnplens_assistant/docs/which_analysis_should_i_use.md b/assistant/rnplens_assistant/docs/which_analysis_should_i_use.md
index 7666111..7e3ae33 100644
--- a/assistant/rnplens_assistant/docs/which_analysis_should_i_use.md
+++ b/assistant/rnplens_assistant/docs/which_analysis_should_i_use.md
@@ -8,7 +8,7 @@ one score. Each tool answers a different question, and the outputs of different
 
 | what you have | use | what it tells you |
 |---|---|---|
-| a prediction **and** an experimental structure of the same complex | **Evaluate** | how close the prediction is: interface accuracy (DockQ, fnat, iRMSD, LRMSD), RNA shape, RNA placement and protein geometry, and whether the prediction could be evaluated at all |
+| a prediction **and** an experimental structure of the same complex | **Evaluate** | how close the prediction is: interface accuracy (DockQ, DockQ class, fnat, iRMSD, LRMSD) and whether the prediction could be evaluated at all; RNA shape, RNA placement and protein geometry (the four-axis geometry route) are blocked in this version, see below |
 | predictions **without** an experimental structure, from one or more engines or runs | **Report** | whether the outputs propose the same binding surface, the same residue–nucleotide contacts and the same RNA pose, and which alternative interface hypotheses exist |
 | several predictions **without** an experimental structure | **Diagnose** | whether each file is a usable protein–RNA complex, and where the predictions disagree (protein, RNA), relative to a frozen reference, within the validated conditions below |
 
@@ -31,10 +31,10 @@ separate. Evaluate is the only tool that measures correctness, and it needs an e
 | DockQ | Evaluate | yes | 0–1 | higher | interface accuracy; classes incorrect < 0.23 ≤ acceptable < 0.49 ≤ medium < 0.80 ≤ high |
 | fnat | Evaluate | yes | 0–1 | higher | fraction of experimental residue–nucleotide contacts reproduced |
 | iRMSD, LRMSD | Evaluate | yes | Å, ≥ 0 | lower | interface and ligand (RNA) RMSD of the DockQ calculation |
-| RNA internal C4′ RMSD | Evaluate | yes | Å, ≥ 0 | lower | RNA shape, after superposing the RNAs |
-| RNA placement C4′ RMSD | Evaluate | yes | Å, ≥ 0 | lower | where the RNA sits, after superposing the proteins |
-| protein internal Cα RMSD | Evaluate | yes | Å, ≥ 0 | lower | whole-construct protein geometry (includes domain arrangement; grows with length) |
-| `dockq.status`, `geometry.status` | Evaluate | yes | `SCORED` / `NO_VALUE` (DockQ); `COMPUTED` / `NO_VALUE` (geometry) | — | whether the value exists; the failing stage and reason are recorded |
+| RNA internal C4′ RMSD | Evaluate | yes | Å, ≥ 0 | lower | **blocked, not computed** (four-axis geometry route; correspondence defect, 2026-10-14). Definition: RNA shape, after superposing the RNAs |
+| RNA placement C4′ RMSD | Evaluate | yes | Å, ≥ 0 | lower | **blocked, not computed** (four-axis geometry route; correspondence defect, 2026-10-14). Definition: where the RNA sits, after superposing the proteins |
+| protein internal Cα RMSD | Evaluate | yes | Å, ≥ 0 | lower | **blocked, not computed** (four-axis geometry route; correspondence defect, 2026-10-14). Definition: whole-construct protein geometry (includes domain arrangement; grows with length) |
+| `dockq.status`, `geometry.status` | Evaluate | yes | `SCORED` / `NO_VALUE` (DockQ); `COMPUTED` / `NO_VALUE` / `BLOCKED` (geometry) | — | whether the value exists; the failing stage and reason are recorded. The geometry values are blocked in this version and are not computed. |
 | surface agreement | Report | no | 0–1 | — | weighted Jaccard overlap of the protein interface residues proposed by two outputs or engines |
 | register agreement | Report | no | 0–1 | — | weighted Jaccard overlap of the residue–nucleotide contacts (5 Å); stricter than surface agreement |
 | RNA pose difference | Report | no | Å, ≥ 0 | — | RNA C4′ RMSD between two outputs after superposing their proteins |
@@ -49,6 +49,12 @@ separate. Evaluate is the only tool that measures correctness, and it needs an e
 "—" means there is no better direction: high agreement is not evidence of correctness, and low agreement is not
 evidence of error.
 
+> **Four-axis geometry is blocked.** Evaluate's four-axis geometry route (protein-internal Cα RMSD, RNA-internal C4′
+> RMSD, RNA placement C4′ RMSD) is blocked because of a residue-correspondence defect found on 2026-10-14; its
+> values are not computed and must not be reported. DockQ, DockQ class, fnat, iRMSD and LRMSD remain available
+> under their own definitions (the DockQ calculation). They are not replacements for the four-axis decomposition:
+> iRMSD and LRMSD do not separate RNA shape, RNA placement and protein geometry.
+
 ## When is a Diagnose statement validated?
 
 Diagnose's statements were validated on particular inputs, and Diagnose checks every run against them. Outside
diff --git a/src/rnplens/assist.py b/src/rnplens/assist.py
index 47c1641..10438db 100644
--- a/src/rnplens/assist.py
+++ b/src/rnplens/assist.py
@@ -193,7 +193,7 @@ def parse_value(need, text, ctx):
     return t
 
 
-PROMPTS = {"rna_range": "RNA range (construct positions 1-{rna}, e.g. 40-60)",
+PROMPTS = {"rna_range": "RNA range (construct positions 1-{rna}, e.g. {rna_example})",
            "protein_range": "protein range (construct positions 1-{prot}, e.g. 10-30)",
            "two_runs": "two runs, comma-separated ({runs})", "runs": "runs, comma-separated ({runs})",
            "run": "one run ({runs})", "reference": "experimental reference structure file",
@@ -205,7 +205,9 @@ def prompt_text(need, ctx):
     man = ctx["manifest"]
     runs = ", ".join("%d=%s" % (i + 1, r["run"]) for i, r in enumerate(man["runs"]))
     base = PROMPTS.get(need, need.replace("_", " "))
-    return base.format(rna=man["construct"]["rna_length"], prot=man["construct"]["protein_length"], runs=runs)
+    rna = man["construct"]["rna_length"]
+    example = "1-%d" % min(int(rna), 20) if isinstance(rna, int) and rna >= 1 else "1-20"   # always inside the construct
+    return base.format(rna=rna, prot=man["construct"]["protein_length"], runs=runs, rna_example=example)
 
 
 def collect(cap, ctx, given, ask=None, out=print):
diff --git a/src/rnplens/doctor.py b/src/rnplens/doctor.py
index 94ab0ea..44650cf 100644
--- a/src/rnplens/doctor.py
+++ b/src/rnplens/doctor.py
@@ -192,10 +192,12 @@ def check_dependencies(env):
     for name, minimum, purpose in OPTIONAL:
         got = env.dist_version(name)
         if got is None:
-            out.append(_c("dep_" + name, "Optional %s" % name, ACTION, "not installed (optional: %s)" % purpose,
-                          "only if you want images: pip install 'rnplens[html]'"))
+            c = _c("dep_" + name, "Optional %s" % name, ACTION, "not installed (optional: %s; no scientific result "
+                   "depends on it)" % purpose, "only if you want images: pip install 'rnplens[html]'")
         else:
-            out.append(_c("dep_" + name, "Optional %s" % name, READY, "%s (%s)" % (got, purpose)))
+            c = _c("dep_" + name, "Optional %s" % name, READY, "%s (%s)" % (got, purpose))
+        c["optional"] = True        # policy: an optional component that is missing is shown, never a failure
+        out.append(c)
     return out
 
 
@@ -413,6 +415,7 @@ def run_checks(agent=False, project=None, out=None, env=None):
     if agent:
         checks += agent_checks(env, project)
     summary = {s: sum(1 for c in checks if c["status"] == s) for s in (READY, ACTION, UNSUPPORTED)}
+    summary["optional_not_ready"] = sum(1 for c in checks if c.get("optional") and c["status"] != READY)
     return {"record": "rnplens-doctor-1", "rnplens_version": __version__, "platform": "%s %s" % (env.system(), env.machine()),
             "agent_checked": bool(agent), "checks": checks, "summary": summary, "notice": NOTICE,
             "changes_made": "none: the doctor installs nothing, changes no setting and reads no credential file"}
@@ -430,7 +433,9 @@ def render(rec):
         if c["remedy"]:
             lines.append("  %-16s %-38s remedy: %s" % ("", "", c["remedy"]))
     s = rec["summary"]
-    lines += ["", "summary: %d READY, %d ACTION REQUIRED, %d UNSUPPORTED" % (s[READY], s[ACTION], s[UNSUPPORTED])]
+    lines += ["", "summary: %d READY, %d ACTION REQUIRED, %d UNSUPPORTED%s" % (
+        s[READY], s[ACTION], s[UNSUPPORTED], " (%d of them optional; exit status 0)" % s["optional_not_ready"]
+        if s.get("optional_not_ready") and s[ACTION] + s[UNSUPPORTED] == s["optional_not_ready"] else "")]
     if not rec["agent_checked"]:
         lines.append("Codex checks not run; 'rnplens doctor --agent' checks the optional natural-language mode. "
                      "The question menu (rnplens assist) needs no language model.")
@@ -464,4 +469,5 @@ def main(argv=None):
     print(json.dumps(rec, indent=1) if a.json else render(rec))
     if a.save:
         print("written: %s" % os.path.join(a.out, "doctor.json"), file=sys.stderr)
-    return 0 if rec["summary"][ACTION] == 0 and rec["summary"][UNSUPPORTED] == 0 else 1
+    blocking = [c for c in rec["checks"] if c["status"] != READY and not c.get("optional")]
+    return 0 if not blocking else 1
```
