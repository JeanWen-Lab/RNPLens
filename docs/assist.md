# The question menu: `rnplens assist`

`rnplens assist` is a terminal menu over an imported project. Each item runs a deterministic RNPLens function; no
language model is involved and nothing leaves your computer (see `setup_and_privacy.md`). RNPLens analyses
existing predicted structures only: it does not predict structures and does not rank or select candidates.

```
rnplens import exec_A exec_B --protein-seq protein.fasta --rna-seq rna.fasta --out P --engine BOLTZ2
rnplens analyse P --out A
rnplens assist --project P --analysis A
```

## The six items

| item | question |
|---|---|
| A | Compare binding surfaces and contacts |
| B | Inspect contacts in an RNA region |
| C | Compare two prediction runs or model versions |
| D | Explain an existing result |
| E | Group distinct binding hypotheses |
| F | Export results and Methods |

Which functions sit behind each item is decided by the capability registry (`rnplens.capabilities`): every 0.4
module declares its functions with a menu letter, a status and the inputs it needs. In your installation:

* an item with at least one offered function can be chosen; each function is shown with its status:
  **QUALIFIED** (reuses a route qualified earlier, unchanged), **DESCRIPTIVE** (new, tested, descriptive output) or
  **EXPERIMENTAL** (needs further evidence; you are asked to confirm before it runs);
* an item with no offered function is shown as *unavailable* with the reason (for example "module not installed"
  or the reason a function was withdrawn) and cannot be run;
* everything RNPLens deliberately does not offer is listed under **Not available** with its reason: Diagnose
  (user-facing; BLOCKED in 0.4, its commands exit with code 5), Evaluate's four-axis geometry, RNA conformation difference, candidate ranking or
  selection, structure prediction, and mutation or experiment advice.

`rnplens assist --project P --list` prints the menu, with these reasons, and exits.

## Inputs

Inputs are asked for one at a time and checked before anything runs; a rejected answer is explained and asked
again.

| input | how it is checked |
|---|---|
| RNA range, protein range | `start-end` in construct numbering, within 1 to the construct length from the project manifest |
| runs | names (or the numbers shown) of runs in the project manifest; "two runs" needs two distinct runs |
| analysis folder | must contain `summary.json` (written by `rnplens analyse`) |
| reference, execution record | must be existing files |
| evidence ID | `<file>#/<pointer>`, for example `region_40-60/region.json#/contacts/3` |

Optional inputs can be skipped with Enter.

## Results

After a function runs, the menu shows where its results were written, their evidence IDs (the first ten and the
total) and the function's one-sentence interpretation limit. Every reported value in those files carries an
evidence ID of the form `<path relative to the analysis folder>#<JSON pointer>`; `rnplens explain` (item D) traces
one back to its files, structures and definition. A function that fails is reported and the menu stays open.

For contact results (items A, B, C and E) the menu also lists the **contact tables** (`report/contacts_by_output.json`,
`report/result.json`, and `region_<a-b>/region_contacts.tsv` for each region) and the **structure viewer page**
`ANALYSIS/viewer/viewer.html` (offline Mol*; open it from disk). If the analysis has no page yet, it is written with
`rnplens view PROJECT --analysis ANALYSIS`, unchanged; if that is not possible, the command is shown instead. The
natural-language mode prints the same links after the answer and writes them to `RUN/result_links.json`. `--json`
output carries them as `result_links`.

## Scripting without prompts

```
rnplens assist --project P --analysis A --item B --rna 40-60 --runs exec_A,exec_B
rnplens assist --project P --analysis A --item B --rna 40-60 --protein 10-30 --runs 1,2 --json
rnplens assist --project P --analysis A --item E --allow-experimental
rnplens assist --project P --item F --capability <function id> --param name=value
```

Exit codes: 0 done; 2 an input is missing or invalid (the message names the option to give); 3 the item is
unavailable in this installation; 4 the function ran and refused or failed; 5 the capability is blocked in 0.4. An EXPERIMENTAL function runs without prompts only with `--allow-experimental`.
`--param NAME=VALUE` supplies any further input a function declares.

For function authors: the menu passes inputs by keyword. It looks for these parameter names, in order, and uses the
first one the function accepts (a function with `**kwargs` receives the first name): project → `project`,
`project_dir`, `project_root`; analysis → `analysis`, `analysis_dir`, `analysis_root`; RNA range → `rna_range`
(a two-element list) or `rna_start` and `rna_end`; protein range → `protein_range` or `protein_start` and
`protein_end`; runs → `runs` (a list) or `run_a` and `run_b`; reference → `reference`, `reference_path`;
execution record → `run_record`, `record`; evidence ID → `evidence_id`, `evidence`. A function that accepts none of
them for a declared input is reported as unavailable when chosen.

## Natural-language questions (optional)

```
rnplens assist --project P --task T --nl "Do the two runs agree on contacts in RNA 40-60?"
```

This mode is **EXPERIMENTAL**: the planner with the 0.4 tools has not been qualified live, and it differs from the
assistant under sealed evaluation (`f998830`). The question is handed to the existing RNPLens assistant
(`rnplens_assistant.ask`) only when
`rnplens doctor --agent` reports every Codex check READY (supported system, tested Codex CLI, ChatGPT sign-in,
tested model, the system's confinement (bubblewrap on Linux, Seatbelt on macOS), jail script). Otherwise the question is not sent anywhere: the menu says which check failed and offers
to open the question menu instead. `--task` is the folder with the prediction folders and FASTA files that the
assistant may list; `--nl-out` names the run folder to create. The answer, the plan, the evidence records and a run
record are written there; the plan can be replayed without any language model
(`python -m rnplens_assistant replay`). What is sent to your Codex account is listed in `setup_and_privacy.md`.

## Structure viewer pages

RNPLens functions can write an offline structure page with `rnplens.viewer.structure_page`:

```python
from rnplens import viewer
st = viewer.project_structures("P")                       # construct-numbered copies, chain ids from the manifest
for s in st:                                              # contacts with RNA 15-30 from Report's own records
    s["highlights"] = viewer.contact_highlights("A", s["key"], protein_seq, rna_seq, rna_range=(15, 30))
viewer.structure_page("A/view_rna_15-30", [{k: s[k] for k in ("path", "label", "chains", "highlights")} for s in st])
```

**Status: automatically tested; basic display and interaction confirmed manually by the owner on macOS (2026-10-18); switching between binding-hypothesis representatives and offline operation not yet confirmed manually; not fully visually qualified.** Automated
check (records/viewer/MOLSTAR_VISUAL_VERIFICATION.md): on the tested Linux host, the six demonstration pages (1VTM RNA 1-3, 2JEA RNA 26-35, 6BJG group representatives at 0.3/0.5/0.7 and all 50 6BJG structures) were rendered in headless Chrome for Testing 155 with software WebGL (SwiftShader), with networking disabled and with every request logged: only file: and data: requests were made, and the intended chains, construct positions, Report contact highlights and group representatives were shown (checked through the Mol* API and by inspection of the screenshots). One defect found by this check (highlight colour not visible on the ribbon) was fixed. This is software-rendered headless evidence inspected by an agent. Owner-reported manual test on macOS (2026-10-18; records/viewer/MOLSTAR_VISUAL_VERIFICATION.md): the 2JEA page opened, displayed the structures, rotated and zoomed, responded to nucleotide clicks, and different selections highlighted different regions. Not yet confirmed by a person: switching between binding-hypothesis representatives (6BJG) and operation with the network disconnected; the viewer is therefore not fully visually qualified. Known limits: Mol* panels name structures by an in-memory arcp:// URI (the snapshot title and side table carry the readable name), and the sequence panel does not colour highlighted positions.

The folder then holds `viewer.html`, copies of the structures, the Mol* files and `viewer_manifest.json` (every file
with its SHA-256, the highlighted residues with their evidence IDs). The page uses the prebuilt Mol* Viewer
(version 5.13.1, MIT licence, unchanged; licence in `assets/LICENSE.molstar.txt`); RNPLens adds no renderer of
its own. One structure is shown at a time; switch with Previous / Next or the structure selector of the contact
explorer beside the viewer (feature/nt-contact-explorer). Protein is grey, RNA sand,
highlighted protein residues orange and highlighted RNA residues blue, with residue labels when there are at most 40
per molecule. The table under the viewer lists every highlighted residue with its evidence ID. Clicking an RNA
nucleotide (or a protein residue) shows only its Report-recorded contacts in the structure on screen, with a contact
panel; see the viewer guide [viewer.md](viewer.md).

Open `viewer.html` directly from disk; no web server and no network are needed. Manual open check (do this once on
a new computer): with the network switched off, open the page in Firefox or Chrome; the status line under the
viewer must read `LOADED: <n> structure(s) loaded from this folder; one is shown at a time`, the structures must be drawn with the colours
above, and the browser's network panel must show no request other than local files and in-memory data. A page whose
files were moved apart shows `ERROR: ...` with the missing file instead.

## Interpretation limits

* The menu only runs functions and shows their results; it adds no interpretation. Each result carries its own
  limit sentence; read it with the result.
* Recurrence of a contact or a surface among predictions is not confidence and does not make a prediction right.
  No item ranks structures or groups, and groups are never ordered by size.
* A highlighted residue in a viewer page is a feature of that predicted structure, taken from the record named by
  its evidence ID; it is not an observation of the real complex.
* Items marked unavailable reflect this installation; the reasons say whether a function is missing or was withdrawn.


## Follow-ups and the structure view (0.4 integration)

- **Follow-ups.** After a menu result, `--followup local` offers deterministic follow-ups with no language model.
  `--followup codex` asks Codex to choose one from a fixed allowlist, and only after you have recorded consent.
  Execution needs confirmation (`--yes` in scripts). This is EXPERIMENTAL; see [followup.md](followup.md).
- **Structure view.** `rnplens view PROJECT --analysis A [--rna 13-23]` writes an offline Mol* page with each
  structure's Report contacts highlighted. The grouping difference page links to `A/viewer/viewer.html` once it
  exists. Status: see above (not fully visually qualified).
- **Exit codes.** 0 means success. 2 means an input error. 3 means the item is unavailable. 4 means the function ran
  and refused or failed (for example, it refused an answer or request it cannot accept); the reason is printed, and
  nothing is reported as a result. 5 means the capability is blocked in 0.4 (the function raised a block, such as
  `DIAGNOSE_BLOCKED`, or returned the status `BLOCKED`); the message names the block, and nothing is reported as a
  result. A refusal is never reported as a block, and a block never as a refusal. In the interactive menu a blocked
  item prints `BLOCKED:` with the reason and the menu stays open.

- **Viewer output folders.** `rnplens view P --analysis A` writes `A/viewer/viewer.html`. With `--rna a-b` it writes
  `A/viewer_a-b/viewer.html`, and `--out DIR` overrides both. `--ids s001,s002` limits the structures shown, in the
  order given. `--representatives 0.5` (or 0.3, 0.7; needs `rnplens group` first) shows the representative of each
  binding-proposal group at that threshold, in the groups' display order and labelled as `rnplens group` labels it
  ("representative of group 2 (t=0.5)"), then each engine-designated structure that is not a representative
  ("engine-designated structure (member of group 1) (t=0.5)"); it writes `A/viewer_representatives_t0.5/`.
  Groups are never ordered by size, and a representative is not a selection of the right structure.
- **`rnplens doctor --project`** takes a folder written by `rnplens import` (or a managed project's import folder),
  not the prediction folders; before an import, leave it out.
- **What `rnplens doctor` counts.** "offered: 1 QUALIFIED, 9 DESCRIPTIVE" counts registered functions, not menu
  items:
  - one menu item can offer several functions (item C: run comparison);
  - some functions are not menu items (clarify, update, group-diff, setup check).
