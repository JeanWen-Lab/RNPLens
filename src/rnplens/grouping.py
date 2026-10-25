"""Binding-hypothesis grouping and two-group difference maps (Function 6; Specification B v2, frozen 16 Oct 2026,
with Amendments 1 and 2 in records/grouping/).

WHAT THIS DOES. Many predicted structures of one complex are grouped into a few explicitly defined binding
proposals: level 1 by protein binding surface (U), level 2 by contact register (R) inside each surface group.
Agglomerative clustering with average (UPGMA) linkage on d = 1 - agreement, in exact rational arithmetic
(fractions.Fraction of integer set sizes), merging while the mean agreement between two clusters is >= t, with
ties broken by canonical keys (sha256 of the structure file used, structure id). The cuts t = 0.3, 0.5 and 0.7
are rc3 Report's three predefined settings and are always all reported; t = 0.5 is the primary cut.

WHAT THIS DOES NOT DO. It never predicts a structure, never ranks a group or a representative, never orders
groups by size, and never treats recurrence among predictions as evidence that a proposal is right. RNA
conformation difference (Spec B 'Q') is unavailable: its correspondence route is blocked.

NUMBERS COME FROM rc3 REPORT'S FROZEN CODE ONLY.
  contacts C_s   rnpbench_report.geometry.interface_contacts (via Report's contacts_by_output.json, or via
                 Report's own per-output routine agreement.analyse_output when there is no analysis directory)
  R, U           rnpbench_report.geometry.weighted_jaccard with unit weights (exact Fraction used for clustering;
                 the two are checked equal for every pair)
  P              rnpbench_report.geometry.rna_pose_difference, argument order (engine, execution) as Report's
                 contract validation orders outputs (Amendment 2); descriptive only, never used for grouping.
"""
import argparse
import collections
import html
import json
import os
import re
import sys
from fractions import Fraction

import numpy as np

from rnpbench_report import agreement as report_agreement
from rnpbench_report import contract as report_contract
from rnpbench_report import geometry

from . import provenance as pv
from . import trace

THRESHOLDS = ("0.3", "0.5", "0.7")
PRIMARY = "0.5"
FREQUENT_CUT = Fraction(1, 2)
SIZE_NOTE = ("Group size reflects how often the supplied predictions produced this proposal; repeated samples "
             "from one model are not independent evidence.")
DIFF_CAVEAT = ("A contact distinguishing two predicted groups is a candidate observation for expert review; it does "
               "not establish a biological contact. Mutation effects can reflect RNA structural change as well as "
               "loss of a contact. No mutation is recommended and no effect is predicted.")
Q_STATEMENT = "RNA conformation difference: unavailable (blocked correspondence route)"
PLACEMENT_NOTE = ("RNA pose difference (P) is shown as a descriptive spread only. RNPLens Diagnose found that "
                  "disagreement in RNA placement between predictions cannot be attributed to error, so a wide "
                  "spread is not a defect of any member.")
NOT_RANKED = ("Groups are listed with the group holding the engine-designated structure first and the others by "
              "their smallest canonical key (sha256 of the structure file, structure id). They are never ordered "
              "by size, and no group or representative is ranked or recommended.")
FREQUENT_TEXT = ("'Frequent' is a presentation cut-point: present in at least half of the group's members in which "
                 "both positions are resolved (fraction >= 1/2). A position that is not resolved counts as 'not "
                 "observed', never as 'no contact'.")
LIMITS = ["Grouping describes how the supplied predictions distribute over binding proposals; it does not say which "
          "proposal, if any, matches the real complex.",
          "The cuts 0.3, 0.5 and 0.7 are sensitivity settings inherited from rc3 Report, not calibrated levels; "
          "an expert may split or merge proposals differently, which is why all three cuts and the dendrogram are shown.",
          "With few structures (for example 5) grouping mostly restates pairwise agreement.",
          Q_STATEMENT + "; groups that differ only in RNA-internal conformation are not separated beyond what P and "
          "the contact register show."]
FORBIDDEN = [r"\bbest\b", r"\bmost likely\b", r"\bcorrect group\b", r"\bconfidence of the group\b"]
DEFINITION = ("Level 1 groups eligible interface structures by protein surface agreement U = Jaccard of protein "
              "positions in contact; level 2 groups each level-1 group by contact-register agreement R = Jaccard of "
              "protein x RNA contact pairs (heavy atoms < 5.0 A, construct numbering, rc3 Report interface_contacts); "
              "both via Report's weighted_jaccard with unit weights. Average-linkage (UPGMA) clustering on "
              "d = 1 - agreement in exact rational arithmetic, merging while d <= 1 - t, ties by canonical key "
              "(sha256 of file used, structure id); t in {0.3, 0.5, 0.7}, primary 0.5, same t at both levels. "
              "Structures with no contact form the 'no interface' group; ineligible structures are listed, never "
              "grouped. Representative = register medoid (highest mean R to the other members, ties by canonical "
              "key). P = Report's rna_pose_difference, descriptive spread only. Spec B v2 with Amendments 1-2.")

CAPABILITIES = [
    {"id": "hypothesis_grouping", "menu": "E",
     "label": "Group the predicted structures into binding proposals (protein surface, then contact register); "
              "groups are not ranked",
     "status": "DESCRIPTIVE", "needs": ["project", "analysis"], "call": "rnplens.grouping:run_capability",
     "limits": "Groups describe how the supplied predictions distribute over binding proposals; group size and "
               "recurrence are not evidence that a proposal matches the real complex."},
    {"id": "group_difference", "menu": None,
     "label": "Shared and group-specific contacts between two binding-proposal groups",
     "status": "DESCRIPTIVE", "needs": ["analysis", "groups"], "call": "rnplens.grouping:diff_capability",
     "limits": DIFF_CAVEAT},
]


class GroupingInputError(ValueError):
    """Malformed, inconsistent or ambiguous input. Raised before anything is written."""


# ----------------------------------------------------------------------------------------------- agreement
def canonical_key(s):
    return (s["sha256"], s["id"])


def exact_jaccard(a, b):
    """|a & b| / |a | b| as a Fraction; None when both are empty (never evaluated in clustering)."""
    a, b = set(a), set(b)
    u = len(a | b)
    return None if u == 0 else Fraction(len(a & b), u)


def report_jaccard(a, b):
    """rc3 Report's weighted_jaccard with unit weights (the parity route)."""
    return geometry.weighted_jaccard({x: 1 for x in a}, {x: 1 for x in b})


def _agreement(a, b):
    """(exact Fraction, Report float); the two must agree exactly (integer counts, correctly rounded division)."""
    ex, rep = exact_jaccard(a, b), report_jaccard(a, b)
    if (ex is None) != (rep is None) or (ex is not None and float(ex) != rep):
        raise RuntimeError("exact Jaccard %s and Report's weighted_jaccard %s differ" % (ex, rep))
    return ex, rep


def _frac(x):
    return None if x is None else "%d/%d" % (x.numerator, x.denominator)


# ----------------------------------------------------------------------------------------------- clustering
def upgma(keys, agree):
    """Exact average-linkage merge sequence over `keys` (canonical keys), run to a single cluster.
    agree(k1, k2) -> Fraction in [0, 1]. Distances d = 1 - agreement; a cluster distance is the mean pairwise d.
    Ties: the lexicographically smaller (min key of cluster 1, min key of cluster 2), the pair itself ordered.
    Returns [{'left': members, 'right': members, 'distance': Fraction}] with members as sorted key tuples."""
    keys = sorted(keys)
    if len(set(keys)) != len(keys):
        raise GroupingInputError("duplicate canonical key")
    clusters = {i: (k,) for i, k in enumerate(keys)}
    S = {}
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a = agree(keys[i], keys[j])
            if a is None:
                raise GroupingInputError("agreement undefined between %s and %s" % (keys[i][1], keys[j][1]))
            S[(i, j)] = 1 - a
    merges, nxt = [], len(keys)
    while len(clusters) > 1:
        ids = sorted(clusters)
        cand = None
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                a, b = ids[x], ids[y]
                d = S[(a, b)] / (len(clusters[a]) * len(clusters[b]))
                pair = tuple(sorted((clusters[a][0], clusters[b][0])))
                if cand is None or (d, pair) < (cand[0], cand[1]):
                    cand = (d, pair, a, b)
        d, pair, a, b = cand
        left, right = (a, b) if clusters[a][0] == pair[0] else (b, a)
        merged = tuple(sorted(clusters[a] + clusters[b]))
        for c in ids:
            if c not in (a, b):
                S[(c, nxt)] = S[(min(a, c), max(a, c))] + S[(min(b, c), max(b, c))]
        merges.append({"left": clusters[left], "right": clusters[right], "distance": d})
        del clusters[a], clusters[b]
        clusters[nxt] = merged
        nxt += 1
    return merges


def cut(keys, merges, t):
    """Partition at threshold t: apply merges in sequence while distance <= 1 - t (stop at the first that is not)."""
    lim = 1 - Fraction(str(t))
    parent = {k: k for k in keys}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for m in merges:
        if m["distance"] > lim:
            break
        parent[find(m["left"][0])] = find(m["right"][0])
    out = collections.defaultdict(list)
    for k in keys:
        out[find(k)].append(k)
    return sorted(tuple(sorted(v)) for v in out.values())


def _ari(labels_a, labels_b):
    """Adjusted Rand index by pair counting; identical partitions give 1.0 (scikit-learn convention)."""
    n = len(labels_a)
    tp = fp = fn = tn = 0
    for i in range(n):
        for j in range(i + 1, n):
            sa, sb = labels_a[i] == labels_a[j], labels_b[i] == labels_b[j]
            tp += sa and sb
            fn += sa and not sb
            fp += sb and not sa
            tn += (not sa) and (not sb)
    if fn == 0 and fp == 0:
        return 1.0
    return 2.0 * (tp * tn - fn * fp) / ((tp + fn) * (fn + tn) + (tp + fp) * (fp + tn))


adjusted_rand_index = _ari


# ----------------------------------------------------------------------------------------------- core grouping
def _validate(structures):
    need = ("id", "engine", "execution", "sha256", "state", "designated")
    seen, seen_ex = set(), set()
    for s in structures:
        miss = [k for k in need if k not in s]
        if miss:
            raise GroupingInputError("structure %r lacks %s" % (s.get("id"), ", ".join(miss)))
        if not isinstance(s["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", s["sha256"]):
            raise GroupingInputError("structure %s: sha256 is not a 64-character hex digest" % s["id"])
        if s["id"] in seen:
            raise GroupingInputError("duplicate structure id %s" % s["id"])
        seen.add(s["id"])
        if (s["engine"], s["execution"]) in seen_ex:
            raise GroupingInputError("duplicate engine/execution %s|%s" % (s["engine"], s["execution"]))
        seen_ex.add((s["engine"], s["execution"]))
        if s["state"] == "ELIGIBLE":
            c = s.get("contacts")
            if c is None or not all(isinstance(x, (list, tuple)) and len(x) == 2 and all(
                    isinstance(v, int) and not isinstance(v, bool) and v >= 1 for v in x) for x in c):
                raise GroupingInputError("structure %s: contacts must be a list of [protein_pos, rna_pos] positive "
                                         "integers" % s["id"])


def _pose(s1, s2):
    """Report's rna_pose_difference in Report's (engine, execution) argument order. -> (value or None, capped, note)."""
    x, y = sorted((s1, s2), key=lambda s: (s["engine"], s["execution"]))
    if x.get("ca") is None or y.get("ca") is None:
        return None, None, "backbone coordinates unavailable"
    v, capped = geometry.rna_pose_difference(x, y)
    return v, bool(capped) if capped is not None else None, (None if v is not None else "not comparable")


def _median(vals):
    return float(np.median(sorted(vals))) if vals else None


def compute(structures, construct=None, pose=True, rel="groups/groups.json"):
    """Grouping of `structures` (list of dicts: id, engine, execution, sha256, state, designated, contacts for
    eligible ones, optional ca/c4 tracks for P, optional used_path). Pure function of the structure records:
    independent of their order. Returns (groups_doc, dendrogram_doc, pairwise_doc) without provenance."""
    _validate(structures)
    elig = sorted((s for s in structures if s["state"] == "ELIGIBLE"), key=canonical_key)
    inel = sorted((s for s in structures if s["state"] != "ELIGIBLE"), key=canonical_key)
    by = {canonical_key(s): s for s in elig}
    C = {k: frozenset(tuple(x) for x in s["contacts"]) for k, s in by.items()}
    Sf = {k: frozenset(p for p, _ in c) for k, c in C.items()}
    iface = [k for k in sorted(by) if C[k]]
    noint = [k for k in sorted(by) if not C[k]]
    D = {k for k in by if by[k]["designated"]}
    n_engine = collections.Counter(by[k]["engine"] for k in by)

    # pairwise agreement (exact and Report float) and P, over all eligible pairs, canonical order
    R, U, P, prow = {}, {}, {}, []
    keys = sorted(by)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            r_ex, r_rep = _agreement(C[a], C[b])
            u_ex, u_rep = _agreement(Sf[a], Sf[b])
            R[(a, b)] = R[(b, a)] = r_ex
            U[(a, b)] = U[(b, a)] = u_ex
            pv_, cap, note = _pose(by[a], by[b]) if pose else (None, None, "not computed")
            P[(a, b)] = P[(b, a)] = pv_
            prow.append({"a": a[1], "b": b[1], "register_agreement_R": r_rep, "R_exact": _frac(r_ex),
                         "surface_agreement_U": u_rep, "U_exact": _frac(u_ex), "rna_pose_difference_P_A": pv_,
                         "P_copy_permutation_capped": cap, "P_note": note,
                         "evidence_id": pv.evidence_id("groups/pairwise.json", "/pairs/%d" % len(prow))})

    def agree_u(a, b):
        return U[(a, b)]

    def agree_r(a, b):
        return R[(a, b)]

    l1_merges = upgma(iface, agree_u)
    l2_cache = {}

    def l2_merges(members):
        if members not in l2_cache:
            l2_cache[members] = upgma(members, agree_r)
        return l2_cache[members]

    def okey(members):
        return (0 if any(m in D for m in members) else 1, min(members))

    ids = lambda ms: [m[1] for m in ms]  # noqa: E731
    thresholds = {}
    dend_l2 = {}
    for t in THRESHOLDS:
        l1 = cut(iface, l1_merges, t)
        entries = [("surface", g) for g in l1] + ([("none", tuple(noint))] if noint else [])
        entries.sort(key=lambda e: okey(e[1]))
        groups, surfaces, dend_l2[t] = [], [], []
        for j, (kind, sg) in enumerate(entries, 1):
            if kind == "surface":
                m2 = l2_merges(sg)
                dend_l2[t].append({"surface_group": j, "members": ids(sg), "merges": _merges_out(m2)})
                subs = sorted(cut(list(sg), m2, t), key=okey)
            else:
                subs = [sg]
            first_k = len(groups) + 1
            for g in subs:
                groups.append(_group_record(len(groups) + 1, j, kind == "none", g, by, R, P, D, n_engine, t, rel,
                                            len(groups)))
            surfaces.append({"surface_group": j, "label": ("no interface" if kind == "none" else "surface group %d" % j),
                             "no_interface": kind == "none", "members": ids(sg),
                             "groups": list(range(first_k, len(groups) + 1)),
                             "evidence_id": pv.evidence_id(rel, "/thresholds/%s/surface_groups/%d" % (t, j - 1))})
        thresholds[t] = {"threshold": t, "n_groups": len(groups), "n_surface_groups": len(surfaces),
                         "n_interface_surface_groups": len(l1), "groups": groups, "surface_groups": surfaces,
                         "designated": _designated_rows(groups, D, by) + [
                             {"id": s["id"], "engine": s["engine"], "group": None,
                              "text": "engine-designated structure: ineligible (Report state %s), listed and never "
                                      "grouped" % s["state"]} for s in inel if s["designated"]]}
    sdoc = []
    for i, s in enumerate(sorted(structures, key=canonical_key)):
        sdoc.append({"id": s["id"], "engine": s["engine"], "execution": s["execution"], "sha256": s["sha256"],
                     "canonical_key": [s["sha256"], s["id"]], "designated": bool(s["designated"]), "state": s["state"],
                     "n_contacts": len(s["contacts"]) if s["state"] == "ELIGIBLE" else None,
                     "contacts": sorted([list(x) for x in s["contacts"]]) if s["state"] == "ELIGIBLE" else None,
                     "used_path": s.get("used_path"),
                     "evidence_id": pv.evidence_id(rel, "/structures/%d" % i)})
    doc = {"kind": "hypothesis_grouping", "status": "DESCRIPTIVE", "definition": DEFINITION,
           "thresholds_reported": list(THRESHOLDS), "primary_threshold": PRIMARY,
           "size_note": SIZE_NOTE, "display_order": NOT_RANKED, "placement_note": PLACEMENT_NOTE,
           "rna_conformation_difference": Q_STATEMENT, "limits": LIMITS, "construct": construct,
           "n_structures": len(structures), "n_eligible": len(elig), "n_interface": len(iface),
           "n_no_interface": len(noint), "eligible_per_engine": dict(sorted(n_engine.items())),
           "structures": sdoc,
           "ineligible": [{"id": s["id"], "engine": s["engine"], "execution": s["execution"], "state": s["state"],
                           "text": "listed, never grouped (Report state %s)" % s["state"],
                           "evidence_id": pv.evidence_id(rel, "/ineligible/%d" % i)} for i, s in enumerate(inel)],
           "thresholds": thresholds}
    dend = {"kind": "hypothesis_grouping_dendrogram",
            "level1": {"agreement": "surface agreement U", "members": ids(iface), "merges": _merges_out(l1_merges)},
            "level2": dend_l2,
            "note": "Full merge sequences; distance = 1 - mean agreement; a cut at t keeps the merges, in sequence, "
                    "while distance <= 1 - t."}
    pairs = {"kind": "hypothesis_grouping_pairwise", "pairs": prow,
             "definition": "R and U by rc3 Report's weighted_jaccard with unit weights (R_exact/U_exact are the "
                           "exact fractions used for clustering); P by Report's rna_pose_difference in Report's "
                           "(engine, execution) argument order, descriptive only."}
    return doc, dend, pairs


def _merges_out(merges):
    return [{"step": i + 1, "left": [m[1] for m in x["left"]], "right": [m[1] for m in x["right"]],
             "distance": _frac(x["distance"]), "distance_value": float(x["distance"]),
             "mean_agreement": _frac(1 - x["distance"])} for i, x in enumerate(merges)]


def _group_record(k, j, no_iface, members, by, R, P, D, n_engine, t, rel, idx):
    members = tuple(sorted(members))
    if no_iface:
        rep, rule, rep_mean = members[0], "no contacts, so no register medoid: member with the smallest canonical key", None
    elif len(members) == 1:
        rep, rule, rep_mean = members[0], "singleton: its own representative", None
    else:
        means = {m: sum((R[(m, o)] for o in members if o != m), Fraction(0)) / (len(members) - 1) for m in members}
        rep = sorted(members, key=lambda m: (-means[m], m))[0]
        rule, rep_mean = "register medoid (highest mean R to the other members; ties by canonical key)", means[rep]
    to_rep = [] if no_iface else [R[(m, rep)] for m in members if m != rep]
    pvals = [P[(a, b)] for i, a in enumerate(members) for b in members[i + 1:]]
    got = [v for v in pvals if v is not None]
    comp = collections.Counter(by[m]["engine"] for m in members)
    w = sum((Fraction(1, n_engine[by[m]["engine"]]) for m in members), Fraction(0))
    des = []
    for m in members:
        if m in D:
            des.append({"id": m[1], "text": ("engine-designated structure; representative of group %d" % k) if m == rep
                        else "engine-designated structure (member of group %d)" % k})
    return {"group": k, "label": "group %d" % k, "surface_group": j, "no_interface": no_iface,
            "members": [m[1] for m in members], "size": len(members), "size_note": SIZE_NOTE,
            "engine_composition": dict(sorted(comp.items())),
            "engine_weighted_size": {"fraction": _frac(w), "value": float(w),
                                     "definition": "each engine's eligible structures sum to one"},
            "representative": {"id": rep[1], "label": "representative of group %d" % k, "rule": rule,
                               "mean_R_to_other_members": None if rep_mean is None else float(rep_mean)},
            "designated_members": des,
            "mean_R_members_to_representative": float(sum(to_rep, Fraction(0)) / len(to_rep)) if to_rep else None,
            "R_members_to_representative": [float(x) for x in to_rep],
            "rna_pose_difference_spread_A": {"min": min(got) if got else None, "median": _median(got),
                                              "max": max(got) if got else None, "n_pairs": len(got),
                                              "n_pairs_unavailable": len(pvals) - len(got)},
            "contains_designated": any(m in D for m in members),
            "evidence_id": pv.evidence_id(rel, "/thresholds/%s/groups/%d" % (t, idx))}


def _designated_rows(groups, D, by):
    rows = []
    for g in groups:
        for d in g["designated_members"]:
            rows.append({"id": d["id"], "engine": by[[k for k in D if k[1] == d["id"]][0]]["engine"],
                         "group": g["group"], "text": d["text"]})
    return rows


# ----------------------------------------------------------------------------------------------- inputs
def _tracks(path):
    model = geometry.parse_model(path)
    prot, rna, _ = geometry.split_chains(model)
    return geometry.backbone_tracks(prot, rna)


def load_analysis(project, analysis):
    """Structures from Report's records in an analysis directory plus the project manifest. Reads only
    manifest.json, report/result.json, report/contacts_by_output.json and the structure files the manifest names."""
    mp = os.path.join(project, "manifest.json")
    rp = os.path.join(analysis, "report", "result.json")
    cp = os.path.join(analysis, "report", "contacts_by_output.json")
    for p in (mp, rp, cp):
        if not os.path.isfile(p):
            raise GroupingInputError("missing input %s" % p)
    try:
        man, rr, cbo = (json.load(open(p, encoding="utf-8")) for p in (mp, rp, cp))
    except ValueError as ex:
        raise GroupingInputError("unreadable JSON input: %s" % ex)
    from . import portability as PT                      # recorded structure files: resolved and hash-verified
    man = PT.check_manifest(project, man, "read", "group")[0]
    inc = {(s["engine"], s["execution"]): s for s in man.get("structures", []) if s.get("verdict") == "INCLUDED"}
    out, notes = [], []
    seen = set()
    for o in rr.get("per_output", []):
        key = (o["engine"], o["execution"])
        s = inc.get(key)
        if s is None:
            raise GroupingInputError("Report output %s|%s is not an included structure of the manifest" % key)
        if o.get("sha256") != s["used_sha256"]:
            raise GroupingInputError("Report output %s|%s has sha256 %s but the manifest used_sha256 is %s"
                                     % (key + (str(o.get("sha256"))[:12], s["used_sha256"][:12])))
        seen.add(key)
        rec = {"id": s["id"], "engine": s["engine"], "execution": s["execution"], "sha256": s["used_sha256"],
               "designated": bool(s.get("designated")), "state": o["state"], "used_path": s["used_path"]}
        ck = "%s|%s" % key
        if o["state"] == "ELIGIBLE":
            if ck not in cbo:
                raise GroupingInputError("eligible output %s has no contact list in contacts_by_output.json" % ck)
            rec["contacts"] = [tuple(x) for x in cbo[ck]]
            if len(rec["contacts"]) != o.get("n_contacts", len(rec["contacts"])):
                raise GroupingInputError("output %s: %d contacts listed, Report counted %s" % (ck, len(rec["contacts"]), o.get("n_contacts")))
            path = s["used_path"]
            if os.path.isfile(path) and pv.sha256_file(path) == s["used_sha256"]:
                rec["ca"], rec["c4"] = _tracks(path)
            else:
                notes.append("%s: structure file missing or changed since import; P unavailable for it" % s["id"])
        elif ck in cbo:
            raise GroupingInputError("output %s is %s in Report but has a contact list" % (ck, o["state"]))
        out.append(rec)
    extra = set(cbo) - {"%s|%s" % k for k in seen}
    if extra:
        raise GroupingInputError("contacts_by_output.json names outputs Report did not analyse: %s" % sorted(extra)[:3])
    not_imported = [{"id": s.get("id"), "engine": s.get("engine"), "execution": s.get("execution"),
                     "state": "NOT_IMPORTED (%s)" % s.get("verdict")}
                    for s in man.get("structures", []) if s.get("verdict") != "INCLUDED"]
    construct = {k: man["construct"].get(k) for k in ("protein_length", "rna_length", "protein_sequence", "rna_sequence")}
    inputs = [mp, rp, cp]
    return out, construct, inputs, notes, not_imported


def records_from_contract(validated_contract, ids=None, designated=None, extra=None):
    """Structures via rc3 Report's own per-output routine (eligibility, interface_contacts, backbone_tracks), for a
    raw pool without an analysis directory. ids/designated/extra: dicts keyed by (engine, execution)."""
    c = validated_contract
    lp, lr = c["construct"]["protein_length"], c["construct"]["rna_length"]
    out = []
    for o in c["outputs"]:
        r = report_agreement.analyse_output({"output": o, "protein_length": lp, "rna_length": lr})
        key = (o["engine"], o["execution"])
        rec = {"id": (ids or {}).get(key, o["execution"]), "engine": o["engine"], "execution": o["execution"],
               "sha256": o["sha256"], "designated": bool((designated or {}).get(key, False)), "state": r["state"],
               "used_path": o["structure_path"]}
        if r["state"] == "ELIGIBLE":
            rec.update(contacts=[tuple(x) for x in r["contacts"]], ca=r["ca"], c4=r["c4"])
        rec.update((extra or {}).get(key, {}))
        out.append(rec)
    return out


def load_project_raw(project):
    mp = os.path.join(project, "manifest.json")
    cp = os.path.join(project, "report_contract.json")
    for p in (mp, cp):
        if not os.path.isfile(p):
            raise GroupingInputError("missing input %s" % p)
    man = json.load(open(mp, encoding="utf-8"))
    from . import portability as PT                      # the contract's paths are read as recorded
    man = PT.check_manifest(project, man, "recorded", "group")[0]
    try:
        vc = report_contract.load(cp)
    except report_contract.ContractError as ex:
        raise GroupingInputError("Report contract refused: %s" % ex)
    inc = {(s["engine"], s["execution"]): s for s in man["structures"] if s.get("verdict") == "INCLUDED"}
    if set(inc) != {(o["engine"], o["execution"]) for o in vc["outputs"]}:
        raise GroupingInputError("report_contract.json and the manifest list different included structures")
    recs = records_from_contract(vc, ids={k: v["id"] for k, v in inc.items()},
                                 designated={k: bool(v.get("designated")) for k, v in inc.items()})
    not_imported = [{"id": s.get("id"), "engine": s.get("engine"), "execution": s.get("execution"),
                     "state": "NOT_IMPORTED (%s)" % s.get("verdict")}
                    for s in man["structures"] if s.get("verdict") != "INCLUDED"]
    construct = {k: man["construct"].get(k) for k in ("protein_length", "rna_length", "protein_sequence", "rna_sequence")}
    return recs, construct, [mp, cp], [], not_imported


# ----------------------------------------------------------------------------------------------- wording
def forbidden_hits(text):
    return ["%r" % m.group(0) for pat in FORBIDDEN for m in re.finditer(pat, text, flags=re.I)]


def audit(text, user_strings=()):
    """Wording audit (rnplens.trace) plus the Spec B forbidden-phrase check. Input-derived strings (paths, ids,
    digests) are masked first: they are the user's content, not RNPLens wording."""
    for u in sorted({x for x in user_strings if x}, key=len, reverse=True):
        text = text.replace(u, " ")
    return trace.wording_audit(text) + forbidden_hits(re.sub(r"<div class='lim'>.*?</div>", " ", text, flags=re.S)) \
        + [h + " (limits block)" for h in forbidden_hits(" ".join(re.findall(r"<div class='lim'>(.*?)</div>", text, flags=re.S)))]


def _user_strings(structures):
    out = []
    for s in structures:
        for k in ("id", "execution", "used_path", "engine", "sha256"):
            if s.get(k):
                out.append(str(s[k]))
    return out


# ----------------------------------------------------------------------------------------------- rendering
def _e(x):
    return html.escape(str(x))


def _fmt(v, nd=3):
    return "n/a" if v is None else ("%.*f" % (nd, v))


def groups_tsv(doc):
    cols = ["threshold", "group", "surface_group", "no_interface", "size", "engine_weighted_size", "engine_composition",
            "representative", "designated_members", "members", "mean_R_members_to_representative", "P_min_A",
            "P_median_A", "P_max_A", "P_pairs", "size_note", "evidence_id"]
    lines = ["\t".join(cols)]
    for t in (PRIMARY,) + tuple(x for x in THRESHOLDS if x != PRIMARY):
        for g in doc["thresholds"][t]["groups"]:
            sp = g["rna_pose_difference_spread_A"]
            lines.append("\t".join(str(x) for x in [
                t, g["group"], g["surface_group"], g["no_interface"], g["size"], g["engine_weighted_size"]["fraction"],
                ";".join("%s:%d" % kv for kv in g["engine_composition"].items()), g["representative"]["id"],
                ";".join(d["id"] for d in g["designated_members"]) or "-", ";".join(g["members"]),
                _fmt(g["mean_R_members_to_representative"], 6), _fmt(sp["min"], 6), _fmt(sp["median"], 6),
                _fmt(sp["max"], 6), sp["n_pairs"], SIZE_NOTE, g["evidence_id"]]))
    return "\n".join(lines) + "\n"


CSS = ("body{font-family:sans-serif;max-width:1100px;margin:2em auto;color:#222}table{border-collapse:collapse;"
       "margin:.5em 0 1.5em}td,th{border:1px solid #ccc;padding:3px 6px;font-size:13px;vertical-align:top}"
       "th{background:#f3f3f3}.note{background:#fff8e0;padding:6px 10px;border-left:4px solid #e0b000}"
       ".lim{background:#f4f4f4;padding:6px 10px;border-left:4px solid #888;font-size:13px}.des{font-weight:bold}")


def groups_html(doc, notes=()):
    h = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>RNPLens binding-proposal groups</title>"
         "<style>%s</style></head><body>" % CSS,
         "<h1>Binding-proposal groups (descriptive)</h1>",
         "<p>%d structures; %d eligible (%d with an interface, %d with no interface); %d ineligible, listed and never "
         "grouped.</p>" % (doc["n_structures"], doc["n_eligible"], doc["n_interface"], doc["n_no_interface"],
                           len(doc["ineligible"])),
         "<p class='note'>%s</p>" % _e(SIZE_NOTE), "<p>%s</p>" % _e(NOT_RANKED), "<p>%s</p>" % _e(PLACEMENT_NOTE),
         "<p><b>%s</b></p>" % _e(Q_STATEMENT), "<p>Report order: protein surface, then contact register, then the "
         "descriptive RNA pose spread. Primary cut t = 0.5; t = 0.3 and t = 0.7 are always shown alongside.</p>"]
    for n in notes:
        h.append("<p class='note'>%s</p>" % _e(n))
    for t in (PRIMARY,) + tuple(x for x in THRESHOLDS if x != PRIMARY):
        T = doc["thresholds"][t]
        h.append("<h2>Cut t = %s%s: %d group(s) in %d surface group(s)</h2>" % (
            t, " (primary)" if t == PRIMARY else "", T["n_groups"], T["n_surface_groups"]))
        for d in T["designated"]:
            h.append("<p class='des'>%s: %s</p>" % (_e(d["id"]), _e(d["text"])))
        h.append("<table><tr><th>group</th><th>surface group</th><th>size</th><th>engine-weighted size</th>"
                 "<th>engines</th><th>representative</th><th>engine-designated</th><th>mean R of members to the "
                 "representative</th><th>P spread, A (min / median / max; pairs)</th><th>members</th></tr>")
        for g in T["groups"]:
            sp = g["rna_pose_difference_spread_A"]
            sgl = "no interface" if g["no_interface"] else "surface group %d" % g["surface_group"]
            h.append("<tr><td>%s</td><td>%s</td><td>%d</td><td>%s</td><td>%s</td><td>%s<br><small>%s</small></td>"
                     "<td>%s</td><td>%s</td><td>%s / %s / %s; %d</td><td>%s</td></tr>" % (
                         _e(g["label"]), _e(sgl), g["size"], _e(g["engine_weighted_size"]["fraction"]),
                         _e(", ".join("%s %d" % kv for kv in g["engine_composition"].items())),
                         _e(g["representative"]["label"] + ": " + g["representative"]["id"]),
                         _e(g["representative"]["rule"]),
                         _e("; ".join(d["id"] + " - " + d["text"] for d in g["designated_members"]) or "-"),
                         _fmt(g["mean_R_members_to_representative"]), _fmt(sp["min"], 2), _fmt(sp["median"], 2),
                         _fmt(sp["max"], 2), sp["n_pairs"], _e(", ".join(g["members"]))))
        h.append("</table><p class='note'>%s</p>" % _e(SIZE_NOTE))
    if doc["ineligible"] or doc.get("not_imported"):
        h.append("<h2>Not grouped</h2><table><tr><th>structure</th><th>engine</th><th>execution</th><th>state</th></tr>")
        for r in doc["ineligible"] + doc.get("not_imported", []):
            h.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % tuple(
                _e(r.get(k)) for k in ("id", "engine", "execution", "state")))
        h.append("</table>")
    h.append("<p>Files: groups.json, groups.tsv, dendrogram.json (full merge sequences), pairwise.json (R, U, P). "
             "Difference between two groups: <code>rnplens group-diff ANALYSIS G H</code>.</p>")
    h.append("<div class='lim'><b>Interpretation limits.</b><ul>%s</ul></div>" % "".join("<li>%s</li>" % _e(x) for x in LIMITS))
    h.append("</body></html>\n")
    return "\n".join(h)


# ----------------------------------------------------------------------------------------------- run / write
def run(project, analysis=None, out=None, quiet=False):
    """Group the structures of `project`. With `analysis`, contacts come from its Report records and outputs go to
    analysis/groups/; without, contacts come from Report's per-output routine and outputs go to out/groups/."""
    if analysis:
        structures, construct, inputs, notes, not_imp = load_analysis(project, analysis)
        root = analysis
    else:
        if not out:
            raise GroupingInputError("without --analysis, --out is required")
        structures, construct, inputs, notes, not_imp = load_project_raw(project)
        root = out
    doc, dend, pairs = compute(structures, construct)
    doc["not_imported"] = [dict(r, evidence_id=pv.evidence_id("groups/groups.json", "/not_imported/%d" % i))
                           for i, r in enumerate(not_imp)]
    doc["notes"] = list(notes)
    doc["source"] = ("Report records of analysis directory" if analysis else
                     "Report's per-output routine agreement.analyse_output on the project contract (no analysis directory)")
    files = inputs + sorted({s["used_path"] for s in structures if s.get("used_path") and os.path.isfile(s["used_path"])})
    ins = [{"path": os.path.abspath(p), "sha256": pv.sha256_file(p)} for p in files]
    cfg = {"thresholds": list(THRESHOLDS), "primary": PRIMARY, "linkage": "average (UPGMA), exact rational",
           "levels": ["surface U", "register R"], "tie_break": "canonical key (sha256 of file used, structure id)",
           "representative": "register medoid", "spec": "SPEC_B_v2 + Amendments 1-2"}
    for d, kind in ((doc, "hypothesis_grouping"), (dend, "hypothesis_grouping_dendrogram"),
                    (pairs, "hypothesis_grouping_pairwise")):
        d["provenance"] = pv.block(kind, ins, DEFINITION, cfg)
    page, tsv = groups_html(doc, notes), groups_tsv(doc)
    us = _user_strings(structures) + [os.path.abspath(p) for p in files] + [project, root]
    bad = []
    for name, text in (("groups.html", page), ("groups.tsv", tsv), ("groups.json", json.dumps(doc)),
                       ("dendrogram.json", json.dumps(dend)), ("pairwise.json", json.dumps(pairs))):
        bad += ["%s: %s" % (name, x) for x in audit(text, us)]
    if bad:
        raise RuntimeError("wording audit refused the grouping output: %s" % bad[:5])
    g = os.path.join(root, "groups")
    pv.atomic_write_json(os.path.join(g, "groups.json"), doc)
    pv.atomic_write_json(os.path.join(g, "dendrogram.json"), dend)
    pv.atomic_write_json(os.path.join(g, "pairwise.json"), pairs)
    pv.atomic_write_text(os.path.join(g, "groups.tsv"), tsv)
    pv.atomic_write_text(os.path.join(g, "groups.html"), page)
    outs = [os.path.join(g, f) for f in ("groups.json", "groups.html", "groups.tsv", "dendrogram.json", "pairwise.json")]
    if not quiet:
        T = doc["thresholds"][PRIMARY]
        print("rnplens group: %d eligible structure(s); t=0.5: %d group(s) in %d surface group(s); t=0.3: %d; t=0.7: %d"
              % (doc["n_eligible"], T["n_groups"], T["n_surface_groups"], doc["thresholds"]["0.3"]["n_groups"],
                 doc["thresholds"]["0.7"]["n_groups"]))
        for d in T["designated"]:
            print("  %s: %s" % (d["id"], d["text"]))
        print("  " + SIZE_NOTE)
        print("  " + Q_STATEMENT)
        print("  written: %s" % os.path.join(g, "groups.html"))
    return {"outputs": outs, "groups_json": outs[0], "doc": doc}


def run_capability(project, analysis=None, out=None, **_):
    r = run(project, analysis=analysis, out=out, quiet=True)
    return {"outputs": r["outputs"], "status": "DESCRIPTIVE", "limits": CAPABILITIES[0]["limits"]}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rnplens group", description="Group predicted structures into binding "
                                 "proposals (protein surface, then contact register). Groups are not ranked.")
    ap.add_argument("project", help="project directory written by 'rnplens import'")
    ap.add_argument("--analysis", help="analysis directory written by 'rnplens analyse' (outputs go to ANALYSIS/groups/)")
    ap.add_argument("--out", help="without --analysis: output root (contacts are computed with Report's own routine)")
    a = ap.parse_args(argv)
    try:
        run(a.project, analysis=a.analysis, out=a.out)
    except GroupingInputError as ex:
        print("rnplens group: refused: %s. Nothing was written." % ex, file=sys.stderr)
        return 2
    return 0


# ----------------------------------------------------------------------------------------------- difference map
def _resolved(path):
    """Construct positions with >= 1 non-hydrogen atom in >= 1 copy of each polymer (Report's chain split)."""
    model = geometry.parse_model(path)
    prot, rna, _ = geometry.split_chains(model)

    def pos(chains):
        return {j + 1 for _, res in chains for j, x in enumerate(res) if any(a.element != "H" for a in x)}
    return pos(prot), pos(rna)


def difference(doc, g, h, threshold=PRIMARY, resolved=None, rel=None):
    """Difference map between groups g and h at `threshold` from a groups.json document.
    resolved: {structure id: (protein positions, rna positions)} or None to read the structure files (sha256 checked)."""
    t = str(threshold)
    if t not in THRESHOLDS:
        raise GroupingInputError("threshold must be one of %s" % ", ".join(THRESHOLDS))
    T = doc["thresholds"][t]
    gs = {x["group"]: x for x in T["groups"]}
    for k in (g, h):
        if k not in gs:
            raise GroupingInputError("group %s does not exist at t = %s (groups 1..%d)" % (k, t, len(gs)))
    if g == h:
        raise GroupingInputError("the two groups must differ")
    rel = rel or "groups/%s/diff.json" % diff_dirname(g, h, t)
    st = {s["id"]: s for s in doc["structures"]}
    notes = []
    if resolved is None:
        resolved = {}
        for sid in gs[g]["members"] + gs[h]["members"]:
            s = st[sid]
            p = s.get("used_path")
            if p and os.path.isfile(p) and pv.sha256_file(p) == s["sha256"]:
                resolved[sid] = _resolved(p)
            else:
                resolved[sid] = (set(), set())
                notes.append("%s: structure file missing or changed; all its positions are counted as not observed" % sid)
    pseq = (doc.get("construct") or {}).get("protein_sequence") or ""
    rseq = (doc.get("construct") or {}).get("rna_sequence") or ""
    cs = {sid: {tuple(c) for c in (st[sid]["contacts"] or [])} for sid in st if st[sid]["state"] == "ELIGIBLE"}
    union = sorted(set().union(*(cs[m] for m in gs[g]["members"] + gs[h]["members"])))
    rows, n_neither = [], 0
    for (p, r) in union:
        side = {}
        for lab, k in (("A", g), ("B", h)):
            per, num, den = [], 0, 0
            for m in gs[k]["members"]:
                rp, rr = resolved[m]
                ok = p in rp and r in rr
                has = (p, r) in cs[m]
                per.append({"id": m, "both_positions_resolved": ok, "contact": has if ok else None})
                if ok:
                    den += 1
                    num += has
            fr = Fraction(num, den) if den else None
            side[lab] = {"group": k, "members_containing": num, "denominator_resolved_members": den,
                         "fraction": ("%d/%d" % (num, den)) if den else None,   # unreduced: counts stay visible
                         "fraction_value": None if fr is None else float(fr),
                         "frequent": fr is not None and fr >= FREQUENT_CUT,
                         "not_observed": [x["id"] for x in per if not x["both_positions_resolved"]], "per_member": per}
        fa, fb = side["A"]["frequent"], side["B"]["frequent"]
        if not (fa or fb):
            n_neither += 1
            continue
        cat = "frequent in both" if fa and fb else ("frequent in group %d only" % g if fa else "frequent in group %d only" % h)
        rows.append({"category": cat, "protein_position": p,
                     "protein_residue": pseq[p - 1] if 0 < p <= len(pseq) else "?",
                     "rna_position": r, "rna_nucleotide": rseq[r - 1] if 0 < r <= len(rseq) else "?",
                     "A": side["A"], "B": side["B"], "caveat": DIFF_CAVEAT,
                     "evidence_id": pv.evidence_id(rel, "/rows/%d" % len(rows))})
    order = {"frequent in both": 0, "frequent in group %d only" % g: 1, "frequent in group %d only" % h: 2}
    rows.sort(key=lambda x: (order[x["category"]], x["protein_position"], x["rna_position"]))
    for i, x in enumerate(rows):
        x["evidence_id"] = pv.evidence_id(rel, "/rows/%d" % i)
    return {"kind": "group_difference_map", "status": "DESCRIPTIVE", "threshold": t, "group_A": g, "group_B": h,
            "members_A": gs[g]["members"], "members_B": gs[h]["members"],
            "frequent_cut_point": "1/2", "frequent_definition": FREQUENT_TEXT, "caveat": DIFF_CAVEAT,
            "rna_conformation_difference": Q_STATEMENT,
            "counts": {"frequent in both": sum(x["category"] == "frequent in both" for x in rows),
                       "frequent in group %d only" % g: sum(x["category"].endswith("%d only" % g) for x in rows),
                       "frequent in group %d only" % h: sum(x["category"].endswith("%d only" % h) for x in rows),
                       "contacts frequent in neither group (not listed)": n_neither},
            "rows": rows, "notes": notes}


def diff_dirname(g, h, t=PRIMARY):
    return "diff_%d_%d" % (g, h) + ("" if str(t) == PRIMARY else "_t%s" % t)


def diff_tsv(d):
    cols = ["category", "protein_position", "protein_residue", "rna_position", "rna_nucleotide",
            "fraction_group_%d" % d["group_A"], "containing_group_%d" % d["group_A"], "denominator_group_%d" % d["group_A"],
            "not_observed_group_%d" % d["group_A"], "fraction_group_%d" % d["group_B"], "containing_group_%d" % d["group_B"],
            "denominator_group_%d" % d["group_B"], "not_observed_group_%d" % d["group_B"], "caveat", "evidence_id"]
    L = ["\t".join(cols)]
    for x in d["rows"]:
        L.append("\t".join(str(v) for v in [
            x["category"], x["protein_position"], x["protein_residue"], x["rna_position"], x["rna_nucleotide"],
            x["A"]["fraction"] or "not observed", x["A"]["members_containing"], x["A"]["denominator_resolved_members"],
            ";".join(x["A"]["not_observed"]) or "-",
            x["B"]["fraction"] or "not observed", x["B"]["members_containing"], x["B"]["denominator_resolved_members"],
            ";".join(x["B"]["not_observed"]) or "-", x["caveat"], x["evidence_id"]]))
    return "\n".join(L) + "\n"


def diff_svg(d):
    """Contact-map overlay: protein positions down, RNA positions across; colour by category."""
    rows = d["rows"]
    ps = sorted({x["protein_position"] for x in rows})
    rs = sorted({x["rna_position"] for x in rows})
    cell, ox, oy = 12, 60, 40
    col = {"frequent in both": "#7b3294", "A": "#2c7bb6", "B": "#e66101"}
    W, H = max(ox + cell * max(1, len(rs)) + 10, ox + 3 * 170 + 10), oy + cell * max(1, len(ps)) + 60   # legend fits
    s = ["<svg xmlns='http://www.w3.org/2000/svg' width='%d' height='%d' font-family='sans-serif' font-size='9'>" % (W, H)]
    for j, r in enumerate(rs):
        s.append("<text x='%d' y='%d' transform='rotate(-90 %d %d)'>%d</text>" % (ox + j * cell + 9, oy - 4, ox + j * cell + 9, oy - 4, r))
    for i, p in enumerate(ps):
        s.append("<text x='4' y='%d'>%s%d</text>" % (oy + i * cell + 9, html.escape(next(
            (x["protein_residue"] for x in rows if x["protein_position"] == p), "?")), p))
    for x in rows:
        c = col["frequent in both"] if x["category"] == "frequent in both" else (
            col["A"] if x["category"].endswith("%d only" % d["group_A"]) else col["B"])
        s.append("<rect x='%d' y='%d' width='%d' height='%d' fill='%s'><title>%s</title></rect>" % (
            ox + rs.index(x["rna_position"]) * cell, oy + ps.index(x["protein_position"]) * cell, cell - 1, cell - 1, c,
            html.escape("%s%d-%s%d: %s" % (x["protein_residue"], x["protein_position"], x["rna_nucleotide"],
                                           x["rna_position"], x["category"]))))
    y = oy + cell * max(1, len(ps)) + 18
    for i, (lab, c) in enumerate((("frequent in both", col["frequent in both"]),
                                  ("frequent in group %d only" % d["group_A"], col["A"]),
                                  ("frequent in group %d only" % d["group_B"], col["B"]))):
        s.append("<rect x='%d' y='%d' width='10' height='10' fill='%s'/><text x='%d' y='%d'>%s</text>" % (
            ox + i * 170, y, c, ox + i * 170 + 14, y + 9, html.escape(lab)))
    s.append("</svg>")
    return "\n".join(s)


def diff_html(d, viewer_href=None):
    h = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>RNPLens group difference map</title>"
         "<style>%s</style></head><body>" % CSS,
         "<h1>Difference map: group %d and group %d (t = %s)</h1>" % (d["group_A"], d["group_B"], d["threshold"]),
         "<p class='note'>%s</p>" % _e(DIFF_CAVEAT), "<p>%s</p>" % _e(FREQUENT_TEXT), "<p><b>%s</b></p>" % _e(Q_STATEMENT),
         "<p>group %d members: %s<br>group %d members: %s</p>" % (d["group_A"], _e(", ".join(d["members_A"])),
                                                                   d["group_B"], _e(", ".join(d["members_B"]))),
         "<p>%s</p>" % _e("; ".join("%s: %d" % kv for kv in d["counts"].items()))]
    h.append("<p>3D view: %s</p>" % ("<a href='%s'>open the local Mol* view</a>" % _e(viewer_href) if viewer_href else
                                     "the local Mol* view is not present in this analysis directory; the structure "
                                     "files are listed in groups.json"))
    for n in d["notes"]:
        h.append("<p class='note'>%s</p>" % _e(n))
    h.append(diff_svg(d))
    h.append("<table><tr><th>category</th><th>protein</th><th>RNA</th><th>group %d: fraction (containing / resolved "
             "members)</th><th>group %d: fraction (containing / resolved members)</th><th>not observed (position not "
             "resolved)</th><th>caveat</th></tr>" % (d["group_A"], d["group_B"]))
    for x in d["rows"]:
        h.append("<tr><td>%s</td><td>%s%d</td><td>%s%d</td><td>%s (%d / %d)</td><td>%s (%d / %d)</td><td>%s</td>"
                 "<td><small>%s</small></td></tr>" % (
                     _e(x["category"]), _e(x["protein_residue"]), x["protein_position"], _e(x["rna_nucleotide"]),
                     x["rna_position"], _e(x["A"]["fraction"] or "not observed"), x["A"]["members_containing"],
                     x["A"]["denominator_resolved_members"], _e(x["B"]["fraction"] or "not observed"),
                     x["B"]["members_containing"], x["B"]["denominator_resolved_members"],
                     _e(", ".join(x["A"]["not_observed"] + x["B"]["not_observed"]) or "-"), _e(x["caveat"])))
    h.append("</table><div class='lim'><b>Interpretation limits.</b> %s</div></body></html>\n" % _e(DIFF_CAVEAT))
    return "\n".join(h)


def run_diff(analysis, g, h, threshold=PRIMARY, quiet=False):
    gp = os.path.join(analysis, "groups", "groups.json")
    if not os.path.isfile(gp):
        raise GroupingInputError("no groups/groups.json in %s; run 'rnplens group' first" % analysis)
    doc = json.load(open(gp, encoding="utf-8"))
    t = str(threshold)
    sub = diff_dirname(g, h, t)
    rel = "groups/%s/diff.json" % sub
    d = difference(doc, g, h, t, rel=rel)
    outdir = os.path.join(analysis, "groups", sub)
    viewer = os.path.join(analysis, "viewer", "viewer.html")     # written by `rnplens view`
    href = os.path.relpath(viewer, outdir) if os.path.isfile(viewer) else None
    ins = [gp] + sorted({s["used_path"] for s in doc["structures"] if s["id"] in set(d["members_A"] + d["members_B"])
                         and s.get("used_path") and os.path.isfile(s["used_path"])})
    d["provenance"] = pv.block("group_difference_map", ins, "Contacts present in >= 1/2 of a group's members in which "
                               "both positions are resolved; fractions over resolved members only.",
                               {"threshold": t, "groups": [g, h], "frequent_cut": "1/2"})
    page, tsv, svg = diff_html(d, href), diff_tsv(d), diff_svg(d)
    us = _user_strings(doc["structures"]) + [os.path.abspath(p) for p in ins] + [analysis]
    bad = []
    for name, text in (("diff.html", page), ("diff.tsv", tsv), ("diff.json", json.dumps(d)), ("overlay.svg", svg)):
        bad += ["%s: %s" % (name, x) for x in audit(text, us)]
    if bad:
        raise RuntimeError("wording audit refused the difference map: %s" % bad[:5])
    pv.atomic_write_json(os.path.join(outdir, "diff.json"), d)
    pv.atomic_write_text(os.path.join(outdir, "diff.tsv"), tsv)
    pv.atomic_write_text(os.path.join(outdir, "diff.html"), page)
    pv.atomic_write_text(os.path.join(outdir, "overlay.svg"), svg)
    outs = [os.path.join(outdir, f) for f in ("diff.json", "diff.tsv", "diff.html", "overlay.svg")]
    if not quiet:
        print("rnplens group-diff: group %d vs group %d at t=%s: %s" % (g, h, t, "; ".join("%s %d" % kv for kv in d["counts"].items())))
        print("  " + DIFF_CAVEAT)
        print("  written: %s" % outs[2])
    return {"outputs": outs, "doc": d}


def diff_capability(analysis, g, h, threshold=PRIMARY, **_):
    r = run_diff(analysis, int(g), int(h), threshold, quiet=True)
    return {"outputs": r["outputs"], "status": "DESCRIPTIVE", "limits": DIFF_CAVEAT}


def main_diff(argv=None):
    ap = argparse.ArgumentParser(prog="rnplens group-diff", description="Shared and group-specific contacts between "
                                 "two binding-proposal groups (from ANALYSIS/groups/groups.json).")
    ap.add_argument("analysis", help="directory holding groups/groups.json (the analysis or --out root)")
    ap.add_argument("g", type=int)
    ap.add_argument("h", type=int)
    ap.add_argument("--threshold", default=PRIMARY, choices=THRESHOLDS)
    a = ap.parse_args(argv)
    try:
        run_diff(a.analysis, a.g, a.h, a.threshold)
    except GroupingInputError as ex:
        print("rnplens group-diff: refused: %s. Nothing was written." % ex, file=sys.stderr)
        return 2
    return 0
