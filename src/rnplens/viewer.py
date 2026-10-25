"""Local, offline structure page built on the vendored Mol* Viewer (no new renderer).

`structure_page(out_dir, structures=[{path, label}], highlights={...})` writes, inside `out_dir` only:

    viewer.html                     the page (opens from the local disk; no network address anywhere in it)
    assets/molstar.js, molstar.css  copies of the vendored, hash-checked Mol* release (src/rnplens/vendor/molstar)
    assets/LICENSE.molstar.txt      the Mol* MIT licence; assets/VERSION.molstar.json its version record
    structures/<nn>_<label>.<ext>   copies of the given structure files (loaded by relative path)
    structures/<nn>_<label>.<ext>.js  the same bytes wrapped as a script, because browsers refuse to let a page opened
                                    from disk read a neighbouring file with fetch; a <script src> by relative path is allowed
    view.mvsj, view_data.js         the MolViewSpec state (residue colours, labels, tooltips) as JSON and as a script;
                                    view_data.js also carries the contact-explorer data (below)
    assets/contact_explorer.js      the RNPLens contact explorer (src/rnplens/viewer_assets; not part of Mol*)
    viewer_manifest.json            provenance, every written file with SHA-256, the highlighted residues and evidence IDs

The page assembles the MolViewSpec state and the structure copies into an in-memory MVSX archive and hands it to
Mol*'s own `loadMvsData`; nothing is fetched. A Content-Security-Policy restricts connections to the page's own
origin and in-memory data, so the remote-database buttons of the Mol* interface cannot reach the network either.

Highlights are the residues the caller supplies (for example a region's contacts from Report's records). The page
shows where they are in each predicted structure and says nothing about the real complex.

Contact explorer (0.4 feature/nt-contact-explorer): one structure is shown at a time (structure selector above the
panel). Clicking an RNA nucleotide shows, for the structure on screen only, the protein residues Report's record lists
in contact with it (magenta selection, orange partners, dashed contact lines, a panel table); clicking a protein residue
shows its RNA partners. Report's record (contacts_by_output.json) is the only source of which residues are in contact.
Minimum heavy-atom distances are recomputed by rnplens.contact_explorer and displayed only for structures whose
recomputed contact set equals Report's record (distance check PASS); otherwise 'Not available'. A per-engine count of
how many structures list the same contact is shown separately, with its denominator and structure ids."""
import html
import json
import os
import re
import shutil

from . import provenance as pv

VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "molstar")
ASSET_FILES = ("molstar.js", "molstar.css", "LICENSE")
EXPLORER_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer_assets", "contact_explorer.js")
PAGE = "viewer.html"
FORMATS = {".pdb": "pdb", ".ent": "pdb", ".cif": "mmcif", ".mmcif": "mmcif", ".bcif": "bcif"}
COLOURS = {"protein": "#BBBBBB", "rna": "#DDCC77", "protein_highlight": "#E69F00", "rna_highlight": "#0072B2",
           "selected": "#CC00CC", "line": "#CC00CC"}
# Cartoon opacity of unrelated parts while a residue is selected (focus mode). Mol* picks only geometry with opacity
# >= 0.5 (Canvas3D pickingAlphaThreshold): the dimmed RNA stays clickable, the dimmed protein lets clicks pass through.
DIM = {"protein": 0.3, "rna": 0.6}
LINE = {"radius": 0.07, "dash_length": 0.25}
FOCUS_EXTENT_A = 12.0      # focus mode frames the selection plus this many A, so neighbouring nucleotides stay in view
MAX_LABELS = 40          # beyond this many residues per molecule, residues get tooltips only (labels would overlap)
CSP = ("default-src 'self' file: blob: data: 'unsafe-inline' 'unsafe-eval'; connect-src 'self' blob: data:; "
       "img-src 'self' file: blob: data:; worker-src 'self' file: blob:")
STATUS = ("Viewer status: automatically tested; basic on-screen display and interaction confirmed manually by the "
          "owner on macOS (2026-10-18, 2JEA page); switching between binding-hypothesis representatives and offline "
          "operation not yet confirmed manually; not fully visually qualified "
          "(records/viewer/MOLSTAR_VISUAL_VERIFICATION.md).")
LIMITS = ("Highlighted residues are the ones supplied to this page (for example contacts in a declared region taken "
          "from RNPLens Report's per-structure records). The page shows where they lie in each predicted structure; "
          "which residues count as contacts is taken from Report's record, not decided by the page. A highlighted "
          "contact is a feature of the prediction, not an observation of the real complex. When the page is written, "
          "RNPLens recomputes the contacts and their minimum heavy-atom distances from each structure file as a check; "
          "the contact explorer shows those distances only for structures whose recomputed contacts equal Report's "
          "record, and otherwise shows 'Not available'.")
ENSEMBLE_LIMITS = ("Ensemble support counts how many predictions of one engine list a contact. It is shown separately "
                   "from the structure on screen, engines are never pooled, and a frequent contact is not thereby an "
                   "observed or more trustworthy one: recurrence among predictions is not evidence about the real complex.")


class ViewerError(ValueError):
    pass


def vendor_record(vendor_dir=None):
    with open(os.path.join(vendor_dir or VENDOR, "VERSION.json"), encoding="utf-8") as fh:
        return json.load(fh)


def verify_assets(vendor_dir=None):
    """{'ok', 'version', 'problems': [...], 'files': {name: sha256}} for the vendored Mol* files (never raises)."""
    vendor_dir = vendor_dir or VENDOR
    out = {"ok": False, "version": None, "problems": [], "files": {}}
    try:
        rec = vendor_record(vendor_dir)
    except (OSError, ValueError) as ex:
        out["problems"].append("VERSION.json unreadable: %s" % ex)
        return out
    out["version"] = rec.get("version")
    for name in ASSET_FILES:
        p = os.path.join(vendor_dir, name)
        want = (rec.get("files", {}).get(name) or {}).get("sha256")
        if not os.path.isfile(p):
            out["problems"].append("%s missing" % name)
            continue
        got = pv.sha256_file(p)
        out["files"][name] = got
        if want is None:
            out["problems"].append("%s has no recorded SHA-256 in VERSION.json" % name)
        elif got != want:
            out["problems"].append("%s SHA-256 %s differs from VERSION.json %s" % (name, got[:12], want[:12]))
    out["ok"] = not out["problems"]
    return out


def _safe(s):
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", str(s)).strip("._")
    return s[:60] or "structure"


def _js_literal(obj):
    """JSON for embedding inside <script>: no '</' sequence can close the script element."""
    return json.dumps(obj, ensure_ascii=True, sort_keys=True).replace("</", "<\\/").replace("<!--", "<\\!--")


def _residues(items, molecule, where):
    out = []
    for i, r in enumerate(items or []):
        if isinstance(r, (list, tuple)) and len(r) == 2:
            r = {"chain": r[0], "residue": r[1]}
        if not isinstance(r, dict):
            raise ViewerError("%s %s[%d]: a residue is a dict {residue, chain?, label?, evidence_id?}" % (where, molecule, i))
        res = r.get("residue")
        if isinstance(res, bool) or not isinstance(res, int):
            raise ViewerError("%s %s[%d]: residue must be an integer residue number, got %r" % (where, molecule, i, res))
        ch = r.get("chain")
        if ch is not None and (not isinstance(ch, str) or not ch.strip()):
            raise ViewerError("%s %s[%d]: chain must be a non-empty string" % (where, molecule, i))
        out.append({"molecule": molecule, "chain": ch, "residue": res, "label": str(r.get("label") or "%s %d" % (molecule, res)),
                    "evidence_id": r.get("evidence_id"), "structure": r.get("structure")})
    return out


def _check_highlights(h, where):
    if h is None:
        return []
    if not isinstance(h, dict):
        raise ViewerError("%s: highlights must be a dict {'protein': [...], 'rna': [...]}" % where)
    extra = set(h) - {"protein", "rna", "title"}
    if extra:
        raise ViewerError("%s: unknown highlight keys %s" % (where, sorted(extra)))
    return _residues(h.get("protein"), "protein", where) + _residues(h.get("rna"), "rna", where)


def _chain_for(res, s):
    if res["chain"]:
        return res["chain"]
    ch = (s.get("chains") or {}).get(res["molecule"])
    if not ch:
        raise ViewerError("structure %r: residue %s %d has no chain and the structure declares no %s chain"
                          % (s["label"], res["molecule"], res["residue"], res["molecule"]))
    return ch


def _mvs_root(rel, fmt, residues, title):
    # Highlighted residues are coloured inside the one cartoon of their molecule (a colour node with a selector, which
    # MolViewSpec applies over the molecule colour). A second, highlight-coloured cartoon on the same residues was seen
    # to render in the molecule colour in Mol* 5.13.1 (viewer-track rendering check,
    # records/viewer/MOLSTAR_VISUAL_VERIFICATION.md), so the ribbon of a highlighted residue did not show its colour.
    sel = {mol: [{"auth_asym_id": r["chain_resolved"], "auth_seq_id": r["residue"]} for r in residues if r["molecule"] == mol]
           for mol in ("protein", "rna")}

    def base(selector, mol):
        colours = [{"kind": "color", "params": {"color": COLOURS[mol]}}]
        if sel[mol]:
            colours.append({"kind": "color", "params": {"color": COLOURS[mol + "_highlight"], "selector": sel[mol]}})
        return {"kind": "component", "params": {"selector": selector}, "children": [
            {"kind": "representation", "params": {"type": "cartoon"}, "children": colours}]}

    comps = [base("protein", "protein"), base("nucleic", "rna")]
    focus_done = False
    for mol in ("protein", "rna"):
        rs = [r for r in residues if r["molecule"] == mol]
        if not rs:
            continue
        kids = [{"kind": "representation", "params": {"type": "ball_and_stick"}, "children": [
                    {"kind": "color", "params": {"color": COLOURS[mol + "_highlight"]}}]},
                {"kind": "tooltip", "params": {"text": "%s: highlighted %s residues (%d)" % (title, mol, len(rs))}}]
        if not focus_done:
            kids.append({"kind": "focus", "params": {}})
            focus_done = True
        comps.append({"kind": "component", "params": {"selector": sel[mol]}, "children": kids})
        if len(rs) <= MAX_LABELS:
            for r in rs:
                comps.append({"kind": "component", "params": {"selector": {"auth_asym_id": r["chain_resolved"], "auth_seq_id": r["residue"]}},
                              "children": [{"kind": "label", "params": {"text": r["label"]}}]})
    return {"kind": "root", "children": [
        {"kind": "canvas", "params": {"background_color": "#FFFFFF"}},
        {"kind": "download", "params": {"url": rel}, "children": [
            {"kind": "parse", "params": {"format": fmt}, "children": [
                {"kind": "structure", "params": {"type": "model"}, "children": comps}]}]}]}


def _page(title, entries, residues_table, vendor_version):
    rows = "\n".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%d</td><td>%s</td><td><code>%s</code></td></tr>" % (
        html.escape(r["structure_label"]), html.escape(r["molecule"]), html.escape(r["chain_resolved"]), r["residue"],
        html.escape(r["label"]), html.escape(r["evidence_id"] or "")) for r in residues_table)
    files = "\n".join("<li><code>%s</code> (%s)</li>" % (html.escape(e["rel"]), html.escape(e["label"])) for e in entries)
    scripts = "\n".join('<script src="%s"></script>' % html.escape(e["rel"] + ".js", quote=True) for e in entries)
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="%(csp)s">
<title>%(title)s</title>
<link rel="stylesheet" type="text/css" href="assets/molstar.css">
<style>
body { font-family: sans-serif; margin: 0; }
#top { display: flex; height: 72vh; }
#app { position: relative; flex: 1 1 auto; min-width: 0; height: 100%%; }
#rnplens-explorer { flex: 0 0 400px; height: 100%%; overflow: auto; box-sizing: border-box; padding: 0.4em 0.7em;
  font-size: 13px; border-left: 1px solid #ccc; }
#rnplens-explorer .ctl { margin: 0.2em 0 0.5em 0; line-height: 2em; }
#rnplens-explorer h4 { margin: 0.6em 0 0.2em 0; }
#rnplens-explorer select { max-width: 100%%; }
.rx-table, .rx-kv { font-size: 12px; }
.rx-note { color: #7a3d00; } .rx-small { font-size: 11px; color: #444; } .rx-ids { font-size: 11px; word-break: break-word; }
#side { padding: 0.5em 1em; font-size: 13px; }
table { border-collapse: collapse; } td, th { border: 1px solid #ccc; padding: 2px 6px; }
.lim { background: #f6f6f6; padding: 0.4em; border-left: 3px solid #999; }
.key span { display: inline-block; width: 1em; height: 1em; vertical-align: middle; margin: 0 0.3em 0 1em; }
</style>
</head>
<body>
<div id="top">
<div id="app"></div>
<div id="rnplens-explorer" data-state="PENDING">
<b>Contact explorer</b>
<div class="ctl">
<button id="rx-prev" type="button">&#9664; Previous</button> <button id="rx-next" type="button">Next &#9654;</button>
<select id="rx-structure" aria-label="Structure on screen"></select><br>
<label><input type="radio" name="rx-mode" value="focus" checked> Focus on selected nucleotide</label>
<label><input type="radio" name="rx-mode" value="all"> Show all contacts</label><br>
<button id="rx-clear" type="button">Clear selection</button>
</div>
<div id="rx-panel"><p>Loading the local viewer.</p></div>
<div class='lim'>%(ens_limits)s</div>
</div>
</div>
<div id="side">
<h2>%(title)s</h2>
<p id="rnplens-viewer-status" class="lim">%(status)s</p>
<p id="rnplens-status" data-state="PENDING">PENDING: loading the local viewer</p>
<p class="key">Colours:<span style="background:%(cp)s"></span>protein<span style="background:%(cr)s"></span>RNA<span style="background:%(cph)s"></span>highlighted protein residue<span style="background:%(crh)s"></span>highlighted RNA residue<span style="background:%(cs)s"></span>selected residue (contact explorer; dashed lines: its contacts)</p>
<p>One structure is shown at a time: choose it with the structure selector or Previous / Next beside the viewer.
Click an RNA nucleotide to see the protein residues in contact with it in that structure (or a protein residue to see
its RNA nucleotides). Click the same residue again, or Clear selection, to return to the overall view.</p>
<div class='lim'>%(limits)s</div>
<h3>Structures (copies in this folder)</h3>
<ul>
%(files)s
</ul>
<h3>Highlighted residues</h3>
<table><tr><th>structure</th><th>molecule</th><th>chain</th><th>residue</th><th>label</th><th>evidence ID</th></tr>
%(rows)s
</table>
<p>Viewer: Mol* %(ver)s (MIT licence, <code>assets/LICENSE.molstar.txt</code>), used unchanged.</p>
</div>
<script src="assets/molstar.js"></script>
<script>window.RNPLENS_STRUCTURE_DATA = {};</script>
%(scripts)s
<script src="view_data.js"></script>
<script src="assets/contact_explorer.js"></script>
<script>
(function () {
  var st = document.getElementById('rnplens-status');
  function say(state, text) { st.setAttribute('data-state', state); st.textContent = state + ': ' + text; }
  var V = window.RNPLENS_VIEW, D = window.RNPLENS_STRUCTURE_DATA;
  if (typeof molstar === 'undefined') { say('ERROR', 'assets/molstar.js did not load'); return; }
  if (!V) { say('ERROR', 'view_data.js did not load'); return; }
  if (typeof window.RNPLENS_EXPLORER_START !== 'function') { say('ERROR', 'assets/contact_explorer.js did not load'); return; }
  for (var i = 0; i < V.structures.length; i++) {
    if (typeof D[V.structures[i]] !== 'string') { say('ERROR', 'structure data script missing for ' + V.structures[i]); return; }
  }
  var issues = molstar.lib.extensions.mvs.MVSData.validationIssues(V.mvs);
  if (issues) { say('ERROR', 'MolViewSpec state invalid: ' + issues.join('; ')); return; }
  molstar.Viewer.create('app', {
    layoutIsExpanded: false, layoutShowControls: true, layoutShowRemoteState: false, layoutShowSequence: true,
    layoutShowLog: true, layoutShowLeftPanel: true, collapseLeftPanel: true, viewportShowExpand: true,
    viewportShowSelectionMode: false, viewportShowAnimation: false
  }).then(function (viewer) {
    window.RNPLENS_VIEWER = viewer;
    return window.RNPLENS_EXPLORER_START(viewer);
  }).then(function () {
    var ex = document.getElementById('rnplens-explorer');
    return new Promise(function (ok, bad) {
      (function wait() { var s = ex.getAttribute('data-state'); if (s === 'READY') ok(); else if (s === 'ERROR') bad(new Error('first structure did not load')); else setTimeout(wait, 100); })();
    });
  }).then(function () {
    var loaded = V.structures.length + ' structure(s) loaded from this folder';
    var plugin = window.RNPLENS_VIEWER && window.RNPLENS_VIEWER.plugin;
    if (!(plugin && plugin.canvas3d)) {
      say('LOADED_NOT_DISPLAYED', loaded + ', but this browser made no WebGL context, so the 3D box stays empty and the structures are not being shown. The structure list, highlighted residues and the contact explorer still work.');
      return;
    }
    say('LOADED', loaded + '; one is shown at a time');
  }).catch(function (e) { say('ERROR', String(e && e.message ? e.message : e)); });
})();
</script>
</body>
</html>
""" % {"csp": html.escape(CSP, quote=True), "title": html.escape(title), "cp": COLOURS["protein"], "cr": COLOURS["rna"],
       "cph": COLOURS["protein_highlight"], "crh": COLOURS["rna_highlight"], "cs": COLOURS["selected"],
       "limits": html.escape(LIMITS), "ens_limits": html.escape(ENSEMBLE_LIMITS), "status": html.escape(STATUS), "files": files,
       "rows": rows, "ver": html.escape(str(vendor_version)), "scripts": scripts}


def structure_page(out_dir, structures, highlights=None, title="RNPLens structure view", provenance_inputs=None,
                   explorer=None):
    """Write the offline page into out_dir (created if needed; only files of this page are written there).

    structures: [{"path": file, "label": str, "chains": {"protein": "A", "rna": "B"} (optional),
                  "highlights": {...} (optional, replaces the shared highlights for this structure),
                  "explorer": rnplens.contact_explorer.structure_record(...) (optional; without it the contact
                              explorer says it is not available for that structure)}]
    highlights: {"protein": [{"residue": int, "chain": str?, "label": str?, "evidence_id": str?, "structure": label?}],
                 "rna": [...]} -- residue numbers are the structure file's own residue numbers (auth_seq_id); for an
                 imported project's used_path copies these equal construct positions. A residue without "chain" uses
                 the structure's declared chain for that molecule; one with "structure" applies to that label only.
    explorer: {"seq": {"protein": str, "rna": str}, "ensemble": contact_explorer.ensemble(...)} (optional, page-wide).
    Returns {"outputs": [page, manifest, ...], "page", "manifest", "evidence_ids"}."""
    chk = verify_assets()
    if not chk["ok"]:
        raise ViewerError("vendored Mol* assets failed their check: %s" % "; ".join(chk["problems"]))
    if not isinstance(structures, (list, tuple)) or not structures:
        raise ViewerError("structures must be a non-empty list of {path, label}")
    shared = _check_highlights(highlights, "highlights")
    out_dir = os.path.abspath(out_dir)
    if os.path.exists(out_dir) and not os.path.isdir(out_dir):
        raise ViewerError("out_dir %s exists and is not a directory" % out_dir)
    entries, labels = [], set()
    for i, s in enumerate(structures):
        if not isinstance(s, dict) or not s.get("path") or not isinstance(s.get("label"), str) or not s["label"].strip():
            raise ViewerError("structures[%d] must be {path, label} with a non-empty label" % i)
        src = os.path.abspath(s["path"])
        if not os.path.isfile(src):
            raise ViewerError("structures[%d]: %s is not a file" % (i, s["path"]))
        ext = os.path.splitext(src)[1].lower()
        if ext not in FORMATS:
            raise ViewerError("structures[%d]: unsupported file type %r (supported: %s)" % (i, ext, ", ".join(sorted(FORMATS))))
        if s["label"] in labels:
            raise ViewerError("structures[%d]: duplicate label %r" % (i, s["label"]))
        labels.add(s["label"])
        own = _check_highlights(s["highlights"], "structures[%d].highlights" % i) if "highlights" in s else None
        rel = "structures/%02d_%s%s" % (i + 1, _safe(s.get("file_label") or s["label"]), ext)
        rec = s.get("explorer")
        if rec is not None and not (isinstance(rec, dict) and {"chains", "residues", "contacts", "available"} <= set(rec)):
            raise ViewerError("structures[%d].explorer must be a record from rnplens.contact_explorer.structure_record" % i)
        entries.append({"src": src, "rel": rel, "label": s["label"], "format": FORMATS[ext], "chains": s.get("chains") or {},
                        "residues": own if own is not None else shared, "explorer": rec})
    for r in shared:
        if r["structure"] is not None and r["structure"] not in labels:
            raise ViewerError("highlight %s %d names unknown structure %r" % (r["molecule"], r["residue"], r["structure"]))

    table, snapshots, written = [], [], []
    for e in entries:
        rs = []
        for r in e["residues"]:
            if r["structure"] is not None and r["structure"] != e["label"]:
                continue
            r = dict(r, chain_resolved=_chain_for(r, e), structure_label=e["label"])
            rs.append(r)
        table += rs
        e["overview"] = {m: [{"chain": r["chain_resolved"], "residue": r["residue"]} for r in rs if r["molecule"] == m]
                         for m in ("protein", "rna")}
        snapshots.append({"root": _mvs_root(e["rel"], e["format"], rs, e["label"]),
                          "metadata": {"title": e["label"], "key": _safe(e["label"]),
                                       "description": "%s; %d highlighted residue(s)" % (e["label"], len(rs))}})
    meta = {"title": title, "version": "1", "timestamp": "1970-01-01T00:00:00Z",
            "description": "RNPLens structure view (residues supplied by the caller)"}
    mvs = ({"kind": "multiple", "snapshots": snapshots, "metadata": meta} if len(snapshots) > 1
           else {"root": snapshots[0]["root"], "metadata": meta})

    def put_bytes(rel, data):
        p = os.path.join(out_dir, rel)
        pv.atomic_write_bytes(p, data)
        written.append(rel)

    for name, rel in (("molstar.js", "assets/molstar.js"), ("molstar.css", "assets/molstar.css"),
                      ("LICENSE", "assets/LICENSE.molstar.txt"), ("VERSION.json", "assets/VERSION.molstar.json")):
        with open(os.path.join(VENDOR, name), "rb") as fh:
            put_bytes(rel, fh.read())
    with open(EXPLORER_JS, "rb") as fh:
        put_bytes("assets/contact_explorer.js", fh.read())
    for e in entries:
        with open(e["src"], "rb") as fh:
            data = fh.read()
        put_bytes(e["rel"], data)
        text = data.decode("latin-1") if e["format"] != "bcif" else None
        if text is None:
            raise ViewerError("binary CIF is not supported by the offline page; supply PDB or mmCIF")
        put_bytes(e["rel"] + ".js", ("window.RNPLENS_STRUCTURE_DATA[%s] = %s;\n" % (_js_literal(e["rel"]), _js_literal(text))).encode("ascii"))
    ex = explorer or {}
    from . import contact_explorer as CE
    view = {"structures": [e["rel"] for e in entries], "mvs": mvs,
            "explorer": {"version": 1, "colours": COLOURS, "dim": DIM, "line": LINE, "cutoff": CE.cutoff(),
                         "focus_extent_A": FOCUS_EXTENT_A,
                         "seq": ex.get("seq"), "ensemble": ex.get("ensemble"),
                         "structures": [{"label": e["label"], "rel": e["rel"], "format": e["format"], "overview": e["overview"],
                                         "rec": e["explorer"]} for e in entries]}}
    put_bytes("view.mvsj", (json.dumps(mvs, indent=1, sort_keys=True) + "\n").encode())
    put_bytes("view_data.js", ("window.RNPLENS_VIEW = %s;\n" % _js_literal(view)).encode("ascii"))
    page = _page(title, entries, table, chk["version"])
    put_bytes(PAGE, page.encode("utf-8"))

    ev = [r["evidence_id"] for r in table if r.get("evidence_id")]
    inputs = [{"path": e["src"], "sha256": pv.sha256_file(e["src"])} for e in entries] + list(provenance_inputs or [])
    man = {"provenance": pv.block("structure_view", inputs,
                                  "Offline Mol* page; structures copied unchanged; residues coloured and labelled as supplied by the caller",
                                  {"highlights": highlights, "title": title, "structures": [{"label": e["label"], "chains": e["chains"]} for e in entries]},
                                  extra={"viewer": {"package": "molstar", "version": chk["version"], "assets_sha256": chk["files"]}}),
           "page": PAGE, "limits": LIMITS, "viewer_status": STATUS,
           "structures": [{"label": e["label"], "source": e["src"], "copy": e["rel"], "format": e["format"], "chains": e["chains"]} for e in entries],
           "highlighted": [{k: r[k] for k in ("structure_label", "molecule", "chain_resolved", "residue", "label", "evidence_id")} for r in table],
           "contact_explorer": {"source": "report/contacts_by_output.json (Report's per-structure contact records)",
                                "ensemble_engines": sorted((ex.get("ensemble") or {}).keys()),
                                "structures": [{"label": e["label"], "available": bool(e["explorer"] and e["explorer"]["available"]),
                                                "reason": (e["explorer"] or {}).get("reason") if e["explorer"] else "no contact record supplied",
                                                "key": (e["explorer"] or {}).get("key"),
                                                "n_contact_rows": len((e["explorer"] or {}).get("contacts") or []),
                                                "distance_check": (e["explorer"] or {}).get("distance_check")} for e in entries]},
           "files": {rel: pv.sha256_file(os.path.join(out_dir, rel)) for rel in sorted(written)}}
    pv.atomic_write_json(os.path.join(out_dir, "viewer_manifest.json"), man)
    return {"outputs": [os.path.join(out_dir, PAGE), os.path.join(out_dir, "viewer_manifest.json")],
            "page": os.path.join(out_dir, PAGE), "manifest": os.path.join(out_dir, "viewer_manifest.json"),
            "evidence_ids": ev, "n_highlighted": len(table)}


# ---- helpers for imported projects (display only; they read the authoritative records and compute nothing new) ----

def project_structures(project_dir, ids=None):
    """[{path, label, chains}] for included structures of an imported project, using the construct-numbered used_path
    copy. A structure with other than exactly one protein and one RNA polymer chain is refused (no guessing)."""
    with open(os.path.join(project_dir, "manifest.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    from . import portability as PT                      # recorded structure files: resolved and hash-verified
    man = PT.check_manifest(project_dir, man, "read", "view")[0]
    out = []
    for s in man["structures"]:
        if s.get("verdict") != "INCLUDED" or (ids and s["id"] not in ids):
            continue
        poly = [c for c in s.get("chains", []) if c.get("status") != "NONPOLYMER_CHAIN"]
        prot = [c["chain"] for c in poly if c.get("type_by_report") == "protein"]
        rna = [c["chain"] for c in poly if c.get("type_by_report") == "rna"]
        if len(prot) != 1 or len(rna) != 1:
            raise ViewerError("structure %s: %d protein and %d RNA chains; supply chains explicitly" % (s["id"], len(prot), len(rna)))
        out.append({"path": s["used_path"], "label": "%s %s" % (s["id"], s.get("execution", "")), "chains": {"protein": prot[0], "rna": rna[0]},
                    "id": s["id"], "key": "%s|%s" % (s["engine"], s.get("execution", ""))})
    if ids:
        missing = set(ids) - {s["id"] for s in out}
        if missing:
            raise ViewerError("structure id(s) not included in the project: %s" % ", ".join(sorted(missing)))
    return out


def contact_highlights(analysis_dir, key, protein_seq, rna_seq, rna_range=None, protein_range=None):
    """Highlights for one structure from Report's per-structure contact record A/report/contacts_by_output.json
    (construct numbering), optionally restricted to an RNA (and protein) range. Every residue carries the evidence ID
    of the contact record it comes from."""
    rel = "report/contacts_by_output.json"
    with open(os.path.join(analysis_dir, rel), encoding="utf-8") as fh:
        rec = json.load(fh)
    if key not in rec:
        raise ViewerError("no contact record for %r in %s" % (key, rel))
    prot, rna = {}, {}
    for i, (p, r) in enumerate(rec[key]):
        if rna_range and not (rna_range[0] <= r <= rna_range[1]):
            continue
        if protein_range and not (protein_range[0] <= p <= protein_range[1]):
            continue
        eid = pv.evidence_id(rel, "/%s/%d" % (key.replace("~", "~0").replace("/", "~1"), i))
        prot.setdefault(p, {"residue": p, "label": "%s%d" % (protein_seq[p - 1] if 0 < p <= len(protein_seq) else "?", p), "evidence_id": eid})
        rna.setdefault(r, {"residue": r, "label": "%s%d" % (rna_seq[r - 1] if 0 < r <= len(rna_seq) else "?", r), "evidence_id": eid})
    return {"protein": [prot[k] for k in sorted(prot)], "rna": [rna[k] for k in sorted(rna)]}


def project_explorer(project_dir, analysis_dir, structs, protein_seq, rna_seq):
    """Contact-explorer data for an imported project: each structure's record (rnplens.contact_explorer) is added to
    its entry in structs as s["explorer"]; returns the page-wide part (construct sequences, per-engine ensemble)."""
    from . import contact_explorer as CE
    cbo = CE.load_records(analysis_dir)
    with open(os.path.join(project_dir, "manifest.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    key_to_id = {"%s|%s" % (s["engine"], s.get("execution", "")): s["id"] for s in man.get("structures", []) if s.get("id")}
    for s in structs:
        s["explorer"] = CE.structure_record(s["path"], s["chains"], cbo.get(s["key"]), s["key"], s.get("id"),
                                            s["key"].split("|", 1)[0], construct_lengths=(len(protein_seq), len(rna_seq)))
    return {"seq": {"protein": protein_seq, "rna": rna_seq}, "ensemble": CE.ensemble(cbo, key_to_id)}


def _range(text, what):
    if not text:
        return None
    try:
        a, b = (int(x) for x in text.split("-"))
    except ValueError:
        raise ViewerError("%s range %r is not 'start-end'" % (what, text))
    if a < 1 or b < a:
        raise ViewerError("%s range %r is not a valid construct range" % (what, text))
    return (a, b)


def _seq(path):
    return "".join(l.strip() for l in open(path) if not l.startswith(">"))


def group_labels(analysis_dir, threshold):
    """{structure id: label} for --representatives: each group's representative at ``threshold``, in the groups'
    display order, with the label 'rnplens group' recorded for it, then each engine-designated structure that is not a
    representative, with its recorded note. The labels are copied from groups.json; nothing is ranked or selected."""
    path = os.path.join(analysis_dir, "groups", "groups.json")
    if not os.path.isfile(path):
        raise ViewerError("%s not found: run 'rnplens group PROJECT --analysis %s' first" % (path, analysis_dir))
    with open(path, encoding="utf-8") as fh:
        groups = json.load(fh)["thresholds"][threshold]["groups"]
    out = {}
    for g in groups:
        r = g["representative"]
        out[r["id"]] = "%s (t=%s)" % (r["label"], threshold)
    for g in groups:
        for d in g.get("designated_members") or []:
            out.setdefault(d["id"], "%s (t=%s)" % (d["text"], threshold))
    return out


def main(argv=None):
    """rnplens view PROJECT --analysis A [--rna a-b] [--protein c-d] [--ids s001,s002] [--out DIR]"""
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="rnplens view", description="Write an offline Mol* page (no network access) of "
                                 "the project's structures, each with its own Report contacts highlighted.")
    ap.add_argument("project", help="project folder written by 'rnplens import'")
    ap.add_argument("--analysis", required=True, help="analysis folder written by 'rnplens analyse'")
    ap.add_argument("--rna", help="highlight only contacts with RNA positions in this construct range, e.g. 13-23")
    ap.add_argument("--protein", help="and protein positions in this range")
    ap.add_argument("--ids", help="structure ids, comma-separated, shown in this order (default: all included structures)")
    ap.add_argument("--representatives", choices=["0.3", "0.5", "0.7"],
                    help="show the representative of every binding-proposal group at this threshold (from "
                         "ANALYSIS/groups/groups.json, written by 'rnplens group'), in the groups' display order and "
                         "labelled with their group, then each engine-designated structure that is not a representative")
    ap.add_argument("--out", help="output folder (default ANALYSIS/viewer, or ANALYSIS/viewer_<a>-<b> with --rna)")
    a = ap.parse_args(argv)
    try:
        rr, pr = _range(a.rna, "RNA"), _range(a.protein, "protein")
        ps = _seq(os.path.join(a.project, "construct_protein.fasta"))
        rs = _seq(os.path.join(a.project, "construct_rna.fasta"))
        if rr and rr[1] > len(rs):
            raise ViewerError("RNA range %s exceeds the construct length %d" % (a.rna, len(rs)))
        ids = [x.strip() for x in a.ids.split(",") if x.strip()] if a.ids else None
        notes = group_labels(a.analysis, a.representatives) if a.representatives else {}
        if a.representatives:
            if ids:
                raise ViewerError("give --ids or --representatives, not both")
            ids = list(notes)
        structs = project_structures(a.project, ids)
        if ids:                                      # the order given (or the groups' display order), not file order
            structs.sort(key=lambda s: ids.index(s["id"]))
        for s in structs:
            if s["id"] in notes:                     # file names keep the plain label; the note goes in the title
                s["file_label"], s["label"] = s["label"], "%s | %s" % (s["label"], notes[s["id"]])
            s["highlights"] = contact_highlights(a.analysis, s["key"], ps, rs, rr, pr)
        explorer = project_explorer(a.project, a.analysis, structs, ps, rs)
        default = ("viewer_representatives_t%s" % a.representatives) if a.representatives else "viewer"
        out = a.out or os.path.join(a.analysis, default if not rr else "%s_%d-%d" % ((default,) + rr))
        title = "RNPLens structure view" + (" (RNA %d-%d)" % rr if rr else "")
        r = structure_page(out, [{k: s[k] for k in ("path", "label", "chains", "highlights", "file_label", "explorer") if k in s}
                                 for s in structs],
                           title=title, explorer=explorer, provenance_inputs=[{"path": os.path.abspath(cbo), "sha256": pv.sha256_file(cbo)}
                                                       for cbo in [os.path.join(a.analysis, "report", "contacts_by_output.json")]])
    except (ViewerError, OSError, KeyError) as ex:
        print("rnplens view: %s" % ex, file=sys.stderr)
        return 2
    print("rnplens view: %d structure(s); page %s (opens without network access; highlighted residues are Report's "
          "contacts for each structure, not a measure of correctness)" % (len(structs), r["page"]))
    print("rnplens view: " + STATUS)
    return 0
