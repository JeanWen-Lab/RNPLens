"""``rnplens explain``: trace a reported value back to its files, structures, definition and limitations.

Deterministic lookups over execution records only; no language model and no new computation.
Sources (all optional, at least one):
  * analysis directories (``rnplens analyse``): summary.json, report/*.json, region_*/region.json, groups/**.json,
    explain/ is never read back;
  * the project directory of an analysis (manifest.json), given or inferred from report/rnplens_run.json;
  * assistant run directories: evidence.jsonl, run_record.json, plan.json (and the analyses they contain);
  * compare directories (``rnplens compare``): comparison_summary.json, comparison.tsv, evaluate_runs.json.

Every statement in an answer carries an ``evidence_id`` = '<file relative to its root>#<JSON pointer>' (for
evidence.jsonl the pointer is the 0-based line, and the assistant's own record id is given as ``record_id``).
Text quoted verbatim from a record is kept in ``quoted`` and never rewritten.
"""
import csv
import glob
import json
import os
import re
import sys

from . import importer
from . import provenance as pv

KIND = "evidence_query"
DEFINITION = ("Deterministic lookup over execution records (manifests, summaries, Report records, region and group "
              "outputs, provenance blocks, run records, assistant evidence records). Nothing is recomputed and no "
              "language model is used; every statement cites the record field it was read from.")
QUERIES = {
    "evidence": "explain one evidence ID (value, contributing structures, definition, versions, files, limitations)",
    "contact": "which structures support a contact (e.g. K14-G20), with run, sample and designation",
    "structures": "included and excluded structures, with reasons, runs, samples and engine designation",
    "excluded": "which prediction files were excluded, and why",
    "count": "how many structures contributed, at each stage",
    "versions": "RNPLens, component and software versions and the commands that were run",
    "definitions": "the calculation and filtering definitions recorded with each output",
    "files": "relevant output files with SHA-256",
    "limitations": "the limitations recorded with each output",
    "unavailable": "which metric or analysis was unavailable, and why",
    "correspondence": "what correspondence rule was applied (chain status and numbering per structure)",
    "region_mapping": "how the RNA region was mapped (numbering, coverage per structure)",
    "not_like_for_like": "why a comparison is not like-for-like (compare classes, run differences)",
}
COMPARE_CLASS_MEANING = {   # rnplens/compare.py module docstring (class definitions), cited as documentation
    "CONSTRUCT_CHANGED": "the declared protein or RNA sequence differs between the two sets",
    "NOT_EVALUABLE_IN_BOTH": "no value before and no value after",
    "NEWLY_EVALUABLE": "no value before, a value after",
    "NEWLY_UNEVALUABLE": "a value before, none after",
    "CORRESPONDENCE_CHANGED": "both have values but the residue correspondence or chain choice differs, so the two "
                              "numbers do not measure the same thing; reported, never pooled",
    "RUN_FAILED": "the Evaluate run itself failed or was refused (an input or run error, not a scientific class)",
}
NOT_LIKE = ("CONSTRUCT_CHANGED", "NOT_EVALUABLE_IN_BOTH", "NEWLY_EVALUABLE", "NEWLY_UNEVALUABLE", "CORRESPONDENCE_CHANGED", "RUN_FAILED")
CAPABILITIES = [
    {"id": "explain_evidence", "menu": "D", "label": "Explain a reported value: which structures, files, definitions, "
     "versions and limitations it rests on", "status": "DESCRIPTIVE", "needs": ["analysis", "evidence_id", "project?"],
     "call": "rnplens.evidence_query:capability_run",
     "limits": "Explanations are read from execution records; they describe how a value was obtained, not whether it "
               "is right."},
]


class QueryError(Exception):
    pass


def _ptr_escape(k):
    return str(k).replace("~", "~0").replace("/", "~1")


def resolve_pointer(obj, ptr):
    if ptr in ("", "/"):
        return obj
    if not ptr.startswith("/"):
        raise KeyError(ptr)
    for part in ptr.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(obj, list):
            obj = obj[int(part)]
        elif isinstance(obj, dict):
            obj = obj[part]
        else:
            raise KeyError(part)
    return obj


class Sources:
    """The declared roots, and every file read from them (for provenance and the data-access test)."""

    def __init__(self, analyses=(), project=None, run_dirs=(), compares=()):
        self.analyses = [os.path.abspath(a) for a in analyses or []]
        self.run_dirs = [os.path.abspath(r) for r in run_dirs or []]
        self.compares = [os.path.abspath(c) for c in compares or []]
        if not (self.analyses or self.run_dirs or self.compares):
            raise QueryError("give at least one --analysis, --run-dir or --compare directory")
        for d in self.analyses + self.run_dirs + self.compares:
            if not os.path.isdir(d):
                raise QueryError("not a directory: %s" % d)
        for r in self.run_dirs:       # analyses produced inside an assistant run are part of that run's records
            for a in sorted(glob.glob(os.path.join(r, "tools", "analysis_*"))):
                if os.path.exists(os.path.join(a, "summary.json")) and a not in self.analyses:
                    self.analyses.append(a)
        self.read, self._cache = {}, {}
        self.projects = {}
        for a in self.analyses:
            self.projects[a] = os.path.abspath(project) if project and a == self.analyses[0] else self._infer_project(a)

    def _infer_project(self, a):
        rec = self.json(os.path.join(a, "report", "rnplens_run.json"))
        for x in (rec or {}).get("inputs", []):
            if x["path"].endswith("report_contract.json") and os.path.exists(os.path.join(os.path.dirname(x["path"]), "manifest.json")):
                return os.path.dirname(x["path"])
        return None

    def json(self, path):
        path = os.path.abspath(path)
        if path in self._cache:
            return self._cache[path]
        if not os.path.exists(path):
            self._cache[path] = None
            return None
        try:
            v = json.load(open(path, encoding="utf-8"))
        except ValueError:
            v = None
        self.read[path] = pv.sha256_file(path)
        self._cache[path] = v
        return v

    def jsonl(self, path):
        path = os.path.abspath(path)
        if path in self._cache:
            return self._cache[path]
        out = []
        if os.path.exists(path):
            for line in open(path, encoding="utf-8"):
                if line.strip():
                    out.append(json.loads(line))
            self.read[path] = pv.sha256_file(path)
        self._cache[path] = out
        return out

    def tsv(self, path):
        path = os.path.abspath(path)
        if not os.path.exists(path):
            return []
        self.read[path] = pv.sha256_file(path)
        return list(csv.DictReader(open(path, encoding="utf-8"), delimiter="\t"))

    def manifest(self, a):
        p = self.projects.get(a)
        m = self.json(os.path.join(p, "manifest.json")) if p else None
        if m is None:
            return None
        from . import portability as PT                  # report only: never refuses, warns and names resolved paths
        return PT.check_manifest(p, m, "report", "explain")[0]

    def regions(self, a):
        return [(os.path.relpath(p, a), self.json(p)) for p in sorted(glob.glob(os.path.join(a, "region_*", "region.json")))]

    def groups(self, a):
        return [(os.path.relpath(p, a), self.json(p)) for p in sorted(glob.glob(os.path.join(a, "groups", "**", "*.json"), recursive=True))]


def _rel(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


def st(text, root, relpath, pointer, value=None, quoted=None, **extra):
    """One statement of an answer. `text` is template text; `quoted` is record text kept verbatim."""
    d = {"text": text, "evidence_id": pv.evidence_id(relpath, pointer), "root": root}
    if value is not None:
        d["value"] = value
    if quoted is not None:
        d["quoted"] = quoted
    d.update(extra)
    return d


# ---------------------------------------------------------------- structure provenance
def structure_statements(src, a, ids=None):
    man = src.manifest(a)
    if man is None:
        return [st("project manifest not available for this analysis (give --project); structure provenance cannot be "
                   "listed", a, "report/rnplens_run.json", "/inputs", state="INPUT_MISSING")]
    mrel = _rel(a, os.path.join(src.projects[a], "manifest.json"))
    out = []
    for i, s in enumerate(man["structures"]):
        if ids is not None and s["id"] not in ids:
            continue
        chains = "; ".join("chain %s %s %s" % (c["chain"], c.get("type_by_report"), c.get("status")) for c in s.get("chains", []))
        out.append(st("%s: engine %s, run %s, sample %s, %s, verdict %s; file %s (used SHA-256 %s)%s; chains: %s" % (
            s["id"], s["engine"], s["run"], s["sample"], "engine-designated" if s.get("designated") else "not engine-designated",
            s["verdict"], s.get("used_path"), s.get("used_sha256"), " [derived copy of %s]" % s["path"] if s.get("derived") else "",
            chains or "none recorded"), a, mrel, "/structures/%d" % i,
            structure=s["id"], engine=s["engine"], run=s["run"], sample=s["sample"], designated=bool(s.get("designated")),
            verdict=s["verdict"], used_path=s.get("used_path"), used_sha256=s.get("used_sha256")))
    return out


def _ids_in(obj, known):
    found = set()

    def walk(o):
        if isinstance(o, str):
            if o in known:
                found.add(o)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    return found


# ---------------------------------------------------------------- per-query answers
def q_structures(src, only_excluded=False):
    out = []
    for a in src.analyses:
        man = src.manifest(a)
        if man is None:
            out += structure_statements(src, a)
            continue
        mrel = _rel(a, os.path.join(src.projects[a], "manifest.json"))
        if not only_excluded:
            for i, r in enumerate(man.get("runs", [])):
                dx = importer.designated_exclusion(man, r)          # QA O4
                out.append(st("run %s (%s): %d structure(s); engine-designated structure: %s%s" % (
                    r["run"], r["engine"], r["n_structures"], r.get("designated_execution") or "not determinable",
                    (" - " + dx) if dx else ""), a, mrel,
                    "/runs/%d" % i, quoted=r.get("designated_rule"), run=r["run"], engine=r["engine"]))
            out += [s for s in structure_statements(src, a) if s["verdict"] == "INCLUDED"]
        for i, s in enumerate(man["structures"]):
            if s["verdict"] != "INCLUDED":
                out.append(st("excluded at import: %s (%s, run %s, sample %s), verdict %s" % (
                    s["path"], s["id"], s["run"], s["sample"], s["verdict"]), a, mrel, "/structures/%d" % i,
                    quoted="; ".join(s.get("reasons") or []), structure=s["id"], verdict=s["verdict"]))
        for j, f in enumerate(man.get("unrecognised_files", [])):
            out.append(st("not imported (no recognised layout): %s" % f, a, mrel, "/unrecognised_files/%d" % j))
        for j, d in enumerate(man.get("decisions", [])):
            out.append(st("not imported as a candidate: %s" % d.get("file"), a, mrel, "/decisions/%d" % j, quoted=d.get("decision")))
        S = src.json(os.path.join(a, "summary.json")) or {}
        for j, x in enumerate((S.get("report") or {}).get("ineligible", [])):
            out.append(st("not counted by Report: %s, state %s" % (x["structure"], x["state"]), a, "summary.json",
                          "/report/ineligible/%d" % j, structure=x["structure"]))
        for rel, doc in src.regions(a):
            for i, d in enumerate((doc or {}).get("runs", [])):
                for j, x in enumerate(d.get("not_compared", [])):
                    out.append(st("not compared in %s, run %s: %s (%s)" % (doc["region"]["output_dir"], d["run"], x["id"], x["sample"]),
                                  a, rel, "/runs/%d/not_compared/%d" % (i, j), quoted=x["reason"], structure=x["id"]))
    for r in src.run_dirs:
        for i, e in enumerate(src.jsonl(os.path.join(r, "evidence.jsonl"))):
            if e.get("field", "").endswith(".verdict") and e.get("tool") == "import_predictions":
                out.append(st("assistant record %s" % e["id"], r, "evidence.jsonl", "/%d" % i, quoted=e["label"], record_id=e["id"]))
    return out


def q_count(src):
    out = []
    for a in src.analyses:
        man = src.manifest(a)
        if man:
            mrel = _rel(a, os.path.join(src.projects[a], "manifest.json"))
            c = man["counts"]
            out.append(st("import: %d structure file(s) found, %d candidate(s) recognised, %d included, %d excluded, %d "
                          "unrecognised" % (c["found"], c["candidates"], c["included"], c["excluded"], c["unrecognised"]),
                          a, mrel, "/counts", value=c))
        S = src.json(os.path.join(a, "summary.json")) or {}
        if (S.get("report") or {}).get("status") == "RAN":
            for e, n in S["contacts"]["denominators"].items():
                out.append(st("Report: %d eligible %s structure(s) contributed contact lists" % (n, e), a, "summary.json",
                              "/contacts/denominators/%s" % _ptr_escape(e), value=n, engine=e))
            out.append(st("Report eligible structures: %s" % ", ".join(S["report"]["eligible_structures"]), a, "summary.json",
                          "/report/eligible_structures", value=len(S["report"]["eligible_structures"])))
        for rel, doc in src.regions(a):
            if doc:
                s_ = doc["summary"]
                out.append(st("%s: %d structure(s) from %d run(s) compared" % (doc["region"]["output_dir"], s_["n_structures_compared"],
                              s_["n_runs_compared"]), a, rel, "/summary", value=s_["n_structures_compared"]))
        for rel, doc in src.groups(a):
            if isinstance(doc, dict) and isinstance(doc.get("n_structures"), int):
                out.append(st("%s: %d structure(s)" % (rel, doc["n_structures"]), a, rel, "/n_structures", value=doc["n_structures"]))
    for r in src.run_dirs:
        for i, e in enumerate(src.jsonl(os.path.join(r, "evidence.jsonl"))):
            if e.get("unit") == "count" and e.get("level") == "INVENTORY" and e.get("state") == "COMPUTED":
                out.append(st("assistant record %s: %s = %s" % (e["id"], e["label"], e["value"]), r, "evidence.jsonl", "/%d" % i,
                              value=e["value"], record_id=e["id"]))
    return out


def q_versions(src):
    out = []
    for a in src.analyses:
        S = src.json(os.path.join(a, "summary.json")) or {}
        if S:
            out.append(st("analysis summary written by RNPLens %s" % S.get("rnplens_version"), a, "summary.json", "/rnplens_version",
                          value=S.get("rnplens_version")))
        man = src.manifest(a)
        if man:
            out.append(st("project imported by RNPLens %s" % man.get("rnplens_version"), a,
                          _rel(a, os.path.join(src.projects[a], "manifest.json")), "/rnplens_version", value=man.get("rnplens_version")))
        for p in sorted(glob.glob(os.path.join(a, "*", "rnplens_run.json"))) + sorted(glob.glob(os.path.join(a, "evaluate", "*", "rnplens_run.json"))):
            rec = src.json(p)
            if rec:
                out.append(st("%s: RNPLens %s; implementation %s" % (_rel(a, os.path.dirname(p)), rec.get("rnplens_version"),
                              rec.get("implementation")), a, _rel(a, p), "/rnplens_version", value=rec.get("rnplens_version")))
                out.append(st("command", a, _rel(a, p), "/command", quoted=" ".join(rec.get("command", []))))
        rr = src.json(os.path.join(a, "report", "result.json"))
        if rr:
            out.append(st("Report component %s; software environment recorded by Report" % rr.get("package_version"), a,
                          "report/result.json", "/environment", value=rr.get("environment")))
        for rel, doc in src.regions(a) + src.groups(a):
            pb = (doc or {}).get("provenance") if isinstance(doc, dict) else None
            if pb:
                out.append(st("%s: %s output, RNPLens %s, code commit %s" % (rel, pb.get("kind"), pb.get("rnplens_version"),
                              pb.get("code_commit")), a, rel, "/provenance", value=pb.get("rnplens_version")))
    for r in src.run_dirs:
        rec = src.json(os.path.join(r, "run_record.json"))
        if rec:
            out.append(st("assistant %s, answer mode %s, %d recorded model call(s)" % (rec.get("assistant_version"), rec.get("answer_mode"),
                          len(rec.get("llm_calls") or [])), r, "run_record.json", "/assistant_version", value=rec.get("assistant_version")))
            out.append(st("assistant tool registry SHA-256 %s" % rec.get("registry_sha256"), r, "run_record.json", "/registry_sha256"))
    for c in src.compares:
        for i, x in enumerate(src.json(os.path.join(c, "evaluate_runs.json")) or []):
            out.append(st("compare: Evaluate run %s %s exit %s" % (x.get("set"), x.get("target"), x.get("exit")), c, "evaluate_runs.json", "/%d" % i))
    return out


def q_definitions(src):
    out = []
    for a in src.analyses:
        S = src.json(os.path.join(a, "summary.json")) or {}
        for k in ("contacts", "protein_positions", "rna_positions"):
            if isinstance(S.get(k), dict) and S[k].get("definition"):
                out.append(st("%s definition (summary.json)" % k, a, "summary.json", "/%s/definition" % k, quoted=S[k]["definition"]))
        if isinstance(S.get("contacts"), dict) and S["contacts"].get("engine_weighting"):
            out.append(st("engine weighting of Report's contact support", a, "summary.json", "/contacts/engine_weighting",
                          quoted=S["contacts"]["engine_weighting"]))
        for rel, doc in src.regions(a) + src.groups(a):
            pb = (doc or {}).get("provenance") if isinstance(doc, dict) else None
            if pb and pb.get("definition"):
                out.append(st("%s: %s definition" % (rel, pb.get("kind")), a, rel, "/provenance/definition", quoted=pb["definition"],
                              config=pb.get("config")))
    for c in src.compares:
        cs = src.json(os.path.join(c, "comparison_summary.json")) or {}
        for k in ("definition_note", "change_class_note"):
            if cs.get(k):
                out.append(st("compare: %s" % k, c, "comparison_summary.json", "/" + k, quoted=cs[k]))
    return out


def q_files(src):
    out = []
    for a in src.analyses:
        for dp, dn, fn in os.walk(a):
            dn[:] = sorted(x for x in dn if x != "explain")
            for f in sorted(fn):
                p = os.path.join(dp, f)
                out.append(st("output file %s" % _rel(a, p), a, _rel(a, p), "/", value=pv.sha256_file(p), file=_rel(a, p)))
    for r in src.run_dirs:
        for f in ("evidence.jsonl", "run_record.json", "plan.json", "answer.json", "answer.md"):
            p = os.path.join(r, f)
            if os.path.exists(p):
                out.append(st("run file %s" % f, r, f, "/", value=pv.sha256_file(p), file=f))
    for c in src.compares:
        for f in sorted(os.listdir(c)):
            p = os.path.join(c, f)
            if os.path.isfile(p):
                out.append(st("compare file %s" % f, c, f, "/", value=pv.sha256_file(p), file=f))
    return out


def q_limitations(src):
    out = []
    for a in src.analyses:
        S = src.json(os.path.join(a, "summary.json")) or {}
        for i, x in enumerate(S.get("limits", [])):
            out.append(st("analysis summary limitation", a, "summary.json", "/limits/%d" % i, quoted=x))
        if S.get("evaluate_withheld"):
            out.append(st("withheld Evaluate values", a, "summary.json", "/evaluate_withheld", quoted=S["evaluate_withheld"]))
        rr = src.json(os.path.join(a, "report", "result.json")) or {}
        if (rr.get("summary") or {}).get("SEMANTICS"):
            out.append(st("Report's own statement of meaning", a, "report/result.json", "/summary/SEMANTICS", quoted=rr["summary"]["SEMANTICS"]))
        for rel, doc in src.regions(a) + src.groups(a):
            if isinstance(doc, dict):
                for i, x in enumerate(doc.get("limits", []) or []):
                    out.append(st("%s limitation" % rel, a, rel, "/limits/%d" % i, quoted=x))
    for c in src.compares:
        cs = src.json(os.path.join(c, "comparison_summary.json")) or {}
        if cs.get("withheld"):
            out.append(st("compare: withheld metrics %s" % ", ".join(cs["withheld"]["metrics"]), c, "comparison_summary.json",
                          "/withheld/reason", quoted=cs["withheld"]["reason"]))
    return out


def q_unavailable(src):
    out = []
    for a in src.analyses:
        S = src.json(os.path.join(a, "summary.json")) or {}
        if (S.get("report") or {}).get("status") not in (None, "RAN"):
            out.append(st("Report produced no result", a, "summary.json", "/report", quoted=str(S["report"].get("message")), state="CALCULATION_FAILED"))
        for key in ("repeat_agreement", "run_repeat_agreement"):
            for e, v in (S.get(key) or {}).items():
                if v.get("status") != "COMPUTED_BY_REPORT":
                    out.append(st("%s for %s: %s" % (key, e, v.get("status")), a, "summary.json", "/%s/%s" % (key, _ptr_escape(e)),
                                  quoted=v.get("reason") or v.get("text"), state="NOT_COMPUTED"))
        for i, d in enumerate(S.get("diagnose", [])):
            if d.get("status") != "RAN":
                out.append(st("Diagnose %s %s: %s" % (d.get("mode"), d.get("engine"), d.get("status")), a, "summary.json",
                              "/diagnose/%d" % i, quoted=(d.get("reason") or d.get("message") or "").strip(), state="NOT_COMPUTED"))
        if (S.get("steps") or {}).get("diagnose_blocked"):
            out.append(st("Diagnose was not run: DIAGNOSE_BLOCKED in this version (until it is re-qualified)", a, "summary.json",
                          "/steps/diagnose_blocked", quoted=S["steps"]["diagnose_blocked"].get("reason"), state="NOT_COMPUTED"))
        elif (S.get("steps") or {}).get("diagnose_skipped"):
            out.append(st("Diagnose was not run (--without-diagnose)", a, "summary.json", "/steps/diagnose_skipped", state="NOT_COMPUTED"))
        if S and not S.get("evaluate"):
            out.append(st("Evaluate was not run: no experimental reference was supplied", a, "summary.json", "/evaluate_reference",
                          state="INPUT_MISSING"))
        for i, e in enumerate(S.get("evaluate", [])):
            if e.get("status") == "NO_RESULT" or (e.get("dockq_status") and e["dockq_status"] != "SCORED"):
                out.append(st("Evaluate %s: %s" % (e["structure"], e.get("status") or e.get("dockq_status")), a, "summary.json",
                              "/evaluate/%d" % i, quoted=e.get("message"), state="METRIC_UNAVAILABLE"))
        if S.get("evaluate_withheld"):
            out.append(st("Evaluate geometry values withheld", a, "summary.json", "/evaluate_withheld", quoted=S["evaluate_withheld"], state="TOOL_BLOCKED"))
        for rel, doc in src.regions(a):
            if doc and doc.get("figure", {}).get("state", "DRAWN") != "DRAWN":
                out.append(st("%s: contact map %s" % (rel, doc["figure"]["state"]), a, rel, "/figure/state", state="NOT_COMPUTED"))
    for r in src.run_dirs:
        for i, e in enumerate(src.jsonl(os.path.join(r, "evidence.jsonl"))):
            if e.get("state") != "COMPUTED":
                out.append(st("assistant record %s (%s): %s" % (e["id"], e.get("tool"), e.get("state")), r, "evidence.jsonl", "/%d" % i,
                              quoted=e.get("label"), state=e.get("state"), record_id=e["id"]))
        rec = src.json(os.path.join(r, "run_record.json")) or {}
        for i, x in enumerate(rec.get("rejected_steps", [])):
            out.append(st("assistant plan step rejected: %s (%s)" % (x.get("tool"), x.get("rule")), r, "run_record.json",
                          "/rejected_steps/%d" % i, quoted=x.get("reason"), state="INPUT_REFUSED"))
    for c in src.compares:
        cs = src.json(os.path.join(c, "comparison_summary.json")) or {}
        if cs.get("withheld"):
            out.append(st("compare: %s not compared" % ", ".join(cs["withheld"]["metrics"]), c, "comparison_summary.json", "/withheld",
                          quoted=cs["withheld"]["reason"], state="TOOL_BLOCKED"))
        for k, v in (cs.get("unmatched") or {}).items():
            if v:
                out.append(st("compare: unmatched targets (%s): %s" % (k, ", ".join(v)), c, "comparison_summary.json",
                              "/unmatched/%s" % _ptr_escape(k), state="NOT_COMPUTED"))
    from .capabilities import BLOCKED
    for i, b in enumerate(BLOCKED):
        out.append(st("not offered in this version: %s" % b["label"], "rnplens", "capabilities.py", "/BLOCKED/%d" % i,
                      quoted=b["reason"], state="UNAVAILABLE"))
    return out


def q_correspondence(src):
    out = []
    for a in src.analyses:
        man = src.manifest(a)
        if man is None:
            out += structure_statements(src, a)
            continue
        mrel = _rel(a, os.path.join(src.projects[a], "manifest.json"))
        out.append(st("construct: protein %d residues, RNA %d nucleotides; every chain is checked against it at import" % (
            man["construct"]["protein_length"], man["construct"]["rna_length"]), a, mrel, "/construct"))
        for i, s in enumerate(man["structures"]):
            for j, c in enumerate(s.get("chains", [])):
                num = c.get("numbering") or {}
                out.append(st("%s chain %s (%s): status %s, file numbering %s-%s%s" % (
                    s["id"], c["chain"], c.get("type_by_report"), c.get("status"), num.get("first"), num.get("last"),
                    (", offset %s" % c["offset"]) if c.get("offset") is not None else ""), a, mrel, "/structures/%d/chains/%d" % (i, j),
                    structure=s["id"], status=c.get("status"),
                    quoted=json.dumps(c["alignment"], sort_keys=True) if c.get("alignment") else None))
            if s.get("derived"):
                out.append(st("%s: derived copy used (original unchanged)" % s["id"], a, mrel, "/structures/%d/derived/transformations" % i,
                              quoted="; ".join(s["derived"]["transformations"]), structure=s["id"]))
        for i, e in enumerate((src.json(os.path.join(a, "summary.json")) or {}).get("evaluate", [])):
            r = src.json(os.path.join(a, os.path.dirname(e.get("source") or ""), "result.json")) if e.get("source") else None
            if r:
                out.append(st("Evaluate %s: DockQ chain mapping" % e["structure"], a, _rel(a, os.path.join(a, e["source"])),
                              "/dockq/selected_mapping", quoted=json.dumps((r.get("dockq") or {}).get("selected_mapping"), sort_keys=True)))
    out += [x for x in q_not_like_for_like(src) if x.get("compare_class") == "CORRESPONDENCE_CHANGED"]
    return out


def q_region_mapping(src, region=None):
    out = []
    for a in src.analyses:
        for rel, doc in src.regions(a):
            if not doc or (region and doc["region"]["output_dir"] != region and doc["region"]["rna"]["label"] != region):
                continue
            R = doc["region"]
            out.append(st("%s: %s (%s), sequence %s; numbering:" % (R["output_dir"], R["rna"]["label"],
                          "and " + R["protein"]["label"] if R.get("protein") else "no protein range", R["rna"]["sequence"]),
                          a, rel, "/region", quoted=R["numbering"]))
            out.append(st("%s: filtering definition" % R["output_dir"], a, rel, "/contact_definition/filter", quoted=doc["contact_definition"]["filter"]))
            for i, d in enumerate(doc["runs"]):
                for j, x in enumerate(d["structures"]):
                    cv = x["coverage"]
                    out.append(st("%s: %s (run %s, sample %s) coverage %s%s%s" % (
                        R["output_dir"], x["id"], d["run"], x["sample"], cv["status"],
                        ("; unresolved RNA %s" % ",".join(map(str, cv["unresolved_rna_positions"]))) if cv["unresolved_rna_positions"] else "",
                        ("; RNA chains %s" % ",".join(cv["rna_chains"])) if cv.get("rna_chains") else ""), a, rel,
                        "/runs/%d/structures/%d/coverage" % (i, j), quoted=cv.get("reason") or cv.get("numbering"), structure=x["id"]))
    for r in src.run_dirs:
        for i, e in enumerate(src.jsonl(os.path.join(r, "evidence.jsonl"))):
            if e.get("tool") == "region_contacts":
                out.append(st("assistant record %s: region %s, filtered from Report's per-structure contact lists in construct "
                              "positions (%s)" % (e["id"], e.get("region"), e.get("source")), r, "evidence.jsonl", "/%d" % i,
                              quoted=e.get("label"), record_id=e["id"]))
    if not out:
        out.append(st("no region output found (run 'rnplens region' first)", src.analyses[0] if src.analyses else "", "region_*/region.json",
                      "/", state="INPUT_MISSING"))
    return out


def q_not_like_for_like(src):
    out = []
    for c in src.compares:
        cs = src.json(os.path.join(c, "comparison_summary.json")) or {}
        for m, row in sorted((cs.get("metrics") or {}).items()):
            for cls in NOT_LIKE:
                for t in (row.get("targets_by_class") or {}).get(cls, []):
                    out.append(st("%s, target %s: %s - %s" % (m, t, cls, COMPARE_CLASS_MEANING[cls]), c, "comparison_summary.json",
                                  "/metrics/%s/targets_by_class/%s" % (_ptr_escape(m), cls), compare_class=cls, target=t, metric=m))
            if "like_for_like_n" in row:
                out.append(st("%s: %d target(s) compared like-for-like" % (m, row["like_for_like_n"]), c, "comparison_summary.json",
                              "/metrics/%s/like_for_like_n" % _ptr_escape(m), value=row["like_for_like_n"]))
        for k, v in (cs.get("unmatched") or {}).items():
            if v:
                out.append(st("unmatched (%s): %s" % (k, ", ".join(v)), c, "comparison_summary.json", "/unmatched/%s" % _ptr_escape(k)))
    for a in src.analyses:
        man = src.manifest(a)
        if not man:
            continue
        mrel = _rel(a, os.path.join(src.projects[a], "manifest.json"))
        runs = man.get("runs", [])
        if len(runs) >= 2:
            rules = sorted({str(r.get("designated_rule")) for r in runs})
            engines = sorted({r["engine"] for r in runs})
            # per-run denominators are the structures a run contributes (verdict INCLUDED), not the files found in it
            # (runs[].n_structures also counts files excluded at import)
            n_inc = [sum(1 for s in man.get("structures", []) if s.get("verdict") == "INCLUDED"
                         and (s.get("engine"), s.get("run")) == (r["engine"], r["run"])) for r in runs]
            n_found = [r["n_structures"] for r in runs]
            if len(set(n_inc)) > 1:
                out.append(st("runs differ in size (%s included structures per run): per-run counts have different "
                              "denominators" % "/".join(str(n) for n in n_inc), a, mrel, "/structures"))
            if n_found != n_inc:
                out.append(st("structure files excluded at import change the run sizes: %s files found, %s included per run"
                              % ("/".join(str(n) for n in n_found), "/".join(str(n) for n in n_inc)), a, mrel, "/runs"))
            if len(rules) > 1:
                out.append(st("runs designate their structure by different rules", a, mrel, "/runs", quoted="; ".join(rules)))
            if len(engines) > 1:
                out.append(st("runs come from different engines (%s)" % ", ".join(engines), a, mrel, "/runs"))
        for rel, doc in src.regions(a):
            for k, v in ((doc or {}).get("summary", {}).get("per_run") or {}).items():
                cvc = v.get("coverage") or {}
                if cvc.get("PARTIAL") or cvc.get("UNRESOLVED"):
                    out.append(st("%s, run %s: %d structure(s) with partial and %d with unresolved coverage of the range" % (
                        doc["region"]["output_dir"], k, cvc.get("PARTIAL", 0), cvc.get("UNRESOLVED", 0)), a, rel,
                        "/summary/per_run/%s/coverage" % _ptr_escape(k)))
    if not out:
        root = src.analyses[0] if src.analyses else (src.compares or src.run_dirs)[0]
        out.append(st("no record shows a comparison that is not like-for-like", root,
                      "summary.json" if src.analyses else ("comparison_summary.json" if src.compares else "run_record.json"), "/",
                      state="NONE_FOUND"))
    return out


def _parse_contact(label, man):
    m = re.fullmatch(r"\s*([A-Za-z]?)(\d+)\s*[-_/, ]\s*([A-Za-z]?)(\d+)\s*", str(label))
    if not m:
        raise QueryError("contact %r is not of the form K14-G20 (or 14-20)" % label)
    p, r = int(m.group(2)), int(m.group(4))
    if man:
        ps, rs = man["construct"]["protein_sequence"], man["construct"]["rna_sequence"]
        if not (1 <= p <= len(ps) and 1 <= r <= len(rs)):
            raise QueryError("contact %s is outside the construct (protein 1-%d, RNA 1-%d)" % (label, len(ps), len(rs)))
        if (m.group(1) and m.group(1).upper() != ps[p - 1]) or (m.group(3) and m.group(3).upper() != rs[r - 1]):
            raise QueryError("contact %s does not match the construct: position %d is %s, position %d is %s" % (
                label, p, ps[p - 1], r, rs[r - 1]))
    return p, r


def q_contact(src, label):
    out = []
    for a in src.analyses:
        man = src.manifest(a)
        p, r = _parse_contact(label, man)
        cbo = src.json(os.path.join(a, "report", "contacts_by_output.json"))
        if cbo is None:
            out.append(st("no Report contact records in this analysis", a, "report/contacts_by_output.json", "/", state="INPUT_MISSING"))
            continue
        by = {"%s|%s" % (s["engine"], s["execution"]): s for s in (man or {}).get("structures", [])}
        lab = ("%s%d-%s%d" % (man["construct"]["protein_sequence"][p - 1], p, man["construct"]["rna_sequence"][r - 1], r)) if man else "%d-%d" % (p, r)
        with_, without = [], []
        for k in sorted(cbo):
            s = by.get(k, {})
            row = (k, s)
            (with_ if [p, r] in cbo[k] else without).append(row)
        out.append(st("contact %s is listed by %d of %d structure(s) with Report contact lists" % (lab, len(with_), len(cbo)),
                      a, "report/contacts_by_output.json", "/", value=[len(with_), len(cbo)]))
        for k, s in with_:
            i = cbo[k].index([p, r])
            out.append(st("%s lists %s: %s, run %s, sample %s, %s, file %s (SHA-256 %s)" % (
                k, lab, s.get("id"), s.get("run"), s.get("sample"), "engine-designated" if s.get("designated") else "not engine-designated",
                s.get("used_path"), s.get("used_sha256")), a, "report/contacts_by_output.json", "/%s/%d" % (_ptr_escape(k), i),
                structure=s.get("id"), run=s.get("run"), sample=s.get("sample"), designated=bool(s.get("designated"))))
        for k, s in without:
            out.append(st("%s does not list %s: %s, run %s, sample %s" % (k, lab, s.get("id"), s.get("run"), s.get("sample")),
                          a, "report/contacts_by_output.json", "/%s" % _ptr_escape(k), structure=s.get("id"), listed=False))
        S = src.json(os.path.join(a, "summary.json")) or {}
        for i, row in enumerate((S.get("contacts") or {}).get("rows", [])):
            if row["protein_position"] == p and row["rna_position"] == r:
                out.append(st("analysis summary row for %s" % lab, a, "summary.json", "/contacts/rows/%d" % i,
                              value={e: [v["count"], v["of"]] for e, v in row["per_engine"].items()}))
        for rel, doc in src.regions(a):
            for i, row in enumerate((doc or {}).get("contacts", [])):
                if row["protein_position"] == p and row["rna_position"] == r:
                    nobs = sorted({x for v in row["per_run"].values() for x in v["structures"]["not_observed_in"]})
                    out.append(st("%s: %s, present in run(s) %s%s" % (doc["region"]["output_dir"], row["presence"],
                                  ", ".join(row["runs"]["present"]) or "none",
                                  ("; not observed (unresolved) in %s" % ", ".join(nobs)) if nobs else ""), a, rel, "/contacts/%d" % i,
                                  presence=row["presence"]))
        if S.get("contacts", {}).get("definition"):
            out.append(st("contact definition", a, "summary.json", "/contacts/definition", quoted=S["contacts"]["definition"]))
    return out


def _file_of_evidence(src, ev):
    if "#" not in ev:
        raise QueryError("evidence ID %r is not '<file>#<JSON pointer>' (or an assistant record id such as E12 with --run-dir)" % ev)
    rel, ptr = ev.split("#", 1)
    for root in src.analyses + src.run_dirs + src.compares:
        p = os.path.normpath(os.path.join(root, rel))
        if os.path.exists(p):
            return root, rel, ptr, p
    raise QueryError("evidence ID %r names a file that is in none of the given directories" % ev)


def q_evidence(src, ev):
    out = []
    if re.fullmatch(r"E\d+", ev or ""):
        for r in src.run_dirs:
            recs = src.jsonl(os.path.join(r, "evidence.jsonl"))
            for i, e in enumerate(recs):
                if e.get("id") == ev:
                    return _explain_assistant_record(src, r, i, e)
        raise QueryError("assistant record %s not found in the given --run-dir directories" % ev)
    root, rel, ptr, path = _file_of_evidence(src, ev)
    if path.endswith(".jsonl"):
        recs = src.jsonl(path)
        i = int(ptr.strip("/"))
        return _explain_assistant_record(src, root, i, recs[i])
    doc = src.json(path)
    if doc is None:
        raise QueryError("%s is not a JSON record" % rel)
    try:
        obj = resolve_pointer(doc, ptr)
    except (KeyError, IndexError, ValueError):
        raise QueryError("pointer %s does not exist in %s" % (ptr, rel))
    out.append(st("value at %s" % ev, root, rel, ptr, value=obj if not isinstance(obj, (dict, list)) or len(json.dumps(obj)) < 4000 else "(large object; see file)",
                  file_sha256=src.read.get(os.path.abspath(path))))
    a = root if root in src.analyses else None
    # definition: nearest 'definition' on the pointer path, else the file's provenance definition
    parts = [p for p in ptr.split("/")[1:]]
    for k in range(len(parts), -1, -1):
        sub = "/" + "/".join(parts[:k]) if k else ""
        try:
            o = resolve_pointer(doc, sub or "")
        except Exception:
            continue
        if isinstance(o, dict) and isinstance(o.get("source"), str):
            out.append(st("recorded source of this value", root, rel, (sub or "") + "/source", quoted=o["source"]))
        if isinstance(o, dict) and isinstance(o.get("definition"), str):
            out.append(st("definition", root, rel, (sub or "") + "/definition", quoted=o["definition"]))
            break
    if isinstance(doc, dict) and isinstance(doc.get("provenance"), dict):
        pb = doc["provenance"]
        out.append(st("%s output, RNPLens %s, code commit %s, configuration" % (pb.get("kind"), pb.get("rnplens_version"), pb.get("code_commit")),
                      root, rel, "/provenance", value=pb.get("config"), quoted=pb.get("definition")))
        for j, x in enumerate(pb.get("inputs", [])):
            out.append(st("input %s" % x["path"], root, rel, "/provenance/inputs/%d" % j, value=x["sha256"]))
    elif isinstance(doc, dict) and doc.get("rnplens_version"):
        out.append(st("written by RNPLens %s" % doc["rnplens_version"], root, rel, "/rnplens_version"))
    rec = src.json(os.path.join(os.path.dirname(path), "rnplens_run.json"))
    if rec:
        out.append(st("command that wrote %s" % rel, root, _rel(root, os.path.join(os.path.dirname(path), "rnplens_run.json")), "/command",
                      quoted=" ".join(rec.get("command", []))))
    if a is not None:
        man = src.manifest(a)
        if man:
            ids = _ids_in(obj, {s["id"] for s in man["structures"]})
            if not ids and rel.endswith("contacts_by_output.json") and ptr.count("/") >= 1:
                key = ptr.split("/")[1].replace("~1", "/").replace("~0", "~")
                ids = {s["id"] for s in man["structures"] if "%s|%s" % (s["engine"], s["execution"]) == key}
            out += structure_statements(src, a, ids)
        if isinstance(doc, dict):
            for i, x in enumerate(doc.get("limits", []) or []):
                out.append(st("limitation recorded with %s" % rel, root, rel, "/limits/%d" % i, quoted=x))
    return out


def _explain_assistant_record(src, r, i, e):
    out = [st("assistant record %s: %s" % (e["id"], e.get("label")), r, "evidence.jsonl", "/%d" % i, value=e.get("value"),
              record_id=e["id"], state=e.get("state"), statement_class=e.get("class"), level=e.get("level"), tool=e.get("tool"))]
    plan = src.json(os.path.join(r, "plan.json")) or {}
    steps = plan.get("steps", [])
    if isinstance(e.get("step"), int) and 0 <= e["step"] < len(steps):
        out.append(st("produced by plan step %d (%s)" % (e["step"], steps[e["step"]]["tool"]), r, "plan.json", "/steps/%d" % e["step"],
                      value=steps[e["step"]].get("args")))
    if e.get("source"):
        sp = os.path.join(r, e["source"])
        out.append(st("record source file %s" % e["source"], r, e["source"], "/", value=pv.sha256_file(sp) if os.path.exists(sp) else None))
        for a in src.analyses:
            if os.path.abspath(sp).startswith(a + os.sep) and src.manifest(a):
                ids = set(e.get("structures") or [])
                if not ids and e.get("unit") in ("fraction_kn", "count") and e.get("engine"):
                    ids = {s["id"] for s in src.manifest(a)["structures"] if s["engine"] == e["engine"] and s["verdict"] == "INCLUDED"}
                if ids:
                    out += structure_statements(src, a, ids)
                S = src.json(os.path.join(a, "summary.json")) or {}
                if S.get("contacts", {}).get("definition") and e.get("level") in ("EXACT_CONTACT", "RNA_REGION", "PROTEIN_SURFACE"):
                    out.append(st("contact definition", a, "summary.json", "/contacts/definition", quoted=S["contacts"]["definition"]))
    if e.get("note"):
        out.append(st("note recorded with %s" % e["id"], r, "evidence.jsonl", "/%d/note" % i, quoted=e["note"]))
    rec = src.json(os.path.join(r, "run_record.json")) or {}
    if rec:
        out.append(st("assistant %s, answer mode %s" % (rec.get("assistant_version"), rec.get("answer_mode")), r, "run_record.json",
                      "/assistant_version"))
    return out


# ---------------------------------------------------------------- driver
def answer(src, query, **params):
    if query not in QUERIES:
        raise QueryError("unknown query %r; one of: %s" % (query, ", ".join(QUERIES)))
    if query == "evidence":
        if not params.get("evidence_id"):
            raise QueryError("--id is required for the 'evidence' query")
        out = q_evidence(src, params["evidence_id"])
    elif query == "contact":
        if not params.get("contact"):
            raise QueryError("--contact is required for the 'contact' query (e.g. K14-G20)")
        out = q_contact(src, params["contact"])
    elif query in ("structures", "excluded"):
        out = q_structures(src, only_excluded=query == "excluded")
    elif query == "region_mapping":
        out = q_region_mapping(src, params.get("region"))
    else:
        out = {"count": q_count, "versions": q_versions, "definitions": q_definitions, "files": q_files,
               "limitations": q_limitations, "unavailable": q_unavailable, "correspondence": q_correspondence,
               "not_like_for_like": q_not_like_for_like}[query](src)
    return out


def build(analyses=(), project=None, run_dirs=(), compares=(), query="evidence", **params):
    src = Sources(analyses, project, run_dirs, compares)
    stmts = answer(src, query, **params)
    params = {k: v for k, v in sorted(params.items()) if v is not None}
    doc = {"query": {"name": query, "description": QUERIES[query], "params": params},
           "roots": {"analyses": src.analyses, "projects": {a: src.projects[a] for a in src.analyses}, "run_dirs": src.run_dirs,
                     "compares": src.compares},
           "statements": stmts, "n_statements": len(stmts),
           "note": "read from execution records; no language model; nothing recomputed"}
    doc["provenance"] = pv.block(KIND, [{"path": p, "sha256": h} for p, h in sorted(src.read.items())], DEFINITION,
                                 {"query": query, "params": params})
    return doc


def render_text(doc):
    roots = sorted({s["root"] for s in doc["statements"]})
    base = os.path.commonpath(roots) if len(roots) > 1 and all(os.path.isabs(r) for r in roots) else None
    L = ["rnplens explain: %s%s" % (doc["query"]["name"], (" " + json.dumps(doc["query"]["params"], sort_keys=True)) if doc["query"]["params"] else ""),
         "(%s)" % doc["query"]["description"]]
    for s in doc["statements"]:
        line = "- " + s["text"]
        if "value" in s:
            if not isinstance(s["value"], (dict, list)):
                line += " = %s" % s["value"]
            else:
                v = json.dumps(s["value"], sort_keys=True, separators=(",", ":"))
                line += " = %s" % (v if len(v) <= 400 else "(%d characters; see the JSON output)" % len(v))
        if s.get("quoted"):
            line += ' "%s"' % s["quoted"]
        where = (" @ %s" % (os.path.relpath(s["root"], base) if base and os.path.isabs(s["root"]) else s["root"])) if len(roots) > 1 else ""
        L.append(line + "  [%s%s]" % (s["evidence_id"], where))
    L.append("Statements are read from execution records; quoted text is verbatim from the cited field.")
    return "\n".join(L) + "\n"


def audit(doc):
    """Wording audit of the generated (template) text; verbatim quotations of records are excluded, as the fixed
    limits block is in the HTML pages."""
    from .trace import wording_audit
    text = "\n".join(s["text"] for s in doc["statements"])
    return wording_audit(re.sub(r"(?:[A-Za-z]:)?[/\\][^\s,;()]+", " ", text))     # file paths are identifiers, not wording


def write(doc, outdir):
    slug = "explain_%s_%s" % (doc["query"]["name"], pv.sha256_json(doc["query"]["params"])[:8])
    pv.atomic_write_json(os.path.join(outdir, slug + ".json"), doc)
    pv.atomic_write_text(os.path.join(outdir, slug + ".txt"), render_text(doc))
    return [os.path.join(outdir, slug + ".json"), os.path.join(outdir, slug + ".txt")]


def capability_run(analysis=None, project=None, run_dir=None, compare=None, query="evidence", write_out=True, **params):
    try:
        doc = build([analysis] if analysis else [], project, [run_dir] if run_dir else [], [compare] if compare else [], query, **params)
    except QueryError as ex:
        return {"status": "REFUSED", "outputs": [], "message": str(ex)}
    bad = audit(doc)
    if bad:
        return {"status": "FAILED", "outputs": [], "message": "wording audit failed: %s" % bad[:3]}
    files = write(doc, os.path.join(analysis, "explain")) if (write_out and analysis) else []
    return {"status": "OK", "outputs": files, "statements": doc["statements"], "message": render_text(doc),
            "limits": CAPABILITIES[0]["limits"]}


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="rnplens explain", description="Trace a reported value back to its files, "
                                 "structures, definition, versions and limitations, from execution records only (no "
                                 "language model). Queries: " + "; ".join("%s: %s" % kv for kv in QUERIES.items()))
    ap.add_argument("query", nargs="?", default=None, choices=list(QUERIES), help="structured query (default: evidence, with --id)")
    ap.add_argument("--id", dest="evidence_id", help="evidence ID, e.g. region_13-23/region.json#/contacts/0, or E12 with --run-dir")
    ap.add_argument("--contact", help="contact for the 'contact' query, e.g. K14-G20")
    ap.add_argument("--region", help="region directory name for 'region_mapping', e.g. region_13-23")
    ap.add_argument("--analysis", action="append", default=[], help="analysis directory (repeatable)")
    ap.add_argument("--project", help="project directory of the (first) analysis, if it cannot be inferred")
    ap.add_argument("--run-dir", action="append", default=[], help="assistant run directory (repeatable)")
    ap.add_argument("--compare", action="append", default=[], help="'rnplens compare' output directory (repeatable)")
    ap.add_argument("--json", action="store_true", help="print the JSON answer instead of text")
    ap.add_argument("--out", help="write the answer here (default: ANALYSIS/explain/ when an analysis is given)")
    ap.add_argument("--no-write", action="store_true", help="print only")
    a = ap.parse_args(argv)
    q = a.query or ("evidence" if a.evidence_id else None)
    if q is None:
        print("rnplens explain: give a query (%s) or --id" % ", ".join(QUERIES), file=sys.stderr)
        return 2
    try:
        doc = build(a.analysis, a.project, a.run_dir, a.compare, q, evidence_id=a.evidence_id, contact=a.contact, region=a.region)
    except QueryError as ex:
        print("rnplens explain: refused: %s" % ex, file=sys.stderr)
        return 2
    bad = audit(doc)
    if bad:
        print("rnplens explain: wording audit failed: %s" % "; ".join(bad[:3]), file=sys.stderr)
        return 1
    print(json.dumps(doc, indent=1, sort_keys=True) if a.json else render_text(doc), end="" if not a.json else "\n")
    if not a.no_write:
        outdir = a.out or (os.path.join(a.analysis[0], "explain") if a.analysis else None)
        if outdir:
            for f in write(doc, outdir):
                print("  written: %s" % f, file=sys.stderr)
    return 0
