"""Input contract for RNPBench Predict.

WHY THIS MODULE EXISTS. The development prototype read two benchmark-internal files: an engine-output index and
the benchmark's own target key, which supplied the declared construct lengths. A third party has neither. The
contract below is the ONLY input the core reads, so the core contains no benchmark-specific knowledge; the
benchmark is one adapter that emits a contract (see adapters/benchmark.py).

WHAT THE CONTRACT DECLARES, AND WHY EACH FIELD IS MANDATORY.
  construct.protein_length / rna_length  the lengths the user ASKED for. Comparison across engines happens in
        input numbering, so a length mismatch means positions cannot be compared. Inferring the intended length
        from the outputs would let a truncated prediction define the question it is being judged against.
  construct.protein_sequence / rna_sequence   optional but checked when present: a sequence whose length
        disagrees with the declared length is a contract error, not something to reconcile silently.
  outputs[].sha256                       the digest of the structure file as submitted. Re-verified before the
        file is parsed, so a report can never describe a file that changed after it was registered.
  outputs[].engine / execution           engine identity drives native-confidence parsing; execution labels
        repeats so that an engine running twice cannot outweigh one running once.

FAILURE POLICY. validate() raises ContractError and names the offending field. It never repairs, defaults or
drops an entry: a malformed contract stops the run.
"""
import hashlib
import json
import os

SCHEMA_VERSION = "rnpbench-predict-contract-1"
KNOWN_ENGINES = ("AF3", "BOLTZ2", "CHAI1", "RF3", "RF2NA", "OTHER")
REQUIRED_TOP = ("schema_version", "case_id", "construct", "outputs")
REQUIRED_CONSTRUCT = ("protein_length", "rna_length")
REQUIRED_OUTPUT = ("engine", "execution", "structure_path", "sha256")


class ContractError(Exception):
    """A malformed or unverifiable input contract. Never raised for a bad PREDICTION, only for a bad input."""


def sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def _require(d, keys, where):
    missing = [k for k in keys if k not in d]
    if missing:
        raise ContractError("%s is missing required field(s): %s" % (where, ", ".join(missing)))


def validate(contract, verify_digests=True):
    """Return a normalised contract or raise ContractError. Normalisation is ordering and typing only."""
    if not isinstance(contract, dict):
        raise ContractError("contract must be a JSON object, got %s" % type(contract).__name__)
    _require(contract, REQUIRED_TOP, "contract")
    if contract["schema_version"] != SCHEMA_VERSION:
        raise ContractError("schema_version must be %r, got %r" % (SCHEMA_VERSION, contract["schema_version"]))
    if not str(contract["case_id"]).strip():
        raise ContractError("case_id must be a non-empty string")

    c = contract["construct"]
    _require(c, REQUIRED_CONSTRUCT, "construct")
    for fld in REQUIRED_CONSTRUCT:
        v = c[fld]
        if not isinstance(v, int) or isinstance(v, bool) or v < 1:
            raise ContractError("construct.%s must be a positive integer, got %r" % (fld, v))
    for seqfld, lenfld in (("protein_sequence", "protein_length"), ("rna_sequence", "rna_length")):
        s = c.get(seqfld)
        if s is None:
            continue
        s = "".join(str(s).split())
        if len(s) != c[lenfld]:
            raise ContractError("construct.%s has length %d but construct.%s declares %d"
                                % (seqfld, len(s), lenfld, c[lenfld]))
        c[seqfld] = s

    outs = contract["outputs"]
    if not isinstance(outs, list) or not outs:
        raise ContractError("outputs must be a non-empty list")
    seen = {}
    norm = []
    for i, o in enumerate(outs):
        where = "outputs[%d]" % i
        if not isinstance(o, dict):
            raise ContractError("%s must be a JSON object" % where)
        _require(o, REQUIRED_OUTPUT, where)
        if o["engine"] not in KNOWN_ENGINES:
            raise ContractError("%s.engine %r is not one of %s; use 'OTHER' and supply "
                                "native_confidence explicitly for an engine this version does not parse"
                                % (where, o["engine"], ", ".join(KNOWN_ENGINES)))
        key = (o["engine"], str(o["execution"]))
        if key in seen:
            raise ContractError("%s duplicates engine/execution %s already declared at %s"
                                % (where, key, seen[key]))
        seen[key] = where
        p = o["structure_path"]
        if not os.path.isabs(p):
            raise ContractError("%s.structure_path must be absolute, got %r" % (where, p))
        if not os.path.exists(p):
            raise ContractError("%s.structure_path does not exist: %s" % (where, p))
        if not p.endswith((".cif", ".mmcif", ".pdb")):
            raise ContractError("%s.structure_path must be .cif, .mmcif or .pdb, got %s" % (where, p))
        if verify_digests:
            got = sha256(p)
            if got != o["sha256"]:
                raise ContractError("%s digest mismatch: contract declares %s, file is %s"
                                    % (where, o["sha256"][:16], got[:16]))
        if o["engine"] == "OTHER" and "native_confidence" not in o:
            raise ContractError("%s.engine is OTHER, so native_confidence and native_confidence_kind must be "
                                "declared explicitly (use null to state that none is available)" % where)
        norm.append({"engine": o["engine"], "execution": str(o["execution"]), "structure_path": p,
                     "sha256": o["sha256"],
                     "native_confidence": o.get("native_confidence", "RESOLVE_FROM_ENGINE_FILES"),
                     "native_confidence_kind": o.get("native_confidence_kind"),
                     "confidence_dir": o.get("confidence_dir") or os.path.dirname(p)})
    norm.sort(key=lambda r: (r["engine"], r["execution"]))
    out = dict(contract)
    out["outputs"] = norm
    out["construct"] = c
    return out


def load(path, verify_digests=True):
    with open(path) as fh:
        return validate(json.load(fh), verify_digests=verify_digests)
