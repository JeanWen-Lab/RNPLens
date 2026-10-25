# Publication boundary: the manuscript and frozen evaluation versus RNPLens 0.4 (16 Oct 2026)

1. **Functions in the original qualified toolkit (rc3 `0eeab64`, as the manuscript describes).**
   - Evaluate, Report and Diagnose.
   - The 0.3 workflow (import, analyse, compare) on `dev/0.3.0` `aa037d0`.
   - The bounded RNPLens Assistant at frozen commit `f998830`, which is the subject of the sealed evaluation
     (22–24 Oct).
2. **Newly implemented in 0.4** (`dev/0.4-interactive`; not released):
   - region contact comparison;
   - evidence queries and the Methods export;
   - clarify and resume; incremental projects;
   - binding-proposal grouping and difference maps;
   - the offline Mol* view, setup check and question menu;
   - the EXPERIMENTAL result-aware follow-up;
   - a portable Codex jail.
3. **Scientific analyses unchanged.**
   - Every Evaluate, Report and Diagnose computation.
   - The frozen scorers and the qualified DockQ route.
   - The geometry route stays withheld; Diagnose interpretation stays as in rc3, but the 0.4 menu does not offer it.
   - 0.4 adds filtering, presentation, provenance and orchestration. It adds no new metric.
4. **New functionality with its own qualification (descriptive, development data only).**
   - Region parity with Report's records.
   - Incremental-equals-fresh recomputation.
   - Grouping per frozen Spec B v2: order invariance, subsampling stability, inspection-set properties, and the
     retrospective pool-A coverage, in which grouping did not outperform engine-confidence order.
   - FOLLOWUP_SUITE_v1 Part 1.
   - Clean installs and an outside-user test.
   - **No sealed or holdout data was used.**
5. **Needs further biological validation before any scientific claim:**
   - whether region- or group-level contact differences correspond to experimentally distinguishable binding modes;
   - whether a grouping display helps experts make better decisions, which needs a user study with experts;
   - live Codex follow-up behaviour (Part 2 not run);
   - Diagnose interpretation after its re-qualification.
6. **Possible future publication.**
   - A software or application note on interactive, evidence-linked inspection of predicted protein–RNA complexes
     (region comparison, provenance-tracked Methods export, incremental projects, grouping as a display of
     alternatives). It would include an outside-user study and, ideally, an expert user study.
   - **Nothing from 0.4 should be claimed in the current manuscript.** Its claims must rest on rc3 and the
     sealed-evaluated assistant `f998830`. The manuscript was not modified.
