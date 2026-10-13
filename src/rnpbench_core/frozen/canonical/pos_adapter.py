#!/usr/bin/env python3
"""RNPBENCH_CONSTRUCT_POSITION_ADAPTER_V1 -- diagnostic only, not a production configuration.

THE QUESTION, AS PUT: can the existing metric evaluate the same structures and the same admissible chain
mappings using the benchmark's established construct-position correspondence, WITHOUT re-inferring that
correspondence from sequence or from raw residue numbers?

WHERE THE ADAPTER SITS, established by reading the pinned source rather than by choosing a convenient
place:
    run_on_all_native_interfaces  -> iterates native chain pairs           [UNCHANGED]
      run_on_chains               -> derives one alignment per chain pair  [ONLY THIS STEP REPLACED]
        align_chains/format_alignment
      calc_DockQ                  -> nat_total on the UNTOUCHED native, then aligned residues
                                     via get_aligned_residues             [UNCHANGED]
`calc_DockQ` computes the native contact denominator BEFORE any alignment is consulted, so supplying a
correspondence cannot move that denominator -- which is why the native chains are never pre-trimmed.

HOW THE CORRESPONDENCE IS SUPPLIED. get_aligned_residues consumes a 3-tuple of equal-length strings
(A, match, B): it advances each chain's residue iterator on a non-gap character and pairs where the match
column is "|". So a position-derived alignment is expressible in the metric's OWN interface: one column
per construct position in ascending order, a gap where a side lacks that position, and "|" only where
both sides have it. Nothing about atom selection, contact thresholds, the maximum-total objective or the
failure classes is touched, and the installed package is not edited -- align_chains/format_alignment are
rebound in THIS process only, and only around the interface call, so candidate enumeration (which uses
the same two functions inside group_chains) still runs on the unmodified path.

THE TWO POSITION SOURCES ARE PROVENANCE-VERIFIED, NEVER ASSUMED:
  native : _atom_site.label_seq_id, the canonical polymer index, reached through an explicit
           (auth_asym_id, auth_seq_id, ins_code) -> label_seq_id map read from the reference itself.
           A residue with no numeric label is EXCLUDED and reported, never guessed.
  model  : the residue number, admitted only for a chain the audit verified as contiguous from 1, of a
           length equal to a frozen construct length, and free of insertion codes. Otherwise the chain
           is INDETERMINATE and the adapter refuses rather than infer positions from another alignment.
Insertion codes are preserved in the provenance. If two native residues ever claimed one construct
position, that chain is refused rather than merged -- the frozen treatment is not relaxed to simplify
this adapter.
"""
import collections, contextlib, glob, hashlib, io, itertools, json, os, sys, time

R = "/home/jwen/projects/PCfold3D-RNP"
SD = R + "/outputs/rnp/jpf/scripts_clean"
P = R + "/outputs/rnpbench/pilot"
REP = R + "/outputs/reports"
sys.path.insert(0, SD)

import gemmi
import DockQ.DockQ as D
from rnpbench_score_v2 import polymer_class, admissibility, to_pairs
import corr_mask_audit as A

AA3 = {"ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E", "GLY": "G",
       "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P", "SER": "S",
       "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V", "MSE": "M"}
NUC = {"A": "A", "U": "U", "G": "G", "C": "C", "DA": "A", "DT": "T", "DG": "G", "DC": "C"}


def letter(res):
    n = res.get_resname().strip()
    return AA3.get(n) or NUC.get(n) or "X"


def positions(chain, lab_map=None, model_num=None):
    """(residue, construct_position) for one chain, or a refusal reason.

    For the native side the position comes from the label map. For the model side it is the residue
    number, and ONLY for a chain whose numbering the audit verified as construct positions.
    """
    out, missing, dupes = [], 0, []
    if lab_map is not None:
        seen = {}
        for r in chain.get_residues():
            ic = str(r.id[2]).strip()
            p = lab_map.get((chain.id, r.id[1], ic))
            if p is None:
                missing += 1
                continue
            if p in seen:
                dupes.append(p)
            seen[p] = True
            out.append((r, p, {"parsed_id": list(r.id), "insertion_code": ic,
                               "resname": r.get_resname()}))
    else:
        v = (model_num or {}).get(chain.id, {})
        if not v.get("usable_as_construct_positions"):
            return None, {"refused": "MODEL_NUMBERING_NOT_VERIFIED_AS_CONSTRUCT_POSITIONS",
                          "detail": v}
        for r in chain.get_residues():
            out.append((r, r.id[1], {"parsed_id": list(r.id),
                                     "insertion_code": str(r.id[2]).strip(),
                                     "resname": r.get_resname()}))
    if dupes:
        return None, {"refused": "TWO_NATIVE_RESIDUES_CLAIM_ONE_CONSTRUCT_POSITION",
                      "positions": sorted(set(dupes))[:8]}
    if [p for _, p, _ in out] != sorted(p for _, p, _ in out):
        return None, {"refused": "RESIDUE_ORDER_IS_NOT_ASCENDING_IN_CONSTRUCT_POSITION"}
    return out, {"n_residues": len(out), "residues_without_a_canonical_position": missing}


def construct_alignment(mchain, nchain, lab_map, model_num):
    """A 3-tuple alignment in the metric's own format, derived only from construct positions."""
    mm, minfo = positions(mchain, None, model_num)
    nn, ninfo = positions(nchain, lab_map, None)
    if mm is None or nn is None:
        return None, {"model": minfo, "native": ninfo}
    mpos = {p: (r, meta) for r, p, meta in mm}
    npos = {p: (r, meta) for r, p, meta in nn}
    cols = sorted(set(mpos) | set(npos))
    a, mt, b, pairs = [], [], [], []
    for p in cols:
        inm, inn = p in mpos, p in npos
        a.append(letter(mpos[p][0]) if inm else "-")
        b.append(letter(npos[p][0]) if inn else "-")
        if inm and inn:
            mt.append("|")
            pairs.append({"construct_position": p,
                          "model": mpos[p][1], "native": npos[p][1],
                          "letters_agree": letter(mpos[p][0]) == letter(npos[p][0])})
        else:
            mt.append(" ")
    return (("".join(a), "".join(mt), "".join(b)),
            {"model": minfo, "native": ninfo, "n_columns": len(cols), "n_pairs": len(pairs),
             "expected_pairs": [x["construct_position"] for x in pairs],
             "pair_provenance": pairs[:4],
             "letters_disagree_on": sum(1 for x in pairs if not x["letters_agree"])})


@contextlib.contextmanager
def correspondence_from_construct_positions(lab_map, model_num, log):
    """Rebind ONLY the correspondence step, and only for the duration of one interface call.

    align_chains and format_alignment are also used by group_chains during candidate enumeration, so
    this is entered AFTER candidates are enumerated on the unmodified path and exited immediately after.
    The originals are restored in a finally block so no later call sees the rebound versions.
    """
    real_align, real_format = D.align_chains, D.format_alignment

    # THE DEFECT THIS FIXES, AND IT WAS NEARLY INVISIBLE. run_on_chains, align_chains,
    # get_aligned_residues and get_residue_distances are all @lru_cache'd in the pinned implementation.
    # Evaluating the default route first populated run_on_chains' cache keyed on the chain objects, so
    # the patched call returned the CACHED result and my stub was invoked ZERO times -- every "adapter"
    # number was the default number, and the population run reported that the adapter fixed 15,980
    # residue pairs while changing no score at all. That is the adapter certifying itself against its
    # own mapping table, which is precisely what the ruling forbade. The caches are now cleared on entry
    # and exit, and the caller asserts the stub was actually invoked.
    for fn in ("run_on_chains", "align_chains", "get_aligned_residues", "get_residue_distances"):
        f = getattr(D, fn, None)
        if hasattr(f, "cache_clear"):
            f.cache_clear()

    def align_stub(model_chain, native_chain, use_numbering=False):
        return {"_adapter": True, "m": model_chain, "n": native_chain}

    def format_stub(aln):
        if not (isinstance(aln, dict) and aln.get("_adapter")):
            return real_format(aln)
        got, info = construct_alignment(aln["m"], aln["n"], lab_map, model_num)
        key = "%s->%s" % (aln["n"].id, aln["m"].id)
        if got is None:
            log[key] = {"status": "REFUSED", **info}
            raise D.DockQError("construct-position correspondence unavailable for %s: %s"
                               % (key, info)) if hasattr(D, "DockQError") else \
                RuntimeError("construct-position correspondence unavailable for %s: %s" % (key, info))
        log[key] = {"status": "SUPPLIED", **info}
        log["_invocations"] = log.get("_invocations", 0) + 1
        return {"seqA": got[0], "matches": got[1], "seqB": got[2]}

    D.align_chains, D.format_alignment = align_stub, format_stub
    try:
        yield
    finally:
        D.align_chains, D.format_alignment = real_align, real_format
        for fn in ("run_on_chains", "align_chains", "get_aligned_residues", "get_residue_distances"):
            f = getattr(D, fn, None)
            if hasattr(f, "cache_clear"):
                f.cache_clear()


def evaluate(ms, ns, cm, lab_map=None, model_num=None, mode="default"):
    """One admissible candidate under either correspondence route. Nothing else differs."""
    log = {}
    try:
        if mode == "default":
            for fn in ("run_on_chains", "align_chains", "get_aligned_residues",
                       "get_residue_distances"):
                f = getattr(D, fn, None)
                if hasattr(f, "cache_clear"):
                    f.cache_clear()
            with contextlib.redirect_stderr(io.StringIO()):
                got = D.run_on_all_native_interfaces(ms, ns, chain_map=cm)
        else:
            with correspondence_from_construct_positions(lab_map, model_num, log):
                with contextlib.redirect_stderr(io.StringIO()):
                    got = D.run_on_all_native_interfaces(ms, ns, chain_map=cm)
    except (Exception, SystemExit) as e:
        return {"outcome": "EXCEPTION", "exception": "%s: %s" % (type(e).__name__, str(e)[:200]),
                "correspondence_log": log}
    if mode != "default" and not log.get("_invocations"):
        return {"outcome": "ADAPTER_NOT_APPLIED_NO_NUMBERS_REPORTED",
                "why": ("the correspondence stub was never invoked, so any total here would be the "
                        "default route's. Reported as a harness failure, never as an adapter result."),
                "correspondence_log": log}
    per = got[0] if isinstance(got, tuple) else got
    tot = got[1] if isinstance(got, tuple) else None
    if not per:
        return {"outcome": "NO_NATIVE_INTERFACE_UNDER_THIS_MAPPING", "total_dockq": 0.0,
                "n_interfaces": 0, "correspondence_log": log}
    return {"outcome": "SCORED", "total_dockq": tot, "n_interfaces": len(per),
            "per_interface": {k: {kk: v.get(kk) for kk in
                                  ("DockQ", "fnat", "fnonnat", "nat_correct", "nat_total",
                                   "model_total", "len1", "len2", "iRMSD", "LRMSD")}
                              for k, v in per.items()},
            "correspondence_log": log}


def paired_residues(ms, ns, cm, lab_map, model_num, mode):
    """The residue pair set the metric ACTUALLY used, read back through its own accessor."""
    out = {}
    for a, b in itertools.combinations(list(cm.keys()), 2):
        for nid in (a, b):
            n_, m_ = ns[nid], ms[cm[nid]]
            if mode == "default":
                with contextlib.redirect_stderr(io.StringIO()):
                    al = D.format_alignment(D.align_chains(m_, n_, use_numbering=False))
                    ra, rb = D.get_aligned_residues(m_, n_, tuple(al.values()))
            else:
                got, _ = construct_alignment(m_, n_, lab_map, model_num)
                if got is None:
                    out["%s->%s" % (nid, cm[nid])] = None
                    continue
                ra, rb = D.get_aligned_residues(m_, n_, got)
            out["%s->%s" % (nid, cm[nid])] = [
                {"model_id": list(x.id), "native_id": list(y.id),
                 "native_construct_position": lab_map.get((n_.id, y.id[1], str(y.id[2]).strip())),
                 "model_construct_position": x.id[1]}
                for x, y in zip(ra, rb)]
    return out


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def model_index():
    idx = {}
    for g in (P + "/boltz/**/*.pdb", P + "/boltz/**/*.cif", P + "/af3/**/*.cif", P + "/af3/**/*.pdb"):
        for p in glob.glob(g, recursive=True):
            idx.setdefault(sha(p), p)
    return idx


def rows_by_target():
    by = collections.defaultdict(list)
    for f in sorted(glob.glob(P + "/score_v2_2/rescored_*.json")):
        Dd = json.load(open(f))
        for r in Dd["rows"]:
            r["_engine"], r["_execution"] = Dd["engine"], Dd["execution"]
            by[r["target"]].append(r)
    return by


def one_row(row, idx, tol_override=None):
    """Enumerate admissible candidates on the UNMODIFIED path, then evaluate both routes."""
    t = row["target"]
    mp, nt = idx.get(row["structure_checksum"]), P + "/references/%s.cif" % t
    if not mp:
        return {"target": t, "status": "MODEL_NOT_RESOLVED_BY_CHECKSUM"}
    lab_map, _, _, _ = A.native_label_map(nt)
    key = {x["target"]: x for x in
           json.load(open(REP + "/jpf_rnpbench_pilot_target_key.json"))["targets"]}
    model_num = A.model_numbering_check(mp, A.construct_lengths(t, key))
    tol = row.get("tolerance") if tol_override is None else tol_override
    tol = tol or 0
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            im, mch, nch = D.format_mapping(None, None)
            ms = D.load_PDB(mp, chains=mch, small_molecule=None)
            ns = D.load_PDB(nt, chains=nch, small_molecule=None)
            mc, nc = [c.id for c in ms], [c.id for c in ns]
            cl, rev = D.group_chains(ms, ns, mc, nc, tol)
            maps = list(D.get_all_chain_maps(cl, im, rev, mc, nc))
    except (Exception, SystemExit) as e:
        return {"target": t, "status": "METRIC_REFUSED_THE_INPUT_BEFORE_ANY_CANDIDATE",
                "detail": type(e).__name__}
    cls_m, cls_n = polymer_class(mp), polymer_class(nt)
    cands = []
    for cm in maps:
        pairs, _ = to_pairs(cm, mc, nc)
        verdict, _ = admissibility(pairs, cls_m, cls_n)
        if verdict != "ADMISSIBLE":
            continue
        lbl = D.format_mapping_string(cm)
        old = evaluate(ms, ns, cm, mode="default")
        new = evaluate(ms, ns, cm, lab_map, model_num, mode="adapter")
        po = paired_residues(ms, ns, cm, lab_map, model_num, "default")
        pn = paired_residues(ms, ns, cm, lab_map, model_num, "adapter")

        def frame(pr):
            inf = outf = ind = 0
            for k, v in (pr or {}).items():
                for x in (v or []):
                    if x["native_construct_position"] is None:
                        ind += 1
                    elif x["native_construct_position"] == x["model_construct_position"]:
                        inf += 1
                    else:
                        outf += 1
            return {"in_frame": inf, "out_of_frame": outf, "indeterminate": ind,
                    "n_pairs": inf + outf + ind}
        same_pairs = json.dumps(po, sort_keys=True) == json.dumps(pn, sort_keys=True)
        cands.append({
            "mapping": lbl, "tolerance": tol,
            "default": {**{k: v for k, v in old.items() if k != "correspondence_log"},
                        "correspondence": frame(po)},
            "adapter": {**{k: v for k, v in new.items() if k != "correspondence_log"},
                        "correspondence": frame(pn)},
            "adapter_correspondence_log": new.get("correspondence_log"),
            "identical_pairings": same_pairs,
            "expected_pair_set_equals_actual": None})
    return {"target": t, "engine": row["_engine"], "execution": row["_execution"],
            "structure_checksum": row["structure_checksum"], "model_path": mp,
            "reference_sha256": sha(nt), "status": "EVALUATED",
            "n_admissible_candidates": len(cands), "candidates": cands}


def independent_expected_pairs(row, idx):
    """The pair set expected from construct positions, computed WITHOUT the adapter's own tables.

    Built straight from the reference cif and the model file rather than from construct_alignment, so
    the audit of the adapter's output does not consult the adapter's mapping table.
    """
    t = row["target"]
    mp, nt = idx.get(row["structure_checksum"]), P + "/references/%s.cif" % t
    blk = gemmi.cif.read(nt).sole_block()
    nat = collections.defaultdict(set)
    for r in blk.find("_atom_site.", ["auth_asym_id", "label_seq_id"]):
        ch, lab = gemmi.cif.as_string(r[0]), gemmi.cif.as_string(r[1])
        # non-polymer rows carry an empty or placeholder label_seq_id; they are skipped, never coerced
        try:
            nat[ch].add(int(lab))
        except (ValueError, TypeError):
            continue
    st = gemmi.read_structure(mp)
    st.setup_entities()
    mod = {ch.name: {r.seqid.num for r in ch} for ch in st[0]}
    return {"native_positions_per_chain": {k: sorted(v) for k, v in nat.items()},
            "model_positions_per_chain": {k: sorted(v) for k, v in mod.items()}}


def relabel_test(row, idx):
    """Change ONLY author identifiers on disposable copies; the selected pairs must not change.

    This is the test that the adapter depends on construct identity rather than quietly reverting to
    author numbering: the geometry, the atoms and the explicit construct mapping are preserved, and only
    auth_asym_id / auth_seq_id are rewritten. The copies are written to a scratch path and are never
    used for any reported score.
    """
    t = row["target"]
    mp, nt = idx.get(row["structure_checksum"]), P + "/references/%s.cif" % t
    scratch = R + "/outputs/rnp/jpf/pos_adapter_scratch"
    os.makedirs(scratch, exist_ok=True)
    alt = os.path.join(scratch, "%s_relabelled.cif" % t)
    doc = gemmi.cif.read(nt)
    blk = doc.sole_block()
    tab = blk.find("_atom_site.", ["auth_asym_id", "auth_seq_id", "label_seq_id"])
    shift, remap = 5000, {}
    for r in tab:
        ch = gemmi.cif.as_string(r[0])
        remap.setdefault(ch, chr(ord("a") + len(remap) % 26))
        try:
            au = int(gemmi.cif.as_string(r[1]))
        except ValueError:
            continue
        r[0] = remap[ch]
        r[1] = str(au + shift)              # label_seq_id column is deliberately left untouched
    doc.write_file(alt)

    key = {x["target"]: x for x in
           json.load(open(REP + "/jpf_rnpbench_pilot_target_key.json"))["targets"]}
    model_num = A.model_numbering_check(mp, A.construct_lengths(t, key))
    out = {"relabelled_reference": alt, "author_chain_remap": remap, "author_seq_shift": shift,
           "label_seq_id_left_untouched": True}
    try:
        lab0, _, _, _ = A.native_label_map(nt)
        lab1, _, _, _ = A.native_label_map(alt)
        with contextlib.redirect_stderr(io.StringIO()):
            im, mch, nch = D.format_mapping(None, None)
            ms = D.load_PDB(mp, chains=mch, small_molecule=None)
            n0 = D.load_PDB(nt, chains=nch, small_molecule=None)
            n1 = D.load_PDB(alt, chains=nch, small_molecule=None)
            mc = [c.id for c in ms]
            c0, c1 = [c.id for c in n0], [c.id for c in n1]
            cl0, rv0 = D.group_chains(ms, n0, mc, c0, 0)
            cl1, rv1 = D.group_chains(ms, n1, mc, c1, 0)
            m0 = list(D.get_all_chain_maps(cl0, im, rv0, mc, c0))
            m1 = list(D.get_all_chain_maps(cl1, im, rv1, mc, c1))
        # compare the CONSTRUCT-POSITION pair sets, which must be invariant to author relabelling
        def posset(ms_, ns_, maps, lab):
            best = {}
            for cm in maps:
                for a, b in itertools.combinations(list(cm.keys()), 2):
                    for nid in (a, b):
                        got, _ = construct_alignment(ms_[cm[nid]], ns_[nid], lab, model_num)
                        if got is None:
                            continue
                        ra, rb = D.get_aligned_residues(ms_[cm[nid]], ns_[nid], got)
                        key2 = "%s|%d" % (cm[nid], len(ra))
                        best[key2] = sorted(
                            (x.id[1], lab.get((ns_[nid].id, y.id[1], str(y.id[2]).strip())))
                            for x, y in zip(ra, rb))
            return best
        s0 = posset(ms, n0, m0, lab0)
        s1 = posset(ms, n1, m1, lab1)
        out["n_chain_correspondences_compared"] = len(s0)
        out["pair_sets_identical_after_author_relabelling"] = (s0 == s1)
        if s0 != s1:
            diff = [k for k in set(s0) | set(s1) if s0.get(k) != s1.get(k)]
            out["differing_keys"] = diff[:6]
    except (Exception, SystemExit) as e:
        out["error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
    return out


CONTROLS = ["8X5D", "4RDX", "1CGM", "4C9D", "1LAJ", "6NY2"]


def stage_controls():
    idx = model_index()
    by = rows_by_target()
    recs = {}
    for t in CONTROLS:
        rr = [x for x in by.get(t, []) if idx.get(x["structure_checksum"])]
        if not rr:
            recs[t] = {"status": "NO_RESOLVABLE_ROW"}
            continue
        row = rr[0]
        rec = one_row(row, idx)
        rec["independent_position_inventory"] = independent_expected_pairs(row, idx)
        recs[t] = rec
        print("  %-6s %s" % (t, rec.get("status")), flush=True)
        for c in rec.get("candidates", [])[:6]:
            d, n = c["default"], c["adapter"]
            print("     %-10s default: %-28s in/out %s/%s | adapter: %-28s in/out %s/%s | same_pairs=%s"
                  % (c["mapping"], d.get("outcome"), d["correspondence"]["in_frame"],
                     d["correspondence"]["out_of_frame"], n.get("outcome"),
                     n["correspondence"]["in_frame"], n["correspondence"]["out_of_frame"],
                     c["identical_pairings"]), flush=True)
    rl = {}
    for t in ("8X5D", "4RDX"):
        rr = [x for x in by.get(t, []) if idx.get(x["structure_checksum"])]
        if rr:
            rl[t] = relabel_test(rr[0], idx)
            print("  relabel %-6s identical=%s (%s correspondences)"
                  % (t, rl[t].get("pair_sets_identical_after_author_relabelling"),
                     rl[t].get("n_chain_correspondences_compared")), flush=True)
    # ---- the four decisive checks, computed over every control candidate
    checks = {"position_correctness_and_coverage": [], "geometry_and_reference_preservation": [],
              "evaluation_preservation": [], "control_behaviour": []}
    for t, rec in recs.items():
        for c in rec.get("candidates", []) or []:
            d, n = c["default"], c["adapter"]
            dc, nc = d["correspondence"], n["correspondence"]
            checks["position_correctness_and_coverage"].append({
                "target": t, "mapping": c["mapping"],
                "out_of_frame_default": dc["out_of_frame"], "out_of_frame_adapter": nc["out_of_frame"],
                "pairs_default": dc["n_pairs"], "pairs_adapter": nc["n_pairs"],
                "zero_shift": nc["out_of_frame"] == 0,
                "coverage_not_bought_by_dropping_pairs": nc["n_pairs"] >= dc["n_pairs"],
                "PASS": nc["out_of_frame"] == 0 and nc["n_pairs"] >= dc["n_pairs"]})
            di, ni = d.get("per_interface") or {}, n.get("per_interface") or {}
            for ik in sorted(set(di) | set(ni)):
                a, b = di.get(ik, {}), ni.get(ik, {})
                checks["geometry_and_reference_preservation"].append({
                    "target": t, "mapping": c["mapping"], "interface": ik,
                    "nat_total_default": a.get("nat_total"), "nat_total_adapter": b.get("nat_total"),
                    "PASS": a.get("nat_total") == b.get("nat_total")})
            checks["evaluation_preservation"].append({
                "target": t, "mapping": c["mapping"],
                "same_candidate_identity": True,
                "outcome_default": d.get("outcome"), "outcome_adapter": n.get("outcome"),
                "interfaces_default": d.get("n_interfaces"), "interfaces_adapter": n.get("n_interfaces"),
                "PASS": d.get("n_interfaces") == n.get("n_interfaces")})
            if c["identical_pairings"]:
                x, y = d.get("total_dockq"), n.get("total_dockq")
                agree = (x is None and y is None) or (
                    x is not None and y is not None and abs(x - y) <= 1e-9)
                checks["control_behaviour"].append({
                    "target": t, "mapping": c["mapping"], "total_default": x, "total_adapter": y,
                    "PASS": agree,
                    "note": "identical residue pairings must reproduce the same total"})
    summary = {k: {"n": len(v), "passed": sum(1 for x in v if x["PASS"]),
                   "failed": [x for x in v if not x["PASS"]][:6]} for k, v in checks.items()}
    summary["identifier_relabelling"] = {
        "n": len(rl), "passed": sum(1 for v in rl.values()
                                    if v.get("pair_sets_identical_after_author_relabelling")),
        "detail": rl}
    na = [x for t, rec in recs.items() for x in (rec.get("candidates") or [])
          if x["adapter"].get("outcome") == "ADAPTER_NOT_APPLIED_NO_NUMBERS_REPORTED"]
    summary["adapter_not_applied_candidates"] = {"n": len(na), "passed": 0 if na else 1, "failed": na[:3]}
    print("  --- decisive checks ---", flush=True)
    for kk, v in summary.items():
        print("     %-38s %s/%s passed" % (kk, v["passed"], v["n"]), flush=True)
        for f in (v.get("failed") or [])[:3]:
            print("        FAIL %s" % json.dumps(f)[:150], flush=True)
    json.dump({"controls": recs, "relabel_tests": rl, "checks": checks, "summary": summary},
              open("/tmp/pos_adapter_controls.json", "w"), indent=1, default=str)
    print("  written /tmp/pos_adapter_controls.json", flush=True)




def stage_population():
    """Uniform diagnostic over ALL 1,440 rows and every admissible candidate mapping.

    Includes the admitted 840 as ruled -- the diagnostic is not restricted to current winners or to
    previously score-contributing candidates, because a corrected correspondence can change which
    mapping attains the maximum.
    """
    idx = model_index()
    rows = []
    for f in sorted(glob.glob(P + "/score_v2_2/rescored_*.json")):
        Dd = json.load(open(f))
        for r in Dd["rows"]:
            r["_engine"], r["_execution"] = Dd["engine"], Dd["execution"]
            rows.append(r)
    out, t0 = [], time.time()
    for i, row in enumerate(rows):
        rec = one_row(row, idx)
        slim = {"target": rec["target"], "engine": row["_engine"], "execution": row["_execution"],
                "structure_checksum": row["structure_checksum"], "status": rec.get("status"),
                "old_dockq": row.get("old_dockq"), "v22_dockq": row.get("new_dockq"),
                "v22_selected_mapping": row.get("selected_mapping"), "candidates": []}
        for c in rec.get("candidates", []) or []:
            d, n = c["default"], c["adapter"]
            slim["candidates"].append({
                "mapping": c["mapping"], "tolerance": c["tolerance"],
                "default_outcome": d.get("outcome"), "default_total": d.get("total_dockq"),
                "default_in_frame": d["correspondence"]["in_frame"],
                "default_out_of_frame": d["correspondence"]["out_of_frame"],
                "adapter_outcome": n.get("outcome"), "adapter_total": n.get("total_dockq"),
                "adapter_in_frame": n["correspondence"]["in_frame"],
                "adapter_out_of_frame": n["correspondence"]["out_of_frame"],
                "adapter_indeterminate": n["correspondence"]["indeterminate"],
                "identical_pairings": c["identical_pairings"],
                "nat_total_default": sorted((d.get("per_interface") or {}).items())
                                     and {k: v.get("nat_total") for k, v in (d.get("per_interface") or {}).items()},
                "nat_total_adapter": {k: v.get("nat_total") for k, v in (n.get("per_interface") or {}).items()},
                # the log also carries the integer invocation counter, so non-dict values are skipped
                "refusals": {k: v for k, v in (c.get("adapter_correspondence_log") or {}).items()
                             if isinstance(v, dict) and v.get("status") == "REFUSED"},
                "adapter_invocations": (c.get("adapter_correspondence_log") or {}).get("_invocations", 0)})
        def best(kind):
            sc = [c for c in slim["candidates"] if c[kind + "_outcome"] == "SCORED"
                  and c[kind + "_total"] is not None]
            if not sc:
                return None, None
            b = max(sc, key=lambda c: c[kind + "_total"])
            return b["mapping"], b[kind + "_total"]
        slim["default_winner"], slim["default_max_total"] = best("default")
        slim["adapter_winner"], slim["adapter_max_total"] = best("adapter")
        slim["winner_changed"] = (slim["default_winner"] != slim["adapter_winner"])
        out.append(slim)
        if (i + 1) % 200 == 0:
            print("      %d/%d (%.0fs)" % (i + 1, len(rows), time.time() - t0), flush=True)
    q = P + "/pos_adapter/population.json"
    os.makedirs(os.path.dirname(q), exist_ok=True)
    json.dump({"contract_id": "RNPBENCH_CONSTRUCT_POSITION_ADAPTER_POPULATION_V1",
               "n_rows": len(out), "rows": out}, open(q, "w"), default=str)
    print("   written %s | rows %d | %.0fs" % (q, len(out), time.time() - t0), flush=True)


if __name__ == "__main__":
    st = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else "controls"
    {"controls": stage_controls, "population": stage_population}[st]()
