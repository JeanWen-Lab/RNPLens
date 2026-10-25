# Mol* viewer visual verification: plan (frozen before any governed page is opened in a browser)

Track `viewer`, branch `track/viewer` (from `cf81acd`), 16-17 Oct 2026. Owner item 2 of the 0.4 decision note.
This plan is committed before the governed run. The governed run uses the harness files at the SHA-256 values below,
taken from this commit in the karyon track clone. A change after this commit is made only as a dated amendment
committed before any re-run, and the original result is kept.

## What is being verified
The offline page written by `rnplens view` (`src/rnplens/viewer.py`, vendored Mol* 5.13.1) is checked on three
demonstrations over development data, generated in scratch by the 0.4 demo scripts at `cf81acd`:

| page_id | demo | page |
|---|---|---|
| demo1_1VTM_rna1-3 | demo 1, d2_1VTM_agreement, 2 runs x 5 samples | `rnplens view --rna <range of logs/03_region_rule.log>` (the demo's own step 05) |
| demo1b_2JEA_rna26-35 | demo 1b, pilot 2JEA exec_A/exec_B | `rnplens view --rna <range>` (step 05) |
| demo3_6BJG_reps_t0.3 / t0.5 / t0.7 | demo 3, pool A 6BJG, 50 samples | `rnplens view --ids <representatives of groups.json at t> --out analysis/viewer_representatives_t<t>` |
| demo3_6BJG_all50 | demo 3 | the demo's own `rnplens view` of all 50 structures (step 06) |

The representatives at each shipped threshold (0.3, 0.5, 0.7) are read from `analysis/groups/groups.json`. The
page list is `records/viewer/harness/pages.json`. No excluded target is used. No DockQ label, reference structure or
LLM is involved.

## Environment
- karyon (Linux 7.0, x86-64); no sudo and no system package changes.
- Chrome for Testing `chrome-headless-shell` 155.0.8059.84 and puppeteer-core 24, installed by
  `npx @puppeteer/browsers` into `scratch_agent/v04/viewer-2/`.
- Rendering uses WebGL through ANGLE on SwiftShader, which is CPU software rendering (`--use-angle=swiftshader
  --enable-unsafe-swiftshader`). The renderer string is recorded from Mol*'s own WebGL context.
- The offline run happens inside `bwrap --unshare-net` (bubblewrap 0.11.1), where only a loopback interface exists.
  Positive control: inside bwrap an external navigation fails with `ERR_INTERNET_DISCONNECTED`; outside bwrap it
  succeeds.

## Runs per page (`run_all.sh`)
1. **offline**: `render.js` inside `bwrap --unshare-net`. All screenshots used for inspection come from this run.
2. **netlog**: `render.js` with networking available, under `strace -f -e trace=connect,sendto` of the whole
   browser process tree. Every request is logged through CDP `Network.requestWillBeSent`, puppeteer `request`
   events, `Network.webSocketCreated`, new targets and workers, and `securitypolicyviolation` events.
   - Positive control: when the browser does navigate to an external site, strace records the AF_INET/AF_INET6
     connects (6 calls in the control).

For every snapshot (one per structure), `render.js` applies the snapshot by key, waits until Mol* is idle, and does
the following:
- reads the loaded model through the Mol* API: chain `auth_asym_id`, `auth_seq_id`, `label_comp_id`;
- reads every structure component, its residues and its representations with their colours;
- reads the state cells and the sequence-panel text of every polymer offered by the panel;
- takes three screenshots of `#app` (1600 x 840):
  - `loaded`: the MolViewSpec state as loaded, focused on the first highlighted component;
  - `overview`: after a Mol* camera reset;
  - `rnafocus`: the camera on the bounding sphere of the highlighted RNA residues, taken only when that
    component exists.

One full-page screenshot per page shows the side table.

## Automated checks (`check_pages.py`; expected values are computed from the records only, nothing imported from rnplens.viewer)
Expected structures:
- region pages and the all-50 page: the INCLUDED structures of `project/manifest.json`, in manifest order;
- representative pages: the representatives in `groups.json` at that threshold.

The label is `<id> <run>#<sample>` and the contact key is `<engine>|<run>#<sample>`, built from the manifest's
`run` and `sample` fields. The expected highlights are the protein and RNA positions of
`analysis/report/contacts_by_output.json[key]`, restricted to the region's RNA range where the page has one.

Page level:
- **V0**: a WebGL context exists and its renderer string is recorded.
- **V1**:
  - status `LOADED` with no page errors, in both runs;
  - the number of snapshots equals the number of expected structures;
  - the snapshot titles equal the expected labels, in order.
- **V10**: in both runs:
  - no request whose scheme is not `file:`, `blob:`, `data:` or `about:`;
  - no WebSocket;
  - no CSP violation;
  - strace (netlog run) shows 0 AF_INET/AF_INET6 `connect`/`sendto` calls;
  - the model and component residue sets are identical between the offline and netlog runs.

  `data:` and `blob:` URLs are in-memory and not network requests. They are listed and counted, and reported as such.
- **V12** (representative pages): the set of structure ids on the page equals the set of representatives in
  `groups.json` at that threshold, and their number equals `n_groups`.

Per snapshot:
- **V2**: the single loaded data cell is the page's copy of this structure, and the copy's SHA-256 equals the
  project's `used_sha256`.
- **V3**: the model has exactly the protein and RNA chains declared in the manifest. Residue numbers are 1..L, and
  the residue names spell the construct protein and RNA sequences.
- **V4**: the `Protein` and `Nucleic` components cover all residues of their chains, coloured `#BBBBBB` and `#DDCC77`.
- **V5**: the ball-and-stick (highlight) components are:
  - one protein component whose (chain, residue) set equals the expected protein set, coloured `#E69F00`;
  - one RNA component equal to the expected RNA set, coloured `#0072B2`;
  - no highlight component where the expected set is empty.
- **V6**: the page's side-table rows for this structure equal the expected (molecule, chain, residue, one-letter
  label) rows, and every evidence ID points into `report/contacts_by_output.json#/<key>/`.
- **V7**: the sequence-panel text of each polymer equals the construct sequence, and the position markers equal
  1 + offset. The result is NOT_EVALUATED if the text cannot be extracted.
- **V8**: the MolViewSpec label layer is present exactly when 1-40 residues of some molecule are highlighted.
- **V9**: pixel classes in the canvas box (40,215)-(1230,745) of the offline screenshots: each colour class that
  should be visible reaches >= 100 px in at least one of the three views. The classes are:
  - grey protein, required if some protein residue is not highlighted;
  - tan RNA, required if some RNA residue is not highlighted;
  - orange, required if protein highlights exist;
  - blue, required if RNA highlights exist.

  V9 is a coarse rendering check. It does not identify residues (negative control NC1 passes V9).

## Visual inspection by the agent (recorded per page in MOLSTAR_VISUAL_VERIFICATION.md)
- Every screenshot is viewed at least on a contact sheet.
- These are viewed at full resolution:
  - demo 1 and 1b: `loaded` and `rnafocus` of the two designated structures, plus `overview` of one;
  - representatives at t = 0.3 and 0.5: `loaded` of every representative;
  - t = 0.7 and the all-50 page: `loaded` of the first, middle (index ceil(n/2)) and last snapshot;
  - every page: the full-page screenshot.
- Recorded for each image viewed at full resolution:
  - protein and RNA visible;
  - highlight colours visible;
  - up to 5 readable residue labels, checked against the expected highlight list;
  - snapshot title equal to the expected structure;
  - sequence panel visible, with the chain shown;
  - any visual defect.
- A page passes visual inspection if no discrepancy is found.

## Pass rule
A page passes if every automated check is PASS and visual inspection finds no discrepancy. NOT_EVALUATED is not a
pass and is reported. Every FAIL is reported as found. A FAIL caused by a harness defect is reported as a harness
defect and fixed only by an amendment committed before a re-run, and the original result stays in the record. A
real viewer defect is fixed in `src/rnplens/viewer.py` with tests, and the affected pages are re-run after the fix
under an amendment.

## Harness validation already done (development page only: bundled 7K9D example, `view --rna 15-30`; not a governed page)
- Unmodified page: 27 PASS, 0 FAIL.
- NC1, every highlight shifted by +1 residue: V5 and V6 FAIL for both structures; V9 still passes, as expected.
- NC2, the unmodified page plus an injected `https://` image and `fetch`: V10 FAIL in both runs. The CSP blocked both
  requests, and CDP logged the image request attempt. strace showed 0 AF_INET calls, because the CSP blocks before
  any socket is opened.

## Frozen files (SHA-256)
| file | sha256 |
|---|---|
| records/viewer/harness/render.js | `46c681f1f91a61c6d526188fc151b88dd925f3cc87d742124dc4ca0f82dd2882` |
| records/viewer/harness/check_pages.py | `b1cd90e2d8d8efc5e300f97dcc6c46f21113e8d45ee2587c45f24303e4d08a3f` |
| records/viewer/harness/run_all.sh | `7f6ef83c27af1a767ef08858c92fa5f3220699b14914da27e30b822d5256fb92` |
| records/viewer/harness/pages.json | `69815de335b5e06dfe644fbc6cbbc329582bc91650ba477445284c50105997fe` |

## Limits stated in advance
Software-rendered headless screenshots inspected by an agent are not an on-screen check by a person on a physical
GPU. This verification can support these claims:
- the page loads and renders in a WebGL2 browser with no network;
- it attempts no non-local request in that browser;
- Mol* loads the intended chains and selects and colours the residues of the contact records;
- the rendered images show them.

It cannot support claims about other browsers or GPUs, interaction (mouse, hover tooltips), readability for a
person, or display at other screen sizes. The repeatable on-screen checklist for the owner is part of the
verification record.
