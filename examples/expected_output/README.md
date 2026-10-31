# Expected outputs of the two worked examples (historical regression fixtures, 0.2.0rc2)

> **Historical record.** These files were produced with RNPLens 0.2.0rc2 and are kept unchanged as regression
> fixtures. They are not RNPLens 0.4 outputs. With 0.4:
> - Evaluate's `summary.txt`, `result.json` and `result.csv` withhold the four-axis geometry values (status
>   `BLOCKED`), whereas `A_evaluate_7K9D/` still contains them;
> - Diagnose refuses with `DIAGNOSE_BLOCKED`, so `B2_diagnose_validity.json` and `B2_diagnose_7K9D/` have no 0.4
>   counterpart;
> - the Report outputs in `B1_report_7K9D/` are reproduced, apart from run metadata.
>
> To generate current outputs, run `bash examples/run_examples.sh OUT` ([docs/quickstart.md](../../docs/quickstart.md)).

Produced by `bash examples/run_examples.sh expected_output` with RNPLens 0.2.0rc2 installed from its wheel, on the
reference platform (Linux x86-64, CPython 3.11.17; DockQ 2.1.3, gemmi 0.6.5, biopython 1.84, numpy 1.26.4,
scipy 1.13.1, matplotlib 3.9.2), from a clone at `/tmp/RNPLens_example_clone`.

| directory / file | example | produced by |
|---|---|---|
| `A_evaluate_7K9D/` (`summary.txt`, `result.json`, `result.csv`) | 1, reference-based | `rnplens evaluate run` |
| `B1_report_contract.json` | 2 | `rnplens example-contract` |
| `B1_report_7K9D/` (`result.json`, `contacts_by_output.json`, `report_7K9D_example.html`) | 2, reference-free agreement | `rnplens report run` |
| `B2_diagnose_validity.json` | 2 | `rnplens diagnose validity` |
| `B2_diagnose_7K9D/` (`report.json`, `report.html`) | 2, validity and disagreement | `rnplens diagnose run` |

**What will differ when you regenerate them.** Absolute paths (your clone location), `created_utc`, `wall_s`, the
platform and Python version records. On another platform, unrounded floating-point values may differ in their
trailing digits: on macOS arm64 the largest difference was 1.4 × 10⁻⁶ Å (an LRMSD), and every rounded value, status,
class, count and label, and the whole of `summary.txt`, were identical. Two runs on one installation give
identical outputs apart from the run time.
