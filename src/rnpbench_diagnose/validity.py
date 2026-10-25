"""Output validity: is this a complete, evaluable protein-RNA complex?

The point of this stage is the separation the benchmark work found necessary: a prediction can fail because
the job did not produce a usable file (TECHNICAL) or because it produced a well-formed file that is not a
protein-RNA complex (STRUCTURAL). Reporting those together, or scoring either as zero quality, is the
mistake this layer exists to prevent.
"""
CLASSES = ("VALID", "TECHNICAL_FAILURE", "STRUCTURAL_FAILURE")


def _deps():
    """The project's own loader and chain selection. Absent -> refuse, never silently degrade."""
    try:
        import score_decomp as SD
    except Exception as ex:                                  # pragma: no cover - environment dependent
        raise RuntimeError("validity requires score_decomp (the project's frozen loader and chain "
                           "selection) on sys.path; import failed: %s" % ex)
    return SD


def validity(path):
    """Classify one predicted structure. Returns a record; never raises on a bad structure."""
    SD = _deps()
    rec = {"path": path, "checks": {}, "classification": None, "detail": ""}
    import math
    import os
    if not os.path.exists(path):
        rec["classification"] = "TECHNICAL_FAILURE"
        rec["detail"] = "file_absent"
        return rec
    if os.path.getsize(path) == 0:
        rec["classification"] = "TECHNICAL_FAILURE"
        rec["detail"] = "file_empty"
        return rec
    try:
        st = SD.feat.load(path)
    except Exception as ex:
        rec["classification"] = "TECHNICAL_FAILURE"
        rec["detail"] = "load_failed:" + type(ex).__name__
        return rec
    rec["checks"]["parses"] = True
    try:
        n_models = len(st)
    except Exception:
        n_models = None
    rec["checks"]["single_model"] = (n_models == 1)
    if n_models != 1:
        rec["classification"] = "TECHNICAL_FAILURE"
        rec["detail"] = "model_count=%s" % n_models
        return rec
    pid, rid = SD.feat.contacting_pair(st)
    rec["checks"]["protein_chain_present"] = pid is not None
    rec["checks"]["rna_chain_present"] = rid is not None
    rec["checks"]["interface_object"] = (pid is not None and rid is not None)
    if pid is None or rid is None:
        rec["classification"] = "STRUCTURAL_FAILURE"
        rec["detail"] = "no_contacting_protein_rna_pair"
        return rec
    rna = [r for r in st[0][rid] if SD.b1c.base1(r) is not None]
    prot = SD.feat.prot_frames(st[0][pid])
    rec["checks"]["rna_residues_resolved"] = len(rna) > 0
    rec["checks"]["protein_residues_resolved"] = len(prot) > 0
    rec["n_rna_residues"] = len(rna)
    rec["n_protein_residues"] = len(prot)
    if not rna or not prot:
        rec["classification"] = "STRUCTURAL_FAILURE"
        rec["detail"] = "resolved_residues_absent"
        return rec
    finite = True
    for r in rna:
        c = SD.b2a.c4_of(r)
        if c is not None and not all(math.isfinite(float(v)) for v in c):
            finite = False
            break
    if finite:
        for x in prot:
            if not all(math.isfinite(float(v)) for v in x[3]):
                finite = False
                break
    rec["checks"]["coordinates_finite"] = finite
    if not finite:
        rec["classification"] = "TECHNICAL_FAILURE"
        rec["detail"] = "nonfinite_coordinate"
        return rec
    rec["classification"] = "VALID"
    return rec


def summarize(records):
    """Per-class counts, so a report can state technical and structural failure separately."""
    out = {c: 0 for c in CLASSES}
    for r in records:
        out[r["classification"]] = out.get(r["classification"], 0) + 1
    out["n_total"] = len(records)
    out["n_valid"] = out["VALID"]
    out["details"] = sorted({r["detail"] for r in records if r["detail"]})
    return out
