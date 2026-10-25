# FREEZE: LIVE_QUALIFICATION_v1

Frozen 2026-10-16T20:10 UTC (2026-10-17 07:10 AEDT, Canberra), on branch track/codex-harness, base cf81acd, **before any run of this suite, mocked or live**.

**State at freeze.**
- No scenario has run, with the fake Codex or with the real one. The driver has not been executed; it was compiled (py_compile) and imported by the premise check only.
- No test of this suite exists yet. No Codex or other language-model call has been made by this track; the real `codex` binary was run only as `codex --version`.
- Maximum live calls: 24 (nominal 12), across all runs (ledger cap 24).
- Cut before freezing: Part F keeps L01, L09, L11 of FOLLOWUP_SUITE_v1 Part 2 and cuts L02-L08, L10, L12; prediction and mutation advice share P09.

**Pre-freeze premise check** (`premise_check.py`, result `premise_check_karyon.json`, run on karyon on the real development tasks; it builds payloads and runs the privacy gate, no scenario, no driver, no model, no Codex subprocess). It was run twice: on a draft, and again after the last pre-freeze edit (sys.path restore in `load_followup_suite`); both results are byte-identical (sha256 ee90858e07a8ce81eb54714485d5818144c284da04c089256643ce34dc92f17b).
1. The independently reconstructed first planning payload equals the assistant's own construction for all 11 planner payloads (Z1, Z2, P01-P09); 17.8-18.4 kB each.
2. The pre-send gate finds nothing in any of the 11 planner payloads and the 3 follow-up payloads (L01, L09, L11; 7.9-8.8 kB).
3. Observation, not changed: `followup.privacy_check` flags every planner payload with 'a reference file name found' (the documentation names .cif files and references). The planner's declared contract (assist.NL_PRIVACY) sends file names and reference file names; the follow-up's does not. This suite applies the planner's declared contract to planner payloads and the follow-up's to follow-up payloads; the difference is reported in the readiness note for the owner.

run_live.py refuses to run if any hash below differs, if any other file exists in this folder outside `results/`, or if a referenced FOLLOWUP_SUITE_v1 file or a pinned source (scenarios.json `pinned_sources`) changed.

**Amendment 1** (frozen 2026-10-17, after mocked test run 1 and before run 2). See AMENDMENT_1.md. It makes the first call's 'before' reading a full reading of the owner-stated baseline in `Guard.__init__`; no scenario, expectation, threshold or scoring rule changed. The hashes below are the post-amendment hashes. The original hash of run_live.py was 239a0fb68a37af548522b8c8271da6f486d7479ee1b05a6fdc19e5eed5be6a3d; all other files are unchanged.

**Amendment 11** (owner-approved; approval record records/native_platforms/LQ_AMENDMENT_11_APPROVAL.md; branch staging/r3-installation-folder-rule on 53711d496bd7cc6c6b7dfac308f8ba345d4a1df4, before any run of this suite at this head, mocked or live). See AMENDMENT_11.md. It re-pins assistant/rnplens_assistant/codex_adapter/codex_jail.sh after the installation-folder correction for release defect R3.

**Amendment 10** (owner-approved; approval record records/native_platforms/LQ_AMENDMENT_10_APPROVAL.md; branch dev/0.4-integration on db464e774fb31d09b531fb25ed9ebb8dce0eb433, before any run of this suite at this head, mocked or live). See AMENDMENT_10.md. It re-pins assistant/rnplens_assistant/codex_llm.py, src/rnplens/doctor.py and assistant/rnplens_assistant/replay.py after the launch-boundary and replay-integrity corrections.

**Amendment 9** (owner-approved; approval record records/native_platforms/LQ_AMENDMENT_9_APPROVAL.md; branch dev/0.4-native-platforms on 4f448612d983a5c799bb2a14e93b88c62b3d1534, before any run of this suite at this head, mocked or live). See AMENDMENT_9.md. It re-pins assistant/rnplens_assistant/codex_llm.py and src/rnplens/doctor.py and pins the new assistant/rnplens_assistant/confine.py after the native-platforms change.

**Amendment 8** (2026-10-19, owner-approved; rc/0.4-candidate on 8c64601, before any run of this suite at this head, mocked or live). See AMENDMENT_8.md. The confirmation file becomes a call-specific authorisation: it must name 18 bound values (experiment, mode, run id, scenario, task, target, task content digest, commit, model, reasoning effort, model-visible payload sha256, registry, jail, FREEZE.md, codex, bwrap and python sha256, maximum model calls); run_live.py recomputes each before anything is created or called and refuses a missing, wrong or extra field or reuse for another experiment, and the guard checks the sent payload and the call count before each call. No pinned source, scenario, expectation, threshold, budget or scoring rule changed. The previous hash of run_live.py was 173d266e78bb33431585ba696042f9e9c621b74b8987239ba097ab52d39cd184; scenarios.json is unchanged.

**Amendment 7** (2026-10-19, owner-approved; RNPLens 0.4 release candidate, rc/0.4-candidate on c5422ba, before any run of this suite at this head, mocked or live). See AMENDMENT_7.md. It re-pins src/rnplens/assist.py after commit 414b5e4 (result links: the menu and the natural-language mode list the contact tables and the offline Mol* page; verified diff 19+/2-). The premise check at c5422ba reproduced premise_check_a6_karyon.json byte for byte (26 payload hashes unchanged). No scenario, expectation, threshold, budget or scoring rule changed. The previous hash of scenarios.json was 58b0a40b3b6b08bd8636872012d7f5e6e26e9b22eb0d8bda45ad1d7e54871dce; all other suite files are unchanged.

**Amendment 6** (2026-10-18, QA round of RNPLens 0.4, on qa/lq-amendment6 from 0d6fe84, before any run of this suite at this head, mocked or live). See AMENDMENT_6.md. It re-pins seven sources: ask.py, followup.py, redact.py, tools.py, src/rnplens/assist.py and src/rnplens/doctor.py after the QA agent-security fix round, plus the guide copy (P3: four-axis geometry route blocked), src/rnplens/assist.py (U3: menu RNA-range example) and src/rnplens/doctor.py (O1: a missing optional component never makes the exit status non-zero). It adds premise_check_a6_karyon.json: the 22 planner payloads change only by the new guide text (+1,008 bytes each, accounted byte by byte); the 4 follow-up payloads are unchanged; gate 0, real names 0. No scenario, expectation, threshold, budget or scoring rule changed. The previous hash of scenarios.json was fed98b0d1f1f743bf0966ff1971641ae3da28be6a192e666a3a962529ecf7f06; all other suite files are unchanged.

**Amendment 5** (2026-10-17, round 3, on track/codex-harness-r3 from 14faecd, before any run of this suite at this head, mocked or live). See AMENDMENT_5.md. It re-pins src/rnplens/assist.py (menu exit status: BLOCKED capability 5, refusal 4) and assistant/rnplens_assistant/followup.py (evidence hash definition rnplens.followup.evidence.2, replay under the recorded definition, portability check before replay), both approved by the owner for the 0.4 branch. The premise check at 14faecd reproduced the frozen premise record byte for byte (26 payload hashes unchanged). No scenario, expectation, threshold, budget or scoring rule changed. The previous hash of scenarios.json was 64c1fbd77b31c39e7f42365e7b809183d70db0ba3ccf320aba41b21991ae741f; all other suite files are unchanged.

**Amendment 4** (2026-10-17, owner decision note item 2, on track/codex-harness-r2 from b3374e4, before any run of this suite, mocked or live). See AMENDMENT_4.md. The planner and follow-up payloads carry opaque identifiers instead of file, folder, run, sample and reference names (product commit fd79c75); the H1 reconstruction and the pre-send gate (all real names forbidden) follow it; a hard spending block is accepted as the alternative precondition; --continue-after-first needs the owner's go-ahead file quoting the first-call digest. It re-pins ask.py, followup.py, consent.py and src/rnplens/assist.py and pins redact.py; it adds premise_check_r2.py and its karyon record premise_check_r2_karyon.json. No scenario, expectation, threshold, budget or scoring rule changed. Previous hashes: run_live.py 473d66d9b50afba58cf844c99d4a47f5a108e7ab7ed944109afe56efc2ff4aa5, scenarios.json 87a29cb524a1e32aaf88f3a32caabfd914f843a6f918bd73f1c1cc02b976e2b1; all other suite files are unchanged.

**Amendment 3** (2026-10-17, integration, before any live run). See AMENDMENT_3.md. It re-pins assistant/rnplens_assistant/codex_llm.py after the unique-call-folder fix. The previous hash of scenarios.json was de2b7cdb5ad176219ef07d3fddeba368b09276d657a36408adf36667f3fd820b.

**Amendment 2** (2026-10-17, integration commit after 4628da8, before any live run). See AMENDMENT_2.md. It moves the pins of src/rnplens/assist.py and src/rnplens/doctor.py to their integration versions (message strings only). The previous hash of scenarios.json was 036a72cb35ba6d0424b1c8d9b4f079c08e7c4c2ebdc4d3cfb0db6b7e4f0c6abd; all other suite files are unchanged.

| file | sha256 |
|---|---|
| `AMENDMENT_11.md` | `c1a87826b2daa9cd9e2734e2a70f9e47221e0b0b9ec9691a27dd7723ebae7242` |
| `AMENDMENT_10.md` | `6b346bbcdb8aa35566b632349de785945197d42be60e3969ca1b56758454d17b` |
| `AMENDMENT_9.md` | `4b4f0b973288b7a8d073fb916e12bd9a7b743716b60f486be489aed255857f5b` |
| `AMENDMENT_8.md` | `a17cf32382a772d2b7ff08cf63f19c945897659e96bbed8a89fec7a61657ae6d` |
| `AMENDMENT_7.md` | `a4310b8eed057bf78870697a42cb5a102f9fa43f58f7ffc1118eb0b022513095` |
| `AMENDMENT_6.md` | `a0ded748cfae110cbce7d82670ef9b34e9de766af1c76bc144cdecd3e3863fcf` |
| `AMENDMENT_5.md` | `d2f0aabdf8a01a631b2be3778a73fdef40926095ff2058478be8549d13bde15f` |
| `AMENDMENT_4.md` | `56516446d6dfe1eb2ae359e4ff735ba68b13c394d4b62525509a4cb53542d923` |
| `AMENDMENT_3.md` | `111cb758b735d3db7928055e02177fcba45d05f5cdee0159840a661d437fdddb` |
| `AMENDMENT_2.md` | `5ad9b427bbd1ebf33222dba9e4e61050091073e494986bfeb20fc63e9c7f760a` |
| `AMENDMENT_1.md` | `c5c33ea1d780a43cab6b25fe1c20f1ad199c4ddad25773861ba33b51dd2e5d19` |
| `DESIGN.md` | `f002cd1e642d4212afc781abd125802f069598f1f7f5de3e2f56daf4235b77fd` |
| `fake_codex.py` | `3a1736f8a113374c67455bd269d3ccde8434fa6524325520b197f6f96dbdc9a6` |
| `premise_check.py` | `3b38bc8b2d0f1dde600981396792441f1e975face8ac8214fcc1569b3ee1e32a` |
| `premise_check_a6_karyon.json` | `f71be2eae0cacebff3f4169361169a10ded57ba1d58eb44eb9b6728a8b129a89` |
| `premise_check_karyon.json` | `ee90858e07a8ce81eb54714485d5818144c284da04c089256643ce34dc92f17b` |
| `premise_check_r2.py` | `917e7ce859c8d8effbf36f1dda4415347cee55468d6c292578f1e6005d68aba3` |
| `premise_check_r2_karyon.json` | `358ae79ce8f5ee6777cd9506a3267ee70d6dbcf85f586b1d9bd395ff2ddc894a` |
| `privacy.py` | `a940f93004251d3ffca2c1a44ef05ff8ce4eaf2650b9e0b5d6536b4bddbb7b5f` |
| `run_live.py` | `015a75452c64223e79cb0a88676178bc2dd1cfe62c44f524f2feae10b1c3f440` |
| `scenarios.json` | `f21785c9a1b6e19c88a4cfeb26dfb425287f8e3bd8168e3e72ec43a72d738266` |
| `score_live.py` | `991994db31a5d348d86aa0f9d54e35992a9021af45827365b8abafd116965d8c` |
