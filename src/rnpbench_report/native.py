"""Native (engine-own) interface confidence resolution.

An engine's own confidence is reported PER ENGINE and never compared across engines: ipTM from one engine and
an inter-chain PAE mean from another are different quantities on different scales. resolve() therefore returns
the value together with the kind, and report.py prints the kind next to every value.

An unavailable confidence is a recorded outcome, not a zero and not a missing key: UNAVAILABLE carries the
reason, so a report can distinguish "this engine publishes no interface confidence" from "the file was absent".
"""
import glob
import json
import os

import numpy as np

KIND_IPTM = "iptm"
KIND_NEG_PAE = "neg_mean_interchain_pae"


def _af3(d):
    files = sorted(glob.glob(os.path.join(d, "*_summary_confidences.json")))
    if len(files) != 1:
        return None, "UNAVAILABLE: %d AF3 summary_confidences files in %s" % (len(files), d)
    return float(json.load(open(files[0]))["iptm"]), KIND_IPTM


def _boltz2(d, model):
    stem = os.path.basename(model).rsplit(".", 1)[0]
    p = os.path.join(d, "confidence_%s.json" % stem)
    if not os.path.exists(p):
        return None, "UNAVAILABLE: no confidence_%s.json" % stem
    return float(json.load(open(p))["iptm"]), KIND_IPTM


def _chai1(d, model):
    base = os.path.basename(model)
    if "model_idx_" not in base:
        return None, "UNAVAILABLE: Chai-1 model filename carries no model_idx_"
    idx = base.split("model_idx_")[1].split(".")[0]
    p = os.path.join(d, "scores.model_idx_%s.npz" % idx)
    if not os.path.exists(p):
        return None, "UNAVAILABLE: no scores.model_idx_%s.npz" % idx
    return float(np.load(p)["iptm"][0]), KIND_IPTM


def _rf3(d, model):
    p = os.path.join(d, os.path.basename(model).replace("_model.cif", "_summary_confidences.json"))
    if not os.path.exists(p):
        return None, "UNAVAILABLE: no RF3 summary_confidences beside the model"
    return float(json.load(open(p))["iptm"]), KIND_IPTM


def _rf2na(model, chain_order):
    """RF2NA publishes no ipTM. A mean inter-chain PAE is computed from its own PAE matrix and NEGATED so that
    larger is better, matching the direction of the other engines' confidences. It remains a different quantity
    and is labelled as such. The PAE matrix must span exactly the residues parsed, or the value is refused."""
    p = model.rsplit(".", 1)[0] + ".npz"
    if not os.path.exists(p):
        return None, "UNAVAILABLE: no RF2NA .npz beside the model"
    pae = np.load(p)["pae"]
    total = sum(n for _, n, _ in chain_order)
    if pae.shape[0] != total:
        return None, "UNAVAILABLE: pae dimension %d != parsed residues %d" % (pae.shape[0], total)
    is_rna = np.concatenate([np.full(n, nucleic) for _, n, nucleic in chain_order])
    if is_rna.all() or (~is_rna).all():
        return None, "UNAVAILABLE: only one polymer type present"
    v = (pae[np.ix_(~is_rna, is_rna)].mean() + pae[np.ix_(is_rna, ~is_rna)].mean()) / 2
    return -float(v), KIND_NEG_PAE


def resolve(engine, model_path, confidence_dir, chain_order, declared=("RESOLVE_FROM_ENGINE_FILES", None)):
    """-> (value_or_None, kind_or_reason). A contract may declare the value explicitly; then nothing is read."""
    value, kind = declared
    if value != "RESOLVE_FROM_ENGINE_FILES":
        return value, (kind or "declared_in_contract")
    try:
        if engine == "AF3":
            return _af3(confidence_dir)
        if engine == "BOLTZ2":
            return _boltz2(confidence_dir, model_path)
        if engine == "CHAI1":
            return _chai1(confidence_dir, model_path)
        if engine == "RF3":
            return _rf3(confidence_dir, model_path)
        if engine == "RF2NA":
            return _rf2na(model_path, chain_order)
    except Exception as ex:
        return None, "UNAVAILABLE: %s: %s" % (type(ex).__name__, str(ex)[:120])
    return None, "UNAVAILABLE: engine %s has no confidence parser in this version" % engine
