"""Wording scan of every text output of a demonstration folder.

Scanned: *.html *.md *.tsv *.txt *.svg *.log (whole text) and *.json (every string value, joined by newlines),
outside inputs/ and except the vendored Mol* files (molstar.js, molstar.css, LICENSE.molstar.txt) and copied structure
files. Two checks per file:
  1. rnplens.trace.wording_audit(text)   (the limits block <div class='lim'> is excluded by the audit itself)
  2. rnplens.grouping.FORBIDDEN          (Spec B v2 section 6: "best", "most likely", "correct group",
                                          "confidence of the group"), on the whole text INCLUDING limits blocks
JSON values under the keys rationale / rationale_stored_not_shown / replies (a model's stored, never-shown rationale)
are not scanned; their number is reported. Every hit is listed with its context and classified: NEGATED when the sentence holding it contains a negation
(not, never, no, nor, cannot, without), otherwise AFFIRMATIVE. A hit inside a whitespace-free JSON string is
classed IDENTIFIER. The scan PASSES when no file outside the frozen rc3 component outputs has a forbidden-phrase hit or
an AFFIRMATIVE wording-audit hit (IDENTIFIER hits excepted); every hit is listed either way.

usage: python wording_scan.py ROOT OUT_JSON [--also FILE ...]
"""
import json
import os
import re
import sys

from rnplens import grouping, trace

TEXT = (".html", ".md", ".tsv", ".txt", ".svg", ".log")
SKIP_FILES = {"molstar.js", "molstar.css", "LICENSE.molstar.txt"}
NEG = re.compile(r"\b(not|never|no|nor|cannot|without|n't)\b", re.I)
# Outputs of the frozen rc3 components (Report: report/; Diagnose: diagnose_*/; Evaluate: evaluate*/) are listed but
# are not 0.4 text: their wording is frozen (RNPLens_release_2026-10-13) and they never fail the scan.
# (Refinement after the first demo-1 run on karyon, recorded in DEMOS_REPORT.md: Diagnose's frozen report was added to
# the frozen set, and a hit inside a whitespace-free JSON string, e.g. the identifier 'probability_of_correctness' in
# Diagnose's refused_statements list, is classed IDENTIFIER.)


def frozen_component(rel):
    parts = rel.split(os.sep)[:-1]
    return any(p == "report" or p.startswith("diagnose_") or p.startswith("evaluate") for p in parts)


# Machine-record fields that hold a model's (here: the scripted client's) free-text rationale. The follow-up stores
# it and never shows it (docs/followup.md); the demonstration checks separately that it is absent from every answer.
SKIP_KEYS = {"rationale", "rationale_stored_not_shown", "replies"}
SKIPPED = []


def strings(o, acc):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in SKIP_KEYS:
                SKIPPED.append(k)
                continue
            strings(v, acc)
    elif isinstance(o, list):
        for v in o:
            strings(v, acc)
    elif isinstance(o, str):
        acc.append(o)
    return acc


def sentence(text, start, end):
    a = max(text.rfind(".", 0, start), text.rfind("\n", 0, start)) + 1
    bs = [i for i in (text.find(".", end), text.find("\n", end)) if i >= 0]
    b = min(bs) if bs else len(text)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text[a:b + 1])).strip()


def scan_json_strings(values):
    hits = []
    for v in values:
        for h in scan_text(v):
            if not v.strip() or len(v.split()) == 1:
                h["class"] = "IDENTIFIER"
            hits.append(h)
    return hits


def scan_text(text):
    hits = []
    body = re.sub(r"<div class='lim'>.*?</div>", " ", text, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    for pat in trace.BANNED:
        for m in re.finditer(pat, body, flags=re.I):
            s = sentence(body, m.start(), m.end())
            hits.append({"check": "wording_audit", "match": m.group(0), "sentence": s[:400],
                         "class": "NEGATED" if NEG.search(s) else "AFFIRMATIVE"})
    plain = re.sub(r"<[^>]+>", " ", text)
    for pat in grouping.FORBIDDEN:
        for m in re.finditer(pat, plain, flags=re.I):
            hits.append({"check": "forbidden_phrase", "match": m.group(0), "sentence": sentence(plain, m.start(), m.end())[:400]})
    return hits


def main(root, out, also=()):
    root = os.path.realpath(root)
    res = {"root": root, "banned_patterns": trace.BANNED, "forbidden_phrases": grouping.FORBIDDEN, "files": []}
    paths = []
    for d, sub, fs in os.walk(root):
        rel = os.path.relpath(d, root)
        if rel.split(os.sep)[0] in ("inputs", "checks"):        # checks/: this scan's own reports
            continue
        for f in fs:
            if f in SKIP_FILES or f.endswith("wording_scan.log") or not f.endswith(TEXT + (".json",)):
                continue
            paths.append(os.path.join(d, f))
    paths += [os.path.realpath(p) for p in also]
    for p in sorted(paths):
        rel = os.path.relpath(p, root)
        n0 = len(SKIPPED)
        vals = None
        if p.endswith(".json"):
            try:
                vals = strings(json.load(open(p, encoding="utf-8")), [])
            except ValueError:
                vals = None
        if vals is not None:
            text, hits = "\n".join(vals), scan_json_strings(vals)
        else:
            text = open(p, encoding="utf-8", errors="replace").read()
            hits = scan_text(text)
        frozen = frozen_component(rel)
        res["files"].append({"file": rel, "frozen_rc3_component_output": frozen, "n_hits": len(hits), "hits": hits,
                             "audit_raw_equals_empty": trace.wording_audit(text) == [],
                             "stored_rationale_values_not_scanned": len(SKIPPED) - n0})
    bad = [(f["file"], h) for f in res["files"] for h in f["hits"] if not f["frozen_rc3_component_output"] and h.get("class") != "IDENTIFIER"
           and (h["check"] == "forbidden_phrase" or h["class"] == "AFFIRMATIVE")]
    res["n_files"] = len(res["files"])
    res["stored_rationale_values_not_scanned"] = len(SKIPPED)
    res["n_files_with_hits"] = sum(1 for f in res["files"] if f["hits"])
    res["n_forbidden_phrase_hits"] = sum(1 for f in res["files"] for h in f["hits"] if h["check"] == "forbidden_phrase")
    res["n_forbidden_phrase_hits_in_0.4_outputs"] = sum(1 for f, h in bad if h["check"] == "forbidden_phrase")
    res["n_hits_in_frozen_component_outputs"] = sum(f["n_hits"] for f in res["files"] if f["frozen_rc3_component_output"])
    res["hit_classes"] = {}
    for f in res["files"]:
        for h in f["hits"]:
            k = "%s/%s/%s" % ("frozen" if f["frozen_rc3_component_output"] else "0.4", h["check"], h.get("class", "-"))
            res["hit_classes"][k] = res["hit_classes"].get(k, 0) + 1
    res["n_affirmative_hits_in_0.4_outputs"] = sum(1 for f, h in bad if h["check"] == "wording_audit")
    res["n_files_audit_not_empty"] = sum(1 for f in res["files"] if not f["audit_raw_equals_empty"])
    res["failing"] = [{"file": f, **h} for f, h in bad]
    res["verdict"] = "PASS" if not bad else "FAIL"
    with open(out, "w") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    print("wording scan: %s; %d files scanned, %d with hits; hit classes %s; failing %d"
          % (res["verdict"], res["n_files"], res["n_files_with_hits"], res["hit_classes"], len(bad)))
    for f, h in bad:
        print("  %s: %s %r in: %s" % (f, h["check"], h["match"], h["sentence"][:200]))
    return 0 if not bad else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    also = a[a.index("--also") + 1:] if "--also" in a else []
    sys.exit(main(a[0], a[1], also))
