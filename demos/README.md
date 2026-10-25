# RNPLens 0.4 demonstrations and clean-install checks

These scripts build self-contained demonstration packages over EXISTING predicted structures. They never predict
structures, rank candidates, or treat recurrence among predictions as confidence or correctness. No script calls a
language model. Rules were fixed in advance in `records/v04_integration/DEMOS_PLAN.md`; results are in
`records/v04_integration/DEMOS_REPORT.md` and `CLEAN_INSTALL_LINUX.md`.

| folder | what it does |
|---|---|
| `1_region_1VTM/run.sh OUT` | RNA-region investigation (development task d2_1VTM_agreement): region rule, `rnplens region`, contact table, designated vs additional samples, region map, `rnplens view --rna` |
| `2_interactive_24BR/run.sh OUT` | interactive analysis (d4_24BR_compare plus a 2-nt-truncated third run): typed clarification, answer, resume, export-methods, explain, local follow-up, the SCRIPTED Codex-path demonstration, replay-followup, updates |
| `3_grouping_6BJG/run.sh OUT` | binding-hypothesis grouping (pool A 6BJG, 50 samples): group, group-diff, view, candidate-retention check, docs parity, wording scan |
| `clean_install/clean_install_linux.sh [ROOT]` | wheel and sdist builds and installs, each verified from the installed packages only; `make_record.py` writes `CLEAN_INSTALL_LINUX.md` |
| `lib/` | step runner (`common.sh`), replay (`replay.sh`, `compare_results.py`, post-hoc `classify_replay_diffs.py`), `wording_scan.py`, `access_audit.py` (strace data-access record), region rule and answer, helpers |

Run on karyon with `RNPLENS_PY=<python>` and `PYTHONPATH=<checkout>/src:<checkout>/assistant`. Each package gets
`replay.sh`, which re-runs the workflow into a new folder and compares every result JSON (`checks/replay_check.json`).
