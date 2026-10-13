# Validation records

These are the frozen records behind two RNPLens behaviours. They are kept **verbatim**, because they were written
and frozen before the analyses they govern. They therefore use the project's internal identifier from that time,
"RNPBench" (for example "RNPBench Diagnose", `rnpbench-diagnose`), which is not a separate project or package.

| file | content |
|---|---|
| `PORTABLE_QUALIFICATION_CONTRACT.md` | the frozen per-quantity tolerances that `--profile portable` applies off the reference platform (one internal host name was replaced by "the reference build host") |
| `PREREGISTRATION.json`, `OOS_VALIDATION_PROTOCOL.md` | the preregistered out-of-sample evaluation of Diagnose's protein-side disagreement statement |
| `OOS_VALIDATION_RESULTS.md` | its results |
| `CAMPAIGN_SCOPE_REVISION.md` | the recorded scope revision of that evaluation |

Commands named in these records correspond to RNPLens commands as follows:

| in the records | RNPLens |
|---|---|
| `rnpbench evaluate …`, `rnpbench-evaluate …` | `rnplens evaluate run …` |
| `rnpbench validate`, `selftest`, `provenance` | `rnplens evaluate validate`, `selftest`, `provenance` |
| `rnpbench-report …`, `python -m rnpbench_predict …` (RNPBench Predict / Report) | `rnplens report …` |
| `rnpbench-diagnose diagnose …` | `rnplens diagnose run …` |
| `rnpbench-diagnose preflight` / `validity` | `rnplens diagnose preflight` / `validity` |

The identifiers that remain in RNPLens outputs are listed in [../identifiers.md](../identifiers.md).
