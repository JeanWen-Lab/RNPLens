# Model use and privacy

Short page; the full description is [setup_and_privacy.md](setup_and_privacy.md).

| question | answer |
|---|---|
| Is a language model needed? | No. RNPLens Standard uses none. The optional Assistant (`rnplens assist --nl`, Codex follow-ups) is the only part that does. |
| Which model and route? | Codex CLI 0.159.3 (`codex exec`) with your own ChatGPT sign-in, model `gpt-6.1-sol`, run inside the operating system's own sandbox: a bubblewrap jail on Linux (`codex_adapter/codex_jail.sh`), a Seatbelt jail on macOS (`codex_adapter/codex_seatbelt.sh`, `codex_seatbelt.sb`); `rnplens_assistant/codex_llm.py`, `confine.py`. |
| Is a separately billed API used? | No. No API key is read or used; `OPENAI_API_KEY` and `CODEX_API_KEY` are removed, the jail starts from a cleared environment, an API-key sign-in is refused by `rnplens doctor --agent`, and no command constructs an API client (`tests/test_no_billed_api.py`). Codex uses your ChatGPT plan's allowance; RNPLens cannot guarantee that supplemental credits are never drawn once the allowance is exhausted (setup_and_privacy.md). |
| What is sent? | One planning message per question (and per Codex follow-up): the question, the list of available tools, and the task inputs by **opaque identifiers** (`run_001`, `protein_sequence_001`, ...). File names, folder names, absolute paths, coordinates, sequences and experimental-reference identities are not sent; a pre-send check refuses the message if any remains after redaction. Numbers in the answer are filled in locally from evidence records. |
| What stays local? | Structures, references, every computation, every number, the evidence records and the viewer page. |
| Can the model read hidden references or evaluation answers? | Codex runs with its shell, code-execution, browser, image and web-search tools disabled (`codex_llm.HARDENING`), inside a jail that exposes only the call folder, the Codex installation and its login file. It returns a plan; RNPLens validates the plan against the tool policy before running anything. The task inputs are seen only through their opaque identifiers. |
| Qualification status | **Experimental.** The assistant is tested with a scripted stand-in for Codex (no model). Live qualification (LIVE_QUALIFICATION_v1) is **prepared, not run**: no live Codex call has been made for RNPLens 0.4. |
| Linux or macOS? | Either, on its own: one computer is enough ([install_linux.md](install_linux.md), [install_macos.md](install_macos.md)). The confinement differs between the two systems; the differences are listed in [platforms.md](platforms.md). The macOS Seatbelt jail is new in this change; its confinement qualification is recorded in `records/native_platforms/`. |
