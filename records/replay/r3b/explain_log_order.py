"""Diagnostic for the post-amendment v2 failure (not part of any frozen contract).

usage: python explain_log_order.py OUT_JSON ROOT...

For every <tree>/logs/10_explain_evidence.log under each ROOT (tmp_* excluded):
  stdout_body_bytes  bytes of the log after its first line ('$ command'), without the '  written:' lines
                     (those are printed to stderr by rnplens.evidence_query; the rest is stdout);
  written_early      True if the '  written:' lines come right after the command line.
Hypothesis checked: written_early == (stdout_body_bytes <= 8192), i.e. CPython's default 8 KiB block buffer of a
redirected stdout is flushed at exit (after the unbuffered stderr lines) unless the body exceeds it.
"""
import glob
import json
import sys


def main(out, *roots):
    rows = []
    for r in roots:
        for f in sorted(glob.glob(r.rstrip("/") + "/**/logs/10_explain_evidence.log", recursive=True)):
            if "/tmp_" in f:
                continue
            L = open(f, "rb").read().split(b"\n")
            body = [x for x in L[1:] if not x.startswith(b"  written:")]
            n = len(b"\n".join(body))
            early = any(x.startswith(b"  written:") for x in L[1:4])
            rows.append({"log": f, "stdout_body_bytes": n, "written_early": early, "predicted_early": n <= 8192})
    ok = all(x["written_early"] == x["predicted_early"] for x in rows)
    json.dump({"n_logs": len(rows), "hypothesis_holds_for_all": ok, "logs": rows}, open(out, "w"), indent=1, sort_keys=True)
    open(out, "a").write("\n")
    print(len(rows), "logs; hypothesis holds for all:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
