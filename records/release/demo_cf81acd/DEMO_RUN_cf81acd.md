# Demonstration: `tools/release_manifest.py` against cf81acd's existing receipts (16 Oct 2026)

**This is a demonstration, not the release manifest.** The real manifest is produced by the integrator at the final
HEAD, with receipts that state that HEAD. The failures below are the expected result.

**Inputs.**
- Repository: a fresh clone of `dev/0.4-interactive` at `cf81acd9fcf998f50a5975ebe11605c9b657a304` (clean tree), on macOS
  arm64 (conda env `rnplens`, Python 3.11.17, setuptools 84.0.0).
- Receipts: `records/grouping/qualification_v1/code_commit.txt` (whole-file sha), this track's macOS baseline test
  receipt `records/release/demo_cf81acd/test_run_macos_cf81acd.json`, and five prose records whose claimed commits are
  transcribed in `records/release/demo_cf81acd/receipts_index_cf81acd.json` (each entry says where the record states
  the commit).
- Required kinds (`--require-kind`): test_run, clean_install, replay_retest, viewer_verification, live_qualification.
- Tool: `tools/release_manifest.py`, sha256 `7ddca10c5b4593bf71d5c9f06f39ae606104b58ec2bd9e200bd6295ced59019f` (this commit's version).

**Command.**
```
python tools/release_manifest.py --repo <clone at cf81acd> \
  --receipts <clone>/records/grouping/qualification_v1/code_commit.txt records/release/demo_cf81acd/test_run_macos_cf81acd.json \
  --index records/release/demo_cf81acd/receipts_index_cf81acd.json \
  --require-kind test_run --require-kind clean_install --require-kind replay_retest \
  --require-kind viewer_verification --require-kind live_qualification --out <outside the clone>
```

**Output (stdout, verbatim; local paths shortened to `./demo_out`).**
```
release manifest: FAIL (HEAD cf81acd, branch dev/0.4-interactive, tree clean, 7 receipt(s))
  FAIL RECEIPT_COMMIT_MISMATCH: records/grouping/qualification_v1/code_commit.txt: claims 5f1156f, HEAD is cf81acd (39 later commit(s))
  FAIL RECEIPT_COMMIT_MISMATCH: records/v04_integration/V04_IMPLEMENTATION_REPORT.md: claims bdd137f, HEAD is cf81acd (14 later commit(s))
  FAIL RECEIPT_COMMIT_MISMATCH: records/v04_integration/CLEAN_INSTALL_LINUX.md: claims bdd137f, HEAD is cf81acd (14 later commit(s))
  FAIL RECEIPT_COMMIT_MISMATCH: records/v04_integration/DEMOS_REPORT.md: claims bdd137f, HEAD is cf81acd (14 later commit(s))
  FAIL RECEIPT_COMMIT_MISMATCH: assistant/evaluation_v04/FOLLOWUP_SUITE_v1_results/FOLLOWUP_QUALIFICATION_REPORT.md: claims dc9767a, HEAD is cf81acd (20 later commit(s))
  FAIL RECEIPT_COMMIT_MISMATCH: records/grouping/GROUPING_QUALIFICATION_REPORT.md: claims 5f1156f, HEAD is cf81acd (39 later commit(s))
  FAIL REQUIRED_RECEIPT_MISSING: no receipt of kind 'clean_install' points at HEAD
  FAIL REQUIRED_RECEIPT_MISSING: no receipt of kind 'replay_retest' points at HEAD
  FAIL REQUIRED_RECEIPT_MISSING: no receipt of kind 'viewer_verification' points at HEAD
  FAIL REQUIRED_RECEIPT_MISSING: no receipt of kind 'live_qualification' points at HEAD
  non-technical conditions OPEN: institutional_ip, licence, distribution
  wrote ./demo_out/RELEASE_MANIFEST.FAILED.{json,md}
EXIT 1
```

The outputs `RELEASE_MANIFEST.FAILED.json` (sha256 `f82eb8f9a6176d7a90b83ca5253fe153fd01be94edf5050730143f08a55e285c`) and
`RELEASE_MANIFEST.FAILED.md` (sha256 `2b9e2e5706f6a204035d2a9fee37827921a03547eb1357bcd04f6b1d06f484f9`) were saved as session
artifacts, not committed: they hold local absolute paths.

**What the demonstration shows.**
1. Every existing qualification record at cf81acd points at an earlier commit: the test, clean-install and
   demonstration records at `bdd137f` (14 commits earlier), follow-up Part 1 at `dc9767a` (20 earlier), grouping at
   `5f1156f` (39 earlier). Only this track's own macOS baseline receipt points at cf81acd.
2. **The bdd137f receipts do not cover the code at cf81acd.** Between `bdd137f` and `cf81acd`, 41 files changed,
   including `src/rnplens/assist.py` (commit `af1669c`: two follow-up message strings, "Nothing was run." became
   "No follow-up was run."). This is a wording-only change, but it is code in the package, and no recorded test,
   clean-install or demonstration run was made after it.
3. Between `af1669c` and `cf81acd` only one file changed
   (`assistant/evaluation_v04/FOLLOWUP_SUITE_v1_results/FOLLOWUP_QUALIFICATION_REPORT.md`, the integrator's note), a
   documentation-only commit. Within the repository, `af1669c` appears only as the integrator's instruction about
   where to run follow-up Part 2, not as the commit of a recorded test run; a statement elsewhere that af1669c was the
   final tested source checkout has no in-repository receipt that the tool could check.
4. No receipt exists yet for the replay retest, the viewer verification or live qualification.
5. Both packages built from HEAD: `rnplens-0.4.0.dev0` (wheel 123 members, sdist 239; 231 sdist members identical to
   HEAD, 8 generated metadata files) and `rnplens_assistant-0.1.0.dev0` (wheel 29, sdist 47; 40 identical, 7 generated).
   Wheel RECORDs are consistent. Wheel archives were byte-identical across two builds; sdist archives were not (gzip
   time stamp) but their members were, which is why each archive also carries a member digest.
6. The three non-technical conditions (institutional IP, licence, distribution) are OPEN: no approval record was
   supplied.
