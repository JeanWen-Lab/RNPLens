"""Deterministic order of a command's stdout and stderr when both go to one file (``cmd >> log 2>&1``).

A redirected stdout is block-buffered (8192 bytes in CPython) while stderr is written at once, so in a combined log
the stderr lines land before or after the stdout text depending on how long that text is - and the text holds
absolute paths, so the order depended on where a project lives (found by the v2 retest at 5b15730). ``install()``
makes both streams line-buffered and flushes stdout before every stderr write, so the combined order is the order in
which the program wrote. It is called by the process entry points (``rnplens`` / ``python -m rnplens`` and
``python -m rnplens_assistant``) only, never on import; nothing written to either stream changes.
"""
import sys

_MARK = "_rnplens_ordered_output"


class _StderrAfterStdout:
    """stderr proxy: flushes stdout before each write, and itself after it."""

    def __init__(self, err):
        object.__setattr__(self, "_err", err)
        object.__setattr__(self, _MARK, True)

    def write(self, s):
        out = sys.stdout
        if out is not None and out is not self:
            try:
                out.flush()
            except Exception:
                pass
        n = self._err.write(s)
        self._err.flush()
        return n

    def writelines(self, lines):
        for x in lines:
            self.write(x)

    def flush(self):
        self._err.flush()

    def __getattr__(self, name):
        return getattr(self._err, name)


def installed():
    return bool(getattr(sys.stderr, _MARK, False))


def install():
    """Idempotent. Streams that cannot be reconfigured (e.g. a test harness's capture objects) are left as they are."""
    if installed() or sys.stderr is None:
        return
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(line_buffering=True)
        except Exception:
            pass
    sys.stderr = _StderrAfterStdout(sys.stderr)
