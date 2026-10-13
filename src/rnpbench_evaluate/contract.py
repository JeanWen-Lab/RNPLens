"""Input contract RNPBENCH_EVALUATE_INPUT_V1 (documented in docs/INPUT_CONTRACT.md).

Validation here only REFUSES inputs the frozen rules cannot interpret, and RECORDS checks; it never
alters an input, guesses a chain, or substitutes a value.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

CONTRACT_ID = "RNPBENCH_EVALUATE_INPUT_V1"
PROTEIN_ALPHABET = set("ACDEFGHIKLMNPQRSTVWYX")
RNA_ALPHABET = set("ACGU")
RNA_UNKNOWN = set("X")   # the frozen benchmark key uses X for a non-standard nucleotide; the frozen pipeline scores such targets
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class ContractError(ValueError):
    """The input cannot be evaluated under the frozen rules. The message says why."""


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_fasta_or_raw(text):
    lines = [l.strip() for l in text.strip().splitlines() if l.strip() and not l.startswith(">")]
    return "".join(lines).upper()


def _reference_checks(ref, prot, rna):
    import gemmi
    try:
        doc = gemmi.cif.read(ref)
        blk = doc.sole_block()
    except Exception as ex:
        raise ContractError("reference is not a readable single-block mmCIF file (%s). The frozen correspondence "
                            "reads construct positions from _atom_site.label_seq_id, so mmCIF is required." % type(ex).__name__)
    tab = blk.find("_atom_site.", ["label_seq_id"])
    if not len(tab):
        raise ContractError("reference mmCIF has no _atom_site.label_seq_id column; construct positions cannot be read")
    seqs = []
    cat = blk.find_mmcif_category("_entity_poly.")
    tags = [t.split(".", 1)[1] for t in cat.tags] if cat else []
    col = "pdbx_seq_one_letter_code_can" if "pdbx_seq_one_letter_code_can" in tags else (
          "pdbx_seq_one_letter_code" if "pdbx_seq_one_letter_code" in tags else None)
    if col:
        for r in blk.find("_entity_poly.", ["entity_id", "type", col]):
            s = re.sub(r"\s", "", gemmi.cif.as_string(r[2])).upper()
            if col == "pdbx_seq_one_letter_code":
                s = re.sub(r"\([A-Z0-9]+\)", "X", s)        # parenthesised modified residues
            seqs.append({"entity_id": r[0], "type": gemmi.cif.as_string(r[1]), "sequence": s})
    def diff(q):
        """1-based construct positions that differ from the closest same-length reference entity sequence
        (X marks a parenthesised modified residue in the reference). None if no same-length entity."""
        same = [e["sequence"] for e in seqs if len(e["sequence"]) == len(q)]
        if not same:
            return None
        best = min(same, key=lambda s: sum(a != b for a, b in zip(q, s)))
        return [{"position": i + 1, "construct": a, "reference": b} for i, (a, b) in enumerate(zip(q, best)) if a != b]

    def match(q):
        hits = [e["entity_id"] for e in seqs if e["sequence"] == q]
        return hits
    return {
        "reference_entity_poly_records": len(seqs),
        "reference_sequence_column": col,
        "protein_construct_equals_a_reference_entity_sequence": bool(match(prot)) if seqs else None,
        "rna_construct_equals_a_reference_entity_sequence": bool(match(rna)) if seqs else None,
        "protein_positions_differing_from_same_length_entity": diff(prot),
        "rna_positions_differing_from_same_length_entity": diff(rna),
        "note": ("construct positions are read as the reference's label_seq_id; they mean the same thing as the "
                 "prediction's residue numbers only when the prediction was made from the reference entity "
                 "sequence. A False here is reported, not corrected; the frozen correspondence then counts any "
                 "letter disagreements (dockq.correspondence and the adapter log)."),
    }


def load(path_or_dict, base_dir=None):
    if isinstance(path_or_dict, (str, os.PathLike)):
        base_dir = os.path.dirname(os.path.abspath(path_or_dict))
        try:
            d = json.load(open(path_or_dict))
        except json.JSONDecodeError as ex:
            raise ContractError("input is not valid JSON: %s" % ex)
    else:
        d = json.loads(json.dumps(path_or_dict))
    base_dir = base_dir or os.getcwd()
    return validate(d, base_dir)


def validate(d, base_dir):
    if d.get("contract") != CONTRACT_ID:
        raise ContractError("contract must be %r (got %r)" % (CONTRACT_ID, d.get("contract")))
    tid = d.get("target_id")
    if not isinstance(tid, str) or not _ID.match(tid):
        raise ContractError("target_id must be 1-64 characters of [A-Za-z0-9_.-]")
    for k in ("prediction", "reference", "construct"):
        if not isinstance(d.get(k), dict):
            raise ContractError("missing object: %s" % k)
    for k in ("prediction", "reference"):
        p = d[k].get("path")
        if not p:
            raise ContractError("%s.path is required" % k)
        p = p if os.path.isabs(p) else os.path.join(base_dir, p)
        if not os.path.isfile(p):
            raise ContractError("%s file not found: %s" % (k, p))
        d[k]["path"] = os.path.abspath(p)
        want = d[k].get("sha256")
        if want and _sha(p) != want.lower():
            raise ContractError("%s sha256 does not match the declared value" % k)
    if not d["prediction"]["path"].lower().endswith((".pdb", ".cif")):
        raise ContractError("prediction must be .pdb or .cif")
    c = d["construct"]
    prot, rna = (c.get("protein_sequence") or "").upper(), (c.get("rna_sequence") or "").upper()
    if not prot or not rna:
        raise ContractError("construct.protein_sequence and construct.rna_sequence are both required: the frozen "
                            "rules evaluate one protein entity and one RNA entity (any copy number)")
    if set(prot) - PROTEIN_ALPHABET:
        raise ContractError("protein_sequence has characters outside the 20 standard amino acids + X: %s" % sorted(set(prot) - PROTEIN_ALPHABET))
    if set(rna) - RNA_ALPHABET - RNA_UNKNOWN:
        raise ContractError("rna_sequence must use A, C, G, U (and X for a non-standard nucleotide): %s" % sorted(set(rna) - RNA_ALPHABET - RNA_UNKNOWN))
    c["protein_sequence"], c["rna_sequence"] = prot, rna
    opts = d.setdefault("options", {})
    tol = opts.get("tolerance", 0)
    if not isinstance(tol, int) or tol < 0:
        raise ContractError("options.tolerance must be a non-negative integer (frozen default 0)")
    des = d["prediction"].get("designated_output")
    if des is not None and not isinstance(des, dict):
        raise ContractError("prediction.designated_output, if given, must be an object")
    d["_checks"] = _reference_checks(d["reference"]["path"], prot, rna)
    d["_checks"]["construct_positions_with_X"] = {"protein": [i + 1 for i, ch in enumerate(prot) if ch == "X"],
                                                  "rna": [i + 1 for i, ch in enumerate(rna) if ch == "X"]}
    return d
