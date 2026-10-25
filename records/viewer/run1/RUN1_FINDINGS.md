# Viewer verification, governed run 1 (code at 019c930; plan as frozen in 634e174/019c930)

Run started 2026-10-16T19:56:47Z on karyon, in the clone at `019c930`. The harness files equal the SHA-256 values frozen in
`VERIFICATION_PLAN.md`. This record is committed as found, before any change to the viewer or the harness.

## Automated checks (`checks.json`, sha256 `b0451d47b3c49124803127f21b2f337a82ec08945072e973d818970f9b130f82`)
| page | structures | PASS | FAIL | NOT_EVALUATED |
|---|---|---|---|---|
| demo1_1VTM_rna1-3 | 10 | 99 | 0 | 0 |
| demo1b_2JEA_rna26-35 | 10 | 99 | 0 | 0 |
| demo3_6BJG_reps_t0.3 | 2 | 28 | 0 | 0 |
| demo3_6BJG_reps_t0.5 | 5 | 55 | 0 | 0 |
| demo3_6BJG_reps_t0.7 | 18 | 172 | 0 | 0 |
| demo3_6BJG_all50 | 50 | 459 | 0 | 0 |
| **total** | 95 snapshots (structures repeat across the demo-3 pages) | 912 | 0 | 0 |

Renderer (Mol*'s own WebGL context): `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)`, WebGL 2.0.

Requests:
- Both runs of every page logged only `file:` and `data:` URLs (`requests_<page>.tsv`).
  - The `data:` URLs are the WebAssembly module and the UI images that molstar.js embeds.
- No WebSocket and no CSP violation was recorded.
- strace of the netlog runs: 0 AF_INET/AF_INET6 calls. The only socket connects are AF_UNIX to the D-Bus sockets
  `/run/dbus/system_bus_socket` and `/run/user/1001/bus` (local IPC of the browser).

## Visual inspection
- Every screenshot (285 per run) was viewed on contact sheets.
- The plan's full-resolution subset (23 images plus 6 full-page images) was also viewed.
- The 175 residue labels read off the full-resolution images all belong to the expected highlight set, with the
  construct's residue letter.

Finding **F1, a viewer defect**:
- For highlighted residues, `viewer.py` adds a highlight-coloured cartoon on top of the molecule's own cartoon.
- In every inspected image the ribbon of highlighted residues shows the molecule colour (grey protein, tan RNA), not
  the highlight colour. Only the ball-and-stick atoms carry the highlight colours.
- The Mol* API confirms that both cartoon representations exist with the intended colours (check V5 passes), but
  the highlight cartoon is not visible. The pixel check V9 passes because the ball-and-stick atoms are coloured.
- The page's colour key ("highlighted protein residue", "highlighted RNA residue") is therefore only partly true of
  what is drawn. The highlighted residues are still identifiable, by their coloured atoms and labels.

Observations, not defects of RNPLens:
- The Mol* Structure panel and the sequence-panel header name the structure by its in-memory archive URI
  (`arcp://ni,MurmurHash3_128;.../assets/<nn>_<label>.pdb`). Only the snapshot title names the structure in readable
  form.
- The highlight components are listed as `Custom Selection: [{auth_asym_id ...` in the Components panel.
- In some focused views:
  - the near clipping plane cuts atoms (for example all-50 s025);
  - the snapshot caption box overlaps the 3D view;
  - labels overlap where many residues are close together.
- The Mol* sequence panel does not show the highlight colours. Its letters and position markers equal the construct
  (V7).
- The all-50 full-page screenshot is 20,870 px tall, above Chrome's 16,384 px capture limit, and its content repeats.
  This is a screenshot artifact. The side-table rows were checked from the DOM (V6), not from the image.

_Correction (17 Oct 2026, after commit 51b9914): the total row first read 85 snapshots and the screenshot count 255; the per-page rows sum to 95 snapshots and 285 screenshots per run. No result changed._
