# RNPLens on macOS: install and use (one computer)

Everything runs on this Mac under your own account. You do not need Linux, SSH, bubblewrap or a second computer.

## 1. Install RNPLens (no administrator rights)

RNPLens 0.4 is one release: this command installs RNPLens together with the optional AI Assistant package.
Installing that package neither enables nor starts it — the Assistant is optional **at run time**, it needs the
extra setup in section 2, and nothing in this section contacts a language model.

```bash
python3.11 -m venv ~/rnplens-venv && source ~/rnplens-venv/bin/activate
python -m pip install "rnplens[html]" ./assistant      # from a source checkout: pip install -e ".[html]" -e ./assistant
rnplens selftest                                        # scientific self-test of this installation
```

RNPLens Standard (no AI) is ready now: `rnplens import`, `rnplens analyse`, the question menu `rnplens assist --project P`.
On macOS arm64 one value has an approved numerical tolerance ([installation.md](installation.md)).

## 2. Optional at run time: enable the AI Assistant

1. **Codex CLI 0.159.3**, a native build. It is found at `~/.codex/packages/standalone/current/bin/codex`, or set
   `RNPLENS_CODEX_BIN` to the native `codex` binary.
   The folder that holds the binary is granted to the Codex process in full, so it must be a folder of its own.
   A binary placed directly in your home directory, in a root, or in a shared system or scratch folder is
   refused (exit 64) with an explanatory message before Codex starts; no run is silently given wider access.
2. **File-based login storage.** RNPLens confines Codex so that it cannot use the macOS keychain. In
   `~/.codex/config.toml` set `cli_auth_credentials_store = "file"`.
3. **Sign in with your own ChatGPT account:** `codex login`, then "Sign in with ChatGPT". This writes
   `~/.codex/auth.json`. No API key is used.
4. **Check:** `rnplens doctor --agent`, from an **ordinary Terminal window**. Every line must be READY.
   - The Seatbelt check applies a harmless sandbox to `/usr/bin/true`.
   - The jail check runs a self-probe with no model call. It confirms that your project folder cannot be read or
     listed from inside, that the login file can be read, and that the call folder is writable.

Seatbelt cannot start inside another sandbox. RNPLens then refuses, and the doctor reports the Seatbelt check as
ACTION REQUIRED. This happens, for example, inside some sandboxed apps or other AI agents. Run RNPLens from Terminal
instead.

## 3. Ask a question

```bash
rnplens import run_A run_B --protein-seq protein.fasta --rna-seq rna.fasta --out P
rnplens assist --project P --nl "Do the two runs agree on contacts in RNA 26-35?" --nl-out R
python -m rnplens_assistant replay R/plan.json --task TASK --out R_replay      # replay without any language model
open R/tools/analysis_project_1/viewer/viewer.html                         # the path is printed after the answer
```

## What the jail does on macOS

The whole Codex process runs under Seatbelt with a deny-by-default profile (`codex_seatbelt.sb`).

| | allowed |
|---|---|
| read | operating-system libraries, time zones and certificates; the Codex installation; the login file; one per-call folder |
| write | the per-call folder; the login file, in place |
| start programs | the Codex installation only |
| network | outbound HTTPS and the system DNS resolver only |

Everything else cannot be read, listed or written: your home folder, SSH keys, projects, references, other call
folders, and Codex's own settings and history. The environment is cleared, with no API keys.

The loader also needs to open the public root directory `/` as a directory
descriptor. Its explicit `file-read-data` rule is literal and nonrecursive: it
permits reading/listing `/` itself, not `/Users`, the home directory or any other
descendant. The `/System/Volumes/Data` protection remains in place. This narrow
exception follows the installed Apple `dyld-support.sb` loader requirement.

Unlike Linux, there is no private mount namespace. Denied paths still exist, but their contents and listings are
blocked. Details: [platforms.md](platforms.md).
