"""0.4 native platforms: the Linux bubblewrap jail (codex_jail.sh, unchanged), tested for real (no model call), with the
same scenarios as the macOS tests where they apply. /usr/bin/bash stands in for the Codex binary (RNPLENS_CODEX_BIN).
Skipped where bubblewrap cannot run, unless RNPLENS_REQUIRE_BWRAP=1 (the qualification script) turns that into a failure.
Differences from macOS (documented in docs/platforms.md): the jail shares the host network (internet, loopback), and
programs under /usr may be started, but every process sees only the jail's private filesystem."""
import os
import platform
import shutil
import subprocess

import pytest

from rnplens_assistant import codex_llm

PKG = os.path.dirname(os.path.realpath(codex_llm.__file__))
JAIL = os.path.join(PKG, "codex_adapter", "codex_jail.sh")


def _usable():
    b = shutil.which("bwrap")
    return platform.system() == "Linux" and b and subprocess.run([b, "--ro-bind", "/", "/", "true"], capture_output=True).returncode == 0


if not _usable():
    if os.environ.get("RNPLENS_REQUIRE_BWRAP") == "1":
        raise RuntimeError("RNPLENS_REQUIRE_BWRAP=1 but bubblewrap cannot run here")
    pytestmark = pytest.mark.skip(reason="bubblewrap with unprivileged user namespaces not available here")


@pytest.fixture
def jail(tmp_path):
    home = tmp_path / "home"; (home / ".codex").mkdir(parents=True)
    (home / ".codex" / "auth.json").write_text('{"fake": "login"}\n')
    for n in ("config.toml", "history.jsonl", "AGENTS.md"):
        (home / ".codex" / n).write_text("SECRET-%s\n" % n)
    (home / ".ssh").mkdir(); (home / ".ssh" / "id_ed25519").write_text("SECRET-KEY\n")
    (home / "research").mkdir(); (home / "research" / "reference.cif").write_text("SECRET-REFERENCE\n")
    (home / "answers.json").write_text("SECRET-ANSWER\n")
    calls = home / ".rnplens" / "codex_calls"
    (calls / "other").mkdir(parents=True); (calls / "other" / "plan.json").write_text("SECRET-OTHER-CALL\n")
    call = calls / "c1"; call.mkdir()

    def run(script):
        env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "RNPLENS_CODEX_BIN": "/usr/bin/bash",
               "OPENAI_API_KEY": "sk-test-must-not-pass", "CODEX_API_KEY": "x"}
        return subprocess.run(["bash", JAIL, str(call), "--", "-c", script], env=env, capture_output=True, text=True, timeout=60)
    return {"home": home, "call": call, "calls": calls, "run": run}


def test_self_probe_passes(jail):
    r = subprocess.run(["bash", JAIL, str(jail["call"]), "--"], env={"HOME": str(jail["home"]), "PATH": "/usr/bin:/bin",
                       "RNPLENS_CODEX_BIN": "/usr/bin/bash", "RNPLENS_JAIL_PROBE": "1", "RNPLENS_JAIL_PROBE_HIDDEN": str(jail["home"] / "research")},
                       capture_output=True, text=True)
    assert r.returncode == 0 and "JAIL_OK" in r.stdout, r.stderr


@pytest.mark.parametrize("rel", ["answers.json", "research/reference.cif", ".ssh/id_ed25519", ".codex/config.toml",
                                 ".codex/history.jsonl", ".codex/AGENTS.md", ".rnplens/codex_calls/other/plan.json"])
def test_private_files_absent_also_for_subprocesses(jail, rel):
    p = jail["home"] / rel
    r = jail["run"]('IFS= read -r l < "%s" && echo "$l"; /usr/bin/cat "%s" 2>/dev/null; /usr/bin/ls -a "%s" 2>/dev/null' % (p, p, p.parent))
    assert "SECRET" not in r.stdout


def test_only_the_call_folder_is_writable_and_host_unchanged(jail):
    r = jail["run"]('echo hi > /work/out.txt && echo x > "%s/new.txt"; echo x > /tmp/t; echo "$PWD"' % jail["home"])
    assert (jail["call"] / "out.txt").read_text() == "hi\n" and not (jail["home"] / "new.txt").exists()
    assert r.stdout.strip().endswith("/work")


def test_path_traversal_does_not_reach_other_calls(jail):
    r = jail["run"]('IFS= read -r l < /work/../other/plan.json && echo "$l"; IFS= read -r l < "%s/../other/plan.json" && echo "$l"' % jail["call"])
    assert "SECRET" not in r.stdout


def test_symlink_in_call_folder_does_not_escape(jail):
    os.symlink(str(jail["home"] / "answers.json"), str(jail["call"] / "link.txt"))
    r = jail["run"]('IFS= read -r l < /work/link.txt && echo "$l"')
    assert "SECRET" not in r.stdout


def test_environment_cleared_and_login_file_only(jail):
    r = jail["run"]('echo "[${OPENAI_API_KEY:-}][${CODEX_API_KEY:-}]"; IFS= read -r l < "$CODEX_HOME/auth.json" && echo "$l"; ls -a "$CODEX_HOME"')
    out = r.stdout
    assert "[][]" in out and "fake" in out and "config.toml" not in out and "history" not in out and "AGENTS" not in out
