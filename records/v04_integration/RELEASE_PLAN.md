# Proposed release plan for RNPLens 0.4 (proposal only; nothing has been pushed, tagged or released)

**Status (updated 16 Oct 2026 after the owner's decision note).** RNPLens 0.4 **remains a development candidate**.
It is not merged into a protected branch, not tagged, not pushed and not released. **A public GitHub release is NOT
approved.** This plan lists what must be true before a release candidate is even proposed; meeting it does not by
itself authorise a release, which remains the owner's decision. (The previous version of this file, at `af1669c`, is
superseded; its history is in git.)

## Release preconditions (all required)

1. **Replay remediation and independent retest pass.** The byte-identical managed-project replay failed its
   pre-registered check (22 of 43 files differed); that verdict stands and is never relabelled as passed. Release
   needs the deterministic-replay contract to be defined first, the remediation implemented, and an independent
   retest on new development cases to pass under that contract. Receipt kind: `replay_retest`.
2. **Viewer rendering verification.** Manual browser verification of the offline Mol* page, including the **owner's
   on-screen check**: the intended protein and RNA chains, sequence positions, contact highlights and group
   representatives render as intended; the page loads with the network off and makes no unintended external request.
   Until then the documentation claims no working visual interface. Receipt kind: `viewer_verification`.
3. **Live Codex qualification**, only **after the owner confirms that automatic credit reload is off** and accepts
   the residual risk of existing credits being used. Bounded 12-24 calls, starting with one call and checking balance
   and usage before continuing serially; development cases only, never the sealed assistant evaluation; never between
   22 and 24 Oct. No credit purchase or separately billed API call is authorised. Until it passes its frozen criteria,
   the natural-language planner and the follow-up stay EXPERIMENTAL. Receipt kind: `live_qualification`.
4. **All receipts at the release HEAD, verified by the manifest tool.** At the proposed release HEAD (even when its
   last commit is documentation-only), the integrator re-runs and records: the full suite on Linux (`test_run`), the
   clean wheel, sdist and documented installs (`clean_install`), and the receipts of items 1 to 3; then runs
   `tools/release_manifest.py` with `--require-kind` for each, a clean tree, and the package build. The tool fails if
   any receipt names another commit, lacks a commit, or if the tree is dirty. The manifest is kept **outside** the
   release commit (as an attachment), since committing it would change HEAD. Its demonstration at cf81acd
   (`records/release/demo_cf81acd/DEMO_RUN_cf81acd.md`) failed as expected: every existing receipt points at an
   earlier commit, and `src/rnplens/assist.py` changed after the last recorded test run (`af1669c`).
5. **Institutional approvals**, independent of every technical item: institutional (ANU) intellectual-property
   approval, licence approval (MIT) and distribution approval. The manifest lists each as OPEN unless an approval
   record is supplied.
6. **The manuscript boundary.** The frozen assistant evaluation (22-24 Oct) and the manuscript stay unchanged; 0.4 is
   not substituted into the manuscript's application experiment. Whether 0.4 becomes an independent enhanced software
   release is decided after the sealed evaluation.

**Platform scope of a release candidate.** Linux x86-64 is the tested interactive environment. macOS may be claimed
as fully qualified only after the owner adopts a numerical tolerance policy (proposal:
`records/release/MACOS_NUMERICAL_DIFFERENCE.md`, PROPOSAL - NOT ADOPTED) and the macOS suite passes under it in an
environment that satisfies every pin.

## Steps, once every precondition holds and the owner approves

1. **Create the release branch.** `release/0.4.0rc1` from the final `dev/0.4-interactive` commit, after a final
   review. Keep `release/0.2.0rc3` untouched.
2. **Set up CI.** GitHub Actions on Linux x86-64 (3.10, 3.11, 3.12) for the full suite. A macOS arm64 job only under
   an adopted tolerance policy. No Codex in CI; the jail probe test uses a fake binary.
3. **Build artifacts.** A wheel and an sdist for `rnplens`, and for `rnplens-assistant` as a separate optional
   package, from the release HEAD; their checksums and every member's checksum come from the manifest tool. Include
   the Mol* licence notice in `THIRD_PARTY_NOTICES`.
4. **Publish documentation.** README status, installation, `setup_and_privacy`, the menu, interpretation,
   limitations; every `[PLACEHOLDER - ...]` replaced by the tracks' results (search for `PLACEHOLDER`).
5. **Write the release notes** from `docs/capabilities.md` (four categories; each capability in exactly one), not by
   quoting section 3 of `V04_IMPLEMENTATION_REPORT.md`, which lists the local follow-up and the viewer differently.
   State that RNPLens neither predicts structures nor ranks candidates by correctness.
6. **Archive.** A Zenodo DOI for the tagged release (distinct from the manuscript's rc3 archive), only with
   distribution approval.
7. **Check after release.** A fresh outside-user install on Linux (and macOS if qualified) from the published
   artifacts; then the issue tracker.

## Open documentation items for the integrator (code text outside the release-docs track)

See `records/release/DOCS_AUDIT.md` section 4 (C1-C6): the doctor's "Darwin arm64 is a qualified platform", the
`--help` texts for `view`, the geometry route, Diagnose and `--nl`, and optional registry entries.
