"""Field-by-field classification of every non-canonical output of a managed-project replay (records/replay, round 2).

usage: python classify_fields.py FIRST SECOND MOVED OUT_JSON
  FIRST, SECOND: two independent case roots (same inputs, other directory, later time)
  MOVED:         a byte copy of FIRST at another absolute path, continued there (FIRST is its former root)

For every regular file under FIRST that is not in the v1 canonical set (retest/canonical_artifacts_v1.json), each
JSON leaf is reduced to a pointer pattern (list indices -> *, path/structure/hash keys -> <key>) and gets:
  observed:  how its value differs FIRST vs SECOND and FIRST vs MOVED (trace_replay_diffs classes; "equal")
  class:     a = volatile execution metadata, b = derived from volatile metadata, c = scientifically meaningful
  rule:      the rule that assigned the class (RULES below; the default for anything not matched is c)
Text files are classified by line: lines that differ only by volatile tokens are a/b, all other lines c.
Binary files are c (figures) unless listed as execution records. The default is c: a field is never classed a or b
because making it deterministic is inconvenient, only by the rules below.
"""
import fnmatch
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import trace_replay_diffs as TR  # noqa: E402

SPEC1 = json.load(open(os.path.join(os.path.dirname(HERE), "retest", "canonical_artifacts_v1.json")))
HEXF = re.compile(r"[0-9a-f]{64}")


def fpat(rel):
    rel = re.sub(r"v\d{4}", "vNNNN", rel)
    rel = HEXF.sub("<key>", rel)
    rel = re.sub(r"_[0-9a-f]{8}\.", "_<id>.", rel)
    rel = re.sub(r"(region|viewer)_\d+-\d+", r"\1_<a>-<b>", rel)
    rel = re.sub(r"fu_\d{4}", "fu_NNNN", rel)
    rel = re.sub(r"diff_[^/]+", "diff_<g>_<h>", rel)
    rel = re.sub(r"s\d{3}", "sNNN", rel)
    rel = re.sub(r"(first|second_copy)_\d{8}T\d{6}Z", "<run>", rel)
    return rel


def ppat(ptr):
    out = []
    for t in ptr.split("/")[1:]:
        if t.isdigit():
            out.append("*")
        elif "~1" in t or "|" in t or "#" in t or HEXF.fullmatch(t) or len(t) > 40 or re.match(r"^[a-z_]+:", t):
            out.append("<key>")
        else:
            out.append(t)
    return "/" + "/".join(out)


def is_v1_canonical(rel_in_project):
    segs = rel_in_project.split("/")
    for pat in SPEC1["patterns_relative_to_project_dir"]:
        ps = pat.split("/")
        if len(ps) == len(segs) and all(fnmatch.fnmatchcase(s, q) for s, q in zip(segs, ps)):
            return True
    return False


# ---------------------------------------------------------------- classification rules (first match wins)
VOL_KEYS = {"created_utc", "recorded_utc", "status_utc", "stored_utc", "since_utc", "timestamp_utc", "started_utc",
            "wall_s", "code_commit", "working_directory", "cwd", "pid", "hostname", "host", "project_root",
            "platform", "python"}
EXEC_RECORD_KEYS = {"command", "argv"}
RULES = [
    ("a:volatile-key", lambda p, v, obs: p.rsplit("/", 1)[-1] in VOL_KEYS, "a"),
    ("a:execution-command", lambda p, v, obs: any(seg in EXEC_RECORD_KEYS for seg in p.split("/")), "a"),
    ("b:id-derived-from-volatile-record", lambda p, v, obs: "ID" in obs, "b"),
    ("a:observed-time-duration", lambda p, v, obs: obs & {"TIMESTAMP", "DURATION"} and not obs - {"TIMESTAMP", "DURATION", "equal"}, "a"),
    ("b:hash-over-volatile-bytes", lambda p, v, obs: "HASH" in obs, "b"),
    ("b:text-with-volatile-hash", lambda p, v, obs: "COMPOSITE" in obs and isinstance(v, str) and HEXF.search(v or ""), "b"),
    ("c:path-identity", lambda p, v, obs: "ABS_PATH" in obs or (isinstance(v, str) and v.startswith("/")), "c"),
    ("c:text-with-path", lambda p, v, obs: "COMPOSITE" in obs, "c"),
    ("c:default", lambda p, v, obs: True, "c"),
]
CANONICAL_FORM = {
    "a": "not in the canonical form (sidecar / execution record)",
    "b": "replaced in the canonical form by the content hash of the bytes it covers, or recomputed from canonical content",
    "c": "kept in the canonical form; absolute paths written project-relative",
}


TEXT_EXT = (".json", ".md", ".txt", ".html", ".tsv", ".svg", ".log", ".mvsj", ".js", ".css", ".fasta", ".tsv")


def category(rel):
    """Which kind of file this is (decides how it is classified)."""
    if rel.startswith("in/"):
        return "input copy (prepared input; identity by content)"
    if "/.rnplens/run/" in "/" + rel:
        return "sidecar (volatile execution metadata by design)"
    if "/viewer_" in rel and "/assets/" in rel:
        return "software asset copy (bundled Mol* files)"
    if "/viewer_" in rel and "/structures/" in rel:
        return "structure copy (viewer)"
    if rel.startswith("logs/") or rel in ("region_rule.json", "followup_scripted.json"):
        return "workflow file outside the managed project"
    if rel.endswith(".log"):
        return "execution log inside the project"
    if rel.endswith(TEXT_EXT) and not rel.endswith(".json"):
        return "text output"
    if rel.endswith(".json"):
        return "JSON output"
    if rel.endswith((".png", ".jpg")):
        return "figure"
    return "other"


def leaves(o, ptr=""):
    if isinstance(o, dict):
        if not o:
            yield ptr, {}
        for k, v in o.items():
            yield from leaves(v, ptr + "/" + TR.esc(k))
    elif isinstance(o, list):
        if not o:
            yield ptr, []
        for i, v in enumerate(o):
            yield from leaves(v, "%s/%d" % (ptr, i))
    else:
        yield ptr, o


class AliasTracer(TR.Tracer):
    """Tracer whose B side also recognises the A root (B is a copy of A at another path)."""

    def norm_path(self, s, side):
        s = s.replace(self.B.root, "<ROOT>") if side == 1 else s.replace(self.A.root, "<ROOT>")
        return s.replace(self.A.root, "<ROOT>") if side == 1 else s


def diff_map(T, rel):
    if rel not in T.B.files:
        return None, {}
    d = T.file_diff(rel, rel)
    m = {}
    for l in d.get("leaves", []):
        m[l["pointer"].replace(" (key)", "")] = l["class"]
    return d, m


def main(first, second, moved, out):
    T12 = TR.Tracer(first, second)
    T1M = AliasTracer(first, moved)
    for T in (T12, T1M):
        both, pairs, _ = T.pair_files()
        T.pairmap = dict(pairs)
    rows, text_rows, bin_rows, cats = {}, {}, {}, {}
    proj = os.path.join(T12.A.root, "project")
    for rel in sorted(T12.A.files):
        relp = os.path.relpath(os.path.join(T12.A.root, rel), proj).replace(os.sep, "/")
        if not relp.startswith("..") and is_v1_canonical(relp):
            continue
        fp = fpat(rel)
        cat = category(rel)
        cats[fp] = cat
        d12, m12 = diff_map(T12, rel)
        d1m, m1m = diff_map(T1M, rel)
        if rel in T12.A.json:
            o = T12.A.json[rel]
            for ptr, v in leaves(o):
                pp = ppat(ptr)
                obs = {m12.get(ptr) or "equal", m1m.get(ptr) or "equal"}
                obs = {x for x in obs if x}
                rule, cls = next((n, c) for n, f, c in RULES if f(ptr, v, obs))
                if cat.startswith("sidecar"):
                    rule, cls = "a:sidecar-by-design", ("b" if "HASH" in obs else "a")
                key = (fp, pp)
                r = rows.setdefault(key, {"file": fp, "field": pp, "n": 0, "observed_first_vs_second": set(),
                                          "observed_first_vs_moved": set(), "classes": set(), "rules": set(),
                                          "example": json.dumps(v, default=str)[:120]})
                r["n"] += 1
                r["observed_first_vs_second"].add(m12.get(ptr) or "equal")
                r["observed_first_vs_moved"].add(m1m.get(ptr) or "equal")
                r["classes"].add(cls)
                r["rules"].add(rule)
        elif not rel.endswith(TEXT_EXT):
            b = bin_rows.setdefault(fp, {"file": fp, "n": 0, "byte_identical_first_vs_second": set(),
                                         "byte_identical_first_vs_moved": set()})
            b["n"] += 1
            b["byte_identical_first_vs_second"].add(rel in T12.B.bytes and T12.A.bytes[rel] == T12.B.bytes[rel])
            b["byte_identical_first_vs_moved"].add(rel in T1M.B.bytes and T1M.A.bytes[rel] == T1M.B.bytes[rel])
        else:
            t = text_rows.setdefault(fp, {"file": fp, "n": 0, "lines": 0, "differing_line_classes_first_vs_second": {},
                                          "differing_line_classes_first_vs_moved": {}})
            t["n"] += 1
            t["lines"] += T12.A.bytes[rel].count(b"\n")
            for d, key in ((d12, "differing_line_classes_first_vs_second"), (d1m, "differing_line_classes_first_vs_moved")):
                for k2, v2 in ((d or {}).get("class_counts") or {}).items():
                    t[key][k2] = t[key].get(k2, 0) + v2
    fields = []
    for (fp, pp), r in sorted(rows.items()):
        cls = sorted(r["classes"])
        r["class"] = "c" if "c" in cls else ("b" if "b" in cls else "a")    # a field pattern is c if any instance is c
        r.update({k: sorted(v) for k, v in r.items() if isinstance(v, set)})
        r["canonical_form"] = CANONICAL_FORM[r["class"]]
        fields.append(r)
    for t in text_rows.values():
        dl = set(t["differing_line_classes_first_vs_second"]) | set(t["differing_line_classes_first_vs_moved"])
        t["class"] = "c (content lines); a/b (volatile tokens on differing lines)"
        t["content_difference"] = bool(dl & {"TEXT_CONTENT", "TEXT_SHORT_HEX_PREFIX"})
    for b in bin_rows.values():
        b.update({k: sorted(v) for k, v in b.items() if isinstance(v, set)})
        b["class"] = "c (figure / derived structure bytes)"
    for r in fields:
        r["category"] = cats.get(r["file"])
    for t in text_rows.values():
        t["category"] = cats.get(t["file"])
    for b in bin_rows.values():
        b["category"] = cats.get(b["file"])
    res = {"schema": "rnplens.replay.noncanonical_fields.1", "first": T12.A.root, "second": T12.B.root,
           "moved": T1M.B.root, "rules": [[n, c] for n, _, c in RULES], "fields": fields,
           "text_files": sorted(text_rows.values(), key=lambda x: x["file"]),
           "binary_files": sorted(bin_rows.values(), key=lambda x: x["file"]),
           "counts": {"field_patterns": len(fields), "by_class": {c: sum(1 for f in fields if f["class"] == c) for c in "abc"},
                      "files_json": len({f["file"] for f in fields}), "files_text": len(text_rows), "files_binary": len(bin_rows)}}
    json.dump(res, open(out, "w"), indent=1, sort_keys=True, default=str)
    open(out, "a").write("\n")
    print(json.dumps(res["counts"]))


if __name__ == "__main__":
    main(*sys.argv[1:5])
