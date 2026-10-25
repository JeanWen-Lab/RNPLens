# Code freeze: grouping (Function 6) and its qualification scripts

- **Written:** 16 Oct 2026, before any DockQ label file was opened. Neither `nscale_sample_dockq.tsv` nor
  `rank_corpus.tsv` (nor any other accuracy record, nor any RNPLens-Rank feature table) has been opened, listed by
  content, or read in any way, including its header.
- **Frozen code commit:** `5f1156f8938f197be6cf33329eb1ebdf7975cf3e` (branch `track/grouping`).
- **What already ran with this commit (reference-free only):** the section 5 reference-free qualification on
  pools A (64) and B (216) and the contacts parity check, on karyon, output
  `RNPLens_dev_0.4/work/grouping/qual_v1/` (code_commit.txt = the commit above).
- **Next, and only after this file is committed:** `qualification_v04/grouping/coverage.py` reads the two label
  files read-only. No parameter, threshold, rule or script is changed after that; any change would need a dated
  amendment stating that labels had been seen.

| file | sha256 |
|---|---|
| `src/rnplens/grouping.py` | `cd62f3b23c5a70073605855489d9f70add5376d93b50d60d77bbd855a6e40b62` |
| `qualification_v04/grouping/qualify.py` | `3ab1f6022ec5d1728138de3a099393921d694d85f59d63be034ef92a8a1c94c0` |
| `qualification_v04/grouping/coverage.py` | `e5fd78cda216ddd7699cbb92ab665a6006978d0fcc756cf957d643348b397819` |
| `qualification_v04/grouping/contacts_parity.py` | `b0871c760fac21533042116710e9d961b686d23b997c4c9f0b653e9ff5fed830` |
| `qualification_v04/grouping/run_reference_free.sh` | `f9696412fab55b694ab356fd590a89ee8abf9482d233b6859cec45eed93180a7` |
| `qualification_v04/grouping/run_coverage.sh` | `308dcbe2b37657be09bdf07d043602cd090118380adadbae6472fa50ae5ceae2` |
| `tests/test_grouping.py` | `e6e50ef97f5a04ccf5ca2f8c66d309022d2fb03d6f062ead9dbc882465081ac7` |
| `tests/test_grouping_karyon.py` | `314e075823d3ee728417dafd874522b89889f4912eff4538796e02b15c088d38` |
| `tests/fixtures_v04/grouping/synth.py` | `47eb34cb6cd20072d754fbeabe8e0c68e7078da25b10f087f1dca5574d2fb469` |
| `docs/dev/specs/SPEC_B_HYPOTHESIS_GROUPING_v2.md` | `1c304fc154aecf3c5cd03c92ed6b59787213d0414ee9f08bf634de10d25fb38d` |
| `records/grouping/SPEC_B_v2_AMENDMENT_1.md` | `24b6c8da98298035ae1e89031ca6d114fa51db88428801a9c71d4a7b3f4fc33d` |
| `records/grouping/SPEC_B_v2_AMENDMENT_2.md` | `b886a52626282ea6426cf1bd902153cfabdbc6a0a1b268b1daf1874b635ef1b9` |
| `records/grouping/SPEC_B_v2_AMENDMENT_3.md` | `df9424bafe1da49931b3c76870750557b02845190ad3c7a100b97ee85420b7ed` |

Frozen parameters (all from Spec B v2 or Amendments 1-3, none chosen from data): thresholds 0.3/0.5/0.7 (primary
0.5); average linkage, exact rational; canonical key (sha256, id); frequent cut 1/2; seed 20261016; 5 permutations;
20 subsets of floor(0.8 n); k in {3, 5, all representatives}; 200 random draws; acceptable DockQ >= 0.23; within 0.05.
