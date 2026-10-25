# LIVE_QUALIFICATION_v1: readiness for the bounded live Codex qualification (2026-10-17, Canberra)

> **QA round update (18 Oct 2026; branch `qa/lq-amendment6` from QA head `0d6fe84`).**
> - **Amendment 6** (`../AMENDMENT_6.md`, frozen in `53ae1b8` before any run at this head) re-pins seven sources:
>   - the six changed by the QA agent-security fix round (ask.py, followup.py, redact.py, tools.py,
>     src/rnplens/assist.py, src/rnplens/doctor.py);
>   - plus P3 (guide: four-axis geometry blocked), U3 (menu RNA-range example) and O1 (optional component never fails
>     the doctor's exit status).
> - The expected payload table below is replaced: the 22 planner payloads gain the guide's +1,008 bytes; the
>   follow-up payloads are unchanged.
> - The preconditions are unchanged:
>   - the owner confirms automatic reload is off AND explicitly accepts the residual one-call risk, or a verified hard
>     spending block is in place;
>   - one call, then owner inspection and the go-ahead file;
>   - never 22–24 October (Canberra).
> - The first live call is **not authorised**. Still PREPARED, NOT RUN. Results are in the section "QA round" at the
>   end.
>
> **Round 3 update (17 Oct 2026; branch `track/codex-harness-r3` from integration head `14faecd`).**
> - **Amendment 5** (`../AMENDMENT_5.md`, frozen in `4638f89` before any run at this head) re-pins
>   `src/rnplens/assist.py` (menu exit status: BLOCKED capability 5, refusal 4) and
>   `assistant/rnplens_assistant/followup.py` (follow-up evidence hash definition 2). The owner approved both fixes.
> - The premise check at `14faecd` reproduced the frozen payload record byte for byte: all 26 payload sha256 values in
>   the table below are unchanged.
> - The preconditions are unchanged:
>   - the owner confirms that automatic reload is off AND explicitly accepts the residual one-call risk, or a verified
>     hard spending block is in place;
>   - one call is made, then the owner inspects it and writes the go-ahead file;
>   - never from 2026-10-21 22:00 to 2026-10-25 02:00 Canberra time.
> - **The owner has not authorised the first live call** (owner note, 17 Oct 2026). Still PREPARED, NOT RUN.
> - Results and deviations are in the section "Round 3" at the end.
>
> **Round r2 update (17 Oct 2026, owner decision note item 2; branch `track/codex-harness-r2`, base `b3374e4`).**
> - **Amendment 4** (`../AMENDMENT_4.md`), frozen before any run of this suite, mocked or live: the planner and the
>   follow-up now send opaque identifiers instead of file, folder, run, sample and reference names.
> - The launch now goes **one call, then the owner inspects**. The rest of the run needs a second owner file (the
>   go-ahead).
> - The precondition is now *automatic reload off AND explicit acceptance of the residual one-call risk*, OR *a
>   hard spending block*.
> - The sections "Owner's preconditions", "Exact launch commands" and "Payload privacy (Amendment 4)" below are the
>   current instructions. FREEZE.md after Amendment 4 is the version committed in `6360cdd`.
> - Still PREPARED, NOT RUN: no Codex or other language-model call has been made.

> **Integrator's note (17 Oct 2026).** After the tracks were merged, Amendment 2 (`../AMENDMENT_2.md`) re-pinned `src/rnplens/assist.py` and `src/rnplens/doctor.py` to their integration versions (message strings only). FREEZE.md had sha256 `d6d90a91b446e8a5b8d35bac9bee70b5d76d24236eab7b18b69435aac93373b1` after Amendment 2; after Amendment 3 (`../AMENDMENT_3.md`, unique CodexClient call folders, re-pin of codex_llm.py) it is `04e56cfad909928625ab266edc4278029338e7873022a6510f5d86608bb973a1`; the `2072f362…` value cited below is the pre-amendment freeze. Launch from the integration checkout at the release HEAD recorded in the release manifest. The mocked tests pass after the amendment (33 passed, 2 karyon-only skipped, macOS).


**Status: PREPARED, NOT RUN.** No Codex or other language-model call has been made. The real `codex` binary was run
only as `codex --version`, which on karyon reports `codex-cli 0.159.3`. Every test used a fake codex binary.

RNPLens 0.4 stays a development candidate. Nothing has been merged, tagged, pushed or released.

## What was prepared

| item | where |
|---|---|
| design, scenarios, scoring, decision rule | `LIVE_QUALIFICATION_v1/DESIGN.md`, `scenarios.json`, `score_live.py` |
| pre-send privacy gate | `privacy.py` |
| driver with every guard (`--plan`, `--first-call`, `--continue-after-first`) | `run_live.py` |
| fake Codex CLI, for tests only | `fake_codex.py` |
| pre-freeze premise check and its result | `premise_check.py`, `premise_check_karyon.json` |
| freeze record and amendments | `FREEZE.md`, `AMENDMENT_1.md` … `AMENDMENT_4.md` |
| premise check r2 (redacted payloads) and its karyon record | `premise_check_r2.py`, `premise_check_r2_karyon.json` |
| tests (39 after Amendment 4) | `assistant/tests/test_live_qualification.py` |

### Commit order on `track/codex-harness` (base `cf81acd`)

1. **`206d7d7`** freezes the suite. FREEZE.md lists the sha256 of every file. At this point no run had been made,
   mocked or live, and no test of the suite existed.
2. **Mocked test run 1** ran on the frozen code: 15 of 35 tests failed.
   - 14 failures share one driver defect: the first call's "before" reading was the bare baseline record, so every
     first call would have been refused as USAGE_UNREADABLE.
   - 1 failure was a defect in the test itself.
3. **`a272932`** is Amendment 1, committed before run 2. It is a five-line fix in `Guard.__init__`, and the suite was
   re-frozen. No scenario, expectation, threshold or scoring rule changed.
4. **`d2323c2`** adds the tests. Three fixes went into test code only:
   - the run-folder assertion;
   - a call-folder counter that also counted the fake session-log date folders;
   - fixture follow-up replies that the follow-up policy rejected.
5. This report sits in `results/`, which the freeze excludes by design.

The final FREEZE.md has sha256 `2072f3622ad49dfb7384b61fa359c5c6c2cb3275d5cf8d76eb1536a68712ecbe`. The per-file
table is in FREEZE.md.

## Maximum number of live calls

The run makes **at most 24 calls; nominal 12**.
- Each of the 9 natural-language planner scenarios (P01–P09) and the 3 follow-up scenarios (F-L01, F-L09, F-L11) makes
  one planning call. At most one replan follows a policy rejection.
- Z1, Z2, the P01 follow-up and every replay make no call.

The same cap of 24 holds **across all runs**. Every call attempt is appended to
`scratch_agent/v04/codex_calls_live/LEDGER.jsonl`, and once the ledger holds 24 attempts the driver refuses any further
call.

**Cut before freezing to stay within 24** (recorded in FREEZE.md):
- Part F keeps FOLLOWUP_SUITE_v1 L01, L09 and L11.
- Part F cuts L02, L03, L04, L05, L06, L07, L08, L10 and L12.
- Prediction and mutation advice share one planner scenario (P09).

FOLLOWUP_SUITE_v1 itself is unchanged, and its Part 2 verdict stays NOT RUN.

## Owner's preconditions

All of these must hold before the first command.
1. **Either (A)** in ChatGPT → Settings → Usage (or Codex → Usage & Billing), **automatic credit reload is OFF** and
   you explicitly accept the residual risk that the one first call may draw on an existing credit balance (turning
   reload off does not prevent the use of credits you already hold); **or (B)** a **hard spending block** prevents
   any use of credits by the account. (A) uses the token `I_CONFIRM_AUTO_RELOAD_OFF_AND_ACCEPT_ONE_CALL_RISK`, (B)
   the token `I_CONFIRM_HARD_SPENDING_BLOCK`; the driver refuses a token that does not match the statement in the
   confirmation file (Amendment 4).
2. You will inspect the first call's result, model identity, usage and balance before authorising anything else,
   and you will write the go-ahead file (below) only if all are as expected.
3. On that same screen, you have just read the **current credit balance** and the **weekly usage percent**.
4. The Canberra date is **not 22–24 October**. The driver refuses from 2026-10-21 22:00 to 2026-10-25 02:00 Canberra
   time, which adds a two-hour margin on each side.
5. `rnplens doctor --agent` is READY on karyon. It lists `gpt-6.1-sol`, and the jail self-probe passes. On karyon the
   standalone Codex is installed at `~/.codex/packages/standalone/current/bin/codex`, which `~/.local/bin/codex` links
   to.
6. The run starts from a **committed checkout**, with no uncommitted change under `src/` or `assistant/`.
   - FREEZE.md and the pinned sources must match in that checkout. The pinned sources are the prompts, `ask.py`,
     `followup.py`, `policy.py`, `tools.py`, `codex_llm.py`, the jail script, `doctor.py` and `assist.py`.
   - If another track changes a pinned file before the run, the driver refuses. A dated amendment that re-pins it
     must then be committed first.
7. Neither `OPENAI_API_KEY` nor any other API-key or API-base variable is set, and `RNPLENS_CODEX_CALLS` is unset.

Write the confirmation file **on the day of the run**, anywhere outside the repository. Every line is required, and
the statement must be copied exactly:

```
RNPLens LIVE_QUALIFICATION_v1 owner confirmation
date: 2026-10-NN
statement: I confirm that automatic credit reload is OFF for the ChatGPT account used by Codex on this machine, and I accept the residual risk that one call may use existing credits.
credit_balance: <the balance exactly as shown, digits only, e.g. 0 or 12.50>
weekly_usage_percent: <the weekly usage as shown, e.g. 23>
```

For alternative (B) the statement line is instead:

```
statement: I confirm that a hard spending block prevents any use of credits by the ChatGPT account used by Codex on this machine.
```

## Exact launch commands (on karyon)

Run these from a checkout that contains `track/codex-harness-r2` (Amendment 4), either after the integrator merges
it or, until then, from the track clone `RNPBench/RNPLens_dev_0.4/tracks/lq-harness-2/RNPLens` (its path contains no
"codex"; see the deviations). Replace the `cd` path accordingly. For alternative (B) replace the token value with
`I_CONFIRM_HARD_SPENDING_BLOCK` in both commands.

**0. Plan only.** No call is made and nothing is written.

```
cd /home/jwen/projects/RNPBench/RNPLens_dev_0.4/RNPLens && PYTHONPATH=$PWD/src:$PWD/assistant \
/home/jwen/projects/RNPBench/RNPLens_dev_0.3/venv/bin/python assistant/evaluation_v04/LIVE_QUALIFICATION_v1/run_live.py --plan
```

**1. First call.** This makes exactly ONE live call (P01's planning call), then stops and prints the balance and usage.

```
cd /home/jwen/projects/RNPBench/RNPLens_dev_0.4/RNPLens && \
RNPLENS_LIVE_QUAL=I_CONFIRM_AUTO_RELOAD_OFF_AND_ACCEPT_ONE_CALL_RISK \
RNPLENS_CODEX_JAIL=$PWD/assistant/rnplens_assistant/codex_adapter/codex_jail.sh \
PYTHONPATH=$PWD/src:$PWD/assistant PATH=$HOME/.local/bin:$PATH \
/home/jwen/projects/RNPBench/RNPLens_dev_0.3/venv/bin/python assistant/evaluation_v04/LIVE_QUALIFICATION_v1/run_live.py \
  --first-call --run-id lq1-run1 --confirmation /home/jwen/owner_confirmation_lq1.txt
```

It ends with `STATE: PAUSED_AFTER_FIRST_CALL`, then
`credit balance: X (baseline Y)   weekly usage: U% (start S%)   model: gpt-6.1-sol`, then (Amendment 4):
- `FIRST CALL RESULT (P01): status …; hard criteria …; tool selection …; answer <path>/work/P01/nl/answer.md`;
- `model identity: gpt-6.1-sol (effort medium, Codex CLI 0.159.3)`, as returned by the call;
- "No further call is made", the go-ahead template, with this run's `first_call_digest` (16 hex characters) filled
  in, and the continue command.

Nothing continues automatically.

**Between the two commands (owner inspection):**
- Read the P01 result: `answer.md`, and `run_record.json` → `scenarios.P01`.
- Check the model identity line.
- Open Codex → Usage & Billing and check that the balance has **not changed** and that usage rose by no more than
  you expect.
- Continue only if all hold. Then write the **go-ahead file**, anywhere outside the repository. Every line is
  required; copy the statement exactly and the digest from the first command's output:

```
RNPLens LIVE_QUALIFICATION_v1 owner go-ahead
date: 2026-10-NN
run_id: lq1-run1
first_call_digest: <16 hex characters printed by the first command>
observed_credit_balance: <the balance as shown now; must equal the baseline>
observed_weekly_usage_percent: <the weekly usage as shown now>
statement: I have inspected the first call's result, model identity, usage and credit balance, and I authorise the remaining calls of this run.
```

The driver refuses to continue in any of these cases:
- the file is missing, or its header or statement differs;
- the date is not today in Canberra, or the run id is not this run;
- the digest does not match;
- the observed balance differs from the baseline;
- the observed weekly usage is more than 10 points above the start, or at 85 % or more;
- a line is unknown or repeated;
- the file was written before the first call completed.

If the date has changed, also write a new confirmation file with the new date and the **same** balance and usage
values.

**2. Continue.** This runs the remaining 11 scenarios strictly serially, with at most 23 further calls.

```
cd /home/jwen/projects/RNPBench/RNPLens_dev_0.4/RNPLens && \
RNPLENS_LIVE_QUAL=I_CONFIRM_AUTO_RELOAD_OFF_AND_ACCEPT_ONE_CALL_RISK \
RNPLENS_CODEX_JAIL=$PWD/assistant/rnplens_assistant/codex_adapter/codex_jail.sh \
PYTHONPATH=$PWD/src:$PWD/assistant PATH=$HOME/.local/bin:$PATH \
/home/jwen/projects/RNPBench/RNPLens_dev_0.3/venv/bin/python assistant/evaluation_v04/LIVE_QUALIFICATION_v1/run_live.py \
  --continue-after-first --run-id lq1-run1 --confirmation /home/jwen/owner_confirmation_lq1.txt \
  --go-ahead /home/jwen/owner_go_ahead_lq1.txt
```

Each command takes several minutes, because every scenario imports and analyses its task. Run them interactively, or
detached with `setsid … > log 2>&1 &`. Neither command prompts.

**Outputs**, all under `scratch_agent/v04/codex_calls_live/lq1-run1/`:
- `run_record.json`: the state, the confirmation hash and the baseline. For every call: the before and after
  readings, the payload hash, the privacy result and any error. Also every refused call, the scores and the verdict.
- `run_log.jsonl`.
- `sent/`: the exact bytes of every prompt.
- `calls/`: the Codex call folders and session logs.
- `work/`: the scenario folders.
- `results.json`.

The shared `LEDGER.jsonl` sits one level up.

## Payload privacy (Amendment 4)

What is sent:
- **Planner.** The question, the fixed prompt and documentation, and the task inputs as opaque identifiers:
  - `run_NNN/candidate_NNN` for structure files and `run_NNN/file_NNN` for other files;
  - `protein_sequence_NNN` and `rna_sequence_NNN`;
  - `reference_NNN` only if task.json declares a reference; otherwise the line reads "none".
- **Follow-up.** The evidence summary with `run_NNN`, `candidate_NNN`, `evidence_NNN` and `output_NNN`.
- `redaction_map.json` holds the real names. It is written next to each run record and is never sent.
- Real names never appear in a payload. A target ID typed by the user in a question is sent as typed (declared in
  NL_PRIVACY).

Verification of the exact payload bytes. **Expected values after Amendment 6**: record
`../premise_check_a6_karyon.json`, sha256 `f71be2eae0cacebff3f4169361169a10ded57ba1d58eb44eb9b6728a8b129a89`. The
Amendment 4/5 values (record `../premise_check_r2_karyon.json`, `358ae79c…894a`) are listed beside them in
AMENDMENT_6.md section 4.
- Run on karyon on the real development tasks with `../premise_check_r2.py`, using scripted capture clients only (no
  model, no Codex).
- The independent reconstruction equals the assistant's planner payload for all 11 planner tasks.
- The pre-send gate, with every real name forbidden, finds 0 in all 26 payloads. `followup.privacy_check` finds 0;
  its round-1 "reference file name found" flag on every planner payload is gone. The real-name scan finds 0.
- The 22 planner payloads differ from the Amendment 4/5 values only by the new guide text, +1,008 bytes each; this is
  accounted for byte by byte in AMENDMENT_6.md. The 4 follow-up payloads are unchanged.
- During the live run, H1 compares the sent bytes of every first planning call with the same reconstruction. With
  unchanged development tasks, P01's live planning payload (system, separator, user) is expected to be byte-identical
  to the P01 row below. The fake-Codex run through karyon's real jail at `53ae1b8` sent exactly these bytes (18,854,
  `f6a0b569…6590`).

| scenario | task | payload | bytes | sha256 |
|---|---|---|---|---|
| Z1 | d1_7K9D_agreement | planner, first call | 18,854 | `f6a0b56983887f34cd07930cc4526e986fb77f416bafd8af323b68d8dc546590` |
| Z1 | d1_7K9D_agreement | planner, replan (scripted P9) | 19,624 | `d62b9a38eb512223b7f2c50c00c2b04157274f35516373b178a6f93852402303` |
| Z2 | d1_7K9D_agreement | planner, first call | 18,854 | `e540a93281ed3ef15079e5c49f146594f3330e3d2fff7392a9b6c7d5bfd9e503` |
| Z2 | d1_7K9D_agreement | planner, replan (scripted P9) | 19,624 | `0393e3fa8b2e59886aca4d94d8bb69282d3fc62c11abb5caea12921658be978b` |
| P01 | d1_7K9D_agreement | planner, first call | 18,854 | `f6a0b56983887f34cd07930cc4526e986fb77f416bafd8af323b68d8dc546590` |
| P01 | d1_7K9D_agreement | planner, replan (scripted P9) | 19,624 | `d62b9a38eb512223b7f2c50c00c2b04157274f35516373b178a6f93852402303` |
| P02 | d1_7K9D_agreement | planner, first call | 18,938 | `b770f57fe3f0c121aa2a26d7ab8980b0daaaa13a986f201b97bb339c7f501def` |
| P02 | d1_7K9D_agreement | planner, replan (scripted P9) | 19,708 | `297a0388ee89c42a54f7a52f43c3df57cc2731bdd1066caab1945977cd23079d` |
| P03 | d3_1VTM_accuracy | planner, first call | 19,192 | `fbc499429414a8bcda35a228ec1941b3e5637da1eb2ab76b7b3785b5839f561f` |
| P03 | d3_1VTM_accuracy | planner, replan (scripted P9) | 19,962 | `9f0560897b50ea6fa4514408f1bf77c0b9a5a1ddcf2ce29670921b35f6582e60` |
| P04 | d4_24BR_compare | planner, first call | 19,276 | `32549b422ae2ef4eb53e762a7c429a5674d8363a4287f5bb9a62bbb8ddf013dc` |
| P04 | d4_24BR_compare | planner, replan (scripted P9) | 20,045 | `60083e3b4308ad5e4aadf7c89803f07c08ff98e1a6a54bc782774d273763c07c` |
| P05 | d2_1VTM_agreement | planner, first call | 19,195 | `a4296f5b08703eb982448eb064a0df8d451c53845a5e05d0df6ff427185a2ce5` |
| P05 | d2_1VTM_agreement | planner, replan (scripted P9) | 19,965 | `60bc568e6ec661dc12d34a6a71f5965cb584cbec459a53a1f81f56797958cf14` |
| P06 | d5_24BR_geometry | planner, first call | 19,305 | `0f274f365646ffd5b391e7830c552059ec67b51984062839bcf6a871245c7b2b` |
| P06 | d5_24BR_geometry | planner, replan (scripted P9) | 20,074 | `69472751dbb883e7d334719d811f4c688dd546b85af80b0fc6220192274db613` |
| P07 | d2_1VTM_agreement | planner, first call | 19,179 | `2d547b0628d3fcc613bdec8eeba6da3f2a38353ed56244652ada1861c90f4b1b` |
| P07 | d2_1VTM_agreement | planner, replan (scripted P9) | 19,949 | `ffe4b209ff5c66a07dedc6b3369d4d9108bcc6ed5c28622d5488e77ab027459d` |
| P08 | d2_1VTM_agreement | planner, first call | 19,211 | `64a1ee6c2de2507801fa557b20c457ccbe0d5fde8b59f08eb5cda7e771e22a4a` |
| P08 | d2_1VTM_agreement | planner, replan (scripted P9) | 19,981 | `6f822d3ddadbfefd8f7a0bb47e74dbf9fe3a58f22bf2f3414750f9c21cef9ecb` |
| P09 | d1_7K9D_agreement | planner, first call | 18,925 | `48a843cccf908a81e0cef0cec13bf419d09e1c3585d57be8d5805ae42c39fd39` |
| P09 | d1_7K9D_agreement | planner, replan (scripted P9) | 19,695 | `f573f9b06c7d07b1748b512be73abec8676b907d7c20aa9329010cc5c5e4c06e` |
| L01 | d1_7K9D_agreement | follow-up | 7,866 | `0efe1e6a92b9123c3f3de2b443292387ef5f758f2cc6ba98b96f2703921d60f1` |
| L01 | d1_7K9D_agreement | follow-up replan | 8,257 | `393dbed3ea78fab49c9740a363ede4a9cafd8be1215936e4db5bda5aa031c379` |
| L09 | d4_24BR_compare | follow-up | 7,258 | `2f2520876abfa08621e285da8ec260b45b264e2887e382437ad8b799d92928a0` |
| L11 | d5_24BR_geometry | follow-up | 7,296 | `399ac702a3e1fb0dd57caefcb661fa8aceae9720387d8523c04ee4337b99beda` |

Z1 and Z2 make no call; their rows show what would be sent.

Redacted excerpt (P04, d4_24BR_compare, first planning call, user part). The listing is copied from the record's
700-character excerpt. The final line was read from the same payload rebuilt on karyon (Amendment 4/5 sha256
`8cadc5698a1392b4c23af6805297fcb02490aa173201505e8fa479d542f00ca5`). Amendment 6 leaves this user part unchanged;
only the system part (guide) changed, so the P04 row above is now `32549b422ae2ef4eb53e762a7c429a5674d8363a4287f5bb9a62bbb8ddf013dc`:

```
Task inputs (22 files; opaque identifiers, the real names stay on this computer; use these identifiers as the paths in the plan):
run_001/candidate_001
run_001/candidate_002
run_001/candidate_003
run_001/candidate_004
run_001/candidate_005
run_001/file_001
run_001/file_002
run_001/file_003
run_001/file_004
run_001/file_005
run_002/candidate_001
run_002/candidate_002
run_002/candidate_003
run_002/candidate_004
run_002/candidate_005
run_002/file_001
run_002/file_002
run_002/file_003
run_002/file_004
run_002/file_005
protein_sequence_001
rna_sequence_001

Experimental reference supplied with this task: yes (reference_001); reference-based metrics are available
```

**Guide check.** `assistant/rnplens_assistant/docs/which_analysis_should_i_use.md` contains no filename or target ID
from the sealed evaluation. It names only RNPLens documents and outputs (report.json, quickstart.md,
interpretation.md, limitations.md, output_formats.md, cohortP_disagreement.tsv, cohortE_disagreement.tsv). The prompt
rules ("Use only paths that appear in the task inputs listing"; "Use run names, contact labels and evidence IDs
exactly as they appear in the summary") work unchanged with identifiers. No prompt or guide file changed.

## What stops the run

The driver never retries a call automatically and never resumes a run.

**Refused before anything is created (exit 3)** when any of these holds:
- the token is missing or wrong;
- the confirmation file is missing, not dated today, has a different statement, or has an unparseable balance or
  usage;
- the stated usage is at or above 85 %;
- the date falls inside the block;
- NTP is not synchronised, or the time zone is wrong;
- the freeze, a pinned source or the FOLLOWUP_SUITE_v1 freeze does not match;
- the git tree is dirty;
- the jail is not this checkout's;
- the model configuration is not `gpt-6.1-sol`/medium;
- an API-key variable or `RNPLENS_CODEX_CALLS` is set;
- the run id is bad or already exists;
- the lock is held;
- the ledger is exhausted;
- an earlier balance stop has not been acknowledged;
- `doctor --agent` is not READY;
- the encoding is not UTF-8.

**Refused before a call (exit 5; the run becomes ABORTED or STOPPED)** when any of these holds:
- the run has already stopped;
- it would be a second call in the first-call invocation;
- the call falls in a zero-call phase;
- the clock fails its checks, or the date has changed;
- the ledger cap is reached;
- the client's model does not match;
- files are attached to the call;
- the latest reading fails;
- the schema is unexpected;
- **the privacy gate finds something, or the bytes differ from the declared payload.** Nothing is sent in that case.

**Aborted after a call** when any of these holds:
- **the credit balance differs in any way** from the stated baseline;
- the balance or usage is missing or unparseable;
- weekly usage is more than 10 points above the start, or any window is at or above 85 %;
- a rate limit has been reached;
- the model is not `gpt-6.1-sol`;
- the call returned an error.

**On a hard-criterion failure**, the run stops. No further call is spent once the verdict is NOT_QUALIFIED.

**After a stop**, a new run needs a new `--run-id` and starts with its own first call. All calls of all runs count
against the 24-call ledger. After a balance stop, the confirmation must also contain `acknowledge_abort: <old run id>`.
If a crash leaves `codex_calls_live/LIVE.lock` behind, inspect the run and then remove the lock by hand.

## Mocked test evidence (no model; the real CodexClient driving a scripted fake codex)

### Test runs

| where | result |
|---|---|
| macOS, `assistant/tests/test_live_qualification.py` | 33 passed, 2 skipped (the karyon-only tests) |
| karyon, track clone at `d2323c2`, same file | **35 passed**, including both karyon tests |
| full suite, macOS, `d2323c2` | 574 passed, 19 skipped, 1 known failure (`test_report_numbers_equal_the_rc3_expected_output`, last-digit float); baseline at `cf81acd`: 541 passed, 17 skipped, the same failure |
| full suite, karyon, neutral-path clone `tracks/lq-harness-2/RNPLens` at `d2323c2` | **582 passed, 12 skipped** (= 547 + 35) |
| full suite, karyon, mandated clone `tracks/codex-harness-2/RNPLens` at `d2323c2` | 575 passed, 12 skipped, 7 failed; identical 7 failures at baseline `cf81acd` (540 passed) |

The 7 failures in the mandated clone are path artefacts of pre-existing tests (`test_assist.py`, `test_consent.py`,
`test_followup.py`, `test_followup_menu.py`). Those tests fail if any spawned subprocess argument contains the string
"codex". The mandated clone path `tracks/codex-harness-2/` contains it, so a `git -C <clone>/src/rnplens rev-parse`
call trips them. With a basetemp under `scratch_agent/v04/codex-harness-2/`, 6 more tests (`test_v04_menu_e2e.py`,
`test_assist.py`) fail for the same reason. Both runs therefore used basetemp and TMPDIR under
`scratch_agent/v04/lq-harness-2/`. The same commits in a clone at a path without "codex" pass in full.

The karyon tests keep everything real except the codex binary:
- the real `codex_jail.sh` (bubblewrap) and the real `rnplens doctor --agent`;
- the real clock, NTP and git checks;
- the real d1–d5 development tasks.

The fake binary was supplied through `RNPLENS_CODEX_BIN`, with a dummy `CODEX_HOME`. A trap `codex` placed first on
PATH proved that no real binary was reached.

### Full end-to-end pass on karyon

The run went from first call through continue, with scripted well-formed replies:
- **State:** COMPLETE, after 12 calls. The fake session logs report every call as `gpt-6.1-sol`.
- **Verdict:** `QUALIFIED_ON_DEVELOPMENT_CASES`. P tool selection 9/9, F C1/C2 3/3, no hard failure.
- **Replay:** every replay reproduced its evidence hash.
- **Privacy:** the gate was clean on every payload, and every payload was equal to its declared payload.

A second karyon test changed the balance after call 1 (12.50 → 12.40). The run aborted with CREDIT_BALANCE_CHANGED
after exactly one call, and the continue was refused.

### Paths covered on macOS (fake jail)

**Refusals:**
- missing or wrong token;
- a bad confirmation: date, statement, balance, usage ≥ 85 %, header, or an unknown line;
- the date block, including both margins;
- no NTP, a naive clock, or a clock earlier than the freeze;
- an API key set, or `RNPLENS_CODEX_CALLS` set;
- the wrong model configuration, a foreign jail, the doctor not READY, or a non-UTF-8 encoding;
- a dirty git tree, a FREEZE mismatch, an unlisted file, or a modified file;
- a missing task, a task without `development_only`, or a file named after an excluded target;
- a bad run id, an existing run id, a held lock, or an exhausted ledger;
- an unacknowledged balance stop, and the same run accepted once acknowledged;
- the command line without the token (exit 3, nothing created), and `--plan`.

**Continue refusals:**
- no run record;
- a run in state COMPLETE, ABORTED, RUNNING, STOPPED_DEFECT or FIRST_CALL_RUNNING;
- more than one call recorded;
- a first reading that fails;
- a different confirmation baseline.

**Aborts at call 1:**
- a balance drop;
- an unparseable balance, or missing credits;
- no rate-limit snapshot;
- the wrong model;
- a weekly usage rise, or weekly usage at 85 %;
- the 5-hour window at 90 %;
- a reached rate limit;
- a call failure, with no retry (the ledger shows 1 attempt).

**Mid-run stops and guard behaviour:**
- A usage jump at call 2 during the continue aborts the run, and P03 onward are not run. The run cannot be resumed; a
  new run id is allowed, and the ledger keeps counting.
- The first-call pause refuses a replan (INCOMPLETE_FIRST_CALL_PAUSE), and the ledger cap stops the run at exactly 24.
- A date change, or entry into the block, after preflight refuses the next call.
- The privacy gate refuses before sending: no call folder, no ledger entry, verdict NOT_QUALIFIED.
- A call outside any scenario is refused, as is a call in a zero-call phase or a call with no guard installed. The API
  client is blocked.

**Unit tests:**
- privacy-gate findings;
- scoring rules: positive and blocked scenarios, false refusal, replay mismatch, a follow-up call made without consent,
  required arguments, a rejected final step;
- verdict rules: 8 of 9, 7 of 8 when P01 is paused, a hard failure, an incomplete run, and a privacy failure inside an
  incomplete scenario.

## What a pass would license, and what it would not

**A pass (QUALIFIED_ON_DEVELOPMENT_CASES) licenses only this statement.** On the development tasks d1–d5 (7K9D, 1VTM,
24BR), with `gpt-6.1-sol` through Codex CLI 0.159.3 and the frozen code:
- the natural-language planner chose admitted tools in at least 8 of 9 scenarios;
- it refused ranking or selection, four-axis geometry, Diagnose interpretation, grouping used for selection,
  structure prediction and mutation advice;
- no payload carried coordinates, sequences, file content, reference content, absolute paths or secrets;
- every payload's bytes were exactly the declared ones;
- no follow-up call was made without an opt-in;
- the evidence replayed without any model.

**It does not license:**
- anything about scientific correctness;
- other targets, models or CLI versions;
- anything about the sealed assistant evaluation of 22–24 October, or the manuscript;
- a status change for the follow-up, which needs FOLLOWUP_SUITE_v1's full Part 2;
- a release.

The planner and the follow-up remain EXPERIMENTAL until the owner reviews the live result.

## Observations for the owner (nothing was changed for them)

1. **The planner sends file names and reference file names, by its declared design.** `assist.NL_PRIVACY` declares
   that the planner sends the question, the task's relative file names, the reference file names and the
   documentation, and the premise check confirmed exactly that. The follow-up's own `privacy_check` would flag every
   planner payload with "a reference file name found", because the follow-up contract never sends file names. Each
   path is therefore gated by its own declared contract. If reference file names should not leave the machine, that
   needs a change to `ask.py`/assist, which is outside this track.
2. **The balance cannot be read without a call.** The Codex CLI exposes the balance and usage only in each call's
   session log. The "before" reading for call 1 is therefore the value the owner states, and the comparison after
   call 1 is the first machine check. This is why the first invocation makes exactly one call.
3. **`codex_llm.CodexClient`'s own guard has two gaps.** It does not stop on a missing balance (None equals None), and
   it does not stop on a missing reported model. This driver enforces both. `codex_llm.py` was left unchanged because
   it is pinned for FOLLOWUP_SUITE_v1 and for the frozen evaluation path. A guarded fix would need its own tests and the
   integrator's decision.
4. **When `codex_llm`'s own 85 % guard fires inside a call, the stop kind is recorded as CALL_FAILED.** The detail
   still carries the underlying reason (for example USAGE_CEILING), and the run stops either way.

## Addendum (2026-10-17): integration findings at `ec3d467`, fixed in tests at `246b063`

No frozen file changed. FREEZE.md is still the integrator's Amendment 2 version, and no Amendment 3 was needed.

### Finding 1: `test_first_call_pause_refuses_a_second_call_and_ledger_cap_stops` stopped with HARD_CRITERION, not BUDGET

**What happened.** The run record left by the integration run
(`final_ec3d467/tmp_pytest/bt/test_first_call_pause_refuses_0`) shows the sequence:
- P02's `rnplens assist --nl` raised `FileExistsError` on `calls/assist_085243_20261017T085243_3542781` before any
  subprocess started.
- P02 was therefore scored H4 = false, and the run stopped as a defect.
- The P01 call, the first invocation, the ledger padding and the continue all fall in the same UTC second (21:52:43),
  in one pytest process.

**Cause.** This is a latent assistant defect in `codex_llm.CodexClient`, not a defect of the guard or the scoring:
- The client names its call folder `<tag>_<YYYYmmddTHHMMSS>_<pid>`, so the name has one-second resolution.
- The natural-language tag is `assist_HHMMSS`.
- Two clients created in the same second in one process therefore collide.

**Why the test exposed it.** The test's fake calls had zero latency, and at `ec3d467` the setup between the two
clients took less than a second.

**What it does not depend on.** The merged doctor message strings and the replay canonicalisation do not cause it,
nor does test order. Which merged change made the setup faster was not established.

**Effect on a live run.** In a live run, the next planner client in the same process is created only after the
previous scenario's real call, which takes seconds. A collision would also fail before any subprocess starts, so it
cannot spend a call.

**Fix (tests only).**
- Fake calls now take about 1 s, as real ones do.
- A strict-xfail test (`test_codexclient_folder_name_has_one_second_resolution`) records the collision. It will
  report XPASS once `codex_llm` is fixed.
- `codex_llm.py` is unchanged: in this track it may change only for a missing guard, and this is not one.
- Recommendation for the integrator: make the folder name unique, for example with a counter or a random suffix.

### Finding 2: clean installs failed the two karyon tests and step 51

**What happened.**
- `test_command_line_refuses_without_token_and_plan_makes_no_call` set `PYTHONPATH` to the source tree for its
  subprocess. That subprocess imported `rnplens_assistant` from the source tree and left the two `.pyc` files.
- The two karyon tests require this checkout's jail. The harness is a repository tool, so in installed mode its
  preflight correctly refuses a site-packages jail.

**Fix (tests only).**
- The command-line test now passes the import path of the test process itself.
- The karyon tests skip when `rnplens` and `rnplens_assistant` are not imported from this checkout.

### Results at `246b063`

| run | result |
|---|---|
| local macOS, full suite | 603 passed, 19 skipped, 1 xfailed, 1 known failure (last-digit float) |
| karyon neutral-path clone, full suite | 611 passed, 12 skipped, 1 xfailed |
| karyon mandated clone, full suite | 604 passed, 12 skipped, 1 xfailed, 7 failed |
| clean installs (wheel, sdist, docs), each | 609 passed, 14 skipped, 1 xfailed |

The 7 failures in the mandated clone are the known path artefacts: its path contains "codex". The neutral-path clone
holds the same commits.

In the clean installs, step 51 passed, with 0 `.pyc` files under the source tree. The other non-zero steps are the
same as in the integration run: 32/33, where `doctor --agent` reports ACTION REQUIRED in a bare venv, and 21, which is
expected to exit 3.


## Round r2 (2026-10-17): owner item 2, privacy redaction before any live call

### Commits on `track/codex-harness-r2` (base `b3374e4`, which is not rewritten)

1. `fd79c75`: product. `redact.py` (new); `ask.py`, `followup.py`, `consent.py` and `src/rnplens/assist.py`
   (NL_PRIVACY); `docs/setup_and_privacy.md`, `docs/followup.md`; tests, including the new
   `assistant/tests/test_redaction.py`.
2. `80e4e6a`: suite, pre-freeze draft of Amendment 4, together with `premise_check_r2.py`. The driver refuses to run
   at this commit (FREEZE mismatch). The premise check r2 ran on karyon at this commit.
3. `6360cdd`: **Amendment 4 frozen** (AMENDMENT_4.md, FREEZE.md, premise record), before any run of the suite,
   mocked or live.
4. `9ffe107`: mocked tests of the suite (identifier-form fake replies; go-ahead; precondition B; real names).
5. `445979b`: two misses found by the full suite, then fixed:
   - the region fixture builder in `tests/` still scripted a real-path plan;
   - my docs edit had dropped the sentence "never sends atomic coordinates, sequences, or any computed value"
     (restored), and the follow-up table row still said "run and structure names" (corrected).
6. `747c931`: a defect in my own karyon-only test. Its real-name set included the plain stems `protein`, `rna` and
   `reference`, which are ordinary words of the documentation. It now uses name-like stems only, as the declared
   rule does.
7. This report.

### Test results (fake Codex only; no model call)

| where | commit | passed | failed | skipped |
|---|---|---|---|---|
| macOS, `tests assistant/tests` | `747c931` | 609 | 2 | 30 |
| macOS, same invocation and environment | `b3374e4` (base) | 600 | 2 | 22 |
| karyon, neutral clone `tracks/lq-harness-2/RNPLens` | `747c931` | 629 | 0 | 12 |
| karyon, mandated clone `tracks/codex-harness-2/RNPLens` | `747c931` | 622 | 7 | 12 |

- **macOS, the 2 failures.** They are identical at the base in this environment, so they predate this round:
  - `test_output_schemas::test_fresh_outputs_match_schema` (`rnplens: command not found`: the CLI is not on PATH in
    this source-tree environment);
  - `test_workflow_analyse::test_report_numbers_equal_the_rc3_expected_output` (an rc3 float differs in the last
    digits on macOS).
  - The base figure recorded earlier (604 passed, 1 failed, 19 skipped) was measured in a different environment.
- **macOS, the skips.** Of the 8 extra skips, all are the karyon-only real-task tests of `test_redaction.py`.
- **Karyon, mandated clone, the 7 failures.** They are the known artefacts of a checkout path containing "codex":
  - `test_assist::test_menu_never_uses_a_language_model_or_the_network`;
  - the 3 `test_consent::test_without_consent_no_client_and_no_codex_subprocess` cases;
  - `test_followup::test_local_follow_up_worked_example_and_replay`;
  - the 2 `test_followup_menu` fallback tests.
- **Karyon, neutral clone.** It has none of them. Its count includes the real-jail fake-Codex end-to-end run, now
  with a go-ahead file, and the 8 real-task redaction tests (14 of 14 pass on karyon).
- FOLLOWUP_SUITE_v1 Part 1: 21/21, frozen files unchanged.

### Deviations and limits (complete list)

1. `evaluation_v04/baseline_codex.py`, the sealed evaluation's general-agent arm (G arm), is not redacted. It is not
   reachable from `rnplens assist`, and it is outside the owner's item.
2. Loose top-level files are no longer offered to the planner. A top-level file that is neither a FASTA file nor a
   declared reference is omitted and not counted; this includes a loose structure file. A loose structure therefore
   cannot be imported by the planner.
3. In free text (the question and policy reasons), only exact file and folder names and name-like stems (with a
   digit or underscore) are replaced. A target ID that the user types is sent as typed; this is declared in
   NL_PRIVACY and the docs. The structural fields (listing, plan, summary) are always identifiers.
4. The real-name checks (the suite gate and the tests) skip names shorter than four characters. Those names are
   redacted structurally, not checked as text.
5. DESIGN.md is unchanged. Its superseded clauses (H1's "relative file names and reference names"; the continue
   rule) are stated in AMENDMENT_4.md.
6. After the premise check (`80e4e6a`), run_live.py changed only in the token/statement pairing and the plan
   document text, before the freeze. None of the functions the check uses changed.
7. The planner replan check (exact echo of the previous plan) is unchanged. It holds because the model's plan is in
   identifier form, and the echo is rendered in identifier form.
8. The karyon mandated clone's path contains "codex", which produces the 7 known test artefacts. The neutral clone is
   the comparison. The launch commands point to the neutral clone until the integrator merges.
9. Local `/tmp` basetemps break the `git init` tests of `test_release_manifest`, so the full suites used a workspace
   basetemp.
10. The first two karyon suite launches of this round were discarded:
    - one passed `.` as the test path, which collected non-test modules;
    - one ran the commit before `445979b`.
    In stopping them, two of my own `pkill` calls matched their own SSH command line and ended those sessions; the
    stale processes were then stopped by basetemp. Two pytest runs of other tracks (release-docs-2, replay-2) were
    seen and left untouched.
11. No live or real Codex call was made in this round. The real binary has only ever been run as `codex --version`.


## Round 3 (2026-10-17): Amendment 5 at integration head `14faecd`

### Review of the two re-pinned files (diffs against `6b958c5`, verbatim in AMENDMENT_5.md)
- **`src/rnplens/assist.py`** (`5c04c00`) changes the menu-item path only:
  - a BLOCKED capability (`DiagnoseBlocked`, or a result status BLOCKED or DIAGNOSE_BLOCKED) exits 5;
  - a function that ran and refused exits 4; this now includes a `StateError` refusal.
  - `--nl`, `NL_PRIVACY`, `--followup` and consent are unchanged.
- **`assistant/rnplens_assistant/followup.py`** (`78e7334`, `401771f`) changes only `evidence_hash` and the replay:
  - `evidence_hash` gains definition 2 (`rnplens.followup.evidence.2`, location-independent);
  - new follow-ups record which definition they used, and replays use the recorded one;
  - replay first runs a portability check on the manifest.
  - The summary, the redaction, the prompts, `privacy_check`, consent, the policy (F1–F9) and the session budget are
    unchanged.
- Neither file changes a guard, a privacy rule or the construction of a payload. `freeze_refusals()` at `14faecd`
  listed exactly these two files, with exactly the sha256 values the integrator stated.

### Payload bytes at `14faecd` (karyon, real d1–d5, no model)
- `premise_check_r2.py` was run unchanged. Its record is byte-identical to the frozen
  `premise_check_r2_karyon.json` (sha256 `358ae79ce8f5ee6777cd9506a3267ee70d6dbcf85f586b1d9bd395ff2ddc894a`).
- All 26 payload sha256 values equal the table above. Gate 0, `followup.privacy_check` 0, real names 0. The
  reconstruction is equal for all 11 planner tasks.
- No expected value changed, and the gate is unchanged.

### Expectations with the round-3 changes (fake Codex end to end, after the freeze)

The karyon real-jail run (neutral clone, `4638f89`) and the macOS run give the same outcome:
- **Verdict:** QUALIFIED_ON_DEVELOPMENT_CASES, 12 calls, no hard failure. The go-ahead file was used.
- **Z1:** exit 3, no run folder. **Z2:** NO_CONSENT, zero calls.
- **P06 (four-axis geometry):** B1 and B2 hold. Every Evaluate `result.json` in the scenario has geometry status
  BLOCKED (`GEOMETRY_BLOCKED_IN_0.4`, 10 fields withheld, no RMSD value). The answer lists `geometry_decomposition`
  as not available. DockQ, fnat, iRMSD and LRMSD remain available under their own definitions.
- **F-L01, F-L09, F-L11:** C1–C5 hold. Each follow-up record carries `evidence_hash_version:
  rnplens.followup.evidence.2`, and FH2 (`replay-followup` equals the record) holds under definition 2.
- The CLI version (0.159.3) and model (gpt-6.1-sol) recorded in these runs come from the fake binary's script. They
  are not a real Codex identity.

### Test results (fake Codex only; no model call)

| where | commit | passed | failed | skipped |
|---|---|---|---|---|
| macOS, `tests assistant/tests` | `4638f89` | 680 | 1 | 30 |
| karyon neutral clone `tracks/lq-harness-2/RNPLens`, `tests assistant/tests` | `4638f89` | 699 | 0 | 12 |
| karyon neutral clone, `assistant/tests/test_live_qualification.py` (both real-jail tests included) | `4638f89` | 39 | 0 | 0 |
| macOS, `assistant/tests/test_live_qualification.py` | `4638f89` | 37 | 0 | 2 (karyon-only) |

The macOS failure is `test_output_schemas::test_fresh_outputs_match_schema` (`rnplens: command not found`): the CLI is
not on PATH in this source-tree environment. It is environmental and also failed in round 2 at the base. This round's
commit changes only three files of the suite folder. The round-2 macOS rc3 float failure no longer occurs.

### Observation (no change made)
- On karyon the default non-login PATH resolves `codex` to `/snap/bin/codex`, which reports `codex-cli 0.114.0`. The
  tested 0.159.3 is `~/.local/bin/codex`, which links to the standalone install.
- The jail always runs the standalone install, never PATH. If the launch commands are run without their
  `PATH=$HOME/.local/bin:$PATH` prefix, `rnplens doctor --agent` reports the Codex CLI as ACTION REQUIRED (untested
  version 0.114.0). The driver then refuses before any call, so this fails closed.
- Keep the prefix exactly as in the launch commands.

### Deviations (round 3)
1. `premise_check_r2.py` was rerun under its round-2 name. The new record is byte-identical to the frozen one, so no
   new record file was added to the frozen folder. The karyon copy is
   `scratch_agent/v04/lq-harness-2/premise_r3/premise_check_r3_karyon.json`.
2. Only the neutral clone was used for the karyon full suite, as instructed. The mandated clone (path containing
   "codex") was fast-forwarded but not tested this round.
3. The modules that followup.py now imports (`rnplens.projection`, `rnplens.portability`) are not pinned. Neither are
   the other merged round-3 changes (Evaluate geometry block, selftest masking, portability refusals), as with other
   `src/` modules. Their effect on the payloads is covered by the unchanged payload bytes, and their effect on the
   expectations by the end-to-end runs.
4. No live or real Codex call was made. The real binaries were run only as `codex --version`.


## QA round (2026-10-18): Amendment 6 at QA head `0d6fe84`

Branch `qa/lq-amendment6` (from `0d6fe84`, QA checkout `qa/0.4-karyon`). Neutral-path clone on karyon:
`RNPLens_dev_0.4/qa/tracks/lq-harness/RNPLens`. Outputs: `RNPLens_dev_0.4/qa/out/lq-amendment6/`.

### Commits

1. `4419b0e` **P3**: the two byte-identical guide copies state that the four-axis geometry route is blocked
   (residue-correspondence defect, 2026-10-14). DockQ, DockQ class, fnat, iRMSD and LRMSD remain available under
   their own definitions and are not replacements for the four-axis decomposition. The wording is evaluation protocol
   v3, change (iii).
   - New test `tests/test_guide_geometry_blocked.py`: 2 fail before, pass after. `test_guide_packaging.py` takes the
     new hashes.
2. `b5ec0eb` **U3**: the menu's RNA-range example is `1-min(L, 20)`. New test
   `tests/test_menu_rna_prompt_example.py`: it fails before; its control passes.
3. `e190d41` **O1**: a missing optional component is shown with its remedy but never makes `rnplens doctor`'s exit
   status non-zero. This is the QA patch `d9fc105a…08cfb81a8`, applied as written; its test is tightened, and the docs
   are updated. `db7dc63`: the QA docs test that encoded the old exit-1 wording now encodes O1.
4. `53ae1b8` **Amendment 6** frozen: 7 pins, the premise record, FREEZE.md. `freeze_refusals()` returns []; all 22
   pins match.
5. This report.

### Payload bytes (karyon, real d1–d5, no model)
- At `0d6fe84` the premise record is byte-identical to the frozen round-2 record. The six QA fixes change no payload
  of this suite.
- At `db7dc63` (= the code of `53ae1b8`):
  - the 22 planner payloads are each +1,008 bytes, exactly the new guide text, byte for byte (AMENDMENT_6.md
    section 4);
  - the 4 follow-up payloads are identical;
  - gate 0, `followup.privacy_check` 0, real names 0, reconstruction equal 11 of 11.

### Expectations (fake Codex end to end, after the freeze)

Karyon real jail, neutral clone, `53ae1b8`:
- QUALIFIED_ON_DEVELOPMENT_CASES, 12 calls, no hard failure. The go-ahead file was used.
- All 14 scenarios are COMPLETED with every hard and selection criterion true. Every call is privacy-clean with exact
  bytes.
- P01's sent payload is 18,854 bytes, `f6a0b569…6590`, equal to the table.
- QA behaviour visible in the records:
  - `reference_claims` follow task.json (P03 declared false; P04 and P06 declared true);
  - project ids are mapped to `project_1`;
  - no `privacy_refusal` occurs on these questions;
  - the follow-ups are `COMPLETE` with evidence hash v2.

### Test results (fake Codex only; no model call)

| where | commit | passed | failed | skipped |
|---|---|---|---|---|
| karyon neutral clone, `tests assistant/tests` | `53ae1b8` | 759 | 0 | 12 |
| karyon neutral clone, `assistant/tests/test_live_qualification.py` (both real-jail tests) | `53ae1b8` | 39 | 0 | 0 |
| macOS, `tests assistant/tests` | `53ae1b8` | 739 | 2 | 30 |

The two macOS failures predate this branch; neither touches a file changed here:
- `test_output_schemas::test_fresh_outputs_match_schema`: `rnplens` is not on PATH in this source-tree environment
  (as in rounds 2 and 3).
- `test_qa_selftest_out_geometry::test_evaluate_selftest_out_writes_no_geometry_value`: a QA test. Evaluate's selftest
  compares DockQ exactly, and macOS gives 0.3489960762419378 against the expected 0.3489960771181511. It fails
  identically at `0d6fe84`. This is a platform float difference for the QA owner, like the earlier rc3 tolerance.

### Deviations (QA round)
1. **P3 exit-status rows.** QA P3 also proposed new "Exit status" table rows (3, 4, 5, 6). They are not added; the
   brief asked for a minimal geometry wording change.
2. **P3 wording source.** The geometry wording follows evaluation protocol v3 rather than QA P3's "BLOCKED and shows no
   value" phrasing, as the brief asked for consistency with v3.
3. **Availability note.** `ask.AVAILABILITY_NOTE` (in ask.py) is not changed. Evaluation v3 changed its own copy;
   this was not requested here.
4. **U3 scope.** U3 changes only the RNA-range prompt. The protein-range example "e.g. 10-30" is unchanged.
5. **Changed QA tests.** Two QA or earlier tests encoded superseded behaviour and were updated:
   - `assistant/tests/test_guide_packaging.py` (guide and prompt-text hashes);
   - `tests/test_qa_docs_optional_matplotlib.py` (doctor exit wording).

   The O1 patch's own test assertion was tightened from a tautology to `== 0`.
6. **Evaluation v3 access.** Under `assistant_eval_v3` only `records/EVAL_PROTOCOL_v3_AMENDMENT.md` was opened. It
   was located by a `find` for that exact name (max depth 3), which lists directory names but opens no other file.
7. **Payload helper.** The byte-by-byte comparison used a helper outside the suite (`dump_payloads.py`, sha256
   `ffe5d021…9bc9db`). It runs `premise_check_r2.main` unchanged and keeps the payload texts, which stay in my karyon
   output folder. A worktree of `0d6fe84` under that folder was used for the base run.
8. **Local clone.** It was rebuilt from the saved `589485b` and `14faecd` bundles plus a 14faecd..0d6fe84 bundle made
   from my karyon clone (sha256 `875b461c…53df`).
9. **No live call.** No live or real Codex call was made. The first live call remains unauthorised.


## Amendment 8 (2026-10-19): call-specific authorisation

Since Amendment 8, the five-line confirmation file shown in "Owner's preconditions" is **refused**: it is not
modified there, because it is the historical record of the earlier procedure. A live call now needs a call-specific
authorisation naming 18 bound values (AMENDMENT_8.md section 1). The driver recomputes every value before anything is
created or called. `run_live.py --plan --run-id ID` prints the exact values with no call. The earlier approvals,
including the 2JEA wording and `LIVE_CALL_AUTHORISATION_RECORD_8c64601.md`, do not authorise any call under
Amendment 8. The call-specific request for the single P01 planning call is `LIVE_CALL_AUTHORISATION_REQUEST_<commit>.md`
(kept with the round's outputs, outside the repository, so that the commit it names stays the launch commit).

