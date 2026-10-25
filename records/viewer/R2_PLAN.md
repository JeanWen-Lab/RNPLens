# Viewer verification, round 2: plan (frozen before the runs it governs)

Branch `track/viewer-r2`, from integration HEAD `b3374e4`, plus `4015406` (viewer status label). 17 Oct 2026.
Authority: the owner decision note of 17 Oct, item 6 ("Mol* visual check") and the viewer label in item 3. All
round-1 results (`run1/`, `run2/`, `MOLSTAR_VISUAL_VERIFICATION.md`) stay as found.

## Part 1. Highlight coverage: a complete per-structure set comparison (`harness/coverage.py`)
Pages:
- **A (as found):** the six governed run-2 pages (`*_a1`, round 1, viewer `7131025`), with Mol*'s own state from
  run 2 (`results_governed2/<page>/result_offline.json`). Page list: `harness/pages_r2_governed_run2.json`.
- **B (new):** the six pages rebuilt at this commit for the owner package. Demos 1, 1b and 3 are re-run with their
  own scripts into a fresh folder, the three representative pages are rebuilt as in round 1, and nothing else is
  changed. Page list: `harness/pages_r2_package.json`. Driver: `harness/r2_stage1.sh`.
  - Mol*'s state for B comes from the zip test in Part 2 (coverage C).

For every structure on every page, the sources compared are:
- **R1 (reference):** Report's record `analysis/report/contacts_by_output.json[<engine>|<run>#<sample>]`. On region
  pages it is restricted to the region's RNA range, read from the demo's `logs/03_region_rule.log`.
- **R2 (region pages):** the region record `region_<a>-<b>/region.json`, as contact pairs per structure.
- **V1:** the page's `view.mvsj`:
  - the residues of the ball-and-stick (highlight) component;
  - the highlight colour layer of the molecule cartoon.
- **V2:** the page's `viewer_manifest.json` "highlighted".
- **V3:** the visible side table of `viewer.html`.
- **V4:** Mol*'s state (render.js): the ball-and-stick component residues, and the cartoon multilayer highlight
  residues.

**Comparison rule.**
- For each of V1-V4, the protein residue set and the RNA residue set, on the declared chain, must equal R1's.
- On region pages, R2's contact-pair set must equal R1's.
- Every difference is recorded, with missing and extra residues.

**Region pages: every RNA position in the region, per structure, is classified exactly once** (`coverage.py`
docstring):

| class | condition |
|---|---|
| HIGHLIGHTED | in R1 and highlighted in every viewer source |
| NO_QUALIFYING_CONTACT | present in the page's structure copy and the construct mapping, not in R1, and highlighted in no source |
| ABSENT_FROM_STRUCTURE_OR_MAPPING | missing from the structure copy, unresolved in the region record, or outside the chain's recorded numbering |
| OMITTED_BY_VIEWER | in R1 but not highlighted in some viewer source (a viewer defect) |
| HIGHLIGHTED_WITHOUT_RECORD | highlighted in some source but not in R1 (a viewer defect) |

**Independent geometry.** For each RNA position in the region, the minimum heavy-atom distance to any protein heavy
atom of the structure copy is computed. Report's definition is 5.0 Å, so a position in R1 should be within 5.0 Å and
a position not in R1 should be beyond it.
- This is a descriptive cross-check, **not** Report's qualified route.
- A disagreement would be reported as a question about Report's record, not as a viewer result.
- It is not a pass criterion for the viewer.

**Pass rule.**
- Part 1 passes for a page if every comparison is equal for every structure, and no position is classed
  OMITTED_BY_VIEWER or HIGHLIGHTED_WITHOUT_RECORD.
- The result for positions 26 and 30 on the 2JEA page is reported per structure exactly as classified.
- A viewer defect is recorded as found, fixed with a test, and the affected pages are re-verified in new folders,
  with earlier results kept as found.

## Part 2. Owner real-screen package and its fresh-unzip test
**Package** (`harness/make_package.py`, driver `harness/r2_stage2.sh`):
- the B pages, copied unchanged into `RNPLens_owner_screen_check/pages/<short>/`, including their vendored Mol*
  assets;
- `index.html`, with relative links only and a CSP;
- `expected_highlights.json`, built from coverage B;
- `OWNER_SCREEN_CHECK.md`, written after coverage B because it carries the expected lists;
- `PACKAGE_MANIFEST.json`, with the SHA-256 of every file;
- a deterministic zip.

Scans, recorded and not rewritten:
- the 37 excluded target identifiers, in file names and in content;
- absolute paths (`/home/<user>`, `/Users/<user>`, `/mnt/...`, `C:\Users`), in all files and separately in the
  visible text of the HTML pages.

**Zip test**, in a fresh unzip folder on karyon:
- The frozen driver `run_all.sh`, unchanged, renders every unzipped page twice:
  - offline, inside `bwrap --unshare-net`;
  - logged, with CDP request logging and `strace -f` of connect/sendto.
- Its own `check_pages.py` step needs the project records, which are not in the package. It is expected to fail
  there, and that failure is not a result.
- `harness/zip_check.py` then checks, per page:
  - **Z1:** LOADED in both runs, with no page error;
  - **Z2:** only `file:` and `data:` requests, no WebSocket, no CSP violation, and 0 AF_INET/AF_INET6 calls;
  - **Z3:** the snapshot titles equal the expected labels, in order;
  - **Z4:** Mol*'s ball-and-stick and cartoon-layer residue sets equal `expected_highlights.json` per structure and
    chain;
  - **Z5:** every `file:` request lies inside the unzip folder;
  - **Z6:** the status label is in `viewer.html` and `index.html`.
- Coverage C re-runs Part 1 on the B pages with Mol*'s state from this zip test.
- **Index probe:** `bwrap --unshare-net --dev-bind / / --proc /proc -- node index_probe.js <chrome>
  <unzip>/RNPLens_owner_screen_check/index.html <out>`. It must record only `file:` requests, and every link must
  resolve to a file inside the package.

**Pass rule.** Part 2 passes if Z1-Z6 pass on all six pages, the index probe passes, coverage C passes Part 1, and
there are 0 excluded-target hits. Absolute paths inside JSON provenance files are reported, not hidden. Absolute
paths in visible page text count as a failure.

## Harness validation already done (development data only: bundled 7K9D example; not governed)
| page | result |
|---|---|
| 7K9D fixed page, RNA 15-30, with Mol*'s state | 0 discrepancies; all 7 comparisons equal for both structures; positions 15-23 HIGHLIGHTED, 24-30 NO_QUALIFYING_CONTACT; independent geometry agrees at every position |
| NC1: every highlight shifted by +1 | 28 discrepancies: V1-V3 unequal; OMITTED_BY_VIEWER at 15-23; HIGHLIGHTED_WITHOUT_RECORD at 24 |
| NC3: RNA residue 27 deleted from the page's structure copy | 27 classed ABSENT_FROM_STRUCTURE_OR_MAPPING; 26 and 28 NO_QUALIFYING_CONTACT |
| package and fresh unzip of the 7K9D page | Z1-Z5 pass. Z6 fails as it should, because that page was built before the status label. A second packaged page with no results is reported as a failure (Z0) instead of crashing the check. Index probe: 1 `file:` request, both links resolve inside the package |

## Frozen files (SHA-256; all in `records/viewer/harness/`)
| file | sha256 |
|---|---|
| coverage.py | `4beedfaeb7058d2233661dfebc7a135935ecc806ad417b825dd3d437b887d3be` |
| make_package.py | `7f13c69d8a154bb5f0a26414e975142b428c77ed4527660cf696ab8dd94b67de` |
| zip_check.py | `559c2c8e6233034af746e1e375d9ac3eead560bc967fda8e66aa91905d876012` |
| index_probe.js | `01bf29c3974990e01ed6cab93e5f692db6312d7f96d92d05203f9abd02bf0245` |
| r2_stage1.sh | `bdc0dc79f33519e1ec7b3016727ecbd5e155bf8e97857b8a0a3f5bf546bfd088` |
| r2_stage2.sh | `4b9785ff8e4491df6f610fc48c79debb215499e4e63096753dfdaf3f400dc8f7` |
| pages_r2_governed_run2.json | `cd5a77dcbab7066f81e86cc412910f0c3318d20d6d193a50c5772c874110d6fa` |
| pages_r2_package.json | `2b57492540afb5837133d036c1e11f1e4a3ffb22dbce3d0d04d504ef26c4e3dd` |
| render.js | `97c3d82f842677c056d0833cb46aad9b1c51830a5976bd1c1c560365ead3c696` |
| run_all.sh | `7f6ef83c27af1a767ef08858c92fa5f3220699b14914da27e30b822d5256fb92` |
| check_pages.py | `15ba277d396fd704d7ba44a278cdd4c77f694b05322dfe1543c032189ce60700` |
