#!/bin/bash
# rnplens-jail: seatbelt
# codex_seatbelt.sh CALLDIR -- codex exec ARGS...          (macOS; on Linux the jail is codex_jail.sh)
# Runs the WHOLE Codex process under Apple's Seatbelt sandbox (/usr/bin/sandbox-exec) with the deny-by-default profile
# codex_seatbelt.sb. Inside, the process can:
#   read      system libraries, time zones and certificates; the Codex installation; the ChatGPT login file (one
#             file, reached through a link in a private per-call CODEX_HOME; never copied or read by this script);
#             and CALLDIR;
#   write     CALLDIR and, in place, the login file (token refresh);
#   execute   only the Codex binary and its own installation folder (no shell, no interpreter, no other program);
# The installation folder is granted read and execute IN FULL, so it must be a folder of its own: a home directory,
#   a root or a shared system or scratch folder is REFUSED (exit 64) before anything is started (check_pkg_folder).
#   connect   outbound TCP port 443 and the system DNS resolver; no other network or local socket.
# Nothing else is readable or writable: no home-directory contents, SSH keys, project folders, references, other
# call folders, or Codex's own settings, history and instructions in ~/.codex. The environment is cleared (no API
# keys); HOME, CODEX_HOME and TMPDIR point into CALLDIR.
# Difference from Linux: there is no private mount namespace. Denied paths still exist; they cannot be read, listed or
# written, and path metadata is readable only for the parent folders of the allowed paths.
# Fails closed: if the sandbox cannot be applied (for example inside another sandbox), Codex is not started. There is
# no unconfined fallback.
# Self-probe without any model call (used by `rnplens doctor --agent`):
#   RNPLENS_JAIL_PROBE=1 [RNPLENS_JAIL_PROBE_HIDDEN=/a/host/path] codex_seatbelt.sh DIR --
#   prints JAIL_OK only if the hidden path can be neither listed nor read, the login file is readable, DIR is
#   writable and the Codex binary is executable, all from inside the same profile.
# Review: RNPLENS_JAIL_PRINT_PROFILE=1 codex_seatbelt.sh DIR -- prints the filled-in profile and runs nothing.
# Confinement tests (no model call): RNPLENS_JAIL_TEST=1 codex_seatbelt.sh DIR -- /bin/bash -c '...' runs the given
#   command instead of Codex, under the same profile plus execute permission for a few system test tools only.
set -u
ME=codex_seatbelt
# >>> rnplens: installation-folder rule (identical text in codex_jail.sh and codex_seatbelt.sh) >>>
# The Codex installation folder (PKG, the folder that holds the binary) is granted to the confined Codex process:
# read access on both platforms, and execute access as well on macOS. The folder is derived from the binary's own
# location, so an operator who points RNPLENS_CODEX_BIN at a binary sitting directly in a shared folder would
# silently widen that grant to everything in the folder. This rule refuses such a folder instead. It can only turn
# a start into a refusal: it never widens access, never changes what is granted, and never touches any evidence,
# hash or scientific output. Fail closed - a folder that cannot be shown to be one program's own is refused.
# The reasons are tried most-specific first, so the message names the actual problem; every one of them refuses.
check_pkg_folder() {                     # $1 = resolved installation folder, $2 = resolved home folder
  pkgf_p=$1; pkgf_h=$2; pkgf_why=
  case "$pkgf_p" in /*) ;; *) pkgf_why="it is not an absolute path" ;; esac
  [ -n "$pkgf_why" ] || [ "$pkgf_p" != / ] || pkgf_why="it is the root folder"
  [ -n "$pkgf_why" ] || [ "$pkgf_p" != "$pkgf_h" ] || pkgf_why="it is your home folder"
  if [ -z "$pkgf_why" ]; then case "$pkgf_h/" in "$pkgf_p"/*) pkgf_why="it contains your home folder";; esac; fi
  if [ -z "$pkgf_why" ]; then
    case "$pkgf_p" in
      /usr/bin|/usr/sbin|/usr/share|/usr/libexec|/usr/local|/usr/local/bin|/usr/local/sbin|/usr/local/share|\
      /var/tmp|/var/run|/private/etc|/private/tmp|/private/var|/private/var/tmp|/private/var/folders|\
      /opt/local|/opt/local/bin|/opt/local/sbin|/opt/homebrew|/opt/homebrew/bin|/opt/homebrew/sbin|\
      /Users/Shared|"/Library/Application Support"|/System/Volumes/Data|/mnt/data|/srv/data)
        pkgf_why="it is a shared system or scratch folder";;
    esac
  fi
  if [ -z "$pkgf_why" ]; then case "${pkgf_p#/}" in */*) ;; *) pkgf_why="it is a top-level system folder";; esac; fi
  [ -n "$pkgf_why" ] || [ -d "$pkgf_p" ] || pkgf_why="it is not an existing folder"
  [ -z "$pkgf_why" ] || {
    printf '%s: refusing Codex installation folder %s: %s The whole folder would be granted to the Codex process.\n' "$ME" "$pkgf_p" "$pkgf_why." >&2
    printf '%s: install the standalone Codex build (its folder is its own), or copy the binary into a folder of its own and point RNPLENS_CODEX_BIN at that copy.\n' "$ME" >&2
    exit 64
  }
}
# <<< rnplens: installation-folder rule <<<
[ "$(/usr/bin/uname -s)" = Darwin ] || { echo "codex_seatbelt: macOS only (use codex_jail.sh on Linux)" >&2; exit 64; }
SBX=/usr/bin/sandbox-exec
[ -x "$SBX" ] || { echo "codex_seatbelt: $SBX not found" >&2; exit 64; }
[ -x /bin/realpath ] || { echo "codex_seatbelt: /bin/realpath not found (macOS 13 or later required)" >&2; exit 64; }
HERE=$(cd "$(dirname "$0")" && pwd -P)
TPL=$HERE/codex_seatbelt.sb
[ -f "$TPL" ] || { echo "codex_seatbelt: profile $TPL not found" >&2; exit 64; }
[ -n "${1:-}" ] && [ -d "$1" ] || { echo "codex_seatbelt: CALLDIR must be an existing folder" >&2; exit 64; }
CALL=$(cd "$1" && pwd -P); shift; [ "${1:-}" = "--" ] && shift
H=${HOME:?HOME must be set}
CH=${CODEX_HOME:-$H/.codex}
HR=$(/bin/realpath "$H" 2>/dev/null || echo "$H")
if [ -n "${RNPLENS_CODEX_BIN:-}" ]; then
  BIN=$(/bin/realpath "$RNPLENS_CODEX_BIN") || exit 64; PKG=$(dirname "$BIN")
else
  PKG=$(/bin/realpath "$CH/packages/standalone/current" 2>/dev/null) || { echo "codex_seatbelt: no standalone Codex under $CH and RNPLENS_CODEX_BIN not set" >&2; exit 64; }
  BIN=$PKG/bin/codex
fi
check_pkg_folder "$PKG" "$HR"
[ -x "$BIN" ] || { echo "codex_seatbelt: $BIN is not executable" >&2; exit 64; }
[ -f "$CH/auth.json" ] || { echo "codex_seatbelt: no ChatGPT login file in $CH (run 'codex login'; RNPLens needs Codex's file-based login storage, cli_auth_credentials_store = \"file\")" >&2; exit 65; }
AUTH=$(/bin/realpath "$CH/auth.json") || exit 65
# The call folder must be a dedicated folder: never /, the home folder or a folder that contains it, the Codex
# installation or the login file.
for x in "$HR" "$PKG" "$AUTH"; do
  case "$x/" in "$CALL"/*) echo "codex_seatbelt: refusing CALLDIR $CALL: it contains $x" >&2; exit 64;; esac
done
JH=$CALL/.codex_home
mkdir -p "$JH" "$CALL/.codex_sessions" "$CALL/.tmp" "$CALL/.home" || exit 64
ln -sfn "$CALL/.codex_sessions" "$JH/sessions" && ln -sfn "$AUTH" "$JH/auth.json" || exit 64
q() { local s=${1//\\/\\\\}; printf '%s' "${s//\"/\\\"}"; }            # SBPL string escaping
anc() { local p; p=$(dirname "$1"); while [ "$p" != / ]; do printf '(literal "%s")\n' "$(q "$p")"; p=$(dirname "$p"); done; }
ANC=$( { anc "$CALL/x"; anc "$PKG/x"; anc "$AUTH"; anc "$HR/x"; } | sort -u )
EXTRA=""
MODE=run
if [ "${RNPLENS_JAIL_PROBE:-}" = 1 ]; then MODE=probe; elif [ "${RNPLENS_JAIL_TEST:-}" = 1 ]; then MODE=test; fi
if [ $MODE != run ]; then           # test tools only; the filesystem, network and service rules are unchanged
  EXTRA='(allow process-exec file-read* (literal "/bin/bash") (literal "/bin/cat") (literal "/bin/ls") (literal "/bin/ln") (literal "/bin/mv") (literal "/bin/rm") (literal "/bin/mkdir") (literal "/usr/bin/touch") (literal "/usr/bin/nc") (literal "/usr/bin/env") (literal "/usr/bin/true") (literal "/usr/bin/false"))'
fi
P=$(cat "$TPL")
P=${P//@CALL@/$(q "$CALL")}; P=${P//@PKG@/$(q "$PKG")}; P=${P//@AUTH@/$(q "$AUTH")}; P=${P//@JH@/$(q "$JH")}
P=${P//@ANCESTORS@/$ANC}; P=${P//@TEST_TOOLS@/$EXTRA}
case "$P" in *@[A-Z]*@*) echo "codex_seatbelt: unresolved profile placeholder" >&2; exit 64;; esac
[ "${RNPLENS_JAIL_PRINT_PROFILE:-}" = 1 ] && { printf '%s\n' "$P"; exit 0; }    # review only; runs nothing
CMD=("$BIN" "$@")
if [ $MODE = probe ]; then
  HID=${RNPLENS_JAIL_PROBE_HIDDEN:-/nonexistent-probe-target}
  CMD=(/bin/bash -c 'h=$1; if [ -d "$h" ]; then /bin/ls "$h" >/dev/null 2>&1 && exit 3; elif [ -e "$h" ]; then /bin/cat "$h" >/dev/null 2>&1 && exit 3; fi
    /bin/cat "$CODEX_HOME/auth.json" >/dev/null 2>&1 || exit 4; /usr/bin/touch "$2/.probe" || exit 5; [ -x "$3" ] || exit 6; echo JAIL_OK' probe "$HID" "$CALL" "$BIN")
elif [ $MODE = test ]; then
  CMD=("$@")
fi
# Configuration discovery must start inside the permitted call folder. An inherited
# outside cwd is unreadable under this profile (getcwd fails before Codex can load
# configuration); do not grant access to the caller's project to work around it.
cd -- "$CALL" || { echo "codex_seatbelt: cannot enter CALLDIR" >&2; exit 64; }
exec /usr/bin/env -i HOME="$CALL/.home" CODEX_HOME="$JH" TMPDIR="$CALL/.tmp/" PATH=/usr/bin:/bin LANG=en_US.UTF-8 \
  "$SBX" -p "$P" "${CMD[@]}"
