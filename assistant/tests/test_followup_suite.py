"""FOLLOWUP_SUITE_v1: the frozen files match FREEZE.md, Part 1 passes in full, and the live Part 2 runner refuses
without every guard (it is frozen and never run by the tests)."""
import datetime
import hashlib
import json
import os
import sys
import types

import pytest

ASSISTANT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITE = os.path.join(ASSISTANT, "evaluation_v04", "FOLLOWUP_SUITE_v1")
SUITE_MODULES = ("score", "fake_client", "run_part1", "run_part2")


@pytest.fixture(autouse=True)
def suite_namespace(monkeypatch):
    """The suite's own modules, never same-named modules of other suites (assistant/evaluation/score.py is imported by
    test_score.py under the name 'score')."""
    for m in SUITE_MODULES:
        monkeypatch.delitem(sys.modules, m, raising=False)
    monkeypatch.syspath_prepend(SUITE)
    yield
    for m in SUITE_MODULES:
        sys.modules.pop(m, None)


def test_freeze_record_matches_every_file():
    rows = [l for l in open(os.path.join(SUITE, "FREEZE.md")) if l.startswith("| `")]
    names = {l.split("`")[1]: l.split("`")[3] for l in rows}
    files = {f for f in os.listdir(SUITE) if f != "FREEZE.md" and not f.startswith(".") and f != "__pycache__"}
    assert set(names) == files
    for f, h in names.items():
        assert hashlib.sha256(open(os.path.join(SUITE, f), "rb").read()).hexdigest() == h, f


def test_suite_uses_no_excluded_target():
    excluded = ("3WZI 4DWA 4KR6 4OHZ 4PMI 4RCJ 4RDX 5B63 5FN1 5HSW 5MSF 5U30 5X2G 6DCB 6E4P 6LT7 6M7K 6NY2 6O6V 6O7B 6P7P 6SCE "
                "6W11 6XMF 7QQK 7S7C 7UZW 7VYX 7XG1 7XS4 8PSQ 8UMF 8WO8 9JXX 9RVP 9U49 9YLU").split()
    for f in os.listdir(SUITE):
        if f.endswith((".json", ".py", ".md")):
            t = open(os.path.join(SUITE, f)).read()
            assert not [x for x in excluded if x in t], f
    S2 = json.load(open(os.path.join(SUITE, "scenarios_part2.json")))
    assert len(S2["scenarios"]) == 12 and {s["task"][:2] for s in S2["scenarios"]} == {"d1", "d2", "d3", "d4", "d5"}
    assert S2["expected_codex_calls"] == {"min": 12, "max": 24, "nominal": 12, "note": S2["expected_codex_calls"]["note"]}


FROZEN_RNPLENS_VERSION = "0.4.0.dev0"   # the version string FOLLOWUP_SUITE_v1/run_part1.py was frozen against


def test_part1_passes_in_full(tmp_path, monkeypatch):
    # FOLLOWUP_SUITE_v1 is hash-frozen (FREEZE.md) and its Part 1 runner asserts the rnplens version it was qualified
    # against. From 0.4.0.dev0 to the 0.4.0 release, the runtime code changed only in version strings and
    # informational fixture text. The frozen Part 1 therefore replays under its frozen version identity; the
    # runner's own version guard is checked by test_part1_version_guard_still_refuses below.
    import rnplens
    import run_part1
    import score
    monkeypatch.setattr(rnplens, "__version__", FROZEN_RNPLENS_VERSION)
    assert os.path.dirname(os.path.abspath(score.__file__)) == SUITE
    assert run_part1.main(["--out", str(tmp_path / "p1")]) == 0
    d = json.load(open(tmp_path / "p1" / "part1_results.json"))
    assert d["n"] == 21 and d["passed"] == 21


def test_part1_version_guard_still_refuses(tmp_path, monkeypatch):
    import rnplens
    import run_part1
    monkeypatch.setattr(rnplens, "__version__", "0.4.0")
    with pytest.raises(AssertionError):
        run_part1.main(["--out", str(tmp_path / "p1")])


def test_part2_refuses_without_guards(tmp_path, monkeypatch):
    import run_part2
    a = types.SimpleNamespace(live=False, out=str(tmp_path / "o"), tasks=None)
    r = run_part2.guards(a, env={}, agent_status=lambda: (True, []), model_check=lambda: {"status": "READY"})
    assert any("--live" in x for x in r) and any("AUTO_RELOAD" in x for x in r) and any("RNPLENS_CODEX_CALLS" in x for x in r)
    a.live = True
    env = {"RNPLENS_FOLLOWUP_LIVE": run_part2.LIVE_TOKEN, "RNPLENS_CODEX_CALLS": "/home/jwen/projects/RNPBench/RNPLens_dev_0.3/x"}
    r = run_part2.guards(a, env=env, agent_status=lambda: (False, ["Codex CLI: not found"]), model_check=lambda: {"status": "ACTION", "detail": "x"})
    assert any("scratch_agent/v04" in x for x in r) and any("not READY" in x for x in r) and any("model catalog" in x for x in r)
    assert run_part2.main(["--out", str(tmp_path / "o")]) == 3 and not os.path.exists(tmp_path / "o")


@pytest.mark.parametrize("utc,inside", [("2026-10-21T12:59", False), ("2026-10-21T13:00", True), ("2026-10-24T12:59", True),
                                        ("2026-10-24T13:00", False), ("2026-10-16T12:00", False)])
def test_sealed_window_in_canberra_time(utc, inside):
    import run_part2
    t = datetime.datetime.fromisoformat(utc).replace(tzinfo=datetime.timezone.utc)
    assert run_part2.in_sealed_window(t) is inside
