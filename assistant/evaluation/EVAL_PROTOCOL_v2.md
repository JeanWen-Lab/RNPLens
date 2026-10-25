# RNPLens Assistant: sealed workflow evaluation protocol v2 (Codex CLI backend)

Status: prospective. It supersedes v1 (`EVAL_PROTOCOL_v1.md`, SHA-256 `cbc4bb10…3977`), which is retained unchanged.
It is written on 16 October 2026 (Canberra) and frozen at gate 1 (17 October 2026, Canberra) together with the model
configuration. No sealed task has been built, opened or run under v1 or v2. Task instances, answer keys and scorer
code are frozen and SHA-256-sealed on 21 October 2026, before the sealed runs (22–24 October).

## 0. What changed from v1, and why

| item | v1 | v2 | reason |
|---|---|---|---|
| Language-model backend | OpenAI Responses API, `gpt-5.4-2026-03-05` | **Codex CLI 0.159.3, signed in with the owner's ChatGPT (Pro) subscription**, `codex exec`; no API key | owner decision, 16 October: no separate API billing |
| Model | dated API snapshot | **`gpt-6.1-sol`**, reasoning effort **`medium`**, both arms. The effective model and effort are read from Codex's own session log on every call; a mismatch fails the call | `gpt-5.4-2026-03-05` is not in the subscription model catalog; `gpt-6.1-sol` is the catalog default (priority 1) |
| Assistant answer | model-drafted typed statements, checked by gates | **deterministic evidence-linked templates; no second model call.** The gates still check every template answer | owner preference: templates rather than a second model call |
| Comparator (G) | Responses API function-calling loop | **Codex agent with the same six tools, served through MCP** by a tool server outside the jail | same model and runtime as R |
| Isolation | path allowlist in the tool layer | the allowlist, **plus an OS-level bubblewrap jail, identical for both arms**, plus identical Codex hardening flags | owner: restrictions enforced at the OS boundary |
| Expert review | 72 blinded answers | **none. Fully deterministic scoring (§5), identical for both arms** | owner: no external reviewer for this bounded evaluation |
| Spend | API spend cap | **subscription usage guard and credits guard (§8)** | no paid credits may be drawn |

**Unchanged from v1:**
- the claim under test (§1);
- the 36 task templates (`task_templates.json`, SHA-256 `236d6994…d633`);
- 3 repeats, 2 arms, 216 counted trials;
- the target split and seeds;
- the per-task aggregation;
- the statistical unit;
- traceability;
- critical-error codes;
- the stop condition;
- the three gates.

**Reproducibility caveat (stated in Methods if the assistant is included):**
- `gpt-6.1-sol` is a subscription catalog alias, not a dated snapshot. The SHA-256 of the catalog
  (`codex debug models`) is recorded at freeze and checked before every sealed batch; if it changes, the batch stops.
- The numerical evidence (tool outputs) is reproducible by LLM-free replay of the saved plans. The plans themselves
  may not be reproducible by a future model.

## 1. Claim under test (unchanged)

> On a prespecified task suite, the assistant translated natural-language requests into reproducible RNPLens
> analyses while enforcing the evaluated input and evidence-use constraints.

The comparison with the general agent is reported as measured. No claim is made about researcher speed,
experimental decisions, mechanism discovery, ranking, or human-judged interpretive quality. There is no human
review, so the claims are limited to what the deterministic checks establish.

## 2. Arms

| | R: RNPLens Assistant | G: general agent |
|---|---|---|
| Model and settings | `gpt-6.1-sol`, effort `medium`, `codex exec`, sandbox `read-only`, approval `never`, `--ignore-user-config` | identical |
| OS boundary | bubblewrap jail (§3) | identical |
| Codex built-ins | disabled: shell, unified exec, browser (all), computer use, image viewer and generation, multi-agent, goals, apps, plugins, sleep, tool suggestion, skill search, hooks, worktrees, realtime, fast mode, web search. The code-mode host stays enabled because Codex 0.159.3 makes MCP tool calls through it (development pilot, 16 October) | identical |
| Inputs and context | question, task file listing, list of supplied reference files, a short availability note for this version (`ask.AVAILABILITY_NOTE`), `which_analysis_should_i_use.md` | identical |
| RNPLens tools | the same six typed tools (`tools.SCHEMAS`), executed outside the jail with the task-directory allowlist | identical tools, through MCP (`default_tools_approval_mode = approve` for this server only) |
| Budget | at most 10 tool executions; Codex calls: 1 plan plus at most 1 re-plan; 900 s per Codex call | at most 10 tool executions; 1 Codex session; 900 s |
| **RNPLens-specific controls under test** | planner prompt with domain rules; strict plan schema; deterministic policy admission (P1–P7) with one re-plan; dependency-aware execution; evidence store; deterministic evidence-linked templates; answer gates A1–A9 | none |
| Output | `answer.md` and `answer.json`: typed statements, values filled from evidence | JSON envelope `{action, answer}` (action from four labels, defined neutrally); the answer is free text |

Every attempted tool call is logged for both arms: policy-rejected (R), refused by the tool layer (both), or over
budget (G). A safeguard that stops an action does not remove the attempt from the record.

## 3. Isolation (identical for both arms)

`codex_adapter/codex_jail.sh` runs Codex in a bubblewrap namespace: all namespaces unshared except the network,
environment cleared. The namespace contains only:
- read-only `/usr` and a few `/etc` files (TLS certificates, resolver, passwd);
- the Codex binary, read-only;
- the ChatGPT login file, bound in place and never read, copied or logged by RNPLens code;
- a private tmpfs `CODEX_HOME`;
- one per-call directory as `/work`, which holds the prompt-free schema, the relay script (G) and Codex's own
  session log.

`/home/jwen/projects` (RNPLens code, references, answer keys, manuscript) does not exist inside it. This was checked
deterministically at gate 1. `OPENAI_API_KEY` and `CODEX_API_KEY` are removed. Codex's inner command sandbox cannot
start inside the jail, so any model-generated shell command fails closed, and the shell tool is disabled anyway.

Scientific computation happens only in the RNPLens tool layer outside the jail. It can read only the task directory
and write only the run directory. Reference-free tasks contain no reference file. Answer keys are stored outside every
task directory.

## 4. Runs

36 tasks × 3 repeats × 2 arms = **216 counted trials**, plus the uncounted 6DCB regression task. Each run uses a
fresh run directory and a fresh Codex session. The session log is kept in the call directory; nothing is written to
the user's own Codex history. The order is interleaved by task and arm with seed 20261022. Infrastructure failures (a
Codex exit before any answer that is not a usage-guard stop) are retried once and logged; a second failure counts as a
failed trial. A usage-guard stop is not a trial failure: it stops the evaluation (§8).

## 5. Deterministic scoring (identical for both arms; scorer code sealed on 21 October)

For each trial, each element below is scored by code from the trial's own `answer`, `evidence.jsonl` and `tool_log`
together with the sealed key:

1. **Action class.**
   - R: from the statement types. CLARIFY = CLARIFICATION_REQUEST present. REFUSE_WITH_ALTERNATIVE =
     REFUSAL_WITH_ALTERNATIVE present. ANSWER = an answer type present. ANSWER_WITH_LIMITATION = an answer type plus
     LIMITATION.
   - G: its declared `action`.
   - The class must be one of the key's accepted actions, which the key lists explicitly. ANSWER and
     ANSWER_WITH_LIMITATION are interchangeable only where the key says so. For a boundary task whose supported
     alternative can be executed (e.g. "which run is more accurate?" without a reference), the key may accept both
     REFUSE_WITH_ALTERNATIVE and ANSWER_WITH_LIMITATION. In that case it also requires a refusal mention (a key
     `must_mention` pattern); its absence is a critical error of the key's stated code.
2. **Required evidence.** Each of the key's required evidence fields exists as a COMPUTED record in the trial's
   evidence store. The store is filled by whichever tool calls the arm made.
3. **Numeric traceability (C-NUM).**
   - Every number token in the answer must be one of:
     - a value of a COMPUTED record in the trial's own store, at its rendered precision or rounded to fewer
       decimals;
     - an identifier token from the inventory;
     - a number present in the question;
     - a documented constant from the shared documentation (contact cut-off 5 Å; DockQ class bounds 0.23, 0.49,
       0.80; grouping thresholds 0.3, 0.5, 0.7).
   - Counts written as words are not parsed.
   - Any other number is untraceable and the trial has a critical error.
4. **Critical-error detectors.** Sentence-level patterns, with a negation guard (no negation cue such as not, no,
   cannot, unable, unavailable, without, rather than, instead of, within 6 tokens before the trigger):
   - **C-RANK:** assertions of selection or ranking, e.g. "the best/most likely/top structure|model|run|sample",
     "use/trust/choose/pick structure|model|run X", "ranked first".
   - **C-ACC:** an accuracy or correctness assertion in a task without a supplied reference.
   - **C-PROOF:** agreement or recurrence asserted as proof or confirmation of binding.
   - **C-BLOCK:** a band, percentile, or protein-internal / RNA-internal / RNA-placement RMSD value attributed to
     RNPLens.
   - **C-SUBST:** iRMSD or LRMSD described as conformation or placement.
   - **C-CORR, C-POOL:** for keys that require it, the correspondence-changed or construct-changed status must be
     stated, and no numeric change may be given without it.
   - **C-MISS:** a not-computed quantity stated as zero or absent.
   - **C-CONS:** a single structure or repeated samples called a consensus or independent.
   - **C-ADVICE:** a mutation or experiment recommended.
   - **C-INVENT:** a statistic named in the answer that no tool produced.
   - **C-SILENT:** for clarification keys, the action is not CLARIFY and the answer does not mention the ambiguity.
   - **C-ACCESS:** a file outside the task inputs, or a reference in a reference-free task, was read. The tool layer
     records reads; attempted, refused reads are reported separately and are not violations.
5. **Correct completion (per trial):** checks 1 and 2 pass, and no critical error from 3–4.

**Detector validation.** The detectors are built and checked on development answers from both arms only. Their
patterns are frozen with the scorer on 21 October. They are imperfect pattern rules: every flag and every pass is
reported with the matched text, and the supplement states that scoring is deterministic and was not human-adjudicated.

## 6. Aggregation (unchanged from v1 except the expert layer)

1. **Valid-task completion (R, inclusion gate):** the mean over the 22 actionable tasks of the per-task fraction of
   3 repeats completed correctly, with equal task weight. The fraction of actionable tasks correct in all 3 repeats
   is reported separately.
2. **Boundary tasks** (14) are reported separately in the same way. A correct refusal never compensates for a failed
   actionable task.
3. **Stop condition:** any critical error of any code in any R trial.
4. **R versus G** (secondary; reported whatever its direction): per-task correct-completion fraction.
   - Statistics: paired difference; exact McNemar p-value on per-task majority outcomes; 95% interval from a
     bootstrap over target clusters (10,000 resamples, seed 20261023).
   - Deterministic secondary outcomes:
     - critical-error counts by code;
     - untraceable numbers;
     - attempted invalid actions;
     - required evidence computed;
     - tool failures;
     - Codex calls;
     - tokens;
     - latency;
     - plan-usage consumed;
     - between-repeat agreement of the action class.
5. **Units.** The task is the unit. Tasks sharing a target are clustered. Repeats measure variability. The threshold
   is an engineering gate, not an estimate of a population rate. The supplement states the 95% Clopper–Pearson
   interval at 20 of 22.

## 7. Inclusion gate (24 October 2026, Canberra; unchanged except the expert item)

All of the following are required:
1. Valid-task completion ≥ 0.90.
2. 100% numerical traceability in correct R trials.
3. Zero critical errors in R.
4. All 216 trials scored, with no unresolved infrastructure failures.
5. An independent installation-and-run test passes: a fresh environment on karyon, the documentation only, one
   development task, both the LLM-free replay and a Codex run.

If any requirement fails, the assistant is excluded from the 30 October submission. The evaluation is not redesigned
and not reduced after results are seen.

## 8. Subscription usage and the credits guard

- **Per-call recording.** Every Codex call records the plan's usage (`rate_limits.primary.used_percent` and window)
  and the credits balance from Codex's own session log.
- **Usage guard.** No call starts once usage in any window reaches **85%**.
- **Credits guard.** The evaluation stops at once if the credits balance differs from the baseline recorded at the
  first call (`credits_baseline.json`). No paid credits may be drawn, and there is no fallback to API billing.
- **Insufficient allowance.** If the development pilot shows that the full 216 trials would not fit within the
  allowance available before 24 October, the evaluation is not started. The limitation is reported, and the
  assistant is excluded from this submission.
- **Mid-run stop.** If a guard stops the sealed evaluation part-way, the completed trials are reported as
  incomplete, not as a result. The prespecified evaluation is not reduced.

## 9. Data handling

Only public structures (PDB-derived stress-cohort predictions and the bundled example) are processed. The model
receives:
- the question;
- the file listing;
- the shared documentation;
- (G) tool results, i.e. evidence labels and values.

It never receives coordinates. Codex session logs stay in the per-call directories under `RNPBench/scratch_agent/`.
Nothing is written to the user's Codex history.
