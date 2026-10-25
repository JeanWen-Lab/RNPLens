// RNPLens viewer track: load one offline RNPLens/Mol* page in headless Chrome (SwiftShader WebGL), log every request
// the page attempts, extract what Mol* actually loaded and selected, and screenshot each snapshot.
// usage: node render.js CHROME_EXE PAGE_HTML OUT_DIR TAG
// Writes OUT_DIR/result_TAG.json and OUT_DIR/TAG_<nn>_<key>_<view>.png. Computes nothing about the structures.
const puppeteer = require('puppeteer-core');
const fs = require('fs'), path = require('path');
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const [exe, pagePath, outDir, tag] = process.argv.slice(2);
  fs.mkdirSync(outDir, {recursive: true});
  const args = ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist',
                '--window-size=1600,1200', '--hide-scrollbars'];
  const browser = await puppeteer.launch({executablePath: exe, headless: 'shell', pipe: true, args,
                                          defaultViewport: {width: 1600, height: 1200}});
  const res = {tag, page: path.resolve(pagePath), browser_version: await browser.version(), launch_args: args,
               requests: [], websockets: [], failed: [], csp_violations: [], console: [], page_errors: [], targets: []};
  browser.on('targetcreated', t => res.targets.push({type: t.type(), url: t.url()}));
  const page = await browser.newPage();
  const cdp = await page.createCDPSession();
  await cdp.send('Network.enable');
  cdp.on('Network.requestWillBeSent', e => res.requests.push({url: e.request.url, type: e.type || null, method: e.request.method, initiator: e.initiator && e.initiator.type}));
  cdp.on('Network.webSocketCreated', e => res.websockets.push(e.url));
  cdp.on('Network.loadingFailed', e => res.failed.push({id: e.requestId, error: e.errorText, blocked: e.blockedReason || null}));
  page.on('request', r => { if (!res.requests.some(x => x.url === r.url())) res.requests.push({url: r.url(), type: r.resourceType(), via: 'puppeteer'}); });
  page.on('workercreated', w => res.targets.push({type: 'worker', url: w.url()}));
  page.on('console', m => res.console.push(m.type() + ': ' + m.text().slice(0, 300)));
  page.on('pageerror', e => res.page_errors.push(String(e).slice(0, 300)));
  await page.evaluateOnNewDocument(() => { window.__csp = []; document.addEventListener('securitypolicyviolation', e =>
      window.__csp.push({blockedURI: e.blockedURI, directive: e.violatedDirective})); });
  const t0 = Date.now();
  await page.goto('file://' + path.resolve(pagePath), {waitUntil: 'load', timeout: 120000});
  try {
    await page.waitForFunction(() => document.getElementById('rnplens-status').getAttribute('data-state') !== 'PENDING', {timeout: 180000});
  } catch (e) { res.page_errors.push('timeout waiting for status'); }
  res.status = await page.$eval('#rnplens-status', el => el.textContent);
  res.load_ms = Date.now() - t0;
  res.gl = await page.evaluate(() => {
    const v = window.RNPLENS_VIEWER; if (!v || !v.plugin.canvas3d) return null;
    const gl = v.plugin.canvas3d.webgl.gl, e = gl.getExtension('WEBGL_debug_renderer_info');
    return {webgl2: (typeof WebGL2RenderingContext !== 'undefined') && gl instanceof WebGL2RenderingContext,
            version: gl.getParameter(gl.VERSION), vendor: gl.getParameter(gl.VENDOR), renderer: gl.getParameter(gl.RENDERER),
            unmasked_vendor: e ? gl.getParameter(e.UNMASKED_VENDOR_WEBGL) : null,
            unmasked_renderer: e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : null};
  });
  const entries = await page.evaluate(() => {
    const v = window.RNPLENS_VIEWER; if (!v) return [];
    return v.plugin.managers.snapshot.state.entries.toArray().map(e => ({key: e.key || null, name: e.name || null,
            description: e.description || null}));
  });
  res.snapshots = [];
  const idle = async () => {
    await page.waitForFunction(() => { const p = window.RNPLENS_VIEWER.plugin;
      return !p.behaviors.state.isUpdating.value && !p.behaviors.state.isAnimating.value; }, {timeout: 120000});
    await sleep(1500);
  };
  for (let i = 0; i < entries.length; i++) {
    const ent = entries[i];
    if (i > 0 || entries.length > 1) { await page.evaluate(k => window.RNPLENS_VIEWER.plugin.managers.snapshot.applyKey(k), ent.key); }
    await sleep(500); await idle();
    const info = await page.evaluate(() => {
      const p = window.RNPLENS_VIEWER.plugin;
      function residuesOf(st) {   // [[auth_asym_id, auth_seq_id, label_comp_id, entity_type], ...] in model order
        const seen = new Set(), out = [];
        for (const u of st.units) {
          if (u.kind !== 0) continue;
          const m = u.model, h = m.atomicHierarchy, rI = h.residueAtomSegments.index, cI = h.chainAtomSegments.index;
          for (let j = 0; j < u.elements.length; j++) {
            const a = u.elements[j], r = rI[a], c = cI[a], key = m.id + ':' + r;
            if (seen.has(key)) continue; seen.add(key);
            const ent = m.entities.data.type.value(m.atomicHierarchy.index.getEntityFromChain(c));
            out.push([h.chains.auth_asym_id.value(c), h.residues.auth_seq_id.value(r), h.atoms.label_comp_id.value(a), ent]);
          }
        }
        return out;
      }
      const hier = p.managers.structure.hierarchy.current;
      const structs = hier.structures.map(s => {
        const st = s.cell.obj.data;
        return {label: s.cell.obj.label, source_label: s.model && s.model.cell.obj ? s.model.cell.obj.label : null,
                atoms: st.elementCount, residues: residuesOf(st),
                components: s.components.map(c => ({label: c.cell.obj ? c.cell.obj.label : null,
                   residues: c.cell.obj ? residuesOf(c.cell.obj.data).map(x => [x[0], x[1]]) : [],
                   representations: c.representations.map(r => ({type: r.cell.transform.params.type.name,
                       color: r.cell.transform.params.colorTheme ? r.cell.transform.params.colorTheme.name : null,
                       color_params: r.cell.transform.params.colorTheme ? JSON.stringify(r.cell.transform.params.colorTheme.params) : null}))}))};
      });
      // every state cell (catches MVS label/primitive nodes that are not structure components)
      const cells = []; p.state.data.cells.forEach(c => { if (c.obj) cells.push({type: c.obj.type ? c.obj.type.name : null, label: c.obj.label}); });
      const seqEl = document.querySelector('.msp-sequence-wrapper');
      const selects = Array.from(document.querySelectorAll('.msp-sequence-select select')).map(s => s.options[s.selectedIndex] ? s.options[s.selectedIndex].text : null);
      const cur = p.managers.snapshot.state.current, ce = cur ? p.managers.snapshot.getEntry(cur) : null;
      return {current_key: ce ? ce.key : null, structures: structs, cells,
              sequence_panel: {selected: selects, text: seqEl ? seqEl.innerText.slice(0, 20000) : null}};
    });
    // sequence panel: read the residue text of every chain offered by the panel's chain selector
    info.sequence_panel.chains = await page.evaluate(async () => {
      const sleep = ms => new Promise(r => setTimeout(r, ms));
      const sels = Array.from(document.querySelectorAll('.msp-sequence-select select'));
      const chainSel = sels.find(s => s.previousElementSibling && /Chain/.test(s.previousElementSibling.textContent || '')) || sels[sels.length - 1];
      if (!chainSel) return null;
      const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set, out = [], first = chainSel.value;
      for (const o of Array.from(chainSel.options)) {
        setter.call(chainSel, o.value); chainSel.dispatchEvent(new Event('change', {bubbles: true})); await sleep(400);
        const el = document.querySelector('.msp-sequence-wrapper');
        out.push({option: o.text, text: el ? el.innerText.replace(/\u200b/g, '').slice(0, 20000) : null});
      }
      setter.call(chainSel, first); chainSel.dispatchEvent(new Event('change', {bubbles: true})); await sleep(300);
      return out;
    });
    const base = path.join(outDir, `${tag}_${String(i + 1).padStart(2, '0')}_${ent.key}`);
    const app = await page.$('#app');
    await app.screenshot({path: base + '_loaded.png'});
    // whole structure in view (Mol* camera reset)
    await page.evaluate(() => window.RNPLENS_VIEWER.plugin.managers.camera.reset(undefined, 0)); await sleep(300); await idle();
    await app.screenshot({path: base + '_overview.png'});
    // focus on the highlighted RNA residues (ball-and-stick component whose residues are all in the RNA entity)
    const focusRna = () => page.evaluate(() => {
      const p = window.RNPLENS_VIEWER.plugin, s = p.managers.structure.hierarchy.current.structures[0];
      const NUC = new Set(['A', 'C', 'G', 'U', 'DA', 'DC', 'DG', 'DT']);
      for (const c of s.components) {
        if (!c.representations.some(r => r.cell.transform.params.type.name === 'ball-and-stick')) continue;
        const st = c.cell.obj.data; let n = 0, nuc = 0;
        for (const u of st.units) { if (u.kind !== 0) continue; const h = u.model.atomicHierarchy;
          for (let j = 0; j < u.elements.length; j++) { n++; if (NUC.has(h.atoms.label_comp_id.value(u.elements[j]))) nuc++; } }
        if (!n || nuc !== n) continue;
        const sph = st.boundary.sphere; p.managers.camera.focusSphere({center: sph.center, radius: Math.max(sph.radius, 8)}, {durationMs: 0});
        return {component: c.cell.obj.label, radius: sph.radius};
      }
      return null;
    });
    const focused = await focusRna();
    await sleep(300); await idle();
    if (focused) await app.screenshot({path: base + '_rnafocus.png'});
    // Amendment 1: ribbon views. Re-apply the snapshot (camera as loaded), hide every ball-and-stick representation,
    // screenshot; then the RNA-focus camera again. Tests that a highlighted residue's ribbon shows its colour.
    if (entries.length > 1) { await page.evaluate(k => window.RNPLENS_VIEWER.plugin.managers.snapshot.applyKey(k), ent.key); await sleep(500); await idle(); }
    const nHidden = await page.evaluate(() => {
      const p = window.RNPLENS_VIEWER.plugin, s = p.managers.structure.hierarchy.current.structures[0]; let n = 0;
      for (const c of s.components) for (const r of c.representations)
        if (r.cell.transform.params.type.name === 'ball-and-stick') { p.state.data.updateCellState(r.cell.transform.ref, {isHidden: true}); n++; }
      return n;
    });
    await sleep(300); await idle();
    await app.screenshot({path: base + '_ribbon.png'});
    const focused2 = await focusRna(); await sleep(300); await idle();
    if (focused2) await app.screenshot({path: base + '_ribbonrna.png'});
    res.snapshots.push(Object.assign({index: i + 1, key: ent.key, name: ent.name, description: ent.description,
                                      rna_focus: focused, ball_and_stick_hidden: nHidden,
                                      shots: ['loaded', 'overview'].concat(focused ? ['rnafocus'] : []).concat(['ribbon']).concat(focused2 ? ['ribbonrna'] : [])}, info));
  }
  // back to the first snapshot, full-page screenshot (shows the side table of highlighted residues)
  if (entries.length) { await page.evaluate(k => window.RNPLENS_VIEWER.plugin.managers.snapshot.applyKey(k), entries[0].key); await sleep(500); await idle(); }
  await page.screenshot({path: path.join(outDir, `${tag}_fullpage.png`), fullPage: true});
  res.csp_violations = await page.evaluate(() => window.__csp);
  res.side_table = await page.evaluate(() => Array.from(document.querySelectorAll('#side table tr')).slice(1).map(tr => Array.from(tr.cells).map(td => td.textContent)));
  const local = u => /^(file|blob|data|about):/.test(u) || u === '' ;
  res.nonlocal_requests = res.requests.map(r => r.url).filter(u => !local(u)).concat(res.websockets)
       .concat(res.targets.map(t => t.url).filter(u => u && !local(u)))
       .concat((res.csp_violations || []).map(v => 'CSP-blocked:' + v.blockedURI).filter(u => !/CSP-blocked:(file|blob|data|inline|eval|self)?$/.test(u) && !/CSP-blocked:(file|blob|data):/.test(u)));
  res.request_schemes = {}; for (const r of res.requests) { const s = (r.url.match(/^([a-z-]+):/) || [null, '?'])[1]; res.request_schemes[s] = (res.request_schemes[s] || 0) + 1; }
  fs.writeFileSync(path.join(outDir, `result_${tag}.json`), JSON.stringify(res, null, 1));
  console.log(JSON.stringify({tag, status: res.status, load_ms: res.load_ms, n_snapshots: res.snapshots.length, schemes: res.request_schemes,
                              nonlocal: res.nonlocal_requests, errors: res.page_errors.slice(0, 5), renderer: res.gl && res.gl.unmasked_renderer}));
  await browser.close();
})().catch(e => { console.log(JSON.stringify({fatal: String(e && e.stack || e).slice(0, 3000)})); process.exit(1); });
