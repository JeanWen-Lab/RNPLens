# Nucleotide contact explorer: qualification report

**Base:** `de66a966260fd7048b6116bada2ddeb2171ac6d3` (qa/0.4-karyon; descends from 80a2afb and 589485b).
**Branch:** `feature/nt-contact-explorer` (not merged anywhere; no protected branch touched).

| commit | content |
|---|---|
| `eb4bf5c` | implementation: `src/rnplens/contact_explorer.py`, `src/rnplens/viewer_assets/contact_explorer.js`, `src/rnplens/viewer.py`, `pyproject.toml` (package data), tests |
| `59cdf6c` | pre-registration `records/viewer/nt_contacts/PREREG_NT_CONTACTS.md` + scripts + `PREREG_SHA256.txt`, committed before any run on 2JEA/1VTM/6BJG |
| `82deb28` | focus camera keeps 12 Å of surroundings and the user's viewing direction (after run 1, see deviation D6) |
| `a19d409` | documentation: `docs/viewer.md` (viewer guide with screenshots), `docs/assist.md`, `README.md`, `docs/images/` |
| `1deade7` and the following commit | this report and the run records (`run1_59cdf6c/`, `run2_82deb28/`, `package_smoke/`); the second commit adds the 1VTM short-distance observation |

**Viewer status (unchanged): automatically tested, awaiting manual visual confirmation; not fully visually qualified.**
Everything below is software evidence from headless Chrome with software WebGL; it is not the owner's on-screen check.

## 1. What was implemented (owner spec sections 2-5)

| spec item | implementation |
|---|---|
| 2A click RNA nucleotide | Mol* click → chain / author number / insertion code from Mol*'s own loci → construct position via the page's correspondence table; molecule from the project manifest's chain types, never from the label |
| 2A highlight | selected residue ball-and-stick magenta `#CC00CC`, chain-prefixed label (`B:A33`); partners ball-and-stick orange `#E69F00`, labelled (`A:E104`); everything else faded (protein cartoon opacity 0.3, RNA 0.6); dashed magenta tube between the closest heavy atoms of every pair; only the selection and its partners labelled |
| 2A update / toggle / clear | every change rebuilds the MolViewSpec state of the structure on screen (one `loadMvsData`, `replaceExisting`); second click on the same residue clears; **Clear selection** button; empty-space clicks change nothing |
| 2B panel | chain, nucleotide (construct letter + file residue name), construct position, structure residue (author number + insertion code, flagged when different), prediction; table protein chain / protein residue / RNA chain / RNA nucleotide / contact distance; count; "No qualifying contact" |
| 2B distances | minimum heavy-atom distance recomputed with Report's parser; displayed (0.01 Å, closest atom pair) only if the recomputed set equals Report's record for that structure; otherwise "Not available" with the reason |
| 2C reverse | click a protein residue → its RNA partners in blue, same panel |
| 3 single structure vs ensemble | table and highlights = the structure on screen only; separate block "Across structures (ensemble support; separate from the structure shown)": k of n structures **of the same engine** with a Report record, ids listed, engines never pooled, limits text |
| 4 numbering | construct position = i-th residue of the chain in the file (Report's own correspondence); author numbers / insertion codes / modified residue names shown; chains whose length differs from the construct get no correspondence ("not available"); multiple chain copies carried in the data model (project route still refuses >1 chain per type, as before) |
| 5 visualisation | **Focus on selected nucleotide** / **Show all contacts** toggle; overview unchanged when nothing is selected; Mol*'s own click behaviours (selection, focus with Mol*-computed surroundings and interactions, camera centring) switched off on the page so no Mol*-computed contact is ever shown |
| structure switching | page-level Previous / Next / selector, one structure loaded at a time; selection kept on the same chain + construct position and re-resolved against the new structure's own record, or cleared with a note |
| offline | vendored Mol* 5.13.1 unchanged; new script `assets/contact_explorer.js` copied from the package; CSP unchanged |

## 2. Distance and correspondence parity (pre-registered part P; `parity_check.py`, gemmi 0.6.5)

Same result in run 1 (59cdf6c) and run 2 (82deb28):

| page | structures pass P1-P7 | contact rows |
|---|---|---|
| 2JEA RNA 26-35 (`viewer_26-35`) | 10 / 10 | 346 |
| 1VTM RNA 1-3 (`viewer_1-3`) | 10 / 10 | 205 |
| 6BJG all structures (`viewer`) | 50 / 50 | 1023 |
| 6BJG representatives t=0.5 | 6 / 6 | 148 |

Largest |displayed distance − gemmi minimum| 0.004987 Å (display rounds to 0.01 Å); named closest atoms at gemmi's minimum with
identical coordinates (deviation 0.0); smallest distance of any residue pair to the 5.0 Å cutoff 0.0011 Å (classified
the same way by Report, the viewer and gemmi). **Distances are therefore displayed**, as pre-registered.

## 3. Real-browser verification (pre-registered part B)

Chrome for Testing headless shell 155.0.8059.84, ANGLE/SwiftShader WebGL, node v22.22.1, puppeteer-core 24.43.1,
bubblewrap 0.11.1 network-less namespace, CDP request log; 2JEA repeated under strace 6.19. Clicks are real mouse
events at the screen position of an atom of the target residue (after Mol*'s hover reported that residue).

### Run 1 (59cdf6c; `run1_59cdf6c/`), reported as found

| plan | steps pass | failures |
|---|---|---|
| 2JEA | 137 / 139 | `03_B30`, `16_B26`: criterion B9 only (no real-click position: B30 hidden behind opaque partner residues, B26 outside the zoomed view; the page hook was used and every content check passed) |
| 2JEA (strace) | 137 / 139 | same two steps, B9 |
| 1VTM | 59 / 59 | – |
| 6BJG t=0.5 | 150 / 150 | – |

### Run 2 (82deb28; `run2_82deb28/`), after the focus-framing change

| plan | steps pass | real mouse clicks | run level |
|---|---|---|---|
| 2JEA | 139 / 139 | 10 / 10 | LOADED; 20 requests, 0 non-local; 0 websockets; 0 failed loads; 0 page errors |
| 2JEA (strace) | 139 / 139 | 10 / 10 | same; strace: 2 connect() calls, both AF_UNIX, **0 AF_INET/AF_INET6** |
| 1VTM | 59 / 59 | 4 / 4 | LOADED; 0 non-local requests |
| 6BJG t=0.5 | 150 / 150 | 2 / 2 | LOADED; 0 non-local requests |

### Run 2, 2JEA RNA 26-35: per-step expected (Report's record) vs observed (panel; Mol* checked in B4)

| step | structure | mode | action | selected | click | expected partners (Report) | observed panel partners | count | lines | max dist. err (Å) | result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 00_overall | s001 | focus | load | - | - | - | - | - | 0 | - | PASS |
| 01_B33 | s001 | focus | click | RNA B:33 | mouse (C2') | A:104 | A:104 | 1 | 1 | 0.0011 | PASS |
| 02_B35 | s001 | focus | click | RNA B:35 | mouse (O3') | A:85, A:90, A:94, A:99, A:101, A:136, A:137, A:138, A:141, A:181, A:184, A:190 | A:85, A:90, A:94, A:99, A:101, A:136, A:137, A:138, A:141, A:181, A:184, A:190 | 12 | 12 | 0.0048 | PASS |
| 03_B30 | s001 | focus | click | RNA B:30 | mouse (OP1) | none | none | 0 | 0 | - | PASS |
| 04_clear | s001 | focus | clear | - | - | - | - | - | 0 | - | PASS |
| 05_show_s006 | s006 | focus | show | - | - | - | - | - | 0 | - | PASS |
| 06_s006_B33 | s006 | focus | click | RNA B:33 | mouse (OP2) | A:104 | A:104 | 1 | 1 | 0.0048 | PASS |
| 07_s006_B35 | s006 | focus | click | RNA B:35 | mouse (O3') | A:85, A:90, A:94, A:99, A:101, A:136, A:137, A:138, A:139, A:141, A:181, A:184, A:190 | A:85, A:90, A:94, A:99, A:101, A:136, A:137, A:138, A:139, A:141, A:181, A:184, A:190 | 13 | 13 | 0.0049 | PASS |
| 08_s006_B30 | s006 | focus | click | RNA B:30 | mouse (C5') | none | none | 0 | 0 | - | PASS |
| 09_s006_clear | s006 | focus | clear | - | - | - | - | - | 0 | - | PASS |
| 10_s006_B33_again | s006 | focus | click | RNA B:33 | mouse (OP2) | A:104 | A:104 | 1 | 1 | 0.0048 | PASS |
| 11_prev_to_s005 | s005 | focus | prev | RNA B:33 | - | A:100, A:104 | A:100, A:104 | 2 | 2 | 0.0013 | PASS |
| 12_next_to_s006 | s006 | focus | next | RNA B:33 | - | A:104 | A:104 | 1 | 1 | 0.0048 | PASS |
| 13_mode_all | s006 | all | mode | RNA B:33 | - | A:104 | A:104 | 1 | 1 | 0.0048 | PASS |
| 14_reverse_A104 | s006 | all | click | protein A:104 | mouse (O) | B:33 | B:33 | 1 | 1 | 0.0048 | PASS |
| 15_mode_focus | s006 | focus | mode | protein A:104 | - | B:33 | B:33 | 1 | 1 | 0.0048 | PASS |
| 16_B26 | s006 | focus | click | RNA B:26 | mouse (C2) | none | none | 0 | 0 | - | PASS |
| 17_B26_toggle_off | s006 | focus | click | - | mouse (C2) | - | - | - | 0 | - | PASS |
| 138_final_clear | s010 | focus | clear | - | - | - | - | - | 0 | - | PASS |

Programmatic sweep: 120 steps, 120 pass; 100 selections (64 with at least one partner, 36 with none); 258 panel rows compared.

Residue notation `A:104` = chain A, construct position 104 (= author number in these copies). s001 = exec_A model 0
and s006 = exec_B model 0 (both engine-designated); s005 = exec_A model 4. In every row "observed" is both the panel
table and the Mol* ball-and-stick component set (criterion B4), with matching colours, opacity and contact lines.

### Run 2, 1VTM RNA 1-3

| step | structure | mode | action | selected | click | expected partners (Report) | observed panel partners | count | lines | max dist. err (Å) | result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 00_overall | s001 | focus | load | - | - | - | - | - | 0 | - | PASS |
| 01_R1 | s001 | focus | click | RNA B:1 | mouse (N3) | A:36, A:37, A:38, A:39, A:40, A:41, A:91, A:92, A:93, A:94, A:99 | A:36, A:37, A:38, A:39, A:40, A:41, A:91, A:92, A:93, A:94, A:99 | 11 | 11 | 0.0043 | PASS |
| 02_R2 | s001 | focus | click | RNA B:2 | mouse (C1') | A:36, A:37, A:92, A:93, A:94, A:99, A:110 | A:36, A:37, A:92, A:93, A:94, A:99, A:110 | 7 | 7 | 0.0044 | PASS |
| 03_R3 | s001 | focus | click | RNA B:3 | mouse (C5') | A:36, A:93, A:94, A:107, A:110, A:111, A:114 | A:36, A:93, A:94, A:107, A:110, A:111, A:114 | 7 | 7 | 0.0037 | PASS |
| 04_clear | s001 | focus | clear | - | - | - | - | - | 0 | - | PASS |
| 05_next | s002 | focus | next | - | - | - | - | - | 0 | - | PASS |
| 06_next_R2 | s002 | focus | click | RNA B:2 | mouse (O4') | A:37, A:92, A:93, A:94, A:99 | A:37, A:92, A:93, A:94, A:99 | 5 | 5 | 0.0034 | PASS |
| 07_clear2 | s002 | focus | clear | - | - | - | - | - | 0 | - | PASS |
| 58_final_clear | s010 | focus | clear | - | - | - | - | - | 0 | - | PASS |

Programmatic sweep: 50 steps, 50 pass; 30 selections (29 with at least one partner, 1 with none); 205 panel rows compared.

### Run 2, 6BJG group representatives (t=0.5)

| step | structure | mode | action | selected | click | expected partners (Report) | observed panel partners | count | lines | max dist. err (Å) | result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 00_overall | s013 | focus | load | - | - | - | - | - | 0 | - | PASS |
| 01_R19 | s013 | focus | click | RNA B:19 | mouse (P) | A:39, A:40 | A:39, A:40 | 2 | 2 | 0.0026 | PASS |
| 02_next_s033 | s033 | focus | next | RNA B:19 | - | A:39 | A:39 | 1 | 1 | 0.0015 | PASS |
| 03_next_s016 | s016 | focus | next | RNA B:19 | - | A:39 | A:39 | 1 | 1 | 0.0019 | PASS |
| 04_next_s039 | s039 | focus | next | RNA B:19 | - | A:39 | A:39 | 1 | 1 | 0.0024 | PASS |
| 05_next_s020 | s020 | focus | next | RNA B:19 | - | A:39 | A:39 | 1 | 1 | 0.0041 | PASS |
| 06_next_s001 | s001 | focus | next | RNA B:19 | - | A:39 | A:39 | 1 | 1 | 0.0006 | PASS |
| 07_last_R20 | s001 | focus | click | RNA B:20 | mouse (O3') | A:19, A:37, A:38, A:39 | A:19, A:37, A:38, A:39 | 4 | 4 | 0.0041 | PASS |
| 08_mode_all | s001 | all | mode | RNA B:20 | - | A:19, A:37, A:38, A:39 | A:19, A:37, A:38, A:39 | 4 | 4 | 0.0041 | PASS |
| 09_clear | s001 | all | clear | - | - | - | - | - | 0 | - | PASS |
| 10_mode_focus | s001 | focus | mode | - | - | - | - | - | 0 | - | PASS |
| 149_final_clear | s001 | focus | clear | - | - | - | - | - | 0 | - | PASS |

Programmatic sweep: 138 steps, 138 pass; 126 selections (46 with at least one partner, 80 with none); 148 panel rows compared.

### Run 1, 2JEA (as found)

| step | structure | mode | action | selected | click | expected partners (Report) | observed panel partners | count | lines | max dist. err (Å) | result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 00_overall | s001 | focus | load | - | - | - | - | - | 0 | - | PASS |
| 01_B33 | s001 | focus | click | RNA B:33 | mouse (C2') | A:104 | A:104 | 1 | 1 | 0.0011 | PASS |
| 02_B35 | s001 | focus | click | RNA B:35 | mouse (O3') | A:85, A:90, A:94, A:99, A:101, A:136, A:137, A:138, A:141, A:181, A:184, A:190 | A:85, A:90, A:94, A:99, A:101, A:136, A:137, A:138, A:141, A:181, A:184, A:190 | 12 | 12 | 0.0048 | PASS |
| 03_B30 | s001 | focus | click | RNA B:30 | api_fallback | none | none | 0 | 0 | - | FAIL (B9) |
| 04_clear | s001 | focus | clear | - | - | - | - | - | 0 | - | PASS |
| 05_show_s006 | s006 | focus | show | - | - | - | - | - | 0 | - | PASS |
| 06_s006_B33 | s006 | focus | click | RNA B:33 | mouse (OP2) | A:104 | A:104 | 1 | 1 | 0.0048 | PASS |
| 07_s006_B35 | s006 | focus | click | RNA B:35 | mouse (O3') | A:85, A:90, A:94, A:99, A:101, A:136, A:137, A:138, A:139, A:141, A:181, A:184, A:190 | A:85, A:90, A:94, A:99, A:101, A:136, A:137, A:138, A:139, A:141, A:181, A:184, A:190 | 13 | 13 | 0.0049 | PASS |
| 08_s006_B30 | s006 | focus | click | RNA B:30 | mouse (C5') | none | none | 0 | 0 | - | PASS |
| 09_s006_clear | s006 | focus | clear | - | - | - | - | - | 0 | - | PASS |
| 10_s006_B33_again | s006 | focus | click | RNA B:33 | mouse (OP2) | A:104 | A:104 | 1 | 1 | 0.0048 | PASS |
| 11_prev_to_s005 | s005 | focus | prev | RNA B:33 | - | A:100, A:104 | A:100, A:104 | 2 | 2 | 0.0013 | PASS |
| 12_next_to_s006 | s006 | focus | next | RNA B:33 | - | A:104 | A:104 | 1 | 1 | 0.0048 | PASS |
| 13_mode_all | s006 | all | mode | RNA B:33 | - | A:104 | A:104 | 1 | 1 | 0.0048 | PASS |
| 14_reverse_A104 | s006 | all | click | protein A:104 | mouse (O) | B:33 | B:33 | 1 | 1 | 0.0048 | PASS |
| 15_mode_focus | s006 | focus | mode | protein A:104 | - | B:33 | B:33 | 1 | 1 | 0.0048 | PASS |
| 16_B26 | s006 | focus | click | RNA B:26 | api_fallback | none | none | 0 | 0 | - | FAIL (B9) |
| 17_B26_toggle_off | s006 | focus | click | - | mouse (C2) | - | - | - | 0 | - | PASS |
| 138_final_clear | s010 | focus | clear | - | - | - | - | - | 0 | - | PASS |

### Candidate dependence (2JEA, Report's records, as shown by the explorer)

B33's partners differ between candidates: s001, s006, s007, s009, s010 → E104; s002 → R100; s003, s005 → R100, E104;
s004 → E5, E104; s008 → G1, H2. B35 has 12-14 partners per structure; B26 and B30 have no qualifying contact in any
of the 10 structures. Full table: `2JEA_expected_contacts_by_structure_RNA26-35.tsv` (Mac package).

### Screenshots (run 2, inspected)

`2JEA_00_overall` (overall interface), `2JEA_01_B33`, `2JEA_02_B35`, `2JEA_03_B30` (no qualifying contact),
`2JEA_05_show_s006`, `2JEA_06_s006_B33`, `2JEA_11_prev_to_s005` (other candidate, selection kept: R100 + E104),
`2JEA_13_mode_all`, `2JEA_14_reverse_A104`, `2JEA_16_B26`, 1VTM `00/01/03/04/05/06`, 6BJG `00`-`09`. Inspection:
the magenta residue, orange partners, dashed lines and chain-prefixed labels agree with the panel in every image;
B30 / B26 show only the magenta nucleotide and the "No qualifying contact" text; after switching, the panel names the
new structure and its own partners. Observations: with many partners (B35, 12 residues) labels overlap; in show-all
mode opaque ribbons can hide the selected residue (documented); in some close-up development views atoms cut by the
camera's near plane render as dark-grey discs (Mol* interior colour; they disappear on camera reset). Screenshots
are illustrations; the evidence is the per-step checks.

Observation about the data shown (not a viewer defect): in 1VTM s001 the explorer lists heavy-atom distances of
0.32 Å (Q38 N – G1 OP1) and 1.52 Å (T37 C – G1 OP1). Such overlaps are physically implausible; they are features of that
predicted structure, recomputed and reported as they are (gemmi gives the same values). The viewer makes no
judgement about them; users should read very short distances as a sign of a clash in the prediction.

## 4. Report and Evaluate outputs unchanged (pre-registered part R)

| comparison (base out/base_de66a96 vs feature) | run 1 | run 2 |
|---|---|---|
| `report/contacts_by_output.json` 1VTM, 2JEA, 6BJG | byte-identical | byte-identical |
| `report/result.json` 1VTM, 2JEA, 6BJG | identical except `/wall_s` (2JEA, 6BJG) | identical except `/wall_s` (6BJG) |
| existing page highlight lists (`viewer_manifest.json` "highlighted") 1VTM, 2JEA, 6BJG | equal | equal |
| Evaluate 7K9D example with reference: `result.csv`, `summary.txt` (s001, s002), `report/*.json` | byte-identical | byte-identical |
| Evaluate `evaluate/s00N/result.json` | **FAIL under the pre-registered rule**: differs in `/created_utc` and `/rnplens_public_output/frozen_component_output_sha256_before_filtering/result.json/raw_file_sha256` | same |

Post-hoc control (not pre-registered, reported separately): the base checkout was run a second time on the same
input; base vs base-repeat differs in exactly the same two leaves (`posthoc_eval_control/`). The difference is a
run timestamp and the hash of a raw file written in that run, not a numerical Evaluate output; the pre-registered
word list (wall, time, environment, ...) did not include `created_utc`. The FAIL is kept as recorded (deviation D7).
No file under `src/rnpbench_*` or the frozen assistant changed (`git diff --stat de66a96..a19d409`: 24 files, all in
`src/rnplens/` viewer files, `tests/test_viewer*.py`, `records/viewer/nt_contacts/`, `docs/`, `README.md` and the
package-data line of `pyproject.toml`); `rnplens doctor`: READY, "all 8 frozen sources match their pinned SHA-256" (both runs).

## 5. Test suites (part S)

| host | de66a96 (base) | a19d409 (feature head) |
|---|---|---|
| karyon (Linux x86_64, Python 3.11) | 759 passed, 0 failed, 12 skipped | 768 passed, 0 failed, 12 skipped |
| local macOS (arm64, conda env rnplens, Python 3.11) | 744 passed, 0 failed, 27 skipped | 753 passed, 0 failed, 27 skipped |

The +9 are `tests/test_viewer_nt_contacts.py`: Report parity + independent brute-force distances (7K9D), per-nucleotide
counts and an empty nucleotide, modified nucleotide (PSU, HETATM) with author numbering and an insertion code, missing
residue (no correspondence), second RNA chain (rows carry their chain; project route still refuses), altered record
(distance check FAIL hides every distance, Report's pairs still shown), per-engine ensemble separation, `rnplens view`
page data + wording audit + no network address in page or script, record validation. Browser-side behaviour
(selection, panel, Mol* components, switching, clear, toggle, offline) is covered by the pre-registered runs above;
the harness was checked with a negative control (10 tampered results, all rejected).

## 6. Mac package

Prebuilt 2JEA RNA 26-35 page (run 2, commit 82deb28; code identical to the head) zipped:
`RNPLens_2JEA_RNA26-35_nt_contacts_viewer_82deb28.zip` (29 files, 2,547,741 bytes, SHA-256
`1abfcae4b9446eb4c0c867a65c0416f6cc8c06e4d0e65559d5008e9c643f3d16`); a fresh unzip passed a 5-step browser smoke test
(overall, B33, B35, B30, clear; `package_smoke/`). Source: full and incremental git bundles and a patch; instructions in
`MAC_TEST_INSTRUCTIONS_nt_contacts.md`. The owner's Mac folder was not accessed.

## 7. Deviations and notes (complete list)

- D1. Base is de66a96 (integrator's designation), not the `dev/0.4-interactive` checkout named in spec section 1;
  that checkout was neither inspected nor modified.
- D2. Structure navigation moved from Mol*'s snapshot controls to a page-level selector (one structure loaded at a
  time; Mol*'s snapshot box shows [1/1]); `view.mvsj` is still the multi-snapshot document. The status line now reads
  "LOADED: n structure(s) loaded from this folder; one is shown at a time".
- D3. Mol*'s click behaviours (selection, focus with surroundings and computed interactions, camera centring) are
  switched off on the page; hover highlighting and the rest of the Mol* interface are unchanged.
- D4. Existing tests edited: `test_viewer.py` data-access allowance extended to the bundled `contact_explorer.js`; the
  optional Firefox browser test's assertion changed from 2 Mol* snapshots to 2 page structures. That optional test
  stays skipped on both hosts (no Firefox configured) and was not executed.
- D5. The page's limits text changed from "It computes nothing" to "It computes no contacts ... distances recomputed
  ... shown only where the recomputed contacts equal Report's record"; a second limits block covers ensemble support.
- D6. Code changed after pre-registration (82deb28, focus framing and orientation) because run 1 failed criterion B9
  twice; run 2 is a complete, separate repetition with the unchanged pre-registered scripts (verified against
  `PREREG_SHA256.txt`: all scripts OK, only `viewer.py` and `contact_explorer.js` differ). Run 1 is kept as found.
- D7. Evaluate comparison criterion failed as pre-registered (two run-environment leaves not covered by the word list);
  explained by a post-hoc control; not relabelled.
- D8. Before pre-registration the base 2JEA page was opened once to probe Mol* API behaviour, and `make_plans.py` was
  executed on base pages (step counts only; a temporary 6BJG t=0.5 page was written to `tmp/`).
- D9. The 6BJG t=0.5 representatives page holds 6 structures (5 representatives + engine-designated s001), all tested.
- D10. In focus mode the faded protein (opacity 0.3, below Mol*'s picking threshold 0.5) cannot be clicked; reverse
  selection works on highlighted residues, in show-all mode, or without a selection (documented).
- D11. Ensemble counts use every structure of the engine with a Report record in the analysis, not only the page's
  structures (e.g. "of 50" on the 6BJG representatives page); the denominator is always printed.
- D12. Modified nucleotides, insertion codes, missing residues and second chains were tested with fixtures derived
  from the bundled 7K9D example; no demonstration target contains them.
- D13. The Evaluate comparison used the bundled 7K9D example (no demonstration has a reference).
- D14. Mac page built on karyon at 82deb28 (docs-only commits follow); Mac instructions clone from a full bundle because
  the incremental bundle requires de66a96, which the Mac's earlier checkout may not contain.
- D15. Known display limits: overlapping labels with many partners; occlusion in show-all mode; Mol* panels still name
  structures by an in-memory arcp:// URI; near-plane dark discs at close zoom.
- D16. Two open Reviewer findings from the earlier interface track (4a76d2e4, b8f4e972) are not addressed here.
- D17. No owner visual approval: headless rendering only; the viewer label is unchanged.
