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
  outputs[].confidence_path / confidence_sha256   the engine's OWN confidence file and its digest, declared and
        verified exactly as the structure file is (RNPLens 0.4, owner-authorised correction 2026-10-24). Before
        this was declared, the file was resolved from dirname(structure_path) with no existence and no integrity
        check, which is outside the guarantee this module states for itself: a DELETED file produced a report
        that no automatic means could distinguish from a complete one, and an EDITED file was read unchecked.
        Wherever this version resolves the value from a file, that file is a required input. Declaring
        native_confidence instead (null states that the engine publishes none) is the sanctioned way to say that
        no file is read, and then nothing is declared or verified here.
  outputs[].engine / execution           engine identity drives native-confidence parsing; execution labels
        repeats so that an engine running twice cannot outweigh one running once.

FAILURE POLICY. validate() raises ContractError and names the offending field. It never repairs, defaults or
drops an entry: a malformed contract stops the run. A DECLARED confidence input that is absent, not a regular
file, not the file the engine parser reads, or whose digest does not match is a malformed contract in exactly
that sense, and is refused here in every mode. An output whose required confidence input is not declared at all
is a different thing -- an input set that cannot support a qualified per-engine confidence column, rather than a
malformed document -- so confidence_input_findings() reports it and the command refuses before producing any
output (cli.py). validate() stays usable by callers that read coordinates only and no confidence file.
"""
import hashlib
import json
import os

SCHEMA_VERSION = "rnpbench-predict-contract-1"
KNOWN_ENGINES = ("AF3", "BOLTZ2", "CHAI1", "RF3", "RF2NA", "OTHER")
REQUIRED_TOP = ("schema_version", "case_id", "construct", "outputs")
REQUIRED_CONSTRUCT = ("protein_length", "rna_length")
REQUIRED_OUTPUT = ("engine", "execution", "structure_path", "sha256")
CONFIDENCE_FIELDS = ("confidence_path", "confidence_sha256")

# The project's settled five-part shape for something a run will not produce (rnplens/geometry_block.py: STATUS,
# CODE, REASON, SUMMARY_LINE, RUN_RECORD_NOTE), applied here to a REFUSAL rather than to a withheld number.
STATUS = "REFUSED"
CODE = "CONFIDENCE_INPUT_CONTRACT_UNSATISFIED"
REASON = ("The engine's own interface confidence is read from a file this contract does not declare and digest, "
          "so neither its presence nor its contents can be verified. Report refuses rather than publish a page "
          "whose per-engine confidence column cannot be traced to a verified input: with the file missing the "
          "run is otherwise indistinguishable from a complete one (same exit code, same printed summary, every "
          "geometric quantity identical), and with the file edited the value shown is unchecked. Declare "
          "confidence_path and confidence_sha256 for each output, or declare native_confidence (null states that "
          "the engine publishes none), or re-run with --reduced-evidence, which produces the coordinate-only "
          "analysis and labels it in every output stream as not a fully qualified analysis.")
SUMMARY_LINE = ("Engine confidence inputs: REFUSED (a required input is not declared, or is declared and does not "
                "verify); no result, no page and no output directory were produced.")
RUN_RECORD_NOTE = ("the engine confidence file of each output is a declared input (confidence_path, "
                   "confidence_sha256) that was verified before the analysis ran; each is listed with its digest "
                   "among the inputs of this record")
REDUCED_EVIDENCE_STATUS = "NATIVE_CONFIDENCE_INPUTS_NOT_VERIFIED"
REDUCED_EVIDENCE_NOTE = ("--reduced-evidence was given, so this analysis ran with one or more engine confidence "
                         "inputs neither declared nor verified. It is NOT the result the same contract produces "
                         "with those inputs declared and verified, and it is not a fully qualified analysis. The "
                         "agreement analysis reads coordinates only and is unaffected; the per-engine confidence "
                         "column is incomplete and must not be cited from this run.")


class ContractError(Exception):
    """A malformed or unverifiable input contract. Never raised for a bad PREDICTION, only for a bad input."""


def sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def _confidence_declaration(o, where, structure_path, confidence_dir, verify_digests):
    """One output's DECLARED confidence input -> the fields to carry into the normalised contract.

    Raises ContractError for every declaration this module cannot stand behind. The ABSENCE of a declaration is
    not judged here (confidence_input_findings does that); a declaration that is wrong is refused outright.
    """
    from . import native
    cpath, csha = o.get("confidence_path"), o.get("confidence_sha256")
    if cpath is None and csha is None:
        return {}
    if cpath is None:
        raise ContractError("%s declares confidence_sha256 without confidence_path; the digest of an unnamed "
                            "file cannot be verified" % where)
    if not isinstance(cpath, str) or not os.path.isabs(cpath):
        raise ContractError("%s.confidence_path must be absolute, got %r" % (where, cpath))
    if o.get("native_confidence", "RESOLVE_FROM_ENGINE_FILES") != "RESOLVE_FROM_ENGINE_FILES":
        raise ContractError("%s declares both native_confidence and confidence_path: the value is taken from the "
                            "contract, so no file is read and the declared input would be verified against "
                            "nothing" % where)
    expect, code, note = native.expected_input(o["engine"], structure_path, confidence_dir)
    if expect is None:
        raise ContractError("%s declares confidence_path %s but this version reads no such file for engine %s "
                            "(%s: %s)" % (where, cpath, o["engine"], code, note))
    if os.path.realpath(cpath) != os.path.realpath(expect):
        raise ContractError("%s.confidence_path %s is not the file this version reads for engine %s, which is %s; "
                            "a declared input that is never read cannot be verified"
                            % (where, cpath, o["engine"], expect))
    if not os.path.exists(cpath):
        raise ContractError("%s.confidence_path does not exist: %s" % (where, cpath))
    link = os.path.realpath(cpath) if os.path.islink(cpath) else None
    if not os.path.isfile(cpath):
        raise ContractError("%s.confidence_path is not a regular file: %s" % (where, cpath))
    if not isinstance(csha, str) or len(csha) != 64 or any(ch not in "0123456789abcdef" for ch in csha.lower()):
        raise ContractError("%s.confidence_sha256 must be the 64-character SHA-256 of confidence_path, got %r"
                            % (where, csha))
    if verify_digests:
        got = sha256(cpath)
        if got != csha.lower():
            raise ContractError("%s confidence digest mismatch: contract declares %s, file is %s"
                                % (where, csha[:16], got[:16]))
    rec = {"confidence_path": cpath, "confidence_sha256": csha.lower(), "confidence_input_note": note}
    if link:                        # disclosed, never silent (rnplens import discloses symlinked structures too)
        rec["confidence_path_symlink_target"] = link
    return rec


def declare_confidence_input(output, confidence_dir=None):
    """Fill confidence_path/confidence_sha256 for one output from the file this version reads, when that file is
    there. -> the same output dict. This is the writer-side counterpart of the sha256 a contract writer already
    computes for the structure file, and every contract writer in this project uses it (rnplens import, the
    bundled example writers). An output declaring native_confidence reads no file and is left alone; a file that
    is not there is left undeclared, so the command refuses rather than the writer inventing a digest.
    """
    from . import native
    if output.get("native_confidence", "RESOLVE_FROM_ENGINE_FILES") != "RESOLVE_FROM_ENGINE_FILES":
        return output
    d = confidence_dir or output.get("confidence_dir") or os.path.dirname(output["structure_path"])
    expect, _code, _note = native.expected_input(output["engine"], output["structure_path"], d)
    if expect and os.path.isfile(expect):
        output["confidence_path"] = os.path.abspath(expect)
        output["confidence_sha256"] = sha256(expect)
    return output


def confidence_input_findings(contract):
    """Outputs whose engine-own confidence this version resolves FROM A FILE that is not a declared, verified
    input. -> list of {engine, execution, code, expected_path, file_present, note}; an empty list means every
    required confidence input is declared and was verified by validate().

    This is the check that must pass BEFORE a qualified output exists. An output that declares
    native_confidence, including null, reads no file and is never reported here.
    """
    from . import native
    out = []
    for o in contract["outputs"]:
        if o.get("native_confidence", "RESOLVE_FROM_ENGINE_FILES") != "RESOLVE_FROM_ENGINE_FILES":
            continue                                   # the value is declared in the contract; no file is read
        cdir = o.get("confidence_dir") or os.path.dirname(o["structure_path"])
        expect, code, note = native.expected_input(o["engine"], o["structure_path"], cdir)
        if code == native.READS_NO_FILE:
            continue
        if o.get("confidence_path"):
            continue                                   # declared, and verified by validate()
        present = bool(expect) and os.path.isfile(expect)
        out.append({"engine": o["engine"], "execution": str(o["execution"]),
                    "code": code or (native.UNDECLARED_REQUIRED_INPUT if present
                                     else native.ABSENT_REQUIRED_INPUT),
                    "expected_path": expect, "file_present": present, "note": note})
    return out


def diagnostic(findings, command="rnplens report run"):
    """The refusal text for unsatisfied confidence inputs, in the five-part shape (STATUS, CODE, REASON,
    SUMMARY_LINE, RUN_RECORD_NOTE). Every offending output and every expected path is named."""
    lines = ["%s: %s: %s" % (command, STATUS, CODE), REASON, "",
             "Outputs whose required confidence input is not a declared, verified input:"]
    for f in findings:
        lines.append("  %s %s  %s  %s  (%s; %s)"
                     % (f["engine"], f["execution"], f["code"], f["expected_path"] or "<no path can be named>",
                        f["note"], "file present, no digest declared" if f["file_present"] else "file absent"))
    lines += ["", SUMMARY_LINE]
    return "\n".join(lines)


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
    cid = str(contract["case_id"])
    if any(ch in cid for ch in ("/", "\\", "\x00")) or cid.startswith(".") or any(ord(ch) < 32 for ch in cid):
        # case_id names the HTML file inside the output directory (report_<case_id>.html); it may not be a path
        raise ContractError("case_id %r may not contain '/', '\\', control characters or start with '.'; it names "
                            "a file inside the output directory" % cid)

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
        conf_dir = o.get("confidence_dir") or os.path.dirname(p)
        conf = _confidence_declaration(o, where, p, conf_dir, verify_digests)
        norm.append({"engine": o["engine"], "execution": str(o["execution"]), "structure_path": p,
                     "sha256": o["sha256"],
                     "native_confidence": o.get("native_confidence", "RESOLVE_FROM_ENGINE_FILES"),
                     "native_confidence_kind": o.get("native_confidence_kind"),
                     "confidence_dir": conf_dir, **conf})
    norm.sort(key=lambda r: (r["engine"], r["execution"]))
    out = dict(contract)
    out["outputs"] = norm
    out["construct"] = c
    return out


def load(path, verify_digests=True):
    with open(path) as fh:
        return validate(json.load(fh), verify_digests=verify_digests)
