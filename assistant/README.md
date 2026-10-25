# RNPLens Assistant (development, bounded companion)

The assistant answers three kinds of question about **existing** predicted protein–RNA complexes:
1. what the predictions agree on (binding surface and residue–nucleotide contacts);
2. matched comparisons against a supplied experimental reference (DockQ, fnat, iRMSD, LRMSD);
3. which analysis the available evidence justifies, including clarification or refusal.

A language model (Codex CLI, signed in with ChatGPT) proposes a plan. Deterministic code checks the plan, runs
qualified RNPLens functions, records every value, and writes the answer from those records.

**Not available in this version:** Diagnose, the four-axis geometry decomposition, ranking, grouping, structure
prediction and mutation advice.

## Install (Linux)

```
python3.11 -m venv VENV
VENV/bin/pip install ./RNPLens            # the RNPLens toolkit (this repository's root)
VENV/bin/pip install ./RNPLens/assistant  # the assistant
VENV/bin/rnplens selftest
```

**Requirements:**
- Codex CLI installed and signed in with ChatGPT (`codex login status` must report "Logged in using ChatGPT"). No API
  key is used.
- Linux: `bwrap` (bubblewrap) and the jail script `assistant/codex_adapter/codex_jail.sh`.
- macOS: nothing to install; the jail is `assistant/codex_adapter/codex_seatbelt.sh` with the profile
  `codex_seatbelt.sb` (Seatbelt, built into macOS), and Codex's file-based login storage
  (`cli_auth_credentials_store = "file"`).
- The jail of this system is chosen automatically (`rnplens_assistant/confine.py`) and cannot be replaced:
  `RNPLENS_CODEX_JAIL` naming any other script is refused before anything starts, and the jail process receives only
  `HOME`, `CODEX_HOME`, `RNPLENS_CODEX_BIN` and `PATH=/usr/bin:/bin`. `RNPLENS_CODEX_CALLS` names a writable folder for
  per-call records.

## Use

A task folder holds the prediction folders, `protein.fasta` and `rna.fasta`. It may also hold a `task.json` listing
supplied reference files: `{"reference_files": ["reference.cif"]}`.

```
VENV/bin/python -m rnplens_assistant ask "Do these two runs support the same binding surface and contacts?" --task TASK --out RUN
VENV/bin/python -m rnplens_assistant replay RUN/plan.json --task TASK --out RUN_REPLAY --expect <evidence_sha256 from RUN/run_record.json>
```

**Outputs:**
- `RUN/answer.md`: the answer, a list of what was not computed, and an evidence table;
- `RUN/evidence.jsonl`: every value with its source;
- `RUN/plan.json`: the plan, which `replay` re-runs without any language model;
- `RUN/run_record.json`: model, usage and checks.

Agreement between predictions is never presented as correctness.
