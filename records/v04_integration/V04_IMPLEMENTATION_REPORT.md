# RNPLens 0.4 interactive workflow: implementation and validation report (16 Oct 2026, Canberra)

**Branch.** `dev/0.4-interactive` (successor of the frozen assistant commit `f998830`). The final commit is the one
that adds this file (listed in the README of the release package).

**Not changed.** No protected branch, frozen record, sealed task, holdout or manuscript file was changed (see
`PROTECTED_STATE_AFTER`). Nothing was merged or released.

## 1. Commit history (integration branch)

| commit | content |
|---|---|
| `eed6274` | foundation: version 0.4.0.dev0, command table, provenance helpers, capability registry, contracts, Spec B v2 frozen |
| `6c4eabb`, `42a608d`, `23b4391`, `37e7f7a` | merges of the Phase 1 tracks: region & evidence (`bca62a3`), project state (`5ca99a5`), grouping (`f3b6407`), interface (`308b98f`) |
| `74681ec` | integration 1: menu item A; refused results reported as refused; region reuse; viewer command |
| `d0bfff9` | merge of the follow-up track (`615cfd5`) |
| `03a0eab` | integration 2: portable jail with a no-model self-probe; doctor verifies it |
| `5caccec` | integration 3: README, CHANGELOG, docs, contracts v1.1 |
| `bdd137f` | integration 4: fixes for the outside-user and demonstration findings |
| `99c1d29` | merge of the demonstrations track (`d1fe38f`) |
| (this commit) | reports, publication-boundary note and release plan |

## 2. Tests

| where | commit | result |
|---|---|---|
| karyon, Linux, source checkout | `bdd137f` | 547 passed, 0 failed, 12 skipped |
| karyon, clean wheel install (no PYTHONPATH) | `bdd137f` | 547 passed, 0 failed, 12 skipped; selftest PASS; doctor 12 READY; `doctor --agent` 17 READY / 4 ACTION REQUIRED (that venv had no Codex sign-in or tested CLI on PATH) |
| karyon, clean sdist install | `bdd137f` | 547 passed, 0 failed, 12 skipped |
| karyon, install following the docs (`pip install .[html,test]` + `pip install ./assistant`) | `bdd137f` | 547 passed, 0 failed, 12 skipped; local follow-up and its LLM-free replay match |
| macOS arm64, source checkout | `bdd137f` | 541 passed, 1 failed (the known last-digit float difference in an rc3 parity test, Linux-only qualified), 17 skipped |
| karyon, real `rnplens doctor --agent` (account with Codex) | `03a0eab` | 20 READY (Codex CLI 0.159.3, ChatGPT sign-in, gpt-6.1-sol, bubblewrap, jail self-probe) |

The baseline before any 0.4 change was 198 passed, 11 skipped (Linux, `f998830`).

## 3. Capabilities, in four separate categories

### 3a. Qualified software functionality (routes qualified before 0.4, unchanged)
- **Report** (reference-free): contacts, protein and RNA positions in contact, surface and register agreement, RNA
  pose difference. Menu item A runs `rnplens analyse` (Report; Diagnose not run).
- **Evaluate** limited to DockQ, DockQ class, fnat, iRMSD and LRMSD. The four-axis geometry is withheld.
- `rnplens import`, `rnplens analyse` and `rnplens compare` (0.3 workflow, with the Gate-1 fixes).
- The per-structure contact records that the region comparison filters are Report's own. The parity tests show that
  the region output equals a direct filter of those records.

### 3b. New descriptive functionality with completed tests
Each item has unit, regression or parity, malformed-input, determinism, missingness and data-access tests, plus a
worked example and a docs page.
- **Region contact comparison** (`rnplens region`; menu B and C):
  - shared and run-specific contacts, designated structures versus additional samples, provenance;
  - "not observed" is kept distinct from "no contact";
  - for three or more runs there is no two-run formula.
  - Demonstrated on 7K9D, 1VTM, 24BR and 2JEA (RNA 26–35).
- **Evidence queries** (`rnplens explain`; menu D) and the **deterministic Methods export** (`rnplens export-methods`;
  menu F). Every sentence traces to a record field.
- **Clarify and resume, and incremental projects** (`rnplens clarify`, `rnplens update`):
  - typed clarifications; contradictory answers are refused;
  - incremental results equal a fresh recomputation on 7K9D and on development tasks d1, d2 and d4 (6 of 6
    comparisons).
- **Binding-proposal grouping and difference maps** (`rnplens group`, `rnplens group-diff`; menu E), per frozen Spec
  B v2 with Amendments 1–4. The descriptive development-pool qualification is in `records/grouping/`:
  - order invariance held on 0 of 280 targets differing;
  - pool A 80%-subsampling ARI averaged 0.97 at t = 0.5;
  - every candidate was retained in the demonstration (50 of 50).
- **Setup check** (`rnplens doctor`), the **question menu** (`rnplens assist`, A–F, no language model), and the
  **offline Mol* view** (`rnplens view`; Mol* 5.13.1, MIT, vendored). Offline loading and residue selection were
  verified in headless Firefox on karyon.
- **Local follow-up rules** (deterministic, no language model) inside the follow-up feature (see 3c).

### 3c. Experimental functionality requiring further evidence
- **Codex result-aware follow-up**, status EXPERIMENTAL.
  - FOLLOWUP_SUITE_v1 Part 1 (scripted clients) passed 21 of 21 on macOS and on Linux.
  - Part 2 (12 live Codex scenarios) is frozen and **has not been run**, pending your confirmation that automatic
    credit reload is off. It refuses to run between 22 and 24 Oct.
- **Natural-language planner with the new 0.4 tools.** It has not been run live, and it differs from the assistant
  under sealed evaluation (`f998830`).
- **Grouping as an aid to inspection.** In the retrospective pool-A check (50 targets with an acceptable candidate),
  the fraction of fixed-size inspection sets containing at least one acceptable structure was:

  | inspection set | k = 3 | k = 5 | all representatives |
  |---|---|---|---|
  | grouping representatives | 0.84 | 0.86 | 0.96 |
  | random | 0.788 | 0.818 | 0.922 |
  | confidence-ordered | 0.88 | 0.94 | 0.98 |

  So grouping did **not** retain accurate proposals better than engine-confidence order. Its use is for seeing the
  alternatives, not for finding the right one.
- **Mol* pixel rendering.** It needs a manual desktop-browser check; no WebGL was available headless.
- **The assistant on macOS, and jail portability.** The jail was verified for one real account and for a simulated
  other-user home on karyon only.

### 3d. Unsupported or blocked functionality
- **Evaluate four-axis geometry:** blocked by the correspondence defect.
- **Diagnose interpretation:** not re-qualified under the corrected correspondence. It is not offered by the menu,
  and `update` runs Diagnose only with `--with-diagnose`, labelled where shown.
- **RNA conformation difference (Spec B "Q"):** blocked, because it uses the same correspondence route.
- **Candidate ranking or selection of a correct structure:** Rank closed with STOP.
- **New structure prediction, mutation or experiment advice.**
- **Platforms:** Windows; snap-installed Codex inside the jail.
- **Pool B retrospective analysis:** the structures do not match the Rank pool B corpus.

## 4. Findings during integration, and their status

| finding | source | status |
|---|---|---|
| menu reported refused results as success | integrator end-to-end test | fixed (exit 4, result status shown), regression test |
| jail hard-coded `/home/jwen` paths (Codex mode unusable for others) | follow-up track | fixed: portable jail with a self-probe; verified on karyon for the real and a simulated other-user layout |
| assistant install undocumented; local follow-up crashed | outside-user test | fixed: install documented; exit 3 with a hint; Linux docs-method install verified |
| Diagnose statements shown while the menu says interpretation is unavailable | outside-user test | fixed: `update` defaults Diagnose off; a "not re-qualified" note wherever shown |
| cache invalidated by later outputs (D1) | demonstrations | fixed, regression test, reproduction now REUSED |
| scripted client labelled "Codex" (D2); install-location test (D3); SVG legend (D4) | demonstrations | fixed and verified |
| "support", "representative", "shown first" could read as preference | outside-user test | interpretation section added to `docs/interpretation.md` |
| Spec B v2 chaining fixture mathematically impossible | grouping track | Amendment 1, written before any code |
| pool B structures are not the Rank pool B corpus (contacts 16/1,080) | grouping track | relabelled; retrospective not computed; my contracts error |
| managed-project records hold absolute paths and timestamps, so demo-2 replays fail the strict pre-registered byte check (22 of 43 files; post-hoc: only timestamps, IDs and hashes) | demonstrations | **open (O1)**: numerical results equal; byte-level comparability of managed-project records is not achieved |

## 5. What an independent researcher can do now (completion criteria)
Install (Linux or macOS toolkit); import ordinary prediction folders; use everything without an LLM; optionally
enable Codex with their own account (Linux, standalone Codex install); ask about an RNA region; get a traceable
contact comparison; clarify and resume; inspect results and get a deterministic follow-up; add runs and compare
states; inspect binding proposals and their representatives; export a report and a Methods draft; replay the
calculations without an LLM.
- **Not yet shown:** a live Codex follow-up (criterion 8 in Codex mode).
- **Not yet achieved:** byte-identical replay for managed projects (criterion 12 is met numerically, not byte-wise).

## 6. Data access
- No sealed-evaluation target and none of the excluded targets was used. The holdout file was hashed, never opened.
- DockQ labels were read only for the retrospective pool-A analysis, after the grouping code freeze.
- Self-declared slips by the grouping track, none used as input:
  - a listing of three file names and counts in the full-run input folders;
  - chain counts from the 5MSF input YAML.
- No Codex model call was made during 0.4 development. On the real CLI, only `--version`, `login status` and
  `debug models` were run (by `rnplens doctor --agent`). Plan usage was not re-read after 0.4 development began.
