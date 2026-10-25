# Pre-registration: nucleotide contact explorer (feature/nt-contact-explorer)

Base: `de66a966260fd7048b6116bada2ddeb2171ac6d3` (qa/0.4-karyon; descends from 80a2afb and 589485b).
Feature implementation commit: `eb4bf5c` (child of de66a96). This document and the scripts it names are committed
before any run on the demonstration targets (2JEA, 1VTM, 6BJG); their SHA-256 are in `PREREG_SHA256.txt` of the same
commit. Results are written to a new folder `feature/nt-contacts/out/feature_<commit>/` and are reported as found,
including failures. Nothing here is changed after the first run; any later change is a new, separately recorded run.

What was looked at before this pre-registration (stated so it is not mistaken for blind design):
- the base 2JEA RNA 26-35 page (`out/base_de66a96`) was opened once in the browser to probe Mol* API behaviour (click
  decoding, behaviour switching, MVS opacity and lines); no contact, highlight or distance value was compared;
- development and all unit tests used the bundled 7K9D example only (harness development target).
- the harness was dry-run on the 7K9D development page: parity P 2/2 structures PASS (89 rows), browser checks 12/12
  steps PASS, run-level PASS; a negative control (`neg_control_dev.py`: ten tampered copies of that browser result --
  missing panel row, extra highlighted residue, wrong colour, distance +0.02 A, stale structure, moved line, mouse
  fallback, network request, Mol* interaction component, wrong ensemble count) was rejected in all ten cases;
- `make_plans.py` was executed on the base pages (2JEA, 1VTM, and a temporary 6BJG t=0.5 page written to tmp/) only to
  check that it runs; only its step counts were looked at (139, 59, 150 steps).

## P. Distance and correspondence parity (`parity_check.py`, gemmi; independent of the viewer code)

Pages: 2JEA `viewer_26-35` (10 structures), 1VTM `viewer_1-3`, 6BJG `viewer` (all 50 structures), 6BJG
`viewer_representatives_t0.5`. For every structure, P1-P7 of `parity_check.py` must hold:
chains equal the project manifest; construct position <-> file residue correspondence equals gemmi's file order;
{residue pairs with minimum heavy-atom distance <= 5.0 A by gemmi} equals Report's `contacts_by_output.json` record;
the page's contact rows equal Report's record; every displayed distance is within 0.005 A of gemmi's minimum
(display rounds to 0.01 A); the named closest atoms are at that minimum and their coordinates equal gemmi's
(<= 5e-4 A); the page's own distance check says PASS.
**Distances are displayed in the delivered pages only if P passes for every structure of every page.** If P fails,
the deviation is reported and the feature is not handed back as distance-qualified.

## B. Real-browser checks (`make_plans.py`, `browser_nt.js`, `check_nt.py`)

Browser: Chrome for Testing headless shell 155.0.8059.84, SwiftShader WebGL, inside a network-less namespace, every
request logged (CDP); the 2JEA run is repeated under `strace -f -e trace=connect,sendto` and must show no AF_INET /
AF_INET6 connect.

Plans (generated from the pages' manifests and Report's records; expected values are never read from the page's
explorer data):
- **2JEA RNA 26-35** (primary). On the first engine-designated structure (s001, exec_A model 0), real mouse clicks on
  RNA chain B 33, 35, 30, then Clear selection; switch to the second engine-designated structure (exec_B model 0) and
  repeat 33, 35, 30, Clear; select 33 again and switch to the previous structure (selection kept, contacts of that
  structure) and back; Show all contacts; reverse click on the lowest-numbered protein partner of B33 in that
  structure (mouse if a visible position exists, otherwise the page hook, recorded); Focus mode; click B26 (no
  contact), click B26 again (toggle off). Then a programmatic sweep: every structure x every RNA position 26-35.
- **1VTM RNA 1-3**: clicks on RNA 1, 2, 3, Clear, Next structure, RNA 2, Clear; sweep every structure x 1-3.
- **6BJG group representatives t=0.5**: RNA 19 on the first representative, Next through every representative with
  the selection kept, RNA 20 on the last, Show all contacts, Clear; sweep every representative x RNA 1-21.

Per-step criteria B0-B9 (`check_nt.py` docstring): structure shown (state, selector, panel label, Mol* coordinates of
the first atom of every chain == the expected structure file); selection; panel rows == Report's pairs of the
selected residue in the structure on screen, count, explicit "No qualifying contact"; Mol* ball-and-stick components
(selected residue alone in magenta #CC00CC, partners alone in orange #E69F00 / blue #0072B2, nothing else in focus
mode; page highlights + selection in show-all mode; page highlights only without selection); cartoon opacity
0.3 / 0.6 in focus mode; contact lines (one per row, endpoints == Mol*'s atom coordinates, length == distance);
displayed distances == gemmi minimum (<= 0.005 A); no Mol*-generated focus/interaction components; ensemble sentence
"k of n BOLTZ2" == count over Report's records; steps marked require_mouse done by a real mouse click.
Run level: status LOADED; no request except file:/data:/blob:/about:; no websocket; no failed load; no page error.
A step that fails is reported as failed; screenshots are inspected but never replace these checks.

Screenshots taken (and inspected): overall interface; B33 selected; B35 selected; B30 (no qualifying contact);
another candidate (exec_B model 0 and the previous structure with selection kept); show-all; reverse selection;
1VTM and 6BJG views.

## R. Report / Evaluate outputs unchanged (`compare_outputs.py`)

The three demonstrations are re-run at the feature commit (same demo scripts and inputs) and compared with
`out/base_de66a96` (run at de66a96 before any feature change): `report/contacts_by_output.json` and
`report/result.json` of 1VTM, 2JEA and 6BJG (byte comparison; for result.json any differing leaf must be a
run-environment field such as wall_s / environment, listed), and the pages' existing highlight lists
(`viewer_manifest.json` "highlighted"). Evaluate: the bundled 7K9D example with its reference is analysed with the
base checkout (qa/RNPLens at de66a96) and with the feature commit; `evaluate/s00*/result.json`, `result.csv`,
`summary.txt` and `report/*.json` are compared the same way. The rc3 parity tests run inside the full suites.

## S. Suites

Full pytest suites at the feature head on karyon and on the local macOS host, compared with the de66a96 counts
(karyon 663 passed / 0 failed / 12 skipped and local 648 / 0 / 27 were the 589485b-era counts; the de66a96 baseline
counts are taken in the same session before the feature commit is tested). `rnplens doctor` frozen-source check
must stay READY.
