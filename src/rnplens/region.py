"""``rnplens region``: contacts in a declared RNA (and optional protein) range, compared between runs.

NOTHING NEW IS COMPUTED ABOUT CONTACTS. The only contact source is Report's own per-structure record
``A/report/contacts_by_output.json`` ("ENGINE|run#sample" -> [[protein_pos, rna_pos], ...], construct numbering),
joined to the project manifest for provenance. This module filters those lists to the requested range and counts,
per run, how many structures list each contact. Residue letters come from the construct FASTA files.

MISSINGNESS. For every compared structure the used structure file is read (gemmi) to check that each RNA position of
the range, and each protein position involved, is present with at least one heavy atom in every copy of the chain
that Report reads. The mapping from file residues to construct positions is accepted only when it is exact: the file
is the one recorded in the manifest (SHA-256), every chain recorded for the polymer has exactly the construct length,
residue i is numbered i (no insertion codes) and carries the construct letter at that position. Otherwise the
structure's coverage is UNRESOLVED and nothing is guessed. A contact that a structure does not list is called
"absent" only where both positions are resolved in that structure; elsewhere it is "not observed".

RUNS. Each run's presence is reported separately (designated structure, then k of n structures). Contacts are
classed as shared by all compared runs, found only in one run (absent, not merely unobserved, in every other run) or
present in some runs. No agreement formula is applied, for two runs or more.

Recurrence among predictions is not evidence of correctness.
"""
import csv
import html as H
import io
import json
import os
import re
import sys

from . import __version__
from . import provenance as pv

KIND = "region_contacts"
SCHEMA = "rnplens-region-1"
DEFINITION = ("Filter of Report's per-structure contact lists (report/contacts_by_output.json, construct numbering) to "
              "the declared RNA range (and protein range, if given); per run, the number of eligible structures listing "
              "each contact, the engine-designated structure shown separately; a contact not listed by a structure is "
              "'absent' only where both positions are resolved in that structure's used file, otherwise 'not observed'.")
RECURRENCE_LIMIT = "Recurrence among predictions is not evidence of correctness."
LIMITS = [
    RECURRENCE_LIMIT,
    "Counts describe how often the supplied predictions list a contact; they are not frequencies in the real complex "
    "and not probabilities that a contact exists.",
    "Predictions from the same model, or from the same run, are not independent; several can share one error.",
    "A contact listed as 'not observed' could not be checked in that structure (unresolved position or inexact "
    "numbering); it is not a negative result.",
    "No agreement score is computed here. Shared and run-specific contacts are listings with explicit counts, not a "
    "measure of how similar the runs are.",
    "This page does not estimate which structure is closest to the experimental complex, binding affinity, or whether "
    "the protein and RNA interact.",
]
NT_STANDARD = {"A", "C", "G", "U", "RA", "RC", "RG", "RU"}
CAPABILITIES = [
    {"id": "region_contacts", "menu": "B", "label": "Contacts in an RNA region (optionally a protein range): which "
     "residues contact it, in which structures and runs", "status": "DESCRIPTIVE",
     "needs": ["project", "analysis", "rna_range", "protein_range?"], "call": "rnplens.region:capability_run",
     "limits": "Counts of predictions that list a contact are descriptive; recurrence among predictions is not "
               "evidence of correctness."},
    {"id": "region_run_comparison", "menu": "C", "label": "Compare runs within an RNA region: contacts shared by all "
     "runs and contacts found only in one run, designated structures and additional samples shown separately",
     "status": "DESCRIPTIVE", "needs": ["project", "analysis", "rna_range", "two_runs"],
     "call": "rnplens.region:capability_run",
     "limits": "Shared and run-specific contacts are listings with counts, not an agreement score; positions not "
               "resolved in a structure are 'not observed', never 'no contact'."},
]


class RegionError(Exception):
    """A refused request (bad range, inconsistent inputs). The message is shown to the researcher."""


# ---------------------------------------------------------------- inputs
def parse_range(text, what, length):
    """'13-23', '13..23' or '20' -> (13, 23), validated against the construct length (1-based, inclusive)."""
    if text is None:
        return None
    t = str(text).strip().replace("..", "-").replace(":", "-")
    m = re.fullmatch(r"(-?\d+)\s*(?:-\s*(-?\d+))?", t)
    if not m:
        raise RegionError("%s range %r is not 'start-end' in construct numbering (for example 13-23)" % (what, text))
    a = int(m.group(1)); b = int(m.group(2)) if m.group(2) is not None else a
    if a > b:
        raise RegionError("%s range %d-%d is reversed: give start <= end (construct numbering, 1-based, inclusive)" % (what, a, b))
    if a < 1 or b > length:
        raise RegionError("%s range %d-%d is outside the declared %s construct (positions 1-%d)" % (what, a, b, what, length))
    return (a, b)


def _fasta(path):
    if not os.path.exists(path):
        raise RegionError("missing construct file %s" % path)
    return "".join(l.strip() for l in open(path, encoding="utf-8") if l.strip() and not l.startswith(">")).upper()


def _load(path, what):
    if not os.path.exists(path):
        raise RegionError("missing %s: %s" % (what, path))
    try:
        return json.load(open(path, encoding="utf-8"))
    except ValueError as ex:
        raise RegionError("%s is not valid JSON (%s): %s" % (what, ex, path))


def load_inputs(project, analysis):
    """Read and cross-check the declared inputs. Nothing else is read (apart from the used structure files)."""
    P = {"manifest": os.path.join(project, "manifest.json"), "protein_fasta": os.path.join(project, "construct_protein.fasta"),
         "rna_fasta": os.path.join(project, "construct_rna.fasta"),
         "contacts": os.path.join(analysis, "report", "contacts_by_output.json"),
         "result": os.path.join(analysis, "report", "result.json"), "summary": os.path.join(analysis, "summary.json"),
         "report_run": os.path.join(analysis, "report", "rnplens_run.json")}
    man = _load(P["manifest"], "project manifest")
    from . import portability as PT                      # recorded structure files: resolved and hash-verified
    man = PT.check_manifest(project, man, "read", "region")[0]
    summ = _load(P["summary"], "analysis summary")
    if summ.get("report", {}).get("status") != "RAN":
        raise RegionError("Report did not produce a result in %s; there are no contact records to filter" % analysis)
    cbo = _load(P["contacts"], "Report contact records")
    rr = _load(P["result"], "Report result")
    ps, rs = _fasta(P["protein_fasta"]), _fasta(P["rna_fasta"])
    c = man.get("construct", {})
    if ps != c.get("protein_sequence") or rs != c.get("rna_sequence"):
        raise RegionError("incompatible constructs: the construct FASTA files of the project differ from the construct "
                          "recorded in manifest.json")
    if summ.get("construct") != {"protein_length": len(ps), "rna_length": len(rs)}:
        raise RegionError("incompatible constructs: the analysis %s was built for construct lengths %s, the project "
                          "declares protein %d / RNA %d" % (analysis, summ.get("construct"), len(ps), len(rs)))
    if summ.get("case_id") != man.get("case_id") or summ.get("inventory", {}).get("counts") != man.get("counts"):
        raise RegionError("the analysis directory %s was not built from this project (case or inventory differs)" % analysis)
    by_exec = {}
    for s in man["structures"]:
        by_exec[(s["engine"], s["execution"])] = s
    sha_of = {(o["engine"], o["execution"]): o.get("sha256") for o in rr.get("per_output", [])}
    for k, cl in cbo.items():
        if "|" not in k:
            raise RegionError("malformed key %r in contacts_by_output.json (expected ENGINE|run#sample)" % k)
        e, x = k.split("|", 1)
        s = by_exec.get((e, x))
        if s is None:
            raise RegionError("contact record %r names no structure of the project manifest" % k)
        if s["verdict"] != "INCLUDED":
            raise RegionError("contact record %r belongs to a structure the project excluded (%s)" % (k, s["verdict"]))
        if sha_of.get((e, x)) not in (None, s["used_sha256"]):
            raise RegionError("Report analysed %s with SHA-256 %s but the manifest records %s" % (k, sha_of[(e, x)], s["used_sha256"]))
        for c_ in cl:
            if not (isinstance(c_, list) and len(c_) == 2 and all(isinstance(v, int) for v in c_)
                    and 1 <= c_[0] <= len(ps) and 1 <= c_[1] <= len(rs)):
                raise RegionError("contact %r of %r is not a pair of construct positions" % (c_, k))
    run_rec = None
    if os.path.exists(P["report_run"]):
        run_rec = _load(P["report_run"], "Report run record")
        want = {o["file"]: o["sha256"] for o in run_rec.get("outputs", [])}
        if "contacts_by_output.json" in want and want["contacts_by_output.json"] != pv.sha256_file(P["contacts"]):
            raise RegionError("report/contacts_by_output.json changed after Report wrote it (SHA-256 differs from "
                              "report/rnplens_run.json)")
    return {"paths": P, "manifest": man, "summary": summ, "contacts": cbo, "result": rr, "protein": ps, "rna": rs,
            "report_run": run_rec}


def run_table(man):
    """[(run_key, engine, run, designated_rule)] in manifest order; run_key is the run name, qualified by the engine
    only when two engines share a run name."""
    rows = man.get("runs", [])
    names = [r["run"] for r in rows]
    out = []
    for r in rows:
        key = r["run"] if names.count(r["run"]) == 1 else "%s:%s" % (r["engine"], r["run"])
        out.append((key, r["engine"], r["run"], r.get("designated_rule")))
    return out


# ---------------------------------------------------------------- coverage (missingness)
def _heavy(res):
    return sum(1 for a in res if a.element.name not in ("H", "D"))


def chain_coverage(st_model, chain_id, kind, seq, positions):
    """-> (mapping_ok, reason, {pos: n_heavy_atoms}, {pos: residue name if non-standard})."""
    from .importer import _one_letter
    ch = next((c for c in st_model if c.name == chain_id), None)
    if ch is None:
        return False, "chain %s recorded in the manifest is not in the used file" % chain_id, {}, {}
    res = [r for r in ch if not r.is_water()]
    if len(res) != len(seq):
        return False, ("chain %s has %d residues in the used file, the %s construct has %d: positions cannot be mapped "
                       "exactly" % (chain_id, len(res), kind, len(seq))), {}, {}
    for i, r in enumerate(res):
        if r.seqid.num != i + 1 or r.seqid.icode.strip():
            return False, ("chain %s residue %d is numbered %s%s, not construct position %d: numbering is not exact"
                           % (chain_id, i + 1, r.seqid.num, r.seqid.icode.strip(), i + 1)), {}, {}
        letter = _one_letter(r.name, "protein" if kind == "protein" else "rna")[0]
        if letter != seq[i]:
            return False, ("chain %s position %d is %s (%s), the construct has %s: sequence does not match"
                           % (chain_id, i + 1, r.name, letter, seq[i])), {}, {}
    heavy = {p: _heavy(res[p - 1]) for p in positions}
    mod = {p: res[p - 1].name for p in positions if kind == "rna" and res[p - 1].name not in NT_STANDARD}
    return True, None, heavy, mod


def structure_coverage(s, rna_seq, prot_seq, rna_positions, prot_positions):
    """Coverage of one manifest structure in its used file. status COMPLETE / PARTIAL / UNRESOLVED."""
    out = {"status": None, "reason": None, "rna_chains": [], "protein_chains": [], "unresolved_rna_positions": [],
           "unresolved_protein_positions": [], "modified_nucleotides": {}, "numbering": None}
    path = s.get("used_path")
    if not path or not os.path.exists(path):
        out.update(status="UNRESOLVED", reason="used structure file not found: %s" % path)
        return out
    if pv.sha256_file(path) != s.get("used_sha256"):
        out.update(status="UNRESOLVED", reason="used structure file changed since import (SHA-256 differs from manifest)")
        return out
    chains = s.get("chains") or []
    rna_ch = [c["chain"] for c in chains if c.get("type_by_report") == "rna" and c.get("status") != "NONPOLYMER_CHAIN"]
    pro_ch = [c["chain"] for c in chains if c.get("type_by_report") == "protein" and c.get("status") != "NONPOLYMER_CHAIN"]
    out["rna_chains"], out["protein_chains"] = rna_ch, pro_ch
    if not rna_ch or not pro_ch:
        out.update(status="UNRESOLVED", reason="the manifest records no protein or no RNA chain for this structure")
        return out
    out["numbering"] = ("derived copy renumbered to construct positions by import (original: %s)" % "; ".join(
        "chain %s %s %s-%s" % (c["chain"], c.get("status"), c.get("numbering", {}).get("first"), c.get("numbering", {}).get("last"))
        for c in chains if c.get("status") != "NONPOLYMER_CHAIN")) if s.get("derived") else "construct numbering in the original file"
    try:
        import gemmi
        st = gemmi.read_structure(path)
        model = st[0]
    except Exception as ex:
        out.update(status="UNRESOLVED", reason="used file could not be read: %s" % str(ex)[:160])
        return out
    unres = {"rna": set(), "protein": set()}
    for kind, ids, seq, pos in (("rna", rna_ch, rna_seq, rna_positions), ("protein", pro_ch, prot_seq, prot_positions)):
        for cid in ids:
            ok, why, heavy, mod = chain_coverage(model, cid, kind, seq, pos)
            if not ok:
                out.update(status="UNRESOLVED", reason=why)
                return out
            unres[kind] |= {p for p, n in heavy.items() if n == 0}
            for p, nm in mod.items():
                out["modified_nucleotides"].setdefault(str(p), sorted(set(out["modified_nucleotides"].get(str(p), [])) | {nm}))
    out["unresolved_rna_positions"] = sorted(unres["rna"])
    out["unresolved_protein_positions"] = sorted(unres["protein"])
    out["status"] = "PARTIAL" if (unres["rna"] or unres["protein"]) else "COMPLETE"
    out["modified_nucleotides"] = dict(sorted(out["modified_nucleotides"].items(), key=lambda kv: int(kv[0])))
    return out


# ---------------------------------------------------------------- the comparison
def out_dirname(rna, prot, runs_selected=None, all_runs=None):
    d = "region_%d-%d" % rna + ("_p%d-%d" % prot if prot else "")
    if runs_selected is not None and all_runs is not None and list(runs_selected) != list(all_runs):
        d += "_runs-" + pv.sha256_json(sorted(runs_selected))[:8]
    return d


def compute(project, analysis, rna_range, protein_range=None, runs=None):
    """Pure computation (no writes). -> (region document, list of TSV rows, map data)."""
    I = load_inputs(project, analysis)
    man, cbo, rr, ps, rs = I["manifest"], I["contacts"], I["result"], I["protein"], I["rna"]
    rna = parse_range(rna_range, "RNA", len(rs))
    if rna is None:
        raise RegionError("an RNA range is required (for example --rna 13-23)")
    prot = parse_range(protein_range, "protein", len(ps))
    table = run_table(man)
    all_keys = [k for k, _, _, _ in table]
    if runs:
        sel = [r.strip() for r in (runs.split(",") if isinstance(runs, str) else runs) if r.strip()]
        unknown = [r for r in sel if r not in all_keys]
        if unknown:
            raise RegionError("unknown run(s) %s; the project's runs are %s" % (", ".join(unknown), ", ".join(all_keys)))
        if len(set(sel)) != len(sel):
            raise RegionError("a run is named twice in the selection")
        sel = [k for k in all_keys if k in sel]
    else:
        sel = list(all_keys)
    dname = out_dirname(rna, prot, sel, all_keys)
    rel = dname + "/region.json"
    per_out = {(o["engine"], o["execution"]): o for o in rr.get("per_output", [])}
    in_rng = lambda p, r: rna[0] <= r <= rna[1] and (prot is None or prot[0] <= p <= prot[1])

    # contacts in range, per structure (the authoritative filter)
    filt = {}
    for k, cl in cbo.items():
        filt[k] = sorted({(p, r) for p, r in cl if in_rng(p, r)})
    keymap = {k: (e, run, rule) for k, e, run, rule in table}

    runs_doc, compared, not_compared_runs = [], [], []
    structs = {}          # cbo key -> structure entry
    for key in sel:
        e, runname, rule = keymap[key]
        members = [s for s in man["structures"] if s["engine"] == e and s["run"] == runname]
        elig, excl = [], []
        for s in members:
            ck = "%s|%s" % (s["engine"], s["execution"])
            if s["verdict"] == "INCLUDED" and ck in cbo:
                elig.append((ck, s))
            else:
                po = per_out.get((s["engine"], s["execution"]))
                why = ("excluded at import: %s (%s)" % (s["verdict"], "; ".join(s.get("reasons") or []))
                       if s["verdict"] != "INCLUDED" else "not eligible in Report: %s" % (po or {}).get("state", "no Report record"))
                excl.append({"id": s["id"], "sample": s["sample"], "designated": bool(s.get("designated")),
                             "path": s.get("path"), "reason": why})
        runs_doc.append({"run": key, "engine": e, "run_name": runname, "designated_rule": rule,
                         "n_structures_in_project": len(members), "n_compared": len(elig), "structures": [],
                         "not_compared": excl})
        if elig:
            compared.append(key)
            for ck, s in elig:
                structs[ck] = (key, s)
        else:
            not_compared_runs.append(key)
    # protein positions whose coverage matters
    in_contacts = sorted({(p, r) for ck in structs for p, r in filt[ck]})
    rna_pos = list(range(rna[0], rna[1] + 1))
    prot_pos = list(range(prot[0], prot[1] + 1)) if prot else sorted({p for p, _ in in_contacts})
    cov = {}
    ri = {d["run"]: i for i, d in enumerate(runs_doc)}
    for ck, (key, s) in sorted(structs.items(), key=lambda kv: kv[1][1]["id"]):
        cv = structure_coverage(s, rs, ps, rna_pos, prot_pos)
        cov[ck] = cv
        d = runs_doc[ri[key]]
        j = len(d["structures"])
        d["structures"].append({"id": s["id"], "engine": s["engine"], "run": s["run"], "sample": s["sample"],
                                "execution": s["execution"], "designated": bool(s.get("designated")),
                                "path": s.get("path"), "used_path": s.get("used_path"), "used_sha256": s.get("used_sha256"),
                                "original_sha256": s.get("original_sha256"), "derived": bool(s.get("derived")),
                                "report_record": "report/contacts_by_output.json#/%s" % ck.replace("~", "~0").replace("/", "~1"),
                                "n_contacts_in_range": len(filt[ck]), "coverage": cv,
                                "evidence_id": pv.evidence_id(rel, "/runs/%d/structures/%d" % (ri[key], j))})
    for d in runs_doc:
        d["structures"].sort(key=lambda x: (not x["designated"], x["id"]))
        for j, x in enumerate(d["structures"]):
            x["evidence_id"] = pv.evidence_id(rel, "/runs/%d/structures/%d" % (ri[d["run"]], j))
        des = [x for x in d["structures"] if x["designated"]]
        d["designated_structure"] = des[0]["id"] if des else None
        dnc = [x for x in d["not_compared"] if x["designated"]]
        d["designated_not_compared"] = dnc[0] if dnc else None
        d["coverage_counts"] = {st: sum(1 for x in d["structures"] if x["coverage"]["status"] == st)
                                for st in ("COMPLETE", "PARTIAL", "UNRESOLVED")}
        d["evidence_id"] = pv.evidence_id(rel, "/runs/%d" % ri[d["run"]])

    def observe(ck, p, r):
        if (p, r) in set(filt[ck]):
            return "PRESENT"
        cv = cov[ck]
        if cv["status"] == "UNRESOLVED" or r in cv["unresolved_rna_positions"] or p in cv["unresolved_protein_positions"]:
            return "NOT_OBSERVED"
        return "ABSENT"

    rows, tsv = [], []
    for i, (p, r) in enumerate(in_contacts):
        per_run, status = {}, {}
        for d in runs_doc:
            if d["run"] not in compared:
                continue
            obs = {x["id"]: observe("%s|%s" % (x["engine"], x["execution"]), p, r) for x in d["structures"]}
            with_ = sorted(sid for sid, o in obs.items() if o == "PRESENT")
            nobs = sorted(sid for sid, o in obs.items() if o == "NOT_OBSERVED")
            add = [x for x in d["structures"] if not x["designated"]]
            dsg = d["designated_structure"] or (d["designated_not_compared"] or {}).get("id")
            k, n = len(with_), len(obs)
            st = "PRESENT" if k else ("NOT_DETERMINED" if nobs else "ABSENT")
            status[d["run"]] = st
            per_run[d["run"]] = {
                "status": st,
                "designated": {"structure": dsg,
                               "observation": (obs[dsg] if dsg in obs else "NOT_COMPARED") if dsg else None,
                               "sample": next((x["sample"] for x in d["structures"] + d["not_compared"] if x["id"] == dsg), None)},
                "structures": {"count": k, "of": n, "not_observed": len(nobs), "observable": n - len(nobs),
                               "with_contact": [{"id": sid, "sample": next(x["sample"] for x in d["structures"] if x["id"] == sid)} for sid in with_],
                               "not_observed_in": nobs},
                "additional_samples": {"count": sum(1 for x in add if obs[x["id"]] == "PRESENT"), "of": len(add),
                                       "not_observed": sum(1 for x in add if obs[x["id"]] == "NOT_OBSERVED")}}
        present = [k_ for k_ in compared if status[k_] == "PRESENT"]
        if len(present) == len(compared):
            cls, only = "SHARED_BY_ALL_RUNS", None
        elif len(present) == 1 and all(status[k_] == "ABSENT" for k_ in compared if k_ != present[0]):
            cls, only = "ONLY_IN_ONE_RUN", present[0]
        else:
            cls, only = "PRESENT_IN_SOME_RUNS", None
        lab_p, lab_r = "%s%d" % (ps[p - 1], p), "%s%d" % (rs[r - 1], r)
        ev = pv.evidence_id(rel, "/contacts/%d" % i)
        rows.append({"protein_position": p, "protein_residue": ps[p - 1], "rna_position": r, "rna_nucleotide": rs[r - 1],
                     "protein_label": lab_p, "rna_label": lab_r, "label": "%s-%s" % (lab_p, lab_r),
                     "presence": cls, "only_in_run": only,
                     "runs": {"present": present, "absent": [k_ for k_ in compared if status[k_] == "ABSENT"],
                              "not_determined": [k_ for k_ in compared if status[k_] == "NOT_DETERMINED"],
                              "count_present": len(present), "of": len(compared)},
                     "per_run": per_run, "evidence_id": ev})
        for d in runs_doc:
            if d["run"] in per_run:
                v = per_run[d["run"]]
                tsv.append([lab_p, p, ps[p - 1], lab_r, r, rs[r - 1], cls, only or "", d["run"], d["engine"],
                            v["designated"]["structure"] or "", v["designated"]["sample"] or "",
                            (v["designated"]["observation"] or "").lower(), v["structures"]["count"], v["structures"]["of"],
                            v["structures"]["not_observed"], v["additional_samples"]["count"], v["additional_samples"]["of"],
                            " ".join("%s:%s" % (w["id"], w["sample"]) for w in v["structures"]["with_contact"]),
                            " ".join(v["structures"]["not_observed_in"]), ev])

    S = _summary(rows, runs_doc, compared, not_compared_runs, sel, all_keys, rel, rna, prot, rs, ps)
    doc = {"schema": SCHEMA,
           "region": {"rna": {"start": rna[0], "end": rna[1], "length": rna[1] - rna[0] + 1,
                              "sequence": rs[rna[0] - 1:rna[1]], "label": "RNA %d-%d" % rna},
                      "protein": ({"start": prot[0], "end": prot[1], "length": prot[1] - prot[0] + 1,
                                   "sequence": ps[prot[0] - 1:prot[1]], "label": "protein %d-%d" % prot} if prot else None),
                      "numbering": "construct numbering, 1-based, inclusive (positions of construct_protein.fasta and "
                                   "construct_rna.fasta)",
                      "construct": {"protein_length": len(ps), "rna_length": len(rs)},
                      "case_id": man.get("case_id"), "output_dir": dname,
                      "evidence_id": pv.evidence_id(rel, "/region")},
           "contact_definition": {"text": I["summary"]["contacts"]["definition"], "source": "summary.json",
                                  "pointer": "/contacts/definition",
                                  "evidence_id": pv.evidence_id("summary.json", "/contacts/definition"),
                                  "filter": DEFINITION},
           "runs": runs_doc, "contacts": rows, "summary": S, "limits": list(LIMITS)}
    used = sorted({x["used_path"] for d in runs_doc for x in d["structures"] if x["used_path"] and os.path.exists(x["used_path"])})
    inputs = [I["paths"][k] for k in ("manifest", "protein_fasta", "rna_fasta", "contacts", "result", "summary")]
    inputs += ([I["paths"]["report_run"]] if I["report_run"] else []) + used
    doc["provenance"] = pv.block(KIND, inputs, DEFINITION,
                                 {"rna_range": list(rna), "protein_range": list(prot) if prot else None, "runs": sel},
                                 extra={"project": os.path.abspath(project), "analysis": os.path.abspath(analysis),
                                        "command": ["rnplens", "region", os.path.abspath(project), os.path.abspath(analysis),
                                                    "--rna", "%d-%d" % rna] + (["--protein", "%d-%d" % prot] if prot else [])
                                                   + (["--runs", ",".join(sel)] if sel != all_keys else [])})
    mapdata = {"cbo": cbo, "structs": structs, "runs_doc": runs_doc, "compared": compared, "protein_seq": ps}
    return doc, tsv, mapdata


def _summary(rows, runs_doc, compared, not_compared_runs, sel, all_keys, rel, rna, prot, rs, ps):
    ev = lambda ptr: pv.evidence_id(rel, "/summary/" + ptr)
    labs = lambda f: [r["label"] for r in rows if f(r)]
    S = {"runs_selected": sel, "runs_in_project": all_keys, "runs_compared": compared,
         "runs_without_compared_structures": not_compared_runs,
         "n_runs_compared": len(compared),
         "n_structures_compared": sum(len(d["structures"]) for d in runs_doc),
         "comparison_mode": ("one run: per-run listing only" if len(compared) == 1 else
                             "two runs: shared and run-specific contacts (no agreement formula)" if len(compared) == 2 else
                             "%d runs: per-run presence, shared by all runs / present in some runs, with counts "
                             "(no agreement formula)" % len(compared))}
    S["n_contacts_in_range"] = {"count": len(rows), "evidence_id": ev("n_contacts_in_range")}
    S["status"] = "NO_CONTACTS_IN_RANGE" if not rows else "CONTACTS_LISTED"
    if not compared:
        S["status"] = "NO_COMPARED_STRUCTURE"
    S["shared_by_all_runs"] = {"count": len(labs(lambda r: r["presence"] == "SHARED_BY_ALL_RUNS")),
                               "of_runs": len(compared), "contacts": labs(lambda r: r["presence"] == "SHARED_BY_ALL_RUNS"),
                               "evidence_id": ev("shared_by_all_runs")}
    S["only_in_run"] = {k: {"count": len(labs(lambda r, k=k: r["only_in_run"] == k)),
                            "contacts": labs(lambda r, k=k: r["only_in_run"] == k),
                            "evidence_id": ev("only_in_run/%s" % k.replace("~", "~0").replace("/", "~1"))} for k in compared}
    S["present_in_some_runs"] = {"count": len(labs(lambda r: r["presence"] == "PRESENT_IN_SOME_RUNS")),
                                 "contacts": labs(lambda r: r["presence"] == "PRESENT_IN_SOME_RUNS"),
                                 "evidence_id": ev("present_in_some_runs")}
    S["present_in_j_runs"] = {"counts": {str(j): sum(1 for r in rows if r["runs"]["count_present"] == j)
                                         for j in range(1, len(compared) + 1)}, "of_runs": len(compared),
                              "evidence_id": ev("present_in_j_runs")}
    S["not_determined"] = {"count": sum(1 for r in rows if r["runs"]["not_determined"]),
                           "contacts": labs(lambda r: bool(r["runs"]["not_determined"])),
                           "note": "contacts that are not listed by some run and could not be checked in at least one of "
                                   "its structures (unresolved position or inexact numbering)",
                           "evidence_id": ev("not_determined")}
    per = {}
    for d in runs_doc:
        if d["run"] not in compared:
            continue
        k = d["run"]
        per[k] = {"n_structures": len(d["structures"]), "designated_structure": d["designated_structure"],
                  "designated_not_compared": (d.get("designated_not_compared") or {}).get("id"),
                  "designated_rule": d["designated_rule"],
                  "contacts_present": sum(1 for r in rows if r["per_run"][k]["status"] == "PRESENT"),
                  "contacts_in_designated": (sum(1 for r in rows if r["per_run"][k]["designated"]["observation"] == "PRESENT")
                                             if d["designated_structure"] else None),
                  "coverage": d["coverage_counts"],
                  "evidence_id": ev("per_run/%s" % k.replace("~", "~0").replace("/", "~1"))}
    S["per_run"] = per
    S["evidence_id"] = pv.evidence_id(rel, "/summary")
    return S


# ---------------------------------------------------------------- outputs
TSV_HEAD = ["protein", "protein_position", "protein_residue", "rna", "rna_position", "rna_nucleotide", "presence",
            "only_in_run", "run", "engine", "designated_structure", "designated_sample", "designated_observation",
            "structures_with_contact", "structures_compared", "structures_not_observed", "additional_samples_with_contact",
            "additional_samples", "with_contact_id_sample", "not_observed_ids", "evidence_id"]


def render_tsv(tsv):
    b = io.StringIO()
    w = csv.writer(b, delimiter="\t", lineterminator="\n")
    w.writerow(TSV_HEAD)
    w.writerows(tsv)
    return b.getvalue()


def region_map_png(doc, mapdata, seq):
    """Protein-by-RNA contact map per compared run (fraction of the run's structures listing the contact), full
    construct, with the declared range outlined. -> PNG bytes; None if matplotlib is absent (optional, as in
    summary.py); False if no structure was compared."""
    try:
        import matplotlib
    except ImportError:
        return None
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.patches import Rectangle
    cbo, structs, compared = mapdata["cbo"], mapdata["structs"], mapdata["compared"]
    L = doc["region"]["construct"]["rna_length"]
    pp = sorted({p for ck in structs for p, _ in cbo[ck]})
    if not compared:
        return False
    R = doc["region"]
    fig, axs = plt.subplots(len(compared), 1, figsize=(min(4 + 0.12 * L, 14), (1.4 + 0.16 * max(len(pp), 3)) * len(compared)),
                            squeeze=False)
    im = None
    for ax, key in zip(axs[:, 0], compared):
        cks = sorted(ck for ck, (k, _) in structs.items() if k == key)
        M = np.full((max(len(pp), 1), L), np.nan)
        for ck in cks:
            for p, r in cbo[ck]:
                i = pp.index(p)
                M[i, r - 1] = (0 if np.isnan(M[i, r - 1]) else M[i, r - 1]) + 1.0 / len(cks)
        im = ax.imshow(M, aspect="auto", cmap="viridis", vmin=0, vmax=1, interpolation="nearest", zorder=1)
        a, b = R["rna"]["start"], R["rna"]["end"]
        ax.axvspan(a - 1.5, b - 0.5, color="#e0a020", alpha=0.18, lw=0, zorder=0)
        if R["protein"]:
            rows_in = [i for i, p in enumerate(pp) if R["protein"]["start"] <= p <= R["protein"]["end"]]
            if rows_in:
                ax.add_patch(Rectangle((a - 1.5, min(rows_in) - 0.5), b - a + 1, max(rows_in) - min(rows_in) + 1,
                                       fill=False, ec="#c03000", lw=1.6))
        else:
            ax.add_patch(Rectangle((a - 1.5, -0.5), b - a + 1, max(len(pp), 1), fill=False, ec="#c03000", lw=1.6))
        ax.set_yticks(range(len(pp)))
        ax.set_yticklabels(["%s%d" % (seq[p - 1], p) for p in pp], fontsize=6 if len(pp) > 30 else 7)
        step = max(1, L // 15)
        ax.set_xticks(range(0, L, step)); ax.set_xticklabels([str(i + 1) for i in range(0, L, step)], fontsize=7)
        ax.set_xlabel("RNA position (construct numbering)")
        ax.set_title("run %s: %d structure(s); outlined: %s%s" % (key, len(cks), R["rna"]["label"],
                     (", " + R["protein"]["label"]) if R["protein"] else ""), fontsize=9)
    fig.subplots_adjust(hspace=0.38)
    fig.colorbar(im, ax=axs[:, 0].tolist(), shrink=0.8, label="fraction of the run's structures listing the contact")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)
    return buf.getvalue()


CSS = ("body{font-family:Helvetica,Arial,sans-serif;max-width:1100px;margin:24px auto;color:#222;line-height:1.4}"
       "table{border-collapse:collapse;margin:8px 0 16px;font-size:13px}td,th{border:1px solid #ccc;padding:3px 7px;text-align:left}"
       "th{background:#f1f1f1}.lim{background:#fff6e5;border-left:4px solid #e0a020;padding:6px 12px}.na{color:#8a3b00}"
       "code{font-size:12px}")


def _table(head, rows):
    h = "<tr>" + "".join("<th>%s</th>" % H.escape(str(x)) for x in head) + "</tr>"
    b = "".join("<tr>" + "".join("<td>%s</td>" % H.escape("" if x is None else str(x)) for x in r) + "</tr>" for r in rows)
    return "<table>%s%s</table>" % (h, b)


def _obs_word(o):
    return {"PRESENT": "yes", "ABSENT": "no", "NOT_OBSERVED": "not observed", "NOT_COMPARED": "designated structure not compared",
            None: "no designated structure"}[o]


def render_html(doc, figure_state):
    R, S = doc["region"], doc["summary"]
    lab = R["rna"]["label"] + ((" and " + R["protein"]["label"]) if R["protein"] else "")
    p = ["<!doctype html><html><head><meta charset='utf-8'><title>RNPLens region %s: %s</title><style>%s</style></head><body>"
         % (H.escape(lab), H.escape(str(R["case_id"])), CSS)]
    p.append("<h1>Contacts in %s (%s)</h1>" % (H.escape(lab), H.escape(str(R["case_id"]))))
    p.append("<p>RNPLens %s. Filtered from Report's own per-structure contact lists; nothing about the structures "
             "is recomputed. Numbering: %s. RNA %d-%d reads <code>%s</code>.%s</p>" % (
                 H.escape(doc["provenance"]["rnplens_version"]), H.escape(R["numbering"]), R["rna"]["start"], R["rna"]["end"],
                 H.escape(R["rna"]["sequence"]), (" Protein %d-%d reads <code>%s</code>." % (R["protein"]["start"], R["protein"]["end"],
                                                                                        H.escape(R["protein"]["sequence"]))) if R["protein"] else ""))
    p.append("<p><b>Contact definition</b> (summary.json, verbatim): %s</p>" % H.escape(doc["contact_definition"]["text"]))
    p.append("<p>%s</p>" % H.escape(S["comparison_mode"]))
    p.append("<h2>1. Structures compared</h2>")
    rows = []
    for d in doc["runs"]:
        for x in d["structures"]:
            cv = x["coverage"]
            covtxt = cv["status"] + ((": " + cv["reason"]) if cv.get("reason") else "") + (
                (" (unresolved RNA %s)" % ",".join(map(str, cv["unresolved_rna_positions"]))) if cv["unresolved_rna_positions"] else "") + (
                (" (unresolved protein %s)" % ",".join(map(str, cv["unresolved_protein_positions"]))) if cv["unresolved_protein_positions"] else "")
            mods = ", ".join("%s:%s" % (k, "/".join(v)) for k, v in cv.get("modified_nucleotides", {}).items())
            rows.append([x["id"], d["run"], x["engine"], x["sample"], "yes" if x["designated"] else "no",
                         x["used_sha256"][:16] + "...", x["n_contacts_in_range"], covtxt, mods or "none"])
    p.append(_table(["structure", "run", "engine", "sample", "engine-designated", "used file SHA-256", "contacts in range",
                     "coverage of the range", "modified nucleotides in range"], rows))
    for d in doc["runs"]:
        dn = d.get("designated_not_compared")
        p.append("<p>Run %s (%s): %d structure(s) compared; engine-designated structure: %s (rule: %s).</p>" % (
            H.escape(d["run"]), H.escape(d["engine"]), d["n_compared"],
            H.escape(d["designated_structure"] or ("%s, not compared: %s" % (dn["id"], dn["reason"]) if dn else "none determinable")),
            H.escape(str(d["designated_rule"]))))
        if d["not_compared"]:
            p.append("<p class='na'>Not compared in run %s: %s</p>" % (H.escape(d["run"]), H.escape("; ".join(
                "%s (%s): %s" % (x["id"], x["sample"], x["reason"]) for x in d["not_compared"]))))
    if S["runs_without_compared_structures"]:
        p.append("<p class='na'>Runs with no structure that Report could use: %s.</p>" % H.escape(", ".join(S["runs_without_compared_structures"])))
    p.append("<h2>2. Overview</h2>")
    if S["status"] == "NO_CONTACTS_IN_RANGE":
        p.append("<p>No contact in %s is listed by any of the %d compared structure(s).</p>" % (H.escape(lab), S["n_structures_compared"]))
    ov = [["contacts in range (any compared structure)", S["n_contacts_in_range"]["count"]],
          ["shared by all %d compared run(s)" % S["n_runs_compared"], S["shared_by_all_runs"]["count"]]]
    for k, v in S["only_in_run"].items():
        ov.append(["found only in run %s" % k, v["count"]])
    ov.append(["present in some runs (not all)", S["present_in_some_runs"]["count"]])
    for j, n in S["present_in_j_runs"]["counts"].items():
        ov.append(["present in exactly %s of %d runs" % (j, S["n_runs_compared"]), n])
    ov.append(["not determined in at least one run (unresolved positions)", S["not_determined"]["count"]])
    p.append(_table(["contacts", "count"], ov))
    p.append("<p>A contact is present in a run when at least one of the run's compared structures lists it. "
             "'Found only in run X' means listed in run X and absent (both positions resolved, contact not listed) in "
             "every structure of every other run.</p>")

    def block(title, sel):
        rs_ = [r for r in doc["contacts"] if sel(r)]
        if not rs_:
            return "<h3>%s</h3><p>none</p>" % H.escape(title)
        head = ["contact"] + sum([["%s designated" % k, "%s structures (k/n)" % k, "%s additional samples (k/n)" % k]
                                  for k in S["runs_compared"]], [])
        body = []
        for r in rs_:
            row = [r["label"]]
            for k in S["runs_compared"]:
                v = r["per_run"][k]
                row += [_obs_word(v["designated"]["observation"]),
                        "%d/%d%s" % (v["structures"]["count"], v["structures"]["of"],
                                     (" (%d not observed)" % v["structures"]["not_observed"]) if v["structures"]["not_observed"] else ""),
                        "%d/%d" % (v["additional_samples"]["count"], v["additional_samples"]["of"]) if v["additional_samples"]["of"] else "none"]
            body.append(row)
        return "<h3>%s (%d)</h3>%s" % (H.escape(title), len(rs_), _table(head, body))
    p.append("<h2>3. Contacts by run</h2>")
    p.append(block("Shared by all compared runs", lambda r: r["presence"] == "SHARED_BY_ALL_RUNS"))
    for k in S["runs_compared"]:
        if len(S["runs_compared"]) > 1:
            p.append(block("Found only in run %s" % k, lambda r, k=k: r["only_in_run"] == k))
    if len(S["runs_compared"]) > 1:
        p.append(block("Present in some runs", lambda r: r["presence"] == "PRESENT_IN_SOME_RUNS"))
    p.append("<h2>4. Contact map</h2>")
    if figure_state:
        p.append("<img src='region_map.png' style='max-width:100%' alt='protein-by-RNA contact map with the range outlined'>")
    elif figure_state is None:
        p.append("<p>Contact map image not drawn: matplotlib is not installed (pip install 'rnplens[html]'). All counts "
                 "above are unaffected.</p>")
    else:
        p.append("<p>Contact map image not drawn: no compared structure.</p>")
    p.append("<p>Files: region.json (every row carries an evidence ID), region_contacts.tsv (one row per contact and "
             "run, with structure and sample identifiers).</p>")
    p.append("<h2>What this page does not establish</h2><div class='lim'><ul>%s</ul></div>" % "".join(
        "<li>%s</li>" % H.escape(x) for x in doc["limits"]))
    p.append("</body></html>")
    return "\n".join(p) + "\n"


def render_text(doc):
    R, S = doc["region"], doc["summary"]
    lab = R["rna"]["label"] + ((" and " + R["protein"]["label"]) if R["protein"] else "")
    L = ["rnplens region: %s; %d run(s) compared (%s); %d structure(s)" % (lab, S["n_runs_compared"], ", ".join(S["runs_compared"]),
                                                                          S["n_structures_compared"]),
         "  contacts in range: %d; shared by all runs: %d; present in some runs: %d; not determined somewhere: %d" % (
             S["n_contacts_in_range"]["count"], S["shared_by_all_runs"]["count"], S["present_in_some_runs"]["count"],
             S["not_determined"]["count"])]
    for k, v in S["only_in_run"].items():
        L.append("  found only in run %s: %d%s" % (k, v["count"], (" (" + ", ".join(v["contacts"]) + ")") if v["contacts"] else ""))
    if S["shared_by_all_runs"]["contacts"]:
        L.append("  shared by all runs: " + ", ".join(S["shared_by_all_runs"]["contacts"]))
    L.append("  " + RECURRENCE_LIMIT)
    return "\n".join(L)


def _reusable(region_json):
    """An existing result is reused only if every input file it records still has the recorded sha256 and it was
    written by this RNPLens version (the output directory name already fixes the range and run selection)."""
    try:
        d = json.load(open(region_json))
        prov = d["provenance"]
        if prov.get("rnplens_version") != __version__:
            return False
        from . import portability as PT     # in a moved/copied project the recorded paths resolve, hash-verified
        for i in prov.get("inputs", []):
            if not PT.file_verified(i["path"], i["sha256"], os.path.dirname(region_json)):
                return False
        return True
    except Exception:
        return False


def run(project, analysis, rna_range, protein_range=None, runs=None, replace=False):
    """Compute and write A/region_<a>-<b>[_p<c>-<d>]/. -> (exit code, outdir or message)."""
    from .trace import wording_audit
    doc, tsv, mapdata = compute(project, analysis, rna_range, protein_range, runs)
    out = os.path.join(analysis, doc["region"]["output_dir"])
    if os.path.exists(os.path.join(out, "region.json")) and not replace:
        if _reusable(os.path.join(out, "region.json")):
            print("rnplens region: existing result reused (recorded inputs unchanged): %s" % os.path.abspath(out))
            return 0, out
        raise RegionError("%s exists (nothing is overwritten; pass --replace to write it again)" % out)
    png = os.path.join(out, "region_map.png")
    img = region_map_png(doc, mapdata, mapdata["protein_seq"]) if mapdata["compared"] else False
    fig = True if img else img
    doc["figure"] = {"file": "region_map.png" if fig else None,
                     "state": {True: "DRAWN", None: "NOT_DRAWN_MATPLOTLIB_MISSING", False: "NOT_DRAWN_NO_STRUCTURE"}[fig]}
    html = render_html(doc, fig)
    bad = wording_audit(html) + wording_audit(render_text(doc))
    os.makedirs(out, exist_ok=True)
    if bad:
        pv.atomic_write_text(os.path.join(out, "WORDING_AUDIT_FAILED.txt"), "\n".join(bad) + "\n")
        return 1, "wording audit failed; see %s" % os.path.join(out, "WORDING_AUDIT_FAILED.txt")
    if fig:
        pv.atomic_write_bytes(png, img)
    elif os.path.exists(png):
        os.unlink(png)
    pv.atomic_write_json(os.path.join(out, "region.json"), doc)
    pv.atomic_write_text(os.path.join(out, "region_contacts.tsv"), render_tsv(tsv))
    pv.atomic_write_text(os.path.join(out, "region.html"), html)
    return 0, out


def _range_text(r):
    if r is None or isinstance(r, str):
        return r
    if isinstance(r, (list, tuple)) and len(r) == 2:
        return "%d-%d" % (int(r[0]), int(r[1]))
    return r


def capability_run(project, analysis, rna_range, protein_range=None, runs=None, replace=False, **_):
    """Capability entry point (menu B and C). -> {"status", "outputs", "summary", "message"}."""
    rna_range, protein_range = _range_text(rna_range), _range_text(protein_range)
    if isinstance(runs, (list, tuple)):
        runs = ",".join(runs)
    try:
        code, out = run(project, analysis, rna_range, protein_range, runs, replace)
    except RegionError as ex:
        return {"status": "REFUSED", "outputs": [], "message": str(ex)}
    if code != 0:
        return {"status": "FAILED", "outputs": [], "message": out}
    doc = json.load(open(os.path.join(out, "region.json"), encoding="utf-8"))
    files = [os.path.join(out, f) for f in ("region.json", "region_contacts.tsv", "region.html", "region_map.png")
             if os.path.exists(os.path.join(out, f))]
    return {"status": "OK", "outputs": files, "summary": doc["summary"], "message": render_text(doc),
            "limits": CAPABILITIES[0]["limits"]}


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="rnplens region", description="Contacts in a declared RNA (and optional protein) "
                                 "range, from Report's own per-structure contact lists: shared by all runs, found only in "
                                 "one run, designated structures and additional samples shown separately, with provenance. "
                                 "Writes ANALYSIS/region_<a>-<b>[_p<c>-<d>]/.")
    ap.add_argument("project", help="project directory written by 'rnplens import'")
    ap.add_argument("analysis", help="analysis directory written by 'rnplens analyse' for that project")
    ap.add_argument("--rna", required=True, help="RNA range in construct numbering, 1-based inclusive (e.g. 13-23)")
    ap.add_argument("--protein", help="optional protein range in construct numbering (e.g. 10-50)")
    ap.add_argument("--runs", help="comma-separated run names to compare (default: all runs of the project)")
    ap.add_argument("--replace", action="store_true", help="write again over an existing region directory")
    a = ap.parse_args(argv)
    try:
        code, out = run(a.project, a.analysis, a.rna, a.protein, a.runs, a.replace)
    except RegionError as ex:
        print("rnplens region: refused: %s" % ex, file=sys.stderr)
        return 2
    if code != 0:
        print("rnplens region: %s" % out, file=sys.stderr)
        return code
    doc = json.load(open(os.path.join(out, "region.json"), encoding="utf-8"))
    print(render_text(doc))
    print("  output folder: %s" % os.path.abspath(out))
    return 0
