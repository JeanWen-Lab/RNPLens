# Demonstration 2: interactive analysis with an ambiguous input (development task d4_24BR_compare)

**What the researcher does.** They point RNPLens at three prediction folders. Two are Boltz-2 runs of their
construct (`run_A`, `run_B`, 5 samples each). The third, `run_C_other_construct`, was copied in by mistake from a
construct whose RNA is 2 nt shorter. RNPLens has to ask about the third folder rather than guess. After the
answer it completes the analysis. The researcher then exports Methods, asks where one reported value comes from,
and takes one follow-up from the question menu.

**Data.** `scratch_agent/assistant_dev_tasks/d4_24BR_compare` (24BR, a development target, not an excluded one):
`run_A`, `run_B`, `protein.fasta`, `rna.fasta`, copied into `inputs/`. The task's `reference.cif` is **not** used, so
this analysis is reference-free. `inputs/in/run_C_other_construct` is built by `scripts/lib/truncate_rna.py`: a
copy of `run_B` with the last two RNA nucleotides removed from every structure file (`TRUNCATION.json` in that
folder lists the removed residues).

## Commands (run from this folder; `rnplens` = `python -m rnplens` of RNPLens 0.4.0.dev0)

```
rnplens update demo --init inputs/in/run_A inputs/in/run_B inputs/in/run_C_other_construct \
    --protein-seq inputs/protein.fasta --rna-seq inputs/rna.fasta --engine BOLTZ2 --case-id 24BR_d4    # exit 3: a question
rnplens clarify demo                                    # exit 3: the typed request (construct_mismatch) and its options
rnplens clarify demo --answer 1 exclude_run --text "run_C was copied in from a truncated-RNA construct by mistake"   # resumes; exit 0
rnplens clarify demo --answer <question id> use_as_reference_set     # exit 2: refused, contradicts the recorded answer
rnplens clarify demo --history ; rnplens update demo --status
rnplens update demo                                     # no change: reused, nothing asked again
python scripts/lib/region_rule.py @P@ @A@ region_rule.json            # RNA @RANGE@ (the rule of demonstration 1)
rnplens region @P@ @A@ --rna @RANGE@
rnplens export-methods @A@ --project @P@
rnplens explain evidence --id "region_@RANGE@/region.json#/contacts/0" --analysis @A@ --project @P@
rnplens assist --project @P@ --analysis @A@ --item C --rna @RANGE@ --runs run_A,run_B --followup local --question "<Q>" --yes
python scripts/lib/followup_scripted.py @P@ @A@ "<Q>" "region_@RANGE@/region.json#/summary/only_in_run/run_B" followup_scripted.json   # SCRIPTED
python -m rnplens_assistant replay-followup @A@/followup/fu_000N/followup_plan.json --project @P@ --analysis @A@     # each follow-up
rnplens update demo ; rnplens update demo --versions
```

`<Q>` is "Which contacts in RNA @RANGE@ are found in only one run, and which structures list them?". `logs/steps.tsv`
lists every command with its expected and actual exit code. Each command's output is in `logs/<step>.log`.

## Outputs

| file | what it is |
|---|---|
| `logs/02_clarify_list.log`, `logs/03_clarify_json.log` | the typed clarification request: type `construct_mismatch`, the differing run, the options, and the inputs it depends on with their SHA-256 |
| `logs/04_clarify_answer.log`, `logs/05_clarify_contradiction.log`, `logs/06_clarify_history.log` | the recorded answer and resumption; the refused contradiction; the answer history |
| `demo/.rnplens/state/v*.json`, `demo/.rnplens/HEAD` | the immutable project versions (answers, hashes, keys) |
| `@A@/` | the current analysis folder (`summary.json`, `report/`) |
| `@A@/region_@RANGE@/` | region comparison of run_A and run_B (`region.json`, `.tsv`, `.html`, `region_map.png`) |
| `@A@/methods/` | the Methods draft (`methods.md`, `methods.txt`), its sentence sources and the provenance manifest |
| `@A@/explain/` | the explanation of `region_@RANGE@/region.json#/contacts/0`, and the explanations written by the follow-ups |
| `@A@/followup/fu_0001/` | the **local** follow-up (deterministic rules, no model): record, plan, evidence summary, answer |
| `@A@/followup/fu_0002/`, `followup_scripted.json` | the **SCRIPTED** Codex-path demonstration (see below) |
| `logs/14_replay_fu_*.log` | each follow-up plan replayed without any language model |
| `update_after_outputs.json`, `logs/15_update_after_outputs.log` | the final no-change update (see defect D1) |

## About the Codex follow-up shown here: SCRIPTED, no model
`fu_0002` comes from the scripted demonstration path of `docs/followup.md` ("Worked example (scripted client)"),
moved to this project. **No Codex process was started and no language model was called.** The planning call is
answered by the stand-in client `rnplens_assistant.llm.Stub` with two fixed proposals. The doctor's agent check is
replaced by a stub. Everything else is the real code: consent record, evidence summary, privacy check, policy,
confirmation, execution, templated answer and traceability check. The two proposals are:
`export_table_or_methods` (the policy refuses it, F9, because the question asks for no export), then, on the
replan, `inspect_existing_comparison` of `only_in_run/run_B`. The replan carries a deliberately over-claiming
rationale. The record stores that rationale, and the answer never shows it (`followup_scripted.json`,
`rationale_shown_in_answer`). **The live Codex follow-up awaits the owner's confirmation. FOLLOWUP_SUITE_v1 Part 2
covers it; that part is frozen and was not run.**

## What these outputs do NOT mean
- The clarification answer is the researcher's decision about which folder belongs to the construct. RNPLens
  records it and applies it, but does not judge it biologically.
- Shared and run-specific contacts are listings with counts. A contact that recurs among predictions is not
  evidence that it exists in the real complex. Samples of one model are not independent.
- The Methods draft is a draft built from execution records. It must be checked by the author, and it generates no
  citations.
- An explanation restates the records. It does not re-check the calculation.
- A follow-up adds one listing or explanation. It does not rank runs or structures. The local rules are
  presentation rules.

