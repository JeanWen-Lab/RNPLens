# Amendment 4 to LIVE_QUALIFICATION_v1 (2026-10-17, Canberra): opaque identifiers in every payload; one call, then the owner's go-ahead

Cause: owner decision note of 17 October 2026, item 2. It is required before any live call. Written and frozen on
branch `track/codex-harness-r2` (base `b3374e4`) **before any run of this suite, mocked or live**, after this
round's changes. No Codex or other language-model call has been made; the real `codex` binary has only been run as
`codex --version`.

## 1. Product change the suite now measures (commit `fd79c75`)

The planner and the follow-up no longer send file names, folder names, run names, sample names, paths or reference
names. They send opaque identifiers instead. The map back to the real names (`redaction_map.json`) stays on the
computer and is never sent.

- **Planner listing** (`rnplens_assistant/redact.py planner_view`). Top-level folders, case-insensitively sorted, become
  `run_001`, `run_002`, and so on. Inside each folder, files sorted the same way become `run_NNN/candidate_NNN` for
  structure files (.pdb .cif .mmcif .ent, plain or .gz) and `run_NNN/file_NNN` for any other file. Top-level FASTA
  files become `protein_sequence_NNN` or `rna_sequence_NNN`, judged by alphabet. A reference is listed only if
  task.json declares it in `reference_files`, and only as `reference_NNN`. If the task has no reference, the payload
  says "none" and nothing else about any reference. Other top-level files are omitted and not counted; a consequence
  is that a loose top-level structure file is never offered to the planner. Plan arguments must be identifiers. A real
  path in a plan is refused with P9 and is mapped back only locally. Replans echo the plan and the policy's reasons
  in identifier form.
- **Follow-up summary**: runs are `run_NNN`, structures `candidate_NNN`, evidence IDs `evidence_NNN` and analysis
  outputs `output_NNN`. The sent summary is `evidence_summary.json`; the local view is `evidence_summary_local.json`.
  Exact file and folder names typed in the question are replaced. A target ID typed by the user is sent as typed;
  this is declared in NL_PRIVACY.
- `assist.NL_PRIVACY`, the consent categories (`followup-categories-2`), docs/setup_and_privacy.md and
  docs/followup.md state this. No prompt file, `codex_llm.py`, the jail, the guide or FOLLOWUP_SUITE_v1 changed.

## 2. Changes to this suite (run_live.py)

1. **H1 reconstruction**. `expected_nl_payload` rebuilds the first planning payload from the prompt files and the rule
   in section 1: identifiers, the reference line, and the documentation with its availability note. It does not call
   `redact.py`. This supersedes DESIGN.md "the relative file names and the reference names" in H1. The replan clause
   ("adds only the previous plan and the policy's rejection lines") is unchanged; both are now in identifier form.
2. **Pre-send gate, real names.** `privacy_ctx` takes a `names` set, and every name in it is a forbidden string.
   - Part P: `real_names(task)`, meaning every relative path, basename, name-like stem (one containing a digit or an
     underscore), folder name, and target ID found in file names (four characters starting with a digit), plus the
     task name.
   - Part F: the same set, plus the project manifest's run names, sample names and structure basenames, plus
     `summary.json`, `region.json` and the `region_*` output folders.
   - Names shorter than four characters are not listed; they are redacted structurally. A name that occurs in the
     fixed system text (prompt and documentation) is dropped from the set.
   - `privacy.py` is unchanged.
3. **Owner precondition, two alternatives.**
   - (A) The existing statement (auto-reload off and the one-call risk accepted), with
     `RNPLENS_LIVE_QUAL=I_CONFIRM_AUTO_RELOAD_OFF_AND_ACCEPT_ONE_CALL_RISK`.
   - (B) NEW: "I confirm that a hard spending block prevents any use of credits by the ChatGPT account used by Codex
     on this machine.", with `RNPLENS_LIVE_QUAL=I_CONFIRM_HARD_SPENDING_BLOCK`.
   - The token must match the statement in the confirmation file. The run record stores which precondition applied.
4. **One call, then the owner inspects.** `--first-call` still makes exactly one call (P01's planning call) and stops.
   It now prints:
   - P01's status, hard criteria, tool selection and answer path;
   - the model identity, effort and CLI version as returned;
   - the balance and usage;
   - a 16-hex `first_call_digest`, computed as sha256 over run id, prompt sha256, the first call's reading and P01's
     status, hard criteria and tool selection;
   - the go-ahead template.

   Nothing continues automatically.
5. **Go-ahead file.** `--continue-after-first` now also needs `--go-ahead FILE`, written by the owner after that
   inspection. Its first line is `RNPLens LIVE_QUALIFICATION_v1 owner go-ahead`, followed by:
   - `date:` (today in Australia/Canberra) and `run_id:` (this run);
   - `first_call_digest:`, which must equal the recomputed digest;
   - `observed_credit_balance:`, which must equal the baseline exactly, otherwise there is no further call;
   - `observed_weekly_usage_percent:`, at most start + 10 points and below 85 %;
   - the exact line `statement: I have inspected the first call's result, model identity, usage and credit balance,
     and I authorise the remaining calls of this run.`

   Unknown or repeated lines are refused. The file's modification time must be later than the first call's
   completion. Its sha256 is stored in the run record. This supersedes DESIGN.md "`--continue-after-first` is accepted
   only for a run in state PAUSED_AFTER_FIRST_CALL whose first reading passes the guards and whose confirmation states
   the same baseline": those conditions remain, and the go-ahead is added to them.
6. `plan_doc` lists the go-ahead guard and both tokens.

## 3. Pins (scenarios.json `pinned_sources`)

| source | before | after |
|---|---|---|
| assistant/rnplens_assistant/ask.py | `08f612fdb46781efb2803d5ddfde7804f24330e47e600b91967ea1fa13c5c14f` | `11dcfcfb7b6954309e4662ceae9b519e116124c5aaa445575f6dd2674bd5a3df` |
| assistant/rnplens_assistant/followup.py | `90600b85a4b1cee53e1653811e8f30aa5d7be6b3c57998cb1bb81b017e9bbce6` | `b97e4820faddbc9e021b794d1a0d773c2bdc771bfcf2a53045572a49430e4e5f` |
| assistant/rnplens_assistant/consent.py | `8a125e15b98b2113085ab9649663270f38182213815663775993a95c307a49c6` | `d797aebaf339aea8f22f12bc1af2145f103be03ce34445e6c081c5c11d72878e` |
| src/rnplens/assist.py | `5849c3dd5bcde304c31e5aa3ae6953865a55ba30200bc90ef56811243d4c5e8f` | `2e504d658a0dd052791bb7a0fbb1bf98f031fb6efe22989849c09988dd68955a` |
| assistant/rnplens_assistant/redact.py | (new pin) | `b1cc5f7b1b9dc8040196b556509b78e6dfc785a53bc5385634a3d22ffc8e66a2` |

All other pins are unchanged (codex_llm.py, policy, tools, templates, gates, render, evidence, replay, llm, guide,
registry, the three prompts, the guide document, the jail, doctor.py). The previous hash of scenarios.json was
`87a29cb524a1e32aaf88f3a32caabfd914f843a6f918bd73f1c1cc02b976e2b1`.

**Expectations unchanged, and why.** Every `require` entry compares the assistant's `tool_log` (folders_include
`run_A`/`run_B`; P02 `rna_start` 13 / `rna_end` 23; P04 `reference: reference.cif`). That log records the admitted
arguments after the local map back to real names, so these entries mean what they meant before. FOLLOWUP_SUITE_v1's
accept sets for L01, L09 and L11 name no run, file or evidence ID, so C1 is unaffected. C5 (the reference file name
is never sent) still applies and now holds structurally. No scenario, question, allowed-tool list, threshold, guard
value, budget (max 24 live calls, nominal 12), scoring rule or decision rule changed.

## 4. Premise check r2 (premise_check_r2.py, record premise_check_r2_karyon.json)

The check was run on karyon at commit `80e4e6a` in the track's neutral clone, on the real development tasks d1–d5. It
used scripted capture clients only: no model, no Codex subprocess, no scenario, no driver run. It builds, through the
assistant's own code path, every first planning payload (Z1, Z2, P01–P09) and a P9 replan for each, and the
follow-up payloads of L01, L09 and L11, plus the replan where the scripted proposal was refused (L01).

- 26 payloads in total. The independent reconstruction equals the assistant's first planning payload for all 11
  planner tasks.
- The pre-send gate, with real names forbidden (16 to 51 names per task), finds 0. `followup.privacy_check` finds 0
  in every payload. Notably, the round-1 observation that it flagged every planner payload with "a reference file
  name found" no longer occurs. A scan for real names finds 0.
- Each payload's sha256, size and a redacted excerpt are in the record. Planner first calls are 17,846–18,297 bytes;
  follow-up payloads are 7,258–7,866 bytes.
- Record sha256: `358ae79ce8f5ee6777cd9506a3267ee70d6dbcf85f586b1d9bd395ff2ddc894a`.
- After the check, run_live.py changed only in the token/statement pairing (2.3) and the plan document text (2.6).
  These touch none of the functions the check uses (`expected_nl_payload`, `real_names`, `manifest_names`,
  `privacy_ctx`).

## Unchanged

DESIGN.md (the superseded clauses are stated above), score_live.py, privacy.py, fake_codex.py, premise_check.py and
premise_check_karyon.json (round-1 record, kept as it was), AMENDMENT_1–3, and FOLLOWUP_SUITE_v1. Out of this
amendment's scope: `evaluation_v04/baseline_codex.py` (the sealed evaluation's general-agent arm, not reachable from
`rnplens assist`) is not redacted.
