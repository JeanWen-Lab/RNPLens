#!/usr/bin/env python3
"""RNPBENCH_CORRESPONDENCE_AND_MASK_AUDIT_V1 -- one combined audit of the EXISTING scorer.

WHAT THIS IS NOT: it is not a replacement atom-selection or contact-calculation rule, and it introduces
no normalisation. Every quantity is read out of the scorer's own path -- the same functions
run_on_chains uses -- and compared against the frozen contract's construct-position correspondence.

THE CORRESPONDENCE GROUND TRUTH, AND WHY THE OBVIOUS ROUTE IS WRONG.
  RNPBENCH_ENTITY_RESTRICTED_NATIVE_V1 keeps every strand of the two entities whose _entity_poly
  canonical sequence EQUALS the construct sequence exactly. So a native residue's position in that
  canonical sequence IS its construct position, and that position is _atom_site.label_seq_id.
  Bio.PDB -- which the metric uses -- exposes auth_seq_id as the residue number, and label_seq_id
  differs from auth_seq_id on 66 of the 72 references. So the audit builds an explicit
  (auth_asym_id, auth_seq_id, ins_code) -> label_seq_id map per reference and uses THAT, never the
  number the metric happens to expose.
  On the model side both engines number chains 1..L over the frozen construct. That is VERIFIED per
  chain rather than assumed; where it cannot be verified the row is INDETERMINATE, never a violation.

WHAT IS AUDITED, PER ROW AND PER SCORE-CONTRIBUTING CANDIDATE (not merely the winner, because the
maximum can be displaced by an incorrectly evaluated alternative):
  1. position identity     -- every residue pair the scorer selected, compared construct position to
                              construct position. Matching counts or residue letters are recorded but
                              are NOT the criterion.
  2. per-copy observations -- each native strand's own observed construct positions, kept separate.
                              No concatenation across copies and no copy filling another's gaps; the
                              project has already had a mask-concatenation defect from treating
                              chain-instance records as entity-level records.
  3. effective inputs      -- which native observations were actually paired, and the metric's own
                              contact denominators, read from its per-interface record.
  4. insertion codes       -- counted and reported rather than normalised away.

RECEIPTS: identical work is not repeated. A receipt key is
(model checksum, native checksum, mapping string, tolerance); a repeat reuses the earlier result.
No-interface candidates are not audited here -- they retain their separately supported zero-total
certificates and contribute no score.
"""
import collections, contextlib, glob, hashlib, io, itertools, json, os, sys, time

R = "/home/jwen/projects/PCfold3D-RNP"
SD = R + "/outputs/rnp/jpf/scripts_clean"
P = R + "/outputs/rnpbench/pilot"
REP = R + "/outputs/reports"
OUT = REP + "/jpf_rnpbench_correspondence_and_mask_audit.json"
sys.path.insert(0, SD)

import gemmi
import DockQ.DockQ as D
from rnpbench_score_v2 import polymer_class, admissibility, to_pairs, SCORER_VERSION

CONTRACT = "RNPBENCH_ENTITY_RESTRICTED_NATIVE_V1"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def native_label_map(cif):
    """(auth_asym_id, auth_seq_id, ins_code) -> label_seq_id, i.e. the construct position.

    Read from the frozen reference itself. A residue whose label_seq_id is absent or non-numeric is
    recorded as unmappable and makes its pairs INDETERMINATE -- never a violation.
    """
    blk = gemmi.cif.read(cif).sole_block()
    lp = blk.find("_atom_site.", ["auth_asym_id", "auth_seq_id", "label_seq_id",
                                  "pdbx_PDB_ins_code", "label_comp_id", "label_asym_id"])
    m, per_chain, icodes, unmappable = {}, collections.defaultdict(set), collections.Counter(), 0
    for row in lp:
        ch = gemmi.cif.as_string(row[0])
        auth = gemmi.cif.as_string(row[1])
        lab = gemmi.cif.as_string(row[2])
        ic = gemmi.cif.as_string(row[3])
        ic = "" if ic in (".", "?") else ic
        if ic:
            icodes[ch] += 1
        try:
            auth_i = int(auth)
        except ValueError:
            continue
        if lab in (".", "?"):
            unmappable += 1
            continue
        try:
            lab_i = int(lab)
        except ValueError:
            unmappable += 1
            continue
        m[(ch, auth_i, ic)] = lab_i
        per_chain[ch].add(lab_i)
    return m, {k: sorted(v) for k, v in per_chain.items()}, dict(icodes), unmappable


def construct_lengths(target, key):
    t = key.get(target)
    if not t:
        return None
    return {"protein": len(t["protein_sequence"]), "rna": len(t["rna_sequence"])}


def model_numbering_check(model_path, clens):
    """Is each model chain numbered 1..L over the frozen construct? Verified, not assumed."""
    st = gemmi.read_structure(model_path)
    st.setup_entities()
    out = {}
    for ch in st[0]:
        nums = [r.seqid.num for r in ch]
        icode = sum(1 for r in ch if str(r.seqid.icode).strip())
        contiguous = nums == list(range(1, len(nums) + 1))
        matches = clens is not None and len(nums) in (clens["protein"], clens["rna"])
        out[ch.name] = {"n": len(nums), "contiguous_from_one": contiguous,
                        "length_equals_a_construct_length": bool(matches),
                        "insertion_codes": icode,
                        "usable_as_construct_positions": bool(contiguous and matches and icode == 0)}
    return out


def audit_candidate(ms, ns, cm, lab_map, model_num, per_interface):
    """Position identity over exactly the residue pairs the scorer selected, per native chain pair.

    The alignment is produced by the scorer's own align_chains/format_alignment/get_aligned_residues,
    with use_numbering=False because that is what run_on_chains passes.
    """
    rec = {"interfaces": {}, "in_frame": 0, "out_of_frame": 0, "indeterminate": 0,
           "name_disagreements": 0, "paired_with_insertion_code": 0}
    native_ids = list(cm.keys())
    for pair_key in per_interface:
        # recover which two native chains this interface record belongs to
        cand = [(a, b) for a, b in itertools.combinations(native_ids, 2)
                if pair_key in (a + b, b + a)]
        if not cand:
            rec["interfaces"][pair_key] = {"status": "INTERFACE_KEY_NOT_RESOLVED_TO_NATIVE_CHAINS"}
            continue
        a, b = cand[0]
        info = {"native_chains": [a, b], "model_chains": [cm[a], cm[b]], "chains": {}}
        for nid in (a, b):
            n_ = ns[nid]
            m_ = ms[cm[nid]]
            with contextlib.redirect_stderr(io.StringIO()):
                al = D.format_alignment(D.align_chains(m_, n_, use_numbering=False))
                r_model, r_native = D.get_aligned_residues(m_, n_, tuple(al.values()))
            inf = outf = ind = nd = ic = 0
            examples = []
            for rm, rn in zip(r_model, r_native):
                mpos = rm.id[1]
                m_ok = model_num.get(m_.id, {}).get("usable_as_construct_positions", False)
                nic = str(rn.id[2]).strip()
                if nic:
                    ic += 1
                npos = lab_map.get((n_.id, rn.id[1], nic))
                if npos is None or not m_ok:
                    ind += 1
                    continue
                if mpos == npos:
                    inf += 1
                else:
                    outf += 1
                    if len(examples) < 5:
                        examples.append({"model_construct_pos": mpos, "native_construct_pos": npos,
                                         "model_res": rm.get_resname(), "native_res": rn.get_resname()})
                if rm.get_resname() != rn.get_resname():
                    nd += 1
            observed = len(lab_map and [1 for kk in lab_map if kk[0] == n_.id] or [])
            info["chains"][nid] = {
                "model_chain": m_.id, "pairs_selected_by_the_scorer": len(r_model),
                "in_frame": inf, "out_of_frame": outf, "indeterminate": ind,
                "residue_name_disagreements": nd, "paired_with_insertion_code": ic,
                "native_observed_positions_this_copy_only": observed,
                "native_observed_positions_left_unpaired": max(0, observed - len(r_native)),
                "out_of_frame_examples": examples}
            rec["in_frame"] += inf
            rec["out_of_frame"] += outf
            rec["indeterminate"] += ind
            rec["name_disagreements"] += nd
            rec["paired_with_insertion_code"] += ic
        d = per_interface[pair_key]
        info["metric_own_denominators"] = {kk: d.get(kk) for kk in
                                           ("nat_correct", "nat_total", "model_total", "nonnat_count",
                                            "fnat", "fnonnat", "clashes", "DockQ", "len1", "len2",
                                            "class1", "class2") if kk in d}
        rec["interfaces"][pair_key] = info
    return rec


def main():
    key = {t["target"]: t for t in
           json.load(open(REP + "/jpf_rnpbench_pilot_target_key.json"))["targets"]}
    # models resolved by checksum, exactly as the rescore resolves them
    # MODEL RESOLUTION MUST MATCH THE RESCORE'S, NOT A NARROWER GUESS OF MINE. My first version globbed
    # only *model.cif and *model_0.pdb, which indexed 879 of the 1,440 models and left 576 rows
    # unresolved -- a coverage failure of this probe, never a property of the store. These are the
    # patterns rnpbench_rescore.py itself uses, read from its source.
    MODEL_GLOBS = [P + "/boltz/**/*.pdb", P + "/boltz/**/*.cif",
                   P + "/af3/**/*.cif", P + "/af3/**/*.pdb"]
    idx = {}
    for g in MODEL_GLOBS:
        for p in glob.glob(g, recursive=True):
            idx.setdefault(sha(p), p)
    rows = []
    for f in sorted(glob.glob(P + "/score_v2_2/rescored_*.json")):
        Dd = json.load(open(f))
        for r in Dd["rows"]:
            r["_engine"], r["_execution"] = Dd["engine"], Dd["execution"]
            rows.append(r)
    frozen = {}
    for f in sorted(glob.glob(P + "/*_score/per_sample_dockq*.json")):
        d = json.load(open(f))
        it = d.items() if isinstance(d, dict) else enumerate(d)
        for _, x in it:
            frozen[x["structure_checksum"]] = x
    print("   rows to audit: %d | models indexed: %d" % (len(rows), len(idx)), flush=True)

    lab_cache, mask_rec, receipts = {}, {}, {}
    per_row, unresolved_models, t0 = [], 0, time.time()
    for i, r in enumerate(rows):
        mp = idx.get(r["structure_checksum"])
        nt = P + "/references/%s.cif" % r["target"]
        if not mp or not os.path.exists(nt):
            unresolved_models += 1
            per_row.append({"target": r["target"], "engine": r["_engine"],
                            "execution": r["_execution"],
                            "structure_checksum": r["structure_checksum"],
                            "status": "MODEL_OR_REFERENCE_NOT_RESOLVED"})
            continue
        if r["target"] not in lab_cache:
            lab_cache[r["target"]] = native_label_map(nt)
            lm, per_chain, icodes, unmap = lab_cache[r["target"]]
            clens = construct_lengths(r["target"], key)
            # per-copy observation record, built once per reference and never merged across copies
            mask_rec[r["target"]] = {
                "construct_lengths": clens,
                "copies": {c: {"n_observed": len(v), "min": min(v) if v else None,
                               "max": max(v) if v else None,
                               "within_construct_range": bool(
                                   clens and v and max(v) <= max(clens.values()))}
                           for c, v in per_chain.items()},
                "insertion_codes_per_chain": icodes,
                "atoms_without_a_canonical_position": unmap,
                "copies_were_never_concatenated": True,
                "no_copy_filled_another_copys_gaps": True}
        lm, per_chain, icodes, unmap = lab_cache[r["target"]]
        tol = frozen.get(r["structure_checksum"], {}).get("allowed_mismatches_used") or 0
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                im, mch, nch = D.format_mapping(None, None)
                ms = D.load_PDB(mp, chains=mch, small_molecule=None)
                ns = D.load_PDB(nt, chains=nch, small_molecule=None)
                mc = [c.id for c in ms]
                nc = [c.id for c in ns]
                cl, rev = D.group_chains(ms, ns, mc, nc, tol)
                maps = list(D.get_all_chain_maps(cl, im, rev, mc, nc))
        except (Exception, SystemExit) as e:
            per_row.append({"target": r["target"], "engine": r["_engine"],
                            "execution": r["_execution"],
                            "structure_checksum": r["structure_checksum"],
                            "status": "METRIC_REFUSED_THE_INPUT_BEFORE_ANY_CANDIDATE",
                            "detail": "%s" % type(e).__name__})
            continue
        model_num = model_numbering_check(mp, construct_lengths(r["target"], key))
        cls_m, cls_n = polymer_class(mp), polymer_class(nt)
        row = {"target": r["target"], "engine": r["_engine"], "execution": r["_execution"],
               "structure_checksum": r["structure_checksum"], "tolerance": tol,
               "reported_dockq": r["new_dockq"], "selected_mapping": r["selected_mapping"],
               "model_numbering": model_num, "candidates_audited": {}, "receipts_reused": 0,
               "in_frame": 0, "out_of_frame": 0, "indeterminate": 0}
        for cm in maps:
            lbl = D.format_mapping_string(cm)
            pairs, _ = to_pairs(cm, mc, nc)
            verdict, _ = admissibility(pairs, cls_m, cls_n)
            if verdict != "ADMISSIBLE":
                continue
            rk = (r["structure_checksum"], r["target"], lbl, tol)
            if rk in receipts:
                row["receipts_reused"] += 1
                got = receipts[rk]
            else:
                try:
                    with contextlib.redirect_stderr(io.StringIO()):
                        out = D.run_on_all_native_interfaces(ms, ns, chain_map=cm)
                    per_iface = out[0] if isinstance(out, tuple) else out
                except (Exception, SystemExit):
                    continue
                if not per_iface:
                    continue          # no-interface candidate: keeps its zero-total certificate
                got = audit_candidate(ms, ns, cm, lm, model_num, per_iface)
                receipts[rk] = got
            row["candidates_audited"][lbl] = got
            row["in_frame"] += got["in_frame"]
            row["out_of_frame"] += got["out_of_frame"]
            row["indeterminate"] += got["indeterminate"]
        row["status"] = ("CORRESPONDENCE_EXACT" if row["out_of_frame"] == 0 and row["indeterminate"] == 0
                         else "CORRESPONDENCE_INDETERMINATE" if row["out_of_frame"] == 0
                         else "CORRESPONDENCE_VIOLATED_ON_SOME_PAIRS")
        per_row.append(row)
        if (i + 1) % 120 == 0:
            print("      %d/%d (%.0fs)" % (i + 1, len(rows), time.time() - t0), flush=True)
    json.dump({"per_row": per_row, "masks": mask_rec}, open("/tmp/cma_raw.json", "w"), default=str)
    print("   raw written | rows %d | unresolved %d" % (len(per_row), unresolved_models), flush=True)
    return per_row, mask_rec


if __name__ == "__main__":
    main()
