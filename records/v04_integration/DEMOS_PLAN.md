# Demos & installs track: rules fixed before any demonstration output was produced

Written and committed on branch `track/demos` (base `5caccec`) **before** the three demonstrations were run on karyon.
The commit that adds this file precedes every demonstration output, so its timestamp is the record that the rules
below were fixed in advance. They are not changed after looking at results; any change would be an amendment with
its reason, recorded in `DEMOS_REPORT.md`.

## Data scope (contracts v1, sections 1 and 6)
- Only development data: `scratch_agent/assistant_dev_tasks/d2_1VTM_agreement`, `d4_24BR_compare`, pool A target
  6BJG, and the bundled 7K9D example. None of these is an excluded target (sealed list, regression target 5MSF, Rank
  holdout; pool A is disjoint from the holdout by the Rank Phase-1 record).
- Source folders are read only and copied into the demonstration package before any RNPLens command runs.
- No DockQ label file is opened (pool A `nscale_sample_dockq.tsv`, pool B `rank_corpus.tsv`), nor
  `reranker_consensus.tsv`, nor anything under `RNPLens-Rank/audit/`. Demo 3 additionally records the files opened
  by the copy step (only `inputs/6BJG.yaml` and `predictions/6BJG/`).
- The d4 reference structure (`reference.cif`) is not used: demo 2 is reference-free.
- No Codex or other language-model call. The Codex follow-up appears only as the scripted demonstration path of
  `docs/followup.md` (a scripted stand-in client, labelled as such).

## Demo 1, RNA-region investigation (d2_1VTM_agreement: Boltz-2, run_A and run_B, 5 samples each)
- **Region rule (fixed now, before any contact is looked at).** Let D be the engine-designated structures recorded
  in `project/manifest.json` (`designated == true`, one per run). Let S be the set of RNA positions occurring in any
  `[protein_pos, rna_pos]` pair of `analysis/report/contacts_by_output.json` for the keys of D. The region is
  `[min S, max S]` in construct numbering. If S is empty, the region is the whole RNA construct and this is stated.
  The rule is computed by `demos/lib/region_rule.py`, which writes `region_rule.json` before `rnplens region` runs.
- Question answered: "Which protein residues contact this RNA region, and which exact contacts differ between
  runs?" with `rnplens region` (all runs of the project, i.e. both), the regional contact table, contributing
  structures (designated vs additional samples), the region map PNG and `rnplens view --rna a-b`.

## Demo 2, interactive analysis (d4_24BR_compare: Boltz-2, run_A and run_B, 5 samples each)
- d2's RNA is 3 nt long, so a 2-nt truncation would leave one nucleotide; d4 is used instead (allowed by the task).
- Ambiguous input: a third folder `run_C_other_construct`, a copy of `run_B` in which the last two nucleotides of the
  RNA chain are removed from every structure file (confidence files copied unchanged).
- Answer to the expected `construct_mismatch` question: `exclude_run`, with the researcher's words "run_C was copied
  in from a truncated-RNA construct by mistake". (Fixed now; the demonstration shows the question, the answer, the
  refusal of a contradicting answer, and resumption.)
- Region for item C and the follow-up: the demo-1 rule applied to this project's designated structures.
- Value explained with `rnplens explain`: the first contact row of the region output,
  `region_<a>-<b>/region.json#/contacts/0`.
- Local follow-up: `rnplens assist --item C ... --followup local --yes`; the question is
  "Which contacts in RNA <a>-<b> are found in only one run, and which structures list them?"
- Scripted Codex path (docs/followup.md worked example, transferred to this project): scripted proposal 1
  `export_table_or_methods` (expected F9), scripted replan `inspect_existing_comparison` of
  `region_<a>-<b>/region.json#/summary/only_in_run/run_B`, with a deliberately over-claiming rationale that must be
  stored and never shown. The policy's verdicts are reported as they come out.
- Then `rnplens update` with no change (expected: nothing recomputed, nothing asked again).

## Demo 3, binding-hypothesis interpretation (pool A, Boltz-2, 50 samples)
- **Target rule (fixed now).** 6BJG, the worked example of `docs/grouping.md`, so that the demonstration is also a
  reproduction check of the documented numbers. Sequences are taken from the Boltz input
  `PCfold3D-RNP/outputs/rnp/jpf/nscale/inputs/6BJG.yaml`.
- Groups compared by `group-diff`: at the primary cut t = 0.5, the group holding the engine-designated structure
  ("engine-pick group") and the next group in display order.
- Checks, each reported pass/fail: (i) for every cut, structures in groups + ineligible + no-interface == 50, and the
  set of structure ids equals the manifest's included ids; (ii) wording scan of every text output (HTML, MD, TSV,
  TXT, SVG, and string values of JSON) with `rnplens.trace.wording_audit` and `rnplens.grouping.FORBIDDEN`, every
  hit listed with context and classified as negated limitation text or affirmative; (iii) the documented 6BJG
  numbers in `docs/grouping.md` reproduced.

## Replay check (all demos)
`replay.sh` re-runs the same deterministic workflow into a new folder and compares every `*.json` outside `inputs/`
with the original, ignoring only keys named `created_utc` and `wall_s`. Files that differ in any other way are
listed with the differing JSON pointers; a second comparison that additionally replaces the package root path is
reported separately, never merged into the first.

## Clean installs (Part A)
Fresh clone of the integration checkout at `5caccec` under `scratch_agent/v04/clean_install_<ts>/`; wheel and sdist
of `rnplens` and `rnplens-assistant`; one venv per format; every check run with `PYTHONPATH` unset and the working
directory outside the source tree.

## Demo 1b, RNA sub-range investigation (added at the integrator's request, 16 Oct 2026)
Recorded and committed **before** any sequence length, structure or contact of the stress-cohort targets was read.
Only file names and counts had been listed: each of the six targets has `pilot/inputs/boltz/<T>.yaml`, and 5
`<T>_model_*.pdb` with 5 `confidence_<T>_model_*.json` in each of `exec_A` and `exec_B`. The lengths of 1VTM (3 nt) and
24BR (4 nt) were already known from demos 1 and 2.
- **Target rule.** Go through the stress-cohort development targets in the order 1VTM, 24BR, 2JEA, 2Q66, 2QQP, 2XGJ.
  Take the first target T for which all three conditions hold:
  1. `PCfold3D-RNP/outputs/rnpbench/pilot/inputs/boltz/<T>.yaml` declares exactly one protein and exactly one RNA
     entry;
  2. the RNA sequence is at least 20 nt long;
  3. `pilot/boltz/exec_A/<T>/boltz_results_<T>/predictions/<T>/` and the same `exec_B` folder each hold 5
     `<T>_model_*.pdb` and 5 `confidence_<T>_model_*.json`.

  If no target qualifies, use the pool-A 6BJG candidates, split into two pseudo-runs by sample index parity
  (even, odd), and state this. The rule is applied by `demos/lib/select_target.py`, which writes
  `target_rule.json` (one row per target examined). Only `exec_A` and `exec_B` are used, never `exec_A_retry1`, and
  no folder of these trees is enumerated beyond the selected target.
- **Region rule.** For s = 1 … L−9, count the distinct `[protein_pos, rna_pos]` pairs with
  `s ≤ rna_pos ≤ s+9`, in the union of the contact lists of the engine-designated structures of
  `analysis/report/contacts_by_output.json`. The region is the 10-nt window with the largest count, with ties
  going to the lowest start. The rule is applied by `demos/lib/region_window_rule.py`, which writes
  `region_rule.json` (the count for every window) before `rnplens region` runs.
- **Analysis.** `rnplens region` on all runs (exec_A, exec_B); `rnplens explain contact` for **every** contact of
  the region whose class is not "shared by all runs"; `explain structures` and `explain region_mapping`;
  `rnplens view --rna a-b`; the template answer; the replay check, wording scan and data-access audit as for the
  other demos.
- **Data access.** The package run itself runs under `strace`. Under `PCfold3D-RNP/`, only the YAMLs of the targets
  examined by the target rule and the selected target's two `predictions/<T>/` folders may be opened. In particular,
  nothing under `pilot/references`, `pilot/audit`, any `*score*` folder or `exec_A_retry1` may be opened.
