"""Launch boundary of the language-model process (0.4 release audit, finding O1/O2).

Every model call is started by codex_llm.CodexClient.run. The confinement backend is the jail shipped with this
installation; it cannot be chosen from the environment, and the jail process receives only HOME, CODEX_HOME,
RNPLENS_CODEX_BIN and PATH=/usr/bin:/bin. These tests use stand-in scripts that only write marker files: no jail, no
Codex, no model call, no credential file."""
import ast
import json
import os
import subprocess

import pytest

from rnplens_assistant import codex_llm

PKG = os.path.dirname(os.path.abspath(codex_llm.__file__))


def _standin(path, marker):
    """A script that, if ever started, records that it ran and the environment it received."""
    path.write_text("#!/bin/bash\n/usr/bin/env > %s\nprintf '{}' > \"$1/last.json\"\n" % marker)
    os.chmod(path, 0o755)
    return str(path)


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(codex_llm, "CALLS_ROOT", str(tmp_path / "calls"))
    os.makedirs(str(tmp_path / "calls"), exist_ok=True)


def test_environment_override_is_refused_before_anything_is_created(monkeypatch, tmp_path):
    _client(monkeypatch, tmp_path)
    marker = tmp_path / "RAN"
    monkeypatch.setenv("RNPLENS_CODEX_JAIL", _standin(tmp_path / "standin.sh", marker))
    with pytest.raises(codex_llm.JailRefused, match="unset RNPLENS_CODEX_JAIL"):
        codex_llm.CodexClient("t")
    assert os.listdir(str(tmp_path / "calls")) == [] and not marker.exists()


def test_override_set_after_construction_is_refused_at_the_call(monkeypatch, tmp_path):
    _client(monkeypatch, tmp_path)
    monkeypatch.delenv("RNPLENS_CODEX_JAIL", raising=False)
    c = codex_llm.CodexClient("t")
    marker = tmp_path / "RAN"
    monkeypatch.setenv("RNPLENS_CODEX_JAIL", _standin(tmp_path / "standin.sh", marker))
    monkeypatch.setattr(codex_llm.subprocess, "run", lambda *a, **k: pytest.fail("a process was started"))
    with pytest.raises(codex_llm.JailRefused):
        c.run("plan", "PROMPT", {"type": "object"})
    assert c.calls == [] and not marker.exists()


def test_override_naming_the_shipped_jail_is_accepted(monkeypatch, tmp_path):
    _client(monkeypatch, tmp_path)
    monkeypatch.setenv("RNPLENS_CODEX_JAIL", codex_llm.APPROVED_JAIL)
    codex_llm.CodexClient("t")
    assert codex_llm.JAIL == codex_llm.APPROVED_JAIL == codex_llm.default_jail()


def test_missing_jail_is_refused(monkeypatch, tmp_path):
    _client(monkeypatch, tmp_path)
    monkeypatch.delenv("RNPLENS_CODEX_JAIL", raising=False)
    monkeypatch.setattr(codex_llm, "JAIL", str(tmp_path / "absent.sh"))
    monkeypatch.setattr(codex_llm.subprocess, "run", lambda *a, **k: pytest.fail("a process was started"))
    with pytest.raises(codex_llm.JailRefused, match="does not exist"):
        codex_llm.CodexClient("t").run("plan", "PROMPT", {"type": "object"})


def test_jail_environment_is_minimal():
    e = codex_llm.jail_environ({"HOME": "/h", "CODEX_HOME": "/h/.codex", "RNPLENS_CODEX_BIN": "/opt/codex",
                                "PATH": "/tmp/planted:/usr/bin", "BASH_ENV": "/tmp/x.sh", "ENV": "/tmp/x.sh",
                                "BASH_FUNC_realpath%%": "() { :; }", "LD_PRELOAD": "/tmp/x.so", "DYLD_INSERT_LIBRARIES": "x",
                                "OPENAI_API_KEY": "sk-x", "CODEX_API_KEY": "x", "RNPLENS_JAIL_TEST": "1",
                                "RNPLENS_JAIL_PROBE": "1", "RNPLENS_CODEX_JAIL": "/tmp/j.sh"})
    assert e == {"HOME": "/h", "CODEX_HOME": "/h/.codex", "RNPLENS_CODEX_BIN": "/opt/codex", "PATH": "/usr/bin:/bin"}


def test_the_jail_process_receives_only_the_minimal_environment(monkeypatch, tmp_path):
    """A real process start through CodexClient.run, with a stand-in in place of the shipped jail (set in code, as the
    test suite does; the environment cannot do this). Caller variables that could run code before or instead of the jail
    (BASH_ENV, exported shell functions, a planted PATH entry) never reach it."""
    _client(monkeypatch, tmp_path)
    monkeypatch.delenv("RNPLENS_CODEX_JAIL", raising=False)
    planted = tmp_path / "planted"; planted.mkdir()
    sourced = tmp_path / "BASH_ENV_SOURCED"
    (tmp_path / "bash_env.sh").write_text("touch %s\n" % sourced)
    (planted / "bwrap").write_text("#!/bin/sh\ntouch %s\n" % (tmp_path / "PLANTED_RAN")); os.chmod(planted / "bwrap", 0o755)
    monkeypatch.setenv("BASH_ENV", str(tmp_path / "bash_env.sh"))
    monkeypatch.setenv("BASH_FUNC_printf%%", "() { touch %s; }" % (tmp_path / "FUNCTION_RAN"))
    monkeypatch.setenv("PATH", str(planted) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-key")
    marker = tmp_path / "ENV_SEEN"
    standin = _standin(tmp_path / "standin.sh", marker)
    monkeypatch.setattr(codex_llm, "JAIL", standin)              # the stand-in plays the shipped jail
    monkeypatch.setattr(codex_llm, "APPROVED_JAIL", standin)
    c = codex_llm.CodexClient("t"); c.credits0 = None
    assert c.run("plan", "PROMPT", {"type": "object"}) == {}
    seen = dict(l.split("=", 1) for l in marker.read_text().splitlines() if "=" in l and not l.startswith("_="))
    for k in ("PWD", "SHLVL", "OLDPWD"):          # set by bash itself
        seen.pop(k, None)
    assert seen["PATH"] == "/usr/bin:/bin" and set(seen) <= {"HOME", "CODEX_HOME", "RNPLENS_CODEX_BIN", "PATH"}
    assert not sourced.exists() and not (tmp_path / "FUNCTION_RAN").exists() and not (tmp_path / "PLANTED_RAN").exists()


def test_a_jail_substituted_in_code_keeps_the_caller_environment(monkeypatch, tmp_path):
    """Test harnesses (and the frozen FOLLOWUP_SUITE_v1) replace codex_llm.JAIL in code and script their fake Codex
    through environment variables; only the shipped jail gets the minimal environment."""
    _client(monkeypatch, tmp_path)
    monkeypatch.delenv("RNPLENS_CODEX_JAIL", raising=False)
    monkeypatch.setenv("FAKE_CODEX_MODE", "ok")
    marker = tmp_path / "ENV_SEEN"
    monkeypatch.setattr(codex_llm, "JAIL", _standin(tmp_path / "standin.sh", marker))
    c = codex_llm.CodexClient("t"); c.credits0 = None
    c.run("plan", "PROMPT", {"type": "object"})
    assert "FAKE_CODEX_MODE=ok" in marker.read_text()


def test_only_codex_llm_starts_the_jail():
    """No shipped module other than codex_llm.py starts a process with the jail, and CodexClient.run passes the
    minimal environment."""
    src = open(os.path.join(PKG, "codex_llm.py")).read()
    assert "env=jail_environ() if os.path.realpath(JAIL) == os.path.realpath(APPROVED_JAIL)" in src
    assert src.count("subprocess.run(") == 1
    for root, _, files in os.walk(PKG):
        for f in files:
            if f.endswith(".py") and f not in ("codex_llm.py", "confine.py"):   # confine.py only names the scripts
                t = open(os.path.join(root, f)).read()
                assert not any(s in t for s in ("JAIL", "codex_jail", "codex_seatbelt")), f
