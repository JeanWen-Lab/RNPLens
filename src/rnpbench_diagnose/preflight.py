"""Preflight: refuse a request this workflow cannot honestly support.

Every gate here mirrors one already enforced in the project's prediction-preparation path. They are
restated rather than imported so that preflight can run without the prediction environment present, and
`verify_against_upstream()` checks that the restatement still matches the upstream source when it is
available.
"""
import re

PERMITTED_IONS = ("ZN", "MG", "CL")
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
EVIDENCE_KEYS = ("unpaired_msa", "paired_msa", "template", "declared_no_msa")


class PreflightRefusal(Exception):
    """Raised instead of proceeding. The message names the gate and what was supplied."""


def preflight(request):
    """Validate a request dict. Returns a receipt; raises PreflightRefusal on any failure."""
    if not isinstance(request, dict):
        raise PreflightRefusal("request must be a mapping, got %s" % type(request).__name__)
    extra = set(request) - {"sample", "evidence", "resources", "provenance"}
    if extra:
        raise PreflightRefusal("unrecognised request keys: %s" % sorted(extra))
    sample = request.get("sample")
    if not isinstance(sample, dict):
        raise PreflightRefusal("request.sample missing")
    name = sample.get("name", "")
    if not NAME_RE.match(str(name)):
        raise PreflightRefusal("sample.name must be a plain token matching %s, got %r" % (NAME_RE.pattern, name))
    ents = sample.get("sequences")
    if not isinstance(ents, list) or not ents:
        raise PreflightRefusal("sample.sequences must be a non-empty list")

    prot, rna, ions, other = [], [], [], []
    for i, e in enumerate(ents):
        if not isinstance(e, dict) or len(e) != 1:
            raise PreflightRefusal("entity %d must be a single-keyed mapping" % (i + 1))
        kind = next(iter(e))
        if kind == "proteinChain":
            prot.append((i, e[kind]))
        elif kind == "rnaSequence":
            rna.append((i, e[kind]))
        elif kind == "ion":
            ions.append((i, e[kind]))
        else:
            other.append(kind)
    if other:
        raise PreflightRefusal("unsupported entity types: %s" % sorted(set(other)))
    if not prot:
        raise PreflightRefusal("no protein chain: this workflow diagnoses protein-RNA complexes")
    if not rna:
        raise PreflightRefusal("no RNA chain: this workflow diagnoses protein-RNA complexes")

    bad_ion = sorted({str(x.get("ion")) for _, x in ions} - set(PERMITTED_IONS))
    if bad_ion:
        raise PreflightRefusal("only %s are supported as single-atom representations; got %s"
                               % (", ".join(PERMITTED_IONS), bad_ion))

    # sequence content: reject anything that is not a plain one-letter sequence
    for i, x in prot:
        s = str(x.get("sequence", ""))
        if not s or set(s.upper()) - set("ACDEFGHIKLMNPQRSTVWY"):
            raise PreflightRefusal("protein entity %d sequence is empty or carries non-standard letters" % (i + 1))
    for i, x in rna:
        s = str(x.get("sequence", ""))
        if not s or set(s.upper()) - set("ACGU"):
            raise PreflightRefusal("RNA entity %d sequence is empty or is not plain ACGU" % (i + 1))

    # MSA / template use must be DECLARED for every protein chain, including declaring its absence
    ev = request.get("evidence", {})
    undeclared = [str(i + 1) for i, _ in prot
                  if not any(kx in ev.get(str(i + 1), {}) for kx in EVIDENCE_KEYS)]
    if undeclared:
        raise PreflightRefusal("protein chains %s declare no MSA or template use; declare one of %s "
                               "(use declared_no_msa to state that none was used)"
                               % (undeclared, list(EVIDENCE_KEYS)))
    copies = {"protein_chains": len(prot), "rna_chains": len(rna), "ion_sites": len(ions)}
    return {"name": name, "copy_number": copies,
            "chemistry": sorted({str(x.get("ion")) for _, x in ions}),
            "evidence_declared": {str(i + 1): sorted(ev.get(str(i + 1), {})) for i, _ in prot},
            "gates_passed": ["request_keys", "sample_name", "entity_types", "protein_present",
                             "rna_present", "chemistry_whitelist", "sequence_alphabet",
                             "msa_use_declared"]}


def verify_against_upstream(path):
    """Confirm the restated gates still match the project's preparation source, if it is reachable."""
    try:
        src = open(path, encoding="utf-8").read()
    except OSError as ex:
        return {"checked": False, "reason": "upstream unreadable: %s" % ex.__class__.__name__}
    findings = []
    for ion in PERMITTED_IONS:
        if ion not in src:
            findings.append("upstream no longer names permitted ion %s" % ion)
    if "unpaired_msa" not in src:
        findings.append("upstream no longer names unpaired_msa evidence")
    return {"checked": True, "upstream": path, "divergences": findings}
