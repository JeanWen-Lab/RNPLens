# RNPLens on Linux: install and use (one computer)

Everything runs on this Linux computer under your own account. You do not need a Mac or a second computer.

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

## 2. Optional at run time: enable the AI Assistant

1. **Bubblewrap.** `bwrap` must be installed in `/usr/bin` or `/bin` (the jail runs with `PATH=/usr/bin:/bin`), and
   unprivileged user namespaces must be allowed. Many desktop
   distributions provide both. Where they are missing or blocked, an administrator has to install the
   `bubblewrap` package or allow user namespaces; RNPLens does not change system settings. Examples are some
   clusters, and Ubuntu 23.10 or later with its AppArmor restriction.
2. **Codex CLI 0.159.3**, standalone build. It is found at `~/.codex/packages/standalone/current/bin/codex`, or set
   `RNPLENS_CODEX_BIN` to a native Codex binary. A snap-installed `codex` cannot run inside the jail.
   The folder that holds the binary is granted to the Codex process in full, so it must be a folder of its own.
   A binary placed directly in your home directory, in a root, or in a shared system or scratch folder is
   refused (exit 64) with an explanatory message before Codex starts; no run is silently given wider access.
3. **Sign in with your own ChatGPT account:** `codex login`, then "Sign in with ChatGPT". No API key is used.
4. **Check:** `rnplens doctor --agent`. Every line must be READY. The jail check runs a self-probe with no model
   call: your project folder must be invisible inside the jail.

## 3. Ask a question

```bash
rnplens import run_A run_B --protein-seq protein.fasta --rna-seq rna.fasta --out P
rnplens assist --project P --nl "Do the two runs agree on contacts in RNA 26-35?" --nl-out R
python -m rnplens_assistant replay R/plan.json --task TASK --out R_replay      # replay without any language model
```

The answer, plan, evidence records and the offline structure viewer page are in `R/`.

## What the jail does on Linux

The whole Codex process runs in a bubblewrap mount namespace. It sees:
- read-only system folders;
- the Codex installation;
- your login file;
- one per-call folder.

It does not see your home folder, SSH keys, projects or references. It shares your network: the internet and
services on this computer's loopback interface. Details: [platforms.md](platforms.md) and
[setup_and_privacy.md](setup_and_privacy.md).
