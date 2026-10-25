# Owner real-screen package: contents and fresh-unzip test

Package `RNPLens_owner_screen_check.zip`: sha256 `4a4857fc87195e6260c7cd64e364a025f7552af78eedb1dd65915bbe562c6a37`, 15,105,993 bytes, 6 files (61,035,187 bytes unzipped).
- Built by `harness/make_package.py`, through `harness/r2_stage2.sh` at commit `2677969`, from the six pages rebuilt
  at `8ddc7b5` (stage 1: the demo scripts and `rnplens view`, unchanged).
- Status: the viewer is automatically tested, awaiting manual visual confirmation; not fully visually qualified.

## Contents
- `index.html`: links to the six pages, by relative path only.
- `OWNER_SCREEN_CHECK.md`: the owner's five steps, the expected highlights per structure, and the result form. It is
  identical to `records/viewer/OWNER_SCREEN_CHECK.md` at `2677969`.
- `expected_highlights.json`: the same lists, machine-readable, built from coverage B.
- `PACKAGE_MANIFEST.json`: the SHA-256 of every file, plus the scan results.
- `pages/<page>/`: unchanged copies of the `rnplens view` output folders:
  - `1_1VTM_RNA_1-3`, `1b_2JEA_RNA_26-35`, `3_6BJG_representatives_t0.3`, `_t0.5`, `_t0.7` and `3_6BJG_all_50`;
  - each folder has `viewer.html`, `assets/` (the vendored Mol* 5.13.1 `molstar.js`, `molstar.css`, licence and
    version record, hash-identical to `src/rnplens/vendor/molstar`), `structures/` (the PDB copies and their `.js`
    wrappers), `view.mvsj`, `view_data.js` and `viewer_manifest.json`.

## Scans (recorded, nothing rewritten)
- **Excluded targets: 0 hits.** The scan checked all 37 identifiers, in file names and in the content of every file,
  including the Mol* assets (rescanned locally over the whole zip). The targets present are 1VTM, 2JEA and 6BJG,
  all development targets.
- **Absolute paths in the visible text of any page: 0.**
- **Absolute paths in file content:**
  - The six `viewer_manifest.json` files hold their provenance: input structure paths, the contact-record path and
    the structure sources on the build machine (karyon, user home folder `jwen`). `PACKAGE_MANIFEST.json` lists
    those hits.
  - The Mol* release `molstar.js` contains the string `/home/web_user`. This is the virtual home folder of the
    in-browser WebAssembly runtime, not a path on any machine, and the file is left unchanged because it is the
    hash-checked release.
  - No path on the owner's machines appears anywhere in the package.

## Fresh-unzip test on karyon (stage 2, frozen driver `run_all.sh` unchanged since round 1)
The zip was unzipped into a new, empty folder. Each page was rendered twice:
- once inside `bwrap --unshare-net`;
- once with CDP request logging and `strace -f`.

The browser was Chrome for Testing headless shell 155.0.8059.84, renderer
`ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)`. `harness/zip_check.py` results:

| page | structures | result | checks | requests (offline) | strace AF_INET/6 calls | load ms |
|---|---|---|---|---|---|---|
| 1_1VTM_RNA_1-3 | 10 | PASS | ✓Z1 ✓Z2 ✓Z3 ✓Z4 ✓Z5 ✓Z6 | file 28, data 10 (both runs: 38 / 38) | 0 | 1617 |
| 1b_2JEA_RNA_26-35 | 10 | PASS | ✓Z1 ✓Z2 ✓Z3 ✓Z4 ✓Z5 ✓Z6 | file 28, data 10 (both runs: 38 / 38) | 0 | 1656 |
| 3_6BJG_all_50 | 50 | PASS | ✓Z1 ✓Z2 ✓Z3 ✓Z4 ✓Z5 ✓Z6 | file 108, data 10 (both runs: 118 / 118) | 0 | 1955 |
| 3_6BJG_representatives_t0.3 | 2 | PASS | ✓Z1 ✓Z2 ✓Z3 ✓Z4 ✓Z5 ✓Z6 | file 12, data 10 (both runs: 22 / 22) | 0 | 1517 |
| 3_6BJG_representatives_t0.5 | 5 | PASS | ✓Z1 ✓Z2 ✓Z3 ✓Z4 ✓Z5 ✓Z6 | file 18, data 10 (both runs: 28 / 28) | 0 | 1573 |
| 3_6BJG_representatives_t0.7 | 18 | PASS | ✓Z1 ✓Z2 ✓Z3 ✓Z4 ✓Z5 ✓Z6 | file 44, data 10 (both runs: 54 / 54) | 0 | 2136 |

Checks:
- Z1: loaded in both runs;
- Z2: only `file:` and `data:` requests, no WebSocket, no CSP violation, 0 internet socket calls;
- Z3: snapshot titles equal the expected labels;
- Z4: Mol*'s ball-and-stick and cartoon-layer residue sets equal `expected_highlights.json` for every structure;
- Z5: every `file:` request lies inside the unzip folder;
- Z6: the status label is present.

**All six pages pass.**
- Coverage C, the full Part-1 comparison with Mol*'s state from this fresh unzip, found 0 discrepancies on all six
  pages.
- Index probe, offline: `index.html` made 1 request, a `file:` request for itself. All 6 links resolve to files
  inside the package.
- `run_all.sh`'s own `check_pages.py` step stopped with exit 1, as the plan says it would: the package does not
  include the project records. This failure is not a result.
- Request logs: `r2/request_logs_zip/requests_<page>.tsv`.

## Limits
This shows that the zip opens from a fresh location in one headless Linux browser with networking off. It does not
show behaviour in Safari, Firefox or desktop Chrome on macOS or Windows, on a physical GPU, or as seen by a person.
`OWNER_SCREEN_CHECK.md` covers those.
