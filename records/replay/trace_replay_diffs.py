"""Byte-level trace of the differences between a demonstration package and its replay (records/replay, step A).

Read-only on both trees. For EVERY regular file under ORIGINAL and REPLAY (inputs/ included, so that hashes of
copied inputs can be resolved) this tool

1. compares the bytes;
2. for a differing JSON file, re-serialises it with the writer RNPLens uses (json.dumps(indent=1, sort_keys=True,
   default=str) + newline) and checks that this reproduces the file byte-for-byte ("roundtrip"); when it does, every
   output line carries the JSON pointer it encodes, so every differing line (and therefore every differing byte) is
   attributed to a pointer; when it does not, only the leaf diff is given (roundtrip false);
3. classifies each differing leaf:
     TIMESTAMP      both values are ISO-8601 or 14+ digit time stamps
     ABS_PATH       equal after replacing each side's package root by <ROOT>
     HASH           both are 64-hex strings; the hash is RESOLVED below
     ID             consent ids consent-NNNN-<8 hex> (prefix of the SHA-256 of the record)
     DURATION       a measured run time (keys wall_s, *_seconds)
     SCRIPT_LOCATION  equal after replacing the absolute folder of the demonstration driver scripts
                    (<...>/demos/lib/ or <...>/scripts/lib/) by <DEMO_LIB>/ (log lines only)
     ORDER          a list whose items are the same after mapping paired hash-named files, in another order
                    (the order follows file names that are cache keys)
     DEMO_TOOLING   a copied demonstration script under scripts/ that differs (not an RNPLens output)
     COMPOSITE      a string that is equal after replacing roots, time stamps and resolved hashes/ids
     CONTENT        anything else (numbers, words, structure): a scientific-content finding
4. resolves every differing 64-hex value on each side against
     (a) the SHA-256 of every file of that tree (-> FILE_SHA256 of <relpath>),
     (b) sha256_json (sorted keys, compact separators, as rnplens.provenance.sha256_json) of every JSON subtree of
         every JSON file of that tree (-> SUBTREE of <relpath>#<pointer>),
     (c) sha256_json of rnplens.incremental.manifest_view / correspondence / selection of every manifest.json
         (-> DERIVED <fn>(<relpath>)), when rnplens is importable,
     (d) the recorded follow-up evidence hash recomputed with rnplens_assistant.followup.evidence_hash
         (-> DERIVED evidence_hash(<relpath>)), when importable,
   and states whether the hashed bytes / object differ between the two trees and through which leaves
   (recursively: VOLATILE_ONLY when the covered object differs only in TIMESTAMP / ABS_PATH / ID / VOLATILE_ONLY
   hashes; CONTENT when any covered leaf is CONTENT; UNRESOLVED when no target was found).
Files present on one side only (cache entries are named by their key) are paired by (name with hex and time stamps
masked, and for cache entries meta.kind/group/computed_in_version and outdir).

usage: python trace_replay_diffs.py ORIGINAL REPLAY OUT_JSON [--label NAME]
"""
import difflib
import hashlib
import json
import os
import re
import sys

TS = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?|\d{14,})$")
TS_IN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?|(?<![0-9a-f])\d{14,}(?![0-9a-f])"
                   r"|\d{8}T\d{6}Z?")
HEX = re.compile(r"^[0-9a-f]{64}$")
HEX_IN = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
CID = re.compile(r"^consent-\d{4}-[0-9a-f]{8}$")
CID_IN = re.compile(r"(consent-\d{4})-[0-9a-f]{8}")
DEMO_LIB_IN = re.compile(r"/[^\s'\"]*/(demos|scripts)/lib/")
DURATION_KEYS = ("wall_s", "elapsed_s", "duration_s")
SHORTHEX_IN = re.compile(r"(?<![0-9a-f])[0-9a-f]{8,12}(?![0-9a-f])")


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_json(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def esc(k):
    return str(k).replace("~", "~0").replace("/", "~1")


# ---------------------------------------------------------------- serialiser with per-line pointers
def emit(o, ind, ptr, lines, prefix="", w=1, srt=True):
    """Reproduce json.dumps(o, indent=w, sort_keys=srt) line by line, tagging each line with its pointer."""
    pad = " " * (ind * w)
    if isinstance(o, dict) and o:
        lines.append((pad + prefix + "{", ptr))
        ks = sorted(o) if srt else list(o)
        for i, k in enumerate(ks):
            sub = []
            emit(o[k], ind + 1, ptr + "/" + esc(k), sub, json.dumps(k) + ": ", w, srt)
            if i < len(ks) - 1:
                sub[-1] = (sub[-1][0] + ",", sub[-1][1])
            lines.extend(sub)
        lines.append((pad + "}", ptr))
    elif isinstance(o, list) and o:
        lines.append((pad + prefix + "[", ptr))
        for i, v in enumerate(o):
            sub = []
            emit(v, ind + 1, "%s/%d" % (ptr, i), sub, "", w, srt)
            if i < len(o) - 1:
                sub[-1] = (sub[-1][0] + ",", sub[-1][1])
            lines.extend(sub)
        lines.append((pad + "]", ptr))
    else:
        lines.append((pad + prefix + json.dumps(o, default=str), ptr))
    return lines


# ---------------------------------------------------------------- trees
def walk(root):
    out = {}
    for dp, dn, fn in os.walk(root):
        dn.sort()
        for f in sorted(fn):
            p = os.path.join(dp, f)
            if os.path.isfile(p) and not os.path.islink(p):
                out[os.path.relpath(p, root).replace(os.sep, "/")] = p
    return out


def subtrees(o, ptr=""):
    yield ptr, o
    if isinstance(o, dict):
        for k, v in o.items():
            yield from subtrees(v, ptr + "/" + esc(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from subtrees(v, "%s/%d" % (ptr, i))


def get(o, ptr):
    if ptr == "":
        return o
    for t in ptr.split("/")[1:]:
        t = t.replace("~1", "/").replace("~0", "~")
        o = o[int(t)] if isinstance(o, list) else o[t]
    return o


class Tree:
    def __init__(self, root):
        self.root = os.path.realpath(root)
        self.files = walk(self.root)
        self.bytes = {r: open(p, "rb").read() for r, p in self.files.items()}
        self.sha = {r: sha_bytes(b) for r, b in self.bytes.items()}
        self.json = {}
        for r, b in self.bytes.items():
            if r.endswith(".json") or r.endswith("HEAD"):
                try:
                    self.json[r] = json.loads(b.decode("utf-8"))
                except Exception:
                    pass
        self.hash_index = {}
        for r, s in self.sha.items():
            self.hash_index.setdefault(s, []).append(("FILE_SHA256", r, None))
        for r, o in self.json.items():
            for ptr, sub in subtrees(o):
                if isinstance(sub, (dict, list)):
                    self.hash_index.setdefault(sha_json(sub), []).append(("SUBTREE", r, ptr))
        self.derived = {}
        self.derive_error = None
        self._derive()

    def _derive(self):
        try:
            from rnplens import incremental as I
        except Exception as ex:
            self.derive_error = "rnplens not importable: %s" % ex
            return
        for r, o in self.json.items():
            if r.endswith("manifest.json") and isinstance(o, dict) and "structures" in o:
                for name, fn in (("manifest_view", I.manifest_view), ("correspondence", I.correspondence),
                                 ("selection", I.selection)):
                    try:
                        v = fn(o)
                    except Exception:
                        continue
                    self.derived["%s(%s)" % (name, r)] = v
                    self.hash_index.setdefault(sha_json(v), []).append(("DERIVED", r, name))
        from rnplens import clarify as C
        for r, o in self.json.items():
            if not (isinstance(o, dict) and isinstance(o.get("inputs"), dict) and isinstance(o["inputs"].get("files"), dict)):
                continue
            files = o["inputs"]["files"]
            # run hashes (clarify.run_hash / current_hash 'run:<root>'): every declared file under the run root
            roots = set((o["inputs"].get("runs") or {}).keys())
            for g in (o.get("decisions") or {}).values():
                roots |= {k.partition(":")[2] for k in (g.get("depends_on") or {}) if k.startswith("run:")}
            for root in sorted(roots):
                v = {p: s for p, s in sorted(files.items()) if C._under(p, root)}
                name = "run_hash:" + root
                self.derived["%s(%s)" % (name, r)] = v
                self.hash_index.setdefault(sha_json(v), []).append(("DERIVED", r, name))
            # import inputs (incremental._group_inputs) of every group: manifest inputs + other files in their folders
            run_of = {}
            for root in roots:
                for p in files:
                    if C._under(p, root):
                        run_of[p] = root
            for g, rec in sorted((o.get("groups") or {}).items()):
                idir = rec.get("import_dir")
                man = self.json.get("%s/manifest.json" % idir) if idir else None
                if man is None:
                    man = next((m for k, m in self.json.items() if idir and k.endswith(idir + "/manifest.json")), None)
                if not man:
                    continue
                v = I._group_inputs(list(man.get("inputs") or []), files, run_of)
                name = "group_inputs:" + g
                self.derived["%s(%s)" % (name, r)] = v
                self.hash_index.setdefault(sha_json(v), []).append(("DERIVED", r, name))
                # import configuration (incremental.run_pipeline: engine, case_id, importer answers, group files)
                decl = o.get("declared") or {}
                case_id = decl.get("case_id") if g == "main" else "%s_%s" % (decl.get("case_id"), g)
                answers = {}
                for d in sorted((o.get("decisions") or {}).values(), key=lambda d: d.get("id", "")):
                    if d.get("status") == "ACTIVE":
                        answers.update((d.get("apply") or {}).get("importer_answers") or {})
                v = {"engine": decl.get("engine"), "case_id": case_id, "answers": answers,
                     "files": sorted(man.get("inputs") or [])}
                name = "import_config:" + g
                self.derived["%s(%s)" % (name, r)] = v
                self.hash_index.setdefault(sha_json(v), []).append(("DERIVED", r, name))
        try:
            from rnplens_assistant import followup as F
        except Exception as ex:
            self.derive_error = "rnplens_assistant not importable: %s" % ex
            return
        for r, o in self.json.items():
            if r.endswith("followup_record.json") and isinstance(o, dict) and o.get("evidence_sha256"):
                ans = self.json.get(r.replace("followup_record.json", "followup_answer.json")) or {}
                keep = [{"type": st["type"], "text": st["text"],
                         "slots": {n: {k: F._norm(x, None, None) for k, x in s.items()} for n, s in sorted(st["slots"].items())},
                         "cites": st["cites"]} for st in ans.get("statements") or []]
                log = [{"tool": e["tool"], "call": e["call"], "status": e["status"], "outputs": e.get("outputs"),
                        "message": F._norm(e.get("message"), None, None)} for e in o.get("tool_log") or []]
                obj = {"statements": keep, "tool_log": log}
                h = hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()
                ver = o.get("evidence_hash_version")
                if ver:     # contract v1 / v2 Amendment 2: recompute under the definition the record declares
                    h = self._declared_evidence_hash(r, o, ans, ver, F)
                self.derived["evidence_hash(%s)" % r] = obj
                self.derived_check = getattr(self, "derived_check", {})
                self.derived_check[r] = {"recomputed": h, "recorded": o["evidence_sha256"], "equal": h == o["evidence_sha256"],
                                         "definition": ver or "rnplens.followup.evidence.1 (no evidence_hash_version)"}
                self.hash_index.setdefault(h, []).append(("DERIVED", r, "evidence_hash"))


    def _declared_evidence_hash(self, r, o, ans, ver, F):
        """Contract v1 / v2 Amendment 2. The evidence hash of a follow-up record that declares evidence_hash_version,
        recomputed by rnplens_assistant.followup.evidence_hash under that definition. Its arguments: the sibling
        followup_answer.json statements, the record's tool_log, and P, A, the import and analysis directories of the
        state version whose analysis 'main' is the record's analysis (newest first). None when this cannot be done,
        e.g. an unknown definition or no such version; the check is then unequal."""
        try:
            from rnplens import state
            i = r.find("/analyses/")
            proj = os.path.join(self.root, r[:i])
            arel = r[i + 1:r.index("/followup/")]
            pr = state.Project(proj)
            for v in reversed(pr.versions()):
                a = ((pr.load(v["version"]).get("analyses") or {}).get("main") or {})
                if a.get("dir") == arel:
                    return F.evidence_hash(ans.get("statements") or [], o.get("tool_log") or [],
                                           os.path.join(proj, a["import_dir"]), os.path.join(proj, arel), version=ver)
        except Exception as ex:
            self.derive_error = "evidence hash under %s for %s: %s" % (ver, r, ex)
        return None


# ---------------------------------------------------------------- comparison
class Tracer:
    def __init__(self, orig, rep):
        self.A, self.B = Tree(orig), Tree(rep)
        self.memo = {}
        self.pairmap = {}

    def norm_path(self, s, side):
        T = self.A if side == 0 else self.B
        return s.replace(T.root, "<ROOT>")

    def pair_files(self):
        a, b = set(self.A.files), set(self.B.files)
        both = sorted(a & b)
        oa, ob = sorted(a - b), sorted(b - a)
        mask = lambda f: HEX_IN.sub("<HEX>", TS_IN.sub("<TS>", f))

        def ident(T, f):
            o = T.json.get(f)
            o = o if isinstance(o, dict) else {}
            m = o.get("meta") or {}
            return (mask(f), m.get("kind"), m.get("group"), m.get("computed_in_version"), o.get("outdir"))
        pairs, used = [], set()
        for f in oa:
            cand = [g for g in ob if g not in used and ident(self.B, g) == ident(self.A, f)]
            if len(cand) == 1:
                used.add(cand[0]); pairs.append((f, cand[0]))
        paired = {p[0] for p in pairs}
        return both, pairs, ([f for f in oa if f not in paired], [g for g in ob if g not in used])

    # leaf classification -------------------------------------------------
    def classify(self, va, vb, ptr=""):
        if va == vb:
            return None
        last = ptr.rsplit("/", 1)[-1]
        if (last in DURATION_KEYS or last.endswith("_seconds")) and isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            return {"class": "DURATION"}
        if isinstance(va, str) and isinstance(vb, str):
            if TS.match(va) and TS.match(vb):
                return {"class": "TIMESTAMP"}
            if self.norm_path(va, 0) == self.norm_path(vb, 1):
                return {"class": "ABS_PATH"}
            if HEX.match(va) and HEX.match(vb):
                return dict(self.resolve(va, vb), **{"class": "HASH"})
            if CID.match(va) and CID.match(vb) and va[:12] == vb[:12]:
                return {"class": "ID", "note": "consent record id: 8-hex prefix of the SHA-256 of the consent record "
                                               "(json.dumps sort_keys), which contains timestamp_utc and the absolute "
                                               "project path (rnplens_assistant/consent.py _append)"}
            na, nb = self.norm_text(va, 0), self.norm_text(vb, 1)
            if na[0] == nb[0]:
                hashes = [self.resolve(x, y) for x, y in zip(na[1], nb[1]) if x != y]
                return {"class": "COMPOSITE", "embedded_hashes": hashes,
                        "verdict": self.worst([h["verdict"] for h in hashes] or ["VOLATILE_ONLY"])}
            return {"class": "CONTENT", "a": va[:300], "b": vb[:300]}
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and not isinstance(va, bool):
            return {"class": "CONTENT", "a": va, "b": vb, "note": "numeric value differs"}
        return {"class": "CONTENT", "a": json.dumps(va, default=str)[:300], "b": json.dumps(vb, default=str)[:300],
                "note": "type or structure differs"}

    def alias(self, o, side):
        """Object with the package root replaced and hex names of paired one-side files mapped to the B side."""
        t = json.dumps(o, sort_keys=True, default=str)
        t = self.norm_path(t, side)
        if side == 0:
            for fa, fb in self.pairmap.items():
                for x, y in zip(HEX_IN.findall(fa), HEX_IN.findall(fb)):
                    t = t.replace(x, y)
        t = re.sub(r"\.\d{14,}\.json", ".<TS>.json", t)
        return json.loads(t)

    def norm_text(self, s, side):
        hexes = HEX_IN.findall(s)
        t = HEX_IN.sub("<HEX>", s)
        t = CID_IN.sub(r"\1-<ID>", self.norm_path(t, side))
        t = TS_IN.sub("<TS>", t)
        return t, hexes

    @staticmethod
    def worst(vs):
        for v in ("CONTENT", "UNRESOLVED", "DEMO_TOOLING", "VOLATILE_ONLY"):
            if v in vs:
                return v
        return "VOLATILE_ONLY"

    def resolve(self, ha, hb):
        """What do ha (in A) and hb (in B) hash, and why do the hashed objects differ?"""
        key = (ha, hb)
        if key in self.memo:
            return self.memo[key]
        self.memo[key] = {"a": ha, "b": hb, "verdict": "UNRESOLVED", "note": "cycle"}
        ta, tb = self.A.hash_index.get(ha, []), self.B.hash_index.get(hb, [])
        res = {"a": ha, "b": hb, "targets_a": [list(t) for t in ta][:4], "targets_b": [list(t) for t in tb][:4]}
        mask = lambda f: HEX_IN.sub("<HEX>", TS_IN.sub("<TS>", f or ""))
        match = None
        for x in ta:
            for y in tb:
                if x[0] == y[0] and self.pairmap.get(x[1], x[1]) == y[1] and \
                        mask(self.norm_path(x[2] or "", 0)) == mask(self.norm_path(y[2] or "", 1)):
                    match = (x, y); break
            if match:
                break
        if not match:
            res.update(verdict="UNRESOLVED", note="no common target found in the two trees")
            self.memo[key] = res
            return res
        (kind, fa, pa), (_, fb, pb) = match
        res["target"] = {"kind": kind, "file_a": fa, "file_b": fb, "pointer": pa if pa == pb else [pa, pb]}
        if kind == "FILE_SHA256":
            d = self.file_diff(fa, fb)
            res["covered_differences"] = d["class_counts"]
            res["verdict"] = d["verdict"]
        else:
            if kind == "SUBTREE":
                leaves = self.leaf_diff(get(self.A.json[fa], pa), get(self.B.json[fb], pb), pa)
            else:
                if pa == "evidence_hash":
                    res["covered"] = ("exact object hashed by rnplens_assistant.followup.evidence_hash: statements "
                                      "(type, text, slots with absolute paths reduced by _norm, cites) and tool_log "
                                      "(tool, call, status, outputs, message); started_utc and wall_s are NOT covered")
                leaves = self.leaf_diff(self.A.derived["%s(%s)" % (pa, fa)], self.B.derived["%s(%s)" % (pb, fb)], "")
                res["covered_object"] = "%s(%s)" % (pa, fa)
            res["covered_differences"] = self.counts(leaves)
            res["covered_leaves_sample"] = [{"pointer": p, "class": c["class"], "verdict": self.leaf_verdict(c)}
                                            for p, c in leaves[:12]]
            res["verdict"] = self.worst([self.leaf_verdict(c) for _, c in leaves] or ["VOLATILE_ONLY"])
        self.memo[key] = res
        return res

    @staticmethod
    def leaf_verdict(c):
        if c["class"] in ("TIMESTAMP", "ABS_PATH", "ID", "DURATION", "SCRIPT_LOCATION", "ORDER"):
            return "VOLATILE_ONLY"
        if c["class"] in ("HASH", "COMPOSITE"):
            return c.get("verdict", "UNRESOLVED")
        return "CONTENT"

    @staticmethod
    def counts(leaves):
        out = {}
        for _, c in leaves:
            k = c["class"] + ("" if c["class"] not in ("HASH", "COMPOSITE") else ":" + c.get("verdict", "?"))
            out[k] = out.get(k, 0) + 1
        return dict(sorted(out.items()))

    def leaf_diff(self, a, b, ptr):
        """Differing leaves; dict keys that differ only by the package root are aligned."""
        out = []
        if isinstance(a, dict) and isinstance(b, dict):
            ka = {self.norm_path(k, 0): k for k in a}
            kb = {self.norm_path(k, 1): k for k in b}
            for nk in sorted(set(ka) | set(kb)):
                if nk in ka and nk in kb:
                    p = ptr + "/" + esc(ka[nk])
                    if ka[nk] != kb[nk]:
                        out.append((p + " (key)", {"class": "ABS_PATH", "note": "map key contains the package root",
                                                   "key_b": ptr + "/" + esc(kb[nk])}))
                    out += self.leaf_diff(a[ka[nk]], b[kb[nk]], p)
                else:
                    out.append((ptr + "/" + esc(ka.get(nk) or kb.get(nk)),
                                {"class": "CONTENT", "note": "key present on one side only"}))
            return out
        if isinstance(a, list) and isinstance(b, list):
            if len(a) == len(b) and a != b:
                el = []
                for i, (x, y) in enumerate(zip(a, b)):
                    el += self.leaf_diff(x, y, "%s/%d" % (ptr, i))
                if any(self.leaf_verdict(c) != "VOLATILE_ONLY" for _, c in el):
                    na = sorted(json.dumps(self.alias(x, 0), sort_keys=True, default=str) for x in a)
                    nb = sorted(json.dumps(self.alias(y, 1), sort_keys=True, default=str) for y in b)
                    if na == nb:
                        return [(ptr, {"class": "ORDER", "note": "same items after mapping paired hash-named files and "
                                       "roots; order differs because it follows hash-valued file names"})]
                return el
            if len(a) != len(b):
                out.append((ptr, {"class": "CONTENT", "note": "list length %d vs %d" % (len(a), len(b))}))
            for i, (x, y) in enumerate(zip(a, b)):
                out += self.leaf_diff(x, y, "%s/%d" % (ptr, i))
            return out
        c = self.classify(a, b, ptr)
        return [(ptr, c)] if c else []

    # file comparison -----------------------------------------------------
    def file_diff(self, fa, fb):
        mk = ("F", fa, fb)
        if mk in self.memo:
            return self.memo[mk]
        self.memo[mk] = {"verdict": "UNRESOLVED", "class_counts": {"cycle": 1}}
        ba, bb = self.A.bytes[fa], self.B.bytes[fb]
        r = {"file": fa, "replay_file": fb if fb != fa else None, "bytes_a": len(ba), "bytes_b": len(bb),
             "sha256_a": sha_bytes(ba), "sha256_b": sha_bytes(bb)}
        if ba == bb:
            r.update(result="BYTE_IDENTICAL", verdict="VOLATILE_ONLY", class_counts={})
            self.memo[mk] = r
            return r
        oa, ob = self.A.json.get(fa), self.B.json.get(fb)
        if oa is not None and ob is not None:
            rt = False
            for w, srt in ((1, True), (2, True), (2, False), (1, False), (4, True), (4, False)):
                la, lb = emit(oa, 0, "", [], "", w, srt), emit(ob, 0, "", [], "", w, srt)
                ta_, tb_ = "\n".join(x for x, _ in la), "\n".join(x for x, _ in lb)
                for nl in ("\n", ""):
                    if (ta_ + nl).encode() == ba and (tb_ + nl).encode() == bb:
                        rt = True
                        r["format"] = {"indent": w, "sort_keys": srt, "final_newline": bool(nl)}
                        break
                if rt:
                    break
            leaves = self.leaf_diff(oa, ob, "")
            lv = dict(leaves)
            keyb = {c.get("key_b"): p[:-6] for p, c in leaves if p.endswith(" (key)")}
            r["roundtrip"] = rt
            if rt:
                sm = difflib.SequenceMatcher(None, [x for x, _ in la], [x for x, _ in lb], autojunk=False)
                off_a, off_b = [0], [0]
                for x, _ in la:
                    off_a.append(off_a[-1] + len(x.encode()) + 1)
                for x, _ in lb:
                    off_b.append(off_b[-1] + len(x.encode()) + 1)
                ranges, unattr = [], 0
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    if tag == "equal":
                        continue
                    ptrs = sorted({p for _, p in la[i1:i2]} | {keyb.get(p, p) for _, p in lb[j1:j2]})
                    cls = set()
                    for p in ptrs:
                        c = lv.get(p) or lv.get(p + " (key)")
                        if c is None:     # a line inside a list compared as a whole (ORDER)
                            anc = [q for q in lv if lv[q]["class"] == "ORDER" and p.startswith(q + "/")]
                            c = lv[anc[0]] if anc else None
                        if c is not None:
                            cls.add(c["class"]); continue
                        sub = [q for q in lv if q.startswith(p + "/") or q == p + " (key)"]
                        # a container line: differs only if a key below it was renamed / its subtree changed
                        if not sub:
                            # pointer under a renamed key on side B: map it back
                            alias = [q for q in lv if q.endswith(" (key)") and p.startswith(q[:-6])]
                            for kb_, ka_ in keyb.items():
                                if kb_ and p.startswith(kb_):
                                    alias.append(ka_ + p[len(kb_):])
                            hit = [lv.get(x) for x in alias if lv.get(x)]
                            if hit:
                                cls |= {h["class"] for h in hit}
                            elif alias:
                                cls.add("ABS_PATH")
                            else:
                                unattr += 1; cls.add("UNATTRIBUTED")
                        else:
                            cls |= {lv[q]["class"] for q in sub}
                    ranges.append({"bytes_a": [off_a[i1], off_a[i2]], "bytes_b": [off_b[j1], off_b[j2]],
                                   "lines_a": [i1 + 1, i2], "lines_b": [j1 + 1, j2], "classes": sorted(cls)})
                r["differing_byte_ranges"] = len(ranges)
                r["differing_bytes_a"] = sum(x["bytes_a"][1] - x["bytes_a"][0] for x in ranges)
                r["differing_bytes_b"] = sum(x["bytes_b"][1] - x["bytes_b"][0] for x in ranges)
                r["unattributed_lines"] = unattr
                r["ranges_sample"] = ranges[:6]
            r["leaves"] = [dict(pointer=p, **c) for p, c in leaves]
            r["class_counts"] = self.counts(leaves)
            r["verdict"] = self.worst([self.leaf_verdict(c) for _, c in leaves] or ["VOLATILE_ONLY"])
            if rt and r["unattributed_lines"]:
                r["verdict"] = self.worst([r["verdict"], "UNRESOLVED"])
            if not leaves:
                r["verdict"] = "UNRESOLVED"; r["note"] = "bytes differ but the parsed JSON is equal (formatting)"
            r["result"] = "DIFFERENT"
        else:
            ta, tb = ba.decode("utf-8", "replace").splitlines(), bb.decode("utf-8", "replace").splitlines()
            sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
            lines, cc = [], {}
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    continue
                xa, xb = "\n".join(ta[i1:i2]), "\n".join(tb[j1:j2])
                na, nb = self.norm_text(xa, 0), self.norm_text(xb, 1)
                if na[0] == nb[0]:
                    hs = [self.resolve(x, y) for x, y in zip(na[1], nb[1]) if x != y]
                    v = self.worst([h["verdict"] for h in hs] or ["VOLATILE_ONLY"])
                    c = "VOLATILE_TEXT" if not hs else "TEXT_WITH_HASH:" + v
                elif DEMO_LIB_IN.sub("<DEMO_LIB>/", na[0]) == DEMO_LIB_IN.sub("<DEMO_LIB>/", nb[0]):
                    c, v = "SCRIPT_LOCATION", "VOLATILE_ONLY"
                elif fa.startswith("scripts/") and fa == fb:
                    c, v = "DEMO_TOOLING", "DEMO_TOOLING"
                elif SHORTHEX_IN.sub("<h>", na[0]) == SHORTHEX_IN.sub("<h>", nb[0]):
                    c, v = "TEXT_SHORT_HEX_PREFIX", "UNRESOLVED"
                else:
                    c, v = "TEXT_CONTENT", "CONTENT"
                cc[c] = cc.get(c, 0) + 1
                lines.append({"lines_a": [i1 + 1, i2], "lines_b": [j1 + 1, j2], "class": c, "verdict": v,
                              "a": xa[:240], "b": xb[:240]})
            r.update(result="DIFFERENT", text=True, class_counts=cc, ranges=lines[:40], n_ranges=len(lines),
                     verdict=self.worst([x["verdict"] for x in lines] or ["VOLATILE_ONLY"]))
        self.memo[mk] = r
        return r


def main(argv):
    orig, rep, out = argv[:3]
    label = argv[argv.index("--label") + 1] if "--label" in argv else os.path.basename(orig)
    T = Tracer(orig, rep)
    both, pairs, (only_a, only_b) = T.pair_files()
    T.pairmap = dict(pairs)
    files = []
    for f in both:
        d = T.file_diff(f, f)
        if d["result"] != "BYTE_IDENTICAL":
            files.append(d)
    for f, g in pairs:
        files.append(T.file_diff(f, g))
    ident = [f for f in both if T.A.bytes[f] == T.B.bytes[f]]
    res = {"label": label, "original": T.A.root, "replay": T.B.root, "tool": "records/replay/trace_replay_diffs.py",
           "derive_error": T.A.derive_error, "n_files_original": len(T.A.files), "n_files_replay": len(T.B.files),
           "n_byte_identical": len(ident), "byte_identical_files": ident, "n_differing": len(files), "unpaired_original": only_a,
           "unpaired_replay": only_b, "files": files, "verdict_counts": {},
           "evidence_hash_recomputation": {"original": getattr(T.A, "derived_check", {}), "replay": getattr(T.B, "derived_check", {})}}
    for f in files:
        res["verdict_counts"][f["verdict"]] = res["verdict_counts"].get(f["verdict"], 0) + 1
    res["scientific_content_differs"] = any(f["verdict"] == "CONTENT" for f in files)
    res["unresolved"] = [f["file"] for f in files if f["verdict"] == "UNRESOLVED"]
    with open(out, "w") as fh:
        json.dump(res, fh, indent=1, sort_keys=True, default=str)
        fh.write("\n")
    print("%s: %d files original, %d replay; %d byte-identical; %d differing; verdicts %s; unpaired %d/%d"
          % (label, len(T.A.files), len(T.B.files), len(ident), len(files), res["verdict_counts"], len(only_a), len(only_b)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
