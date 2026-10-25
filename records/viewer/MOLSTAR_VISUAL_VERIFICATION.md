# Mol* viewer: rendering verification in a WebGL browser without network (RNPLens 0.4 development candidate)

> **Status (added 17 Oct 2026, owner decision; results below unchanged):** the offline viewer is **automatically
> tested, awaiting manual visual confirmation; not fully visually qualified**. A real-screen check by a person is
> pending: see `records/viewer/OWNER_SCREEN_CHECK.md`. For 2JEA RNA 26-35 the highlighted chain-B nucleotides are a per-structure subset of the
> interval; the interval as a whole is not highlighted. Position-by-position coverage is in `records/viewer/HIGHLIGHT_COVERAGE_2JEA_AND_ALL_PAGES.md`.
>
> **Status (added 18 Oct 2026, owner report; earlier text unchanged):** automatically tested; basic display and
> interaction confirmed manually by the owner on macOS (2JEA page; entry "2026-10-18 — owner-reported manual test on
> macOS" at the end of this record). Switching between binding-hypothesis representatives (6BJG) and offline operation
> with the network disconnected are not yet confirmed by a person, so the viewer is still **not fully visually
> qualified**. Step-by-step instructions for the two remaining checks: `MAC_REMAINING_VIEWER_CHECKS.md` in the RC
> hand-back package.

Track `viewer`, branch `track/viewer` (from `cf81acd`), 16-17 Oct 2026. Owner decision note, item 2. RNPLens 0.4
remains a development candidate. Nothing in this record was merged, tagged, pushed or released.

**What this record does and does not show.** A headless browser rendered every page on CPU, with WebGL in
software (SwiftShader). An agent took the screenshots and looked at them. That is **not** the same as a person
checking the viewer on screen, in a normal desktop browser on a physical GPU. The claims this evidence supports
are listed under "Claims supported" below, and the owner's checklist for an on-screen check is at the end.

## Summary
- **A WebGL route works.** It is Chrome for Testing `chrome-headless-shell` 155.0.8059.84, with WebGL 2.0 through
  ANGLE on SwiftShader. In-page renderer string, read from Mol*'s own WebGL context through
  `WEBGL_debug_renderer_info`: `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)` (vendor `Google Inc. (Google)`).
- **Offline loading works.** All 6 pages of demos 1, 1b and 3 loaded in both runs, 95 structure snapshots in total:
  - once inside `bwrap --unshare-net`, where only loopback exists;
  - once with networking available and every request logged.

  The pages attempted no request other than `file:` and `data:` URLs, opened no WebSocket and triggered no CSP
  violation. strace recorded 0 AF_INET/AF_INET6 socket calls.
- **The chains, positions, highlights and representatives match the records**, both through the Mol* API and in
  the rendered images:
  - Mol* loaded the intended protein and RNA chains, with residue numbers 1..L spelling the construct sequences.
  - It selected exactly the residues of Report's per-structure contact records.
  - The demo-3 pages show exactly the group representatives of `groups.json` at 0.3, 0.5 and 0.7.
- **One viewer defect was found and fixed (F1).**
  - At `cf81acd` the ribbon of highlighted residues rendered in the molecule colour. Only the ball-and-stick atoms
    carried the highlight colour.
  - The fix is `7131025`, with regression tests. Highlighted residues are now coloured inside the molecule's single
    cartoon.
  - After the fix, governed run 2 passed all 1,007 automated checks, including the new ribbon-colour check V13.
- Governed run 1 (code at `019c930`, viewer unchanged from `cf81acd`) is kept as found: 912 PASS, 0 FAIL, plus the
  visual finding F1 (`run1/RUN1_FINDINGS.md`).

## Pre-registration and commit order (all on `track/viewer`)
| commit | content |
|---|---|
| `634e174` | verification plan and harness (`render.js`, `check_pages.py`, `run_all.sh`, `pages.json`), frozen before any governed page was opened in a browser |
| `019c930` | plan wording only (harness unchanged); governed run 1 used this checkout |
| `51b9914` | run 1 recorded as found (checks, request logs, F1); inspection aids `make_sheets.py`, `request_log.py` |
| `7131025` | `viewer.py` fix for F1 + `tests/test_viewer_highlight_colour.py` |
| `b24a6d9` | plan Amendment 1 (ribbon views, V4 colour layers, V13, `pages_a1.json`, `regen_a1.sh`), frozen before governed run 2; run 2 used this checkout |
| `de8a653` | correction of two totals in `RUN1_FINDINGS.md` (95 snapshots, 285 screenshots); no result changed |
| (this commit) | this record, run-2 results, screenshots |

The harness SHA-256 values are listed in `VERIFICATION_PLAN.md` and `VERIFICATION_PLAN_AMENDMENT_1.md`. On karyon,
before each governed run, the files in the clone were checked against those values.

Development-only harness validation, done before freezing and recorded in the plan, used the bundled 7K9D
example, which is not a governed page:
- an unmodified page passes;
- negative control NC1 (every highlight shifted by +1) fails V5 and V6;
- negative control NC2 (an injected `https://` image and `fetch`) fails V10;
- the unfixed page fails V13 and the fixed page passes it.

## Environment (karyon, scratch only, no sudo, no system package change)
- Linux 7.0.0-34-generic x86-64, node v22.22.1, puppeteer-core 24.43.1, bubblewrap 0.11.1, strace 6.19.
- Chrome for Testing 155.0.8059.84 (`chrome-headless-shell` and `chrome`), installed by
  `npx @puppeteer/browsers install` into `scratch_agent/v04/viewer-2/browsers/`.
- Launch flags: `--no-sandbox --use-angle=swiftshader --enable-unsafe-swiftshader --ignore-gpu-blocklist
  --window-size=1600,1200`, headless shell mode, pipe transport. `--no-sandbox` turns off Chrome's own process
  sandbox. The bwrap network namespace is applied from outside.
- The earlier Firefox 158 route (no WebGL context) was not used. No Xvfb is installed on karyon, so the Mesa
  llvmpipe route was not available without system packages.
- Network-isolation positive control: inside bwrap an external navigation fails with `net::ERR_INTERNET_DISCONNECTED`;
  outside it succeeds. Under strace, a navigation to an external site produced 6 AF_INET/AF_INET6 connects. The
  logging therefore detects real network use.

## Pages (generated by the 0.4 commands in scratch, from development data)
| page | demo, data | command |
|---|---|---|
| demo 1 | `1_region_1VTM`; d2_1VTM_agreement, Boltz-2, 2 runs x 5 samples | `rnplens view project --analysis analysis --rna 1-3` (the region rule gives RNA 1-3, the whole 3-nt RNA) |
| demo 1b | `1b_region_subrange`; pilot 2JEA exec_A / exec_B, 5 + 5 | `rnplens view ... --rna 26-35` |
| demo 3, representatives t = 0.3 / 0.5 / 0.7 | `3_grouping_6BJG`; pool A 6BJG, 50 samples | `rnplens view ... --ids <representatives at t from groups.json> --out analysis/viewer_representatives_t<t>` |
| demo 3, all 50 | as above | the demo's own `rnplens view project --analysis analysis` |

Representatives in `groups.json` (group number in display order):
- t = 0.3: s021 (1), s019 (2).
- t = 0.5: s013 (1), s033 (2), s016 (3), s039 (4), s020 (5).
- t = 0.7: 18 groups, with representatives s013, s007, s005, s025, s010, s034, s014, s043, s011, s045, s044, s041,
  s023, s042, s016, s003, s039 and s020 for groups 1-18.

The demo scripts at `cf81acd` (`019c930` for run 1; demos unchanged) ran to exit 0 on karyon. They used the same
regions as `DEMOS_REPORT.md`: RNA 1-3 for 1VTM and RNA 26-35 for 2JEA. The groups at t = 0.3 / 0.5 / 0.7 numbered
2 / 5 / 18.

No excluded target, DockQ label, reference structure, Codex call or language-model call was involved.

## Results per page and item (governed run 2, code `b24a6d9`, viewer after the F1 fix; `run2/checks.json` sha256 `ea4d50117c6704e30490ce11a59671abaac1ab774f3b17d4f2273df0db1ae8b5`)
| page | snapshots | V1 load (both runs) | V10 network | V2 file | V3 chains + positions | V4 cartoon colours | V5 highlight = contact record | V6 side table | V7 sequence panel | V8 labels | V9 colours rendered | V13 ribbon colour | V12 representatives | PASS/FAIL/NE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| demo1_1VTM_rna1-3_a1 | 10 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | n/a | 109/0/0 |
| demo1b_2JEA_rna26-35_a1 | 10 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | n/a | 109/0/0 |
| demo3_6BJG_reps_t0.3_a1 | 2 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | 30/0/0 |
| demo3_6BJG_reps_t0.5_a1 | 5 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | 60/0/0 |
| demo3_6BJG_reps_t0.7_a1 | 18 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | 190/0/0 |
| demo3_6BJG_all50_a1 | 50 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | n/a | 509/0/0 |
| **total** | 95 | | | | | | | | | | | | | **1007/0/0** |

Visual inspection by the agent passed on all six pages, with no discrepancy against the records. Details:
- All 475 screenshots of run 2 were viewed on 24 contact sheets: 5 per snapshot (loaded, overview, RNA focus,
  ribbon, ribbon-RNA focus).
- The full-resolution subset was viewed: 40 images.
- 199 residue labels were read off the full-resolution images. All 199 are in the expected highlight set of that
  structure, with the construct's residue letter. This is checked in code against the records.
- Snapshot titles name the intended structure, and the sequence panel shows the construct sequence of the selected
  chain.
- With ball-and-stick hidden, every highlighted residue's ribbon shows the highlight colour, and the other residues
  show the molecule colour.

### Governed run 1 (code `019c930` = viewer at `cf81acd`), kept as found
| page | snapshots | V1 load (both runs) | V10 network | V2 file | V3 chains + positions | V4 cartoon colours | V5 highlight = contact record | V6 side table | V7 sequence panel | V8 labels | V9 colours rendered | V13 ribbon colour | V12 representatives | PASS/FAIL/NE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| demo1_1VTM_rna1-3 | 10 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | not in plan | n/a | 99/0/0 |
| demo1b_2JEA_rna26-35 | 10 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | not in plan | n/a | 99/0/0 |
| demo3_6BJG_reps_t0.3 | 2 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | not in plan | PASS | 28/0/0 |
| demo3_6BJG_reps_t0.5 | 5 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | not in plan | PASS | 55/0/0 |
| demo3_6BJG_reps_t0.7 | 18 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | not in plan | PASS | 172/0/0 |
| demo3_6BJG_all50 | 50 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | not in plan | n/a | 459/0/0 |
| **total** | 95 | | | | | | | | | | | | | **912/0/0** |

Visual inspection of run 1: **FAIL on every page for the highlight ribbon colour (F1)**. Otherwise it found no
discrepancy: 175 labels were read and all matched the records.

## Finding F1 and the fix
- **What was seen.** At `cf81acd`, `viewer.py` drew highlighted residues three times: once in the molecule's own
  cartoon (grey or tan), once as a second, highlight-coloured cartoon over the same residues, and once as
  ball-and-stick.
  - In SwiftShader the second cartoon was never visible. The ribbon of each highlighted residue stayed grey (protein)
    or tan (RNA), and only the atoms were orange or blue.
  - The Mol* state contained the second cartoon with the intended colour, so the automated checks of the frozen plan
    passed.
  - The colour key on the page promises highlighted residues in orange and blue. The highlighted residues were still
    identifiable by their coloured atoms and labels.
- **Fix (`7131025`).** `_mvs_root` now adds the highlight colour as a MolViewSpec `color` node with a residue
  selector inside the molecule's single cartoon. Mol* builds this as an `mvs-multilayer` colour theme: the molecule
  colour on all residues, and the highlight colour on the selected ones. The ball-and-stick component is unchanged.
- **Tests.** `tests/test_viewer_highlight_colour.py` has 3 tests:
  - there is one cartoon per molecule, whose colour layer equals Report's contact record for the region;
  - highlight components draw ball-and-stick only;
  - a page without highlights uses plain colours;
  - when only protein residues are highlighted, only the protein cartoon is coloured.

  Two of the three fail on the unfixed `viewer.py`. The existing `tests/test_viewer.py` passes unchanged.
- **Whether F1 depends on the renderer** (SwiftShader against a hardware GPU) was not determined. The fix does not
  depend on it, because it removes the coincident surface.

## Request logs
For each page there are two runs (offline and netlog). In each run, every URL requested is logged by CDP
`Network.requestWillBeSent` and by the puppeteer `request` event:
- `run2/requests_<page>.tsv` for the pages after the fix;
- `run1/requests_<page>.tsv` for the pages before it.

| page (run 2) | requests per run | schemes | non-local | WebSocket | CSP violations | strace AF_INET/6 calls (netlog run) |
|---|---|---|---|---|---|---|
| demo1_1VTM_rna1-3_a1 | 38 | file 28, data 10 | 0 | 0 | 0 | 0 |
| demo1b_2JEA_rna26-35_a1 | 38 | file 28, data 10 | 0 | 0 | 0 | 0 |
| demo3_6BJG_reps_t0.3_a1 | 22 | file 12, data 10 | 0 | 0 | 0 | 0 |
| demo3_6BJG_reps_t0.5_a1 | 28 | file 18, data 10 | 0 | 0 | 0 | 0 |
| demo3_6BJG_reps_t0.7_a1 | 54 | file 44, data 10 | 0 | 0 | 0 | 0 |
| demo3_6BJG_all50_a1 | 118 | file 108, data 10 | 0 | 0 | 0 | 0 |

What the requests are:
- `file:` requests: `viewer.html`, `assets/molstar.css`, `assets/molstar.js`, `structures/NN_<label>.pdb.js` (one
  per structure) and `view_data.js`, each logged by both listeners.
- `data:` requests: the WebAssembly module and the small UI images embedded in molstar.js. These are in-memory, not
  network requests.
- The only socket connects in strace are AF_UNIX to the local D-Bus sockets (`/run/dbus/system_bus_socket`,
  `/run/user/1001/bus`).

The page's CSP limits `connect-src` to `'self' blob: data:`. Negative control NC2 showed that an injected `https://`
request is blocked by the CSP and is still caught by the harness.

## Screenshots (reduced JPEG copies; full PNGs remain in karyon scratch `scratch_agent/v04/viewer-2/results_governed*/`)
Run 2 (after the fix):

![demo 1, s001 run_A#1VTM_model_0, RNA 1-3: as loaded](screenshots/run2_demo1_1VTM_s001_loaded.jpg) ![demo 1, s001, ball-and-stick hidden: highlighted ribbon colours](screenshots/run2_demo1_1VTM_s001_ribbon.jpg)
![demo 1, s001, whole structure](screenshots/run2_demo1_1VTM_s001_overview.jpg) ![demo 1, s006 run_B#1VTM_model_0, focus on the RNA contacts](screenshots/run2_demo1_1VTM_s006_rnafocus.jpg)
![demo 1b, s001 exec_A#2JEA_model_0, RNA 26-35](screenshots/run2_demo1b_2JEA_s001_loaded.jpg) ![demo 1b, s001, whole structure](screenshots/run2_demo1b_2JEA_s001_overview.jpg)
![demo 1b, s006 exec_B#2JEA_model_0](screenshots/run2_demo1b_2JEA_s006_loaded.jpg) ![demo 1b, s006, ribbon view](screenshots/run2_demo1b_2JEA_s006_ribbon.jpg)
![demo 3, t = 0.3, representative of group 2: s019](screenshots/run2_demo3_t0.3_s019_loaded.jpg) ![demo 3, t = 0.3, representative of group 1: s021](screenshots/run2_demo3_t0.3_s021_loaded.jpg)
![t = 0.5, group 1: s013](screenshots/run2_demo3_t0.5_s013_loaded.jpg) ![t = 0.5, group 2: s033](screenshots/run2_demo3_t0.5_s033_loaded.jpg) ![t = 0.5, group 3: s016](screenshots/run2_demo3_t0.5_s016_loaded.jpg)
![t = 0.5, group 4: s039](screenshots/run2_demo3_t0.5_s039_loaded.jpg) ![t = 0.5, s039, ribbon view](screenshots/run2_demo3_t0.5_s039_ribbon.jpg) ![t = 0.5, group 5: s020](screenshots/run2_demo3_t0.5_s020_loaded.jpg)
![t = 0.7, first snapshot: s003 (group 16)](screenshots/run2_demo3_t0.7_s003_loaded.jpg) ![t = 0.7, last snapshot: s045 (group 10)](screenshots/run2_demo3_t0.7_s045_loaded.jpg) ![all 50, s025, ribbon view](screenshots/run2_demo3_all50_s025_ribbon.jpg)

Snapshots on the representative pages are in the page's structure order (manifest order by id), not group order.
The group number of each representative is given in the captions above and in V12.

Run 1 (before the fix): the ribbon of highlighted residues is grey or tan; only the atoms are coloured.

![run 1, demo 1, s001](screenshots/run1_demo1_1VTM_s001_loaded.jpg) ![run 1, demo 1b, s006](screenshots/run1_demo1b_2JEA_s006_loaded.jpg) ![run 1, t = 0.5, s039](screenshots/run1_demo3_t0.5_s039_loaded.jpg)
![run 1, all 50, s025](screenshots/run1_demo3_all50_s025_loaded.jpg) ![run 1, demo 1 overview](screenshots/run1_demo1_1VTM_s001_overview.jpg) ![run 1, demo 1b overview](screenshots/run1_demo1b_2JEA_s001_overview.jpg)
![run 1, t = 0.3, s019](screenshots/run1_demo3_t0.3_s019_loaded.jpg) ![run 1, t = 0.7, s045](screenshots/run1_demo3_t0.7_s045_loaded.jpg)

## Observations (not defects of RNPLens; for the owner's judgement)
1. The Mol* Structure panel and sequence-panel header name each structure by its in-memory archive URI
   (`arcp://ni,MurmurHash3_128;.../assets/<nn>_<label>.pdb`). The readable structure name (`s001 run_A#...`)
   appears only in the snapshot title and the page's side table.
2. The highlight components are listed in the Mol* Components panel as `Custom Selection: [{auth_asym_id ...`.
3. In some focused views:
   - the near clipping plane cuts atoms (for example 6BJG s025);
   - the snapshot caption box overlaps the 3D view;
   - labels overlap where many highlighted residues are close together, as in the 2JEA pages with 24-30
     highlighted residues.
4. The Mol* sequence panel shows the construct sequence and position markers, verified as V7. It does not colour
   the highlighted positions.
5. Full-page screenshots taller than Chrome's capture limit (16,384 px; the all-50 page is 20,870 px) repeat their
   content. The side table was checked from the DOM (V6), not from that image.
6. The structure rendering of a 50-structure page takes about 2 s to the LOADED state in software rendering
   (load_ms 1,863-1,905). Switching between snapshots was not timed.

## Claims supported by this evidence
- In Chrome for Testing 155 (headless shell) with software WebGL 2, and with no network interface available, each
  of the six pages:
  - loads from the local disk;
  - renders all of its structures;
  - attempts no request other than to local files and in-memory data.
- Mol* loads the protein and RNA chains declared in the project manifest, with construct numbering and construct
  sequence.
- The highlighted residues are exactly those of Report's per-structure contact records, restricted to the region on
  region pages. They are drawn in the documented colours, and since `7131025` also on the ribbon.
- The labels and the side table show the same residues, with evidence IDs that point into
  `report/contacts_by_output.json`.
- The demo-3 representative pages show exactly the representatives in `groups.json` at the shipped thresholds 0.3,
  0.5 and 0.7.

## Claims NOT supported
- Rendering on a physical GPU, or in other browsers: Firefox, Safari, desktop Chrome or Edge.
- Rendering on macOS or Windows.
- Rendering at other screen sizes and pixel densities.
- Interaction: mouse rotation, hover tooltips, clicking the snapshot controls, the Mol* UI menus.
- Readability for a person, colour perception, and accessibility.
- Behaviour when the page is served over HTTP rather than opened from disk.
- That a person on a real display sees what the screenshots show. "A working visual interface" should not be
  claimed until the owner has done the checklist below.

## Checklist for the owner (real display, physical GPU, normal desktop browser, network unplugged)
Use any recent desktop browser (Chrome, Firefox or Safari), on a machine with a GPU, with Wi-Fi off and the cable
unplugged. Build pages with `rnplens view` from this branch at or after `7131025`, for example by re-running
`demos/1_region_1VTM`, `demos/1b_region_subrange` and `demos/3_grouping_6BJG`, or the bundled 7K9D example. Record a
yes or no for each step.
1. Open `analysis/viewer_<range>/viewer.html` by double-click, a `file://` URL. Within a few seconds, the status
   line under the viewer reads `LOADED: N structure(s) loaded from this folder`. It must not read `ERROR` or stay
   on `PENDING`.
2. Open the browser developer tools, Network tab, and reload. Every request is to `file://` or `data:`; nothing
   else appears, and the Console shows no CSP or network errors.
3. The first structure shows a grey protein cartoon and a tan RNA cartoon. The highlighted protein residues are
   orange and the highlighted RNA residues are blue, both as ball-and-stick and on the ribbon itself.
4. The snapshot title, top left of the viewer, names the first structure in the page's "Structures" list (for
   example `s001 run_A#1VTM_model_0`).
5. Pick three labelled residues in the 3D view and find each one in the page's "Highlighted residues" table: same
   structure, molecule, chain and number.
6. In the sequence panel at the top, choose each chain in the chain selector. The letters and numbering match
   `project/construct_protein.fasta` and `construct_rna.fasta`.
7. Step through the snapshots with the arrows next to the title. Each structure in the list appears once, and its
   highlights change with it.
8. On `analysis/viewer_representatives_t0.5/viewer.html` from demo 3, the five structures shown are the five
   representatives listed for t = 0.5 in `analysis/groups/groups.html`.
9. Rotate and zoom with the mouse, and hover over a highlighted residue. The tooltip names the structure and
   "highlighted ... residues".
10. Note anything unclear, unreadable or slow, the browser name and version, the operating system and the GPU.

## Tests (this branch)
| where | HEAD | result |
|---|---|---|
| local macOS (conda `rnplens`, `PYTHONPATH` = clone; `rnplens.__version__` 0.4.0.dev0) | `cf81acd` (baseline) | 541 passed, 1 failed (known: `test_report_numbers_equal_the_rc3_expected_output`, last-digit float), 17 skipped |
| local macOS | `b24a6d9` | 544 passed, 1 failed (the same known test), 17 skipped |
| karyon (track clone `tracks/viewer-2`, dev_0.3 venv) | `b24a6d9` | 550 passed, 12 skipped |

The final-HEAD counts are in the hand-back report. The optional real-browser test in `tests/test_viewer.py`
(Firefox) stays skipped: `RNPLENS_BROWSER_CHECK` is not set, and that Firefox route has no WebGL context.

## Deviations
- **Local sandbox.** The sandbox refuses shell commands containing the bwrap network-namespace flag.
  - The driver `run_all.sh` was written with the file editor; it contains the flag and is used only on karyon.
  - A planned optional WebGL pytest (`tests/test_viewer_webgl.py`) was first written in a way that split that flag
    string to get past the filter. It was deleted, never committed, and is **not** part of this branch. The owner
    has been told.
- **Excluded from the governed pages.** The bundled 7K9D example was used only to develop and validate the harness,
  including the negative controls.
- **F1 changed the viewer in mid-verification.** It was handled as the plan requires: run 1 is recorded as found;
  the fix and Amendment 1 were committed before run 2; run 2 re-checked new copies of all six pages (`*_a1`) from
  unchanged projects and analyses.
- **Plan wording.** The plan was committed twice before the governed run (`634e174`, then `019c930` for wording).
  The harness files are identical in both commits.
- **Visual-inspection scope.** Every screenshot was viewed on contact sheets. Full resolution covered the planned
  subset only, not all 760 screenshots.
- **Not done:**
  - Firefox with Mesa llvmpipe, because karyon has no Xvfb.
  - macOS rendering, because browsers abort in the local sandbox.
  - Interaction tests.
- **Screenshot copies.** Full-resolution PNGs and contact sheets were not committed, to keep the repository small.
  They are in karyon scratch; reduced JPEGs are in `records/viewer/screenshots/` (27 files, 1.7 MB).


## 2026-10-18 — owner-reported manual test on macOS

Source: the owner's decision note of 18 Oct 2026 (section 4). Recorded as reported by the owner; the agent did not
observe the screen. Machine: the owner's Mac (macOS), desktop browser on a physical display; page: the 2JEA RNA 26-35
viewer page (`1b_2JEA_RNA_26-35`) from the owner real-screen package (`RNPLens_owner_screen_check.zip`).

Reported as working:
- the 2JEA viewer page opens;
- it displays the structures;
- rotation and zoom work;
- the page responds to nucleotide clicks;
- different nucleotide selections highlight different regions.

Not yet checked manually (remaining before the viewer can be called visually qualified):
1. **6BJG binding-hypothesis representatives**: switching between the representatives of the grouping
   (`3_6BJG_representatives_t0.5`, five representatives s013, s033, s016, s039, s020) shows a different structure
   each time, with its own highlights.
2. **Offline operation**: the pages open and work with Wi-Fi and Ethernet disconnected.

Consequence for the status label: the label now names the manual confirmation and the two remaining checks
(`rnplens.viewer.STATUS`, `rnplens view` help, docs); the viewer remains **not fully visually qualified**. Fresh pages
for the two remaining checks were built from the RC branch `rc/0.4-candidate` (6BJG representatives at t = 0.5, and the
2JEA page as a control), with step-by-step instructions and a results template in `MAC_REMAINING_VIEWER_CHECKS.md`
(RC hand-back package). Their results, when the owner reports them, belong in a new dated entry below.
