# RNPLens Assistant (optional, experimental)

The assistant answers three kinds of question about **existing** predicted protein–RNA complexes:
1. what the predictions agree on (binding surface and residue–nucleotide contacts);
2. matched comparisons against a supplied experimental reference (DockQ, fnat, iRMSD, LRMSD);
3. which analysis the available evidence justifies, including clarification or refusal.

A language model (Codex CLI, signed in with ChatGPT) proposes a plan. Deterministic code checks the plan, runs
qualified RNPLens functions, records every value, and writes the answer from those records.

**Not available in this version:** Diagnose, the four-axis geometry decomposition, ranking, grouping, structure
prediction and mutation advice.

## Status and limitations (read before use)

The Assistant is a **separate, optional** package: installing RNPLens does not install it, and every scientific
capability of RNPLens works without it. It is an **experimental research interface**, not a qualified component.
Its package version, 0.1.0, marks a packaged release of the automatically tested implementation. It does not
imply completed native security qualification or validation of live model calls.

- **Native security qualification is incomplete** on both Linux and macOS. The historical macOS qualification of
  an earlier commit does **not** certify the jail wrapper shipped here, which has since changed.
- **Live model calls are not qualified.** Automated tests exercise the Codex route only through replay and paths
  that make no model call.
- **Credential and network isolation is not proven.** The confinement restricts what the model process can read
  and reach, and the tests check that the toolkit's own output does not echo credential content. This release
  nevertheless makes **no claim of complete isolation** of credentials or network traffic. Treat any sensitive
  material on the same machine accordingly.
- **Sending a question to a hosted model sends data to a third party.** Decide whether that is acceptable for your
  data before you enable it.
- **It plans and refuses; it does not extend the science.** It cannot make a blocked capability available.

**Confinement.** The Assistant needs a working Codex CLI sign-in and a native confinement backend chosen by
platform: **bubblewrap** on Linux, **Seatbelt** on macOS. It refuses to start a model process outside that
confinement. It also refuses a Codex installed in a location that the installation-location rule rejects, such as
a Homebrew prefix on macOS or a snap installation on Linux. That refusal is intended behaviour. See
[docs/install_linux.md](../docs/install_linux.md), [docs/install_macos.md](../docs/install_macos.md) and
[docs/setup_and_privacy.md](../docs/setup_and_privacy.md).

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
