"""R3: the Codex installation folder must be a folder of the program's own, or the jail wrapper refuses.

Both wrappers grant the whole installation folder (PKG, the folder holding the binary) to the confined Codex
process: `--ro-bind "$PKG" "$PKG"` on Linux, `(allow file-read* (subpath "@PKG@"))` and
`(allow process-exec (subpath "@PKG@"))` on macOS. Before this correction, RNPLENS_CODEX_BIN=$HOME/codex made the
whole home directory readable by that process. The wrappers now refuse such a folder.

No model call, no sandbox and no login file is needed by anything here: every refusal is decided before the
wrapper looks at the login file, so no test in this module creates one.
"""
import hashlib
import os
import platform
import re
import stat
import subprocess

import pytest

from rnplens_assistant import codex_llm

PKG = os.path.dirname(os.path.realpath(codex_llm.__file__))
SRC = os.path.join(os.path.dirname(PKG), "codex_adapter")              # source checkout copy (absent when installed)
LINUX = os.path.join(PKG, "codex_adapter", "codex_jail.sh")
MAC = os.path.join(PKG, "codex_adapter", "codex_seatbelt.sh")
OPEN = "# >>> rnplens: installation-folder rule"
CLOSE = "# <<< rnplens: installation-folder rule <<<"
REFUSAL = "refusing Codex installation folder"
REFUSED = 64                                                           # the wrappers' configuration-refusal status


def rule_block(path):
    s = open(path, encoding="utf-8").read()
    i, j = s.index(OPEN), s.index(CLOSE)
    return s[i:j + len(CLOSE)]


def wrapper_copies():
    out = [LINUX, MAC]
    if os.path.isdir(SRC):
        out += [os.path.join(SRC, "codex_jail.sh"), os.path.join(SRC, "codex_seatbelt.sh")]
    return out


def test_the_rule_is_one_identical_text_in_every_wrapper_copy():
    blocks = {p: rule_block(p) for p in wrapper_copies()}
    assert len(set(blocks.values())) == 1, sorted(blocks)
    assert len(blocks) >= 2
    for p, b in blocks.items():
        assert "check_pkg_folder()" in b and "exit 64" in b, p


def test_the_rule_is_applied_before_anything_is_started():
    """Structural: in both wrappers the folder is validated before the executable and login-file checks, before
    any folder is created, before the profile is rendered and before the single exec that starts a process."""
    for p in (LINUX, MAC):
        s = open(p, encoding="utf-8").read()
        call = s.index("check_pkg_folder \"$PKG\" \"$HR\"")
        for later in ("[ -x \"$BIN\" ]", "auth.json", "\nexec "):
            assert call < s.index(later), (p, later)
        execs = [m.start() for m in re.finditer(r"(?m)^\s*exec\b", s)]
        assert len(execs) == 1 and call < execs[0], p
    s = open(LINUX, encoding="utf-8").read()
    assert s.index("check_pkg_folder \"$PKG\" \"$HR\"") < s.index("--ro-bind \"$PKG\" \"$PKG\"")
    s = open(MAC, encoding="utf-8").read()
    assert s.index("check_pkg_folder \"$PKG\" \"$HR\"") < s.index("mkdir -p \"$JH\"") < s.index('P=$(cat "$TPL")')


# (folder, home, reason) - the reason the message must name. Every row must be refused.
UNSAFE = [
    ("/", "/home/u", "root folder"),
    ("/home/u", "/home/u", "home folder"),
    ("/home", "/home/u", "contains your home folder"),
    ("/Users/u", "/Users/u", "home folder"),
    ("/Users", "/Users/u", "contains your home folder"),
    ("/tmp", "/home/u", "top-level"),
    ("/usr", "/home/u", "top-level"),
    ("/opt", "/home/u", "top-level"),
    ("/Applications", "/Users/u", "top-level"),
    ("/usr/bin", "/home/u", "shared system or scratch"),
    ("/usr/local", "/home/u", "shared system or scratch"),
    ("/usr/local/bin", "/home/u", "shared system or scratch"),
    ("/var/tmp", "/home/u", "shared system or scratch"),
    ("/private/tmp", "/Users/u", "shared system or scratch"),
    ("/private/var/folders", "/Users/u", "shared system or scratch"),
    ("/opt/homebrew/bin", "/Users/u", "shared system or scratch"),
    ("/Users/Shared", "/Users/u", "shared system or scratch"),
    ("/Library/Application Support", "/Users/u", "shared system or scratch"),
    ("relative/folder", "/home/u", "absolute path"),
    ("/no/such/folder/rnplens-r3", "/home/u", "existing folder"),
]


def _harness(tmp_path, wrapper):
    """The rule block of `wrapper`, sourced on its own: the decision is tested on either platform."""
    h = tmp_path / ("rule_%s.sh" % os.path.basename(wrapper))
    h.write_text("#!/bin/bash\nset -u\nME=rule_probe\n%s\ncheck_pkg_folder \"$1\" \"$2\"\necho ACCEPTED\n"
                 % rule_block(wrapper))
    return str(h)


@pytest.mark.parametrize("wrapper", [LINUX, MAC], ids=["linux_jail", "macos_wrapper"])
def test_the_rule_refuses_every_unsafe_folder_on_both_platforms(tmp_path, wrapper):
    h = _harness(tmp_path, wrapper)
    for folder, home, reason in UNSAFE:
        r = subprocess.run(["bash", h, folder, home], capture_output=True, text=True)
        assert r.returncode == REFUSED, (folder, r.returncode, r.stderr)
        assert REFUSAL in r.stderr and reason in r.stderr, (folder, r.stderr)
        assert "ACCEPTED" not in r.stdout, folder


@pytest.mark.parametrize("wrapper", [LINUX, MAC], ids=["linux_jail", "macos_wrapper"])
def test_the_rule_accepts_a_folder_of_the_programs_own(tmp_path, wrapper):
    h = _harness(tmp_path, wrapper)
    home = tmp_path / "home"
    ok = [home / ".codex" / "packages" / "standalone" / "v1",      # the documented standalone build
          home / "bin",                                            # a no-root user-owned program folder
          home / ".local" / "bin",
          tmp_path / "opt" / "codex-0.159.3" / "bin"]
    for d in ok:
        d.mkdir(parents=True)
        r = subprocess.run(["bash", h, str(d), str(home)], capture_output=True, text=True)
        assert r.returncode == 0 and "ACCEPTED" in r.stdout, (str(d), r.returncode, r.stderr)
        assert r.stderr == "", (str(d), r.stderr)


def _fake_install(tmp_path):
    """A home with the documented standalone layout and two loose copies. No login file: every refusal tested
    here is decided before the wrapper looks at one."""
    home = tmp_path / "home"
    binp = home / ".codex" / "packages" / "standalone" / "v1" / "bin"
    binp.mkdir(parents=True)
    (home / ".codex" / "packages" / "standalone" / "current").symlink_to(home / ".codex" / "packages" / "standalone" / "v1")
    (home / "bin").mkdir()
    for p in (binp / "codex", home / "codex", home / "bin" / "codex"):
        p.write_bytes(open("/bin/sh", "rb").read())
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    call = tmp_path / "calls" / "c1"
    call.mkdir(parents=True)
    return home, call


def _run(wrapper, home, call, codex_bin=None, path="/usr/bin:/bin"):
    env = {"HOME": str(home), "PATH": path}
    if codex_bin is not None:
        env["RNPLENS_CODEX_BIN"] = str(codex_bin)
    return subprocess.run(["bash", wrapper, str(call), "--"], env=env, capture_output=True, text=True)


WRAPPER = MAC if platform.system() == "Darwin" else LINUX
NO_LOGIN = 65        # the gate immediately after the rule: reaching it proves the folder was accepted


@pytest.mark.skipif(platform.system() not in ("Linux", "Darwin"), reason="no wrapper for this system")
def test_documented_installation_still_works(tmp_path):
    home, call = _fake_install(tmp_path)
    r = _run(WRAPPER, home, call)                                  # RNPLENS_CODEX_BIN unset: standalone build
    assert r.returncode == NO_LOGIN and REFUSAL not in r.stderr, (r.returncode, r.stderr)
    r = _run(WRAPPER, home, call, home / ".codex" / "packages" / "standalone" / "current" / "bin" / "codex")
    assert r.returncode == NO_LOGIN and REFUSAL not in r.stderr, (r.returncode, r.stderr)
    r = _run(WRAPPER, home, call, home / "bin" / "codex")          # no-root user-owned folder
    assert r.returncode == NO_LOGIN and REFUSAL not in r.stderr, (r.returncode, r.stderr)


@pytest.mark.skipif(platform.system() not in ("Linux", "Darwin"), reason="no wrapper for this system")
def test_a_bare_home_directory_is_refused(tmp_path):
    home, call = _fake_install(tmp_path)
    r = _run(WRAPPER, home, call, home / "codex")
    assert r.returncode == REFUSED, (r.returncode, r.stdout, r.stderr)
    assert REFUSAL in r.stderr and "home folder" in r.stderr and str(os.path.realpath(str(home))) in r.stderr
    assert "RNPLENS_CODEX_BIN" in r.stderr                         # the message says how to fix the installation
    # a refusal, not a crash: no interpreter error, no traceback, nothing on stdout
    assert r.stdout == "" and "Traceback" not in r.stderr
    assert not re.search(r"(?m)^(bash|.*\.sh): line [0-9]+:", r.stderr), r.stderr


@pytest.mark.skipif(platform.system() != "Linux", reason="bubblewrap jail")
def test_the_refusal_happens_before_bubblewrap_starts(tmp_path):
    """The jail starts exactly one process, `bwrap`, found on PATH. With a shim on PATH that records being run,
    an unsafe folder leaves no record: nothing was started."""
    home, call = _fake_install(tmp_path)
    shim = tmp_path / "shim"
    shim.mkdir()
    marker = tmp_path / "STARTED"
    (shim / "bwrap").write_text("#!/bin/sh\ntouch %s\n" % marker)
    (shim / "bwrap").chmod(0o755)
    assert subprocess.run(["bash", "-c", "PATH=%s:$PATH bwrap" % shim]).returncode == 0 and marker.exists()
    marker.unlink()                                                # the shim works; now the real check
    r = _run(LINUX, home, call, home / "codex", path="%s:/usr/bin:/bin" % shim)
    assert r.returncode == REFUSED and REFUSAL in r.stderr
    assert not marker.exists(), "bwrap was started despite the refusal"


@pytest.mark.skipif(platform.system() != "Darwin", reason="Seatbelt wrapper")
def test_the_refusal_happens_before_the_sandbox_is_prepared(tmp_path):
    """The Seatbelt wrapper creates the private CODEX_HOME and renders the profile only after the rule passes."""
    home, call = _fake_install(tmp_path)
    r = _run(MAC, home, call, home / "codex")
    assert r.returncode == REFUSED and REFUSAL in r.stderr
    assert not (call / ".codex_home").exists() and not (call / ".home").exists()
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "RNPLENS_CODEX_BIN": str(home / "codex"),
           "RNPLENS_JAIL_PRINT_PROFILE": "1"}
    r = subprocess.run(["bash", MAC, str(call), "--"], env=env, capture_output=True, text=True)
    assert r.returncode == REFUSED and "(deny default)" not in r.stdout      # no profile is even rendered


@pytest.mark.skipif(platform.system() != "Linux", reason="bubblewrap jail")
def test_a_binary_under_usr_is_unaffected_on_linux(tmp_path):
    """/usr is already bound read-only in full, so no package bind is made and there is nothing to validate;
    this layout keeps working exactly as before."""
    home, call = _fake_install(tmp_path)
    r = _run(LINUX, home, call, "/usr/bin/env")
    assert r.returncode == NO_LOGIN and REFUSAL not in r.stderr, (r.returncode, r.stderr)
    s = open(LINUX, encoding="utf-8").read()
    assert s.count('case "$PKG" in /usr/*) PKGBIND=0;; *) PKGBIND=1;; esac') == 1    # one decision, two uses
    assert s.count("PKGBIND") == 4


# The part of each wrapper that builds and applies the sandbox, from the first line that depends on the resolved
# paths to the end of the file. Byte-identical to the qualification candidate 53711d49: the correction adds a
# refusal in front of it and changes nothing inside it. For a folder the rule accepts, `pkgbind` holds exactly
# what it held before (PKGBIND=1 outside /usr, empty under /usr), so the bubblewrap argument list and the
# Seatbelt profile are the same as the candidate's. This matters because the Linux confinement gate G5
# (test_confine_linux.py), which measures what is visible inside the jail, is blocked by a standing owner
# restriction and cannot be re-run: this test is the evidence, in its place, that in-jail behaviour is untouched.
UNCHANGED = {
    "codex_jail.sh": ('CMD=("$BIN"', "807a191143ef0285cbdb640ca6b03ca49010eccc2e3c1ba42406f369b8131f33"),
    "codex_seatbelt.sh": ("JH=$CALL/.codex_home", "7f463c59f5903e1ee5b08ca6954155771a01ff11bc433cf8f23b04b5f709a9ee"),
}


@pytest.mark.parametrize("name", sorted(UNCHANGED), ids=sorted(UNCHANGED))
def test_the_sandbox_itself_is_unchanged_from_the_candidate(name):
    start, digest = UNCHANGED[name]
    for d in ([os.path.join(PKG, "codex_adapter")] + ([SRC] if os.path.isdir(SRC) else [])):
        s = open(os.path.join(d, name), encoding="utf-8").read()
        tail = s[s.index("\n" + start) + 1:]
        assert hashlib.sha256(tail.encode("utf-8")).hexdigest() == digest, os.path.join(d, name)
