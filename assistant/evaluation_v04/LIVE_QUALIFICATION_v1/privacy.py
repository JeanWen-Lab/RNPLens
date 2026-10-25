"""LIVE_QUALIFICATION_v1 pre-send privacy gate (frozen). Applied to the exact bytes of every prompt BEFORE the Codex
subprocess starts; any finding refuses the call (nothing is sent) and aborts the run.

What the two assistant paths declare they send:
* natural-language planner (rnplens assist --nl, assistant.ask): the question, the RELATIVE file names in the task
  folder, the reference file NAMES and the RNPLens documentation (assist.NL_PRIVACY);
* follow-up (assistant.followup): the question and the derived evidence summary (consent.CATEGORIES).
Neither may contain coordinates, sequences, the content of any input/output file, file paths outside the task,
reference content, reference-derived values (follow-up without the separate opt-in), file hashes or secrets.

The checks are text-only and conservative. Sequences are read locally for the check only (as followup.privacy_check
does). RNA constructs shorter than K residues cannot be checked by K-mers; the whole sequence is then not checked
(recorded as a limitation of the gate in the run record)."""
import os
import re

K = 8                     # sequence fragment length, the same as followup.privacy_check
MIN_LINE = 20             # a file line of at least this many characters found verbatim in a payload = file content
TEXT_SUFFIXES = (".fasta", ".fa", ".pdb", ".cif", ".mmcif", ".ent", ".json", ".txt", ".csv", ".tsv", ".md")
COORD_LINE = re.compile(r"^(ATOM|HETATM)\s", re.M)
ATOM_SITE = re.compile(r"\b_atom_site\.")
XYZ = re.compile(r"-?\d{1,4}\.\d{3}\s+-?\d{1,4}\.\d{3}\s+-?\d{1,4}\.\d{3}")
ABS_PATH = re.compile(r"(?:^|[\s\"'=(,\[])(/(?:home|Users|tmp|private|var|mnt|scratch|data|opt|srv|root|etc)/[^\s\"']*)")
HEX64 = re.compile(r"\b[0-9a-f]{64}\b")
REF_KEY = re.compile(r"\"(dockq|dockq_class|fnat|irmsd|lrmsd)\"\s*:", re.I)
SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)", re.I)


def fasta_sequences(paths):
    out = []
    for p in paths:
        if os.path.isfile(p):
            with open(p, encoding="utf-8", errors="replace") as fh:
                s = "".join(l.strip() for l in fh if l.strip() and not l.startswith(">")).upper()
            if s:
                out.append(s)
    return out


def text_files(roots, exclude_dirs=(".rnplens",)):
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dp, dn, fn in os.walk(root):
            dn[:] = sorted(d for d in dn if d not in exclude_dirs)
            for f in sorted(fn):
                if f.lower().endswith(TEXT_SUFFIXES):
                    yield os.path.join(dp, f)


def file_lines(paths, min_len=MIN_LINE):
    """Distinct stripped lines (>= min_len characters) of the given text files."""
    lines = set()
    for p in paths:
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                for l in fh:
                    l = l.strip()
                    if len(l) >= min_len and not l.startswith(("ATOM", "HETATM")):   # coordinate rows: COORD_LINE/XYZ
                        lines.add(l)
        except OSError:
            continue
    return lines


def gate(payload, sequences=(), content_lines=(), allowed_lines=(), forbidden_strings=(), reference_derived_allowed=False,
         env=None):
    """-> list of findings (empty: the payload may be sent).
    sequences: construct sequences (protein and RNA) whose K-mers may not appear;
    content_lines: lines of input/output/reference files that may not appear verbatim;
    allowed_lines: lines that legitimately appear in the payload (e.g. documentation lines also present in a file);
    forbidden_strings: literal strings that may not appear (absolute folders of this run, reference content markers)."""
    f = []
    up = payload.upper()
    for s in sequences:
        if len(s) < K:
            continue
        for i in range(len(s) - K + 1):
            if s[i:i + K] in up:
                f.append("sequence fragment of length %d found" % K)
                break
    if COORD_LINE.search(payload) or ATOM_SITE.search(payload):
        f.append("coordinate records found")
    if XYZ.search(payload):
        f.append("a coordinate-like triple of 3-decimal numbers found")
    allowed = set(allowed_lines)
    plines = set(l.strip() for l in payload.splitlines())
    hits = [l for l in content_lines if l not in allowed and (l in plines or l in payload)]
    if hits:
        f.append("%d line(s) of file content found (first: %r)" % (len(hits), sorted(hits)[0][:60]))
    m = ABS_PATH.search(payload)
    if m:
        f.append("an absolute path found (%r)" % m.group(1)[:60])
    for s in forbidden_strings:
        if s and s in payload:
            f.append("a forbidden string found (%r)" % s[:60])
    if HEX64.search(payload):
        f.append("a 64-hex hash found")
    if not reference_derived_allowed:
        m = REF_KEY.search(payload)
        if m:
            f.append("reference-derived value key %r found" % m.group(1))
    env = os.environ if env is None else env
    for k, v in env.items():
        if SECRET_NAME.search(k) and v and len(v) >= 8 and v in payload:
            f.append("the value of environment variable %s found" % k)
    return f
