# Supported platforms and the two modes (RNPLens 0.4 release candidate)

RNPLens has two modes. Both use the same qualified scientific computations.

- **RNPLens Standard (no AI).** You choose the analyses (`rnplens import`, `analyse`, `region`, `group`, `view`,
  `explain`, `export-methods`, or the question menu `rnplens assist --project P`). No language model, no account,
  no network access.
- **RNPLens Assistant (optional, AI-guided, EXPERIMENTAL).** `rnplens assist --nl "question"`: Codex proposes a plan,
  RNPLens checks and runs it with the same tools, and you receive an evidence-linked answer. It needs your own Codex
  (ChatGPT) sign-in and the Codex CLI. The whole Codex process runs confined by the operating system's own sandbox:
  bubblewrap on Linux, Seatbelt on macOS. RNPLens stays fully useful without it.

**One computer is enough.** Each supported system runs both modes on its own: a Linux user needs no Mac, and a Mac
user needs no Linux server, no SSH and no bubblewrap. There is no second computer in routine use. (The blinded
evaluation of the Assistant used a separate machine for the sealed answers; that arrangement belongs to the
evaluation only.)

## Platform matrix

| platform | Standard | Assistant | offline viewer page |
|---|---|---|---|
| Linux x86-64, Python 3.10-3.12 (tested: Ubuntu 26.04.1, Python 3.11.15) | **supported, tested** (full suite; clean wheel, sdist, documented and no-matplotlib installs) | **supported natively** (EXPERIMENTAL): needs Codex CLI 0.159.3 (tested version), ChatGPT sign-in, the tested model, and bubblewrap with unprivileged user namespaces (some systems need an administrator to install bubblewrap or allow user namespaces); `rnplens doctor --agent` must report every check READY. Tested only with a scripted stand-in for Codex; **not live-qualified** (no live Codex call has been made for 0.4) | writes and serves nothing; open the page from disk |
| macOS arm64, Python 3.10-3.12 (tested: macOS 27.0.1, Python 3.11.17) | **supported, tested** (full suite; clean installs). One approved single-value numerical tolerance (`records/release/TOLERANCE_POLICY_AMENDMENT_1.md`) | **supported natively** (EXPERIMENTAL): needs Codex CLI 0.159.3, ChatGPT sign-in with Codex's file-based login storage, and the tested model. The Codex process runs under Seatbelt (`sandbox-exec`, built into macOS; no administrator rights). Run from an ordinary Terminal session: Seatbelt cannot start inside another sandbox, and RNPLens then refuses. `rnplens doctor --agent` must report every check READY. **not live-qualified**; the macOS confinement qualification is recorded in `records/native_platforms/` | basic display and interaction confirmed by the owner on macOS; switching between binding-hypothesis representatives and offline operation not yet confirmed (not fully visually qualified) |
| Linux or macOS on other architectures | runs, not qualified: run `rnplens selftest` and keep its output with your results | as above for the same system | as above |
| Windows | unsupported | unsupported | not tested |

Python 3.13 and later are refused at install time (`requires-python <3.13`).

No public web server, no laboratory GPU and no Codex subscription are needed for Standard.

Installation and first use: [install_linux.md](install_linux.md) and [install_macos.md](install_macos.md).

## How the confinement differs between Linux and macOS

Both jails confine the **entire** Codex process (not only RNPLens's own tool calls), start from nothing visible, and
refuse to run if they cannot be set up. There is no unconfined fallback.

| property | Linux (bubblewrap, `codex_jail.sh`) | macOS (Seatbelt, `codex_seatbelt.sh` + `codex_seatbelt.sb`) |
|---|---|---|
| files the Codex process can read | read-only `/usr` and a few `/etc` files, the Codex installation, the login file, one per-call folder (as `/work`) | operating-system libraries, time zones and certificates, the Codex installation, the login file, one per-call folder (real path) |
| files it can write | the per-call folder, the login file (in place) | the same |
| everything else (home folder, SSH keys, projects, references, other call folders, Codex's own settings and history) | does not exist inside (private mount namespace) | exists but cannot be read, listed or written; path metadata only for the parent folders of the allowed paths |
| programs it can start | programs under `/usr`, all inside the same private view (Codex's shell tool is switched off) | only the Codex installation (no shell, no interpreter, no other program) |
| network | shared with your account: the internet, loopback services, abstract Unix sockets | outbound HTTPS (TCP port 443) and the system DNS resolver only; no other local or remote port, no Unix sockets |
| environment | cleared; API keys removed | cleared; API keys removed |
| needs an administrator | sometimes (bubblewrap package; user-namespace policy) | no |
| when it cannot be set up | the assistant refuses (`rnplens doctor --agent` names the check) | the same, including inside another sandbox |

Apple marks `sandbox-exec` as deprecated; it ships with current macOS and is the mechanism Codex itself uses on
macOS. If a future macOS removes it, the assistant refuses on that system.

Qualification evidence for each row (commit, test, record) is in the release-candidate qualification matrix and, for
the native-platform change, in `records/native_platforms/`.
