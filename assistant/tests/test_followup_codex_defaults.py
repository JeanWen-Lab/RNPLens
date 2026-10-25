"""0.4 fix: the Codex adapter defaults point at this installation's jail and a per-user calls folder, never into the
frozen evaluation (RNPLens_dev_0.3) or its shared calls folder."""
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSISTANT = os.path.dirname(HERE)
ROOT = os.path.dirname(ASSISTANT)


def _defaults(env_extra=None):
    env = {k: v for k, v in os.environ.items() if k not in ("RNPLENS_CODEX_JAIL", "RNPLENS_CODEX_CALLS")}
    env.update(env_extra or {})
    code = "import json; from rnplens_assistant import codex_llm as c; print(json.dumps([c.JAIL, c.CALLS_ROOT, c.default_jail()]))"
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=60)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout.strip().splitlines()[-1])


def test_defaults_never_point_into_the_frozen_evaluation():
    jail, calls, dj = _defaults()
    for p in (jail, calls, dj):
        assert "RNPLens_dev_0.3" not in p and "assistant_2026-10-16" not in p
    assert os.path.realpath(calls) != "/home/jwen/projects/RNPBench/scratch_agent/codex_calls"
    assert calls == os.path.join(os.path.expanduser("~"), ".rnplens", "codex_calls")
    import rnplens_assistant
    pkg = os.path.dirname(os.path.realpath(rnplens_assistant.__file__))     # source checkout or installed site-packages
    assert os.path.isfile(jail) and (os.path.realpath(jail).startswith(pkg + os.sep)
                                     or os.path.realpath(jail).startswith(os.path.realpath(ASSISTANT) + os.sep))


def test_overrides_and_packaged_jail_is_identical_to_the_source_copy(tmp_path):
    # RNPLENS_CODEX_CALLS still overrides; RNPLENS_CODEX_JAIL never selects the jail (launch boundary, 0.4)
    jail, calls, dj = _defaults({"RNPLENS_CODEX_CALLS": str(tmp_path / "c"), "RNPLENS_CODEX_JAIL": str(tmp_path / "j.sh")})
    assert calls == str(tmp_path / "c") and jail == dj and jail != str(tmp_path / "j.sh")
    a = open(os.path.join(ASSISTANT, "codex_adapter", "codex_jail.sh"), "rb").read()
    b = open(os.path.join(ASSISTANT, "rnplens_assistant", "codex_adapter", "codex_jail.sh"), "rb").read()
    assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()
    assert "codex_adapter/*.sh" in open(os.path.join(ASSISTANT, "pyproject.toml")).read()
    assert os.access(os.path.join(ASSISTANT, "rnplens_assistant", "codex_adapter", "codex_jail.sh"), os.X_OK)


def test_weekly_guard_is_optional_and_stops(tmp_path, monkeypatch):
    from rnplens_assistant import codex_llm
    monkeypatch.setattr(codex_llm, "CALLS_ROOT", str(tmp_path))
    c = codex_llm.CodexClient("t", config={"weekly_guard_percent": 10.0})
    c.last_limits = {"primary": {"used_percent": 1, "window_minutes": 300}, "secondary": {"used_percent": 12.0, "window_minutes": 10080},
                     "credits": {"balance": "0"}}
    import pytest
    with pytest.raises(codex_llm.UsageGuard, match="weekly"):
        c._guard()
    c2 = codex_llm.CodexClient("t2")
    c2.last_limits = dict(c.last_limits)
    c2._guard()                                         # default config: no weekly guard below 85 %
