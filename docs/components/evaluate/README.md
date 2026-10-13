# rnpbench-evaluate 0.2.0.dev1 (toolkit candidate; not released)

This is the toolkit build of RNPBench Evaluate, with the frozen sources and loader now supplied by `rnpbench-core`. **The qualified release remains 0.1.1** (`software/rnpbench-evaluate/`). Within the toolkit, the standalone command is `rnpbench-evaluate`, and the unified command is `rnpbench evaluate run|validate|selftest|provenance`, from the meta-package `rnpbench`.

`rnpbench evaluate` scores a predicted protein–RNA complex against an experimental structure with the **frozen RNPBench evaluation rules**:
- designated-output reporting convention;
- polymer-class admissible chain mappings;
- construct-position residue correspondence;
- DockQ 2.1.3;
- the four-axis RNA/protein geometry;
- explicit no-value states.

The scientific code is not reimplemented. The eight frozen source files are vendored byte-for-byte, pinned by SHA-256 in `rnpbench_evaluate/frozen/FROZEN_SOURCES.json`, and their scoring functions are executed unmodified (`rnpbench provenance --full`).

- Qualification and readiness: `PUBLIC_RELEASE_READINESS_REPORT.md`
- Tutorial: `docs/TUTORIAL.md`
- Input contract: `docs/INPUT_CONTRACT.md`
- Worked example: `examples/`
- Tests: `rnpbench selftest --profile portable|reference` and `pytest` (see `docs/PORTABLE_QUALIFICATION_CONTRACT.md`)
- Scope: one user-supplied prediction at a time; no structure prediction; no automatic choice of a designated output; separate frozen DockQ and geometry routes; NO VALUE is never zero

**Status:** qualification build for review. It is not released, published or archived. The owners' preferred licence for original RNPBench code is BSD-3-Clause, subject to ANU IP clearance; no licence is declared until then (see `docs/DEPENDENCY_AND_LICENCE_ASSESSMENT.md`).
