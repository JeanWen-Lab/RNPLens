"""RNPLens viewer track r2: build the owner's real-screen check package from six viewer pages.

usage: python make_package.py PAGES_JSON COVERAGE_JSON OUT_DIR SOURCE_COMMIT [OWNER_SCREEN_CHECK_MD]

Writes OUT_DIR/RNPLens_owner_screen_check/ (pages/<short>/ = unchanged copies of each viewer folder, index.html,
expected_highlights.json, PACKAGE_MANIFEST.json) and OUT_DIR/RNPLens_owner_screen_check.zip (deterministic: sorted
entries, fixed timestamps). Also scans every file for the excluded target identifiers and for absolute paths, and
records what it found in PACKAGE_MANIFEST.json (nothing is rewritten)."""
import hashlib
import html
import json
import os
import re
import shutil
import sys
import zipfile

EXCLUDED = ("3WZI 4DWA 4KR6 4OHZ 4PMI 4RCJ 4RDX 5B63 5FN1 5HSW 5MSF 5U30 5X2G 6DCB 6E4P 6LT7 6M7K 6NY2 6O6V 6O7B 6P7P "
            "6SCE 6W11 6XMF 7QQK 7S7C 7UZW 7VYX 7XG1 7XS4 8PSQ 8UMF 8WO8 9JXX 9RVP 9U49 9YLU").split()
ABS = re.compile(r"(?:/home/[A-Za-z0-9_.-]+|/Users/[A-Za-z0-9_.-]+|/mnt/[A-Za-z0-9_.-]+|[A-Za-z]:\\\\Users)")
SHORT = {"demo1_1VTM_rna1-3": "1_1VTM_RNA_1-3", "demo1b_2JEA_rna26-35": "1b_2JEA_RNA_26-35",
         "demo3_6BJG_reps_t0.3": "3_6BJG_representatives_t0.3", "demo3_6BJG_reps_t0.5": "3_6BJG_representatives_t0.5",
         "demo3_6BJG_reps_t0.7": "3_6BJG_representatives_t0.7", "demo3_6BJG_all50": "3_6BJG_all_50"}
STATUS = ("Viewer status: automatically tested, awaiting manual visual confirmation; not fully visually qualified.")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def visible_text(html_text):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html_text)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return html.unescape(t)


def main(argv):
    pages = json.load(open(argv[0]))
    cov = {p["page_id"]: p for p in json.load(open(argv[1]))["pages"]}
    out, commit = argv[2], argv[3]
    root = os.path.join(out, "RNPLens_owner_screen_check")
    if os.path.exists(root):
        raise SystemExit("refused: %s exists" % root)
    os.makedirs(os.path.join(root, "pages"))
    expected, rows = {}, []
    for pg in pages:
        short = SHORT.get(pg["page_id"], pg["page_id"])
        src = os.path.join(pg["package"], pg["viewer_dir"])
        shutil.copytree(src, os.path.join(root, "pages", short))
        c = cov[pg["page_id"]]
        expected[short] = {"page": "pages/%s/viewer.html" % short, "region": c["range"], "structures": [
            {"snapshot": i + 1, "label": s["label"], "group": s["group"], "chains": s["chains"],
             "protein_residues": s["expected"]["protein"], "rna_residues": s["expected"]["rna"]} for i, s in enumerate(c["structures"])]}
        rows.append((short, len(c["structures"]), c["range"]))
    idx = ["<!DOCTYPE html>", '<html lang="en"><head><meta charset="utf-8">',
           "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'self' file:; style-src 'unsafe-inline'\">",
           "<title>RNPLens offline viewer: real-screen check</title>",
           "<style>body{font-family:sans-serif;margin:2em;max-width:60em} td,th{border:1px solid #ccc;padding:3px 8px}"
           " table{border-collapse:collapse} .lim{background:#f6f6f6;padding:.4em;border-left:3px solid #999}</style></head><body>",
           "<h1>RNPLens offline viewer: real-screen check</h1>", '<p class="lim">%s</p>' % html.escape(STATUS),
           "<p>Six offline pages written by <code>rnplens view</code> (RNPLens 0.4 development candidate, commit %s). "
           "Open each page from this folder with networking off. The steps and the result form are in "
           "<code>OWNER_SCREEN_CHECK.md</code>; the expected highlighted residues of every structure are in "
           "<code>expected_highlights.json</code>.</p>" % html.escape(commit[:7]),
           "<table><tr><th>page</th><th>structures</th><th>RNA region</th></tr>"]
    for short, n, rng in rows:
        idx.append('<tr><td><a href="pages/%s/viewer.html">%s</a></td><td>%d</td><td>%s</td></tr>' % (
            short, html.escape(short), n, "%d-%d" % tuple(rng) if rng else "all contacts"))
    idx += ["</table>", "<p>Highlighted residues are Report's per-structure contacts; a highlighted contact is a feature of "
            "the prediction, not an observation of the real complex, and nothing here measures correctness.</p>", "</body></html>"]
    with open(os.path.join(root, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(idx) + "\n")
    if len(argv) > 4:
        shutil.copyfile(argv[4], os.path.join(root, "OWNER_SCREEN_CHECK.md"))
    with open(os.path.join(root, "expected_highlights.json"), "w") as fh:
        json.dump(expected, fh, indent=1, sort_keys=True)
    # scans
    files = sorted(os.path.relpath(os.path.join(d, f), root) for d, _, fs in os.walk(root) for f in fs)
    excl_hits, abs_hits, vis_abs = [], {}, []
    for rel in files:
        for t in EXCLUDED:
            if t.lower() in rel.lower():
                excl_hits.append({"file": rel, "id": t, "where": "file name"})
        if rel.endswith((".pdb.js", "molstar.js", "molstar.css")):
            continue          # structure scripts are the same bytes as the .pdb next to them; Mol* assets are the release
        txt = open(os.path.join(root, rel), encoding="latin-1").read()
        for t in EXCLUDED:
            if re.search(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % t, txt, re.I):
                excl_hits.append({"file": rel, "id": t, "where": "content"})
        m = ABS.findall(txt)
        if m:
            abs_hits[rel] = {"count": len(m), "prefixes": sorted(set(m))}
        if rel.endswith(".html"):
            vm = ABS.findall(visible_text(txt))
            if vm:
                vis_abs.append({"file": rel, "prefixes": sorted(set(vm))})
    manifest = {"record": "rnplens-owner-screen-check-package-1", "source_commit": commit, "status": STATUS,
                "pages": [{"page": "pages/%s/viewer.html" % r[0], "structures": r[1], "region": r[2]} for r in rows],
                "excluded_target_hits": excl_hits, "absolute_path_hits_in_files": abs_hits,
                "absolute_path_hits_in_visible_page_text": vis_abs,
                "note": "files under pages/ are unchanged copies of the rnplens view output; viewer_manifest.json keeps its "
                        "provenance (absolute paths of the machine that built the pages), listed above",
                "files": {rel: sha(os.path.join(root, rel)) for rel in files}}
    with open(os.path.join(root, "PACKAGE_MANIFEST.json"), "w") as fh:
        json.dump(manifest, fh, indent=1, sort_keys=True)
    zp = os.path.join(out, "RNPLens_owner_screen_check.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(files + ["PACKAGE_MANIFEST.json"]):
            zi = zipfile.ZipInfo("RNPLens_owner_screen_check/" + rel, date_time=(2026, 10, 17, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            with open(os.path.join(root, rel), "rb") as fh:
                z.writestr(zi, fh.read())
    print(json.dumps({"zip": zp, "sha256": sha(zp), "bytes": os.path.getsize(zp), "n_files": len(files) + 1,
                      "excluded_target_hits": len(excl_hits), "files_with_absolute_paths": sorted(abs_hits),
                      "visible_text_absolute_paths": vis_abs}))


if __name__ == "__main__":
    main(sys.argv[1:])
