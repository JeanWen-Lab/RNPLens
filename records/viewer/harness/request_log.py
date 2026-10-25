"""Inspection aid: every request the browser logged, per page and run, as TSV (run, scheme, type, url relative to the
page folder when inside it). usage: python request_log.py RESULTS_DIR OUT_DIR"""
import glob, json, os, sys
res, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for d in sorted(glob.glob(os.path.join(res, "*", ""))):
    pid = os.path.basename(os.path.dirname(d))
    rows = ["run\tsource\tscheme\ttype\turl"]
    for run in ("offline", "netlog"):
        r = json.load(open(os.path.join(d, "result_%s.json" % run)))
        base = "file://" + os.path.dirname(r["page"]) + "/"
        for q in r["requests"]:
            u = q["url"]
            if u.startswith("data:"):
                u = u[:40] + "...(%d chars)" % len(q["url"])
            elif u.startswith(base):
                u = "./" + u[len(base):]
            rows.append("\t".join([run, q.get("via", "cdp"), q["url"].split(":", 1)[0], str(q.get("type")), u]))
        for w in r["websockets"]:
            rows.append("\t".join([run, "websocket", w.split(":", 1)[0], "websocket", w]))
        for v in r["csp_violations"] or []:
            rows.append("\t".join([run, "csp-violation", "", v["directive"], v["blockedURI"]]))
    open(os.path.join(out, "requests_%s.tsv" % pid), "w").write("\n".join(rows) + "\n")
    print(pid, len(rows) - 1)
