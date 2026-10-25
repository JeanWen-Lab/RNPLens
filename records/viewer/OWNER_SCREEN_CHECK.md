# Owner real-screen check of the RNPLens offline viewer (short test)

Viewer status: **automatically tested, awaiting manual visual confirmation; not fully visually qualified.** This test
is the manual visual confirmation. Please record what you actually see, including any discrepancy. An unhighlighted
nucleotide is not by itself a defect: the expected highlights are listed below for every structure.

**Package.** `RNPLens_owner_screen_check.zip`. It holds six offline pages written by `rnplens view` (RNPLens 0.4
development candidate, branch `track/viewer-r2`) together with their vendored Mol* 5.13.1 files. Unzip it anywhere,
then **turn networking off**: Wi-Fi off and cable unplugged. Use a desktop browser on a machine with a GPU.
- The pages were tested only in headless Chrome for Testing 155 on Linux, with software WebGL. Chrome or Firefox is
  the closest match.
- On macOS Safari, if a page stays at `PENDING` or shows `ERROR`, note it, then repeat in Chrome or Firefox.
- What is in the zip:
  - `index.html`;
  - `pages/<page>/viewer.html` (six pages), each with its own `assets/` (Mol*), `structures/` (copies of the
    predicted structures), `view.mvsj`, `view_data.js` and `viewer_manifest.json`;
  - `expected_highlights.json`, with the lists in this document in machine-readable form;
  - `PACKAGE_MANIFEST.json`, with the SHA-256 of every file;
  - this file.
- Targets: 1VTM (development task d2), 2JEA (stress-cohort pilot), 6BJG (pool A). None is an excluded target.
- Each page's `viewer_manifest.json` keeps its provenance, including absolute paths of the machine that built the
  pages (karyon home-folder paths). The pages themselves show no absolute path.

Colour key on every page:
- grey cartoon: protein, chain A;
- tan cartoon: RNA, chain B;
- **orange**: highlighted protein residue (ball-and-stick, and the ribbon segment);
- **blue**: highlighted RNA nucleotide (ball-and-stick, and the ribbon segment).

A highlighted residue is one of Report's contacts for that structure: a protein residue and an RNA nucleotide with
any heavy-atom pair within 5.0 Å. It is a feature of the prediction, not an observation of the real complex, and
nothing on the page measures correctness.

## The five steps
### 1. Open the offline report
Open `index.html` from the unzipped folder by double-click, as a `file://` URL. Then open
`1b_2JEA_RNA_26-35`.

Expected:
- Under the 3D view, the status line reads `LOADED: 10 structure(s) loaded from this folder`. It must not read
  `ERROR` or stay at `PENDING`.
- The page shows the line "Viewer status: automatically tested, awaiting manual visual confirmation; not fully
  visually qualified".
- Optional: in the browser's developer tools (Network tab), after a reload, only `file://` and `data:` entries
  appear.

### 2. Check protein/RNA chain identity and orientation
On the 2JEA page, use the sequence panel at the top. Its chain selector offers "1: Polymer 1" and "2: Polymer 2".

Expected:
- **Polymer 1 is the protein, chain A:** 250 residues, starting `GHMREMLQVERP...` at position 1 and ending
  `...VEFKEEGV` at 250.
- **Polymer 2 is the RNA, chain B:** 35 nucleotides, `CCCCCCCCGAAAGGGGGGGGAAAAAAAAAAAAAAA`, 5' to 3', positions
  1-35.
- **Orientation.** In the 3D view, hover the two ends of the tan RNA ribbon. One end reads C 1 (the 5' end); the
  other reads A 35 (the 3' end). The highlighted blue nucleotides lie toward the 3' end. Hover the protein ends: G 1
  is the N-terminus, V 250 the C-terminus.
- The same holds on the other pages:
  - 1VTM: protein chain A, 158 residues `PYTINSPSQFVY...VWTTTPAT`; RNA chain B, 3 nucleotides `GAA`.
  - 6BJG: protein chain A, 143 residues `MERAIQGNDTRE...SKQELLQL`; RNA chain B, 21 nucleotides
    `UCGAAGUAUUCCGCGUACGUU`.

### 3. Select the 2JEA RNA region 26-35
The 2JEA page is built for RNA 26-35: its title is "RNPLens structure view (RNA 26-35)". To see the whole region,
choose "2: Polymer 2" in the sequence panel and drag across positions 26-35 (all `A`). Mol* outlines those ten
nucleotides in the 3D view.

Expected:
- All ten nucleotides 26-35 exist in every structure.
- **Not all of them are highlighted. Positions 26 and 30 are not highlighted in any of the ten structures.** In
  each structure they are present in the structure and in the construct mapping, but Report's record has no
  contact for them: no protein heavy atom is within 5.0 Å. The closest protein heavy atom is 6.1-12.0 Å from 26 and
  5.4-7.5 Å from 30.
- The highlighted set differs between structures (step 4).

### 4. Confirm the displayed highlighted contacts correspond to the per-structure contact records
Step through the ten structures with the arrows next to the snapshot title, top left. For each one, check that:
- the blue nucleotides are exactly the RNA positions listed below;
- the orange residues are the protein positions listed below, at least by spot-checking about five labels per
  structure;
- the page's own "Highlighted residues" table lists the same residues.

Labels are drawn for up to 40 residues per molecule.

2JEA, RNA 26-35. Positions are construct numbers (= the residue numbers in the structure); the count is in brackets.

| snapshot | structure | highlighted RNA nucleotides (chain B) | highlighted protein residues (chain A) |
|---|---|---|---|
| 1 | s001 exec_A#2JEA_model_0 | 29, 31-35 (6) | 85, 90, 94-95, 97, 99-101, 104, 136-138, 141, 181, 184-185, 190, 208 (18) |
| 2 | s002 exec_A#2JEA_model_1 | 31-35 (5) | 85, 90, 94, 99-101, 136-139, 141, 181, 184-185, 190, 208 (16) |
| 3 | s003 exec_A#2JEA_model_2 | 28, 31-35 (6) | 85, 90, 94-101, 104, 136-139, 141, 181, 184-185, 190, 208 (21) |
| 4 | s004 exec_A#2JEA_model_3 | 29, 31-35 (6) | 5, 85, 90-91, 94-95, 97, 99-101, 104, 136-139, 141, 181, 184-185, 190, 208 (21) |
| 5 | s005 exec_A#2JEA_model_4 | 27-29, 31-35 (8) | 4, 85, 90, 94-101, 104, 136-139, 141, 181, 184-185, 190, 208 (22) |
| 6 | s006 exec_B#2JEA_model_0 | 27-29, 31-35 (8) | 82, 85, 90, 94-101, 104, 136-139, 141, 181, 184-185, 190, 208 (22) |
| 7 | s007 exec_B#2JEA_model_1 | 28-29, 31-35 (7) | 85, 90, 94-101, 104, 136-138, 141, 181, 184-185, 190, 208 (20) |
| 8 | s008 exec_B#2JEA_model_2 | 29, 31-35 (6) | 1-2, 85, 90, 94-97, 99-101, 136-139, 141, 181, 184-185, 190, 208 (21) |
| 9 | s009 exec_B#2JEA_model_3 | 29, 31-35 (6) | 85, 90, 94, 97-101, 104, 136-141, 181, 184-185, 190, 208 (20) |
| 10 | s010 exec_B#2JEA_model_4 | 29, 31-35 (6) | 85, 90, 94, 97-101, 104, 136-139, 141, 181, 184-185, 190, 208 (19) |

The same, position by position, for RNA 26-35. **H** = highlighted (in Report's record for that structure);
– = not highlighted (no qualifying contact in Report's record; the nucleotide is present in the structure).

| structure | 26 | 27 | 28 | 29 | 30 | 31 | 32 | 33 | 34 | 35 |
|---|---|---|---|---|---|---|---|---|---|---|
| s001 exec_A#2JEA_model_0 | – | – | – | **H** | – | **H** | **H** | **H** | **H** | **H** |
| s002 exec_A#2JEA_model_1 | – | – | – | – | – | **H** | **H** | **H** | **H** | **H** |
| s003 exec_A#2JEA_model_2 | – | – | **H** | – | – | **H** | **H** | **H** | **H** | **H** |
| s004 exec_A#2JEA_model_3 | – | – | – | **H** | – | **H** | **H** | **H** | **H** | **H** |
| s005 exec_A#2JEA_model_4 | – | **H** | **H** | **H** | – | **H** | **H** | **H** | **H** | **H** |
| s006 exec_B#2JEA_model_0 | – | **H** | **H** | **H** | – | **H** | **H** | **H** | **H** | **H** |
| s007 exec_B#2JEA_model_1 | – | – | **H** | **H** | – | **H** | **H** | **H** | **H** | **H** |
| s008 exec_B#2JEA_model_2 | – | – | – | **H** | – | **H** | **H** | **H** | **H** | **H** |
| s009 exec_B#2JEA_model_3 | – | – | – | **H** | – | **H** | **H** | **H** | **H** | **H** |
| s010 exec_B#2JEA_model_4 | – | – | – | **H** | – | **H** | **H** | **H** | **H** | **H** |

### 5. Switch binding-hypothesis representatives and confirm the displayed structures actually change
Open `3_6BJG_representatives_t0.5`. It shows the five group representatives at the shipped threshold 0.5,
in structure-id order. Step through the five snapshots.

Expected, at each step:
- the snapshot title changes to the next structure;
- the caption count changes;
- **the structure itself changes**: the RNA (tan) sits differently against the protein (grey), with a different
  part of the RNA blue;
- the blue and orange sets change as listed.

Groups are listed by group number, not by size. Recurrence among predictions is not evidence of correctness, and no
representative is recommended.

| snapshot | structure | group (t) | highlighted RNA nucleotides (chain B) | highlighted protein residues (chain A) |
|---|---|---|---|---|
| 1 | s013 boltz_out#6BJG_model_2 | 1 | 18-21 (4) | 18-19, 36-42, 46, 53, 56, 69 (13) |
| 2 | s016 boltz_out#6BJG_model_22 | 3 | 5-7, 18-21 (7) | 15, 19, 36-39, 42, 56, 69 (9) |
| 3 | s020 boltz_out#6BJG_model_26 | 5 | 4-13, 19-21 (13) | 11, 15, 18-19, 36-40, 42-43, 56, 67, 69, 107, 109, 111, 116, 118 (19) |
| 4 | s033 boltz_out#6BJG_model_38 | 2 | 3-5, 19-21 (6) | 18-19, 36-40, 42-43, 56, 69 (11) |
| 5 | s039 boltz_out#6BJG_model_43 | 4 | 3-8, 12-14, 19-21 (12) | 11, 15, 18-19, 36-40, 42-43, 46, 56, 69, 109, 111, 116, 118 (18) |

What should visibly differ between representatives:
- s013 and s016 contact mainly the RNA 3' end (18-21, and 5-7 for s016).
- s020 and s039 also contact the 5' half of the RNA (s020: 4-13; s039: 3-8 and 12-14).
- s033 contacts 3-5 and 19-21.

The five files are distinct structures: five different SHA-256 values in `viewer_manifest.json`. The pages
`3_6BJG_representatives_t0.3` (2 representatives) and `3_6BJG_representatives_t0.7` (18) behave the same way.
Their lists are in the appendix.

## Result form (one per browser)
| field | entry |
|---|---|
| Step 1: page loaded (LOADED / ERROR / PENDING); status line visible | |
| Step 2: chain A protein and chain B RNA as listed; 5' end C 1, 3' end A 35; N-terminus G 1 | |
| Step 3: 26-35 all present; 26 and 30 not highlighted in any structure | |
| Step 4: highlighted residues match the table for structures 1-10 (list any that do not) | |
| Step 5: the five t = 0.5 representatives change structure, title and highlights as listed | |
| Observed result (free text) | |
| Discrepancy (what, where: page, snapshot, residue) | |
| Browser and version | |
| Operating system and version | |
| GPU | |
| Network off during the test (yes / no) | |
| Date | |
| Name | |

## Appendix: expected highlights on the other pages (also in `expected_highlights.json`)
### 1VTM, RNA 1-3 (`1_1VTM_RNA_1-3`)
| snapshot | structure | highlighted RNA nucleotides (chain B) | highlighted protein residues (chain A) |
|---|---|---|---|
| 1 | s001 run_A#1VTM_model_0 | 1-3 (3) | 36-41, 91-94, 99, 107, 110-111, 114 (15) |
| 2 | s002 run_A#1VTM_model_1 | 1-3 (3) | 36-40, 92-94, 99, 107, 110-111, 114 (13) |
| 3 | s003 run_A#1VTM_model_2 | 1-3 (3) | 36-39, 41-42, 92-94, 102, 106-107, 110-111, 114 (15) |
| 4 | s004 run_A#1VTM_model_3 | 1-3 (3) | 36-41, 91-94, 102, 106-107, 110-111, 114 (16) |
| 5 | s005 run_A#1VTM_model_4 | 1-2 (2) | 85-86, 88, 90 (4) |
| 6 | s006 run_B#1VTM_model_0 | 1-3 (3) | 36-39, 41-42, 91-94, 99, 107, 110-111, 114 (15) |
| 7 | s007 run_B#1VTM_model_1 | 1-3 (3) | 36, 38, 41, 89-96, 99, 102, 106-107, 110-111, 114 (18) |
| 8 | s008 run_B#1VTM_model_2 | 1-3 (3) | 37-39, 41, 91-95, 107, 110-111, 114 (13) |
| 9 | s009 run_B#1VTM_model_3 | 1-3 (3) | 36-42, 92-94, 99, 107, 110-111, 114 (15) |
| 10 | s010 run_B#1VTM_model_4 | 1-3 (3) | 38, 88-93, 95, 99 (9) |

### 6BJG representatives, t = 0.3 (`3_6BJG_representatives_t0.3`)
| snapshot | structure | group (t) | highlighted RNA nucleotides (chain B) | highlighted protein residues (chain A) |
|---|---|---|---|---|
| 1 | s019 boltz_out#6BJG_model_25 | 2 | 4-8, 10-14, 19-21 (13) | 11, 15, 18-19, 36-40, 42-43, 46, 56, 67, 69, 107, 109, 111, 116, 118 (20) |
| 2 | s021 boltz_out#6BJG_model_27 | 1 | 18-21 (4) | 18-19, 36-42, 46, 56, 69 (12) |

### 6BJG representatives, t = 0.7 (`3_6BJG_representatives_t0.7`)
| snapshot | structure | group (t) | highlighted RNA nucleotides (chain B) | highlighted protein residues (chain A) |
|---|---|---|---|---|
| 1 | s003 boltz_out#6BJG_model_10 | 16 | 18-21 (4) | 18-19, 36-37, 39, 41-42, 45, 52-53, 56, 69 (12) |
| 2 | s005 boltz_out#6BJG_model_12 | 3 | 18-21 (4) | 18-19, 36-40, 42-43, 46, 56, 69 (12) |
| 3 | s007 boltz_out#6BJG_model_14 | 2 | 4-6, 19-21 (6) | 18-19, 36-39, 42-43, 56, 69 (10) |
| 4 | s010 boltz_out#6BJG_model_17 | 5 | 19-21 (3) | 18-19, 34, 36-43, 46, 56, 69 (14) |
| 5 | s011 boltz_out#6BJG_model_18 | 9 | 18-21 (4) | 18-19, 37-43, 46, 53, 55-56, 69 (14) |
| 6 | s013 boltz_out#6BJG_model_2 | 1 | 18-21 (4) | 18-19, 36-42, 46, 53, 56, 69 (13) |
| 7 | s014 boltz_out#6BJG_model_20 | 7 | 18-21 (4) | 18-19, 36-39, 42, 56, 69, 111 (10) |
| 8 | s016 boltz_out#6BJG_model_22 | 15 | 5-7, 18-21 (7) | 15, 19, 36-39, 42, 56, 69 (9) |
| 9 | s020 boltz_out#6BJG_model_26 | 18 | 4-13, 19-21 (13) | 11, 15, 18-19, 36-40, 42-43, 56, 67, 69, 107, 109, 111, 116, 118 (19) |
| 10 | s023 boltz_out#6BJG_model_29 | 13 | 18-21 (4) | 18-19, 36-42, 46, 53, 56, 69 (13) |
| 11 | s025 boltz_out#6BJG_model_30 | 4 | 3-5, 19-21 (6) | 18-19, 36-40, 42-43, 56, 69 (11) |
| 12 | s034 boltz_out#6BJG_model_39 | 6 | 1-5, 19-21 (8) | 18-19, 36-39, 42-43, 56, 69 (10) |
| 13 | s039 boltz_out#6BJG_model_43 | 17 | 3-8, 12-14, 19-21 (12) | 11, 15, 18-19, 36-40, 42-43, 46, 56, 69, 109, 111, 116, 118 (18) |
| 14 | s041 boltz_out#6BJG_model_45 | 12 | 2-4, 20-21 (5) | 18-19, 36-39, 42, 46, 56, 69 (10) |
| 15 | s042 boltz_out#6BJG_model_46 | 14 | 2-4, 19-21 (6) | 18-19, 36-39, 42, 53, 56, 68-69 (11) |
| 16 | s043 boltz_out#6BJG_model_47 | 8 | 5-7, 18-21 (7) | 18-19, 36-43, 56, 69 (12) |
| 17 | s044 boltz_out#6BJG_model_48 | 11 | 1, 6-7, 18-21 (7) | 16, 18-19, 36-42, 46, 53, 56, 69 (14) |
| 18 | s045 boltz_out#6BJG_model_49 | 10 | 3-5, 19-21 (6) | 18-19, 37-39, 42-43, 56, 69 (9) |

### 6BJG, all 50 structures (`3_6BJG_all_50`)
The per-structure lists for all 50 structures are in `expected_highlights.json`, under `3_6BJG_all_50`.

Source of every list: `analysis/report/contacts_by_output.json` of the demonstration packages, restricted to the
page's RNA region, and checked against the page and Mol*'s state (`records/viewer/HIGHLIGHT_COVERAGE_2JEA_AND_ALL_PAGES.md`).
