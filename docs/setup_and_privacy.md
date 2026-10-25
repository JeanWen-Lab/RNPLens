# Setup, requirements and privacy (RNPLens 0.4 development)

RNPLens analyses protein-RNA structures that were already predicted by other methods. It does not predict
structures, it does not rank candidates, and agreement among predictions is never reported as confidence.

This page says what each mode of the interactive workflow needs, what it does on your computer, and what, if
anything, leaves your computer. `rnplens doctor` checks all of it for you; it is described at the end.

## Modes at a glance

| mode | command | needs a language model | what leaves your computer |
|---|---|---|---|
| toolkit and workflow | `rnplens import`, `rnplens analyse`, `rnplens report ...` | no | nothing |
| question menu | `rnplens assist --project P` | no | nothing |
| structure viewer page (automatically tested; basic display and interaction confirmed manually by the owner on macOS (2026-10-18); switching between binding-hypothesis representatives and offline operation not yet confirmed manually; not fully visually qualified) | `rnplens view`, or RNPLens functions (`rnplens.viewer.structure_page`) | no | nothing; the page opens from disk and makes no network connection |
| natural-language planner (EXPERIMENTAL; not live-qualified) | `rnplens assist --project P --task T --nl "question"` | yes: Codex CLI with your ChatGPT sign-in | the question and opaque identifiers for the task's folders and files (never their names or paths), whether a reference is supplied (reference-based tasks only) and the RNPLens documentation (details below) |
| follow-up, local (EXPERIMENTAL) | `rnplens assist ... --followup local` | no | nothing |
| follow-up, Codex (EXPERIMENTAL) | `rnplens assist ... --followup codex` | yes: Codex CLI with your ChatGPT sign-in | derived summaries only (question, agreement values, contact labels and positions, counts, opaque identifiers for runs, structures and evidence; never file, folder, run or sample names), and only after you opt in for the project |

The question menu and the toolkit are the language-model-free path. They give the same deterministic results
whether or not Codex is installed, and they never start Codex.

## Supported platforms

| platform | toolkit, workflow, question menu, viewer page | natural-language planner |
|---|---|---|
| Linux x86_64 | supported (the tested interactive environment for 0.4) | supported, with bubblewrap and unprivileged user namespaces; EXPERIMENTAL, not live-qualified |
| macOS arm64 | runs; the one known numerical parity difference is covered by an approved single-value tolerance (`records/release/TOLERANCE_POLICY_AMENDMENT_1.md`; see `installation.md`) | supported natively, with Seatbelt (built in; no administrator rights); EXPERIMENTAL, not live-qualified; not inside another sandbox |
| Linux or macOS on another architecture | runs, but is not a qualified platform: run `rnplens selftest` and keep its output with your results | as above for the same system |
| Windows and others | unsupported | unsupported |

Requirements of the natural-language planner (one computer: Linux or macOS):

* the Codex CLI, tested version **0.159.3** (other versions are reported by the doctor as "untested version");
* sign-in with your **own ChatGPT account** (`codex login`, "Sign in with ChatGPT"); an API-key sign-in is not used;
* the model **gpt-6.1-sol** offered to your account (the only model the assistant was evaluated with);
* the confinement of your system, because every Codex call runs inside a jail chosen by `rnplens_assistant/confine.py`:
  on **Linux** `bwrap` (bubblewrap) and unprivileged user namespaces (`assistant/codex_adapter/codex_jail.sh`); on
  **macOS** Seatbelt, which is built in (`codex_seatbelt.sh` with the profile `codex_seatbelt.sb`), plus Codex's
  file-based login storage (`cli_auth_credentials_store = "file"`), and an ordinary Terminal session (Seatbelt cannot
  start inside another sandbox). The jail cannot be replaced: `RNPLENS_CODEX_JAIL` naming any other script is
  refused, and the jail process gets only `HOME`, `CODEX_HOME`, `RNPLENS_CODEX_BIN` and `PATH=/usr/bin:/bin` from your
  environment (on Linux, `bwrap` must therefore be in `/usr/bin` or `/bin`);
* the `rnplens_assistant` package (`assistant/` in the RNPLens source).

Python 3.10 to 3.12 and the pinned dependencies (`DockQ==2.1.3`, `gemmi==0.6.5`, `biopython==1.84`,
`numpy==1.26.4`, `scipy==1.13.1`) are required in every mode; `matplotlib` is optional (images in the HTML pages).

## Your Codex account, usage and credits

Codex mode uses your own ChatGPT account and its usage allowance; RNPLens cannot guarantee that supplemental
credits will not be used once the included allowance is exhausted; no API key is required or used.

In more detail:

* Each natural-language question uses one Codex call for the plan, and one more only when the policy rejects a
  planned step and asks for a corrected plan. The answer itself is written by deterministic templates from the
  evidence records, without another call. Every call counts against your plan's usage.
* The adapter reads the usage level and the credits balance that Codex reports after each call. It refuses further
  calls when the plan usage reaches its guard threshold (85 % of a window) and stops a run when the credits balance
  changes. These guards act on reported numbers and are not a hard block: RNPLens cannot stop Codex or your
  account from drawing supplemental credits within a call, so set your own account limits if that matters to you.
* No API key is read or used. `OPENAI_API_KEY` and `CODEX_API_KEY` are removed from the environment of every Codex
  call and of the doctor's own probes.
* No separately billed API is called. Every language-model route of RNPLens (`rnplens assist --nl`, Codex
  follow-ups, `python -m rnplens_assistant ask`) builds `rnplens_assistant.codex_llm.CodexClient`, which runs
  `codex exec` with your ChatGPT sign-in inside the jail (started with `--clearenv`). A sign-in with an API key is
  reported by `rnplens doctor --agent` as ACTION REQUIRED and the assistant stays off. The package still contains
  `rnplens_assistant.llm.Client`, the OpenAI API client of the frozen 16 Oct development record; no command
  constructs it, the `openai` package is not a dependency, and the former optional `llm` extra was removed
  (`tests/test_no_billed_api.py`).
* RNPLens never reads, copies or prints Codex's login file. The jail binds the login file into Codex's own private
  namespace so Codex can authenticate; the doctor reports only the status line of `codex login status`.

## Exactly what leaves your computer

**Question menu (`rnplens assist`).** Nothing. Each menu item calls a deterministic RNPLens function on your
computer. No language model is started and no network connection is made.

**Viewer pages.** Nothing. The page loads the vendored Mol* files and the structure copies from its own folder;
its Content-Security-Policy allows connections only to the page's own origin and to in-memory data, so the
database buttons in the Mol* interface cannot fetch remote entries either.

**Natural-language planner (`rnplens assist --nl`).** One request to your Codex account containing:

1. your question, after a pre-send redaction (and, if a corrected plan is requested, the previous plan and the
   rejection reasons, redacted in the same way): file, folder and run names of the task in any letter case become
   their identifiers; an absolute path becomes the identifier of the task item it names, otherwise `<path>`; the
   name of any top-level file that is not offered to the planner (an undeclared or restricted reference, or any
   other file) becomes `<undisclosed file>`;
2. opaque identifiers for the task folder's contents, never their names (0.4): each top-level folder becomes
   `run_001`, `run_002`, ...; its structure files `run_001/candidate_001`, ...; its other files `run_001/file_001`, ...;
   the top-level FASTA files `protein_sequence_001` / `rna_sequence_001` (by alphabet); the number of listed files;
3. whether an experimental reference is supplied: for a reference-based task (references declared in `task.json`)
   only `reference_001`, ... and that reference-based metrics are available, never the reference's name, path or
   content. For a reference-free task nothing about any reference is sent: top-level files that are neither FASTA
   files nor declared references (including any undeclared or restricted reference) are not listed and not counted;
4. the RNPLens documentation that tells the planner which analysis answers which question (the packaged
   `which_analysis_should_i_use.md` and an availability note).

It never sends atomic coordinates, sequences, or any computed value (contacts, agreement fractions, DockQ values,
counts), and it never sends file or folder names or paths. The identifiers are assigned deterministically (sorted names) and the map
from identifiers to the real names is written only to `redaction_map.json` in the run folder; the plan the model
returns is checked in identifiers, translated to the real paths on your computer, and the answer is rendered locally
with the real names. **Pre-send check (0.4):** after the redaction, the outgoing message is checked again for an
absolute path, any real file, folder or run name of the task (any letter case) and any undisclosed file name; if one
is still found, **nothing is sent** (no Codex call), the run folder says why, and you are asked to rephrase. The
redactions made are listed in `run_record.json` (`redaction.question_redactions`). A target ID that you type in the
question yourself and that is not a file or folder name is sent as typed, so leave it out if it is confidential. Inside the jail, Codex sees only a per-call folder holding
the answer schema (the request arrives on standard input); your project, references and results are not mounted.
How OpenAI processes and retains the request is governed by your ChatGPT account's terms, not by RNPLens.

**Follow-up (0.4, EXPERIMENTAL; this replaces the "Future follow-up mode" note of earlier drafts).** In local mode
(`--followup local`), nothing is sent: deterministic suggestions over your results only. In Codex mode
(`--followup codex`), one planning message (at most two, with one replan) goes to your Codex account, and only
after an explicit opt-in per project, recorded in `<project>/.rnplens/consent.json` with a timestamp, the
category-list version and the scope.

The message contains:
1. your question, redacted as for the planner (absolute paths become `<path>`; run, sample and file names in any
   letter case become identifiers; the message is then checked again and not sent if anything remains);
2. the agreement values computed by Report, with evidence IDs;
3. contact labels with residue and nucleotide letters and construct positions;
4. counts;
5. opaque identifiers instead of names: `run_001` for each run, `candidate_001` for each structure's sample name,
   `evidence_001` for each evidence ID (evidence IDs are output paths), `output_001` for each analysis output, and the
   RNPLens structure IDs (`s001`). The real names and the map stay in the follow-up folder (`redaction_map.json`).

It never contains:
- coordinates or structure file content;
- sequences;
- file contents, file paths, or file, folder, run or sample names taken from your files;
- reference structures or reference files, or their names or paths;
- engine confidence values.

Values derived from a reference (DockQ, fnat, iRMSD, LRMSD) are sent only if the opt-in itself allows them.
Before sending, RNPLens checks the outgoing message for sequence fragments, coordinate records, absolute paths, file
hashes, reference file names and any real run, folder, sample or file name of this analysis, and refuses to send if
any is found. An opt-in recorded for the earlier category list (`followup-categories-1`) no longer counts; the
follow-up asks for a new opt-in to list 2. Without a current opt-in, no Codex process
is started.

`python -m rnplens_assistant consent show --project P` prints the exact screen; `consent opt-out` revokes the
opt-in. The model's rationale is stored but never shown, and every number in the answer comes from RNPLens' own
records. Codex call records default to `~/.rnplens/codex_calls` (override: `RNPLENS_CODEX_CALLS`), outside any
project. The jail used is always the one shipped with this installation (`rnplens_assistant/codex_adapter/codex_jail.sh`;
on macOS `codex_seatbelt.sh`); there is no override. Details are in [followup.md](followup.md).

## `rnplens doctor`

```
rnplens doctor                          # installation, platform, dependencies, viewer files
rnplens doctor --project P --out O      # also read access to P and write access to O
rnplens doctor --agent                  # also the optional Codex natural-language mode
rnplens doctor --json                   # machine-readable result
rnplens doctor --out O --save           # also write O/doctor.json (the only file the doctor ever writes)
```

Every check is **READY**, **ACTION REQUIRED** or **UNSUPPORTED**, and each one that is not READY carries a one-line
remedy. The exit code is 1 when a required check is not READY, and 0 otherwise. An optional component is shown but
never changes the exit code: in an installation without the `html` extra, **Optional matplotlib** is ACTION REQUIRED
(with its remedy) and the exit code is 0, because only images are unavailable (Report then writes its JSON output and
no HTML page). The summary line then ends with "(1 of them optional; exit status 0)".

| check | what is looked at |
|---|---|
| Python | interpreter version (3.10 to 3.12) |
| RNPLens, qualified components | the RNPLens version; installed components and the pinned SHA-256 of every frozen source (the internals of `rnplens provenance`) |
| 0.4 functions | the capability registry: how many functions are offered at each status, how many are not available |
| platform (toolkit / assistant) | operating system and architecture against the table above |
| dependencies | installed versions against the qualified pins; matplotlib as optional |
| project / output folder | read access to `--project` (with its `manifest.json`), write access to `--out` or to the folder that would hold it; nothing is created |
| structure viewer | the vendored Mol* files against the SHA-256 recorded in `VERSION.json` |
| Codex CLI (`--agent`) | the binary the jail runs: `RNPLENS_CODEX_BIN` if set, else Codex's standalone install `$CODEX_HOME/packages/standalone/current/bin/codex` (a `codex` on `PATH`, for example a snap, is not used by the jail and is not checked; the doctor names it if it differs); `codex --version` against 0.159.3 |
| ChatGPT sign-in (`--agent`) | the status line of `codex login status`, with anything that looks like a token or an e-mail address removed |
| model (`--agent`) | whether `codex debug models` lists gpt-6.1-sol |
| bubblewrap (`--agent`, Linux) | `bwrap` present, and the probe `bwrap --ro-bind / / true` succeeds; a probe that cannot run (inside a container or sandbox) is reported as **not verified**, never as READY |
| Seatbelt (`--agent`, macOS) | `/usr/bin/sandbox-exec` present, and the probe `sandbox-exec -p '(version 1)(allow default)' /usr/bin/true` succeeds; inside another sandbox it fails and is reported as ACTION REQUIRED, never as READY |
| Codex jail, assistant package (`--agent`) | the jail shipped for this system is readable and passes its own no-model self-probe, run with the environment of a real call; `RNPLENS_CODEX_JAIL` naming another script is ACTION REQUIRED; `rnplens_assistant` imports |
| language-model functions (`--agent`) | enabled only when every check above is READY (and `RNPLENS_LLM` is not `off`) |

The doctor installs nothing, changes no setting, does not sign you in or out, and writes nothing unless `--save` is
given. Besides `git` (to record the source commit of a checkout), it runs only the four read-only commands of
`--agent`: `codex --version`, `codex login status`, `codex debug models` and the bubblewrap probe (Linux) or the
Seatbelt probe (macOS), plus the jail's self-probe.

## Interpretation limits

* A READY setup says the installation matches what was qualified; it says nothing about any scientific result.
* "Supported" for the natural-language planner means the planner and its checks were tested with the tested Codex
  version and model, with a scripted stand-in for Codex, on Linux and on macOS; other versions may behave
  differently, which is why they are flagged.
* The usage and credit guards act on numbers Codex reports after a call; they cannot prevent use within a call.


## Network inside the Codex jail (0.4)

The jail separates files, not the network. It is started with bubblewrap `--share-net`, because Codex has to reach
OpenAI for every call, so a process inside the jail has the same network access as your user account:

- the internet;
- services that listen on this computer's loopback interface (for example a print service, a local database or an
  SSH server on `127.0.0.1`), and abstract Unix sockets, because the network namespace is shared.

What limits use of the network is the set of Codex features, not the jail: for every call RNPLens switches off
Codex's shell and command execution, browser and computer use, web search, apps, plugins and image tools
(`rnplens_assistant/codex_llm.py`, `HARDENING`), so the model has no tool that opens a connection; only the Codex
program itself talks to OpenAI. The jail's filesystem view is described above (only system directories, the Codex
installation, the login file and one per-call folder). If services on this computer must not be reachable from a
Codex process, do not use the natural-language planner or the Codex follow-up on that computer; a network-restricted
jail is a proposal for a later version and is not implemented in 0.4.

## Network and files inside the Codex jail on macOS (Seatbelt)

The macOS jail limits the network as well as files. Its deny-by-default profile (`codex_seatbelt.sb`) allows only
outbound HTTPS (TCP port 443) and the system DNS resolver: no other port, no loopback services on other ports, no
Unix sockets (for example an SSH agent). Readable: operating-system libraries, time zones and certificates, the Codex
installation, the login file and the per-call folder; writable: the per-call folder and the login file (in place).
Only the Codex installation may be started. There is no private mount namespace: other paths exist but cannot be
read, listed or written. If Seatbelt cannot be applied, Codex is not started.

## Codex installation layouts supported by the jail (0.4)

- **Supported.** The Codex standalone installer layout, `$CODEX_HOME/packages/standalone/current/bin/codex` (with
  `CODEX_HOME` defaulting to `~/.codex`). Alternatively, set `RNPLENS_CODEX_BIN` to a native Codex binary; its
  directory is bound read-only.
- **Not supported.** A **snap**-installed `codex`: the snap wrapper `/usr/bin/snap` cannot run inside a bubblewrap
  namespace.
- **How to check.** `rnplens doctor --agent` runs the jail's no-model self-probe. It reports READY only if your
  project folder is invisible inside the jail and your login file is present.
