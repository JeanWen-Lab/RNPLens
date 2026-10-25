"""0.4 usability: the contact tables and the offline Mol* page that belong to an analysis, for the question menu and the
natural-language mode (owner programme 2026-10-18, section 6: "the assistant should link automatically to the produced
contact tables and the Mol* viewer").

Nothing new is computed about the structures. The contact tables are the files Report and the region functions wrote.
If the analysis has no viewer page yet, one is written with ``rnplens view PROJECT --analysis ANALYSIS`` (the
unchanged viewer, ANALYSIS/viewer/); if that is not possible here, the command is shown instead.
"""
import contextlib
import io
import os

CONTACT_ITEMS = ("A", "B", "C", "E")          # menu items whose results are contacts of the analysis
TABLES = (("Report per-structure contacts", os.path.join("report", "contacts_by_output.json")),
          ("Report result (contacts, agreement)", os.path.join("report", "result.json")))


def links(project, analysis, write_viewer=True):
    """-> {"contact_tables": [[label, path]], "viewer": path or None, "viewer_command": str or None, "viewer_note": str}"""
    out = {"contact_tables": [], "viewer": None, "viewer_command": None, "viewer_note": None}
    if not analysis or not os.path.isdir(analysis):
        return out
    analysis = os.path.abspath(analysis)
    for label, rel in TABLES:
        if os.path.isfile(os.path.join(analysis, rel)):
            out["contact_tables"].append([label, os.path.join(analysis, rel)])
    for d in sorted(os.listdir(analysis)):
        t = os.path.join(analysis, d, "region_contacts.tsv")
        if d.startswith("region_") and os.path.isfile(t):
            out["contact_tables"].append(["region %s contacts" % d[len("region_"):], t])
    if not project or not os.path.isfile(os.path.join(analysis, "report", "contacts_by_output.json")):
        return out
    project = os.path.abspath(project)
    page = os.path.join(analysis, "viewer", "viewer.html")
    out["viewer_command"] = "rnplens view %s --analysis %s" % (project, analysis)
    if not os.path.isfile(page) and write_viewer:
        buf = io.StringIO()
        try:
            from . import viewer
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                rc = viewer.main([project, "--analysis", analysis])
            if rc != 0:
                out["viewer_note"] = "not written here: " + ((buf.getvalue().strip().splitlines() or ["exit %s" % rc])[-1])[:300]
        except Exception as ex:                       # the result itself stands; only the page is missing
            out["viewer_note"] = "not written here: %s" % str(ex).splitlines()[0][:300] if str(ex) else "not written here"
    if os.path.isfile(page):
        out["viewer"] = page
    return out


def text(L):
    lines = []
    if L.get("contact_tables"):
        lines.append("  contact tables:")
        lines += ["    %s: %s" % (lab, p) for lab, p in L["contact_tables"]]
    if L.get("viewer"):
        lines.append("  structure viewer (offline Mol* page; open it from disk): %s" % L["viewer"])
    elif L.get("viewer_command"):
        lines.append("  structure viewer: %s%s" % (L["viewer_command"], " (%s)" % L["viewer_note"] if L.get("viewer_note") else ""))
    return lines
