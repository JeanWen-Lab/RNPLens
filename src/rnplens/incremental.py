"""``rnplens update``: a managed project that changes over time, recomputed incrementally.

A managed project is a directory with a versioned state (``state.py``) and, per state version,

    imports/vNNNN/<group>/     an ``rnplens import`` project (only when the import had to be redone)
    analyses/vNNNN/<group>/    an ``rnplens analyse`` directory (only when the analysis had to be redone)
    analyses/vNNNN/index.json  which import and analysis directory each group uses in this version
    analyses/vNNNN/update_report.json, .html   before/after report against the previous complete version

``<group>`` is ``main`` (the declared construct) or ``construct_<hash>`` for a run that the researcher chose to
analyse separately as a different construct. Nothing is overwritten: earlier versions keep their directories.

Each update (1) hashes every file under the declared inputs and detects new, changed, removed and moved files and
runs; (2) re-checks every recorded answer against the hashes it depends on; (3) imports each group, reusing an
earlier import whose key is unchanged; (4) raises clarification requests (``clarify.py``) for anything ambiguous
and stops if one is unanswered; (5) runs ``rnplens analyse`` for each group whose analysis key changed and reuses
the others. The key of a computation is ``state.analysis_key`` over the exact input hashes, construct identity,
chain correspondence, candidate and engine selection rules, tool version, metric definition and analysis
configuration. The state moves to the new version only after every step finished (one atomic commit); completed
steps are cached as they finish, so an interrupted update resumes without redoing them.

Adding candidates changes which predictions are counted; it is not evidence that anything is more correct.

Determinism (DETERMINISM_CONTRACT_v1): the state versions, cache entries, ``index.json`` and the before/after reports
are canonical files (``canonical.py``). Cache keys are computed over the canonical forms of their components (paths
relative to the project), so a project moved or replayed elsewhere keeps its keys; the hashes of the importer's
manifest and of ``summary.json`` (0.3 routes that carry their own creation time) are recorded as content hashes, and
their raw byte hashes only in the sidecar.
"""
import contextlib
import copy
import html as H
import io
import json
import os
import sys

from . import canonical as CN
from . import clarify as C
from . import importer
from . import portability as PT
from . import projection as PJ
from . import provenance as pv
from . import state as S

EXIT_OK, EXIT_FAILED, EXIT_REFUSED, EXIT_NEEDS_ANSWER = 0, 1, 2, 3
IMPORTS, ANALYSES = "imports", "analyses"
REPORT_SCHEMA = "rnplens-update-report-1"

CAPABILITIES = [
    {"id": "incremental_update", "menu": None,
     "label": "Add, change or remove prediction runs in a project and recompute only what changed",
     "status": "DESCRIPTIVE", "needs": ["project_state"], "call": "rnplens.incremental:capability_update",
     "limits": "A before/after report describes how the supplied predictions changed; adding candidates is not "
               "evidence of increased correctness or confidence."},
]

STATEMENTS = [
    "Adding candidates is not evidence of increased correctness or confidence: it changes which predictions are "
    "counted, not what is known about the real complex.",
    "Changes in the contact-support distribution are descriptive. They say how often the supplied predictions list a "
    "contact, not whether the contact exists in the real complex.",
    "Predictions from the same engine are not independent evidence; more of them can repeat the same error.",
    "Changes of the analysis contract (tool version, metric definition, configuration, selection rules) can change "
    "numbers without any change of the predictions; they are listed separately for that reason.",
]

IMPORT_DEFINITION = {"step": "rnplens import", "manifest_schema": importer.MANIFEST_SCHEMA}


def metric_definition():
    """The metric definition and thresholds an analysis depends on (part of its cache key)."""
    from rnpbench_report import agreement, geometry
    from . import analyse
    return {"step": "rnplens analyse", "contact_cutoff_A": geometry.CONTACT_CUTOFF_A,
            "report_version": agreement.VERSION, "summary_schema": analyse.SUMMARY_SCHEMA,
            "contact_definition": "protein residue and RNA nucleotide with any heavy-atom pair within the cutoff, in "
                                  "construct positions (Report's own contact lists)"}


def _hook(step):
    """Failure-injection point for tests (no effect otherwise)."""


# ---------------------------------------------------------------- scanning
def scan(inputs):
    """{absolute path: sha256} of every regular, non-hidden file under the declared inputs, and the missing inputs."""
    files, missing = {}, []
    for a in inputs:
        if os.path.isfile(a):
            files[a] = pv.sha256_file(a)
        elif os.path.isdir(a):
            for dp, dn, fn in os.walk(a):
                dn[:] = sorted(x for x in dn if not x.startswith("."))
                for f in sorted(fn):
                    p = os.path.join(dp, f)
                    if not f.startswith(".") and os.path.isfile(p) and not os.path.islink(p):
                        files[p] = pv.sha256_file(p)
        else:
            missing.append(a)
    return dict(sorted(files.items())), missing


def file_changes(before, after):
    """new / changed / removed / moved paths between two {path: sha} maps (a move keeps the bytes)."""
    new = sorted(set(after) - set(before)); removed = sorted(set(before) - set(after))
    changed = sorted(p for p in set(before) & set(after) if before[p] != after[p])
    moved = []
    for p in list(new):
        src = [q for q in removed if before[q] == after[p]]
        if src:
            moved.append({"from": src[0], "to": p}); new.remove(p); removed.remove(src[0])
    return {"new": new, "changed": changed, "removed": removed, "moved": moved}


def _labels(roots):
    roots = sorted(set(roots))
    if not roots:
        return {}
    common = os.path.commonpath(roots) if len(roots) > 1 else os.path.dirname(roots[0])
    return {r: (os.path.relpath(r, common) if os.path.relpath(r, common) != "." else os.path.basename(r)) for r in roots}


# ---------------------------------------------------------------- canonical views (cache-key inputs)
def manifest_view(man):
    keep = ("id", "engine", "engine_source", "run", "sample", "execution", "path", "original_sha256", "used_sha256",
            "ranking_score", "ranking_kind", "designated", "verdict", "reasons")
    return {"case_id": man["case_id"], "construct": man["construct"], "inputs": man["inputs"],
            "structures": [dict({k: s.get(k) for k in keep},
                                derived=(s.get("derived") or {}).get("transformations")) for s in man["structures"]],
            "runs": man["runs"], "counts": man["counts"], "unrecognised_files": man["unrecognised_files"],
            "decisions": man["decisions"], "resolution_answers": man["resolution_answers"]}


def correspondence(man):
    return {s["path"]: {"id": s["id"], "used_sha256": s.get("used_sha256"), "verdict": s["verdict"],
                        "chains": [[c.get("chain"), c.get("type_by_report"), c.get("status"), c.get("offset")]
                                   for c in s.get("chains") or []],
                        "derived": (s.get("derived") or {}).get("transformations")} for s in man["structures"]}


def selection(man):
    return {"runs": man["runs"], "designated": {s["id"]: bool(s.get("designated")) for s in man["structures"]}}


def construct_record(ps, rs):
    return {"protein_sha256": C.seq_sha(ps), "rna_sha256": C.seq_sha(rs), "protein_length": len(ps),
            "rna_length": len(rs), "sha256": C.construct_sha(ps, rs)}


# ---------------------------------------------------------------- steps
def _fresh_dir(root, kind, vid, name):
    base = os.path.join(root, kind, vid, name)
    d, i = base, 1
    while os.path.exists(d) or os.path.exists(d + ".log"):
        i += 1
        d = "%s.%d" % (base, i)
    os.makedirs(os.path.dirname(d), exist_ok=True)
    return d


def _quiet(fn, log, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = fn(*a, **k)
    pv.atomic_write_text(log, buf.getvalue())
    return rc, buf.getvalue()


def _import(files, construct, out, decl, case_id, answers):
    return _quiet(importer.run, out + ".log", list(files), construct["protein_sequence"], construct["rna_sequence"],
                  out, case_id, decl.get("engine"), answers, False)


def default_analyse(project_dir, out, reference, nproc, diagnose):
    from . import analyse
    return _quiet(analyse.run, out + ".log", project_dir, out, reference, nproc, diagnose)[0]


def _preflight(files, construct, engine):
    """When the importer refuses (nothing includable), the same chain checks it ran, for the construct question."""
    recs, _, _ = importer.recognise(files, engine)
    out = []
    for r in recs:
        try:
            ch = importer.examine_chains(r["path"], construct["protein_sequence"], construct["rna_sequence"])
            v = importer.file_verdict(ch)[0]
        except Exception:
            ch, v = [], "UNREADABLE"
        out.append({"path": r["path"], "verdict": v, "chains": ch})
    return out


def _answer_applies(key, files, roots):
    kind, _, subj = key.partition(":")
    return subj in files or subj in roots


def _group_inputs(gfiles, files, run_of):
    """Hashes of the group's structure files and of every other file in the folders the importer reads for them."""
    dirs = {os.path.dirname(f) for f in gfiles} | {run_of.get(f, os.path.dirname(f)) for f in gfiles}
    structure = set(gfiles)
    return {p: s for p, s in files.items() if p in structure or
            (not p.lower().endswith(importer.STRUCT_EXT) and os.path.dirname(p) in dirs)}


def _rel(root, p):
    return os.path.relpath(p, root).replace(os.sep, "/")


def _sha_or_none(p):
    return pv.sha256_file(p) if p and os.path.isfile(p) else None


# ---------------------------------------------------------------- the pipeline
def run_pipeline(P, reason, declared=None, analyse_fn=None):
    """Bring the project to a state consistent with its current inputs and recorded answers.
    -> (exit code, version id). One commit; on an exception the previous version stays current."""
    analyse_fn = analyse_fn or default_analyse
    pre = P.head()
    if pre is not None:                 # portability: refused before any lock, write or version (PORTABILITY_TEST_v1)
        d0 = copy.deepcopy(declared or pre["declared"])
        PT.apply_relinked_inputs(P.root, d0)
        PT.check_declared_inputs(P.root, d0)
    with P.lock():
        prev = P.head()
        if prev is None:
            raise S.StateError("%s is not a managed project; create it with 'rnplens update --init'" % P.root)
        decl = copy.deepcopy(declared or prev["declared"])
        relinked = PT.apply_relinked_inputs(P.root, decl)   # declared inputs recorded elsewhere by 'rnplens relink'

        vnext = "v%04d" % (int(prev["version"][1:]) + 1)
        files, missing = scan(decl["inputs"])
        ref = decl["config"].get("reference")
        paths = P.paths({"declared": decl})
        cv = paths.canon                 # canonical form of every object that goes into a key
        config = {"diagnose": bool(decl["config"].get("diagnose", True)),
                  "reference": {"path": ref["path"], "sha256": _sha_or_none(ref["path"])} if ref else None}
        if config["diagnose"]:          # 0.4: Diagnose is BLOCKED; refuse before anything is computed or written
            from .capabilities import DiagnoseBlocked
            raise DiagnoseBlocked("the declared analysis contract asks for Diagnose (config.diagnose is true or absent); "
                                  "run 'rnplens update %s --without-diagnose' to declare it off" % P.root)
        if ref and config["reference"]["sha256"] is None:
            raise S.StateError("the declared reference %s is missing" % ref["path"])
        present = [a for a in decl["inputs"] if os.path.exists(a)]
        sfiles = importer.find_structures(present) if present else []
        recs, tops, unrec = importer.recognise(sfiles, decl.get("engine"))
        run_of = {r["path"]: r["run_root"] for r in recs}
        for t in list(tops) + list(unrec):
            run_of.setdefault(t, os.path.dirname(t))
        labels = _labels(run_of.values())
        ps, rs = decl["protein_sequence"], decl["rna_sequence"]
        ctx = {"files": files, "constructs": {"declared": C.construct_sha(ps, rs)}}
        decisions = PT.translate_paths(copy.deepcopy(prev.get("decisions") or {}), relinked)
        log = copy.deepcopy(prev.get("decision_log") or [])
        invalidated = []

        def invalidate(did, why, changed):
            rec = dict(decisions[did], status="INVALIDATED", status_utc=S.now_utc(), status_reason=why,
                       changed_dependencies=changed)
            decisions[did] = rec; log.append(rec)
            invalidated.append({"id": did, "option": rec["option"], "reason": why, "changed": changed})

        # recorded answers: validity against current hashes, then the groups they define (iterate to a fixed point)
        for _ in range(10):
            active = {k: v for k, v in decisions.items() if v.get("status") == "ACTIVE"}
            refs = [v for v in active.values() if v["apply"].get("reference_set")]
            main_c = refs[0]["apply"]["construct"] if refs else {"protein_sequence": ps, "rna_sequence": rs}
            ctx["constructs"]["main"] = C.construct_sha(main_c["protein_sequence"], main_c["rna_sequence"])
            sep = {v["apply"]["separate_run"]: v["apply"]["construct"] for v in active.values() if v["apply"].get("separate_run")}
            groups = {"main": main_c}
            sep_group = {}
            for root, c in sorted(sep.items()):
                g = "construct_" + C.construct_sha(c["protein_sequence"], c["rna_sequence"])[:12]
                groups[g] = c; sep_group[root] = g
                ctx["constructs"]["group:" + g] = C.construct_sha(c["protein_sequence"], c["rna_sequence"])
            bad = [(k, C.changed_dependencies(v, ctx)) for k, v in sorted(active.items())]
            bad = [(k, ch) for k, ch in bad if ch]
            for k, ch in bad:
                invalidate(k, "an input it depends on changed", [{"key": a, "recorded": b, "current": c} for a, b, c in ch])
            if not bad:
                break
        active = {k: v for k, v in decisions.items() if v.get("status") == "ACTIVE"}
        excl_runs = sorted({v["apply"]["exclude_run"] for v in active.values() if v["apply"].get("exclude_run")})
        excl_files = sorted({f for v in active.values() for f in v["apply"].get("exclude_files") or []})
        answers_all = {}
        for k in sorted(active):
            answers_all.update(active[k]["apply"].get("importer_answers") or {})

        gfiles = {g: [] for g in groups}
        for f in sfiles:
            if f in excl_files or any(C._under(f, r) for r in excl_runs):
                continue
            sroot = next((r for r in sorted(sep_group) if C._under(f, r)), None)
            gfiles[sep_group[sroot] if sroot else "main"].append(f)

        requests, grec, reimport = [], {}, {}
        order = ["main"] + sorted(g for g in groups if g != "main")
        for g in order:
            gc = groups[g]; cname = "main" if g == "main" else "group:" + g
            gf = gfiles[g]
            rec = {"construct": construct_record(gc["protein_sequence"], gc["rna_sequence"]), "n_files": len(gf),
                   "runs": sorted({labels.get(run_of.get(f), "") for f in gf})}
            grec[g] = rec
            if not gf:
                rec["status"] = "EMPTY"
                continue
            roots = {run_of.get(f, os.path.dirname(f)) for f in gf}
            answers = {k: v for k, v in sorted(answers_all.items()) if _answer_applies(k, set(gf), roots)}
            case_id = decl["case_id"] if g == "main" else "%s_%s" % (decl["case_id"], g)
            comp = S.key_components("import", cv({"engine": decl.get("engine"), "case_id": case_id, "answers": answers,
                                                  "files": sorted(gf)}),
                                    cv(_group_inputs(gf, files, run_of)), rec["construct"]["sha256"],
                                    cv({k: v for k, v in answers.items() if k.startswith("chainmap:")}),
                                    cv({k: v for k, v in answers.items() if k.startswith("designated:")}),
                                    S.tool_version(), IMPORT_DEFINITION)
            ikey = pv.sha256_json(comp)
            reimport[g] = (gf, gc, case_id, answers, ikey, comp)
            hit = P.cache_lookup(ikey)
            if hit:
                idir, rc, msg = hit["path"], 0, None
            else:
                idir = _fresh_dir(P.root, IMPORTS, vnext, g)
                rc, msg = _import(gf, gc, idir, decl, case_id, answers)
                PJ.sweep(P.root, idir)                  # projections of the files the importer wrote itself (v2)
                _hook("after_import")
            rec.update({"import_key": ikey, "import_components": comp, "import_dir": _rel(P.root, idir),
                        "import_reused": bool(hit), "import_exit": rc})
            if rc == importer.EXIT_NEEDS_CONFIRMATION:
                qs = json.load(open(os.path.join(idir, "QUESTIONS.json"), encoding="utf-8"))["questions"]
                requests += C.from_importer(qs, g, ctx)
                rec["status"] = "NEEDS_CLARIFICATION"
                continue
            if rc != importer.EXIT_OK:
                pre = C.construct_requests(_preflight(gf, gc, decl.get("engine")), g, cname, ctx, run_of, labels,
                                           g == "main" and not refs)
                requests += pre
                rec["status"] = "NEEDS_CLARIFICATION" if pre else "IMPORT_REFUSED"
                rec["message"] = (msg or "")[-1500:]
                continue
            if not hit:
                P.cache_store(ikey, idir, {"kind": "import", "group": g, "components": comp, "computed_in_version": vnext})
            man = json.load(open(os.path.join(idir, "manifest.json"), encoding="utf-8"))
            requests += C.construct_requests(man["structures"], g, cname, ctx, run_of, labels, g == "main" and not refs)
            requests += C.chain_mapping_requests(man["structures"], g, ctx, run_of, labels)
            requests += C.designation_requests(man["structures"], man["runs"], g, ctx, run_of, labels)
            mpath = os.path.join(idir, "manifest.json")
            rec.update({"status": "IMPORTED", "manifest_sha256": pv.sha256_file(mpath),       # raw: sidecar only
                        "manifest_content_sha256": CN.content_sha256(mpath, paths),
                        "counts": man["counts"], "correspondence": correspondence(man), "selection_rules": selection(man)})

        resolved, pending, inval = C.resolve(requests, active)
        for did, why in inval:
            invalidate(did, why, [])
        scan_rec = {"files": files, "missing_inputs": missing, "structure_files": sfiles,
                    "runs": {r: {"label": labels.get(r), "sha256": C.run_hash(r, files)} for r in sorted(set(run_of.values()))}}
        pfiles = (prev.get("inputs") or {}).get("files") or {}
        changes = {"files": file_changes(pfiles, files),
                   "runs": file_changes({r: v["sha256"] for r, v in ((prev.get("inputs") or {}).get("runs") or {}).items()},
                                        {r: v["sha256"] for r, v in scan_rec["runs"].items()})}
        changes["runs"].pop("moved", None)
        base = {"declared": decl, "inputs": scan_rec, "changes_since_parent": changes,
                "construct": {"declared": construct_record(ps, rs),
                              "main": construct_record(groups["main"]["protein_sequence"], groups["main"]["rna_sequence"]),
                              "groups": {g: grec[g]["construct"] for g in order}},
                "config": config, "config_sha256": pv.sha256_json(cv(config)),
                "exclusions": {"runs": excl_runs, "files": excl_files}, "separate_runs": sep_group,
                "decisions": decisions, "decision_log": log, "invalidated_in_this_version": invalidated,
                "applied_decisions": sorted(k for k, v in decisions.items() if v.get("status") == "ACTIVE"),
                "groups": grec, "pending": pending,
                "correspondence": {g: grec[g].get("correspondence") for g in order},
                "selection_rules": {g: grec[g].get("selection_rules") for g in order},
                "last_complete_version": prev["version"] if prev.get("status") == "COMPLETE" else prev.get("last_complete_version")}
        if pending:
            base.update({"status": "NEEDS_CLARIFICATION", "analyses": {}, "resume": {"from": "import"}})
            _hook("before_commit")
            return EXIT_NEEDS_ANSWER, P.commit(base, "%s; %d question(s) need an answer" % (reason, len(pending)))

        analyses = {}
        mdef = metric_definition()
        for g in order:
            rec = grec[g]
            if rec["status"] != "IMPORTED":
                continue
            idir = os.path.join(P.root, rec["import_dir"])
            man = json.load(open(os.path.join(idir, "manifest.json"), encoding="utf-8"))
            comp = S.key_components("analyse", cv(config), cv(manifest_view(man)), rec["construct"]["sha256"],
                                    cv(correspondence(man)), cv(selection(man)), S.tool_version(), mdef)
            akey = pv.sha256_json(comp)
            hit = P.cache_lookup(akey)
            if not hit and rec.get("import_reused") and not PT.recorded_paths_local(
                    idir, list(decl["inputs"]) + ([ref["path"]] if ref else [])):
                # the reused import records structure paths that are not this project's files here (a moved copy or a
                # relinked project): the analysis reads recorded paths, so import again from the current inputs first
                gf_, gc_, cid_, ans_, ikey_, icomp_ = reimport[g]
                idir = _fresh_dir(P.root, IMPORTS, vnext, g)
                rc_, msg_ = _import(gf_, gc_, idir, decl, cid_, ans_)
                PJ.sweep(P.root, idir)
                if rc_ != importer.EXIT_OK:
                    analyses[g] = {"key": akey, "components": comp, "import_dir": _rel(P.root, idir), "status": "FAILED",
                                   "exit": rc_, "reused": False, "message": "re-import for portability failed: %s" % (msg_ or "")[-500:]}
                    continue
                P.cache_store(ikey_, idir, {"kind": "import", "group": g, "components": icomp_, "computed_in_version": vnext})
                mpath = os.path.join(idir, "manifest.json")
                rec.update({"import_dir": _rel(P.root, idir), "import_reused": False, "reimported_for_portability": True,
                            "manifest_sha256": pv.sha256_file(mpath), "manifest_content_sha256": CN.content_sha256(mpath, paths)})
                man = json.load(open(mpath, encoding="utf-8"))
                comp = S.key_components("analyse", cv(config), cv(manifest_view(man)), rec["construct"]["sha256"],
                                        cv(correspondence(man)), cv(selection(man)), S.tool_version(), mdef)
                akey = pv.sha256_json(comp)
                hit = P.cache_lookup(akey)
            row = {"key": akey, "components": comp, "import_dir": rec["import_dir"]}
            if hit:
                adir = hit["path"]
                row.update({"reused": True, "computed_in_version": hit["meta"].get("computed_in_version")})
            else:
                adir = _fresh_dir(P.root, ANALYSES, vnext, g)
                rc = analyse_fn(idir, adir, ref["path"] if ref else None, int(decl.get("nproc") or 1), config["diagnose"])
                PJ.sweep(P.root, adir)                  # projections of the files the analysis wrote itself (v2)
                _hook("after_analyse")
                if rc != 0 or not os.path.exists(os.path.join(adir, "summary.json")):
                    analyses[g] = dict(row, status="FAILED", dir=_rel(P.root, adir), exit=rc, reused=False)
                    continue
                P.cache_store(akey, adir, {"kind": "analyse", "group": g, "components": comp, "computed_in_version": vnext})
                row.update({"reused": False, "computed_in_version": vnext})
            spath = os.path.join(adir, "summary.json")
            row.update({"status": "COMPLETE", "dir": _rel(P.root, adir),
                        "summary_sha256": pv.sha256_file(spath),                                 # raw: sidecar only
                        "summary_content_sha256": CN.content_sha256(spath, paths),
                        "contacts_by_output_sha256": _sha_or_none(os.path.join(adir, "report", "contacts_by_output.json"))})
            analyses[g] = row
        ok = analyses and all(a["status"] == "COMPLETE" for a in analyses.values())
        base.update({"status": "COMPLETE" if ok else "FAILED", "analyses": analyses, "resume": None})
        vdir = os.path.join(P.root, ANALYSES, vnext)
        os.makedirs(vdir, exist_ok=True)
        index = {"provenance": pv.block("analysis_index", [], "which import and analysis directory each group uses in "
                                        "state version %s; a reused directory was computed in an earlier version with "
                                        "an identical cache key" % vnext, {"version": vnext}),
                 "version": vnext, "groups": {g: {"analysis_dir": a.get("dir"), "import_dir": a["import_dir"],
                                                  "reused": a.get("reused"), "computed_in_version": a.get("computed_in_version"),
                                                  "status": a["status"], "key": a["key"],
                                                  "evidence_id": pv.evidence_id("%s/index.json" % vnext, "/groups/" + g)}
                                              for g, a in analyses.items()}}
        CN.write(P.root, os.path.join(ANALYSES, vnext, "index.json"), index, paths)
        new_state = dict(copy.deepcopy(prev), **base, version=vnext, tool_version=S.tool_version())
        if base["last_complete_version"]:
            rep = before_after(P, P.load(base["last_complete_version"]), new_state)
            write_report(rep, os.path.join(vdir, "update_report"), P, paths)
            base["update_report"] = {"json": _rel(P.root, os.path.join(vdir, "update_report.json")),
                                     "html": _rel(P.root, os.path.join(vdir, "update_report.html")),
                                     "from": base["last_complete_version"]}
        _hook("before_commit")
        vid = P.commit(base, reason)
        return (EXIT_OK if ok else EXIT_FAILED), vid


# ---------------------------------------------------------------- creating a project
def init_project(root, inputs, protein_seq, rna_seq, engine=None, case_id=None, reference=None, diagnose=False,
                 nproc=1, analyse_fn=None):
    """Create a managed project at ``root`` and run the pipeline. -> (exit code, version id)."""
    if diagnose:                        # 0.4: Diagnose is BLOCKED
        from .capabilities import DiagnoseBlocked
        raise DiagnoseBlocked("--with-diagnose was given")
    root = os.path.abspath(root)
    P = S.Project(root)
    if P.exists() or os.path.exists(P.dir):
        raise S.StateError("%s is already a managed project; use 'rnplens update %s'" % (root, root))
    if os.path.exists(root) and os.listdir(root):
        raise S.StateError("%s exists and is not empty; a managed project needs a new or empty directory" % root)
    ins = sorted({os.path.abspath(a) for a in inputs})
    for a in ins:
        if not os.path.exists(a):
            raise S.StateError("input %s does not exist" % a)
        if C._under(root, a) or C._under(a, root):
            raise S.StateError("the project directory and the input %s must not contain each other" % a)
    if engine and engine not in importer.ENGINES:
        raise S.StateError("--engine must be one of %s" % ", ".join(importer.ENGINES))
    if set(rna_seq) - set("ACGUN"):
        raise S.StateError("the RNA sequence must use A, C, G, U (N for unknown)")
    cid = case_id or os.path.basename(root)
    decl = {"inputs": ins, "protein_sequence": protein_seq, "rna_sequence": rna_seq, "engine": engine, "case_id": cid,
            "config": {"diagnose": bool(diagnose), "reference": {"path": os.path.abspath(reference)} if reference else None},
            "nproc": int(nproc)}
    os.makedirs(root, exist_ok=True)
    P.commit({"declared": decl, "status": "INITIALISED", "decisions": {}, "decision_log": [], "pending": [],
              "analyses": {}, "construct": {"declared": construct_record(protein_seq, rna_seq)}}, "project created")
    return run_pipeline(P, "first import and analysis", analyse_fn=analyse_fn)


# ---------------------------------------------------------------- before/after report
def _load_json(p):
    return json.load(open(p, encoding="utf-8")) if p and os.path.exists(p) else None


def _included(P, g, st):
    rec = (st.get("groups") or {}).get(g) or {}
    if not rec.get("import_dir"):
        return {}
    man = _load_json(os.path.join(P.root, rec["import_dir"], "manifest.json"))
    if not man:
        return {}
    # keyed by (engine, execution), unique within an import: the recorded absolute path changes when a relocated
    # project is re-imported, which made every unchanged structure look removed and added (QA workflow-replay)
    return {(s["engine"], s["execution"]): {"execution": s["execution"], "sha256": s["original_sha256"],
                                           "engine": s["engine"]}
            for s in man["structures"] if s["verdict"] == "INCLUDED"}


BINS = (("listed in every structure of the engine", lambda f: f == 1.0),
        ("listed in at least half, not all", lambda f: 0.5 <= f < 1.0),
        ("listed in fewer than half", lambda f: f < 0.5))


def support_distribution(P, st, g):
    a = (st.get("analyses") or {}).get(g)
    if not a or a.get("status") != "COMPLETE":
        return None
    rel = a["dir"] + "/summary.json"
    Sm = _load_json(os.path.join(P.root, rel))
    rows = Sm["contacts"]["rows"]
    per = {}
    for e, den in sorted(Sm["contacts"]["denominators"].items()):
        fr = [r["per_engine"][e]["count"] / r["per_engine"][e]["of"] for r in rows
              if r["per_engine"].get(e, {}).get("of") and r["per_engine"][e]["count"]]
        per[e] = {"structures": den, "contacts_listed": len(fr),
                  "bins": {name: sum(1 for f in fr if t(f)) for name, t in BINS},
                  "evidence_id": pv.evidence_id(rel, "/contacts/denominators/" + e)}
    return {"source": rel, "evidence_id": pv.evidence_id(rel, "/contacts/rows"), "contacts_listed": len(rows),
            "per_engine": per,
            "denominators_evidence_id": pv.evidence_id(rel, "/contacts/denominators")}


def _diff_dict(b, a):
    keys = sorted(set(b or {}) | set(a or {}))
    return [{"key": k, "before": (b or {}).get(k), "after": (a or {}).get(k)} for k in keys
            if (b or {}).get(k) != (a or {}).get(k)]


def before_after(P, b, a):
    """Report of what changed between two complete versions, in three separate parts."""
    vb, va = b["version"], a["version"]
    sp = lambda v: ".rnplens/state/%s.json" % v
    paths = P.paths(a)
    groups = ["main"] + sorted(set(b.get("groups") or {}) | set(a.get("groups") or {}) - {"main"})
    comp = {"input_files": file_changes((b.get("inputs") or {}).get("files") or {}, (a.get("inputs") or {}).get("files") or {}),
            "runs": file_changes({r: v["sha256"] for r, v in ((b.get("inputs") or {}).get("runs") or {}).items()},
                                 {r: v["sha256"] for r, v in ((a.get("inputs") or {}).get("runs") or {}).items()}),
            "evidence_id": pv.evidence_id(sp(va), "/inputs"), "groups": {}}
    comp["runs"].pop("moved", None)
    for g in groups:
        ib, ia = _included(P, g, b), _included(P, g, a)
        comp["groups"][g] = {"included_before": len(ib), "included_after": len(ia),
                             "added": sorted(ia[p]["execution"] for p in set(ia) - set(ib)),
                             "removed": sorted(ib[p]["execution"] for p in set(ib) - set(ia)),
                             "changed": sorted(ia[p]["execution"] for p in set(ia) & set(ib) if ia[p]["sha256"] != ib[p]["sha256"]),
                             "evidence_id": pv.evidence_id(sp(va), "/groups/%s/counts" % g),
                             "evidence_id_before": pv.evidence_id(sp(vb), "/groups/%s/counts" % g)}
    serial_b = max([r["serial"] for r in b.get("decision_log") or []] or [0])
    csha = lambda st: dict([(k, ((st.get("construct") or {}).get(k) or {}).get("sha256")) for k in ("declared", "main")] +
                           [("group " + g, v.get("sha256")) for g, v in sorted(((st.get("construct") or {}).get("groups") or {}).items())])
    corr = {"construct": _diff_dict(csha(b), csha(a)),
            "groups_added": sorted(set(a.get("groups") or {}) - set(b.get("groups") or {})),
            "groups_removed": sorted(set(b.get("groups") or {}) - set(a.get("groups") or {})),
            "chain_correspondence": {}, "evidence_id": pv.evidence_id(sp(va), "/correspondence"),
            "answers_recorded": [{"id": r["id"], "option": r["option"], "status": r["status"], "recorded_utc": r["recorded_utc"],
                                  "recorded_in_version": r.get("recorded_in_version")}
                                 for r in a.get("decision_log") or [] if r["serial"] > serial_b and r["status"] == "ACTIVE"],
            "answers_invalidated_or_superseded": [{"id": r["id"], "option": r["option"], "status": r["status"],
                                                  "reason": r.get("status_reason")}
                                                 for r in (a.get("decision_log") or [])[len(b.get("decision_log") or []):]
                                                 if r["status"] != "ACTIVE"]}
    for g in groups:
        cb = ((b.get("correspondence") or {}).get(g)) or {}
        ca = ((a.get("correspondence") or {}).get(g)) or {}
        ch = [{"structure_file": p, "before": cb[p]["chains"], "after": ca[p]["chains"]} for p in sorted(set(cb) & set(ca))
              if cb[p]["chains"] != ca[p]["chains"]]
        if ch:
            for x in ch:
                key = paths.canon_str(x["structure_file"])     # the key as written in the canonical state file
                x["evidence_id"] = pv.evidence_id(sp(va), "/correspondence/%s/%s" % (g, key.replace("~", "~0").replace("/", "~1")))
            corr["chain_correspondence"][g] = ch
    contract = {"tool_version": {"before": b.get("tool_version"), "after": a.get("tool_version")},
                "config": _diff_dict(b.get("config"), a.get("config")),
                "selection_rules": {}, "evidence_id": pv.evidence_id(sp(va), "/config")}
    for g in groups:
        rb = {(x["engine"], x["run"]): x for x in (((b.get("selection_rules") or {}).get(g) or {}).get("runs") or [])}
        ra = {(x["engine"], x["run"]): x for x in (((a.get("selection_rules") or {}).get(g) or {}).get("runs") or [])}
        d = [{"engine": k[0], "run": k[1], "before": rb[k], "after": ra[k]} for k in sorted(set(rb) & set(ra))
             if (rb[k]["designated_rule"], rb[k]["designated_execution"]) != (ra[k]["designated_rule"], ra[k]["designated_execution"])]
        if d:
            contract["selection_rules"][g] = d
    md = {}
    for g in groups:
        kb = ((b.get("analyses") or {}).get(g) or {}).get("components") or {}
        ka = ((a.get("analyses") or {}).get(g) or {}).get("components") or {}
        if kb and ka and kb.get("definition_sha256") != ka.get("definition_sha256"):
            md[g] = {"before": kb.get("definition_sha256"), "after": ka.get("definition_sha256")}
    contract["metric_definition"] = md
    an = {}
    for g in groups:
        x, y = (b.get("analyses") or {}).get(g) or {}, (a.get("analyses") or {}).get(g) or {}
        kb, ka = x.get("components") or {}, y.get("components") or {}
        an[g] = {"before": {"dir": x.get("dir"), "key": x.get("key")}, "after": {"dir": y.get("dir"), "key": y.get("key")},
                 "computation": ("REUSED" if y.get("reused") else "RECOMPUTED") if y else "NOT_PRESENT",
                 "key_components_changed": sorted(k for k in set(kb) | set(ka) if kb.get(k) != ka.get(k)) if (kb and ka) else None,
                 "evidence_id": pv.evidence_id(sp(va), "/analyses/" + g)}
    desc = {g: {"before": support_distribution(P, b, g), "after": support_distribution(P, a, g)} for g in groups}
    inputs = [{"path": os.path.join(P.root, sp(v)), "sha256": pv.sha256_file(os.path.join(P.root, sp(v)))}
              for v in (vb,) if os.path.exists(os.path.join(P.root, sp(v)))]
    for st in (b, a):
        for g, x in (st.get("analyses") or {}).items():
            p = os.path.join(P.root, x.get("dir") or "", "summary.json")
            if x.get("dir") and os.path.exists(p):     # summary.json is not canonical: content hash, raw in sidecar
                inputs.append({"path": p, "content_sha256": CN.content_sha256(p, paths),
                               "raw_file_sha256": pv.sha256_file(p)})
    seen, uniq = set(), []
    for i in inputs:
        if i["path"] not in seen:
            seen.add(i["path"]); uniq.append(i)
    return {"report": REPORT_SCHEMA, "from_version": vb, "to_version": va,
            "provenance": pv.block("update_report", uniq, "comparison of two complete state versions of one managed "
                                   "project, in three separate parts: candidate composition; correspondence and "
                                   "construct; analysis contract and tool version. Evidence IDs are relative to the "
                                   "project directory.", {"from": vb, "to": va}),
            "evidence_root": "project directory",
            "i_candidate_composition": comp, "ii_correspondence_and_construct": corr,
            "iii_analysis_contract_and_tool_version": contract, "analyses": an,
            "descriptive_contact_support": desc, "statements": STATEMENTS}


def _t(rows, head):
    e = H.escape
    return "<table><tr>%s</tr>%s</table>" % ("".join("<th>%s</th>" % e(h) for h in head),
                                             "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % e(str(c)) for c in r) for r in rows))


def render_html(R):
    e = H.escape
    c, k, t = R["i_candidate_composition"], R["ii_correspondence_and_construct"], R["iii_analysis_contract_and_tool_version"]
    parts = ["<!doctype html><html><head><meta charset='utf-8'><title>RNPLens update: %s to %s</title>"
             "<style>body{font-family:sans-serif;max-width:70em;margin:2em auto}td,th{border:1px solid #ccc;padding:2px 6px}"
             "table{border-collapse:collapse;margin:.5em 0}.lim{background:#f4f4f4;padding:.5em 1em}</style></head><body>"
             % (e(R["from_version"]), e(R["to_version"])),
             "<h1>Project update: state %s to %s</h1>" % (e(R["from_version"]), e(R["to_version"])),
             "<div class='lim'><b>Read this first.</b><ul>%s</ul></div>" % "".join("<li>%s</li>" % e(s) for s in R["statements"]),
             "<h2>(i) Candidate composition</h2>",
             _t([[g, x["included_before"], x["included_after"], ", ".join(x["added"]) or "-", ", ".join(x["removed"]) or "-",
                  ", ".join(x["changed"]) or "-"] for g, x in c["groups"].items()],
                ["group", "included before", "included after", "added", "removed", "changed bytes"]),
             _t([[kk, len(v)] for kk, v in c["input_files"].items()], ["input files", "count"]),
             _t([[kk, ", ".join(v) or "-"] for kk, v in c["runs"].items()], ["runs", "folders"]),
             "<h2>(ii) Correspondence and construct</h2>",
             _t([[d["key"], d["before"], d["after"]] for d in k["construct"]] or [["no change", "", ""]], ["construct", "before", "after"]),
             _t([[g, len(v)] for g, v in k["chain_correspondence"].items()] or [["no change", 0]], ["group", "structures with changed chain correspondence"]),
             _t([[r["id"], r["option"], r.get("recorded_in_version") or ""] for r in k["answers_recorded"]] or [["none", "", ""]],
                ["answer recorded", "option", "recorded in state version"]),
             _t([[r["id"], r["option"], r["status"], r.get("reason")] for r in k["answers_invalidated_or_superseded"]] or [["none", "", "", ""]],
                ["earlier answer", "option", "status", "reason"]),
             "<h2>(iii) Analysis contract and tool version</h2>",
             _t([["tool version", t["tool_version"]["before"], t["tool_version"]["after"]]] +
                [["config " + d["key"], json.dumps(d["before"]), json.dumps(d["after"])] for d in t["config"]] +
                [["metric definition (%s)" % g, v["before"][:12], v["after"][:12]] for g, v in t["metric_definition"].items()] +
                [["selection rule %s %s" % (g, d["run"]), d["before"]["designated_execution"], d["after"]["designated_execution"]]
                 for g, v in t["selection_rules"].items() for d in v], ["item", "before", "after"]),
             "<h2>Analyses</h2>",
             _t([[g, x["computation"], ", ".join(x["key_components_changed"] or []) or "-", x["before"]["dir"], x["after"]["dir"]]
                 for g, x in R["analyses"].items()], ["group", "computation", "key parts changed", "before", "after"]),
             "<h2>Contact support (descriptive)</h2>"]
    for g, d in R["descriptive_contact_support"].items():
        rows = []
        for when in ("before", "after"):
            x = d[when]
            if not x:
                rows.append([when, "-", "-", "-", "not available"]); continue
            for eng, v in x["per_engine"].items():
                rows.append([when, eng, v["structures"], v["contacts_listed"], "; ".join("%s: %d" % kv for kv in v["bins"].items())])
        parts.append("<h3>group %s</h3>" % e(g) + _t(rows, ["version", "engine", "structures", "contacts listed", "how often listed"]))
    parts.append("</body></html>")
    return "\n".join(parts)


def write_report(R, stem, P=None, paths=None):
    """Write <stem>.json and <stem>.html; inside a managed project P both are canonical files (sidecar for times)."""
    from . import trace
    html = render_html(R)
    bad = trace.wording_audit(html) + [b for s in R["statements"] for b in trace.wording_audit(s)]
    if bad:
        raise S.StateError("update report wording audit failed: %s" % bad[:3])
    if P is None:
        pv.atomic_write_json(stem + ".json", R)
        pv.atomic_write_text(stem + ".html", html)
        return
    paths = paths or P.paths(P.head())
    rel = os.path.relpath(os.path.abspath(stem), P.root)
    CN.write(P.root, rel + ".json", R, paths)
    CN.write_text(P.root, rel + ".html", html, paths)


# ---------------------------------------------------------------- qualified numerical view (parity checks)
VOLATILE = ("created_utc",)


def _strip(x):
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if k not in VOLATILE}
    if isinstance(x, list):
        return [_strip(v) for v in x]
    return x


def qualified_view(analysis_dir):
    """summary.json (without creation times) and contacts_by_output.json of one analysis directory."""
    return {"summary": _strip(_load_json(os.path.join(analysis_dir, "summary.json"))),
            "contacts_by_output": _load_json(os.path.join(analysis_dir, "report", "contacts_by_output.json"))}


# ---------------------------------------------------------------- command line and capability
def print_status(P, out=sys.stdout):
    st = P.head()
    print("project %s: state %s, %s" % (P.root, st["version"], st.get("status")), file=out)
    for g, a in sorted((st.get("analyses") or {}).items()):
        print("  %-24s %-9s %s%s" % (g, a["status"], a.get("dir"), " (reused from %s)" % a["computed_in_version"]
                                      if a.get("reused") else ""), file=out)
    for x in st.get("invalidated_in_this_version") or []:
        print("  answer invalidated: %s (%s): %s" % (x["id"], x["option"], x["reason"]), file=out)
    if st.get("pending"):
        print("  %d question(s) need an answer: rnplens clarify %s" % (len(st["pending"]), P.root), file=out)
    if st.get("update_report"):
        print("  before/after report: %s" % os.path.join(P.root, st["update_report"]["html"]), file=out)


def capability_update(project, add=None, remove=None, analyse_fn=None):
    P = S.Project(project)
    st = P.head()
    decl = copy.deepcopy(st["declared"])
    decl["inputs"] = sorted((set(decl["inputs"]) | {os.path.abspath(x) for x in add or []}) - {os.path.abspath(x) for x in remove or []})
    code, vid = run_pipeline(P, "update", declared=decl, analyse_fn=analyse_fn)
    st = P.head()
    outs = [a["dir"] for a in (st.get("analyses") or {}).values() if a.get("dir")]
    if st.get("update_report"):
        outs += [st["update_report"]["json"], st["update_report"]["html"]]
    return {"exit": code, "version": vid, "outputs": outs, "pending": [r["id"] for r in st.get("pending") or []]}


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="rnplens update", description="Create or update a managed project: detect new, "
                                 "changed and removed prediction files by SHA-256, recompute only the analyses whose "
                                 "inputs or contract changed, keep every earlier version, and write a before/after "
                                 "report.")
    ap.add_argument("project", help="managed project directory")
    ap.add_argument("paths", nargs="*", help="input folders or files to add (with --init: the inputs)")
    ap.add_argument("--init", action="store_true", help="create the managed project")
    ap.add_argument("--protein-seq", help="(--init) protein construct sequence or FASTA file")
    ap.add_argument("--rna-seq", help="(--init) RNA construct sequence or FASTA file")
    ap.add_argument("--engine", choices=importer.ENGINES, help="(--init) engine label, as for rnplens import")
    ap.add_argument("--case-id", help="(--init) name of the complex (default: the project folder name)")
    ap.add_argument("--remove-input", action="append", default=[], help="stop using a declared input folder or file")
    ap.add_argument("--reference", help="experimental reference structure for Evaluate (an analysis-contract change)")
    ap.add_argument("--no-reference", action="store_true", help="stop using the reference")
    ap.add_argument("--without-diagnose", action="store_true", help="declare Diagnose off (an analysis-contract change; "
                    "needed only for projects whose contract still asks for Diagnose)")
    ap.add_argument("--with-diagnose", action="store_true", help="refused in 0.4: Diagnose is BLOCKED (exit 5)")
    ap.add_argument("--nproc", type=int, help="processes for Report (not part of any result)")
    ap.add_argument("--status", action="store_true", help="print the current state and exit")
    ap.add_argument("--versions", action="store_true", help="print the version history and exit")
    ap.add_argument("--report", nargs=2, metavar=("FROM", "TO"), help="write the before/after report between two "
                    "complete versions into analyses/reports/")
    a = ap.parse_intermixed_args(argv)
    from .capabilities import DIAGNOSE_BLOCKED_EXIT, DiagnoseBlocked, diagnose_blocked_text
    if a.with_diagnose:
        print(diagnose_blocked_text("update --with-diagnose"), file=sys.stderr)
        return DIAGNOSE_BLOCKED_EXIT
    P = S.Project(a.project)
    try:
        if a.init:
            if not (a.protein_seq and a.rna_seq and a.paths):
                print("rnplens update: --init needs --protein-seq, --rna-seq and at least one input path", file=sys.stderr)
                return EXIT_REFUSED
            try:
                ps, rs = importer.read_sequence_arg(a.protein_seq), importer.read_sequence_arg(a.rna_seq)
            except ValueError as ex:
                print("rnplens update: refused: %s" % ex, file=sys.stderr); return EXIT_REFUSED
            code, vid = init_project(a.project, a.paths, ps, rs, a.engine, a.case_id, a.reference, False, a.nproc or 1)
            print_status(P)
            return code
        st = P.head()
        if st is None:
            print("rnplens update: refused: %s is not a managed project; create it with --init" % a.project, file=sys.stderr)
            return EXIT_REFUSED
        if a.status:
            print_status(P); PT.report_head(P.root, "update --status"); return EXIT_OK
        if a.versions:
            for v in P.versions():
                print("%s  %-20s %s  %s" % (v["version"], v["status"], v["created_utc"], v["reason"]))
            return EXIT_OK
        if a.report:
            R = before_after(P, P.load(a.report[0]), P.load(a.report[1]))
            stem = os.path.join(P.root, ANALYSES, "reports", "update_%s_%s" % tuple(a.report))
            write_report(R, stem, P)
            print("rnplens update: report written to %s.html" % stem)
            return EXIT_OK
        decl = copy.deepcopy(st["declared"])
        decl["inputs"] = sorted((set(decl["inputs"]) | {os.path.abspath(x) for x in a.paths})
                                - {os.path.abspath(x) for x in a.remove_input})
        for x in a.paths:
            if not os.path.exists(x):
                print("rnplens update: refused: %s does not exist" % x, file=sys.stderr); return EXIT_REFUSED
            if C._under(os.path.abspath(x), P.root) or C._under(P.root, os.path.abspath(x)):
                print("rnplens update: refused: %s and the project must not contain each other" % x, file=sys.stderr)
                return EXIT_REFUSED
        if a.reference:
            decl["config"]["reference"] = {"path": os.path.abspath(a.reference)}
        if a.no_reference:
            decl["config"]["reference"] = None
        if a.without_diagnose:
            decl["config"]["diagnose"] = False
        if a.nproc:
            decl["nproc"] = a.nproc
        code, vid = run_pipeline(P, "update", declared=decl)
        print_status(P)
        PT.report_head(P.root, "update")
        return code
    except DiagnoseBlocked as ex:
        print("%s (%s)" % (diagnose_blocked_text("update"), ex), file=sys.stderr)
        return DIAGNOSE_BLOCKED_EXIT
    except S.StateError as ex:
        print("rnplens update: refused: %s" % ex, file=sys.stderr)
        return EXIT_REFUSED
