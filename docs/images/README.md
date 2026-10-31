# Screenshots

`example_report.png` and `example_diagnose.png` are rendered from the bundled expected outputs
(`examples/expected_output/`) of the two worked examples, produced by RNPLens 0.2.0rc3 on the reference platform
(the Diagnose page is historical: Diagnose is blocked in 0.4). `example_evaluate.png` shows the 0.4 output, because
the rc3 Evaluate summary displays the blocked four-axis geometry values. Nothing in them was edited or produced
separately.

| file | source |
|---|---|
| `example_evaluate.png` | `summary.txt` written by `rnplens evaluate run --input example_input.json` in `examples/reference_based/` with RNPLens 0.4.0.dev0 (round 3, macOS arm64), shown as text; SHA-256 556eb465caecb0233975805c8ab951aada333fcd979c76cdb86ed97b22ed6488 |
| `example_report.png` | `B1_report_7K9D/report_7K9D_example.html` |
| `example_diagnose.png` | `B2_diagnose_7K9D/report.html` |

The two HTML pages were rendered with headless Firefox at 1100 px width; trailing white space below the content was
cropped. `example_evaluate.png` was drawn as monospaced text (DejaVu Sans Mono, matplotlib) at 1100 px width.

`viewer_nt_overall.png`, `viewer_nt_B33.png`, `viewer_nt_B35.png`, `viewer_nt_B30.png` and `viewer_nt_switch.png`
(viewer guide, [../viewer.md](../viewer.md)) are screenshots of the 2JEA RNA 26-35 demonstration page taken by
`records/viewer/nt_contacts/browser_nt.js` in qualification run 2 (commit 82deb28; headless Chrome for Testing
155.0.8059.84, SwiftShader WebGL, network-less namespace; steps 00_overall, 01_B33, 02_B35, 03_B30 and
11_prev_to_s005 of plan 2JEA). Each was cropped to the top 848 px (viewer and contact panel) and stored with a
256-colour palette; nothing else was edited.

`report_7K9D_v040.png` (README) shows the Report page `B1_report_7K9D/report_7K9D_example.html`, written by
`bash examples/run_examples.sh` with RNPLens 0.4.0 (commit b4132bb1, Linux x86-64, CPython 3.11.15; page SHA-256
d18bddd50803d1c40f7781e8356e12761424f8310a42f34e84e41dd6b31e5867). It was rendered with headless Firefox at 1100 px width;
the trailing white space below the content was cropped, and nothing else was edited.
