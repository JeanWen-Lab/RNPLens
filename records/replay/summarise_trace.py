"""Aggregate trace_replay_diffs.py outputs into REPLAY_DIFF_TRACE.json (records/replay, step A).

usage: python summarise_trace.py OUT_JSON PRE_REGISTERED_CHECK_1 TRACE_1 [PRE_REGISTERED_CHECK_2 TRACE_2 ...]
For each run: per-file rows (bytes, byte ranges, leaf classes, verdict), whether each file is among the files the
pre-registered check called DIFFERENT, and one row per HASH FAMILY (pointer pattern in a file pattern) with the
object the hash covers and the classes of the covered differences (followed recursively through nested hashes).
"""
import json
import re
import sys

IDX = re.compile(r"/\d+(?=/|$)")
ROOTKEY = re.compile(r"(/|:)~1home~1[^/]*")
HEXN = re.compile(r"[0-9a-f]{64}")
TSN = re.compile(r"\.\d{14,}\.json")


def pat(p):
    return ROOTKEY.sub(r"\1<abs path>", IDX.sub("/N", p or ""))


def fpat(f):
    return TSN.sub(".<ts>.json", HEXN.sub("<key>", f or ""))


def chain(h, depth=0, seen=None):
    """Nested description of what a hash covers."""
    seen = seen if seen is not None else set()
    t = h.get("target")
    if not t:
        return {"unresolved": True}
    out = {"kind": t["kind"], "covers": fpat(t["file_a"]) + (("#" + pat(t["pointer"])) if isinstance(t.get("pointer"), str) and t["pointer"] else ""),
           "covered_difference_classes": h.get("covered_differences"), "verdict": h["verdict"]}
    if h.get("covered_object"):
        out["derived_object"] = fpat(h["covered_object"])
    return out


def main(out, *pairs):
    runs = []
    for chk_path, tr_path in zip(pairs[::2], pairs[1::2]):
        chk, tr = json.load(open(chk_path)), json.load(open(tr_path))
        prereg = {f["file"]: f["result"] for f in chk["files"]}
        prereg_diff = sorted(f for f, r in prereg.items() if r == "DIFFERENT")
        files, fam = [], {}
        for f in tr["files"]:
            row = {"file": f["file"], "replay_file": f.get("replay_file"), "kind": "text" if f.get("text") else "json",
                   "bytes": [f["bytes_a"], f["bytes_b"]], "verdict": f["verdict"], "classes": f["class_counts"],
                   "pre_registered_result": prereg.get(f["file"], "not compared (not *.json, or one-side file)"
                                                        if not f["file"].endswith(".json") or f.get("replay_file") else "not listed")}
            if not f.get("text"):
                row.update({"format": f.get("format"), "differing_byte_ranges": f.get("differing_byte_ranges"),
                            "differing_bytes": [f.get("differing_bytes_a"), f.get("differing_bytes_b")],
                            "unattributed_lines": f.get("unattributed_lines")})
                for l in f.get("leaves", []):
                    hs = [l] if l["class"] == "HASH" else (l.get("embedded_hashes") or [] if l["class"] == "COMPOSITE" else [])
                    for h in hs:
                        k = (fpat(f["file"]), pat(l["pointer"]))
                        c = chain(h)
                        e = fam.setdefault(k, {"file": k[0], "pointer": k[1], "n": 0, "covers": set(), "classes": {}, "verdicts": set()})
                        e["n"] += 1
                        e["covers"].add(c.get("covers", "UNRESOLVED") + ((" via " + c["derived_object"]) if c.get("derived_object") else ""))
                        for kk, vv in (c.get("covered_difference_classes") or {}).items():
                            e["classes"][kk] = e["classes"].get(kk, 0) + vv
                        e["verdicts"].add(c.get("verdict", "UNRESOLVED"))
            else:
                row["n_ranges"] = f.get("n_ranges")
                row["ranges_sample"] = [{k: r[k] for k in ("lines_a", "class", "a", "b")} for r in (f.get("ranges") or [])[:3]]
            files.append(row)
        traced = {r["file"] for r in files}
        runs.append({"label": tr["label"], "original": tr["original"], "replay": tr["replay"],
                     "pre_registered_check": {"file": chk_path.split("/")[-1], "verdict": chk["verdict"],
                                              "verdict_strict": chk.get("verdict_strict"), "counts": chk["counts"],
                                              "n_DIFFERENT": len(prereg_diff)},
                     "pre_registered_DIFFERENT_files": prereg_diff,
                     "pre_registered_DIFFERENT_not_traced": sorted(set(prereg_diff) - traced),
                     "n_files_original": tr["n_files_original"], "n_files_replay": tr["n_files_replay"],
                     "n_byte_identical": tr["n_byte_identical"], "byte_identical_files": tr.get("byte_identical_files"),
                     "n_differing_files": tr["n_differing"],
                     "unpaired_original_only": tr["unpaired_original"], "unpaired_replay_only": tr["unpaired_replay"],
                     "verdict_counts": tr["verdict_counts"], "scientific_content_differs": tr["scientific_content_differs"],
                     "unresolved_files": tr["unresolved"],
                     "evidence_hash_recomputation": tr["evidence_hash_recomputation"],
                     "unattributed_lines_total": sum(r.get("unattributed_lines") or 0 for r in files),
                     "files": files,
                     "hash_families": [dict(v, covers=sorted(v["covers"]), verdicts=sorted(v["verdicts"]))
                                       for _, v in sorted(fam.items())]})
    json.dump({"schema": "rnplens.replay.diff_trace.1", "tool": ["records/replay/trace_replay_diffs.py",
                                                                 "records/replay/summarise_trace.py"], "runs": runs},
              open(out, "w"), indent=1, sort_keys=True, default=str)
    open(out, "a").write("\n")
    for r in runs:
        print(r["label"], r["verdict_counts"], "prereg DIFFERENT", r["pre_registered_check"]["n_DIFFERENT"],
              "not traced", r["pre_registered_DIFFERENT_not_traced"], "hash families", len(r["hash_families"]),
              "unattributed", r["unattributed_lines_total"])


if __name__ == "__main__":
    main(*sys.argv[1:])
