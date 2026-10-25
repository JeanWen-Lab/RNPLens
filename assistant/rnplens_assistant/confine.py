"""Confinement of the whole Codex process, one interface for both supported operating systems (0.4 native platforms).

A jail is an executable script with one contract on every platform:

    JAIL CALLDIR -- codex-arguments...        run Codex confined, with CALLDIR as its only writable folder
    RNPLENS_JAIL_PROBE=1 [RNPLENS_JAIL_PROBE_HIDDEN=PATH] JAIL DIR --
                                              no model call: print JAIL_OK only if PATH is unreadable inside,
                                              the login file is readable and DIR is writable

Backends (selected by the operating system; there is no unconfined fallback):

    Linux   codex_adapter/codex_jail.sh      bubblewrap mount namespace; the call folder appears as /work
    macOS   codex_adapter/codex_seatbelt.sh  Apple Seatbelt (sandbox-exec), deny-by-default profile
                                             codex_seatbelt.sb; the call folder keeps its real path

Any other system gets the Linux jail name, which cannot run there, so the assistant refuses (as before)."""
import os
import platform

LINUX_JAIL = "codex_jail.sh"
MACOS_JAIL = "codex_seatbelt.sh"
SEATBELT_MARK = "# rnplens-jail: seatbelt"      # second line of codex_seatbelt.sh


def jail_name(system=None):
    return MACOS_JAIL if (system or platform.system()) == "Darwin" else LINUX_JAIL


def default_jail(pkg_dir, system=None):
    """The jail shipped with THIS installation for this operating system: the packaged copy
    (rnplens_assistant/codex_adapter/), else the source checkout's assistant/codex_adapter/."""
    name = jail_name(system)
    for p in (os.path.join(pkg_dir, "codex_adapter", name), os.path.join(os.path.dirname(pkg_dir), "codex_adapter", name)):
        if os.path.isfile(p):
            return p
    return os.path.join(pkg_dir, "codex_adapter", name)


def is_seatbelt(jail):
    """True for a Seatbelt-style jail (it declares itself in its first lines). Anything else, including the Linux jail
    and custom jails given with RNPLENS_CODEX_JAIL, is treated as a mount-namespace jail with the call folder at /work."""
    try:
        with open(jail, encoding="utf-8", errors="replace") as fh:
            head = [fh.readline().strip() for _ in range(3)]
    except OSError:
        return False
    return SEATBELT_MARK in head


def call_view(jail, call_dir):
    """The call folder as the confined Codex process sees it."""
    return os.path.realpath(call_dir) if is_seatbelt(jail) else "/work"


def sandbox_label(jail):
    return "read-only (inside Seatbelt jail)" if is_seatbelt(jail) else "read-only (inside bubblewrap jail)"
