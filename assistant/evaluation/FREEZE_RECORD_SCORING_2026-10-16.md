# Freeze record: sealed set, runner, scorer and aggregator (16 October 2026, Canberra)

**Frozen at commit:** `5173e4b` (branch `gate1/assistant-companion`). This is before any sealed trial.

**No further changes.** The files below do not change before or during the sealed evaluation. A defect found later
is reported as a defect; it is not fixed in place.

## Sealed set (built once, 16 Oct 2026, on karyon)
- Location: `RNPLens_dev_0.3/assistant_2026-10-16/eval/sealed` (read-only).
- `SEALED_MANIFEST.json` sha256: `330c9d28d63be78b6b0ad2fc2c14b87a8f664a176a421b3afc8546a1cc57edcf`.
- Contents: 37 task folders (36 counted plus the uncounted regression task R6DCB), 37 keys and 706 manifest files.
- Pool: the 58 stress-pair targets left after Amendment 2. 56 are eligible; 4C9D and 4I67 are ineligible because
  their unmodified predictions do not import.
- Reference-workflow command failures: 0.
- Key values have not been inspected.

## File hashes (sha256)

| file | sha256 |
|---|---|
| evaluation/score.py | 6d22fcd61f257555a0966a9f87d47b8f0e2c88cc9af7cb27d8acac6a95a2ed5c |
| evaluation/aggregate.py | 804ec0bfa2974655b7b13e6ad769636b591fc16825c6fb2059a167c5ffb770f3 |
| evaluation/run_eval.py | f82716778392c6699b5b8d0064edc8e2b51f3ed7ac8dab0b87713e05cb819f85 |
| evaluation/replay_all.py | cd79a14e630241f8c2739d8661f76d41ecef6fc77063313957953fd0ce3aeaa8 |
| evaluation/build_sealed.py | 2a6d937f03616afaa41434a8f7b2eb0b2f452ffa1a219462213bd529f9c65630 |
| evaluation/EVAL_PROTOCOL_v2.md | 16a37571c1cb8cd4e5fc8f2c9e9b8284228dc1503e6cf278ba496acd22a2eee6 |
| evaluation/FREEZE_RECORD_PROTOCOL_v2.md | f9618aa6957dfcec9cc3e631fc138396f061efbed9cfebbc2249cfe0fe9e4765 |
| evaluation/AMENDMENT_1_2026-10-16.md | 5d61069d7acdc14bd012413c96269978c98ec9321f810f79664581255c1142bb |
| evaluation/AMENDMENT_2_2026-10-16.md | 983dae884f2dd287d729746ccc241ce4096e7e6d43a362d330bfa1b1f00ac80b |
| evaluation/AMENDMENT_3_2026-10-16.md | 936140044d90ba9698246f765bd1228661a73c5683467e793e000f50d431e998 |
| evaluation/task_templates.json | 236d6994e2917da2c6c683b7ab860a9b1eefe334c3ff4af70d904af07452d633 |
| evaluation/PLAN_SCHEMA_v1.json | b12cd0919bd8997c3c38e10f3b16f0b6b6daece28e5dc4ad473390fc1c1cf227 |
| evaluation/COMPARATOR_ENVELOPE_SCHEMA_v1.json | facdaaa3e10e0fada4601b40e0112abdd16f4ce02e69cdbaa6148d6274aefa1f |
| codex_adapter/codex_jail.sh | bceb8afb68abc2eb23356d7e14fcd76f631a340035d32e44187c16d919da7149 |
| rnplens_assistant/prompts/planner.md | b4268779d16da6eda13b3c0e712eebcc9e91924313a5509e139445c8f10e77ff |

The local and karyon copies of the evaluation files were confirmed identical. All other code is fixed by the commit
hash.

## Fixed parameters
- Model: `gpt-6.1-sol` at reasoning effort `medium`.
- Codex model catalog sha256: `aad73e9b…d763f`. The runner refuses to start if the catalog has changed.
- Trial-order seed: 20261022.
- Bootstrap seed: 20261023, with 10,000 resamples.
- Usage guard: 85% on both plan windows, plus a projection to completion.
- Credits: the run stops on any change from the recorded baseline (62,500).

## Inclusion interlock (aggregate.py)
`inclusion` is true only if all of the following hold:
1. the set is not a development set;
2. `RUN_COMPLETE.json` is present;
3. every trial is scored;
4. R mean completion on actionable tasks is at least 0.90;
5. R has zero critical errors;
6. every number in correct R answers is traceable;
7. every R replay matches, against the same sealed manifest;
8. `INSTALL_TEST.json` passed.
