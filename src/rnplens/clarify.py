"""``rnplens clarify``: typed clarification requests for a managed project, recorded answers, and resume.

A clarification request is raised whenever the inputs leave a decision open that RNPLens must not make itself:

  construct_mismatch   a run's chains differ from the declared construct (another construct, or the wrong folder)
  chain_mapping        a structure holds more than one chain that matches the construct (competing mappings)
  engine_designation   which structure the engine designated is ambiguous (several confidence files, a tied score)
  importer_question    the questions ``rnplens import`` already asks (engine label, uncertain chain type, derived
                       copy, top-level copy), reused from its QUESTIONS.json unchanged

Every request lists explicit options; none is ever chosen automatically. An answer is recorded with provenance (time,
the user's own text, the chosen option, and the SHA-256 of every input it depends on) in a new state version
(``state.Project.record_decision``); the pipeline then resumes from the import, reuses cached work whose key is
unchanged, and recomputes only what the answer affects. A recorded answer is applied again, without asking, for as
long as the hashes it depends on are unchanged; when one changes the answer is marked INVALIDATED (kept in the
history) and the question is asked again. An answer that contradicts a recorded one is refused with a message.
"""
import itertools
import json
import os
import re
import sys

from . import provenance as pv
from . import state as S

EXIT_OK, EXIT_FAILED, EXIT_REFUSED, EXIT_NEEDS_ANSWER = 0, 1, 2, 3

CAPABILITIES = [
    {"id": "clarify_and_resume", "menu": None, "label": "Answer a pending clarification for a project and resume",
     "status": "DESCRIPTIVE", "needs": ["project_state"], "call": "rnplens.clarify:capability_answer",
     "limits": "An answer records a researcher's decision about construct identity, chain correspondence or engine "
               "designation; RNPLens does not judge whether that decision is biologically right."},
]

TYPES = {
    "construct_mismatch": "chains of a run differ from the declared construct",
    "chain_mapping": "more than one chain matches the construct: competing chain mappings",
    "engine_designation": "the engine-designated structure of a run is ambiguous",
    "importer_question": "a question asked by rnplens import",
}


# ---------------------------------------------------------------- hashes the answers depend on
def seq_sha(s):
    return pv.sha256_json(s)


def construct_sha(ps, rs):
    return pv.sha256_json({"protein": seq_sha(ps), "rna": seq_sha(rs)})


def _under(p, root):
    return p == root or p.startswith(root.rstrip(os.sep) + os.sep)


def _run_files(root, files):
    """{path relative to the run folder: sha256} of the declared files under root (location independent)."""
    return {os.path.relpath(p, root).replace(os.sep, "/"): s for p, s in sorted(files.items()) if _under(p, root)}


def run_hash(root, files):
    """Hash of one run folder: its files' SHA-256 keyed by their path relative to the run folder, so the same bytes
    in the same layout give the same hash wherever the run lives (DETERMINISM_CONTRACT_v1, rule 4c)."""
    return pv.sha256_json(_run_files(root, files))


def legacy_run_hash(root, files):
    """The run hash of projects written before the canonical records (keyed by absolute paths)."""
    h = {p: s for p, s in files.items() if _under(p, root)}
    return pv.sha256_json(dict(sorted(h.items()))) if h else None


def current_hash(key, ctx):
    """Current value of one dependency key. ctx: {"files": {path: sha}, "constructs": {name: sha}}."""
    kind, _, rest = key.partition(":")
    if kind == "file":
        return ctx["files"].get(rest)
    if kind == "run":
        h = _run_files(rest, ctx["files"])
        return pv.sha256_json(h) if h else None
    if kind == "construct":
        return ctx["constructs"].get(rest)
    return None


def _unchanged(key, recorded, ctx):
    if current_hash(key, ctx) == recorded:
        return True
    kind, _, rest = key.partition(":")       # an answer recorded before the canonical run hash (backward compatible)
    return kind == "run" and recorded is not None and legacy_run_hash(rest, ctx["files"]) == recorded


def changed_dependencies(rec, ctx):
    """-> [(key, recorded, current)] for every dependency of a recorded answer whose hash differs now."""
    return [(k, v, current_hash(k, ctx)) for k, v in sorted(rec["depends_on"].items()) if not _unchanged(k, v, ctx)]


# ---------------------------------------------------------------- request builders
def _req(rid, typ, question, options, depends_on, group, source, detail=None):
    return {"id": rid, "type": typ, "type_meaning": TYPES[typ], "question": question, "options": options,
            "depends_on": dict(sorted(depends_on.items())), "group": group, "source": source,
            "detail": detail or {}, "chosen_automatically": False}


def from_importer(questions, group, ctx):
    """The importer's own question dicts (QUESTIONS.json) as typed requests; options are the importer's."""
    out = []
    for q in questions:
        qid, opts = q["id"], list(q.get("options") or [])
        kind, _, subj = qid.partition(":")
        dep = {("run:" if kind == "engine" else "file:") + subj: current_hash(("run:" if kind == "engine" else "file:") + subj, ctx)}
        if kind == "top":
            root = os.path.dirname(subj)
            dep["run:" + root] = current_hash("run:" + root, ctx)
        options = []
        if kind == "derived":
            options = [{"id": "accept", "label": "accept the derived copy for this file (the importer's "
                        "--accept-derived, for this file only; the original is kept unchanged)",
                        "effects": {"file_in_analysis:" + subj: True}, "apply": {"importer_answers": {qid: "accept"}}},
                       {"id": "exclude_file", "label": "exclude this file", "effects": {"file_in_analysis:" + subj: False},
                        "apply": {"importer_answers": {qid: "exclude_file"}}}]
        else:
            for o in opts:
                eff = {}
                if kind == "engine":
                    eff = {"engine_of:" + subj: o}
                elif kind == "chains" and o == "exclude_file":
                    eff = {"file_in_analysis:" + subj: False}
                options.append({"id": o, "label": o, "effects": eff, "apply": {"importer_answers": {qid: o}}})
        out.append(_req(qid, "importer_question", q["question"], options, dep, group, "rnplens import QUESTIONS.json",
                        {"importer_question": q}))
    return out


def observed_sequences(path):
    """Polymer chain sequences of one structure, read with Report's chain typing: {"protein": [...], "rna": [...]}."""
    from rnpbench_report import geometry
    from . import importer
    prot, rna, _ = geometry.split_chains(geometry.parse_model(path))
    out = {"protein": [], "rna": []}
    for kind, group in (("protein", prot), ("rna", rna)):
        for cid, res in group:
            names = [x.get_resname().strip() for x in res]
            poly = [n for n in names if importer._polymer_class(n) == "polymer"]
            if poly:
                out[kind].append("".join(importer._one_letter(n, kind)[0] for n in poly))
    return out


def _label(root, labels):
    return labels.get(root) or os.path.basename(root)


def construct_requests(structures, group, gname_construct, ctx, run_of, labels, offer_reference_set):
    """Runs (in this group) holding structures whose chains differ from the group's construct."""
    by_run = {}
    for s in structures:
        root = run_of.get(s["path"])
        if root is None:
            continue
        differ = s["verdict"] == "INCOMPATIBLE" and any(c.get("status") == "SEQUENCE_DIFFERS" for c in s.get("chains") or [])
        by_run.setdefault(root, {"differ": [], "match": []})["differ" if differ else "match"].append(s)
    out = []
    for root, d in sorted(by_run.items()):
        if not d["differ"]:
            continue
        lab = _label(root, labels)
        dep = {"run:" + root: current_hash("run:" + root, ctx),
               "construct:" + gname_construct: ctx["constructs"].get(gname_construct)}
        obs = {}
        for s in d["differ"]:
            try:
                o = observed_sequences(s["path"])
                obs[s["path"]] = (tuple(o["protein"]), tuple(o["rna"]))
            except Exception:
                obs[s["path"]] = None
        uniq = set(obs.values())
        single = None
        if len(uniq) == 1 and None not in uniq:
            pp, rr = next(iter(uniq))
            if len(pp) == 1 and len(rr) == 1 and pp[0] and rr[0] and not (set(rr[0]) - set("ACGUN")):
                single = {"protein_sequence": pp[0], "rna_sequence": rr[0]}
        detail = {"run": lab, "run_root": root, "n_differing": len(d["differ"]), "n_matching": len(d["match"]),
                  "differing_files": sorted(s["path"] for s in d["differ"]),
                  "alignments": {s["path"]: [{"chain": c["chain"], "type": c["type_by_report"], **(c.get("alignment") or {})}
                                             for c in s["chains"] if c.get("status") == "SEQUENCE_DIFFERS"] for s in d["differ"]}}
        opts = [{"id": "exclude_run", "label": "wrong folder: exclude run %s from this project's analysis" % lab,
                 "effects": {"run_in_analysis:" + root: False}, "apply": {"exclude_run": root}}]
        if d["match"]:
            opts.append({"id": "exclude_differing_files", "label": "keep run %s, exclude only its %d structure(s) whose "
                         "chains differ from the declared construct" % (lab, len(d["differ"])),
                         "effects": {"run_in_analysis:" + root: True}, "apply": {}})
        if single and not d["match"]:
            detail["observed_construct"] = {"protein_length": len(single["protein_sequence"]),
                                            "rna_length": len(single["rna_sequence"]),
                                            "sha256": construct_sha(single["protein_sequence"], single["rna_sequence"])}
            opts.append({"id": "analyse_separately", "label": "intentional different constructs: analyse run %s "
                         "separately, as its own construct (protein %d residues, RNA %d nucleotides, as read from its "
                         "chains)" % (lab, len(single["protein_sequence"]), len(single["rna_sequence"])),
                         "effects": {"run_in_analysis:" + root: True, "construct_of:" + root: detail["observed_construct"]["sha256"]},
                         "apply": {"separate_run": root, "construct": single}})
            if offer_reference_set:
                opts.append({"id": "use_as_reference_set", "label": "the declared construct is not the intended one: "
                             "use run %s as the reference set (its chain sequences become the project construct; "
                             "runs that matched the earlier declaration are then asked about)" % lab,
                             "effects": {"reference_set": root, "run_in_analysis:" + root: True},
                             "apply": {"reference_set": root, "construct": single},
                             "depends_on_override": {"construct:" + gname_construct: None,
                                                     "construct:declared": ctx["constructs"].get("declared")}})
        q = ("%d structure(s) of run %s have chains that differ from the construct declared for this project%s. "
             "One project analyses one construct. Which applies?" % (
                 len(d["differ"]), lab, "" if not d["match"] else " (%d of its structures match)" % len(d["match"])))
        out.append(_req("construct_mismatch:" + root, "construct_mismatch", q, opts, dep, group, "rnplens clarify", detail))
    return out


CANDIDATE = re.compile(r"^(EXACT|RENUMBER)")


def chain_mapping_requests(structures, group, ctx, run_of, labels):
    """Structures with more than one construct-matching protein chain or RNA chain; one request per run and chain
    layout, whose options are every candidate mapping (never chosen automatically) and exclusion."""
    layouts = {}
    for s in structures:
        if s["verdict"] in ("INCOMPATIBLE", "UNREADABLE", "DUPLICATE", "EXCLUDED_BY_USER"):
            continue
        cand = {"protein": [], "rna": []}
        for c in s.get("chains") or []:
            if CANDIDATE.match(c.get("status") or ""):
                cand[c["type_by_report"]].append(c["chain"])
        if len(cand["protein"]) > 1 or len(cand["rna"]) > 1:
            sig = "protein=%s;rna=%s" % (",".join(cand["protein"]), ",".join(cand["rna"]))
            layouts.setdefault((run_of.get(s["path"], os.path.dirname(s["path"])), sig), []).append(s)
    out = []
    for (root, sig), ss in sorted(layouts.items()):
        lab = _label(root, labels)
        p = sig.split(";")[0].split("=")[1].split(","); r = sig.split(";")[1].split("=")[1].split(",")
        paths = sorted(s["path"] for s in ss)
        opts = []
        for a, b in itertools.product([x for x in p if x], [x for x in r if x]):
            mid = "protein=%s;rna=%s" % (a, b)
            unused = [x for x in p + r if x and x not in (a, b)]
            opts.append({"id": mid, "label": "protein chain %s with RNA chain %s (chain(s) %s not used: a derived copy "
                         "without them is written; the original file is unchanged)" % (a, b, ",".join(unused)),
                         "effects": dict([("file_in_analysis:" + x, True) for x in paths] +
                                         [("chain_mapping:" + x, mid) for x in paths]),
                         "apply": {"importer_answers": dict([("chainmap:" + x, mid) for x in paths] +
                                                            [("derived:" + x, "accept") for x in paths])}})
        opts.append({"id": "exclude_files", "label": "exclude these %d structure(s) from the analysis" % len(paths),
                     "effects": {"file_in_analysis:" + x: False for x in paths}, "apply": {"exclude_files": paths}})
        q = ("%d structure(s) of run %s contain more than one chain that matches the construct (protein chains %s; "
             "RNA chains %s). Which chains correspond to the construct? RNPLens does not choose." % (
                 len(paths), lab, ",".join(p), ",".join(r)))
        r_ = _req("chain_mapping:%s|%s|%s" % (root, sig, pv.sha256_json(
                      [os.path.relpath(x, root).replace(os.sep, "/") for x in paths])[:10]), "chain_mapping", q, opts,
                  {"file:" + x: ctx["files"].get(x) for x in paths}, group, "rnplens clarify",
                  {"run": lab, "files": paths, "candidate_chains": {"protein": p, "rna": r}})
        # id used before the canonical records (hash of absolute paths): recognised in resolve(), never stored
        r_["_legacy_id"] = "chain_mapping:%s|%s|%s" % (root, sig, pv.sha256_json(paths)[:10])
        out.append(r_)
    return out


def _confidence_candidates(s):
    d = s.get("confidence_dir")
    if not d or not os.path.isdir(d):
        return []
    stem = os.path.basename(s["path"]).rsplit(".", 1)[0]
    pat = re.compile(re.escape(stem) + r"(?![0-9A-Za-z])")
    return sorted(f for f in os.listdir(d) if f.lower().endswith(".json") and "confid" in f.lower() and pat.search(f))


def designation_requests(structures, runs, group, ctx, run_of, labels):
    """Runs of two or more structures whose designated structure is ambiguous: more than one confidence file for a
    structure, or a tie in the engine's ranking score."""
    out = []
    by = {}
    for s in structures:
        by.setdefault((s["engine"], s["run"]), []).append(s)
    for row in runs:
        ss = by.get((row["engine"], row["run"]), [])
        if len(ss) < 2:
            continue
        root = run_of.get(ss[0]["path"], os.path.dirname(ss[0]["path"]))
        multi = {s["path"]: c for s in ss for c in [_confidence_candidates(s)] if len(c) > 1}
        scores = [s["ranking_score"] for s in ss if s.get("ranking_score") is not None]
        tied = [s for s in ss if scores and s.get("ranking_score") == max(scores)] if scores else []
        if not multi and len(tied) < 2:
            continue
        lab = _label(root, labels)
        inc = [s for s in ss if s["verdict"] == "INCLUDED"]
        pool = [s for s in (tied if len(tied) >= 2 and not multi else inc) if s["verdict"] == "INCLUDED"]
        opts = []
        if multi:
            opts.append({"id": "engine_files", "label": "use the engine's own confidence file names only (designated: "
                         "%s); the other JSON files are not the engine's" % (row["designated_execution"] or "none"),
                         "effects": {"designated:" + root: row["designated_execution"] or "none"}, "apply": {}})
        for s in pool:
            opts.append({"id": "designate:" + s["execution"], "label": "designate %s (%s %s)" % (
                s["execution"], s.get("ranking_kind") or "score", s.get("ranking_score")),
                "effects": {"designated:" + root: s["execution"], "run_in_analysis:" + root: True},
                "apply": {"importer_answers": {"designated:" + root: s["execution"]}}})
        opts.append({"id": "none", "label": "no designated structure for run %s (analyses that need one state that "
                     "they were not computed)" % lab, "effects": {"designated:" + root: "none"},
                     "apply": {"importer_answers": {"designated:" + root: "none"}}})
        why = []
        if multi:
            why.append("more than one confidence file for %s" % ", ".join("%s (%s)" % (os.path.basename(k), ", ".join(v))
                                                                           for k, v in sorted(multi.items())))
        if len(tied) >= 2:
            why.append("%d structures share the top %s %s" % (len(tied), ss[0].get("ranking_kind"), max(scores)))
        q = "Which structure did the engine designate in run %s? It is ambiguous: %s." % (lab, "; ".join(why))
        out.append(_req("engine_designation:" + root, "engine_designation", q, opts, {"run:" + root: current_hash("run:" + root, ctx)},
                        group, "rnplens clarify", {"run": lab, "importer_designated": row["designated_execution"],
                                                   "confidence_files": multi, "tied": [s["execution"] for s in tied]}))
    return out


# ---------------------------------------------------------------- matching answers to requests
def resolve(requests, active):
    """-> (resolved [(request, decision)], pending [request], invalid [(decision id, reason)]). A recorded answer
    resolves a request when its option is still offered (its dependency hashes were already checked)."""
    resolved, pending, invalid = [], [], []
    for r in requests:
        legacy = r.pop("_legacy_id", None)
        d = active.get(r["id"])
        if d is None and legacy and legacy != r["id"] and legacy in active:
            d = active[legacy]
        opt = next((o for o in r["options"] if d and o["id"] == d["option"]), None)
        if d and opt is None:
            invalid.append((d.get("id", r["id"]), "the recorded option %r is no longer offered for this question" % d["option"]))
        elif d:
            dropped = {k for k, v in (opt.get("depends_on_override") or {}).items() if v is None}
            uncovered = sorted(set(r["depends_on"]) - dropped - set(d["depends_on"]))
            if uncovered:
                invalid.append((d.get("id", r["id"]), "the question now depends on inputs the recorded answer did not cover: %s"
                                % ", ".join(uncovered)))
            else:
                resolved.append((r, d))
                continue
        pending.append(r)
    return resolved, pending, invalid


def find_request(st, qid):
    """A pending request by its number in the pending list (1-based), its id, or a unique id prefix; or, for
    --revise, the question of a recorded answer."""
    pend = st.get("pending") or []
    if re.fullmatch(r"\d+", qid or "") and 1 <= int(qid) <= len(pend):
        return pend[int(qid) - 1], "pending"
    hits = [r for r in pend if r["id"] == qid] or [r for r in pend if r["id"].startswith(qid)]
    if len(hits) == 1:
        return hits[0], "pending"
    if len(hits) > 1:
        raise S.StateError("%r matches %d pending questions; give the full id" % (qid, len(hits)))
    rec = (st.get("decisions") or {}).get(qid)
    if rec and rec.get("question"):
        return rec["question"], "recorded"
    return None, None


def answer(project, qid, option, text=None, revise=False):
    """Record an answer for a pending request (or, with revise=True, replace a recorded one). Raises
    StateError / ContradictoryAnswer with a researcher-facing message. -> (version id, record)."""
    P = project if isinstance(project, S.Project) else S.Project(project)
    st = P.head()
    if st is None:
        raise S.StateError("%s is not a managed project (no .rnplens/HEAD); create one with 'rnplens update --init'" % P.root)
    req, where = find_request(st, qid)
    if req is None:
        raise S.StateError("no pending question %r in %s (pending: %d). 'rnplens clarify %s' lists them."
                           % (qid, P.root, len(st.get("pending") or []), P.root))
    if where == "recorded" and not revise:
        raise S.StateError("%s is not pending: it was answered %r. Use --revise to replace that answer."
                           % (req["id"], st["decisions"][req["id"]]["option"]))
    opt = next((o for o in req["options"] if o["id"] == option), None)
    if opt is None:
        raise S.StateError("%r is not an option of %s; options: %s" % (option, req["id"], ", ".join(o["id"] for o in req["options"])))
    dep = dict(req["depends_on"])
    for k, v in (opt.get("depends_on_override") or {}).items():
        if v is None:
            dep.pop(k, None)
        else:
            dep[k] = v
    ans = {"option": option, "text": text, "effects": opt.get("effects") or {}, "apply": opt.get("apply") or {},
           "question": req, "request_type": req["type"]}
    pend = [r for r in (st.get("pending") or []) if r["id"] != req["id"]]
    last = st["version"] if st.get("status") == "COMPLETE" else st.get("last_complete_version")
    # results that may depend on the answer are no longer current; resuming reuses whatever the cache still covers
    return P.record_decision(req["id"], ans, dep, revise=revise,
                             extra_change={"pending": pend, "status": "RESUME_PENDING", "analyses": {},
                                           "last_complete_version": last,
                                           "resume": {"from": "import", "reason": "answer to %s" % req["id"]}})


def capability_answer(project, question, option, text=None, revise=False, resume=True):
    """Capability call: record one answer and (by default) resume the pipeline. -> {"outputs": [...], ...}."""
    vid, rec = answer(project, question, option, text, revise)
    out = {"recorded_in_version": vid, "decision": rec["id"], "option": rec["option"], "outputs": []}
    if resume:
        from . import incremental
        code, vres = incremental.run_pipeline(S.Project(project), "resume after answer to %s" % rec["id"])
        out.update({"exit": code, "version": vres})
        st = S.Project(project).head()
        out["outputs"] = [a["dir"] for a in (st.get("analyses") or {}).values() if a.get("dir")]
        out["pending"] = [r["id"] for r in st.get("pending") or []]
    return out


# ---------------------------------------------------------------- command line
def format_request(i, r):
    lines = ["[%d] %s  (%s)" % (i, r["id"], r["type"]), "    " + r["question"]]
    for o in r["options"]:
        lines.append("      - %s: %s" % (o["id"], o["label"]))
    return "\n".join(lines)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="rnplens clarify", description="List the clarification requests of a managed "
                                 "project, record an answer with provenance, and resume. No request is ever answered "
                                 "automatically.")
    ap.add_argument("project", help="managed project directory (made by 'rnplens update --init')")
    ap.add_argument("--answer", nargs=2, metavar=("QUESTION", "OPTION"), help="question number, id or unique id "
                    "prefix, and the option id")
    ap.add_argument("--text", help="your own words for the answer (recorded with it)")
    ap.add_argument("--revise", action="store_true", help="replace a recorded answer (the earlier one is kept in the "
                    "history as superseded)")
    ap.add_argument("--no-resume", action="store_true", help="record the answer only; resume later with --resume")
    ap.add_argument("--resume", action="store_true", help="resume the pipeline from the current state")
    ap.add_argument("--history", action="store_true", help="print every recorded answer, including superseded and "
                    "invalidated ones")
    ap.add_argument("--json", action="store_true", help="print the pending requests as JSON")
    a = ap.parse_args(argv)
    P = S.Project(a.project)
    try:
        st = P.head()
    except S.StateError as ex:
        print("rnplens clarify: refused: %s" % ex, file=sys.stderr)
        return EXIT_REFUSED
    if st is None:
        print("rnplens clarify: refused: %s is not a managed project (no .rnplens/HEAD)" % a.project, file=sys.stderr)
        return EXIT_REFUSED
    if a.history:
        for r in st.get("decision_log") or []:
            print("%3d %-11s %s = %s  (%s; %s)%s" % (r["serial"], r["status"], r["id"], r["option"], r["recorded_utc"],
                                                   r["recorded_in_version"], ("  text: " + r["text"]) if r.get("text") else ""))
        return EXIT_OK
    from . import incremental
    from .capabilities import DIAGNOSE_BLOCKED_EXIT, DiagnoseBlocked, diagnose_blocked_text
    if a.answer:
        try:
            vid, rec = answer(P, a.answer[0], a.answer[1], a.text, a.revise)
        except S.StateError as ex:
            print("rnplens clarify: refused: %s" % ex, file=sys.stderr)
            return EXIT_REFUSED
        print("rnplens clarify: recorded %s = %s in state %s" % (rec["id"], rec["option"], vid))
        if a.no_resume:
            print("  resume later with: rnplens clarify %s --resume" % a.project)
            return EXIT_OK
        a.resume = True
    if a.resume:
        try:
            code, vid = incremental.run_pipeline(P, "resume")
        except DiagnoseBlocked as ex:       # 0.4: a contract that still asks for Diagnose is refused
            print("%s (%s)" % (diagnose_blocked_text("clarify --resume"), ex), file=sys.stderr)
            return DIAGNOSE_BLOCKED_EXIT
        except S.StateError as ex:
            print("rnplens clarify: refused: %s" % ex, file=sys.stderr)
            return EXIT_REFUSED
        incremental.print_status(P)
        return code
    pend = st.get("pending") or []
    if a.json:
        print(json.dumps(pend, indent=1))
    elif not pend:
        print("rnplens clarify: no pending question in %s (state %s, %s)" % (a.project, st["version"], st.get("status")))
    else:
        print("rnplens clarify: %d pending question(s) in %s (state %s):" % (len(pend), a.project, st["version"]))
        for i, r in enumerate(pend, 1):
            print(format_request(i, r))
        print("answer with: rnplens clarify %s --answer <number> <option> [--text \"...\"]" % a.project)
    return EXIT_NEEDS_ANSWER if pend else EXIT_OK
