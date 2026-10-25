// RNPLens contact explorer: real-browser step runner (headless Chrome, SwiftShader WebGL, run inside a network-less
// namespace by run_nt.sh). usage: node browser_nt.js CHROME_EXE PLAN_JSON OUT_DIR
// PLAN_JSON: {"tag", "page", "steps": [{"id", "do": load|click|clear|show|next|prev|mode|api_select|api_residue|camera_reset,
//             ...args, "shot": bool}]}
// For each step it records what the page and Mol* show: the explorer state, the panel (DOM), every Mol* component
// with the residues it contains, every representation with its type, opacity and colour layers (residues per colour),
// the contact-line primitives with Mol*'s own coordinates of the named atoms, and a screenshot when asked.
// Clicks are real mouse events at the screen position of an atom of the target residue (chosen so that Mol*'s hover
// reports that residue first); only if no such position exists does the step use the page's programmatic hook, and
// the record says so. It computes nothing about the structures.
const puppeteer = require('puppeteer-core');
const fs = require('fs'), path = require('path');
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const [exe, planPath, outDir] = process.argv.slice(2);
  const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
  fs.mkdirSync(outDir, {recursive: true});
  const args = ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist',
                '--window-size=1600,1200', '--hide-scrollbars'];
  const browser = await puppeteer.launch({executablePath: exe, headless: 'shell', pipe: true, args, defaultViewport: {width: 1600, height: 1200}});
  const res = {tag: plan.tag, page: path.resolve(plan.page), browser_version: await browser.version(), launch_args: args,
               requests: [], websockets: [], failed: [], console: [], page_errors: [], steps: []};
  const page = await browser.newPage();
  const cdp = await page.createCDPSession();
  await cdp.send('Network.enable');
  cdp.on('Network.requestWillBeSent', e => res.requests.push({url: e.request.url.slice(0, 200), type: e.type || null}));
  cdp.on('Network.webSocketCreated', e => res.websockets.push(e.url));
  cdp.on('Network.loadingFailed', e => res.failed.push({error: e.errorText, blocked: e.blockedReason || null}));
  page.on('console', m => res.console.push(m.type() + ': ' + m.text().slice(0, 300)));
  page.on('pageerror', e => res.page_errors.push(String(e).slice(0, 300)));
  const t0 = Date.now();
  await page.goto('file://' + path.resolve(plan.page), {waitUntil: 'load', timeout: 120000});
  await page.waitForFunction(() => document.getElementById('rnplens-status').getAttribute('data-state') !== 'PENDING', {timeout: 180000});
  res.status = await page.$eval('#rnplens-status', el => el.textContent);
  res.load_ms = Date.now() - t0;
  res.gl = await page.evaluate(() => { const gl = window.RNPLENS_VIEWER.plugin.canvas3d.webgl.gl, e = gl.getExtension('WEBGL_debug_renderer_info');
    return {version: gl.getParameter(gl.VERSION), renderer: e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : null}; });
  await page.evaluate(() => {
    const P = molstar.lib.structure.StructureProperties, SE = molstar.lib.structure.StructureElement;
    window.__hover = null;
    window.RNPLENS_VIEWER.plugin.behaviors.interaction.hover.subscribe(e => {
      const l = e.current && e.current.loci;
      if (l && SE.Loci.is(l) && !SE.Loci.isEmpty(l)) { const loc = SE.Loci.getFirstLocation(l);
        window.__hover = [P.chain.auth_asym_id(loc), P.residue.auth_seq_id(loc), P.residue.pdbx_PDB_ins_code(loc) || ''];
      } else window.__hover = l ? [l.kind] : null;
    });
  });

  const settle = async () => {
    await sleep(400);
    await page.waitForFunction(() => { const x = window.RNPLENS_EXPLORER; if (!x) return false; const s = x.state();
      const p = window.RNPLENS_VIEWER.plugin;
      return s.ready && s.want === s.signature && !p.behaviors.state.isUpdating.value && !p.behaviors.state.isAnimating.value; }, {timeout: 120000});
    await sleep(900);
  };

  const capture = async () => page.evaluate(() => {
    const v = window.RNPLENS_VIEWER, p = v.plugin, L = molstar.lib.structure, P = L.StructureProperties, SE = L.StructureElement;
    const key = loc => P.chain.auth_asym_id(loc) + ':' + P.residue.auth_seq_id(loc) + (P.residue.pdbx_PDB_ins_code(loc) || '');
    const lociRes = loci => { const out = new Set(); SE.Loci.forEachLocation(loci, loc => out.add(key(loc))); return Array.from(out).sort(); };
    const hex = c => '#' + ('000000' + (c >>> 0).toString(16)).slice(-6).toUpperCase();
    const comps = [];
    const h = p.managers.structure.hierarchy.current;
    let sdata = null;
    for (const s of h.structures) { sdata = s.cell.obj.data;
      for (const c of s.components) {
        const d = c.cell.obj && c.cell.obj.data; const residues = new Set();
        if (d) { const loc = SE.Location.create(d);
          for (const u of d.units) { loc.unit = u; for (let i = 0; i < u.elements.length; i++) { loc.element = u.elements[i]; residues.add(key(loc)); } } }
        const reprs = c.representations.map(r => {
          const tp = r.cell.transform.params; const kids = [];
          const ch = p.state.data.tree.children.get(r.cell.transform.ref);
          if (ch) ch.forEach(ref => { const cc = p.state.data.cells.get(ref); const id = cc.transform.transformer.id; const pr = cc.transform.params || {};
            const layers = (pr.layers || []).map(l => ({color: l.color !== undefined ? hex(l.color) : null, value: l.value, clear: !!l.clear,
              residues: l.bundle && sdata ? lociRes(SE.Bundle.toLoci(l.bundle, sdata)) : null}));
            kids.push({transformer: id, layers}); });
          return {type: tp.type && tp.type.name, alpha: tp.type && tp.type.params ? tp.type.params.alpha : null,
                  colorTheme: tp.colorTheme ? tp.colorTheme.name : null,
                  uniform: tp.colorTheme && tp.colorTheme.params && tp.colorTheme.params.value !== undefined ? hex(tp.colorTheme.params.value) : null,
                  children: kids};
        });
        comps.push({label: c.cell.obj ? c.cell.obj.label.slice(0, 160) : null, residues: Array.from(residues).sort(), reprs});
      }
    }
    const labels = []; p.state.data.cells.forEach(c => { if (c.obj) labels.push(c.obj.label); });
    const X = window.RNPLENS_EXPLORER, st = X.state();
    // Mol*'s own coordinates of the atoms the contact lines join
    const atomXYZ = (chain, seq, ins, name) => { if (!sdata) return null; const loc = SE.Location.create(sdata);
      for (const u of sdata.units) { loc.unit = u; for (let i = 0; i < u.elements.length; i++) { loc.element = u.elements[i];
        if (P.chain.auth_asym_id(loc) === chain && P.residue.auth_seq_id(loc) === seq && (P.residue.pdbx_PDB_ins_code(loc) || '') === ins && P.atom.auth_atom_id(loc) === name)
          return [P.atom.x(loc), P.atom.y(loc), P.atom.z(loc)]; } } return null; };
    const lines = (st.lines || []).map(l => ({...l, molstar_p: atomXYZ(l.pc, l.pauth[0], l.pauth[1], l.pa), molstar_r: atomXYZ(l.rc, l.rauth[0], l.rauth[1], l.ra)}));
    const fingerprint = [];                              // first atom of every unit, with Mol*'s coordinates
    if (sdata) { const loc = SE.Location.create(sdata);
      for (const u of sdata.units) { loc.unit = u; loc.element = u.elements[0];
        fingerprint.push({chain: P.chain.auth_asym_id(loc), seq: P.residue.auth_seq_id(loc), ins: P.residue.pdbx_PDB_ins_code(loc) || '',
                          atom: P.atom.auth_atom_id(loc), xyz: [P.atom.x(loc), P.atom.y(loc), P.atom.z(loc)]}); } }
    const ex = document.getElementById('rnplens-explorer');
    const sel = document.getElementById('rnplens-selection');
    const cnt = document.getElementById('rnplens-contact-count');
    const rows = Array.from(document.querySelectorAll('#rnplens-contact-table tr[data-p]')).map(tr => ({pc: tr.dataset.pc, p: +tr.dataset.p, rc: tr.dataset.rc, r: +tr.dataset.r,
      d: tr.dataset.d === '' ? null : +tr.dataset.d, eid: tr.dataset.eid, cells: Array.from(tr.children).map(td => td.textContent)}));
    return {state: st, panel: {state: ex.getAttribute('data-state'), signature: ex.getAttribute('data-signature'),
              structure_text: (document.querySelector('.rx-structure') || {}).textContent || null,
              selection: sel ? {molecule: sel.dataset.molecule, chain: sel.dataset.chain, pos: +sel.dataset.pos, text: sel.textContent} : null,
              count: cnt ? (cnt.dataset.count === '' ? null : +cnt.dataset.count) : null, count_text: cnt ? cnt.textContent : null, rows,
              note: (document.querySelector('.rx-note') || {}).textContent || null, select_value: document.getElementById('rx-structure').value,
              text: document.getElementById('rx-panel').innerText},
            components: comps, primitive_cells: labels.filter(x => x === 'Primitive Data').length,
            focus_cells: labels.filter(x => /\[Focus\]|Non-covalent|Interactions/.test(x)),
            lines, fingerprint, camera: p.canvas3d.camera.getSnapshot().target.slice ? Array.from(p.canvas3d.camera.getSnapshot().target) : null};
  });

  const realClick = async (chain, auth, ins) => {
    const cands = await page.evaluate((chain, auth, ins) => {
      const p = window.RNPLENS_VIEWER.plugin, L = molstar.lib.structure, P = L.StructureProperties, SE = L.StructureElement;
      const s = p.managers.structure.hierarchy.current.structures[0].cell.obj.data, loc = SE.Location.create(s), out = [];
      const r = p.canvas3d.webgl.gl.canvas.getBoundingClientRect(), dpr = window.devicePixelRatio, cam = p.canvas3d.camera;
      for (const u of s.units) { loc.unit = u; for (let i = 0; i < u.elements.length; i++) { loc.element = u.elements[i];
        if (P.chain.auth_asym_id(loc) === chain && P.residue.auth_seq_id(loc) === auth && (P.residue.pdbx_PDB_ins_code(loc) || '') === ins) {
          const o = [0, 0, 0, 0]; cam.project(o, [P.atom.x(loc), P.atom.y(loc), P.atom.z(loc)]);
          const x = r.left + o[0] / dpr, y = r.top + r.height - o[1] / dpr;
          if (x > r.left + 5 && x < r.right - 5 && y > r.top + 5 && y < r.bottom - 5) out.push({atom: P.atom.auth_atom_id(loc), x, y, z: o[2]});
        } } }
      out.sort((a, b) => a.z - b.z);                       // nearest to the camera first
      return out;
    }, chain, auth, ins);
    const tried = [];
    for (const c of cands.slice(0, 40)) {
      await page.mouse.move(c.x, c.y); await sleep(250);
      const hv = await page.evaluate(() => window.__hover);
      tried.push([c.atom, hv]);
      if (hv && hv[0] === chain && hv[1] === auth && hv[2] === ins) {
        await page.mouse.click(c.x, c.y);
        return {how: 'mouse', atom: c.atom, x: Math.round(c.x), y: Math.round(c.y), tried: tried.length};
      }
    }
    return {how: 'none', candidates: cands.length, tried};
  };

  for (const step of plan.steps) {
    const rec = {id: step.id, do: step.do, args: step, t: Date.now() - t0};
    try {
      if (step.do === 'click') {
        let r = await realClick(step.chain, step.auth, step.ins || '');
        if (r.how !== 'mouse') {
          await page.evaluate((c, a, i) => window.RNPLENS_EXPLORER.selectResidue(c, a, i), step.chain, step.auth, step.ins || '');
          r = {...r, how: 'api_fallback'};
        }
        rec.click = r;
      } else if (step.do === 'clear') { await page.click('#rx-clear');
      } else if (step.do === 'show') { await page.select('#rx-structure', String(step.k));
      } else if (step.do === 'next') { await page.click('#rx-next');
      } else if (step.do === 'prev') { await page.click('#rx-prev');
      } else if (step.do === 'mode') { await page.click('input[name="rx-mode"][value="' + step.m + '"]');
      } else if (step.do === 'api_select') { await page.evaluate((m, c, p) => window.RNPLENS_EXPLORER.selectPosition(m, c, p), step.molecule, step.chain, step.pos);
      } else if (step.do === 'camera_reset') { await page.evaluate(() => window.RNPLENS_VIEWER.plugin.canvas3d.requestCameraReset());
      } else if (step.do === 'api_residue') { await page.evaluate((c, a, i) => window.RNPLENS_EXPLORER.selectResidue(c, a, i), step.chain, step.auth, step.ins || '');
      }
      await settle();
      Object.assign(rec, await capture());
      if (step.shot) { const f = plan.tag + '_' + step.id + '.png'; await page.screenshot({path: path.join(outDir, f)}); rec.screenshot = f; }
    } catch (e) { rec.error = String(e).slice(0, 400); }
    res.steps.push(rec);
  }
  res.wall_ms = Date.now() - t0;
  fs.writeFileSync(path.join(outDir, 'result_' + plan.tag + '.json'), JSON.stringify(res));
  await browser.close();
})().catch(e => { console.log('FATAL ' + e); process.exit(1); });
