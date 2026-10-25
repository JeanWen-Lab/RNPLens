"""0.4 native platforms: the macOS Seatbelt jail, tested for real (no model call). The model-controlled process is
represented by a copy of /bin/bash installed as the 'Codex binary': its builtins can read, write, list folders, follow
links and open TCP connections without starting any other program, so every check exercises the profile itself.

These tests need a Mac where Seatbelt can be applied (an ordinary Terminal session; not inside another sandbox).
Elsewhere they are skipped, unless RNPLENS_REQUIRE_SEATBELT=1 (the qualification script), which turns the skip into a
failure. RNPLENS_TEST_REAL_CODEX=1 also runs the installed Codex binary under the jail (`--version`, `login status`;
no model call)."""
import os
import platform
import shutil
import socket
import subprocess
import threading

import pytest

from rnplens_assistant import codex_llm

PKG = os.path.dirname(os.path.realpath(codex_llm.__file__))
MAC = os.path.join(PKG, "codex_adapter", "codex_seatbelt.sh")
PROBE = ["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)", "/usr/bin/true"]


def _usable():
    return (platform.system() == "Darwin" and os.path.isfile(PROBE[0])
            and subprocess.run(PROBE, capture_output=True).returncode == 0)


USABLE = _usable()
if not USABLE:
    if os.environ.get("RNPLENS_REQUIRE_SEATBELT") == "1":
        raise RuntimeError("RNPLENS_REQUIRE_SEATBELT=1 but Seatbelt cannot be applied here (run from an ordinary Terminal)")
    pytestmark = pytest.mark.skip(reason="Seatbelt cannot be applied here (not macOS, or already inside a sandbox)")


@pytest.fixture
def jail(tmp_path):
    """A fake home with a standalone-style Codex install (bash copy), a login file, Codex settings that must stay
    hidden, private data, a second call folder and the call folder under test."""
    home = tmp_path / "home"
    v1 = home / ".codex" / "packages" / "standalone" / "v1"; (v1 / "bin").mkdir(parents=True)
    (home / ".codex" / "packages" / "standalone" / "current").symlink_to(v1)
    # Copy executable bytes, not Apple's protected system-file flags (copy2/chflags
    # cannot apply those flags to an ordinary user's disposable fixture).
    shutil.copyfile("/bin/bash", v1 / "bin" / "codex")
    (v1 / "bin" / "codex").chmod(0o755)
    # Current macOS launch constraints reject the relocated Apple signature even
    # without Seatbelt. Give only our disposable copy an ad-hoc signature.
    signed = subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(v1 / "bin" / "codex")],
                            capture_output=True, text=True)
    assert signed.returncode == 0, signed.stderr
    (home / ".codex" / "auth.json").write_text('{"fake": "login"}\n')
    for n in ("config.toml", "history.jsonl", "AGENTS.md"):
        (home / ".codex" / n).write_text("SECRET-%s\n" % n)
    (home / ".ssh").mkdir(); (home / ".ssh" / "id_ed25519").write_text("SECRET-KEY\n")
    (home / "research").mkdir(); (home / "research" / "reference.cif").write_text("SECRET-REFERENCE\n")
    (home / "answers.json").write_text("SECRET-ANSWER\n")
    calls = home / ".rnplens" / "codex_calls"
    (calls / "other").mkdir(parents=True); (calls / "other" / "plan.json").write_text("SECRET-OTHER-CALL\n")
    call = calls / "c1"; call.mkdir()

    def run(script, test_mode=False, extra_env=None, timeout=60):
        env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "OPENAI_API_KEY": "sk-test-must-not-pass", "CODEX_API_KEY": "x"}
        env.update(extra_env or {})
        if test_mode:
            env["RNPLENS_JAIL_TEST"] = "1"
            argv = ["bash", MAC, str(call), "--", "/bin/bash", "-c", script]
        else:
            argv = ["bash", MAC, str(call), "--", "-c", script]           # the bash copy is the 'Codex' process
        # Match CodexClient.run: model-controlled commands start in their call folder.
        return subprocess.run(argv, cwd=call, env=env, capture_output=True, text=True, timeout=timeout)
    return {"home": home, "call": call, "calls": calls, "run": run}


def _can_read(j, path):
    r = j["run"]('IFS= read -r line < "%s" && printf "%%s" "$line"' % path)
    return r.returncode == 0 and "SECRET" in r.stdout


def _can_list(j, path):
    r = j["run"]('shopt -s nullglob dotglob; a=("%s"/*); echo "${#a[@]}"' % path)
    return r.returncode == 0 and r.stdout.strip() not in ("", "0")


def test_self_probe_passes(jail):
    for hidden in (jail["home"], jail["home"] / "research", jail["home"] / "answers.json"):
        r = subprocess.run(["bash", MAC, str(jail["call"]), "--"], env={"HOME": str(jail["home"]), "PATH": "/usr/bin:/bin",
                           "RNPLENS_JAIL_PROBE": "1", "RNPLENS_JAIL_PROBE_HIDDEN": str(hidden)}, capture_output=True, text=True)
        assert r.returncode == 0 and "JAIL_OK" in r.stdout, (hidden, r.stderr)


def test_confined_process_starts_and_owns_its_call_folder(jail):
    r = jail["run"]('echo hello > "$PWD/out.txt" && IFS= read -r x < "$PWD/out.txt" && echo "$x|$HOME|$CODEX_HOME|$TMPDIR"')
    assert r.returncode == 0, r.stderr
    x, home, ch, tmp = r.stdout.strip().split("|")
    call = os.path.realpath(str(jail["call"]))
    assert x == "hello" and home == call + "/.home" and ch == call + "/.codex_home" and tmp.startswith(call + "/.tmp")


@pytest.mark.parametrize("call_path", ["absolute", "relative", "symlink"])
def test_wrapper_enters_call_folder_from_unreadable_caller(jail, tmp_path, call_path):
    """Configuration discovery must start in CALLDIR, even when the caller starts elsewhere.
    The caller folder stays unreadable; no profile exception is needed for it."""
    caller = tmp_path / "caller"; caller.mkdir()
    secret = caller / "config.toml"; secret.write_text("SECRET-CALLER-CONFIG\n")
    call = os.path.realpath(str(jail["call"]))
    arg = call
    if call_path == "relative":
        arg = os.path.relpath(call, caller)
    elif call_path == "symlink":
        link = caller / "call-link"; link.symlink_to(call, target_is_directory=True)
        arg = str(link)
    script = ('pwd -P || exit 7; echo "$PWD"; '
              'echo owned > cwd-marker; '
              'if IFS= read -r line < "$1"; then echo LEAK; exit 8; fi')
    r = subprocess.run(["bash", MAC, arg, "--", "-c", script, "probe", str(secret)], cwd=caller,
                       env={"HOME": str(jail["home"]), "PATH": "/usr/bin:/bin"},
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and r.stdout.splitlines() == [call, call], (r.stdout, r.stderr)
    assert (jail["call"] / "cwd-marker").read_text() == "owned\n"
    assert not (caller / "cwd-marker").exists()


def test_dyld_root_descriptor_does_not_grant_private_descendants(jail):
    r = jail["run"]('exec 3</ && exec 3<&- && echo ROOT_DESCRIPTOR')
    assert r.returncode == 0 and "ROOT_DESCRIPTOR" in r.stdout, r.stderr
    assert not _can_read(jail, jail["home"] / "answers.json")
    assert not _can_list(jail, jail["home"])
    assert not _can_list(jail, "/Users")
    data = "/System/Volumes/Data" + os.path.realpath(str(jail["home"] / "answers.json"))
    assert not _can_read(jail, data)


def test_root_descriptor_alternate_paths_do_not_escape(jail):
    """Lead review of 07aeca8: the literal "/" read rule must not reach private descendants through a path relative
    to "/", through the boot-volume alias under /Volumes, or through volfs (/.vol/<device>/<inode>). Each alternate
    path is first confirmed readable OUTSIDE the jail, so a denial inside is meaningful."""
    secret = os.path.realpath(str(jail["home"] / "answers.json"))
    r = jail["run"]('cd / && IFS= read -r l < "%s" && echo "$l"' % secret.lstrip("/"))
    assert "SECRET" not in r.stdout
    r = jail["run"]('cd / && shopt -s nullglob dotglob; a=(Users/*); echo "${#a[@]}"')
    assert r.stdout.strip() in ("", "0")
    r = jail["run"]('shopt -s nullglob; a=(/*); echo "${#a[@]}"')            # the root itself: public top-level names
    assert r.returncode == 0 and int(r.stdout.strip() or 0) > 0
    boots = [os.path.join("/Volumes", v) for v in os.listdir("/Volumes")
             if os.path.realpath(os.path.join("/Volumes", v)) == "/"]
    for b in boots:
        if os.path.isfile(b + secret):
            assert not _can_read(jail, b + secret), b
        assert not _can_list(jail, b + "/Users"), b
    st = os.stat(secret)
    vol = "/.vol/%d/%d" % (st.st_dev, st.st_ino)
    try:
        outside = open(vol).read()
    except OSError:
        outside = ""
    if "SECRET" in outside:
        assert not _can_read(jail, vol)


@pytest.mark.parametrize("rel", ["answers.json", "research/reference.cif", ".ssh/id_ed25519", ".codex/config.toml",
                                 ".codex/history.jsonl", ".codex/AGENTS.md", ".rnplens/codex_calls/other/plan.json"])
def test_private_files_unreadable(jail, rel):
    assert not _can_read(jail, jail["home"] / rel)


def test_path_traversal_and_alternative_paths_unreadable(jail):
    call = os.path.realpath(str(jail["call"]))
    assert not _can_read(jail, call + "/../other/plan.json")
    assert not _can_read(jail, call + "/../../../answers.json")
    data = "/System/Volumes/Data" + os.path.realpath(str(jail["home"] / "answers.json"))     # firmlinked data volume
    assert not _can_read(jail, data)


@pytest.mark.parametrize("rel", ["", "research", ".ssh", ".codex", ".rnplens/codex_calls"])
def test_folders_cannot_be_listed(jail, rel):
    assert not _can_list(jail, jail["home"] / rel if rel else jail["home"])


def test_real_user_folders_cannot_be_listed_or_read(jail):
    real = os.path.realpath(os.path.expanduser("~"))
    for p in (real, real + "/.ssh", "/Users", "/Volumes", "/private/var/folders", "/System/Volumes/Data/Users"):
        assert not _can_list(jail, p), p
    for f in (real + "/.ssh/id_ed25519", real + "/.ssh/id_rsa", real + "/.ssh/config", real + "/.zsh_history"):
        if os.path.exists(f):
            assert not _can_read(jail, f), f


def test_writes_outside_the_call_folder_denied(jail):
    for p in (jail["home"] / "new.txt", jail["calls"] / "other" / "x", "/tmp/rnplens_jail_write_test", "/private/tmp/rnplens_jail_w2",
              os.path.realpath(os.path.expanduser("~")) + "/rnplens_jail_write_test"):
        r = jail["run"]('echo x > "%s"' % p)
        assert r.returncode != 0 and not os.path.exists(str(p)), p


def test_symlinks_do_not_escape(jail):
    os.symlink(str(jail["home"] / "answers.json"), str(jail["call"] / "link.txt"))
    os.symlink(str(jail["home"] / "research"), str(jail["call"] / "dirlink"))
    assert not _can_read(jail, jail["call"] / "link.txt")
    assert not _can_list(jail, jail["call"] / "dirlink")
    assert not _can_read(jail, jail["call"] / "dirlink" / "reference.cif")
    jail["run"]('echo y > "$PWD/dirlink/new.txt"')                                         # write through a link: denied
    assert not (jail["home"] / "research" / "new.txt").exists()


def test_hard_links_do_not_expose_private_files(jail):
    r = jail["run"]('/bin/ln "%s" "$PWD/hard.txt" 2>/dev/null; IFS= read -r l < "$PWD/hard.txt" && echo "$l"' % (jail["home"] / "answers.json"),
                    test_mode=True)
    assert "SECRET" not in r.stdout


def test_no_other_program_can_be_started(jail):
    for prog in ("/bin/ls /", "/bin/sh -c true", "/usr/bin/python3 -c 1", "/usr/bin/curl -s https://example.org",
                 "/usr/bin/osascript -e 1", "/usr/bin/ssh -V", "/usr/bin/sandbox-exec -p '(version 1)(allow default)' /usr/bin/true"):
        r = jail["run"]("%s; echo rc=$?" % prog)
        assert "rc=0" not in r.stdout, (prog, r.stdout, r.stderr)


def test_environment_is_cleared(jail):
    r = jail["run"]('echo "[${OPENAI_API_KEY:-}][${CODEX_API_KEY:-}][${SSH_AUTH_SOCK:-}]"', extra_env={"SSH_AUTH_SOCK": "/tmp/agent.sock"})
    assert r.returncode == 0 and r.stdout.strip() == "[][][]"


def test_login_file_readable_only_through_its_link_and_link_not_replaceable(jail):
    r = jail["run"]('IFS= read -r l < "$CODEX_HOME/auth.json" && echo "$l"')
    assert r.returncode == 0 and "fake" in r.stdout
    r = jail["run"]('echo "{}" > "$PWD/x.json"; /bin/mv "$PWD/x.json" "$CODEX_HOME/auth.json"; /bin/rm "$CODEX_HOME/auth.json"; '
                    '[ -L "$CODEX_HOME/auth.json" ] && echo LINK', test_mode=True)
    assert "LINK" in r.stdout and (jail["home"] / ".codex" / "auth.json").read_text() == '{"fake": "login"}\n'


class _Listener:
    def __init__(self, family=socket.AF_INET, path=None):
        self.s = socket.socket(family, socket.SOCK_STREAM)
        if path:
            self.s.bind(path)
        else:
            self.s.bind(("127.0.0.1", 0)); self.port = self.s.getsockname()[1]
        self.s.listen(1); self.s.settimeout(5); self.hits = 0
        threading.Thread(target=self._acc, daemon=True).start()

    def _acc(self):
        try:
            c, _ = self.s.accept(); self.hits += 1; c.close()
        except OSError:
            pass


def test_network_local_services_denied(jail, monkeypatch):
    lis = _Listener()
    r = jail["run"]("exec 3<>/dev/tcp/127.0.0.1/%d && echo CONNECTED" % lis.port)
    assert "CONNECTED" not in r.stdout and lis.hits == 0
    # sockaddr_un has a short path limit on macOS. Bind/connect relative to the
    # call folder: a long workspace still works, and this tests the network rule
    # even though the socket's filesystem path is explicitly readable.
    with monkeypatch.context() as m:
        m.chdir(jail["call"])
        ul = _Listener(socket.AF_UNIX, "s.sock")
    r = jail["run"]('/usr/bin/nc -U s.sock < /dev/null && echo CONNECTED', test_mode=True)
    assert "CONNECTED" not in r.stdout and ul.hits == 0
    r = jail["run"]("exec 3<>/dev/tcp/127.0.0.1/22 && echo CONNECTED")
    assert "CONNECTED" not in r.stdout


def test_network_https_allowed_when_online(jail):
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=5).close()
    except OSError:
        pytest.skip("no internet connection from this machine")
    r = jail["run"]("exec 3<>/dev/tcp/1.1.1.1/443 && echo CONNECTED")
    assert "CONNECTED" in r.stdout, r.stderr
    r = jail["run"]("exec 3<>/dev/tcp/1.1.1.1/80 && echo CONNECTED")
    assert "CONNECTED" not in r.stdout


def test_nested_sandbox_fails_closed(jail):
    marker = jail["call"] / "RAN"
    r = subprocess.run(PROBE[:3] + ["bash", MAC, str(jail["call"]), "--", "-c", "echo x > %s" % marker],
                       env={"HOME": str(jail["home"]), "PATH": "/usr/bin:/bin"}, capture_output=True, text=True)
    assert r.returncode != 0 and not marker.exists()


REAL = os.environ.get("RNPLENS_TEST_REAL_CODEX") == "1"


@pytest.mark.skipif(not REAL, reason="set RNPLENS_TEST_REAL_CODEX=1 to run the installed Codex binary (no model call)")
def test_real_codex_starts_under_the_jail(tmp_path):
    from rnplens import doctor
    exe = doctor.codex_path(doctor.Env())
    assert exe, "no standalone Codex (or RNPLENS_CODEX_BIN) on this Mac"
    call = tmp_path / "call"; call.mkdir()
    env = {k: os.environ[k] for k in ("HOME", "CODEX_HOME", "RNPLENS_CODEX_BIN") if k in os.environ}
    env["PATH"] = "/usr/bin:/bin"
    r = subprocess.run(["bash", MAC, str(call), "--", "--version"], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "codex" in (r.stdout + r.stderr).lower(), r.stderr[-500:]
    r = subprocess.run(["bash", MAC, str(call), "--", "login", "status"], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "chatgpt" in (r.stdout + r.stderr).lower(), (r.stdout + r.stderr)[-500:]
