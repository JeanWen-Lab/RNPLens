# Follow-ups: one bounded, result-aware next step (RNPLens 0.4, EXPERIMENTAL)

After a result, the question menu (`rnplens assist`) and the natural-language mode (`--nl`) can offer one further
analysis. That analysis is chosen from a fixed list and checked by deterministic rules. It runs only after you
confirm it, and its answer is written by fixed templates from RNPLens' own records.

The follow-up is **EXPERIMENTAL**. Its live part has been frozen but not yet evaluated
(`assistant/evaluation_v04/FOLLOWUP_SUITE_v1`). The follow-up never predicts structures. It never ranks or selects a
structure, run or group. It never treats agreement among predictions as evidence of correctness.

## How it works

1. **Evidence summary.**
   - RNPLens reads the analysis outputs: `summary.json`, `region_*/region.json`, the names of the explain outputs
     already written, and whether a Methods export or a grouping exists.
   - It writes a structured summary, `evidence_summary.json`. The summary holds the agreement values with their
     evidence IDs, the contact counts per frequency band, the contacts present in exactly one structure and the
     run-specific contacts (labels such as `R18-A21`, with construct positions), the unavailable or blocked items,
     the inventory counts, and the analyses already run.
   - What may be sent is that summary with every run, sample, evidence-ID (output path) and output name replaced by an
     opaque identifier (`run_001`, `candidate_001`, `evidence_001`, `output_001`; RNPLens 0.4, category list 2). The
     summary with the real names is kept as `evidence_summary_local.json` and the map as `redaction_map.json`; neither
     is sent. The arguments the model returns are mapped back to the real names before the policy checks them.
   - The construct and structure files are never opened for the summary. Neither are `contacts_by_output.json` or
     the grouping file, which contains the construct sequences.
2. **Local suggestions.** These need no language model and are always available. Deterministic rules run over the
   summary, in this order:

| rule | when | suggestion |
|---|---|---|
| L1 | structures were excluded, or files were in no recognised layout | `retrieve_contributing_structures` (excluded): look at the inventory before interpreting |
| L2 | the question, or the initial plan, asks for something unavailable (Diagnose, geometry, reference metrics, ranking, prediction, mutation advice, repeat agreement) and the summary lists it as unavailable | `explain_unavailable_metric` |
| L3 | binding-surface agreement ≥ contact-register agreement + 0.2 (Report's own values) | region comparison over the RNA positions of the run-specific and single-structure contacts (`compare_runs_in_region` with two runs, otherwise `inspect_region_contacts`) |
| L4 | an existing region comparison lists contacts found in only one run | `inspect_existing_comparison` of that list |
| L5 | two runs, no region comparison yet, contacts present in only one structure | `compare_runs_in_region` over their RNA positions |
| L6 | the question asks for an export | `export_table_or_methods` |
| L7 | the question names an RNA range | region comparison of that range |

   The margin of 0.2 in L3 is a **presentation rule** (`followup.CONSTANTS`). It is not a score, a threshold of
   biological relevance or a confidence level; it only decides which suggestion is listed. Every suggestion passes
   the same policy as a model proposal, so a suggestion that repeats an analysis already run is dropped.

3. **Optional Codex planning call.** This needs your recorded opt-in and `rnplens doctor --agent` READY.
   - RNPLens sends one message: the question, the summary, and the allowlist with its argument schema.
   - The model returns `{follow_up, args, rationale}`. The `follow_up` is one of `inspect_region_contacts`,
     `compare_runs_in_region`, `explain_unavailable_metric`, `retrieve_contributing_structures`,
     `inspect_existing_comparison`, `export_table_or_methods` or `none`.
   - The **rationale is stored in the record and never shown**. You see the templated reason for the chosen id.
4. **Policy.** The policy approves or rejects every proposal, including the local ones:

| rule | refuses |
|---|---|
| F1 | an id outside the allowlist |
| F2 | invalid arguments: positions outside the construct, a reversed range, a half protein range, booleans as numbers, runs not in the manifest or not two different runs, contact labels or evidence IDs not in the summary, unused arguments set |
| F3 | a blocked capability: four-axis geometry, Diagnose interpretation, ranking, grouping as selection, prediction, mutation advice |
| F4 | over the tool-call budget |
| F5 | a repeat of an analysis already run with the same arguments |
| F6 | a circular proposal: the same proposal again after a rejection |
| F7 | a missing input |
| F8 | a proposal of the wrong shape |
| F9 | a proposal not grounded in this result or question (for example a range with no contact, an export nobody asked for, or an unavailable item the question does not mention) |

5. **Confirmation.** RNPLens shows the proposed follow-up with its templated reason and asks `Run this follow-up?`.
   - `--yes` confirms without the prompt. It is meant for tests and scripted use, and its use is recorded.
   - Without confirmation, nothing runs.
6. **Execution.** Only the controlled RNPLens functions run:
   - `rnplens region` for the two region follow-ups;
   - `rnplens explain` for the unavailable, structures, excluded, count, contact and evidence queries;
   - `rnplens export-methods`.
7. **Answer.**
   - `followup_answer.md` is built from fixed templates. Every number is a slot filled from a record (by evidence
     ID), an approved argument or a declared constant.
   - `check_traceable()` refuses any other number, and any slot whose value differs from its source. If the check
     fails, no statement is shown.
   - Wording is audited by `rnplens.trace.wording_audit`.

## Limits (constants in `rnplens_assistant/followup.py`, recorded in every record)

| limit | value |
|---|---|
| planning rounds per question | 1 (a second Codex follow-up for the same question stops with ROUND_USED) |
| replans after a policy rejection | 1 |
| model calls per follow-up | 2 |
| tool calls per follow-up | 4 |
| identical tool call repeated | never |
| second follow-up chained automatically | never |
| usage guard or credit change | the follow-up stops cleanly (USAGE_GUARD) and lists the local suggestions |

A follow-up can also stop cleanly for these reasons:
- NO_CONSENT;
- AGENT_NOT_READY;
- PRIVACY_CHECK, where the outgoing message failed the check for sequence fragments, coordinate records, absolute
  paths, file hashes, reference file names, a real run, folder, sample or file name, or reference-derived values without
  the separate opt-in;
- MODEL_UNAVAILABLE;
- TIMEOUT;
- REJECTED;
- NOT_CONFIRMED.

A stop is recorded and the local suggestions are listed, but they are not run.

## What is sent (Codex mode only), and what never is

This is shown before the opt-in (`python -m rnplens_assistant consent show --project P`).
- **Sent:** your question (run, folder and file names in it, in any letter case, replaced by identifiers; absolute paths replaced by `<path>`; the outgoing message is checked again before sending); the agreement values
  computed by Report, with their evidence identifiers; contact labels with residue and nucleotide letters and
  construct positions; counts; opaque identifiers for runs, samples, evidence and outputs, and the structure IDs.
- **Never sent:** coordinates or any structure file content; protein or RNA sequences; file contents or paths; file,
  folder, run or sample names taken from your files; experimental reference structures or reference files, or their
  names; engine confidence values; account details.
- **Reference-derived values** (DockQ, DockQ class, fnat, iRMSD, LRMSD) are excluded unless the opt-in itself records
  `allow_reference_derived` (`consent opt-in --allow-reference-derived`). The reference file is never sent even then.

The consent record is `<project>/.rnplens/consent.json`.
- It holds the timestamp, the category-list version (`followup-categories-2` since 0.4;
  an opt-in to `followup-categories-1` must be renewed), the scope (this project), the method
  (interactive, or `--yes`) and the hash of the screen that was shown.
- An opt-out (`consent opt-out`) revokes the opt-in.
- A change of the category list requires a new opt-in.
- Without a current opt-in the follow-up is local-only, and no Codex process is started.

## Local-only mode

`--followup local` (or `s` in the interactive menu) uses the deterministic suggestions only. No language model is
used, nothing leaves your computer, and the assistant package is imported only when you ask for a follow-up.

```
rnplens assist --project P --analysis A --item C --rna 13-23 --runs exec_A,exec_B --followup local --yes
rnplens assist --project P --analysis A --item C --rna 13-23 --runs exec_A,exec_B --followup codex     # after opting in
rnplens assist --project P --task T --nl "question" --followup local --yes                           # NL mode
python -m rnplens_assistant consent show|opt-in|opt-out|status --project P
python -m rnplens_assistant followup "question" --project P --analysis A [--mode codex] [--yes]
python -m rnplens_assistant replay-followup A/followup/fu_0001/followup_plan.json --project P --analysis A
```

## Records and replay

Each follow-up writes the following files to `A/followup/fu_NNNN/`:
- **`followup_record.json`:**
  - the summary sent (exact text, byte count and sha256) and every payload sent (exact text and sha256);
  - the consent record ID;
  - the model configuration and the per-call records (model returned, tokens, plan usage, credits, error);
  - the proposals with their policy verdicts, the chosen follow-up, and the stored rationale;
  - the user confirmation, the tool log, the limits, the evidence hash, and provenance.
- **`followup_plan.json`:** the approved id, its arguments and its tool calls.
- **`evidence_summary.json`:** the summary exactly as it may be sent (identifiers only).
- **`evidence_summary_local.json`** and **`redaction_map.json`:** the same summary with the real names, and the map
  from identifiers to real names. They stay local.
- **`followup_answer.md` and `followup_answer.json`:** the statements with their slots and sources.

`replay-followup` re-runs the plan without any language model and must reproduce the evidence hash. It also does so
in a moved copy of the analysis, because absolute paths are reduced to file names in the hash.

## Worked example (scripted client, bundled 7K9D example)

The example is the bundled 7K9D example with two Boltz-2 runs, after menu item C (RNA 13-23, runs exec_A and
exec_B). The question is: *"Which contacts in RNA 13-23 are found in only one run, and which structures list them?"*

Local suggestions:

```
L4 inspect_existing_comparison {'evidence_id': 'region_13-23/region.json#/summary/only_in_run/exec_A'} -> approved
L4 inspect_existing_comparison {'evidence_id': 'region_13-23/region.json#/summary/only_in_run/exec_B'} -> approved
L7 compare_runs_in_region {'rna_start': 13, 'rna_end': 23, 'runs': ['exec_A', 'exec_B']} -> F5 (already run: dropped)
```

The local suggestions use the real names because they never leave the computer. The scripted client then proposes
two follow-ups, and the policy decides:
1. `export_table_or_methods` → **F9**, because the question does not ask for an export.
2. On the replan, `inspect_existing_comparison` of `only_in_run/exec_B`, with a rationale asserting that exec_B is
   the right run → approved. The rationale is stored in the record only.

After `--yes`, the answer begins as follows. The rationale does not appear, and no number is written by the model:

```
- Follow-up. Explain the recorded value region_13-23/region.json#/summary/only_in_run/exec_B: the structures,
  files, definition and limitations it rests on.
- From the records. Recorded: value at region_13-23/region.json#/summary/only_in_run/exec_B (contacts R16-U14,
  D39-U15, R45-U15; count 3). [region_13-23/region.json#/summary/only_in_run/exec_B; explain/...#/statements/0]
  ...
- Limitation. Recorded limitation: Recurrence among predictions is not evidence of correctness.
```

With the 0.4 redaction the summary sent is 4,834 bytes and the two payloads are 7,861 and 8,236 bytes (the
pre-redaction figures were 5,711 and 8,738 bytes for the summary and the first payload); in the payloads the runs
appear as `run_001` and `run_002` and every evidence ID as `evidence_NNN`, while the answer above, rendered locally,
shows the real names. Replay without a model reproduces the evidence
hash. In this example the two runs are a single structure each: the contacts listed for exec_B are those of one
structure, not a consensus.

## Interpretation limits

- A follow-up adds a listing or an explanation. It does not establish that a contact, region or structure is
  right. Recurrence among predictions, and agreement between runs, describe the supplied predictions only;
  predictions can share the same error.
- The local rules are presentation rules. The L3 margin of 0.2 decides which suggestion is listed. It is not a
  measure of disagreement or of how much a result can be trusted.
- The model's choice is constrained, not validated. The policy checks form, arguments, availability, repetition and
  grounding. It cannot judge whether a follow-up is the scientifically most useful one. Part 2 of the frozen suite
  measures this on development tasks only, and it has not run.
- Explanations restate what the execution records say. They do not re-check the calculation.
- The Codex follow-up is available only on platforms where `rnplens doctor --agent` is READY (Linux x86_64 with
  bubblewrap). Local follow-ups work everywhere RNPLens runs.
