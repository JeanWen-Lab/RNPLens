"""Acceptance checks for an analysis summary: every displayed number must be re-derivable from a module output
file, and the generated text must not describe agreement as correctness. Both run before a summary is written."""
import json
import math
import os
import re


def _eq(a, b):
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and math.isclose(a, b, rel_tol=0, abs_tol=0)
    return a == b


def verify(S, man, out):
    bad = []
    if S["inventory"]["counts"] != man["counts"]:
        bad.append("inventory counts differ from manifest.json")
    R = S.get("report", {})
    if R.get("status") == "RAN":
        rr = json.load(open(os.path.join(out, "report", "result.json")))
        cbo = json.load(open(os.path.join(out, "report", "contacts_by_output.json")))
        ids = {(s["engine"], s["execution"]): s["id"] for s in man["structures"]}
        elig = [o for o in rr["per_output"] if o["state"] == "ELIGIBLE"]
        den = {}
        for o in elig:
            den[o["engine"]] = den.get(o["engine"], 0) + 1
        if den != S["contacts"]["denominators"]:
            bad.append("denominators %s differ from Report's eligible structures %s" % (S["contacts"]["denominators"], den))
        listing = {}
        for k, cl in cbo.items():
            e, x = k.split("|", 1)
            for c in cl:
                listing.setdefault(tuple(c), {}).setdefault(e, set()).add(ids[(e, x)])
        shown = {(r["protein_position"], r["rna_position"]): r for r in S["contacts"]["rows"]}
        if set(shown) != set(listing):
            bad.append("contacts shown (%d) differ from contacts in Report's lists (%d)" % (len(shown), len(listing)))
        if set("%d,%d" % k for k in listing) != set(rr["contact_support"]):
            bad.append("Report's contact lists and contact_support name different contacts")
        for key, r in shown.items():
            sup = rr["contact_support"].get("%d,%d" % key)
            if not _eq(r["report_contact_support"], sup):
                bad.append("contact %s: shown support %s, Report %s" % (key, r["report_contact_support"], sup))
            for e, v in r["per_engine"].items():
                truth = listing.get(key, {}).get(e, set())
                if v["count"] != len(truth) or set(v["structures"]) != truth or v["of"] != den.get(e):
                    bad.append("contact %s engine %s: shown %d/%d, Report lists %d/%s" % (key, e, v["count"], v["of"], len(truth), den.get(e)))
            w = round(sum(v["count"] / v["of"] for v in r["per_engine"].values() if v["of"]), 6)
            if not math.isclose(w, sup, abs_tol=1e-6):
                bad.append("contact %s: engine-weighted count %s does not reproduce Report's contact_support %s" % (key, w, sup))
        for kind, idx in (("protein_positions", 0), ("rna_positions", 1)):
            truth = {}
            for k, cl in cbo.items():
                e, x = k.split("|", 1)
                for p in {c[idx] for c in cl}:
                    truth.setdefault(p, {}).setdefault(e, set()).add(ids[(e, x)])
            for r in S[kind]["rows"]:
                for e, v in r["per_engine"].items():
                    if set(v["structures"]) != truth.get(r["position"], {}).get(e, set()) or v["count"] != len(v["structures"]):
                        bad.append("%s %d engine %s does not match Report's lists" % (kind, r["position"], e))
            if {r["position"] for r in S[kind]["rows"]} != set(truth):
                bad.append("%s: positions shown differ from Report's lists" % kind)
        for e, v in S["repeat_agreement"].items():
            src = rr["summary"]["repeat_agreement"].get(e)
            if v["status"] == "COMPUTED_BY_REPORT":
                for f in ("surface_agreement", "register_agreement", "rna_pose_difference_A"):
                    if not _eq(v[f], src[f]):
                        bad.append("repeat agreement %s.%s differs from Report" % (e, f))
            elif src is not None:
                bad.append("repeat agreement for %s shown as not computed although Report computed it" % e)
            elif v.get("n_structures") == 2:
                bad.append("repeat agreement for %s: two structures but Report computed none" % e)
    for d in S["diagnose"]:
        if d["status"] == "RAN":
            src = json.load(open(os.path.join(out, d["source"])))
            want = [{k: v for k, v in x.items() if k != "evidence"} for x in src["diagnosis"].get("statements", [])]
            if want != d["statements"] or src["validity"] != d["validity"]:
                bad.append("Diagnose %s %s differs from %s" % (d["mode"], d["engine"], d["source"]))
    for e, v in (S.get("run_repeat_agreement") or {}).items():
        if v["status"] == "COMPUTED_BY_REPORT":
            path, key = v["source"].split(":", 1)
            src = json.load(open(os.path.join(out, path)))["summary"]["repeat_agreement"].get(e)
            for f in ("surface_agreement", "register_agreement", "rna_pose_difference_A"):
                if src is None or not _eq(v[f], src[f]):
                    bad.append("run repeat agreement %s.%s differs from %s" % (e, f, v["source"]))
            ids = {s["id"]: s for s in man["structures"]}
            if any(not ids.get(x, {}).get("designated") for x in v["structures"]) or len({ids[x]["run"] for x in v["structures"]}) != 2:
                bad.append("run repeat agreement %s: structures are not the designated structures of two runs" % e)
    for e in S["evaluate"]:
        if e.get("source"):
            src = json.load(open(os.path.join(out, e["source"])))
            pi = src["dockq"].get("per_interface") or {}
            pairs = [("dockq", src["dockq"].get("dockq")), ("dockq_status", src["dockq"]["status"]),
                     ("fnat_per_interface", {k: x.get("fnat") for k, x in pi.items()} or None),
                     ("irmsd_per_interface", {k: x.get("iRMSD") for k, x in pi.items()} or None),
                     ("lrmsd_per_interface", {k: x.get("LRMSD") for k, x in pi.items()} or None)]
            for f, v in pairs:
                if not _eq(e.get(f), v):
                    bad.append("Evaluate %s.%s differs from %s" % (e["structure"], f, e["source"]))
            for f in ("prot_internal_ca_rmsd", "rna_internal_c4_rmsd", "rna_placement_c4_rmsd", "geometry_status"):
                if f in e:
                    bad.append("Evaluate %s.%s: the geometry route is withheld and must not be shown" % (e["structure"], f))
    return bad


BANNED = [r"\breliab\w*", r"\bbest\b", r"\bcorrect\b", r"\bprobabilit\w*", r"\baccurate\b", r"\bmost likely\b",
          r"\bconfidence of\b", r"\btrue (binding|interface|structure)\b", r"\b\d+(\.\d+)?\s?% confiden"]


def wording_audit(text):
    """Refuse wording that turns agreement into correctness. The fixed limits block (which says what is NOT
    established) is the only place such words may appear."""
    body = re.sub(r"<div class='lim'>.*?</div>", " ", text, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    hits = []
    for pat in BANNED:
        for m in re.finditer(pat, body, flags=re.I):
            hits.append("%r at ...%s..." % (m.group(0), body[max(0, m.start() - 60): m.end() + 60].replace("\n", " ")))
    return hits
