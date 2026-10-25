"""0.4 native platforms: the shared confinement interface (confine.py), on every platform. No model call; nothing
here needs a working sandbox. Linux behaviour must be unchanged: same jail, same Codex arguments, same labels."""
import hashlib
import os
import platform
import re
import subprocess

import pytest

from rnplens_assistant import codex_llm, confine

PKG = os.path.dirname(os.path.realpath(codex_llm.__file__))
SRC = os.path.join(os.path.dirname(PKG), "codex_adapter")            # source checkout copy (absent when installed)
LINUX = os.path.join(PKG, "codex_adapter", "codex_jail.sh")
MAC = os.path.join(PKG, "codex_adapter", "codex_seatbelt.sh")
PROFILE = os.path.join(PKG, "codex_adapter", "codex_seatbelt.sb")
SEATBELT_PROBE = ["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)", "/usr/bin/true"]


def seatbelt_usable():
    if platform.system() != "Darwin" or not os.path.isfile("/usr/bin/sandbox-exec"):
        return False
    return subprocess.run(SEATBELT_PROBE, capture_output=True).returncode == 0


def test_backend_selection_by_operating_system():
    assert confine.jail_name("Linux") == "codex_jail.sh" and confine.jail_name("Darwin") == "codex_seatbelt.sh"
    assert confine.jail_name("Windows") == "codex_jail.sh"                   # cannot run there: refused as before
    assert confine.default_jail(PKG, "Linux") == LINUX and confine.default_jail(PKG, "Darwin") == MAC
    for p in (LINUX, MAC):
        assert os.path.isfile(p) and os.access(p, os.X_OK), p
    assert os.path.isfile(PROFILE)


@pytest.mark.skipif(not os.path.isdir(SRC), reason="installed mode: no source-checkout copy")
def test_packaged_and_source_copies_identical():
    for n in ("codex_jail.sh", "codex_seatbelt.sh", "codex_seatbelt.sb"):
        a = open(os.path.join(SRC, n), "rb").read(); b = open(os.path.join(PKG, "codex_adapter", n), "rb").read()
        assert hashlib.sha256(a).digest() == hashlib.sha256(b).digest(), n


LINUX_JAIL_SHA256 = "8365baeeec004e4cd96370677c823d08b6eb4d9b019f34e3061f10576c9e6853"


def test_linux_jail_file_unchanged_from_the_candidate():
    # Amendment 11 (R3): the jail refuses an unsafe Codex installation folder; see
    # assistant/tests/test_install_location.py. Before that, rc/0.4-candidate 8e57aea through the
    # candidate 53711d49: 2a88313b4829fde9c6e56b230ca7bddc5f5c35227a402923b7409ac4a1c8c2be.
    assert hashlib.sha256(open(LINUX, "rb").read()).hexdigest() == LINUX_JAIL_SHA256


def test_jail_kind_and_call_view(tmp_path):
    assert confine.is_seatbelt(MAC) and not confine.is_seatbelt(LINUX)
    fake = tmp_path / "custom_jail.sh"; fake.write_text("#!/bin/bash\nexec \"$@\"\n")
    assert not confine.is_seatbelt(str(fake)) and not confine.is_seatbelt(str(tmp_path / "missing"))
    assert confine.call_view(LINUX, str(tmp_path)) == "/work" and confine.call_view(str(fake), str(tmp_path)) == "/work"
    assert confine.call_view(MAC, str(tmp_path)) == os.path.realpath(str(tmp_path))
    assert confine.sandbox_label(LINUX) == "read-only (inside bubblewrap jail)"
    assert confine.sandbox_label(MAC) == "read-only (inside Seatbelt jail)"


def _captured_args(monkeypatch, tmp_path, jail):
    seen = {}

    def fake_run(args, **kw):
        seen["args"] = list(args)
        open(os.path.join(kw["cwd"], "last.json"), "w").write("{}")
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(codex_llm, "JAIL", jail)
    monkeypatch.setattr(codex_llm, "CALLS_ROOT", str(tmp_path / "calls"))
    monkeypatch.setattr(codex_llm.subprocess, "run", fake_run)
    os.makedirs(str(tmp_path / "calls"))
    c = codex_llm.CodexClient("t")
    c.credits0 = None
    c.run("plan", "PROMPT", {"type": "object"})
    return seen["args"], c.calls[-1]["call_dir"], c


def test_linux_codex_arguments_identical_to_the_candidate(monkeypatch, tmp_path):
    args, cd, c = _captured_args(monkeypatch, tmp_path, LINUX)
    cfg = c.config
    # the exact list built by rc/0.4-candidate 8e57aea (codex_llm.py lines 134-139)
    want = [os.path.abspath(LINUX), cd, "--", "exec", "--skip-git-repo-check", "--ignore-user-config", "--json", "-s", "read-only",
            "-m", cfg["model"], "-c", 'model_reasoning_effort="%s"' % cfg["reasoning_effort"], "--output-schema", "/work/schema.json",
            "-o", "/work/last.json"] + codex_llm.HARDENING + ["-"]
    assert args == want


def test_seatbelt_codex_arguments_use_the_real_call_folder(monkeypatch, tmp_path):
    args, cd, _ = _captured_args(monkeypatch, tmp_path, MAC)
    real = os.path.realpath(cd)
    assert args[args.index("--output-schema") + 1] == real + "/schema.json" and args[args.index("-o") + 1] == real + "/last.json"
    assert not any("/work/" in a for a in args)


def test_profile_is_deny_by_default_and_narrow():
    p = open(PROFILE, encoding="utf-8").read()
    code = "\n".join(l.split(";;")[0] for l in p.splitlines())          # without comments
    assert "(deny default)" in code and "(allow default)" not in code
    assert '(subpath "/System")' not in code                             # /System/Volumes/Data holds /Users
    for bad in ('"/Users', '"/Volumes', '"/private/var/folders', '"/private/tmp', '"/Applications', '"/opt', '"/usr/local',
                '"/bin"', '"/usr/bin"', "file-read* (subpath \"/\")"):
        assert bad not in code, bad
    assert re.findall(r"\(allow process-exec[^\n]*", code) == ['(allow process-exec (subpath "@PKG@"))']
    assert set(re.findall(r"\(allow network-outbound ([^\n]*)\)", code)) == {'(remote tcp "*:443")', '(literal "/private/var/run/mDNSResponder")'}
    services = set(re.findall(r'global-name "([^"]+)"', code))
    for forbidden in ("pasteboard", "appleevents", "SecurityServer", "cfprefsd", "coreservices", "launchservices", "lsd", "tccd", "pboard"):
        assert not any(forbidden.lower() in s.lower() for s in services), forbidden
    assert "(allow file-write* (require-all (subpath \"@CALL@\") (require-not (literal \"@JH@/auth.json\"))))" in code
    assert '(allow file-read* file-write-data (literal "@AUTH@"))' in code
    # 07aeca8 (dyld root descriptor): "/" gets data-read (open, list) and metadata only; never recursive, never write
    assert '(allow file-read-data (literal "/"))' in code
    assert code.count('(literal "/")') == 2
    assert not re.search(r'file-read\*[^\n]*\(literal "/"\)', code) and not re.search(r'file-write[^\n]*\(literal "/"\)', code)


def test_wrapper_starts_codex_only_through_sandbox_exec():
    s = open(MAC, encoding="utf-8").read()
    assert s.splitlines()[1] == confine.SEATBELT_MARK
    runs = [l for l in s.splitlines() if re.match(r"\s*exec\b", l)]
    assert len(runs) == 1 and runs[0].strip().startswith("exec /usr/bin/env -i ")
    assert '"$SBX" -p "$P" "${CMD[@]}"' in s                              # the only launch, always under the profile
    assert "OPENAI_API_KEY" not in s.split("exec /usr/bin/env -i", 1)[1]  # cleared environment: nothing passed through
    assert "SBX=/usr/bin/sandbox-exec" in s and "unconfined" not in s.replace("no unconfined fallback", "")


def _fake_home(tmp_path, bin_src="/bin/bash"):
    home = tmp_path / "home"; pkg = home / ".codex" / "packages" / "standalone" / "v1" / "bin"
    pkg.mkdir(parents=True)
    (home / ".codex" / "packages" / "standalone" / "current").symlink_to(home / ".codex" / "packages" / "standalone" / "v1")
    exe = pkg / "codex"
    if bin_src:
        exe.write_bytes(open(bin_src, "rb").read()); exe.chmod(0o755)
    (home / ".codex" / "auth.json").write_text('{"fake": "login"}')
    calls = tmp_path / "calls"; (calls / "c1").mkdir(parents=True)
    return home, calls / "c1"


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS wrapper")
def test_wrapper_guards_and_profile_rendering(tmp_path):
    home, call = _fake_home(tmp_path)
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    r = subprocess.run(["bash", MAC, str(call), "--"], env=dict(env, RNPLENS_JAIL_PRINT_PROFILE="1"), capture_output=True, text=True)
    assert r.returncode == 0 and "(deny default)" in r.stdout and "@" not in r.stdout.replace("@PKG@", "X")
    assert os.path.realpath(str(call)) in r.stdout and not re.search(r"@[A-Z]+@", r.stdout)
    r = subprocess.run(["bash", MAC, str(home), "--"], env=env, capture_output=True, text=True)       # call folder = home
    assert r.returncode == 64 and "refusing CALLDIR" in r.stderr
    (home / ".codex" / "auth.json").unlink()
    r = subprocess.run(["bash", MAC, str(call), "--"], env=env, capture_output=True, text=True)       # no login file
    assert r.returncode == 65


@pytest.mark.skipif(platform.system() != "Darwin" or seatbelt_usable(), reason="needs macOS where Seatbelt CANNOT be applied")
def test_wrapper_fails_closed_when_seatbelt_cannot_be_applied(tmp_path):
    home, call = _fake_home(tmp_path)
    marker = call / "RAN"
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    r = subprocess.run(["bash", MAC, str(call), "--", "-c", "echo x > %s" % marker], env=env, capture_output=True, text=True)
    assert r.returncode != 0 and not marker.exists()
    r = subprocess.run(["bash", MAC, str(call), "--"], env=dict(env, RNPLENS_JAIL_PROBE="1"), capture_output=True, text=True)
    assert "JAIL_OK" not in r.stdout
