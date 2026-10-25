# Highlight coverage: 2JEA positions 26 and 30, and a complete per-structure set comparison on every governed page

Track `viewer` round 2, branch `track/viewer-r2`. Plan frozen in `R2_PLAN.md` at commit `8ddc7b5`, before the runs it
governs. Stage 1 ran at `8ddc7b5`; stage 2 ran at `2677969`, which changes only OWNER_SCREEN_CHECK.md. Viewer status:
**automatically tested, awaiting manual visual confirmation; not fully visually qualified.**

## Answer for 2JEA, RNA 26-35 (owner item 6)
On the 2JEA page, positions **26 and 30 fall in case (a): no qualifying contact in that structure.** This holds in
**every one of the ten structures**, s006 exec_B#2JEA_model_0 included:
- Both nucleotides are present in each structure copy on the page, as adenosines at chain B residues 26 and 30.
- Both are inside the construct mapping: chain B is numbered 1-35, with no unresolved positions in the region record.
- Report's per-structure record lists no contact for either of them.
- The viewer omitted nothing.

Case (b), absent from the mapped structure or construct mapping, applies to no position on any page. Case (c),
contacts omitted by the viewer, also applies to no position on any page.

An independent geometric cross-check agrees. It is descriptive, not Report's qualified route. For 26 and 30, the
nearest protein heavy atom is always farther than Report's 5.0 Å cutoff:
- 6.10-12.04 Å for position 26;
- 5.40-7.49 Å for position 30.

Over all 100 (structure, position) pairs of the region, highlighted positions are at most 4.943 Å from the
protein, and unhighlighted ones at least 5.055 Å. Every position agrees with Report's record.

Which nucleotides of 26-35 are highlighted differs from structure to structure. Their union over the ten structures
is 27-29 and 31-35. **The interval 26-35 as a whole is not highlighted in any structure.** In s006 exec_B#2JEA_model_0
the highlighted chain-B nucleotides are 27-29 and 31-35.

| structure | highlighted RNA (chain B) in 26-35 | 26: class | 26: min distance (Å) | 30: class | 30: min distance (Å) |
|---|---|---|---|---|---|
| s001 exec_A#2JEA_model_0 | 29, 31-35 | NO_QUALIFYING_CONTACT | 11.30 | NO_QUALIFYING_CONTACT | 6.42 |
| s002 exec_A#2JEA_model_1 | 31-35 | NO_QUALIFYING_CONTACT | 10.82 | NO_QUALIFYING_CONTACT | 6.64 |
| s003 exec_A#2JEA_model_2 | 28, 31-35 | NO_QUALIFYING_CONTACT | 8.07 | NO_QUALIFYING_CONTACT | 7.41 |
| s004 exec_A#2JEA_model_3 | 29, 31-35 | NO_QUALIFYING_CONTACT | 10.92 | NO_QUALIFYING_CONTACT | 6.55 |
| s005 exec_A#2JEA_model_4 | 27-29, 31-35 | NO_QUALIFYING_CONTACT | 12.04 | NO_QUALIFYING_CONTACT | 7.49 |
| s006 exec_B#2JEA_model_0 | 27-29, 31-35 | NO_QUALIFYING_CONTACT | 6.10 | NO_QUALIFYING_CONTACT | 5.40 |
| s007 exec_B#2JEA_model_1 | 28-29, 31-35 | NO_QUALIFYING_CONTACT | 10.95 | NO_QUALIFYING_CONTACT | 6.01 |
| s008 exec_B#2JEA_model_2 | 29, 31-35 | NO_QUALIFYING_CONTACT | 10.62 | NO_QUALIFYING_CONTACT | 5.47 |
| s009 exec_B#2JEA_model_3 | 29, 31-35 | NO_QUALIFYING_CONTACT | 11.24 | NO_QUALIFYING_CONTACT | 6.00 |
| s010 exec_B#2JEA_model_4 | 29, 31-35 | NO_QUALIFYING_CONTACT | 11.52 | NO_QUALIFYING_CONTACT | 5.60 |

Class counts over the 2JEA region: HIGHLIGHTED 64, NO_QUALIFYING_CONTACT
36, ABSENT_FROM_STRUCTURE_OR_MAPPING 0, OMITTED_BY_VIEWER 0,
HIGHLIGHTED_WITHOUT_RECORD 0. The 1VTM region (RNA 1-3) has 29 HIGHLIGHTED and 1 NO_QUALIFYING_CONTACT: position 3
in s005 run_A#1VTM_model_4, with the nearest protein heavy atom at 6.44 Å.

## Complete per-structure set comparison on every governed page
For every structure shown, `harness/coverage.py` compares Report's record (R1) with the region record (R2, region
pages only) and with every viewer source:
- the page's MolViewSpec ball-and-stick and cartoon-highlight layer (V1);
- `viewer_manifest.json` (V2);
- the visible side table (V3);
- Mol*'s own loaded state, ball-and-stick and cartoon multilayer (V4).

Each comparison covers the protein and the RNA residue sets on the declared chains. Definitions are in `R2_PLAN.md`.

| pages | page | structures | highlighted residues expected | comparisons equal | discrepancies |
|---|---|---|---|---|---|
| A (run-2 pages, Mol* run 2) | 1VTM, RNA 1-3 | 10 | 162 | 70/70 | 0 |
| A (run-2 pages, Mol* run 2) | 2JEA, RNA 26-35 | 10 | 264 | 70/70 | 0 |
| A (run-2 pages, Mol* run 2) | 6BJG representatives t = 0.3 | 2 | 49 | 12/12 | 0 |
| A (run-2 pages, Mol* run 2) | 6BJG representatives t = 0.5 | 5 | 112 | 30/30 | 0 |
| A (run-2 pages, Mol* run 2) | 6BJG representatives t = 0.7 | 18 | 331 | 108/108 | 0 |
| A (run-2 pages, Mol* run 2) | 6BJG all 50 | 50 | 899 | 300/300 | 0 |
| B (package pages) | 1VTM, RNA 1-3 | 10 | 162 | 50/50 | 0 |
| B (package pages) | 2JEA, RNA 26-35 | 10 | 264 | 50/50 | 0 |
| B (package pages) | 6BJG representatives t = 0.3 | 2 | 49 | 8/8 | 0 |
| B (package pages) | 6BJG representatives t = 0.5 | 5 | 112 | 20/20 | 0 |
| B (package pages) | 6BJG representatives t = 0.7 | 18 | 331 | 72/72 | 0 |
| B (package pages) | 6BJG all 50 | 50 | 899 | 200/200 | 0 |
| C (package pages, Mol* from fresh unzip) | 1VTM, RNA 1-3 | 10 | 162 | 70/70 | 0 |
| C (package pages, Mol* from fresh unzip) | 2JEA, RNA 26-35 | 10 | 264 | 70/70 | 0 |
| C (package pages, Mol* from fresh unzip) | 6BJG representatives t = 0.3 | 2 | 49 | 12/12 | 0 |
| C (package pages, Mol* from fresh unzip) | 6BJG representatives t = 0.5 | 5 | 112 | 30/30 | 0 |
| C (package pages, Mol* from fresh unzip) | 6BJG representatives t = 0.7 | 18 | 331 | 108/108 | 0 |
| C (package pages, Mol* from fresh unzip) | 6BJG all 50 | 50 | 899 | 300/300 | 0 |

Result:
- **Every highlighted residue on every page corresponds to a contact record of that structure, and every in-range
  contact record is highlighted.** This was checked on 95 structures in each of three page sets (A, B, C).
- The number of comparisons per structure is 7 in A and C and 5 in B, because B has no Mol* state.
- No discrepancy was found, so no viewer defect was recorded and no fix was needed in this round.
- The expected sets are identical between A (pages built in round 1) and B (rebuilt at this branch).
- The 2JEA position classes are identical in A, B and C.

Records, all in `records/viewer/r2/`:
- `coverage_A_run2_pages.json`, sha256 `9d4b64e5be5f3b4453c5024ba9c0524342ffba092bf2fb4865da1da8f712e1fb`;
- `coverage_B_package_pages.json`, sha256 `def4dcf3eec5372c4870a29ad9b53b264d10abc8c29f9e3bc005cc00d84b5fc8`;
- `coverage_C_package_pages_molstar.json`, sha256 `2fc0dbb307f084ac53de185ad0afbca83c4707a1fdc74caecb9ceac437484106`.

Harness validation on development data (7K9D example, recorded in `R2_PLAN.md`) showed the check can detect
discrepancies:
- shifted highlights produce OMITTED_BY_VIEWER and HIGHLIGHTED_WITHOUT_RECORD;
- a residue deleted from the structure copy produces ABSENT_FROM_STRUCTURE_OR_MAPPING.

## Screenshots (fresh-unzip test, s006 exec_B#2JEA_model_0)
![2JEA s006 as loaded: blue nucleotides 27-29 and 31-35](../screenshots/r2zip_2JEA_s006_loaded.jpg)
![2JEA s006, ball-and-stick hidden: highlight colour on the ribbon](../screenshots/r2zip_2JEA_s006_ribbon.jpg)
![2JEA s006, RNA-focus view](../screenshots/r2zip_2JEA_s006_rnafocus.jpg)

## What this does not show
These are automatic checks of records against the page and Mol*'s state, plus software-rendered headless
screenshots. They do not replace the owner's on-screen check (`OWNER_SCREEN_CHECK.md`).
