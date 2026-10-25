"""Bounded, result-aware follow-up (RNPLens 0.4, Function 4). EXPERIMENTAL until the frozen live suite (Part 2) has run.

After an initial result (a menu item, or an answer of the bounded assistant pipeline) this module offers ONE further
analysis:

1. build_summary(): a structured evidence summary read from the analysis outputs only (agreement values, contact
   counts per frequency band, run-specific contact labels and positions, unavailable items, inventory counts, the
   analyses already run). Every value carries its evidence ID. Never coordinates, sequences, file contents, file
   paths, engine confidence values or reference files; reference-derived values only with a recorded opt-in.
2. suggest_local(): deterministic follow-up suggestions (rules L1-L7, no language model; always available).
3. Optional Codex planning call (only with recorded consent, consent.py): question + summary + allowlist schema; the
   model returns {follow_up, args, rationale}. policy_check() approves or rejects every proposal (rules F1-F9); one
   replan after a rejection; the model's rationale is stored, never shown.
4. The researcher confirms; execute() runs the controlled RNPLens functions (region, explain, export-methods);
   statements_for() renders the answer from those outputs by fixed templates; check_traceable() refuses any number
   that does not come from a cited record, an approved argument or a declared constant.
5. followup_record.json and followup_plan.json are written; replay.run_followup() re-executes the plan without any
   language model and must reproduce the evidence hash.

Nothing here computes a new statistic and nothing ranks, selects or judges structures."""
import datetime
import glob
import hashlib
import json
import os
import re
import time

from rnplens import provenance as pv

from . import redact

from . import consent as C

SCHEMA = "rnplens.followup.1"
LIMITS = {"max_planning_rounds_per_question": 1, "max_replans_after_rejection": 1, "max_model_calls": 2,
          "max_tool_calls": 4, "identical_tool_call_repeated": False, "second_follow_up_chained_automatically": False,
          "stop_on_usage_guard_or_credit_change": True}
CONSTANTS = {"surface_register_margin": 0.2}    # presentation rule declared in docs/followup.md, not a score
MAX_LISTED = 40                                  # contact labels per list in the summary (truncation is recorded)
ALLOWLIST = ["inspect_region_contacts", "compare_runs_in_region", "explain_unavailable_metric",
             "retrieve_contributing_structures", "inspect_existing_comparison", "export_table_or_methods", "none"]
METRICS = ["repeat_agreement", "run_repeat_agreement", "diagnose", "evaluate_reference_metrics",
           "geometry_four_axis", "diagnose_interpretation", "rna_conformation_difference", "ranking",
           "structure_prediction", "mutation_advice"]
METRIC_LABEL = {"repeat_agreement": "pairwise repeat agreement between structures of an engine",
                "run_repeat_agreement": "agreement between runs",
                "diagnose": "Diagnose", "evaluate_reference_metrics": "reference-based metrics (DockQ, fnat, iRMSD, LRMSD)",
                "geometry_four_axis": "Evaluate four-axis geometry", "diagnose_interpretation": "Diagnose disagreement interpretation",
                "rna_conformation_difference": "RNA conformation difference between candidates",
                "ranking": "candidate ordering or selection", "structure_prediction": "new structure prediction",
                "mutation_advice": "mutation or experiment advice"}
QUERIES = ["structures", "excluded", "count", "contact"]
ARGS = ["rna_start", "rna_end", "protein_start", "protein_end", "runs", "metric", "query", "contact", "evidence_id", "export"]
_N = lambda t: {"type": [t, "null"]}
FOLLOWUP_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "follow_up": {"type": "string", "enum": ALLOWLIST},
    "args": {"type": "object", "additionalProperties": False, "properties": {
        "rna_start": _N("integer"), "rna_end": _N("integer"), "protein_start": _N("integer"), "protein_end": _N("integer"),
        "runs": {"type": ["array", "null"], "items": {"type": "string"}},
        "metric": {"type": ["string", "null"], "enum": METRICS + [None]},
        "query": {"type": ["string", "null"], "enum": QUERIES + [None]},
        "contact": _N("string"), "evidence_id": _N("string"),
        "export": {"type": ["string", "null"], "enum": ["methods", None]}}, "required": ARGS},
    "rationale": {"type": "string"}}, "required": ["follow_up", "args", "rationale"]}
ARG_SPEC = {  # id -> (required, optional pairs)
    "inspect_region_contacts": (["rna_start", "rna_end"], ["protein_start", "protein_end"]),
    "compare_runs_in_region": (["rna_start", "rna_end", "runs"], ["protein_start", "protein_end"]),
    "explain_unavailable_metric": (["metric"], []),
    "retrieve_contributing_structures": (["query"], ["contact"]),
    "inspect_existing_comparison": (["evidence_id"], []),
    "export_table_or_methods": (["export"], []),
    "none": ([], []),
}
REASON = {  # templated reasons shown to the researcher (slots {name} are filled from records, arguments or constants)
    "inspect_region_contacts": "List which residues contact RNA positions {rna_start}-{rna_end}{protein}, in which structures and runs.",
    "compare_runs_in_region": "Compare runs {runs} within RNA positions {rna_start}-{rna_end}{protein}: contacts shared by both runs and contacts found in only one.",
    "explain_unavailable_metric": "Explain from the records why {metric_label} is not available for this result.",
    "retrieve_contributing_structures": "Retrieve from the records which structures contributed ({query}).",
    "inspect_existing_comparison": "Explain the recorded value {evidence_id}: the structures, files, definition and limitations it rests on.",
    "export_table_or_methods": "Write a Methods draft and a provenance manifest from the execution records.",
    "none": "No further analysis is proposed for this result.",
}
RULE_TEXT = {
    "L1": "{excluded} structure file(s) were excluded and {unrecognised} file(s) were in no recognised layout: look at the inventory before interpreting the result.",
    "L2": "The question refers to {metric_label}, which is not available here; the records state why.",
    "L3": "Binding-surface agreement ({surface}) is at least {margin} above contact-register agreement ({register}) (a presentation rule, not a score): the structures share more of the protein surface than of the exact contacts, so the RNA positions of the contacts that differ are worth inspecting.",
    "L4": "The existing region comparison lists {n} contact(s) found only in run {run}.",
    "L5": "The two runs list contacts that appear in only one structure; a region comparison over their RNA positions lists them by run.",
    "L6": "The question asks for an export.",
    "L7": "The question names RNA positions {rna_start}-{rna_end}.",
    "L0": "No local follow-up rule applies to this result.",
}
POLICY_RULES = {"F1": "follow-up id is not in the allowlist", "F2": "arguments are invalid for this follow-up",
                "F3": "the analysis is blocked or not available in this version", "F4": "over the follow-up budget",
                "F5": "repeats an analysis that was already run with the same arguments",
                "F6": "circular: repeats a proposal that the policy already rejected", "F7": "a required input is missing",
                "F8": "the proposal does not have the required shape", "F9": "not grounded in this result or question"}
QUESTION_METRICS = [  # question keywords -> unavailable items they ask about (deterministic relevance rule F9/L2)
    (r"diagnos", ["diagnose", "diagnose_interpretation"]),
    (r"geometr|placement|conformation|internal rmsd|rna[- ]internal|protein[- ]internal", ["geometry_four_axis", "rna_conformation_difference"]),
    (r"dockq|fnat|irmsd|lrmsd|accura|native|experimental|reference", ["evaluate_reference_metrics"]),
    (r"\brank|\bbest\b|\bselect|which (one|structure|model|prediction)s? (is|are|should)|\btrust|\bcorrect", ["ranking"]),
    (r"new prediction|predict (a |new |another )|re-?predict|re-?fold", ["structure_prediction"]),
    (r"mutat|which experiment|experiment to", ["mutation_advice"]),
    (r"agree", ["repeat_agreement", "run_repeat_agreement"]),
]
EXPORT_WORDS = r"export|methods|table|write[- ]?up|supplement|manuscript|paper"
INVENTORY_WORDS = r"exclud|missing|which structures|contribut|how many|inventory|what was (supplied|imported)"
CAP_STATUS_OF = {"inspect_region_contacts": ("region", "region_contacts"), "compare_runs_in_region": ("region", "region_run_comparison"),
                 "explain_unavailable_metric": ("evidence_query", "explain_evidence"),
                 "retrieve_contributing_structures": ("evidence_query", "explain_evidence"),
                 "inspect_existing_comparison": ("evidence_query", "explain_evidence"),
                 "export_table_or_methods": ("methods_export", "export_methods")}
ENGINE_TOKENS = ["BOLTZ2", "CHAI1", "AF3", "RF3", "RF2NA", "Boltz-2", "Chai-1", "C4'"]
CONTACT_RE = re.compile(r"^([A-Za-z])(\d+)-([A-Za-z])(\d+)$")
EID_RE = re.compile(r"^[A-Za-z0-9_.\-]+(/[A-Za-z0-9_.\-]+)*#/[A-Za-z0-9_.~/\-]*$")


class Stop(Exception):
    """A clean stop of the follow-up (kind is recorded): NO_CONSENT, AGENT_NOT_READY, PRIVACY_CHECK, USAGE_GUARD,
    MODEL_UNAVAILABLE, TIMEOUT, ROUND_USED, NOT_CONFIRMED, BUDGET."""
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind, self.message = kind, message


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ================================================================ summary (what may be sent)
class Reader:
    """Every file the summary builder opens (data-access test: only the declared analysis and project records)."""
    def __init__(self):
        self.read = []

    def json(self, path):
        self.read.append(os.path.abspath(path))
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)


def _v(value, eid, **extra):
    d = {"value": value, "evidence_id": eid}
    d.update(extra)
    return d


def _parse_contact(label):
    m = CONTACT_RE.match(label or "")
    if not m:
        return None
    return {"label": label, "protein_residue": m.group(1), "protein_position": int(m.group(2)),
            "rna_nucleotide": m.group(3), "rna_position": int(m.group(4))}


def _esc(k):
    return str(k).replace("~", "~0").replace("/", "~1")


def build_summary(project, analysis, question=None, allow_reference_derived=False, initial=None, reader=None):
    """Structured evidence summary of one analysis (see module docstring). `initial` describes the initial result:
    {"kind": "menu_item"|"assistant_answer", "capability": id, "requested_capabilities": [...]} (no paths)."""
    R = reader or Reader()
    A = os.path.abspath(analysis)
    S = R.json(os.path.join(A, "summary.json"))
    man = R.json(os.path.join(os.path.abspath(project), "manifest.json"))
    inv = S.get("inventory") or {}
    counts = inv.get("counts") or man.get("counts") or {}
    out = {"schema": "rnplens.followup.summary.1", "categories_version": C.CATEGORIES_VERSION,
           "initial_result": {k: v for k, v in (initial or {}).items() if k in ("kind", "capability", "requested_capabilities", "goal")},
           "construct": {k: _v((S.get("construct") or {}).get(k), "summary.json#/construct/%s" % k) for k in ("protein_length", "rna_length")},
           "inventory": {"counts": {k: _v(counts.get(k), "summary.json#/inventory/counts/%s" % k)
                                    for k in ("found", "included", "excluded", "unrecognised") if k in counts},
                         "runs": [], "structures": []}}
    for i, r in enumerate(inv.get("runs") or man.get("runs") or []):
        out["inventory"]["runs"].append({"run": r["run"], "engine": r["engine"],
                                         "n_structures": _v(r["n_structures"], "summary.json#/inventory/runs/%d/n_structures" % i)})
    run_of = {}
    for s in man.get("structures") or []:
        run_of[s["id"]] = s.get("run")
        out["inventory"]["structures"].append({"id": s["id"], "run": s.get("run"), "sample": s.get("sample"),
                                               "engine": s.get("engine"), "designated": bool(s.get("designated")),
                                               "verdict": s.get("verdict")})
    # agreement values (Report's own)
    ag = []
    for key in ("repeat_agreement", "run_repeat_agreement"):
        for e, v in sorted((S.get(key) or {}).items()):
            if isinstance(v, dict) and v.get("status") == "COMPUTED_BY_REPORT":
                base = "summary.json#/%s/%s" % (key, _esc(e))
                ag.append({"scope": key, "engine": e, "between": v.get("runs") or v.get("structures") or S["report"].get("eligible_structures"),
                           "surface_agreement": _v(v.get("surface_agreement"), base + "/surface_agreement"),
                           "register_agreement": _v(v.get("register_agreement"), base + "/register_agreement"),
                           "rna_pose_difference_A": _v(v.get("rna_pose_difference_A"), base + "/rna_pose_difference_A")})
    out["agreement"] = ag
    # contact counts per frequency band (counts over Report's rows; derivation recorded)
    den = (S.get("contacts") or {}).get("denominators") or {}
    rows = (S.get("contacts") or {}).get("rows") or []
    bands, single = [], []
    for e, n in sorted(den.items()):
        ks = [r["per_engine"].get(e, {}).get("count", 0) for r in rows]
        ks = [k for k in ks if k > 0]
        rid = "summary.json#/contacts/rows"
        bands.append({"engine": e, "structures": _v(n, "summary.json#/contacts/denominators/%s" % _esc(e)),
                      "distinct_contacts": _v(len(ks), rid, derivation="rows with count > 0 for %s" % e),
                      "in_every_structure": _v(sum(k == n for k in ks), rid, derivation="rows with count == %s denominator" % e),
                      "in_at_least_half": _v(sum(2 * k >= n for k in ks), rid, derivation="rows with 2*count >= %s denominator" % e),
                      "in_exactly_one": _v(sum(k == 1 for k in ks), rid, derivation="rows with count == 1 for %s" % e)})
        if n >= 2:
            for i, r in enumerate(rows):
                pe = r["per_engine"].get(e) or {}
                if pe.get("count") == 1:
                    lab = "%s%d-%s%d" % (r["protein_residue"], r["protein_position"], r["rna_nucleotide"], r["rna_position"])
                    sid = (pe.get("structures") or [None])[0]
                    single.append(dict(_parse_contact(lab), engine=e, structure=sid, run=run_of.get(sid),
                                       evidence_id="summary.json#/contacts/rows/%d" % i))
    out["contact_bands"] = bands
    out["single_structure_contacts"] = {"listed": single[:MAX_LISTED], "n_total": len(single), "truncated": len(single) > MAX_LISTED}
    rp = sorted({r["position"] for r in (S.get("rna_positions") or {}).get("rows") or [] if any(
        (x or {}).get("count", 0) > 0 for x in r.get("per_engine", {}).values())})
    out["rna_positions_in_contact"] = _v(rp, "summary.json#/rna_positions/rows", derivation="positions with count > 0")
    # region outputs already written (run-specific contact lists, labels and positions only)
    regions, analyses_run = [], []
    for p in sorted(glob.glob(os.path.join(A, "region_*", "region.json"))):
        rel = os.path.relpath(os.path.dirname(p), A).replace(os.sep, "/")
        doc = R.json(p)
        rg, sm = doc.get("region") or {}, doc.get("summary") or {}
        rna = [rg["rna"]["start"], rg["rna"]["end"]] if rg.get("rna") else None
        prot = [rg["protein"]["start"], rg["protein"]["end"]] if rg.get("protein") else None
        runs = sorted(sm.get("runs_selected") or [])
        entry = {"output": rel, "rna": rna, "protein": prot, "runs_compared": sm.get("runs_compared") or [],
                 "n_contacts_in_range": _v((sm.get("n_contacts_in_range") or {}).get("count"), "%s/region.json#/summary/n_contacts_in_range/count" % rel),
                 "only_in_run": []}
        if sm.get("shared_by_all_runs"):
            entry["shared_by_all_runs"] = _v(sm["shared_by_all_runs"].get("count"), "%s/region.json#/summary/shared_by_all_runs/count" % rel)
        for run, x in sorted((sm.get("only_in_run") or {}).items()):
            labs = [c for c in (x.get("contacts") or [])]
            entry["only_in_run"].append({"run": run, "count": _v(x.get("count"), "%s/region.json#/summary/only_in_run/%s/count" % (rel, _esc(run))),
                                         "evidence_id": "%s/region.json#/summary/only_in_run/%s" % (rel, _esc(run)),
                                         "contacts": [_parse_contact(l) or {"label": l} for l in labs[:MAX_LISTED]],
                                         "truncated": len(labs) > MAX_LISTED})
        regions.append(entry)
        analyses_run.append({"kind": "region", "rna": rna, "protein": prot, "runs": runs or None, "output": rel})
    out["region_outputs"] = regions
    for p in sorted(glob.glob(os.path.join(A, "explain", "explain_*.json"))):
        q = (R.json(p).get("query") or {})
        analyses_run.append({"kind": "explain", "query": q.get("name"), "params": q.get("params") or {},
                             "output": os.path.relpath(p, A).replace(os.sep, "/")})
    if os.path.isfile(os.path.join(A, "methods", "methods.md")):
        analyses_run.append({"kind": "methods", "output": "methods/methods.md"})
    if os.path.isfile(os.path.join(A, "groups", "groups.json")):
        analyses_run.append({"kind": "groups", "output": "groups/groups.json"})
    out["analyses_run"] = analyses_run
    # unavailable or blocked items (codes and evidence IDs only)
    un = []
    for key in ("repeat_agreement", "run_repeat_agreement"):
        for e, v in sorted((S.get(key) or {}).items()):
            if not (isinstance(v, dict) and v.get("status") == "COMPUTED_BY_REPORT"):
                un.append({"item": key, "engine": e, "state": (v or {}).get("status", "NOT_COMPUTED"), "evidence_id": "summary.json#/%s/%s" % (key, _esc(e))})
    if (S.get("steps") or {}).get("diagnose_skipped"):
        un.append({"item": "diagnose", "state": "NOT_COMPUTED", "evidence_id": "summary.json#/steps/diagnose_skipped"})
    if not S.get("evaluate"):
        un.append({"item": "evaluate_reference_metrics", "state": "INPUT_MISSING", "evidence_id": "summary.json#/evaluate_reference"})
    if S.get("evaluate_withheld"):
        un.append({"item": "geometry_four_axis", "state": "TOOL_BLOCKED", "evidence_id": "summary.json#/evaluate_withheld"})
    from rnplens.capabilities import BLOCKED
    for i, b in enumerate(BLOCKED):
        if b["id"] in METRICS and not any(u["item"] == b["id"] for u in un):
            un.append({"item": b["id"], "state": "UNAVAILABLE", "static": True, "evidence_id": "capabilities.py#/BLOCKED/%d" % i})
    out["unavailable"] = un
    # reference-derived values: excluded unless the opt-in records allow_reference_derived
    ev = S.get("evaluate") or []
    if allow_reference_derived and ev:
        rd = []
        for i, e in enumerate(ev):
            rd.append({"structure": e.get("structure"), "dockq": _v(e.get("dockq"), "summary.json#/evaluate/%d/dockq" % i),
                       "dockq_class": _v(e.get("dockq_class"), "summary.json#/evaluate/%d/dockq_class" % i)})
        out["reference_derived"] = {"included": True, "values": rd}
    else:
        out["reference_derived"] = {"included": False, "n_structures_with_reference_values_excluded": len(ev)}
    return out


def summary_text(summary):
    """The exact bytes that are hashed and (with consent) sent."""
    return json.dumps(summary, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _walk_eids(o, acc):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "evidence_id" and isinstance(v, str):
                acc.add(v)
            else:
                _walk_eids(v, acc)
    elif isinstance(o, list):
        for v in o:
            _walk_eids(v, acc)
    return acc


def summary_evidence_ids(summary):
    return _walk_eids(summary, set())


def contact_labels(summary):
    labs = {c["label"] for c in summary["single_structure_contacts"]["listed"]}
    for r in summary["region_outputs"]:
        for x in r["only_in_run"]:
            labs.update(c["label"] for c in x["contacts"])
    return labs


def contacted_positions(summary):
    pos = set(summary["rna_positions_in_contact"]["value"] or [])
    pos.update(c["rna_position"] for c in summary["single_structure_contacts"]["listed"])
    return pos


# ================================================================ privacy check of the outgoing payload
REFERENCE_KEYS = re.compile(r"\b(dockq|fnat|irmsd|lrmsd)\b", re.I)


def _construct_sequences(project):
    seqs = []
    for f in ("construct_protein.fasta", "construct_rna.fasta"):
        p = os.path.join(project, f)
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                seqs.append("".join(l.strip() for l in fh if l.strip() and not l.startswith(">")).upper())
    return [s for s in seqs if s]


def privacy_check(text, project, allow_reference_derived=False, k=8, names=None):
    """-> violations (empty: the payload may be sent). Sequences are read locally for this check only. names: the
    redaction map (0.4); any real run, folder, sample or file name of at least four characters is a violation."""
    v = []
    if names is not None and redact.leaked_names(text, names):
        v.append("a real file, folder, run or sample name found")
    up = text.upper()
    for s in _construct_sequences(project):
        for i in range(0, max(0, len(s) - k + 1)):
            if s[i:i + k] in up:
                v.append("sequence fragment of length %d found" % k); break
    if re.search(r"^(ATOM|HETATM)\s", text, re.M) or re.search(r"\b_atom_site\.", text):
        v.append("coordinate records found")
    if re.search(r"(^|[\s\"'=])(/|[A-Za-z]:\\)[^\s\"']+", text):
        v.append("an absolute file path found")
    if re.search(r"\b[0-9a-f]{64}\b", text):
        v.append("a file hash found")
    if re.search(r"\.(cif|pdb|mmcif|ent)\b", text, re.I) and re.search(r"reference", text, re.I):
        v.append("a reference file name found")
    if not allow_reference_derived:
        body = text.split("Structured evidence summary", 1)[-1]
        for m in re.finditer(r"\"(dockq|dockq_class|fnat|irmsd|lrmsd)\"\s*:", body, re.I):
            v.append("reference-derived value %s without the separate opt-in" % m.group(1)); break
    return v


# ================================================================ deterministic local suggestions (no LLM)
def _blank():
    return {k: None for k in ARGS}


def _args(**kw):
    a = _blank()
    a.update(kw)
    return a


def question_metrics(question):
    q = (question or "").lower()
    out = []
    for pat, items in QUESTION_METRICS:
        if re.search(pat, q):
            out += [i for i in items if i not in out]
    return out


def question_ranges(question, rna_length):
    out = []
    for m in re.finditer(r"(?<![\w.])(\d{1,5})\s*(?:-|–|\.\.|to)\s*(\d{1,5})(?![\w.])", question or ""):
        a, b = int(m.group(1)), int(m.group(2))
        if 1 <= a <= b <= (rna_length or 0):
            out.append((a, b))
    return out


def _runs(summary):
    return [r["run"] for r in summary["inventory"]["runs"]]


def _region_args(summary, a, b):
    runs = _runs(summary)
    if len(runs) == 2:
        return "compare_runs_in_region", _args(rna_start=a, rna_end=b, runs=list(runs))
    return "inspect_region_contacts", _args(rna_start=a, rna_end=b)


def suggest_local(summary, question=None):
    """Deterministic follow-up suggestions (rules L1-L7). Each: {id, args, rule, reason_slots}. Suggestions that the
    policy would refuse (for example a repeat of an analysis already run) are dropped by the caller."""
    S, out = summary, []
    def add(fid, args, rule, slots):
        if not any(x["id"] == fid and x["args"] == args for x in out):
            out.append({"id": fid, "args": args, "rule": rule, "reason_slots": slots})
    c = S["inventory"]["counts"]
    exc, unr = c.get("excluded", {}).get("value") or 0, c.get("unrecognised", {}).get("value") or 0
    if exc or unr:                                                                         # L1 inventory first
        add("retrieve_contributing_structures", _args(query="excluded"), "L1",
            {"excluded": {"evidence_id": c["excluded"]["evidence_id"], "value": exc},
             "unrecognised": {"evidence_id": c["unrecognised"]["evidence_id"], "value": unr}})
    unavailable = [u["item"] for u in S["unavailable"]]
    asked = question_metrics(question) + [x for x in ((S.get("initial_result") or {}).get("requested_capabilities") or [])]
    asked = [{"ranking_or_selection": "ranking", "diagnose_disagreement": "diagnose_interpretation", "geometry_decomposition": "geometry_four_axis",
              "new_prediction": "structure_prediction", "reference_accuracy": "evaluate_reference_metrics"}.get(m, m) for m in asked]
    for m in asked:                                                                        # L2 an unavailable metric was asked for
        if m in unavailable and m in METRICS:
            add("explain_unavailable_metric", _args(metric=m), "L2", {"metric_label": {"text": METRIC_LABEL[m]}})
    runs = _runs(S)
    single = S["single_structure_contacts"]["listed"]
    for g in S["agreement"]:                                                               # L3 surface >= register + margin
        sv, rv = g["surface_agreement"]["value"], g["register_agreement"]["value"]
        if sv is None or rv is None or sv - rv < CONSTANTS["surface_register_margin"] - 1e-12:
            continue
        pos = sorted({x["rna_position"] for r in S["region_outputs"] for o in r["only_in_run"] for x in o["contacts"] if "rna_position" in x}
                     | {x["rna_position"] for x in single})
        if pos:
            fid, a = _region_args(S, pos[0], pos[-1])
            add(fid, a, "L3", {"surface": dict(g["surface_agreement"]), "register": dict(g["register_agreement"]),
                               "margin": {"constant": "surface_register_margin", "value": CONSTANTS["surface_register_margin"]}})
    for r in S["region_outputs"]:                                                          # L4 run-specific contacts already listed
        for o in r["only_in_run"]:
            if o["count"]["value"]:
                add("inspect_existing_comparison", _args(evidence_id=o["evidence_id"]), "L4",
                    {"n": dict(o["count"]), "run": {"text": o["run"]}})
    if len(runs) == 2 and single and not S["region_outputs"]:                              # L5
        pos = sorted({x["rna_position"] for x in single})
        add("compare_runs_in_region", _args(rna_start=pos[0], rna_end=pos[-1], runs=list(runs)), "L5", {})
    if re.search(EXPORT_WORDS, (question or "").lower()):                                 # L6
        add("export_table_or_methods", _args(export="methods"), "L6", {})
    L = (S["construct"]["rna_length"] or {}).get("value")
    for a, b in question_ranges(question, L):                                              # L7
        fid, args = _region_args(S, a, b)
        add(fid, args, "L7", {"rna_start": {"arg": "rna_start", "value": a}, "rna_end": {"arg": "rna_end", "value": b}})
    return out


# ================================================================ policy: approve or reject every proposal
def _norm_runs(runs, all_runs):
    if runs is None or sorted(runs) == sorted(all_runs):
        return "ALL"
    return ",".join(sorted(runs))


def tool_calls_for(fid, args, summary):
    """Fixed mapping of an allowlisted follow-up to controlled tool calls (no other call is possible)."""
    rr = lambda: "%d-%d" % (args["rna_start"], args["rna_end"])
    pr = lambda: ("%d-%d" % (args["protein_start"], args["protein_end"])) if args.get("protein_start") is not None else None
    if fid == "inspect_region_contacts":
        return [{"tool": "region", "rna_range": rr(), "protein_range": pr(), "runs": None}]
    if fid == "compare_runs_in_region":
        return [{"tool": "region", "rna_range": rr(), "protein_range": pr(), "runs": list(args["runs"])}]
    if fid == "explain_unavailable_metric":
        return [{"tool": "explain", "query": "unavailable", "params": {}}]
    if fid == "retrieve_contributing_structures":
        q = args["query"]
        return [{"tool": "explain", "query": q, "params": {"contact": args["contact"]} if q == "contact" else {}}]
    if fid == "inspect_existing_comparison":
        return [{"tool": "explain", "query": "evidence", "params": {"evidence_id": args["evidence_id"]}}]
    if fid == "export_table_or_methods":
        return [{"tool": "methods"}]
    return []


def call_key(call, all_runs):
    if call["tool"] == "region":
        return ("region", call["rna_range"], call["protein_range"], _norm_runs(call["runs"], all_runs))
    if call["tool"] == "explain":
        return ("explain", call["query"], json.dumps(call["params"], sort_keys=True))
    return (call["tool"],)


def _done_keys(summary):
    all_runs = _runs(summary)
    keys = set()
    for a in summary["analyses_run"]:
        if a["kind"] == "region":
            keys.add(("region", "%d-%d" % tuple(a["rna"]) if a["rna"] else None,
                      "%d-%d" % tuple(a["protein"]) if a["protein"] else None, _norm_runs(a["runs"], all_runs)))
        elif a["kind"] == "explain":
            p = {k: v for k, v in (a["params"] or {}).items() if k != "query"}
            if a["query"] == "evidence" and "evidence_id" not in p and "id" in p:
                p = {"evidence_id": p["id"]}
            keys.add(("explain", a["query"], json.dumps(p, sort_keys=True)))
        elif a["kind"] == "methods":
            keys.add(("methods",))
    return keys


def _int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def _arg_errors(fid, a, summary):
    req, opt = ARG_SPEC[fid]
    err = []
    for k in ARGS:
        if k not in req + opt and a.get(k) is not None:
            err.append("argument %s is not used by %s" % (k, fid))
    for k in req:
        if a.get(k) is None:
            err.append("argument %s is required" % k)
    if err:
        return err
    L = {"rna": (summary["construct"]["rna_length"] or {}).get("value"), "protein": (summary["construct"]["protein_length"] or {}).get("value")}
    for kind in ("rna", "protein"):
        s, e = a.get(kind + "_start"), a.get(kind + "_end")
        if s is None and e is None:
            continue
        if s is None or e is None:
            err.append("%s range needs both start and end" % kind); continue
        if not (_int(s) and _int(e)):
            err.append("%s range must be integers" % kind); continue
        if not (1 <= s <= e <= (L[kind] or 0)):
            err.append("%s range %s-%s is outside construct positions 1-%s" % (kind, s, e, L[kind]))
    if fid == "compare_runs_in_region":
        runs, names = a.get("runs"), _runs(summary)
        if not isinstance(runs, list) or len(runs) != 2 or len(set(runs)) != 2 or any(r not in names for r in runs):
            err.append("runs must be two different runs of this project (%s)" % ", ".join(names))
    if fid == "explain_unavailable_metric" and a.get("metric") not in METRICS:
        err.append("metric %r is not a known item" % a.get("metric"))
    if fid == "retrieve_contributing_structures":
        if a.get("query") not in QUERIES:
            err.append("query %r is not one of %s" % (a.get("query"), ", ".join(QUERIES)))
        elif a["query"] == "contact" and a.get("contact") not in contact_labels(summary):
            err.append("contact %r is not a contact listed in this result" % a.get("contact"))
        elif a["query"] != "contact" and a.get("contact") is not None:
            err.append("contact is used only with query 'contact'")
    if fid == "inspect_existing_comparison":
        e = a.get("evidence_id")
        if not isinstance(e, str) or not EID_RE.match(e) or ".." in e or e.startswith("capabilities.py"):
            err.append("evidence_id %r is not an evidence ID of this analysis" % e)
        elif e not in summary_evidence_ids(summary):
            err.append("evidence_id %r is not in the evidence summary" % e)
    return err


def _grounded(fid, a, summary, question):
    q = (question or "").lower()
    if fid in ("inspect_region_contacts", "compare_runs_in_region"):
        rng = (a["rna_start"], a["rna_end"])
        if rng in question_ranges(question, (summary["construct"]["rna_length"] or {}).get("value")):
            return None
        if not any(a["rna_start"] <= p <= a["rna_end"] for p in contacted_positions(summary)):
            return "no structure lists a contact at RNA positions %d-%d" % rng
        return None
    if fid == "explain_unavailable_metric":
        m = a["metric"]
        items = {u["item"]: u for u in summary["unavailable"]}
        if m not in items:
            return "%s is available in this result" % m
        req = (summary.get("initial_result") or {}).get("requested_capabilities") or []
        if m in question_metrics(question) or (not items[m].get("static") and m in ("repeat_agreement", "run_repeat_agreement")) or \
                m in [{"ranking_or_selection": "ranking", "diagnose_disagreement": "diagnose_interpretation",
                       "geometry_decomposition": "geometry_four_axis", "new_prediction": "structure_prediction"}.get(x, x) for x in req]:
            return None
        return "the question does not ask about %s" % METRIC_LABEL[m]
    if fid == "retrieve_contributing_structures":
        c = summary["inventory"]["counts"]
        if a["query"] == "contact" or re.search(INVENTORY_WORDS, q) or (c.get("excluded", {}).get("value") or 0) or (c.get("unrecognised", {}).get("value") or 0):
            return None
        return "nothing was excluded and the question does not ask about the inventory"
    if fid == "export_table_or_methods":
        return None if re.search(EXPORT_WORDS, q) else "the question does not ask for an export"
    return None


def capability_status(fid):
    """Registry status of the RNPLens capability a follow-up uses (UNAVAILABLE when its module does not import)."""
    if fid not in CAP_STATUS_OF:
        return None
    import importlib
    mod, cid = CAP_STATUS_OF[fid]
    try:
        m = importlib.import_module("rnplens." + mod)
    except ImportError:
        return "UNAVAILABLE"
    return next((c["status"] for c in getattr(m, "CAPABILITIES", []) if c["id"] == cid), "UNAVAILABLE")


def policy_check(proposal, summary, question, session):
    """-> verdict {approved, rule, reason, tool_calls}. session: {"model_calls", "tool_calls", "rejected": [...],
    "done": set of call keys from this session}. Deterministic; the model's rationale is never read."""
    def no(rule, why):
        return {"approved": False, "rule": rule, "rule_text": POLICY_RULES[rule], "reason": why, "tool_calls": []}
    if not isinstance(proposal, dict) or not isinstance(proposal.get("follow_up"), str) or not isinstance(proposal.get("args"), dict):
        return no("F8", "the proposal is not an object with follow_up and args")
    fid, a = proposal["follow_up"], dict(_blank(), **proposal["args"])
    from rnplens.capabilities import BLOCKED
    blocked = {b["id"] for b in BLOCKED} | {"diagnose", "geometry_decomposition", "grouping_as_selection", "ranking_or_selection",
                                            "new_prediction", "prediction", "grouping"}
    if fid in blocked:
        return no("F3", "%s is not offered in this version" % fid)
    if fid not in ALLOWLIST:
        return no("F1", "%r is not an allowlisted follow-up" % fid)
    extra = set(proposal["args"]) - set(ARGS)
    if extra:
        return no("F8", "unknown argument(s): %s" % ", ".join(sorted(extra)))
    key = (fid, json.dumps(a, sort_keys=True))
    if key in session.get("rejected", []):
        return no("F6", "this exact proposal was already rejected")
    if fid == "none":
        return {"approved": True, "rule": None, "rule_text": None, "reason": "no follow-up", "tool_calls": []}
    err = _arg_errors(fid, a, summary)
    if err:
        return no("F2", "; ".join(err))
    st = capability_status(fid)
    if st not in ("QUALIFIED", "DESCRIPTIVE"):
        return no("F3", "the function used by %s is %s here" % (fid, st))
    g = _grounded(fid, a, summary, question)
    if g:
        return no("F9", g)
    calls = tool_calls_for(fid, a, summary)
    allr = _runs(summary)
    done = _done_keys(summary) | set(session.get("done", ()))
    for c in calls:
        if call_key(c, allr) in done:
            return no("F5", "%s was already run with these arguments" % c["tool"])
    if session.get("tool_calls", 0) + len(calls) > LIMITS["max_tool_calls"]:
        return no("F4", "%d tool call(s) would exceed the limit of %d" % (session.get("tool_calls", 0) + len(calls), LIMITS["max_tool_calls"]))
    return {"approved": True, "rule": None, "rule_text": None, "reason": "approved", "tool_calls": calls, "args": a}


# ================================================================ execution with the controlled tools only
def _run_tool(call, project, analysis):
    if call["tool"] == "region":
        from rnplens import region
        return region.capability_run(project, analysis, call["rna_range"], call["protein_range"], call["runs"])
    if call["tool"] == "explain":
        from rnplens import evidence_query as EQ
        return EQ.capability_run(analysis=analysis, project=project, query=call["query"], **call["params"])
    if call["tool"] == "methods":
        from rnplens import methods_export as ME
        return ME.capability_run(analysis, project)
    raise ValueError("no controlled tool %r" % call["tool"])


_ABS = re.compile(r"(?<![\w<])(?:/[^\s/'\"<>]+)+/([^\s/'\"<>]+)")


def _norm(text, project, analysis):
    """Every absolute path reduced to its last component (a replay in a moved copy of the
    analysis must reproduce the hash; provenance texts of copied records keep their original absolute paths)."""
    if not isinstance(text, str):
        return text
    return _ABS.sub(lambda m: "<path>/" + m.group(1), text)


def execute(calls, project, analysis, session, log):
    """Run approved tool calls; refuses an identical repeat and anything over the tool-call limit."""
    allr = session.get("all_runs") or []
    results = []
    for c in calls:
        k = call_key(c, allr)
        entry = {"tool": c["tool"], "call": c, "started_utc": _now()}
        if k in session.setdefault("done", set()):
            entry.update(status="REFUSED_REPEAT", message="identical tool call already made in this follow-up")
        elif session.get("tool_calls", 0) >= LIMITS["max_tool_calls"]:
            entry.update(status="REFUSED_BUDGET", message="tool-call limit of %d reached" % LIMITS["max_tool_calls"])
        else:
            session["tool_calls"] = session.get("tool_calls", 0) + 1
            session["done"].add(k)
            t0 = time.time()
            try:
                res = _run_tool(c, project, analysis)
            except Exception as ex:                    # a failing function is recorded, never hidden
                res = {"status": "FAILED", "outputs": [], "message": "%s: %s" % (type(ex).__name__, ex)}
            entry.update(status=str(res.get("status")), message=_norm(res.get("message") if res.get("status") != "OK" else None, project, analysis),
                         outputs=[os.path.relpath(o, analysis).replace(os.sep, "/") for o in res.get("outputs") or []],
                         wall_s=round(time.time() - t0, 2))
        log.append(entry)
        results.append(entry)
    return results


# ================================================================ answer statements (fixed templates)
def _load_rel(analysis, rel):
    with open(os.path.join(analysis, rel), encoding="utf-8") as fh:
        return json.load(fh)


def resolve(analysis, eid):
    """Value at an evidence ID '<file relative to the analysis>#<JSON pointer>'."""
    path, _, ptr = eid.partition("#")
    if path == "capabilities.py":
        from rnplens.capabilities import BLOCKED
        doc = {"BLOCKED": BLOCKED}
    else:
        p = os.path.realpath(os.path.join(analysis, path))
        if not p.startswith(os.path.realpath(analysis) + os.sep):
            raise KeyError("evidence outside the analysis: %s" % eid)
        doc = _load_rel(analysis, path)
    from rnplens.evidence_query import resolve_pointer
    return resolve_pointer(doc, ptr)


def _st(typ, text, slots=None, cites=()):
    return {"type": typ, "text": text, "slots": slots or {}, "cites": [c for c in cites if c]}


def _ev(analysis, eid):
    return {"evidence_id": eid, "value": resolve(analysis, eid)}


LIMIT_TEXT = {
    "region": "Shared and run-specific contacts are listings with counts, not an agreement score; positions not resolved in a structure are 'not observed', never 'no contact'. Recurrence among predictions does not show that a contact exists in the real complex.",
    "explain": "Explanations are read from execution records; they describe how a value was obtained, not whether it is right.",
    "methods": "The Methods draft is for author review: it restates what the records show was run and adds no citation, condition or statistic.",
    "general": "Agreement among predictions is not evidence that any structure is right: predictions can share the same error.",
}
METRIC_MATCH = {"repeat_agreement": r"#/repeat_agreement/", "run_repeat_agreement": r"#/run_repeat_agreement/",
                "diagnose": r"#/(steps/diagnose_skipped|diagnose/)",
                "evaluate_reference_metrics": r"#/(evaluate_reference|evaluate/)", "geometry_four_axis": r"#/evaluate_withheld"}


def _blocked_index(metric):
    from rnplens.capabilities import BLOCKED
    return next((i for i, b in enumerate(BLOCKED) if b["id"] == metric), None)


def statements_for(fid, args, results, analysis):
    S = []
    for r in results:
        if r["status"] != "OK":
            S.append(_st("NOT_RUN", "The follow-up step {tool} did not give a result ({status}): {message}",
                         {"tool": {"text": r["tool"]}, "status": {"log": "status", "value": r["status"], "index": results.index(r)},
                          "message": {"log": "message", "value": r.get("message") or "", "index": results.index(r)}}))
            continue
        if r["tool"] == "region":
            rj = next(o for o in r["outputs"] if o.endswith("region.json"))
            rel = rj[:-len("/region.json")]
            doc = _load_rel(analysis, rj)
            sm = doc["summary"]
            sl = {"a": _ev(analysis, rj + "#/region/rna/start"), "b": _ev(analysis, rj + "#/region/rna/end"),
                  "n": _ev(analysis, rj + "#/summary/n_contacts_in_range/count")}
            t = "RNA positions {a}-{b}"
            if doc["region"].get("protein"):
                sl.update(c=_ev(analysis, rj + "#/region/protein/start"), d=_ev(analysis, rj + "#/region/protein/end"))
                t += " with protein positions {c}-{d}"
            S.append(_st("OBSERVATION", t + ": {n} distinct residue–nucleotide contact(s) are listed by at least one compared structure.",
                         sl, [rj + "#/summary/n_contacts_in_range"]))
            if len(sm.get("runs_compared") or []) >= 2:
                S.append(_st("OBSERVATION", "{k} of them are shared by all compared runs ({runs}).",
                             {"k": _ev(analysis, rj + "#/summary/shared_by_all_runs/count"), "runs": _ev(analysis, rj + "#/summary/runs_compared")},
                             [rj + "#/summary/shared_by_all_runs"]))
                for run in sorted(sm.get("only_in_run") or {}):
                    base = rj + "#/summary/only_in_run/%s" % _esc(run)
                    sl = {"run": {"text": run}, "c": _ev(analysis, base + "/count")}
                    t = "Found only in run {run}: {c} contact(s)"
                    if sm["only_in_run"][run].get("contacts"):
                        sl["labels"] = _ev(analysis, base + "/contacts"); t += " ({labels})"
                    S.append(_st("OBSERVATION", t + ".", sl, [base]))
            nd = (sm.get("not_determined") or {}).get("count")
            if nd:
                S.append(_st("LIMITATION", "{nd} contact(s) could not be checked in at least one structure; they are 'not observed', not 'no contact'.",
                             {"nd": _ev(analysis, rj + "#/summary/not_determined/count")}, [rj + "#/summary/not_determined"]))
            S.append(_st("LIMITATION", LIMIT_TEXT["region"]))
        elif r["tool"] == "explain":
            ej = next(o for o in r["outputs"] if o.endswith(".json"))
            doc = _load_rel(analysis, ej)
            sts = doc.get("statements") or []
            idx = list(range(len(sts)))
            if fid == "explain_unavailable_metric":
                m = args["metric"]
                bi = _blocked_index(m)
                pat = METRIC_MATCH.get(m)
                idx = [i for i in idx if (pat and re.search(pat, sts[i].get("evidence_id", ""))) or
                       (bi is not None and sts[i].get("evidence_id", "").endswith("capabilities.py#/BLOCKED/%d" % bi))]
                if not idx:
                    S.append(_st("NOT_RUN", "The records list no reason for {metric_label} in this analysis.", {"metric_label": {"text": METRIC_LABEL[m]}}))
            shown = idx[:25]
            for i in shown:
                if "#/limits/" in (sts[i].get("evidence_id") or "") and sts[i].get("quoted"):
                    S.append(_st("LIMITATION", "Recorded limitation: {q}", {"q": _ev(analysis, ej + "#/statements/%d/quoted" % i)},
                                 [sts[i].get("evidence_id")]))
                    continue
                sl = {"t": _ev(analysis, ej + "#/statements/%d/text" % i)}
                t = "Recorded: {t}"
                val = sts[i].get("value")
                if val is not None and not isinstance(val, (dict, list)):
                    sl["v"] = _ev(analysis, ej + "#/statements/%d/value" % i); t += " = {v}"
                elif isinstance(val, dict):
                    parts = []
                    for j, (k, x) in enumerate(sorted((k, x) for k, x in val.items() if k != "evidence_id" and re.fullmatch(r"[a-z_]+", k)
                                                       and (not isinstance(x, (dict, list)) or (isinstance(x, list) and all(not isinstance(y, (dict, list)) for y in x))))):
                        if j >= 6:
                            break
                        sl["f" + "abcdefgh"[j]] = _ev(analysis, ej + "#/statements/%d/value/%s" % (i, _esc(k)))
                        parts.append("%s {f%s}" % (k.replace("_", " "), "abcdefgh"[j]))
                    if parts:
                        t += " (" + "; ".join(parts) + ")"
                if sts[i].get("quoted") and fid == "explain_unavailable_metric":
                    sl["q"] = _ev(analysis, ej + "#/statements/%d/quoted" % i); t += " (recorded reason: {q})"
                S.append(_st("NOT_AVAILABLE" if fid == "explain_unavailable_metric" else "RECORD", t + ".", sl,
                             [sts[i].get("evidence_id"), ej + "#/statements/%d" % i]))
            if len(idx) > len(shown):
                S.append(_st("RECORD", "Further statements are in {f}.", {"f": {"file": ej, "value": ej}}))
            S.append(_st("LIMITATION", LIMIT_TEXT["explain"]))
        elif r["tool"] == "methods":
            md = next((o for o in r["outputs"] if o.endswith("methods.md")), None)
            pm = next((o for o in r["outputs"] if o.endswith("provenance_manifest.json")), None)
            S.append(_st("OUTPUT", "A Methods draft was written to {md} and a provenance manifest to {pm}.",
                         {"md": {"file": md, "value": md}, "pm": {"file": pm, "value": pm}}))
            S.append(_st("LIMITATION", LIMIT_TEXT["methods"]))
    return S


def reason_statement(fid, args, rule=None, rule_slots=None):
    """The templated reason for the chosen follow-up (the model's rationale is never used)."""
    a = args or {}
    t = REASON[fid]
    sl = {}
    if "{protein}" in t:
        if a.get("protein_start") is not None:
            t = t.replace("{protein}", " with protein positions {protein_start}-{protein_end}")
        else:
            t = t.replace("{protein}", "")
    for k in ("rna_start", "rna_end", "protein_start", "protein_end", "runs", "evidence_id"):
        if "{%s}" % k in t:
            sl[k] = {"arg": k, "value": a.get(k)}
    if "{metric_label}" in t:
        sl["metric_label"] = {"text": METRIC_LABEL.get(a.get("metric"), "")}
    if "{query}" in t:
        sl["query"] = {"text": {"structures": "all structures", "excluded": "excluded files", "count": "counts at each stage",
                                "contact": "structures listing contact %s" % a.get("contact")}.get(a.get("query"), "")}
        if a.get("query") == "contact":
            sl["query"] = {"arg": "contact", "value": a.get("contact"), "prefix": "structures listing contact "}
    out = [_st("REASON", t, sl)]
    if rule and rule in RULE_TEXT:
        rs = {}
        for k, v in (rule_slots or {}).items():
            rs[k] = dict(v)
        out.append(_st("REASON", "Why this was suggested (local rule %s): " % rule.replace("L", "L-") + RULE_TEXT[rule], rs,
                       [v.get("evidence_id") for v in rs.values()]))
    return out


# ================================================================ traceability and rendering
SLOT_RE = re.compile(r"\{([a-z_]+)\}")


def _fmt(v):
    if v is None:
        return "not recorded"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return "%.3f" % v
    if isinstance(v, (list, tuple)):
        return ", ".join(_fmt(x) for x in v)
    return str(v)


def _slot_text(s):
    return s.get("prefix", "") + _fmt(s["value"] if "value" in s else s.get("text"))


def fill(st):
    return SLOT_RE.sub(lambda m: _slot_text(st["slots"][m.group(1)]) if m.group(1) in st["slots"] else m.group(0), st["text"])


def allowed_tokens(summary):
    toks = set(ENGINE_TOKENS)
    for r in summary["inventory"]["runs"]:
        toks.add(r["run"])
    for s in summary["inventory"]["structures"]:
        toks.update(x for x in (s["id"], s.get("sample"), s.get("run")) if x)
    toks.discard("")
    return sorted(toks, key=len, reverse=True)


def check_traceable(statements, analysis, args, tool_log, tokens, suggestions=None):
    """-> violations. T0 no statements; T1 a number outside a slot; T2 a slot whose value differs from its source;
    T3 a text slot carrying digits that are not identifiers; T4 an unfilled or unknown slot; T5 a slot without source."""
    v = []
    if not statements:
        return ["T0 no statements"]
    for k, st in enumerate(statements):
        tag = "statement %d (%s)" % (k + 1, st.get("type"))
        names = SLOT_RE.findall(st["text"])
        for n in names:
            if n not in st["slots"]:
                v.append("T4 %s: slot {%s} has no value" % (tag, n))
        for n, s in st["slots"].items():
            try:
                if "evidence_id" in s:
                    ok = resolve(analysis, s["evidence_id"]) == s["value"]
                elif "arg" in s:
                    ok = (args or {}).get(s["arg"]) == s["value"]
                elif "sugg_arg" in s:
                    ok = ((suggestions or [])[s["suggestion"]]["args"].get(s["sugg_arg"]) == s["value"])
                elif "constant" in s:
                    ok = CONSTANTS.get(s["constant"]) == s["value"]
                elif "file" in s:
                    ok = s["file"] == s["value"] and s["file"] is not None and os.path.isfile(os.path.join(analysis, s["file"]))
                elif "log" in s:
                    ok = (tool_log[s["index"]].get(s["log"]) or "") == (s["value"] or "")
                elif "text" in s:
                    bare = str(s["text"])
                    for t in tokens:
                        bare = bare.replace(t, " ")
                    ok = not re.search(r"\d", bare)
                    if not ok:
                        v.append("T3 %s: text slot {%s} carries a number: %r" % (tag, n, s["text"])); continue
                else:
                    v.append("T5 %s: slot {%s} has no source" % (tag, n)); continue
            except Exception as ex:
                ok = False
                v.append("T2 %s: slot {%s} source unreadable (%s)" % (tag, n, type(ex).__name__)); continue
            if not ok:
                v.append("T2 %s: slot {%s} value differs from its source" % (tag, n))
        bare = SLOT_RE.sub(" ", st["text"])
        for t in tokens:
            bare = bare.replace(t, " ")
        bare = re.sub(r"\bL-\d\b", " ", bare)       # rule names L-1..L-7 are identifiers
        d = re.findall(r"[^\s]*\d[^\s]*", bare)
        if d:
            v.append("T1 %s: number(s) outside evidence slots: %s" % (tag, ", ".join(d[:5])))
    return v


#: definitions of the evidence hash; a record states the one it used (records without the field use definition 1)
EVIDENCE_HASH_V1 = "rnplens.followup.evidence.1"
EVIDENCE_HASH_V2 = "rnplens.followup.evidence.2"
EVIDENCE_HASH_VERSION = EVIDENCE_HASH_V2          # written by new follow-ups
_HEX64 = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")


def evidence_hash(statements, tool_log, project, analysis, version=None):
    """Hash of the measured content of the follow-up (run-time fields and absolute roots excluded).

    version None or EVIDENCE_HASH_V1: absolute paths reduced to their last component (definition 1, unchanged).
    EVIDENCE_HASH_V2: in addition, a 64-hex value in a statement slot or tool-log message that is the raw SHA-256 of
    a JSON/text record of the project or analysis is replaced by the hash of that record's canonical projection
    (rnplens.projection; records/replay/PORTABILITY_TEST_v1.md section 3), so the hash does not depend on where the
    project is or when its records were written."""
    if version not in (None, EVIDENCE_HASH_V1, EVIDENCE_HASH_V2):
        raise ValueError("unknown evidence hash definition %r" % version)
    if version == EVIDENCE_HASH_V2:
        from rnplens.projection import location_independent_mapper
        mp = location_independent_mapper(project, analysis)
        f = lambda x: _HEX64.sub(lambda m: mp(m.group(0)), x) if isinstance(x, str) else x
        norm = lambda x: f(_norm(x, project, analysis))
    else:
        norm = lambda x: _norm(x, project, analysis)
    keep = []
    for st in statements:
        keep.append({"type": st["type"], "text": st["text"],
                     "slots": {n: {k: norm(x) for k, x in s.items()} for n, s in sorted(st["slots"].items())},
                     "cites": st["cites"]})
    log = [{"tool": e["tool"], "call": e["call"], "status": e["status"], "outputs": e.get("outputs"),
            "message": norm(e.get("message"))} for e in tool_log]
    return hashlib.sha256(json.dumps({"statements": keep, "tool_log": log}, sort_keys=True, default=str).encode()).hexdigest()


HEAD = {"NOT_AVAILABLE": "Not available here", "REASON": "Follow-up", "OBSERVATION": "Observed in the follow-up", "RECORD": "From the records", "OUTPUT": "Written",
        "LIMITATION": "Limitation", "NOT_RUN": "Not run", "NOTICE": "Note"}


def render(question, initial, chosen, statements, mode_note, violations):
    L = ["# RNPLens follow-up", "", "**Question.** %s" % question, ""]
    if initial:
        L.append("**Initial result.** %s." % ", ".join("%s: %s" % (k, v) for k, v in sorted(initial.items()) if k in ("kind", "capability", "goal")))
    L.append("**Follow-up chosen.** `%s` (%s)." % (chosen, mode_note))
    L.append("")
    if violations:
        L += ["The follow-up answer failed its traceability check, so its statements are not shown; see followup_record.json.", ""]
    else:
        for st in statements:
            cites = (" [%s]" % "; ".join(st["cites"])) if st["cites"] else ""
            L.append("- **%s.** %s%s" % (HEAD.get(st["type"], st["type"]), fill(st), cites))
    L += ["", "_Every number above is inserted from an RNPLens record, an approved argument or a declared constant; "
              "no language-model text is shown. %s_" % LIMIT_TEXT["general"]]
    return "\n".join(L) + "\n"


# ================================================================ the Codex planning call (only with consent)
HERE = os.path.dirname(os.path.abspath(__file__))
ALLOWLIST_TEXT = """- inspect_region_contacts: rna_start, rna_end (construct positions); optional protein_start, protein_end. Lists which residues contact that RNA range, in which structures and runs.
- compare_runs_in_region: rna_start, rna_end, runs (exactly two run names from the summary); optional protein range. Contacts shared by both runs and found only in one.
- explain_unavailable_metric: metric (one of the "unavailable" items of the summary). The recorded reason why it is not available.
- retrieve_contributing_structures: query = structures | excluded | count | contact (with contact = a contact label from the summary). Which structures contributed.
- inspect_existing_comparison: evidence_id (one of the evidence IDs in the summary). How a recorded value was obtained.
- export_table_or_methods: export = methods. A Methods draft and provenance manifest from the execution records.
- none: no further analysis is useful.
Every argument not used by the chosen follow-up must be null."""


def prompt_system():
    with open(os.path.join(HERE, "prompts", "followup.md"), encoding="utf-8") as fh:
        return fh.read()


def prompt_user(question, summary_txt, feedback=None):
    u = ("Question:\n%s\n\nStructured evidence summary (JSON; derived values only, each with its evidence ID):\n%s\n\n"
         "Allowed follow-ups (choose exactly one id, or none):\n%s\n" % (question, summary_txt, ALLOWLIST_TEXT))
    if feedback:
        u += "\n" + feedback
    return u


def _round_used(analysis, qsha):
    for p in glob.glob(os.path.join(analysis, "followup", "fu_*", "followup_record.json")):
        try:
            r = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if r.get("question_sha256") == qsha and (r.get("model_calls_made") or 0) > 0:
            d = os.path.relpath(os.path.dirname(p), analysis)
            return d + (" (interrupted during a model call; recorded as MODEL_CALL_IN_PROGRESS)"
                        if r.get("state") == "MODEL_CALL_IN_PROGRESS" else "")
    return None


def _next_dir(analysis):
    base = os.path.join(analysis, "followup")
    n = 1 + max([int(m.group(1)) for m in (re.match(r"fu_(\d{4})$", d) for d in (os.listdir(base) if os.path.isdir(base) else [])) if m] or [0])
    return os.path.join(base, "fu_%04d" % n)


def _codex_round(rec, summary, sumtxt, question, project, client_factory, session, out, allow_ref, fmap=None, fdir=None):
    """sumtxt is the redacted summary (identifiers only); summary is the local one with real names. The model's
    arguments are mapped back to real names (redact.followup_args_to_real) before the policy sees them."""
    fmap = fmap or redact.Map("followup")
    sysp = prompt_system()
    qtext, rec["question_redactions"] = redact.scrub_user_text(question, None, fmap)   # QA fix #6: paths, case variants
    user = prompt_user(qtext, sumtxt)
    proposals, final = [], None
    client = None
    for attempt in range(1 + LIMITS["max_replans_after_rejection"]):
        if session["model_calls"] >= LIMITS["max_model_calls"]:
            raise Stop("BUDGET", "model-call limit of %d reached" % LIMITS["max_model_calls"])
        payload = sysp + "\n\n---\n\n" + user
        pv_ = privacy_check(payload, project, allow_ref, names=fmap)
        rec["payloads"].append({"attempt": attempt, "sha256": _sha(payload), "bytes": len(payload.encode()), "text": payload,
                                "privacy_violations": pv_})
        if pv_:
            raise Stop("PRIVACY_CHECK", "payload refused by the privacy check: %s" % "; ".join(pv_))
        if client is None:
            client = client_factory()
            rec["model_config"] = dict(getattr(client, "config", {}) or {})
            rec["client_class"] = type(client).__name__
        session["model_calls"] += 1
        rec["model_calls_made"] = session["model_calls"]
        if fdir:   # QA fix (interruption): the round is on disk before the call, so an interrupted round still counts
            pv.atomic_write_json(os.path.join(fdir, "followup_record.json"), dict(rec, state="MODEL_CALL_IN_PROGRESS",
                                                                                  state_utc=_now()))
        try:
            prop = client.structured("followup" if attempt == 0 else "followup_replan", sysp, user, "rnplens_followup", FOLLOWUP_SCHEMA)
        except Exception as ex:
            rec["model_calls"] = list(getattr(client, "calls", []))
            name = type(ex).__name__
            msg = str(ex)
            if name == "UsageGuard":
                raise Stop("USAGE_GUARD", msg)
            if "exceeded" in msg and " s" in msg or name in ("TimeoutExpired", "TimeoutError"):
                raise Stop("TIMEOUT", msg)
            raise Stop("MODEL_UNAVAILABLE", "%s: %s" % (name, msg[:300]))
        rec["model_calls"] = list(getattr(client, "calls", []))
        local = (dict(prop, args=redact.followup_args_to_real(prop["args"], fmap))
                 if isinstance(prop, dict) and isinstance(prop.get("args"), dict) else prop)
        verdict = policy_check(local, summary, question, session)
        proposals.append({"attempt": attempt, "proposal": prop, "proposal_local": local, "verdict": verdict})
        rec["proposals"] = proposals
        if verdict["approved"]:
            final = (local, verdict)
            break
        session["rejected"].append((local.get("follow_up") if isinstance(local, dict) else None,
                                    json.dumps(dict(_blank(), **(local.get("args") or {})) if isinstance(local, dict) and isinstance(local.get("args"), dict) else None, sort_keys=True)))
        shown = ({"follow_up": prop.get("follow_up"), "args": redact.followup_args_to_ids(prop.get("args"), fmap)
                  if isinstance(prop.get("args"), dict) else prop.get("args")} if isinstance(prop, dict) else prop)
        user = prompt_user(qtext, sumtxt, "Your previous proposal:\n%s\nThe RNPLens policy rejected it: %s (%s). "
                           "Return a corrected proposal, or none." % (json.dumps(shown, sort_keys=True), verdict["rule"], fmap.text(verdict["reason"])))
    return final


def run(project, analysis, question, mode="local", initial=None, choice=None, yes=False, ask=None, out=print,
        client_factory=None, agent_status=None, consent_project=None, out_dir=None):
    """One bounded follow-up. mode 'local' (deterministic suggestions) or 'codex' (one planning call with recorded
    consent; local suggestions when anything stops it). Returns the follow-up record (also written to disk)."""
    P, A = os.path.abspath(project), os.path.abspath(analysis)
    cp = os.path.abspath(consent_project or project)
    fdir = os.path.abspath(out_dir) if out_dir else _next_dir(A)
    if os.path.exists(fdir):
        raise FileExistsError("%s exists" % fdir)
    os.makedirs(fdir)
    qsha = _sha(question or "")
    rec = {"schema": SCHEMA, "status": "EXPERIMENTAL", "created_utc": _now(), "question": question, "question_sha256": qsha,
           "mode_requested": mode, "mode": "local", "limits": LIMITS, "constants": CONSTANTS, "allowlist": ALLOWLIST,
           "initial_result": {k: v for k, v in (initial or {}).items() if k in ("kind", "capability", "goal", "requested_capabilities")},
           "consent": None, "consent_record_id": None, "summary": None, "payloads": [], "model_config": None,
           "model_calls": [], "model_calls_made": 0, "proposals": [], "local_suggestions": [], "chosen": None,
           "user_confirmation": None, "tool_log": [], "stop": None, "traceability_violations": [], "wording_audit": []}
    session = {"model_calls": 0, "tool_calls": 0, "rejected": [], "done": set()}
    granted, crec, why = C.status(cp)
    rec["consent"] = {"project": cp, "granted": granted, "detail": why}
    allow_ref = bool(granted and crec and crec.get("allow_reference_derived"))
    if granted:
        rec["consent_record_id"] = crec["id"]
    summary = build_summary(P, A, question, allow_ref and mode == "codex", initial)
    session["all_runs"] = _runs(summary)
    localtxt = summary_text(summary)
    # 0.4 privacy: what may be sent carries identifiers only; the real names and the map stay in this folder
    with open(os.path.join(P, "manifest.json"), encoding="utf-8") as fh:
        fmap = redact.followup_map(summary, json.load(fh))
    sumtxt = summary_text(redact.redact_summary(summary, fmap))
    pv.atomic_write_text(os.path.join(fdir, "evidence_summary.json"), sumtxt)
    pv.atomic_write_text(os.path.join(fdir, "evidence_summary_local.json"), localtxt)
    fmap.write(os.path.join(fdir, "redaction_map.json"), {"summary_local": "evidence_summary_local.json", "summary_sent": "evidence_summary.json"})
    rec["summary"] = {"sha256": _sha(sumtxt), "bytes": len(sumtxt.encode()), "text": sumtxt, "file": "evidence_summary.json",
                      "reference_derived_included": summary["reference_derived"]["included"],
                      "redacted": True, "local_file": "evidence_summary_local.json", "local_sha256": _sha(localtxt),
                      "redaction_map": "redaction_map.json"}
    sugg = []
    for s in suggest_local(summary, question):
        verdict = policy_check({"follow_up": s["id"], "args": s["args"]}, summary, question, {"done": set()})
        rec["local_suggestions"].append(dict(s, verdict={k: verdict[k] for k in ("approved", "rule", "reason")}))
        if verdict["approved"]:
            sugg.append(dict(s, verdict=verdict))
    chosen, core = None, []
    try:
        if mode == "codex":
            if not granted:
                raise Stop("NO_CONSENT", "no current opt-in for follow-up planning in this project (%s); nothing was sent" % why)
            used = _round_used(A, qsha)
            if used:
                raise Stop("ROUND_USED", "the one follow-up planning round for this question was used in %s" % used)
            ready, reasons = (agent_status or _agent_status)()
            if not ready:
                raise Stop("AGENT_NOT_READY", "rnplens doctor --agent is not READY: %s" % "; ".join(reasons))
            if client_factory is None:
                raise Stop("AGENT_NOT_READY", "no model client configured")
            rec["mode"] = "codex"
            final = _codex_round(rec, summary, sumtxt, question, cp, client_factory, session, out, allow_ref, fmap, fdir)
            if final is None:
                raise Stop("REJECTED", "the policy rejected the proposal(s); no follow-up is run")
            prop, verdict = final
            chosen = {"source": "codex", "id": prop["follow_up"], "args": dict(_blank(), **prop["args"]), "verdict": verdict,
                      "rationale_stored_not_shown": prop.get("rationale")}
        else:
            if not sugg:
                chosen = {"source": "local", "id": "none", "args": _blank(), "rule": "L0", "verdict": {"approved": True, "tool_calls": []}}
            else:
                k = choice
                if k is None and ask is not None and not yes:
                    out("Suggested follow-ups (local, no language model):")
                    for i, s in enumerate(sugg, 1):
                        out("  %d  %s" % (i, fill(reason_statement(s["id"], s["args"])[0])))
                    t = ask("follow-up number (Enter to skip): ")
                    k = int(t) if (t or "").strip().isdigit() else 0
                k = 1 if k is None else k
                if not (1 <= k <= len(sugg)):
                    raise Stop("NOT_CONFIRMED", "no follow-up chosen")
                s = sugg[k - 1]
                chosen = {"source": "local", "id": s["id"], "args": s["args"], "rule": s["rule"], "rule_slots": s["reason_slots"], "verdict": s["verdict"]}
        rec["chosen"] = {k: v for k, v in chosen.items() if k != "verdict"}
        rec["chosen"]["policy_verdict"] = {k: chosen["verdict"].get(k) for k in ("approved", "rule", "reason", "tool_calls")}
        reasons = reason_statement(chosen["id"], chosen["args"], chosen.get("rule"), chosen.get("rule_slots"))
        core = list(reasons)
        if chosen["id"] != "none":
            out("Proposed follow-up: %s" % " ".join(fill(x) for x in reasons))
            if yes:
                rec["user_confirmation"] = {"method": "--yes", "answer": "yes", "timestamp_utc": _now()}
            elif ask is not None:
                a = (ask("Run this follow-up? [y/N]: ") or "").strip().lower()
                rec["user_confirmation"] = {"method": "interactive", "answer": a, "timestamp_utc": _now()}
                if a not in ("y", "yes"):
                    raise Stop("NOT_CONFIRMED", "the researcher did not confirm the follow-up")
            else:
                rec["user_confirmation"] = {"method": "none", "answer": None, "timestamp_utc": _now()}
                raise Stop("NOT_CONFIRMED", "not confirmed (non-interactive use needs --yes)")
        results = execute(chosen["verdict"].get("tool_calls") or [], P, A, session, rec["tool_log"])
        core = reasons + statements_for(chosen["id"], chosen["args"], results, A)
        statements = list(core)
        if chosen["id"] == "none":
            statements += _local_notices(sugg)
    except Stop as s:
        rec["stop"] = {"kind": s.kind, "message": s.message, "at_utc": _now()}
        statements = [_st("NOTICE", "The follow-up stopped cleanly: {kind}. {message}",
                          {"kind": {"text": s.kind}, "message": {"text": re.sub(r"\d", "#", s.message)}})]
        statements = core + statements + _local_notices(sugg)
        if chosen is None and rec["mode_requested"] == "codex":
            rec["mode"] = "local (fallback)" if s.kind not in ("REJECTED",) else "codex"
    args_for_check = (chosen or {}).get("args") or {}
    viol = check_traceable(statements, A, args_for_check, rec["tool_log"], allowed_tokens(summary), sugg)
    from rnplens.trace import wording_audit
    text_all = "\n".join(fill(s) for s in statements if s["type"] not in ("LIMITATION", "NOT_AVAILABLE"))
    rec["traceability_violations"], rec["wording_audit"] = viol, wording_audit(text_all)
    _client = rec.get("client_class")
    _by = "Codex" if _client == "CodexClient" else "a scripted test client (%s), not a language model" % (_client or "unknown")
    note = {"codex": "proposed by %s, approved by the RNPLens policy" % _by, "local": "local rule, no language model"}.get(
        (chosen or {}).get("source"), "no follow-up run")
    md = render(question, rec["initial_result"], (chosen or {}).get("id", "none"), statements, note, viol or rec["wording_audit"])
    ehash = evidence_hash(core, rec["tool_log"], P, A, version=EVIDENCE_HASH_VERSION)
    plan = {"schema": "rnplens.followup.plan.1", "question_sha256": qsha, "source": (chosen or {}).get("source"),
            "evidence_hash_version": EVIDENCE_HASH_VERSION,
            "follow_up": (chosen or {}).get("id"), "args": (chosen or {}).get("args"), "rule": (chosen or {}).get("rule"),
            "rule_slots": (chosen or {}).get("rule_slots"), "tool_calls": (chosen or {}).get("verdict", {}).get("tool_calls") or [],
            "executed": bool(rec["tool_log"]), "evidence_sha256": ehash}
    pv.atomic_write_json(os.path.join(fdir, "followup_plan.json"), plan)
    pv.atomic_write_json(os.path.join(fdir, "followup_answer.json"), {"statements": statements, "rendered": [fill(s) for s in statements],
                                                                     "traceability_violations": viol})
    pv.atomic_write_text(os.path.join(fdir, "followup_answer.md"), md)
    rec.update(evidence_sha256=ehash, evidence_hash_version=EVIDENCE_HASH_VERSION, n_tool_calls=session["tool_calls"], outputs={
        "record": "followup_record.json", "plan": "followup_plan.json", "answer": "followup_answer.md", "summary": "evidence_summary.json"},
        dir=os.path.relpath(fdir, A).replace(os.sep, "/"))
    rec["provenance"] = pv.block("followup", [os.path.join(A, "summary.json"), os.path.join(P, "manifest.json")],
                                 "bounded follow-up: deterministic suggestion rules L1-L7 or one Codex planning call with consent; "
                                 "policy rules F1-F9; controlled tools region/explain/export-methods; templated answer",
                                 {"limits": LIMITS, "constants": CONSTANTS, "allowlist": ALLOWLIST, "mode": mode})
    rec["state"] = "COMPLETE"
    pv.atomic_write_json(os.path.join(fdir, "followup_record.json"), rec)
    out(md)
    return rec


def _local_notices(sugg):
    out = []
    for i, x in enumerate(sugg):
        r = reason_statement(x["id"], x["args"])[0]
        sl = {n: ({"suggestion": i, "sugg_arg": v["arg"], "value": v["value"], **({"prefix": v["prefix"]} if "prefix" in v else {})}
                  if "arg" in v else v) for n, v in r["slots"].items()}
        out.append(_st("NOTICE", "Local suggestion (not run): " + r["text"], sl))
    return out


def _agent_status():
    from rnplens import doctor
    return doctor.agent_status()


def replay_plan(plan_path, project, analysis):
    """Re-run a saved follow-up plan without any language model; -> (evidence hash, tool log)."""
    with open(plan_path, encoding="utf-8") as fh:
        plan = json.load(fh)
    P, A = os.path.abspath(project), os.path.abspath(analysis)
    man = json.load(open(os.path.join(P, "manifest.json"), encoding="utf-8"))
    from rnplens import portability as PT       # a replay vouches for the evidence: the recorded files must be usable
    PT.check_manifest(P, man, "read", "replay-followup")
    session = {"model_calls": 0, "tool_calls": 0, "rejected": [], "done": set(), "all_runs": [r["run"] for r in man["runs"]]}
    log = []
    fid, args = plan.get("follow_up"), plan.get("args") or _blank()
    ver = plan.get("evidence_hash_version") or EVIDENCE_HASH_V1     # the definition the record was written under
    if fid is None:
        return evidence_hash([], log, P, A, version=ver), log
    statements = reason_statement(fid, args, plan.get("rule"), plan.get("rule_slots"))
    if plan.get("executed") or fid == "none":
        results = execute(plan["tool_calls"], P, A, session, log)
        statements += statements_for(fid, args, results, A)
    return evidence_hash(statements, log, P, A, version=ver), log


def from_assistant_run(run_dir):
    """(project, analysis, initial) of an R-pipeline run directory (its first analysed project)."""
    run_dir = os.path.abspath(run_dir)
    ans = sorted(glob.glob(os.path.join(run_dir, "tools", "analysis_*", "summary.json")))
    if not ans:
        return None
    a = os.path.dirname(ans[0])
    pid = os.path.basename(a)[len("analysis_"):]
    p = os.path.join(run_dir, "tools", "project_" + pid)
    plan = {}
    if os.path.isfile(os.path.join(run_dir, "plan.json")):
        plan = json.load(open(os.path.join(run_dir, "plan.json"), encoding="utf-8"))
    return p, a, {"kind": "assistant_answer", "goal": plan.get("goal"), "requested_capabilities": plan.get("requested_capabilities") or []}
