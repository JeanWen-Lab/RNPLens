# Project state, clarifications and incremental updates (`rnplens clarify`, `rnplens update`)

Status: **DESCRIPTIVE** (RNPLens 0.4; new and tested; no result here is a qualified measurement of anything new).
Capabilities: `clarify_and_resume` (`rnplens.clarify`), `incremental_update` (`rnplens.incremental`).

RNPLens analyses predicted structures that already exist. A *managed project* keeps those analyses over time. You can
add, change or remove prediction runs. Anything ambiguous is asked, and the answers are recorded. Only the work whose
inputs or definition changed is redone. These commands never predict structures. They never rank candidates or judge
which one is right. They never call agreement among predictions confidence or correctness.

## What a managed project is

```
demo/
  .rnplens/HEAD                 {"version": "v0006", "sha256": ...}: replaced atomically (os.replace)
  .rnplens/state/v0001.json ... one read-only file per version, never rewritten
  .rnplens/state/abandoned/     a version file written by an interrupted update, kept unchanged
  .rnplens/cache/<key>.json     completed work: its directory and the SHA-256 of every file in it
  imports/vNNNN/<group>/        an `rnplens import` project, only when the import had to be redone
  analyses/vNNNN/<group>/       an `rnplens analyse` directory, only when the analysis had to be redone
  analyses/vNNNN/index.json     which import and analysis directory each group uses in version vNNNN
  analyses/vNNNN/update_report.json, .html   before/after report against the previous complete version
```

`<group>` is `main` for the declared construct. It is `construct_<hash>` for a run that you chose to analyse
separately, as a different construct. Each `analyses/.../<group>/` directory is an ordinary analysis directory
(`summary.json`, `report/contacts_by_output.json`, `report/result.json`). The other 0.4 commands accept it unchanged.
`state.Project(root).head()["analyses"][group]["dir"]` gives the directory that is current.

Every version records:

- the SHA-256 of every input file (never a file name or time alone);
- the construct sequence hashes (declared, effective and per group);
- the chain correspondence of every structure, and the recorded answers;
- the tool version;
- the configuration and its hash;
- the designation (selection) rules;
- the cache key of every import and analysis, and of each part of that key.

Each version also records the SHA-256 of its parent version's file. So if an earlier version is changed or damaged,
`verify()` detects it. A corrupted state is refused, and nothing is changed.

## Commands

| command | does |
|---|---|
| `rnplens update DIR --init PATHS... --protein-seq P --rna-seq R [--engine E] [--case-id C]` | create a managed project and run the first import and analysis |
| `rnplens update DIR [PATHS...] [--remove-input PATH]` | add or remove input folders, re-scan all of them by hash, and recompute what changed |
| `rnplens update DIR --without-diagnose / --reference F / --no-reference` | change the analysis contract (recorded as such). `--with-diagnose` is refused in 0.4 (Diagnose BLOCKED, exit code 5); a project whose contract still asks for Diagnose is refused with exit 5 until `--without-diagnose` declares it off |
| `rnplens update DIR --status`, `--versions`, `--report VA VB` | show the state, show the history, or write a before/after report between two versions |
| `rnplens clarify DIR [--json]` | list the pending clarification requests (exit 3 if any) |
| `rnplens clarify DIR --answer N OPTION [--text "..."] [--revise] [--no-resume]` | record an answer and resume |
| `rnplens clarify DIR --resume`, `--history` | resume after an interruption; print every recorded answer |
| `rnplens relink DIR --search FOLDER` or `--map OLD=NEW` [`--dry-run`] | record where a copied or moved project finds its input files; each file is accepted only if its SHA-256 equals the recorded one (an edited file is a new input version: see [Edited input files](#edited-input-files-a-new-input-version)) |

The exit codes are: 0 complete; 3 a question needs an answer; 2 refused (with a message); 1 an analysis failed (the
version is recorded as FAILED, the previous complete version stays the reference for the next report, and nothing
failed is cached); 6 `PORTABILITY REFUSED`: the project was copied or moved and recorded input files are missing
or changed, so nothing was written. The message lists the files; put them back, or record where they are with
`rnplens relink`, then run the command again ([reproducibility.md](reproducibility.md)). `rnplens region`,
`rnplens view` and the other commands that read a managed project's import folder refuse in the same way.

Questions are answered by the number shown by `rnplens clarify DIR` or by their id. Once a question is answered it
is no longer pending, so its number is refused (`no pending question`); to change the answer, give the id with
`--revise`.

## Clarification requests (Function 3)

No request is ever answered automatically. Every request lists its options, and the inputs it depends on together
with their SHA-256.

| type | raised when | options |
|---|---|---|
| `construct_mismatch` | a run's chains differ from the construct (substitution, insertion, truncation) | `exclude_run` ("wrong folder"); `exclude_differing_files` (only if some of the run's structures match); `analyse_separately` ("intentional different constructs": a separate group, with the sequences read from the run's chains, offered only when they are consistent); `use_as_reference_set` (the declared construct is replaced by the run's sequences; runs that matched the old declaration are then asked about) |
| `chain_mapping` | a structure holds more than one chain that matches the protein or RNA construct | one option for each candidate mapping, e.g. `protein=A;rna=B` (a derived copy without the unused chains is written; the original is unchanged); `exclude_files` |
| `engine_designation` | a run of two or more structures has more than one confidence file for a structure, or a tie in the engine's ranking score | `engine_files` (keep the engine's own file naming); `designate:<run#sample>` for each included structure; `none` |
| `importer_question` | `rnplens import` asks its own question: an AF3/RF3 engine label, an uncertain chain type, a derived copy, or a top-level copy | the importer's own options. For a derived copy, `accept` or `exclude_file` applies to that one file only |

**Recording.** An answer is recorded in a new state version, together with:

- the time;
- your own words (`--text`);
- the chosen option;
- the facts it fixes (for example `run_in_analysis:<run> = false`);
- the SHA-256 of every input it depends on.

**Resuming.** After an answer, the pipeline resumes from the import. It reuses every cached step whose key is
unchanged, and recomputes only the steps the answer affects. The previous analyses stay where they are. The state
marks them as not current until the resume completes.

**Never asked twice.** A recorded answer is applied again, silently, for as long as every hash it depends on is
unchanged.

**Invalidated by change.** If an input it depends on changes, the answer is marked `INVALIDATED`. The changed hashes
are listed, the answer is kept in the history, and the question is asked again. Examples of such a change:

- a byte of a structure file;
- a new file in the run;
- the construct the mismatch was observed against.

**Contradictions are refused.** There are two cases:

- *The same question again.* Answering a question again with a different option is refused while the first answer
  still applies. Use `--revise` to replace it; the earlier answer is kept as `SUPERSEDED`.
- *Another question.* An answer whose facts contradict another recorded answer is refused. For example, choosing a
  designated structure for run X keeps run X in the analysis, and excluding run X then contradicts that. Revise the
  other answer first.

**Biological identity.** Competing chain mappings and incompatible constructs always need an explicit recorded
answer. Nothing is analysed until every pending question has one.

## Incremental updates (Function 5)

Each update:

1. hashes every file under the declared inputs, and detects new, changed, removed and moved files and runs;
2. re-checks every recorded answer against the hashes it depends on;
3. imports each group, reusing an earlier import whose key is unchanged;
4. raises the clarification requests above;
5. runs `rnplens analyse` for each group whose key changed, and reuses the other groups.

**The cache key.** The key of a computation is `state.analysis_key(kind, config, input_hashes, construct_sha,
correspondence, selection_rule, tool_version, definition)`. Its parts are:

- the exact input hashes (for an analysis: the import manifest, including every structure's SHA-256);
- the construct identity;
- the chain correspondence;
- the candidate and engine selection rules;
- the tool version;
- the metric definition and thresholds (contact cutoff, Report version, summary schema);
- the analysis configuration (Diagnose on or off; the reference and its SHA-256).

A change in any one part changes the key. The number of processes is not part of any result, so it is not in the key.

**When work is reused.** A cache entry is reused only if every file it recorded still has its recorded SHA-256.
An analysis that was computed earlier is referred to by `analyses/vNNNN/index.json`; it is not copied.

**One commit per update.** The state moves to the new version only when every step has finished. Completed steps are
cached as they finish. So if an update is interrupted (an exception, or the process exits), it leaves the previous
version current and readable, and running the same command again finishes it without redoing the completed steps.
A lock left behind by a process that no longer runs is taken over.

### Edited input files (a new input version)

An input file whose bytes changed is a **new input version**, not the old file in a new place. RNPLens never relinks
it, and it never alters an earlier version: every state version, import manifest, analysis and provenance record that
used the earlier bytes stays byte-identical. The continuation is the update workflow itself:

- **Edited in place** (the file is still in a declared input folder): `rnplens update PROJECT`. The update hashes
  the folder, lists the structure under "changed bytes" in the before/after report (for example
  `changed: exec_A#7K9D_model_0`), and commits the result as the next version. Until then, commands that read the
  earlier import (`region`, `view`, ...) refuse with `PORTABILITY REFUSED` (MISMATCH) and name `rnplens update`.
- **Edited copy in another folder** (for example a moved project whose copied inputs include an edited file):
  `rnplens relink PROJECT --search DIR` records the byte-identical files, refuses the edited one (exit 6) and prints
  the exact command, `rnplens update PROJECT NEW_FOLDER --remove-input OLD_FOLDER`. In one update this adds the folder
  that holds the edited copy and drops the declared input it replaces; the report lists the edited structure under
  "changed" and the two folders as a new and a removed run.

`rnplens update PROJECT --versions` lists the history; `rnplens update PROJECT --report VA VB` compares any two
versions. Tested in `tests/test_relink_edited_input.py`.

### The before/after report

The report (`update_report.json` and `.html`) separates three kinds of change:

1. **Candidate composition.** Input files and runs that are new, changed, removed or moved. For each group: the
   structures included, added, removed, or with changed bytes.
2. **Correspondence and construct.** Construct hashes; groups added or removed; the chain correspondence of
   structures present in both versions; answers recorded, invalidated or superseded.
3. **Analysis contract and tool version.** The tool version; configuration differences; changes of the metric
   definition; designation-rule changes for runs present in both versions.

For each group, the report also says whether the analysis was `RECOMPUTED` or `REUSED`, and which parts of the key
changed. When a structure is added, the correspondence and selection parts of the key also change, because those
records now include the new structure. The three sections list only changes to items present in both versions.

The report also gives a descriptive contact-support summary. For each engine, it counts how many contacts are listed
in every structure, in at least half, and in fewer than half. Each count has an evidence ID into the analysis
`summary.json`. Evidence IDs in this report are relative to the project directory.

## Worked example (7K9D example structures)

The inputs are copies of the bundled 7K9D runs `exec_A` and `exec_B`, plus a folder `other_construct` that holds a
copy of exec_B with the last two RNA nucleotides removed: a folder from another construct, put in by mistake. Paths
are shortened to the working directory, and the output was produced by these commands.

```
$ rnplens update demo --init in/exec_A in/exec_B in/other_construct --protein-seq 7K9D_protein.fasta --rna-seq 7K9D_rna.fasta --engine BOLTZ2 --case-id 7K9D_example
project demo: state v0002, NEEDS_CLARIFICATION
  1 question(s) need an answer: rnplens clarify demo
[exit 3]

$ rnplens clarify demo
rnplens clarify: 1 pending question(s) in demo (state v0002):
[1] construct_mismatch:in/other_construct  (construct_mismatch)
    1 structure(s) of run other_construct have chains that differ from the construct declared for this project. One project analyses one construct. Which applies?
      - exclude_run: wrong folder: exclude run other_construct from this project's analysis
      - analyse_separately: intentional different constructs: analyse run other_construct separately, as its own construct (protein 98 residues, RNA 58 nucleotides, as read from its chains)
      - use_as_reference_set: the declared construct is not the intended one: use run other_construct as the reference set (its chain sequences become the project construct; runs that matched the earlier declaration are then asked about)
[exit 3]

$ rnplens clarify demo --answer 1 exclude_run --text "other_construct was copied in from the truncated-RNA project by mistake"
rnplens clarify: recorded construct_mismatch:in/other_construct = exclude_run in state v0003
project demo: state v0004, COMPLETE
  main                     COMPLETE  analyses/v0004/main
[exit 0]

$ rnplens clarify demo --answer construct_mismatch:in/other_construct use_as_reference_set
rnplens clarify: refused: construct_mismatch:in/other_construct is not pending: it was answered 'exclude_run'. Use --revise to replace that answer.
[exit 2]

$ rnplens update demo                       # nothing changed: nothing recomputed, nothing asked again
project demo: state v0005, COMPLETE
  main                     COMPLETE  analyses/v0004/main (reused from v0004)
[exit 0]
```

Next, a third run is added: a copy of exec_B's structure as a new sample (`exec_C/7K9D_model_1.pdb`).

```
$ rnplens update demo in/exec_C
project demo: state v0006, COMPLETE
  main                     COMPLETE  analyses/v0006/main
  before/after report: demo/analyses/v0006/update_report.html
[exit 0]

$ rnplens update demo --versions
v0001  INITIALISED          project created
v0002  NEEDS_CLARIFICATION  first import and analysis; 1 question(s) need an answer
v0003  RESUME_PENDING       answer recorded for construct_mismatch:in/other_construct: exclude_run
v0004  COMPLETE             resume
v0005  COMPLETE             update
v0006  COMPLETE             update
```

What the v0005 to v0006 report contains:

- **(i) Candidate composition.** The new run `in/exec_C`; one structure added (`exec_C#7K9D_model_1`); included
  structures go from 2 to 3.
- **(ii) Correspondence and construct.** No change.
- **(iii) Analysis contract and tool version.** No change.
- **Analyses.** `main` was RECOMPUTED. The key parts that changed are the inputs, the correspondence and the selection
  rule (each now includes the new structure).
- **Contact support (descriptive).** Before, with 2 structures: 47 contacts, of which 42 are listed in every structure
  and 5 in at least half. After, with 3 structures: 47 contacts, of which 42 are listed in every structure, 3 in at
  least half and 2 in fewer than half.

The added structure is a copy of an existing one. It changes how the counts are distributed, not what is known about
the complex.

A complete fresh project built from the same final inputs (`exec_A`, `exec_B`, `exec_C`) gives the same
`summary.json` (apart from its creation time) and the same `contacts_by_output.json`. The tests check this
(`tests/test_incremental.py::test_add_modify_remove_runs_equal_fresh_recomputation`), and they repeat it after one
file is modified and after a run is removed.

## Python API

```python
from rnplens import state, clarify, incremental
P = state.Project("demo")
P.head(); P.versions(); P.verify()                   # verified against the hash chain
P.commit(change_dict, reason)                        # new immutable version; HEAD replaced atomically
P.record_decision(id, answer, depends_on, revise=False)
P.decisions(); P.decision_log()
P.cache_lookup(key); P.cache_store(key, outdir, meta)
state.analysis_key(kind, config, input_hashes, construct_sha, correspondence, selection_rule, tool_version, definition=None)
clarify.answer(P, "1", "exclude_run", text="...")    # then incremental.run_pipeline(P, "resume")
incremental.init_project(root, inputs, protein_seq, rna_seq, engine, case_id)
incremental.capability_update(root, add=[...], remove=[...])
```

## Interpretation limits

- Adding candidates is not evidence of increased correctness or confidence. It changes which predictions are
  counted, not what is known about the real complex.
- Changes in the contact-support distribution are descriptive. They say how often the supplied predictions list a
  contact, not whether the contact exists in the real complex. Predictions from one engine are not independent
  evidence.
- A recorded answer is a researcher's decision about construct identity, chain correspondence or designation.
  RNPLens records it and applies it consistently, but does not judge whether it is biologically right.
- `analyse_separately` and `use_as_reference_set` take the construct sequences from the chains of the structures in
  that run. They are offered only when those sequences are the same in every differing structure.
- An analysis key covers the inputs and the definitions listed above. It does not cover the operating system, or
  library versions other than the RNPLens version. The platform note for the rc3 example (a last-digit float
  difference on macOS) applies here too.
- Designation ambiguity is checked only for runs of two or more structures. For a single structure, Report reads only
  the engine's own `confidence_<model>.json`.

## Practical notes (0.4 integration)

- **Reproducibility status.** Numerical/evidence reproducibility: supported by the reported tests. Canonical-file
  byte reproducibility: passed in four development cases under the new contract. Complete managed-project byte
  reproducibility: not yet established. The original byte-identical replay check failed its pre-registered test (22
  of 43 files differed); that verdict stands.
  Remediation (records/replay/DETERMINISM_CONTRACT_v1.md): canonical managed-project files now hold relative paths and no time stamps, and volatile execution metadata moved to sidecars under .rnplens/run/. In the pre-registered retest on four further development cases (1VTM, 7K9D, 2JEA, 2Q66), each replayed in another directory at another time on the tested Linux host, every canonical file was byte-identical and no scientific content differed (records/replay/REPLAY_REQUALIFICATION_REPORT.md). Other outputs (importer manifests, summary.json, Report run records, region, explain, follow-up and Methods records) are not byte-identical between runs; a follow-up's evidence_sha256 changes when a project is moved. Byte identity was tested on one Linux host and one Python version only.

- **Finding the current folders of a managed project.**
  - `analyses/vNNNN/index.json` (the newest NNNN) names the current import folder and analysis folder of each group,
    for example `imports/v0004/main` and `analyses/v0004/main`.
  - Pass those folders to `rnplens region`, `rnplens explain`, `rnplens group`, `rnplens export-methods` or
    `rnplens assist`.
  - An unchanged analysis is referenced, not copied, so the folder may belong to an earlier version.
  - An interrupted update can leave a partly written folder (for example `analyses/v0003/main`); running the command
    again writes the next free name (`analyses/v0003/main.2`). Take the current folder from `index.json`, never from
    the folder names.
- **Making an ambiguous input to try the clarification step.** Copy one run folder, then remove the last two RNA
  residues from its structure file. For a PDB file with RNA chain B:
  `awk '!(($1=="ATOM"||$1=="HETATM") && substr($0,22,1)=="B" && substr($0,23,4)+0>58)' in.pdb > out.pdb`
  (58 is the 60-nt 7K9D RNA minus two; use your RNA length minus two, for example 33 for a 35-nt RNA).
  Keep the engine's confidence file beside it. `rnplens update --init` then asks a typed `construct_mismatch`
  question.
- **Bundled examples overlap.** `examples/reference_free/diagnose_7K9D/model_0` is byte-identical to
  `report_7K9D/exec_A/7K9D_model_0`. Import reports it as a duplicate.
