# Release manifest verifier (`tools/release_manifest.py`; development tool)

The tool checks that every qualification receipt points at the proposed release HEAD and writes
`RELEASE_MANIFEST.json` and `RELEASE_MANIFEST.md`: HEAD, branch, clean-tree status, each receipt's SHA-256 and claimed
commit, a wheel and an sdist of each package built from HEAD (`git archive`) in a temporary directory with every
member's SHA-256, and the non-technical release conditions.

```
python tools/release_manifest.py --repo . --receipts RECEIPTS_DIR [--index INDEX.json] \
    --require-kind test_run --require-kind clean_install --require-kind replay_retest \
    --require-kind viewer_verification --require-kind live_qualification \
    [--approval APPROVAL.json ...] --out OUTSIDE_THE_REPOSITORY
```

**A receipt states one commit**: a JSON key (`receipt_commit`, `commit`, `recorded_commit`, ...), a Markdown line
`Receipt-Commit: <sha>`, a file holding only a sha, or an entry in an index that transcribes the claim of an older
prose record. JSON receipts name their kind in `"receipt"`.

**It fails (exit 1, files named `RELEASE_MANIFEST.FAILED.*`)** when the tree is dirty (tracked or untracked
changes), when no receipt is given, when a receipt states no commit, several commits or a commit other than HEAD
(it then lists how many commits and which files changed since), when a required kind is missing, or when a package
build fails or is skipped. Input errors exit 2 and write nothing; existing manifests are never overwritten.

**Conditions.** Institutional IP, licence and distribution approval are always listed, as OPEN unless an approval
record is supplied; `--require-approvals` turns an OPEN condition into exit 3.

## Interpretation limits
- A passing run shows only that the receipts name HEAD, the tree is clean and the packages were built from HEAD. It
  does not read or check what the receipts report, and it cannot confirm that an approval record is authentic.
- Without `--require-kind`, the tool does not know which receipts a release needs.
- sdist archives are not byte-reproducible (gzip time stamp); compare their member digest instead.
- Keep the manifest outside the release commit: committing it changes HEAD.
