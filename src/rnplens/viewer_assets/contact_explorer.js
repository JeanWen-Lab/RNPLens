/* RNPLens viewer: nucleotide contact explorer (local, offline; part of RNPLens, not of Mol*).
 *
 * Reads window.RNPLENS_VIEW.explorer, written by rnplens.viewer from Report's per-structure contact records
 * (report/contacts_by_output.json) and the structure copies of this folder. It does not decide which residues are in
 * contact: the residues it highlights for a selection are exactly the pairs Report recorded for the structure on
 * screen. The distances it shows were recomputed in Python (rnplens.contact_explorer) when the page was written, and
 * only for structures whose recomputed contact set matched Report's record (distance_check PASS); otherwise the panel
 * says "Not available". Nothing is computed from the structures in the browser.
 *
 * One structure is shown at a time. Every change (structure, selection, display mode) rebuilds the MolViewSpec state
 * of the structure on screen and loads it with Mol*'s loadMvsData; nothing from a previous state is kept, so a
 * highlight of one structure cannot remain attached to another. Mol*'s own click behaviours (selection, focus with
 * surroundings and Mol*-computed interactions, camera centring) are switched off on this page so that a click shows
 * only Report's contacts.
 *
 * Test hooks: window.RNPLENS_EXPLORER (state(), show(k), selectResidue(chain, authSeq, insCode), selectPosition(mol,
 * chain, pos), clear(), setMode('focus'|'all')); #rnplens-explorer[data-state] is READY when the last state is on
 * screen and the panel matches it (data-signature).
 */
(function () {
  'use strict';
  var V, D, X, viewer, MVS, SE, SP;
  var st = {k: 0, sel: null, mode: 'focus', recentre: false, note: '', busy: false, pending: false, gen: 0, signature: ''};
  var el = {};

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]; }); }
  function cur() { return X.structures[st.k]; }

  // ---- residue correspondence (construct position <-> structure residue), from the page data only
  function ix(s) {
    if (s._ix) return s._ix;
    var byAuth = {}, byPos = {}, num = {}, res = (s.rec && s.rec.residues) || {};
    Object.keys(res).forEach(function (ch) {
      res[ch].forEach(function (r) {
        byAuth[ch + '|' + r[1] + '|' + r[2]] = r; byPos[ch + '|' + r[0]] = r;
        num[ch + '|' + r[1]] = (num[ch + '|' + r[1]] || 0) + 1;
      });
    });
    s._ix = {byAuth: byAuth, byPos: byPos, num: num};
    return s._ix;
  }
  function moleculeOf(s, chain) {
    var c = (s.rec && s.rec.chains) || {protein: [], rna: []};
    if (c.protein.indexOf(chain) >= 0) return 'protein';
    if (c.rna.indexOf(chain) >= 0) return 'rna';
    return null;
  }
  function selector(s, chain, r) {
    var q = {auth_asym_id: chain, auth_seq_id: r[1]};
    if (r[2] || ix(s).num[chain + '|' + r[1]] > 1) q.pdbx_PDB_ins_code = r[2];
    return q;
  }
  function letter(mol, pos) {
    var q = X.seq && X.seq[mol];
    return q && pos >= 1 && pos <= q.length ? q.charAt(pos - 1) : '?';
  }
  var STD = {protein: ['ALA', 'ARG', 'ASN', 'ASP', 'CYS', 'GLN', 'GLU', 'GLY', 'HIS', 'ILE', 'LEU', 'LYS', 'MET', 'PHE', 'PRO', 'SER', 'THR', 'TRP', 'TYR', 'VAL'],
             rna: ['A', 'C', 'G', 'U', 'RA', 'RC', 'RG', 'RU']};
  function isModified(mol, r) { return STD[mol].indexOf(r[3]) < 0; }
  function short(mol, chain, pos) { return chain + ':' + letter(mol, pos) + pos; }

  // ---- what the current state selects (Report's records for the structure on screen only)
  function resolve() {
    var s = cur(), out = {s: s, sel: st.sel, res: null, rows: [], partners: []};
    if (!st.sel) return out;
    out.res = ix(s).byPos[st.sel.chain + '|' + st.sel.pos] || null;
    if (!s.rec || !s.rec.available) return out;
    var rna = st.sel.molecule === 'rna';
    out.rows = s.rec.contacts.filter(function (c) {
      return rna ? (c.rc === st.sel.chain && c.r === st.sel.pos) : (c.pc === st.sel.chain && c.p === st.sel.pos);
    }).sort(function (a, b) { return rna ? (a.pc < b.pc ? -1 : a.pc > b.pc ? 1 : a.p - b.p) : (a.rc < b.rc ? -1 : a.rc > b.rc ? 1 : a.r - b.r); });
    var seen = {};
    out.rows.forEach(function (c) {
      var ch = rna ? c.pc : c.rc, pos = rna ? c.p : c.r, key = ch + '|' + pos;
      if (seen[key]) return; seen[key] = 1;
      out.partners.push({molecule: rna ? 'protein' : 'rna', chain: ch, pos: pos, res: ix(s).byPos[key] || null});
    });
    return out;
  }

  // ---- MolViewSpec state for the structure on screen
  function overviewRoot(k) { return JSON.parse(JSON.stringify(V.mvs.kind === 'multiple' ? V.mvs.snapshots[k].root : V.mvs.root)); }
  function comp(sel, kids) { return {kind: 'component', params: {selector: sel}, children: kids}; }
  function bs(color) { return {kind: 'representation', params: {type: 'ball_and_stick'}, children: [{kind: 'color', params: {color: color}}]}; }
  function selectionRoot(r) {
    var s = r.s, C = X.colours, focus = st.mode === 'focus', ov = s.overview || {protein: [], rna: []};
    var hl = {protein: ov.protein.map(function (x) { return {auth_asym_id: x.chain, auth_seq_id: x.residue}; }),
              rna: ov.rna.map(function (x) { return {auth_asym_id: x.chain, auth_seq_id: x.residue}; })};
    function base(sel, mol) {
      var kids = [{kind: 'color', params: {color: C[mol]}}];
      if (!focus && hl[mol].length) kids.push({kind: 'color', params: {color: C[mol + '_highlight'], selector: hl[mol]}});
      var rep = {kind: 'representation', params: {type: 'cartoon'}, children: kids};
      if (focus) rep.children.push({kind: 'opacity', params: {opacity: mol === 'protein' ? X.dim.protein : X.dim.rna}});
      return comp(sel, [rep]);
    }
    var comps = [base('protein', 'protein'), base('nucleic', 'rna')];
    if (!focus) {                                     // "Show all contacts": the page's contact highlights stay, unlabelled;
      var own = {};                                   // the selection and its partners get their own components below
      if (r.res) own[st.sel.chain + '|' + r.res[1]] = 1;
      r.partners.forEach(function (p) { if (p.res) own[p.chain + '|' + p.res[1]] = 1; });
      ['protein', 'rna'].forEach(function (mol) {
        var rest = hl[mol].filter(function (q) { return !own[q.auth_asym_id + '|' + q.auth_seq_id]; });
        if (rest.length) comps.push(comp(rest, [bs(C[mol + '_highlight'])]));
      });
    }
    var all = [];
    if (r.res) {
      var me = selector(s, st.sel.chain, r.res);
      all.push(me);
      comps.push(comp(me, [bs(C.selected), {kind: 'label', params: {text: short(st.sel.molecule, st.sel.chain, st.sel.pos)}},
                           {kind: 'tooltip', params: {text: 'Selected: ' + short(st.sel.molecule, st.sel.chain, st.sel.pos) + ' (' + s.label + ')'}}]));
    }
    var pc = st.sel.molecule === 'rna' ? C.protein_highlight : C.rna_highlight;
    var ps = r.partners.filter(function (p) { return p.res; }).map(function (p) { return selector(s, p.chain, p.res); });
    if (ps.length) {
      comps.push(comp(ps, [bs(pc)]));
      r.partners.forEach(function (p) {
        if (p.res) comps.push(comp(selector(s, p.chain, p.res), [{kind: 'label', params: {text: short(p.molecule, p.chain, p.pos)}}]));
      });
      all = all.concat(ps);
    }
    if (focus && all.length) comps.push(comp(all, [{kind: 'focus', params: {radius_extent: X.focus_extent_A}}]));
    else if (!focus && st.recentre) {                 // switching to "Show all contacts": frame the page's contacts again
      var frame = hl.protein.concat(hl.rna).concat(all);
      if (frame.length) comps.push(comp(frame, [{kind: 'focus', params: {}}]));
    }
    var root = {kind: 'root', children: [
      {kind: 'canvas', params: {background_color: '#FFFFFF'}},
      {kind: 'download', params: {url: s.rel}, children: [{kind: 'parse', params: {format: s.format}, children: [
        {kind: 'structure', params: {type: 'model'}, children: comps}]}]}]};
    var drawn = r.rows.filter(function (c) { return c.pxyz && c.rxyz; });
    st.drawn = drawn.map(function (c) {
      var pr = ix(s).byPos[c.pc + '|' + c.p], rr = ix(s).byPos[c.rc + '|' + c.r];
      return {pc: c.pc, p: c.p, rc: c.rc, r: c.r, pa: c.pa, ra: c.ra, start: c.pxyz, end: c.rxyz,
              pauth: pr ? [pr[1], pr[2]] : null, rauth: rr ? [rr[1], rr[2]] : null};
    });
    var lines = drawn.map(function (c) {
      return {kind: 'primitive', params: {kind: 'tube', start: c.pxyz, end: c.rxyz, radius: X.line.radius,
              dash_length: X.line.dash_length, color: C.line}};
    });
    if (lines.length) root.children.push({kind: 'primitives', params: {}, children: lines});
    return root;
  }

  function load(root, keepCamera, keepOrientation) {
    var s = cur(), mvs = {root: root, metadata: {title: s.label, version: '1', timestamp: '1970-01-01T00:00:00Z'}};
    var issues = MVS.validationIssues(mvs);
    if (issues) return Promise.reject(new Error('MolViewSpec state invalid: ' + issues.join('; ')));
    var assets = {}; assets[s.rel] = D[s.rel];
    return MVS.toMVSX(mvs, {assets: assets}).then(function (bytes) {
      return viewer.loadMvsData(bytes, 'mvsx', {replaceExisting: true, keepCamera: !!keepCamera, keepCameraOrientation: !!keepOrientation});
    });
  }

  function signature() {
    return [st.k, st.mode, st.sel ? st.sel.molecule + ':' + st.sel.chain + ':' + st.sel.pos : '-'].join('/');
  }

  function render() {
    if (st.busy) { st.pending = true; return; }
    st.busy = true; st.pending = false;
    var sig = signature(), r = resolve();
    el.root.setAttribute('data-state', 'BUSY');
    st.drawn = [];
    var root = st.sel ? selectionRoot(r) : overviewRoot(st.k);
    var keep = !!st.sel && st.mode === 'all' && !st.recentre;
    var orient = !!st.sel && st.mode === 'focus';      // focusing a selection keeps the user's viewing direction
    st.recentre = false;
    load(root, keep, orient).then(function () {
      st.busy = false;
      if (st.pending || sig !== signature()) { render(); return; }
      panel(r); st.signature = sig; st.shown = {lines: st.drawn};
      el.root.setAttribute('data-signature', sig);
      el.root.setAttribute('data-state', 'READY');
    }).catch(function (e) {
      st.busy = false;
      el.root.setAttribute('data-state', 'ERROR');
      el.panel.innerHTML = '<p class="rx-error">The viewer could not show this state: ' + esc(e && e.message ? e.message : e) + '</p>';
    });
  }

  // ---- panel
  function residueText(mol, chain, pos, res) {
    var t = letter(mol, pos) + pos;
    if (!res) return t + ' (not modelled in this structure)';
    var sid = chain + ' ' + res[1] + (res[2] || '');
    var extra = [];
    if (String(res[1]) + (res[2] || '') !== String(pos)) extra.push('structure residue ' + sid);
    if (isModified(mol, res)) extra.push((mol === 'rna' ? 'modified nucleotide ' : 'non-standard residue ') + res[3] + ', construct letter ' + letter(mol, pos));
    return t + (extra.length ? ' (' + extra.join('; ') + ')' : '');
  }
  function ensembleHtml(r) {
    var s = r.s, E = X.ensemble && s.rec && s.rec.engine ? X.ensemble[s.rec.engine] : null;
    if (!E) return '<p class="rx-ens">No ensemble summary for this page.</p>';
    var rna = st.sel.molecule === 'rna', pos = st.sel.pos;
    var hits = (rna ? E.rna : E.protein)[String(pos)] || [];
    function ids(list) { return list.map(function (i) { return E.ids[i]; }).join(', '); }
    var h = '<h4>Across structures (ensemble support; separate from the structure shown)</h4>' +
      '<p>' + esc((rna ? 'RNA position ' : 'Protein position ') + letter(st.sel.molecule, pos) + pos) + ' has at least one Report contact in <b>' +
      hits.length + ' of ' + E.n + '</b> ' + esc(s.rec.engine) + ' structure(s) with a Report contact record in this analysis' +
      (hits.length ? ': <span class="rx-ids">' + esc(ids(hits)) + '</span>' : '') + '.</p>';
    if (r.partners.length) {
      h += '<table class="rx-table"><tr><th>Contact</th><th>Structures listing it</th><th>Structure ids</th></tr>';
      r.partners.forEach(function (p) {
        var key = rna ? p.pos + '-' + pos : pos + '-' + p.pos, l = E.pair[key] || [];
        var name = rna ? letter('protein', p.pos) + p.pos + '-' + letter('rna', pos) + pos : letter('protein', pos) + pos + '-' + letter('rna', p.pos) + p.pos;
        h += '<tr><td>' + esc(name) + '</td><td>' + l.length + ' of ' + E.n + '</td><td class="rx-ids">' + esc(ids(l)) + '</td></tr>';
      });
      h += '</table>';
    }
    h += '<p class="rx-small">Counts are of ' + esc(s.rec.engine) + ' predictions only (other engines are counted separately) and ' +
      'are positions in construct numbering, pooled over chain copies as Report pools them. A count says how often the ' +
      'predictions contain the contact, not whether the real complex does.</p>';
    return h;
  }
  function panel(r) {
    var s = r.s, h = '';
    h += '<p class="rx-structure">Structure on screen: <b>' + esc(s.label) + '</b>' + (s.rec && s.rec.key ? ' <code>' + esc(s.rec.key) + '</code>' : '') + '</p>';
    if (st.note) h += '<p class="rx-note">' + esc(st.note) + '</p>';
    if (!st.sel) {
      h += '<p>No residue selected. Click an RNA nucleotide (or a protein residue) in the viewer to see its contacts in this structure. ' +
        'The overall view shows the contacts supplied to this page.</p>';
      if (!s.rec || !s.rec.available) h += '<p class="rx-note">Contact explorer not available for this structure: ' + esc((s.rec && s.rec.reason) || 'no contact record supplied') + '.</p>';
      el.panel.innerHTML = h; return;
    }
    var rna = st.sel.molecule === 'rna', ch = st.sel.chain, pos = st.sel.pos;
    h += '<h4>Selected ' + (rna ? 'RNA nucleotide' : 'protein residue') + '</h4><table class="rx-kv" id="rnplens-selection" data-molecule="' + esc(st.sel.molecule) +
      '" data-chain="' + esc(ch) + '" data-pos="' + pos + '">' +
      '<tr><th>' + (rna ? 'RNA' : 'Protein') + ' chain</th><td>' + esc(ch) + '</td></tr>' +
      '<tr><th>' + (rna ? 'Nucleotide' : 'Residue') + '</th><td>' + esc(letter(st.sel.molecule, pos)) + (r.res ? ' (' + esc(r.res[3]) + ')' : '') + '</td></tr>' +
      '<tr><th>Construct position</th><td>' + pos + '</td></tr>' +
      '<tr><th>Structure residue</th><td>' + (r.res ? esc(ch + ' ' + r.res[1] + (r.res[2] || '')) + (String(r.res[1]) + (r.res[2] || '') === String(pos) ? ' (same as construct position)' : ' (differs from construct position)') +
        (isModified(st.sel.molecule, r.res) ? '; ' + (rna ? 'modified nucleotide ' : 'non-standard residue ') + esc(r.res[3]) : '') : 'not modelled in this structure') + '</td></tr>' +
      '<tr><th>Prediction</th><td>' + esc(s.label) + '</td></tr></table>';
    if (!s.rec || !s.rec.available) {
      h += '<p class="rx-note" id="rnplens-contact-count" data-count="">Contacts: Not available for this structure (' + esc((s.rec && s.rec.reason) || 'no contact record supplied') + '). Nothing is highlighted besides the selection.</p>';
      el.panel.innerHTML = h; return;
    }
    var n = r.partners.length, what = rna ? 'protein residue' : 'RNA nucleotide';
    h += '<h4>Contacting ' + what + 's in this structure</h4>';
    if (!n) {
      h += '<p id="rnplens-contact-count" data-count="0"><b>No qualifying contact.</b> Report\'s record for this structure lists no ' + what +
        ' with a heavy atom within ' + X.cutoff + ' \u00c5 of this ' + (rna ? 'nucleotide' : 'residue') + '. Nothing is highlighted besides the selection.</p>';
    } else {
      h += '<p id="rnplens-contact-count" data-count="' + n + '"><b>' + n + '</b> ' + what + (n === 1 ? '' : 's') + ' in contact (Report\'s record for this structure).</p>';
      h += '<table class="rx-table" id="rnplens-contact-table"><tr><th>Protein chain</th><th>Protein residue</th><th>RNA chain</th><th>RNA nucleotide</th><th>Contact distance</th></tr>';
      r.rows.forEach(function (c) {
        var pr = ix(s).byPos[c.pc + '|' + c.p], rr = ix(s).byPos[c.rc + '|' + c.r];
        var d = c.d === null || c.d === undefined ? 'Not available' : c.d.toFixed(2) + ' \u00c5 (' + c.pa + '\u2013' + c.ra + ')';
        h += '<tr data-pc="' + esc(c.pc) + '" data-p="' + c.p + '" data-rc="' + esc(c.rc) + '" data-r="' + c.r + '" data-d="' + (c.d === null ? '' : c.d) + '" data-eid="' + esc(c.eid) + '">' +
          '<td>' + esc(c.pc) + '</td><td>' + esc(residueText('protein', c.pc, c.p, pr)) + '</td><td>' + esc(c.rc) + '</td><td>' + esc(residueText('rna', c.rc, c.r, rr)) + '</td><td>' + esc(d) + '</td></tr>';
      });
      h += '</table>';
      var dc = s.rec.distance_check || {};
      h += '<p class="rx-small">Contact distance: minimum distance between heavy atoms (closest atom pair in brackets), recomputed from this structure file. ' +
        (dc.status === 'PASS' ? 'Shown because the recomputed contacts (all residue pairs within ' + X.cutoff + ' \u00c5) equal Report\'s record for this structure.'
                              : 'Not available: ' + esc(s.rec.reason_distances || 'the recomputation was not run') + '.') + '</p>';
    }
    h += ensembleHtml(r);
    el.panel.innerHTML = h;
  }

  // ---- interaction
  function onResidue(chain, authSeq, ins, how) {
    var s = cur(), mol = moleculeOf(s, chain);
    if (!mol) { st.note = 'Clicked residue (chain ' + chain + ', residue ' + authSeq + (ins || '') + ') is not in the declared protein or RNA chain of this structure; selection unchanged.'; render(); return false; }
    var res = ix(s).byAuth[chain + '|' + authSeq + '|' + (ins || '')];
    if (!res) { st.note = 'Clicked residue (chain ' + chain + ', residue ' + authSeq + (ins || '') + ') has no construct position in the page data; selection unchanged.'; render(); return false; }
    selectPosition(mol, chain, res[0], how);
    return true;
  }
  function selectPosition(mol, chain, pos, how) {
    if (st.sel && st.sel.molecule === mol && st.sel.chain === chain && st.sel.pos === pos) {
      st.sel = null; st.note = 'Selection cleared (the same residue was clicked again).';
    } else { st.sel = {molecule: mol, chain: chain, pos: pos}; st.note = ''; }
    render();
  }
  function clear() { st.sel = null; st.note = 'Selection cleared.'; render(); }
  function setMode(m) {
    st.mode = m === 'all' ? 'all' : 'focus';
    st.recentre = true;
    var r = document.querySelectorAll('input[name="rx-mode"]');
    for (var i = 0; i < r.length; i++) r[i].checked = r[i].value === st.mode;
    render();
  }
  function show(k) {
    k = Math.max(0, Math.min(X.structures.length - 1, k | 0));
    var old = st.k; st.k = k; el.select.value = String(k);
    st.recentre = true;                                 // structures need not share a coordinate frame
    st.note = '';
    if (st.sel && old !== k) {
      var s = cur(), r = ix(s).byPos[st.sel.chain + '|' + st.sel.pos];
      if (moleculeOf(s, st.sel.chain) === st.sel.molecule && r) {
        st.note = 'Selection kept on the same chain and construct position; the contacts shown are this structure\'s own.';
      } else {
        st.note = 'Selection cleared: chain ' + st.sel.chain + ' position ' + st.sel.pos + ' is not present in this structure.';
        st.sel = null;
      }
    }
    render();
  }

  function disableMolstarClickBehaviours(plugin) {
    var done = [], cells = [];
    plugin.state.behaviors.cells.forEach(function (c, ref) { cells.push([ref, c]); });
    var p = Promise.resolve();
    cells.forEach(function (rc) {
      var id = rc[1].transform.transformer.id;
      if (['ms-plugin.representation-select-loci', 'ms-plugin.representation-focus-loci', 'ms-plugin.camera-focus-loci'].indexOf(id) < 0) return;
      var params = JSON.parse(JSON.stringify(rc[1].transform.params || {}));
      if (!params.bindings) return;
      Object.keys(params.bindings).forEach(function (b) { params.bindings[b] = {triggers: [], action: '', description: ''}; });
      p = p.then(function () { return plugin.state.behaviors.build().to(rc[0]).update(params).commit(); }).then(function () { done.push(id); });
    });
    return p.then(function () { return done; });
  }

  function start(v) {
    viewer = v; V = window.RNPLENS_VIEW; D = window.RNPLENS_STRUCTURE_DATA; X = V.explorer;
    MVS = molstar.lib.extensions.mvs.MVSData; SE = molstar.lib.structure.StructureElement; SP = molstar.lib.structure.StructureProperties;
    el.root = $('rnplens-explorer'); el.panel = $('rx-panel'); el.select = $('rx-structure');
    X.structures.forEach(function (s, i) { var o = document.createElement('option'); o.value = String(i); o.textContent = (i + 1) + '/' + X.structures.length + '  ' + s.label; el.select.appendChild(o); });
    el.select.addEventListener('change', function () { show(parseInt(el.select.value, 10)); });
    $('rx-prev').addEventListener('click', function () { show(st.k - 1); });
    $('rx-next').addEventListener('click', function () { show(st.k + 1); });
    $('rx-clear').addEventListener('click', clear);
    var radios = document.querySelectorAll('input[name="rx-mode"]');
    for (var i = 0; i < radios.length; i++) radios[i].addEventListener('change', function (e) { if (e.target.checked) setMode(e.target.value); });
    window.RNPLENS_EXPLORER = {
      state: function () {
        var r = resolve();
        return {k: st.k, label: cur().label, key: cur().rec && cur().rec.key, sel: st.sel, mode: st.mode, note: st.note, signature: st.signature,
                want: signature(), lines: (st.shown || {}).lines || [],
                ready: el.root.getAttribute('data-state') === 'READY', available: !!(cur().rec && cur().rec.available),
                residue: r.res, partners: r.partners.map(function (p) { return {molecule: p.molecule, chain: p.chain, pos: p.pos, auth: p.res ? [p.res[1], p.res[2]] : null}; }),
                rows: r.rows.map(function (c) { return {pc: c.pc, p: c.p, rc: c.rc, r: c.r, d: c.d}; })};
      },
      show: show, clear: clear, setMode: setMode,
      selectResidue: function (chain, authSeq, ins) { return onResidue(chain, authSeq, ins || '', 'api'); },
      selectPosition: function (mol, chain, pos) { selectPosition(mol, chain, pos, 'api'); },
      structures: X.structures.length, disabled: []
    };
    return disableMolstarClickBehaviours(viewer.plugin).then(function (done) {
      window.RNPLENS_EXPLORER.disabled = done;
      el.root.setAttribute('data-disabled-behaviours', done.join(' '));
      viewer.plugin.behaviors.interaction.click.subscribe(function (e) {
        var l = e && e.current && e.current.loci;
        if (e && typeof e.button === 'number' && !(e.button & 1)) return;      // primary button only
        if (!l || !SE.Loci.is(l) || SE.Loci.isEmpty(l)) return;                  // empty space: selection unchanged
        var loc = SE.Loci.getFirstLocation(l);
        onResidue(SP.chain.auth_asym_id(loc), SP.residue.auth_seq_id(loc), SP.residue.pdbx_PDB_ins_code(loc) || '', 'click');
      });
      el.select.value = '0';
      render();
    });
  }
  window.RNPLENS_EXPLORER_START = start;
})();
