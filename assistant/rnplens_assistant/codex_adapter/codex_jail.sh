#!/bin/bash
# codex_jail.sh CALLDIR -- codex exec ARGS...
# Runs Codex in a bubblewrap mount namespace that contains only:
#   read-only system directories (/usr and a few /etc files), the Codex installation (read-only), the ChatGPT login file
#   (bound, never copied or read by this script), a private tmpfs CODEX_HOME, and CALLDIR as /work.
# Nothing else of the host filesystem exists inside: no home directory contents, no project folders, no references.
# Portable across users (0.4): CODEX_HOME defaults to $HOME/.codex; the Codex binary is the standalone installer's
# ($CODEX_HOME/packages/standalone/current/bin/codex) or RNPLENS_CODEX_BIN (its directory is bound read-only).
# That directory is bound read-only IN FULL, so it must be a folder of its own: a home directory, a root or a
#   shared system or scratch folder is REFUSED (exit 64) before anything is started. See check_pkg_folder below.
# Self-probe without any model call: RNPLENS_JAIL_PROBE=1 [RNPLENS_JAIL_PROBE_HIDDEN=/a/host/path] codex_jail.sh DIR --
#   prints JAIL_OK only if the hidden path does not exist inside, the login file is present and /work is writable.
set -u
ME=codex_jail
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
CALL=$(realpath "$1"); shift; [ "${1:-}" = "--" ] && shift
mkdir -p "$CALL/.codex_sessions"
H=${HOME:?HOME must be set}
CH=${CODEX_HOME:-$H/.codex}
HR=$(realpath "$H" 2>/dev/null) || HR=$H
if [ -n "${RNPLENS_CODEX_BIN:-}" ]; then
  BIN=$(realpath "$RNPLENS_CODEX_BIN"); PKG=$(dirname "$BIN")
else
  PKG=$(realpath "$CH/packages/standalone/current" 2>/dev/null) || { echo "codex_jail: no standalone Codex under $CH and RNPLENS_CODEX_BIN not set" >&2; exit 64; }
  BIN=$PKG/bin/codex
fi
# A binary under /usr/ needs no grant of its own: /usr is already bound read-only in full, so the bind
# below is skipped and there is nothing to validate. Every other folder is granted and must pass the rule.
case "$PKG" in /usr/*) PKGBIND=0;; *) PKGBIND=1;; esac
if [ "$PKGBIND" = 1 ]; then check_pkg_folder "$PKG" "$HR"; fi
[ -x "$BIN" ] || { echo "codex_jail: $BIN is not executable" >&2; exit 64; }
[ -f "$CH/auth.json" ] || { echo "codex_jail: no ChatGPT login file in $CH (run 'codex login')" >&2; exit 65; }
ro=(); for d in /etc/ssl /etc/ca-certificates /etc/resolv.conf /etc/hosts /etc/nsswitch.conf /etc/passwd /etc/group /etc/localtime /etc/pki; do [ -e $d ] && ro+=(--ro-bind $d $d); done
pkgbind=(); if [ "$PKGBIND" = 1 ]; then pkgbind=(--ro-bind "$PKG" "$PKG"); fi
CMD=("$BIN" "$@")
if [ "${RNPLENS_JAIL_PROBE:-}" = 1 ]; then
  HID=${RNPLENS_JAIL_PROBE_HIDDEN:-/nonexistent-probe-target}
  CMD=(/usr/bin/sh -c '[ ! -e "$1" ] && [ -f "$CODEX_HOME/auth.json" ] && touch /work/.probe && [ -x "$2" ] && echo JAIL_OK' probe "$HID" "$BIN")
fi
exec env -u OPENAI_API_KEY -u CODEX_API_KEY bwrap \
  --ro-bind /usr /usr --symlink usr/lib /lib --symlink usr/lib64 /lib64 --symlink usr/bin /bin --symlink usr/sbin /sbin \
  "${ro[@]}" --proc /proc --dev /dev --tmpfs /tmp \
  --dir "$H" --tmpfs "$CH" \
  "${pkgbind[@]}" --bind "$CH/auth.json" "$CH/auth.json" \
  --bind "$CALL" /work --chdir /work --bind "$CALL/.codex_sessions" "$CH/sessions" \
  --unshare-all --share-net --die-with-parent --new-session \
  --clearenv --setenv HOME "$H" --setenv CODEX_HOME "$CH" --setenv PATH /usr/bin:/bin --setenv LANG C.UTF-8 \
  --setenv SSL_CERT_DIR /etc/ssl/certs \
  "${CMD[@]}"
