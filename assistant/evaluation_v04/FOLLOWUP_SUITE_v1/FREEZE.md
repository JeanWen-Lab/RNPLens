# FREEZE: FOLLOWUP_SUITE_v1

Frozen 2026-10-16T12:04 UTC (2026-10-16 23:04 AEDT, Canberra), on branch track/followup, base 74681ec, before any scenario of this suite was run.

**State at freeze.**
- No Part 1 scenario has run, and Part 2 has not run.
- No unit test of the follow-up exists yet.
- No Codex or language-model call has been made by this track.
- The follow-up module was smoke-tested by hand on the bundled 7K9D example: local follow-up, scripted-stub Codex path, no-consent path and replay.

**Pre-freeze premise checks.** These changed the definition before the freeze. They are recorded here because they were informed by inspecting tool outputs, not suite results.
1. explain outputs carry recorded limitations as statements, and refusal records that name ranking. The C4 exemption was therefore aligned with the assistant's gate convention: question, Limitation and Not-available lines are exempt.
2. explain provenance texts carry absolute paths. This is handled in the module (hash normalisation), not in the suite.

run_part1.py refuses to run if any hash below differs.

**Amendment 1** (frozen 2026-10-16, after Part 1 run 1 and before run 2). See AMENDMENT_1.md. It makes the --out path of run_part1.py absolute; no expectation changed. The hashes below are the post-amendment hashes. The original hash of run_part1.py was 0f6a3bf43b9085435a911f1dccbd6cea4640c880aad15488cab339b5f187fc22, and all other files are unchanged.

| file | sha256 |
|---|---|
| `AMENDMENT_1.md` | `2ef18120ffe6ae4dbab9e4abc63e9be09a3d1d45e6c9be8f1220d0a14a9e1002` |
| `SUITE.md` | `d05a442cf63ac376c78ca0b3a6fca6aef1c7e39991883ef660b4bfea48ab2123` |
| `fake_client.py` | `970be59e9118ec680f28a9276498dccd54a75764dc0cfccffaf99df98d6c9cdb` |
| `run_part1.py` | `2336a0b485c6e036878c0a44ef5e9f2f2cb23789392aeb029a4d59cd8dea9f4c` |
| `run_part2.py` | `0b78851c5d64353f3d77336baa141a1d93afbde41e6d4ec0d26ada84674f11b7` |
| `scenarios_part1.json` | `068d1106acf2bada7f65557372972cd3ca516c07d690b138ddfb75e7b73b58fd` |
| `scenarios_part2.json` | `67663eb11538d44a725c45eece6ffadef63bf7f712652fe21e611af0fe057237` |
| `score.py` | `412bc3f5c330299b41a95d8ceb031a8832b7baebc83eeea0398c3b931c57d257` |
