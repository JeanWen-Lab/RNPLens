"""``rnplens import``: turn ordinary engine output folders into a confirmed, checksummed RNPLens project.

WHAT IT DOES. It inventories structure files, recognises the output layouts of the five engines RNPLens parses,
checks every chain against the construct the user declares, and writes a manifest plus the exact rc3 input files
(the Report contract and the Diagnose and Evaluate inputs). Nothing is scored here.

WHAT IT NEVER DOES.
  * It never modifies, moves or copies an original structure file. Originals are referenced by absolute path and
    SHA-256. When a transformation is needed (renumbering to construct positions, removing non-polymer chains),
    a DERIVED copy is written under the project, only after the user accepts it, and the transformation is logged.
  * It never decides anything ambiguous. An engine label that cannot be read from the layout, a chain whose
    polymer type is uncertain, or an engine's designated copy that does not match any of its samples stops the
    import with a question (exit status 3) and a resolution file to fill in.
  * It never repairs a sequence. A chain that differs from the declared construct (substitution, insertion,
    truncation) is reported with its alignment and the file is excluded; one project holds one construct.

Chain typing reuses rnpbench_report.geometry.split_chains, so a chain is protein or RNA here exactly when Report
will treat it so.
"""
import datetime
import glob
import hashlib
import json
import os
import re
import sys

MANIFEST_SCHEMA = "rnplens-project-manifest-1"
ENGINES = ("BOLTZ2", "CHAI1", "AF3", "RF3", "RF2NA", "OTHER")
EXIT_OK, EXIT_REFUSED, EXIT_NEEDS_CONFIRMATION = 0, 2, 3
STRUCT_EXT = (".cif", ".mmcif", ".pdb")
# QA O3: every other file under an input folder, and every hidden folder (not searched), is listed in manifest.json
# skipped_files with a reason; files that look like structures in a format import does not read are flagged.
COMPRESSED_EXT = (".gz", ".bz2", ".xz", ".zip", ".zst")
OTHER_STRUCT_EXT = (".ent", ".pdbx", ".bcif", ".mmtf")
SKIP_REASONS = {
    "compressed": "compressed structure file: import does not read compressed files (decompress it to import; nothing is "
                  "guessed)",
    "other_format": "structure-like file with an extension import does not read (.ent, .pdbx, .bcif, .mmtf); rename or "
                    "convert it to .pdb or .cif to import",
    "confidence": "engine confidence file of a recognised structure (read for the engine's ranking score only)",
    "hidden_folder": "hidden folder (name starts with '.'): not searched",
    "other": "not a structure file",
}
UNRECOGNISED_HINT = ("  Files in no recognised layout are imported only when you name their engine with --engine "
                     "(nothing is guessed). With --engine BOLTZ2 a confidence_<model>.json beside each file is read "
                     "for the engine's ranking; with --engine OTHER no engine confidence is used. Recognised layouts "
                     "are listed in docs/workflow.md.")

AA3 = {"ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H",
       "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
       "TYR": "Y", "VAL": "V"}
NT = {"A": "A", "C": "C", "G": "G", "U": "U", "RA": "A", "RC": "C", "RG": "G", "RU": "U"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_sequence_arg(v):
    """A sequence given directly or as a FASTA/plain-text file (one record)."""
    if v is None:
        return None
    if not os.path.isfile(v) and (os.sep in v or "/" in v or v.lower().endswith((".fa", ".fasta", ".fna", ".faa", ".txt", ".seq"))):
        raise ValueError("sequence file not found: %s" % v)
    if os.path.isfile(v):
        lines = [l.strip() for l in open(v, encoding="utf-8") if l.strip()]
        if sum(l.startswith(">") for l in lines) > 1:
            raise ValueError("%s holds more than one FASTA record; give one sequence" % v)
        v = "".join(l for l in lines if not l.startswith(">"))
    s = "".join(v.split()).upper()
    if not s or not re.fullmatch(r"[A-Z]+", s):
        raise ValueError("sequence contains characters other than letters")
    return s


# ---------------------------------------------------------------- layout recognition
def _boltz2(paths):
    """boltz_results_<T>/predictions/<T>/<T>_model_<k>.(pdb|cif) with confidence_<T>_model_<k>.json."""
    out = []
    for p in paths:
        m = re.search(r"boltz_results_([^/]+)/predictions/([^/]+)/(\2)_model_(\d+)\.(pdb|cif)$", p)
        if not m:
            continue
        d = os.path.dirname(p); stem = os.path.basename(p).rsplit(".", 1)[0]
        conf = os.path.join(d, "confidence_%s.json" % stem)
        score = None
        if os.path.exists(conf):
            try:
                score = float(json.load(open(conf))["confidence_score"])
            except Exception:
                score = None
        root = p[:m.start()].rstrip("/")
        out.append({"engine": "BOLTZ2", "path": p, "run_root": root or "/", "boltz_dir": p[:m.end(1)],
                    "sample": int(m.group(4)),
                    "confidence_dir": d, "ranking_score": score, "ranking_kind": "Boltz-2 confidence_score",
                    "engine_rank_hint": int(m.group(4))})
    return out


def _boltz2_flat(paths):
    """<T>_model_<k>.(pdb|cif) next to confidence_<T>_model_<k>.json holding a numeric "confidence_score".

    This is the Boltz-2 output copied out of its boltz_results_<T>/predictions/<T>/ nesting (6DCB first-use test,
    finding M1). The file name alone is not used: the layout is recognised only when Boltz-2's own confidence
    file, with Boltz-2's own key, sits beside the structure. Anything else stays unrecognised."""
    out = []
    for p in paths:
        m = re.search(r"/([^/]+)_model_(\d+)\.(pdb|cif)$", p)
        if not m:
            continue
        d = os.path.dirname(p); stem = os.path.basename(p).rsplit(".", 1)[0]
        conf = os.path.join(d, "confidence_%s.json" % stem)
        try:
            score = float(json.load(open(conf))["confidence_score"])
        except Exception:
            continue
        out.append({"engine": "BOLTZ2", "layout": "Boltz-2 flat (model file with confidence_*.json)", "path": p,
                    "run_root": d, "sample": stem, "confidence_dir": d, "ranking_score": score,
                    "ranking_kind": "Boltz-2 confidence_score",
                    "engine_source": "output layout (Boltz-2 confidence_*.json with confidence_score beside the file)"})
    return out


def _chai1(paths):
    out = []
    for p in paths:
        m = re.search(r"pred\.model_idx_(\d+)\.cif$", p)
        if not m:
            continue
        d = os.path.dirname(p); npz = os.path.join(d, "scores.model_idx_%s.npz" % m.group(1))
        score = None
        if os.path.exists(npz):
            try:
                import numpy as np
                score = float(np.load(npz)["aggregate_score"].reshape(-1)[0])
            except Exception:
                score = None
        out.append({"engine": "CHAI1", "path": p, "run_root": d, "sample": int(m.group(1)), "confidence_dir": d,
                    "ranking_score": score, "ranking_kind": "Chai-1 aggregate_score"})
    return out


def _af3_style(paths):
    """AF3 and RF3 write the same layout: <T>/seed-<s>_sample-<k>/<T>_seed-<s>_sample-<k>_model.cif plus a
    top-level <T>/<T>_model.cif that copies the top-ranked sample. The engine cannot be read from the layout."""
    out, tops = [], []
    for p in paths:
        m = re.search(r"/([^/]+)/seed-(\d+)_sample-(\d+)/\1_seed-\2_sample-\3_model\.cif$", p)
        if m:
            d = os.path.dirname(p); sc = p.replace("_model.cif", "_summary_confidences.json")
            score = None
            if os.path.exists(sc):
                try:
                    score = float(json.load(open(sc))["ranking_score"])
                except Exception:
                    score = None
            out.append({"engine": None, "layout": "AF3-style", "path": p, "run_root": os.path.dirname(d),
                        "sample": "seed-%s_sample-%s" % (m.group(2), m.group(3)), "confidence_dir": d,
                        "ranking_score": score, "ranking_kind": "ranking_score (summary_confidences.json)",
                        "has_af3_terms": os.path.exists(os.path.join(os.path.dirname(d), "TERMS_OF_USE.md"))})
            continue
        m2 = re.search(r"/([^/]+)/\1_model\.cif$", p)
        if m2 and glob.glob(os.path.join(os.path.dirname(p), "seed-*_sample-*")):
            tops.append(p)
    return out, tops


def _rf2na(paths):
    out = []
    for p in paths:
        m = re.search(r"/models/model_(\d+)\.pdb$", p)
        if not m:
            continue
        d = os.path.dirname(p)
        out.append({"engine": "RF2NA", "path": p, "run_root": os.path.dirname(d), "sample": int(m.group(1)),
                    "confidence_dir": d, "ranking_score": None, "ranking_kind": None})
    return out


def _sidecar_score(engine, f):
    d, stem = os.path.dirname(f), os.path.basename(f).rsplit(".", 1)[0]
    try:
        if engine == "BOLTZ2" and os.path.exists(os.path.join(d, "confidence_%s.json" % stem)):
            return float(json.load(open(os.path.join(d, "confidence_%s.json" % stem)))["confidence_score"]), "Boltz-2 confidence_score"
        if engine in ("AF3", "RF3") and os.path.exists(f.replace("_model.cif", "_summary_confidences.json")) and f.endswith("_model.cif"):
            return float(json.load(open(f.replace("_model.cif", "_summary_confidences.json")))["ranking_score"]), "ranking_score (summary_confidences.json)"
    except Exception:
        pass
    return None, None


def find_structures(inputs):
    files = []
    for a in inputs:
        a = os.path.abspath(a)
        if os.path.isfile(a):
            files.append(a)
        elif os.path.isdir(a):
            for dp, dn, fn in os.walk(a):
                dn[:] = sorted(x for x in dn if not x.startswith("."))
                files += [os.path.join(dp, f) for f in sorted(fn) if f.lower().endswith(STRUCT_EXT)]
        else:
            raise FileNotFoundError(a)
    return sorted(set(files))


def _sidecars(recs):
    """Engine confidence files beside recognised structures (Boltz-2, Chai-1, AF3/RF3 naming)."""
    out = set()
    for r in recs:
        p = r["path"]; d = os.path.dirname(p); stem = os.path.basename(p).rsplit(".", 1)[0]
        out.add(os.path.join(d, "confidence_%s.json" % stem))
        m = re.search(r"pred\.model_idx_(\d+)\.cif$", p)
        if m:
            out.add(os.path.join(d, "scores.model_idx_%s.npz" % m.group(1)))
        if p.endswith("_model.cif"):
            out.add(p.replace("_model.cif", "_summary_confidences.json"))
    return out


def skipped_files(inputs, recs):
    """Every file under the input folders that is not a candidate structure file, and every hidden folder (which is
    not searched), each with a reason (QA O3). Structure files themselves are reported elsewhere (structures,
    unrecognised_files, decisions)."""
    side, out = _sidecars(recs), []
    for a in inputs:
        a = os.path.abspath(a)
        if not os.path.isdir(a):
            continue
        for dp, dn, fn in os.walk(a):
            for x in sorted(x for x in dn if x.startswith(".")):
                out.append({"path": os.path.join(dp, x), "kind": "folder", "structure_like": False,
                            "reason": SKIP_REASONS["hidden_folder"]})
            dn[:] = sorted(x for x in dn if not x.startswith("."))
            for f in sorted(fn):
                low, p = f.lower(), os.path.join(dp, f)
                if low.endswith(STRUCT_EXT):
                    continue
                base = low[: -len(next(e for e in COMPRESSED_EXT if low.endswith(e)))] if low.endswith(COMPRESSED_EXT) else None
                if base is not None and base.endswith(STRUCT_EXT + OTHER_STRUCT_EXT):
                    key = "compressed"
                elif low.endswith(OTHER_STRUCT_EXT):
                    key = "other_format"
                elif p in side:
                    key = "confidence"
                else:
                    key = "other"
                out.append({"path": p, "kind": "file", "structure_like": key in ("compressed", "other_format"),
                            "reason": SKIP_REASONS[key]})
    seen, uniq = set(), []
    for x in sorted(out, key=lambda x: x["path"]):
        if x["path"] not in seen:
            seen.add(x["path"]); uniq.append(x)
    return uniq


def designated_exclusion(man, row):
    """QA O4: None when the run's engine-designated structure was analysed (or there is none); otherwise the text
    'excluded at import (<VERDICT>); not analysed[: reasons]'. Works from man['structures'], so also for manifests
    written before run rows carried designated_included."""
    ex = row.get("designated_execution")
    if not ex:
        return None
    s = next((s for s in man.get("structures") or [] if s.get("execution") == ex and s.get("engine") == row.get("engine")), None)
    if s is None or s.get("verdict") == "INCLUDED":
        return None
    return "excluded at import (%s); not analysed%s" % (s.get("verdict"), (": " + "; ".join(s["reasons"])) if s.get("reasons") else "")


def recognise(files, engine_override=None):
    """-> (records, top_level_copies, unrecognised). A record is one candidate structure."""
    recs = []
    claimed = set()
    for fn in (_boltz2, _boltz2_flat, _chai1, _rf2na):
        for r in fn([f for f in files if f not in claimed]):
            recs.append(r); claimed.add(r["path"])
    af, tops = _af3_style([f for f in files if f not in claimed])
    for r in af:
        recs.append(r); claimed.add(r["path"])
    claimed |= set(tops)
    rest = [f for f in files if f not in claimed]
    if engine_override:
        for r in recs:
            if r["engine"] is None or engine_override == r["engine"]:
                r["engine"] = engine_override
                r.pop("engine_source", None)
            elif r["engine"] != engine_override:
                r["engine_conflict"] = "layout is %s but --engine %s was given" % (r["engine"], engine_override)
        # files in no recognised layout are accepted only because the user named their engine; the run is the
        # folder, the sample is the file name, and the engine's ranking score is read from a sidecar if present
        for f in rest:
            sc, kind = _sidecar_score(engine_override, f)
            recs.append({"engine": engine_override, "engine_source": "--engine (generic layout)", "path": f,
                         "run_root": os.path.dirname(f), "sample": os.path.basename(f).rsplit(".", 1)[0],
                         "confidence_dir": os.path.dirname(f), "ranking_score": sc, "ranking_kind": kind})
        rest = []
    return recs, tops, rest


# ---------------------------------------------------------------- chain correspondence
def _one_letter(name, kind):
    if kind == "protein":
        if name in AA3:
            return AA3[name], True
    elif name in NT:
        return NT[name], True
    try:
        import gemmi
        t = gemmi.find_tabulated_residue(name)
        if t is not None and t.one_letter_code.strip() and t.one_letter_code not in "?":
            return t.one_letter_code.upper(), False
    except Exception:
        pass
    return "X", False


def _polymer_class(name):
    if name in AA3 or name in NT:
        return "polymer"
    try:
        import gemmi
        t = gemmi.find_tabulated_residue(name)
        if t is not None and (t.is_amino_acid() or t.is_nucleic_acid()):
            return "polymer"
    except Exception:
        pass
    return "nonpolymer"


def align_summary(seq, ref):
    """Global alignment of a chain sequence to the declared construct: identity, substitutions, gaps."""
    from Bio import Align
    al = Align.PairwiseAligner(mode="global", match_score=1, mismatch_score=-1, open_gap_score=-2,
                               extend_gap_score=-0.5)
    a = al.align(seq, ref)[0]
    s1, s2 = a[0], a[1]
    subs = sum(1 for x, y in zip(s1, s2) if x != "-" and y != "-" and x != y)
    gaps = sum(1 for x, y in zip(s1, s2) if x == "-" or y == "-")
    ident = sum(1 for x, y in zip(s1, s2) if x == y and x != "-")
    first = [i + 1 for i, (x, y) in enumerate(zip(s1, s2)) if x != y][:5]
    return {"identity_over_construct": round(ident / len(ref), 4), "substitutions": subs, "gap_columns": gaps,
            "first_differing_alignment_columns": first}


def examine_chains(path, protein_seq, rna_seq):
    """Classify each chain of one structure against the declared construct, with Report's own chain typing."""
    from rnpbench_report import geometry
    model = geometry.parse_model(path)
    prot, rna, _ = geometry.split_chains(model)
    chains, issues = [], []
    for kind, group, ref in (("protein", prot, protein_seq), ("rna", rna, rna_seq)):
        for cid, res in group:
            names = [x.get_resname().strip() for x in res]
            cls = [_polymer_class(n) for n in names]
            npoly = sum(c == "polymer" for c in cls)
            row = {"chain": cid, "type_by_report": kind, "n_residues": len(res), "n_nonpolymer_residues": len(res) - npoly}
            if npoly == 0:
                row["status"] = "NONPOLYMER_CHAIN"
                chains.append(row); continue
            if kind == "protein":
                nuc_like = sum(n in NT for n in names)
                if nuc_like and nuc_like / len(names) > 0.2:
                    row["status"] = "TYPE_UNCERTAIN"; row["detail"] = "%d of %d residue names are nucleotides" % (nuc_like, len(names))
                    chains.append(row); continue
            poly = [x for x, c in zip(res, cls) if c == "polymer"]
            letters = [_one_letter(x.get_resname().strip(), kind) for x in poly]
            seq = "".join(l for l, _ in letters)
            row["nonstandard_residues"] = sorted({x.get_resname().strip() for (l, std), x in zip(letters, poly) if not std})
            nums = [x.id[1] for x in poly]; icodes = [x.id[2].strip() for x in poly]
            row["numbering"] = {"first": nums[0], "last": nums[-1], "insertion_codes": sum(1 for c in icodes if c)}
            if seq == ref:
                offs = {n - (i + 1) for i, n in enumerate(nums)}
                if offs == {0} and not any(icodes):
                    row["status"] = "EXACT"
                else:
                    row["status"] = "RENUMBER"
                    row["offset"] = offs.pop() if len(offs) == 1 and not any(icodes) else None
                if row["n_nonpolymer_residues"]:
                    row["status"] += "+STRIP_RESIDUES"
            else:
                row["status"] = "SEQUENCE_DIFFERS"
                row["alignment"] = align_summary(seq, ref)
            chains.append(row)
    return chains


NOT_IN_MAPPING = "NOT_IN_MAPPING"


def apply_chain_mapping(chains, mapping):
    """0.4 additive (rnplens clarify): apply a chain mapping recorded by the user, "protein=A;rna=B". Polymer chains
    of a named type that are not chosen get status NOT_IN_MAPPING and are removed in the derived copy (the original
    file is unchanged). Used only when a resolution answer "chainmap:<path>" is supplied. -> error text or None."""
    want = {}
    for part in [x for x in str(mapping).split(";") if x.strip()]:
        k, _, v = part.partition("=")
        want[k.strip()] = {c for c in v.split(",") if c}
    have = {c["chain"] for c in chains}
    for kind, ids in want.items():
        if kind not in ("protein", "rna") or not ids or not ids <= have:
            return "recorded chain mapping %r names chains not present in the file" % mapping
    for c in chains:
        if c["type_by_report"] in want and c["chain"] not in want[c["type_by_report"]] and c["status"] != "NONPOLYMER_CHAIN":
            c["status"] = NOT_IN_MAPPING
    return None


def file_verdict(chains):
    """One structure -> INCLUDED / NEEDS_DERIVED_COPY / NEEDS_CONFIRMATION / INCOMPATIBLE, with reasons."""
    st = [c["status"] for c in chains]
    polymer = [c for c in chains if c["status"] not in ("NONPOLYMER_CHAIN", NOT_IN_MAPPING)]
    reasons = []
    if not any(c["type_by_report"] == "protein" and c["status"] not in ("NONPOLYMER_CHAIN", NOT_IN_MAPPING) for c in chains):
        reasons.append("no protein chain")
    if not any(c["type_by_report"] == "rna" and c["status"] != NOT_IN_MAPPING for c in chains):
        reasons.append("no RNA chain")
    differ = [c["chain"] for c in polymer if c["status"] == "SEQUENCE_DIFFERS"]
    if differ:
        reasons.append("chain(s) %s differ from the declared construct" % ",".join(differ))
    if reasons:
        return "INCOMPATIBLE", reasons
    if any(s == "TYPE_UNCERTAIN" for s in st):
        return "NEEDS_CONFIRMATION", ["chain polymer type uncertain: %s" % ",".join(c["chain"] for c in chains if c["status"] == "TYPE_UNCERTAIN")]
    if any(s in ("NONPOLYMER_CHAIN", NOT_IN_MAPPING) or s.startswith("RENUMBER") or s.endswith("+STRIP_RESIDUES") for s in st):
        t = []
        if any(s == "NONPOLYMER_CHAIN" for s in st):
            t.append("remove non-polymer chain(s) %s" % ",".join(c["chain"] for c in chains if c["status"] == "NONPOLYMER_CHAIN"))
        if any(s == NOT_IN_MAPPING for s in st):
            t.append("remove chain(s) %s, which are not in the recorded chain mapping" % ",".join(c["chain"] for c in chains if c["status"] == NOT_IN_MAPPING))
        if any(s.endswith("+STRIP_RESIDUES") for s in st):
            t.append("remove non-polymer residues inside polymer chains")
        if any(s.startswith("RENUMBER") for s in st):
            t.append("renumber chain(s) %s to construct positions 1..L" % ",".join(c["chain"] for c in chains if c["status"].startswith("RENUMBER")))
        return "NEEDS_DERIVED_COPY", t
    return "INCLUDED", []


def write_derived(src, dst, chains):
    """Derived copy: drop non-polymer chains and residues, renumber polymer residues 1..L in order. gemmi writes
    mmCIF; the basename is kept so engine confidence files can still be located beside the original."""
    import gemmi
    st = gemmi.read_structure(src)
    st.setup_entities()
    keep = {c["chain"] for c in chains if c["status"] not in ("NONPOLYMER_CHAIN", NOT_IN_MAPPING)}
    for m in st:
        for ch in list(m):
            if ch.name not in keep:
                m.remove_chain(ch.name)
        for ch in m:
            for i in range(len(ch) - 1, -1, -1):
                if _polymer_class(ch[i].name) != "polymer" or ch[i].name == "HOH":
                    del ch[i]
            for i, r in enumerate(ch):
                r.seqid = gemmi.SeqId(i + 1, " ")
    os.makedirs(os.path.dirname(dst), exist_ok=False)
    if dst.endswith(".pdb"):
        st.write_pdb(dst)
    else:
        st.make_mmcif_document().write_file(dst)
    os.chmod(dst, 0o444)


# ---------------------------------------------------------------- the import
def run(inputs, protein_seq, rna_seq, out, case_id=None, engine=None, answers=None, accept_derived=False):
    if os.path.exists(out):
        print("rnplens import: refused: %s exists (nothing is overwritten)" % out, file=sys.stderr)
        return EXIT_REFUSED
    if engine and engine not in ENGINES:
        print("rnplens import: --engine must be one of %s" % ", ".join(ENGINES), file=sys.stderr)
        return EXIT_REFUSED
    answers = dict(answers or {})
    try:
        files = find_structures(inputs)
    except FileNotFoundError as ex:
        print("rnplens import: refused: input path not found: %s (nothing was written)" % ex, file=sys.stderr)
        return EXIT_REFUSED
    recs, tops, unrec = recognise(files, engine)
    skipped = skipped_files(inputs, recs)
    struct_like = [x for x in skipped if x["structure_like"]]
    questions, decisions = [], []

    # engine labels for AF3-style runs
    for r in recs:
        if r["engine"] is None:
            key = "engine:" + r["run_root"]
            a = answers.get(key)
            if a in ("AF3", "RF3"):
                r["engine"] = a; r["engine_source"] = "resolution file"
            else:
                if key not in [q["id"] for q in questions]:
                    hint = " (TERMS_OF_USE.md present, as AF3 writes)" if r.get("has_af3_terms") else ""
                    questions.append({"id": key, "question": "AF3 and RF3 write the same layout; which engine produced %s?%s"
                                      % (r["run_root"], hint), "options": ["AF3", "RF3"]})
        else:
            r.setdefault("engine_source", "output layout" if not engine else "--engine")
        if r.get("engine_conflict"):
            print("rnplens import: refused: %s (%s)" % (r["engine_conflict"], r["path"]), file=sys.stderr)
            return EXIT_REFUSED

    # runs and labels
    # One Boltz-2 output folder (boltz_results_<T>) is one run. Its run is named after the folder above it, so
    # that exec_A/boltz_results_T and exec_B/boltz_results_T stay runs exec_A and exec_B; when one folder holds
    # several boltz_results_<T> folders (several predictions written to one --out_dir), each of them is its own run.
    by_root = {}
    for r in recs:
        if r.get("boltz_dir"):
            by_root.setdefault(r["run_root"], set()).add(r["boltz_dir"])
    for r in recs:
        if r.get("boltz_dir") and len(by_root[r["run_root"]]) > 1:
            r["run_root"] = r["boltz_dir"]
    roots = sorted({r["run_root"] for r in recs})
    common = os.path.commonpath(roots) if len(roots) > 1 else os.path.dirname(roots[0]) if roots else ""
    for r in recs:
        rel = os.path.relpath(r["run_root"], common) if common else r["run_root"]
        r["run"] = rel if rel != "." else os.path.basename(r["run_root"])
        r["execution"] = "%s#%s" % (r["run"], r["sample"])
    # every structure must keep its own (engine, run#sample) label: Report refuses a contract that repeats one,
    # and a shared label would merge two structures' identities. Refuse before anything is written.
    labels = {}
    for r in recs:
        labels.setdefault((str(r["engine"]), r["execution"]), []).append(r["path"])
    clashes = {k: v for k, v in labels.items() if len(v) > 1}
    if clashes:
        print("rnplens import: refused: %d label(s) would be shared by more than one structure file; every structure "
              "needs its own run and sample label (run = output folder, sample = model index or file name). "
              "Nothing was written." % len(clashes), file=sys.stderr)
        for (eng, ex), paths in sorted(clashes.items()):
            print("  same run and sample label %s %s: %s" % (eng, ex, ", ".join(paths)), file=sys.stderr)
        print("  Put each run in its own folder (or keep one file format per model) and import again.", file=sys.stderr)
        return EXIT_REFUSED

    # checksums, chains, verdicts
    for r in recs:
        r["original_sha256"] = sha256(r["path"])
        try:
            r["chains"] = examine_chains(r["path"], protein_seq, rna_seq)
            err = apply_chain_mapping(r["chains"], answers["chainmap:" + r["path"]]) if answers.get("chainmap:" + r["path"]) else None
            r["verdict"], r["reasons"] = ("INCOMPATIBLE", [err]) if err else file_verdict(r["chains"])
        except Exception as ex:
            r["chains"], r["verdict"], r["reasons"] = [], "UNREADABLE", ["%s: %s" % (type(ex).__name__, str(ex)[:160])]
        if r["verdict"] == "NEEDS_CONFIRMATION":
            key = "chains:" + r["path"]
            if answers.get(key) == "exclude_file":
                r["verdict"], r["reasons"] = "EXCLUDED_BY_USER", r["reasons"] + ["excluded in the resolution file"]
            else:
                questions.append({"id": key, "question": "%s: %s. Exclude this file?" % (r["path"], "; ".join(r["reasons"])),
                                  "options": ["exclude_file"]})
        dans = answers.get("derived:" + r["path"])   # 0.4 additive: per-file answer recorded by rnplens clarify
        if r["verdict"] == "NEEDS_DERIVED_COPY" and not accept_derived and dans == "exclude_file":
            r["verdict"], r["reasons"] = "EXCLUDED_BY_USER", r["reasons"] + ["excluded in the resolution file"]
        if r["verdict"] == "NEEDS_DERIVED_COPY" and not accept_derived and dans != "accept":
            questions.append({"id": "derived:" + r["path"], "question": "%s needs a derived copy: %s. Accept with "
                              "--accept-derived (the original is kept unchanged)." % (r["path"], "; ".join(r["reasons"])),
                              "options": ["--accept-derived"]})

    # duplicate files (same bytes reachable twice)
    seen = {}
    for r in recs:
        if r["original_sha256"] in seen and r["verdict"] in ("INCLUDED", "NEEDS_DERIVED_COPY"):
            r["verdict"], r["reasons"] = "DUPLICATE", ["byte-identical to %s" % seen[r["original_sha256"]]]
        seen.setdefault(r["original_sha256"], r["path"])

    # designated structure per run
    runs = {}
    for r in recs:
        runs.setdefault((r["engine"], r["run"]), []).append(r)
    run_rows = []
    for (eng, run_), rs in sorted(runs.items(), key=lambda x: (str(x[0][0]), x[0][1])):
        scored = [x for x in rs if x["ranking_score"] is not None]
        chosen = answers.get("designated:" + rs[0]["run_root"])   # 0.4 additive: designation recorded by rnplens clarify
        if chosen == "none":
            des, rule = None, "no designated structure (recorded answer)"
        elif chosen and any(x["execution"] == chosen for x in rs):
            des, rule = next(x for x in rs if x["execution"] == chosen), "chosen in a recorded answer"
        elif len(rs) == 1:
            des, rule = rs[0], "only structure of the run"
        elif scored and len(scored) == len(rs):
            des = max(rs, key=lambda x: (x["ranking_score"], -rs.index(x)))
            rule = "highest %s" % rs[0]["ranking_kind"]
        else:
            des, rule = None, "not determinable: the engine's ranking score is not available for every structure"
        for x in rs:
            x["designated"] = des is x
        run_rows.append({"engine": eng, "run": run_, "n_structures": len(rs), "designated_rule": rule,
                         "designated_execution": des["execution"] if des else None})

    # top-level copies (AF3-style): must equal the designated sample's coordinates
    for t in tops:
        cand = [r for r in recs if r["run_root"] == os.path.dirname(t) and r.get("designated")]
        same = bool(cand) and _same_coordinates(t, cand[0]["path"])
        decisions.append({"file": t, "decision": "not imported as a candidate: the engine's copy of its designated "
                          "sample" + (" (coordinates equal %s)" % cand[0]["path"] if same else ""), "verified": same})
        if not same and answers.get("top:" + t) != "ignore":
            questions.append({"id": "top:" + t, "question": "%s is the engine's top-level model but its coordinates "
                              "match no single designated sample. Ignore it?" % t, "options": ["ignore"]})

    if questions:
        os.makedirs(out)
        qf = os.path.join(out, "QUESTIONS.json")
        json.dump({"questions": questions, "how_to_answer": "copy this file, set each answer, rerun with --resolve FILE "
                   "into a new --out directory", "answers": {q["id"]: None for q in questions}}, open(qf, "w"), indent=1)
        print("rnplens import: %d question(s) need your decision; nothing was imported. See %s" % (len(questions), qf))
        for q in questions:
            print("  - " + q["question"])
        return EXIT_NEEDS_CONFIRMATION

    # nothing to import: refuse, write nothing (6DCB first-use test, findings M1 and m9)
    if not any(r["verdict"] in ("INCLUDED", "NEEDS_DERIVED_COPY") for r in recs):
        print("rnplens import: refused: no structure can be included (%d structure file(s) found, %d in a recognised "
              "layout, %d in no recognised layout). Nothing was written." % (len(files), len(recs), len(unrec)),
              file=sys.stderr)
        for r in recs:
            print("  not includable %s: %s (%s)" % (r["path"], r["verdict"], "; ".join(r["reasons"])), file=sys.stderr)
        for x in struct_like:
            print("  not imported %s: %s" % (x["path"], x["reason"]), file=sys.stderr)
        if skipped:
            print("  %d other file(s) or hidden folder(s) under the inputs were not imported (%d structure-like, named "
                  "above)." % (len(skipped), len(struct_like)), file=sys.stderr)
        if unrec:
            print(UNRECOGNISED_HINT, file=sys.stderr)
        return EXIT_REFUSED

    # write the project
    os.makedirs(os.path.join(out, "derived"))
    for i, r in enumerate(recs):
        r["id"] = "s%03d" % (i + 1)
        r["used_path"], r["used_sha256"], r["derived"] = r["path"], r["original_sha256"], None
        if r["verdict"] == "NEEDS_DERIVED_COPY":
            dst = os.path.join(out, "derived", r["id"], os.path.basename(r["path"]))
            write_derived(r["path"], dst, r["chains"])
            r["used_path"], r["used_sha256"] = os.path.abspath(dst), sha256(dst)
            r["derived"] = {"from": r["path"], "from_sha256": r["original_sha256"], "transformations": r["reasons"]}
            post = examine_chains(dst, protein_seq, rna_seq)
            if file_verdict(post)[0] != "INCLUDED":
                r["verdict"], r["reasons"] = "INCOMPATIBLE", ["derived copy did not verify: %s" % file_verdict(post)[1]]
            else:
                r["verdict"] = "INCLUDED"
    inc = [r for r in recs if r["verdict"] == "INCLUDED"]
    for row in run_rows:                       # QA O4: is the engine-designated structure the one that is analysed?
        des = next((x for x in recs if x["execution"] == row["designated_execution"] and x["engine"] == row["engine"]), None) \
            if row["designated_execution"] else None
        row["designated_verdict"] = des["verdict"] if des else None
        row["designated_included"] = (des["verdict"] == "INCLUDED") if des else None
        note = designated_exclusion({"structures": recs}, row)
        row["designated_note"] = ("the engine-designated structure %s was %s" % (row["designated_execution"], note)) if note else None
    # reported, never silent: structure files read through a symbolic link (the file itself or a linked folder)
    links = [{"path": r["path"], "target": os.path.realpath(r["path"])} for r in recs if os.path.realpath(r["path"]) != os.path.abspath(r["path"])]
    cid = case_id or os.path.basename(os.path.abspath(out))
    keep = ("id", "engine", "engine_source", "run", "sample", "execution", "path", "original_sha256", "used_path",
            "used_sha256", "derived", "confidence_dir", "ranking_score", "ranking_kind", "designated", "chains",
            "verdict", "reasons")
    man = {"manifest": MANIFEST_SCHEMA, "rnplens_version": _version(),
           "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "case_id": cid, "inputs": [os.path.abspath(a) for a in inputs],
           "construct": {"protein_sequence": protein_seq, "rna_sequence": rna_seq,
                         "protein_length": len(protein_seq), "rna_length": len(rna_seq)},
           "structures": [{k: r.get(k) for k in keep} for r in recs], "runs": run_rows,
           "unrecognised_files": unrec, "skipped_files": skipped, "decisions": decisions, "resolution_answers": answers,
           "accepted_derived_copies": bool(accept_derived),
           **({"symlinked_files": links} if links else {}),
           "counts": {"found": len(files), "candidates": len(recs), "included": len(inc),
                      "excluded": len(recs) - len(inc), "unrecognised": len(unrec), "engine_top_level_copies": len(tops),
                      "skipped_files": len(skipped), "skipped_structure_like": len(struct_like)}}
    from rnpbench_report import contract as report_contract      # declare and digest each engine confidence file
    con_outs = []
    for r in inc:
        o = {"engine": r["engine"], "execution": r["execution"], "structure_path": r["used_path"],
             "sha256": r["used_sha256"], "confidence_dir": r["confidence_dir"]}
        if r["engine"] == "OTHER":
            o.update(native_confidence=None, native_confidence_kind=None)
        else:
            report_contract.declare_confidence_input(o)
        con_outs.append(o)
    contract = {"schema_version": "rnpbench-predict-contract-1", "case_id": cid,
                "construct": {"protein_length": len(protein_seq), "rna_length": len(rna_seq),
                              "protein_sequence": protein_seq, "rna_sequence": rna_seq},
                "outputs": con_outs}
    json.dump(man, open(os.path.join(out, "manifest.json"), "x"), indent=1)
    json.dump(contract, open(os.path.join(out, "report_contract.json"), "x"), indent=1)
    open(os.path.join(out, "construct_protein.fasta"), "x").write(">protein\n%s\n" % protein_seq)
    open(os.path.join(out, "construct_rna.fasta"), "x").write(">rna\n%s\n" % rna_seq)
    print("rnplens import: %d structure file(s) found, %d candidate(s) recognised, %d included, %d excluded, %d unrecognised"
          % (len(files), len(recs), len(inc), len(recs) - len(inc), len(unrec)))
    for r in recs:
        if r["verdict"] != "INCLUDED":
            print("  excluded %s: %s (%s)" % (r["path"], r["verdict"], "; ".join(r["reasons"])))
        elif r["derived"]:
            print("  derived copy for %s: %s" % (r["path"], "; ".join(r["derived"]["transformations"])))
    for row in run_rows:
        print("  run %s (%s): %d structure(s); designated: %s%s" % (row["run"], row["engine"], row["n_structures"],
                                                                    row["designated_execution"] or row["designated_rule"],
                                                                    " - EXCLUDED at import (%s); not analysed" % row["designated_verdict"]
                                                                    if row.get("designated_included") is False else ""))
    if links:
        print("  note: %d structure file(s) were read through a symbolic link; the link targets are listed under "
              "symlinked_files in manifest.json:" % len(links))
        for x in links[:10]:
            print("    %s -> %s" % (x["path"], x["target"]))
    if unrec:
        print("  note: %d file(s) in no recognised layout were not imported (listed under unrecognised_files in "
              "manifest.json)." % len(unrec))
        print(UNRECOGNISED_HINT)
    for x in struct_like:
        print("  not imported %s: %s" % (x["path"], x["reason"]))
    if skipped:
        print("  note: %d other file(s) or hidden folder(s) under the inputs were not imported (%d structure-like); each "
              "is listed with its reason under skipped_files in manifest.json." % (len(skipped), len(struct_like)))
    print("  project written to %s" % os.path.abspath(out))
    return EXIT_OK


def _same_coordinates(a, b, tol=1e-3):
    import gemmi
    import numpy as np
    def xyz(p):
        st = gemmi.read_structure(p)
        return np.array([at.pos.tolist() for ch in st[0] for r in ch for at in r])
    try:
        x, y = xyz(a), xyz(b)
        return x.shape == y.shape and float(np.abs(x - y).max()) <= tol
    except Exception:
        return False


def _version():
    from . import __version__
    return __version__


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="rnplens import", description="Inventory predicted protein-RNA complexes from "
                                 "engine output folders, check every chain against the declared construct, and write a "
                                 "checksummed project (manifest and rc3 tool inputs). Original files are never changed.")
    ap.add_argument("paths", nargs="+", help="output folders or structure files")
    ap.add_argument("--protein-seq", required=True, help="protein construct sequence, or a FASTA file")
    ap.add_argument("--rna-seq", required=True, help="RNA construct sequence, or a FASTA file")
    ap.add_argument("--out", required=True, help="project directory to create (must not exist)")
    ap.add_argument("--case-id", help="name for the complex (default: the --out folder name)")
    ap.add_argument("--engine", choices=ENGINES, help="engine label for every file (required for AF3/RF3 layouts "
                    "unless given in --resolve, and for files in no recognised layout). BOLTZ2 reads "
                    "confidence_<model>.json beside each file if present; AF3/RF3 read *_summary_confidences.json; "
                    "OTHER accepts any structure files, without engine confidence")
    ap.add_argument("--resolve", help="answers to the questions of a previous run (QUESTIONS.json, edited)")
    ap.add_argument("--accept-derived", action="store_true", help="accept derived copies (renumbering to construct "
                    "positions, removal of non-polymer chains or residues); originals are kept unchanged")
    a = ap.parse_args(argv)
    try:
        ps, rs = read_sequence_arg(a.protein_seq), read_sequence_arg(a.rna_seq)
    except ValueError as ex:
        print("rnplens import: refused: %s" % ex, file=sys.stderr)
        return EXIT_REFUSED
    if set(rs) - set("ACGUN"):
        print("rnplens import: refused: --rna-seq must use A, C, G, U (N for unknown)", file=sys.stderr)
        return EXIT_REFUSED
    answers = {}
    if a.resolve:
        d = json.load(open(a.resolve, encoding="utf-8"))
        answers = {k: v for k, v in d.get("answers", d).items() if v is not None}
    return run(a.paths, ps, rs, a.out, a.case_id, a.engine, answers, a.accept_derived)
