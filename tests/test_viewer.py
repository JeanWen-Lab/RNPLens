"""Offline Mol* page: local references only, every referenced file exists, asset hashes, relative structure paths,
highlight parity with Report's per-structure contact records, malformed input, determinism, data access.

An optional real-browser check (headless Firefox inside a network-less bubblewrap namespace, driven by
puppeteer-core) runs when RNPLENS_BROWSER_CHECK names a folder containing node_modules/puppeteer-core and
RNPLENS_FIREFOX names a Firefox binary; otherwise it is skipped."""
import builtins
import json
import os
import re
import shutil
import subprocess
from html.parser import HTMLParser

import pytest

from rnplens import analyse, importer, provenance as pv, trace, viewer

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")
PS = importer.read_sequence_arg(os.path.join(EX, "reference_based", "7K9D_protein.fasta"))
RS = importer.read_sequence_arg(os.path.join(EX, "reference_based", "7K9D_rna.fasta"))
URL = re.compile(r"(?i)\b(?:https?|ftp|wss?):|//[a-z0-9.-]+\.[a-z]{2,}")


@pytest.fixture(scope="module")
def worked(tmp_path_factory):
    """Worked example: the bundled 7K9D project, contacts with RNA 15-30 from Report's own per-structure records."""
    t = tmp_path_factory.mktemp("viewer")
    assert importer.run([os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B")], PS, RS, str(t / "p"), "7K9D_example", "BOLTZ2") == 0
    assert analyse.run(str(t / "p"), str(t / "a")) == 0
    st = viewer.project_structures(str(t / "p"))
    for s in st:
        s["highlights"] = viewer.contact_highlights(str(t / "a"), s["key"], PS, RS, rna_range=(15, 30))
    res = viewer.structure_page(str(t / "a" / "view_rna_15-30"), [{k: s[k] for k in ("path", "label", "chains", "highlights")} for s in st],
                                title="7K9D example: contacts with RNA 15-30")
    return t, st, res


class Refs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ("src", "href") and v is not None:
                self.refs.append(v)


def page_refs(page):
    p = Refs(); p.feed(open(page, encoding="utf-8").read())
    return p.refs


def test_page_references_only_local_files_that_exist(worked):
    t, st, res = worked
    out = os.path.dirname(res["page"])
    refs = page_refs(res["page"])
    assert "assets/molstar.js" in refs and "assets/molstar.css" in refs and "view_data.js" in refs
    for r in refs:
        assert not URL.search(r) and not os.path.isabs(r) and ".." not in r.split("/"), r
        assert os.path.isfile(os.path.join(out, r)), r
    for f in ("viewer.html", "view_data.js", "view.mvsj"):
        assert not URL.search(open(os.path.join(out, f), encoding="utf-8").read()), f      # no CDN or other address
    import html as H
    page = open(res["page"], encoding="utf-8").read()
    csp = H.unescape(re.search(r'http-equiv="Content-Security-Policy" content="([^"]*)"', page).group(1))
    assert "connect-src 'self' blob: data:" in csp           # Content-Security-Policy: no remote connections


def test_asset_hashes_match_version_record(worked):
    t, st, res = worked
    out = os.path.dirname(res["page"])
    rec = viewer.vendor_record()
    assert rec["package"] == "molstar" and rec["license"] == "MIT" and rec["version"] == "5.13.1"
    assert viewer.verify_assets()["ok"]
    for name, rel in (("molstar.js", "assets/molstar.js"), ("molstar.css", "assets/molstar.css"), ("LICENSE", "assets/LICENSE.molstar.txt")):
        assert pv.sha256_file(os.path.join(out, rel)) == rec["files"][name]["sha256"]
    assert "MIT License" in open(os.path.join(viewer.VENDOR, "LICENSE")).read()
    man = json.load(open(res["manifest"]))
    for rel, h in man["files"].items():
        assert pv.sha256_file(os.path.join(out, rel)) == h
    assert man["provenance"]["viewer"]["version"] == "5.13.1"


def test_structure_paths_are_relative_inside_out_dir_and_unchanged_copies(worked):
    t, st, res = worked
    out = os.path.dirname(res["page"])
    mvs = json.load(open(os.path.join(out, "view.mvsj")))
    urls = []

    def walk(n):
        if n.get("kind") == "download":
            urls.append(n["params"]["url"])
        for c in n.get("children", []):
            walk(c)
    for s in mvs["snapshots"]:
        walk(s["root"])
    assert len(urls) == 2
    for u, s in zip(urls, st):
        assert not os.path.isabs(u) and not u.startswith("..")
        full = os.path.realpath(os.path.join(out, u))
        assert full.startswith(os.path.realpath(out) + os.sep)
        assert pv.sha256_file(full) == pv.sha256_file(s["path"])
        assert os.path.isfile(full + ".js")
    data = open(os.path.join(out, urls[0] + ".js"), encoding="ascii").read()
    m = re.fullmatch(r"window\.RNPLENS_STRUCTURE_DATA\[(\".*?\")\] = (\".*\");\n", data, re.S)
    assert json.loads(m.group(1)) == urls[0] and json.loads(m.group(2)) == open(st[0]["path"], "rb").read().decode("latin-1")


def _selectors(mvs_root):
    sel = []

    def walk(n):
        if n.get("kind") == "component" and isinstance(n["params"]["selector"], list):
            sel.append(n["params"]["selector"])
        for c in n.get("children", []):
            walk(c)
    walk(mvs_root)
    return sel


def test_highlights_equal_reports_per_structure_contacts(worked):
    """Parity with the authoritative record A/report/contacts_by_output.json, restricted to RNA 15-30."""
    t, st, res = worked
    rec = json.load(open(t / "a" / "report" / "contacts_by_output.json"))
    mvs = json.load(open(os.path.join(os.path.dirname(res["page"]), "view.mvsj")))
    for s, snap in zip(st, mvs["snapshots"]):
        pairs = [(p, r) for p, r in rec[s["key"]] if 15 <= r <= 30]
        prot, rna = _selectors(snap["root"])
        assert [x["auth_seq_id"] for x in prot] == sorted({p for p, _ in pairs}) and {x["auth_asym_id"] for x in prot} == {s["chains"]["protein"]}
        assert [x["auth_seq_id"] for x in rna] == sorted({r for _, r in pairs}) and {x["auth_asym_id"] for x in rna} == {s["chains"]["rna"]}
    man = json.load(open(res["manifest"]))
    for h in man["highlighted"]:
        path, ptr = h["evidence_id"].split("#", 1)
        key, i = ptr[1:].rsplit("/", 1)
        p, r = json.load(open(t / "a" / path))[key.replace("~1", "/").replace("~0", "~")][int(i)]
        assert (h["residue"] in (p, r)) and 15 <= r <= 30
    assert res["n_highlighted"] == len(man["highlighted"]) == 46
    first = json.load(open(t / "a" / "report" / "contacts_by_output.json"))[st[0]["key"]]
    assert man["highlighted"][0]["label"] == "%s%d" % (PS[sorted({p for p, r in first if 15 <= r <= 30})[0] - 1], sorted({p for p, r in first if 15 <= r <= 30})[0])


def test_page_lists_highlights_with_evidence_ids_and_passes_wording_audit(worked):
    t, st, res = worked
    html = open(res["page"], encoding="utf-8").read()
    assert res["evidence_ids"][0] in html and "report/contacts_by_output.json#/BOLTZ2|exec_A#7K9D_model_0/" in html
    assert trace.wording_audit(html) == []


def test_malformed_inputs_are_refused(tmp_path, worked):
    t, st, res = worked
    s0 = {"path": st[0]["path"], "label": "a", "chains": st[0]["chains"]}
    bad = [
        ([], None, "non-empty list"),
        ([{"path": str(tmp_path / "missing.pdb"), "label": "a"}], None, "is not a file"),
        ([dict(s0, label="")], None, "non-empty label"),
        ([s0, dict(s0)], None, "duplicate label"),
        ([s0], {"protein": [{"residue": "14"}]}, "integer residue"),
        ([s0], {"protein": [{"residue": True}]}, "integer residue"),
        ([s0], {"ligand": []}, "unknown highlight keys"),
        ([s0], {"protein": [{"residue": 1, "structure": "zzz"}]}, "unknown structure"),
        ([{"path": st[0]["path"], "label": "nochain"}], {"rna": [{"residue": 3}]}, "declares no rna chain"),
        ([s0], {"protein": ["A14"]}, "a residue is a dict"),
    ]
    txt = tmp_path / "x.txt"; txt.write_text("hello")
    bad.append(([{"path": str(txt), "label": "t"}], None, "unsupported file type"))
    for structures, hl, msg in bad:
        with pytest.raises(viewer.ViewerError, match=msg):
            viewer.structure_page(str(tmp_path / "o"), structures, hl)
    f = tmp_path / "file"; f.write_text("")
    with pytest.raises(viewer.ViewerError, match="not a directory"):
        viewer.structure_page(str(f), [s0])


def test_label_text_cannot_break_out_of_the_page(tmp_path, worked):
    t, st, res = worked
    evil = "</script><script>alert(1)</script><!--"
    r = viewer.structure_page(str(tmp_path / "o"), [{"path": st[0]["path"], "label": evil, "chains": st[0]["chains"]}],
                              {"protein": [{"residue": 14, "label": evil}]}, title=evil)
    html = open(r["page"], encoding="utf-8").read()
    assert "<script>alert(1)" not in html
    js = open(tmp_path / "o" / "view_data.js").read()
    assert "</script" not in js.lower() and "<!--" not in js


def test_tampered_vendor_assets_are_refused(tmp_path, worked, monkeypatch):
    t, st, res = worked
    v = tmp_path / "molstar"; shutil.copytree(viewer.VENDOR, v)
    with open(v / "molstar.js", "ab") as fh:
        fh.write(b"\n//x")
    monkeypatch.setattr(viewer, "VENDOR", str(v))
    assert not viewer.verify_assets()["ok"]
    with pytest.raises(viewer.ViewerError, match="failed their check"):
        viewer.structure_page(str(tmp_path / "o"), [{"path": st[0]["path"], "label": "a"}])


def test_deterministic_output(tmp_path, worked):
    t, st, res = worked
    args = [{k: s[k] for k in ("path", "label", "chains", "highlights")} for s in st]
    a = viewer.structure_page(str(tmp_path / "1"), args)
    b = viewer.structure_page(str(tmp_path / "2"), args)
    ma, mb = json.load(open(a["manifest"])), json.load(open(b["manifest"]))
    assert ma["files"] == mb["files"] and ma["highlighted"] == mb["highlighted"]
    assert ma["provenance"]["config_sha256"] == mb["provenance"]["config_sha256"]


def test_reads_only_the_structures_and_vendored_assets(tmp_path, worked, monkeypatch):
    t, st, res = worked
    opened = []
    real = builtins.open

    def rec(f, *a, **k):
        opened.append(os.path.abspath(str(f)))
        return real(f, *a, **k)
    monkeypatch.setattr(builtins, "open", rec)
    viewer.structure_page(str(tmp_path / "o"), [{"path": st[0]["path"], "label": "a", "chains": st[0]["chains"]}],
                          {"rna": [{"residue": 15}]})
    allowed = {os.path.abspath(st[0]["path"]), os.path.abspath(viewer.EXPLORER_JS)}   # + the RNPLens contact explorer script
    for o in opened:
        assert o in allowed or o.startswith(os.path.abspath(viewer.VENDOR) + os.sep) or o.startswith(str(tmp_path / "o")), o


def test_project_helpers_refuse_ambiguous_input(tmp_path, worked):
    t, st, res = worked
    with pytest.raises(viewer.ViewerError, match="not included"):
        viewer.project_structures(str(t / "p"), ids=["s999"])
    man = json.load(open(t / "p" / "manifest.json"))
    man["structures"][0]["chains"].append(dict(man["structures"][0]["chains"][0], chain="C"))
    q = tmp_path / "p"; q.mkdir(); (q / "manifest.json").write_text(json.dumps(man))
    with pytest.raises(viewer.ViewerError, match="2 protein and 1 RNA"):
        viewer.project_structures(str(q))
    with pytest.raises(viewer.ViewerError, match="no contact record"):
        viewer.contact_highlights(str(t / "a"), "BOLTZ2|nope", PS, RS)
    h = viewer.contact_highlights(str(t / "a"), st[0]["key"], PS, RS, rna_range=(15, 30), protein_range=(14, 20))
    assert all(15 <= r["residue"] <= 30 for r in h["rna"]) and all(14 <= p["residue"] <= 20 for p in h["protein"]) and h["protein"]


def test_missing_highlights_give_a_plain_page(tmp_path, worked):
    t, st, res = worked
    r = viewer.structure_page(str(tmp_path / "o"), [{"path": st[0]["path"], "label": "only"}])
    mvs = json.load(open(tmp_path / "o" / "view.mvsj"))
    assert mvs.get("kind") is None and _selectors(mvs["root"]) == [] and r["n_highlighted"] == 0


# ---------------------------------------------------------------- optional real-browser check

CHECK_JS = r"""
const puppeteer = require('puppeteer-core');
const path = require('path');
(async () => {
  const browser = await puppeteer.launch({browser: 'firefox', executablePath: process.env.RNPLENS_FIREFOX, headless: true});
  const page = await browser.newPage();
  const requests = [], errors = [];
  page.on('request', r => requests.push(r.url()));
  page.on('pageerror', e => errors.push(String(e).slice(0, 300)));
  await page.goto('file://' + path.resolve(process.argv[2]), {waitUntil: 'load', timeout: 60000});
  try { await page.waitForFunction(() => document.getElementById('rnplens-status').getAttribute('data-state') !== 'PENDING', {timeout: 90000}); }
  catch (e) { errors.push('timeout'); }
  const status = await page.$eval('#rnplens-status', el => el.textContent);
  const stats = await page.evaluate(() => {
    const v = window.RNPLENS_VIEWER; if (!v) return null;
    const h = v.plugin.managers.structure.hierarchy.current;
    const comps = [];
    for (const s of h.structures) for (const c of s.components) {
      const d = c.cell.obj && c.cell.obj.data; let n = 0;
      if (d) for (const u of d.units) { const seen = new Set(); const rI = u.model.atomicHierarchy.residueAtomSegments.index;
        for (let i = 0; i < u.elements.length; i++) seen.add(rI[u.elements[i]]); n += seen.size; }
      comps.push({label: c.cell.obj ? c.cell.obj.label : null, residues: n});
    }
    return {n_snapshots: v.plugin.managers.snapshot.state.entries.size, components: comps,
            n_structures: window.RNPLENS_EXPLORER ? window.RNPLENS_EXPLORER.structures : null};
  });
  const nonlocal = requests.filter(u => !/^(file|blob|data|about):/.test(u));
  console.log(JSON.stringify({status, nonlocal, errors, stats}));
  await browser.close();
})().catch(e => { console.log(JSON.stringify({fatal: String(e)})); process.exit(1); });
"""


@pytest.mark.skipif(not (os.environ.get("RNPLENS_BROWSER_CHECK") and os.environ.get("RNPLENS_FIREFOX") and shutil.which("node")
                         and shutil.which("bwrap")), reason="real-browser check not configured (RNPLENS_BROWSER_CHECK, RNPLENS_FIREFOX, node, bwrap)")
def test_page_loads_in_a_real_browser_without_network(tmp_path, worked):
    t, st, res = worked
    d = os.environ["RNPLENS_BROWSER_CHECK"]
    script = os.path.join(d, "rnplens_viewer_check.js")
    with open(script, "w") as fh:
        fh.write(CHECK_JS)
    p = subprocess.run(["bwrap", "--dev-bind", "/", "/", "--unshare-net", "--die-with-parent", "node", script, res["page"]],
                       capture_output=True, text=True, timeout=240, cwd=d)
    r = json.loads(p.stdout.strip().splitlines()[-1])
    assert r.get("status", "").startswith("LOADED"), r
    assert r["nonlocal"] == []
    rec = json.load(open(t / "a" / "report" / "contacts_by_output.json"))
    pairs = [(a, b) for a, b in rec[st[0]["key"]] if 15 <= b <= 30]
    sel = [c["residues"] for c in r["stats"]["components"] if c["label"].startswith("Custom Selection")]
    # one structure is loaded at a time (contact explorer); the page's selector holds both structures
    assert sel == [len({a for a, _ in pairs}), len({b for _, b in pairs})] and r["stats"]["n_structures"] == 2
