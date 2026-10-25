"""Privacy contract for the optional Codex follow-up planning call (RNPLens 0.4, Function 4).

Before the first follow-up call for a project, the researcher sees the exact categories of data that would be sent to
their Codex (ChatGPT) account and opts in explicitly. The decision is recorded in <project>/.rnplens/consent.json with
a timestamp, the category-list version and the scope (this project). Without a current opt-in the follow-up is
local-only: deterministic suggestions, and no subprocess to Codex is started. An opt-out revokes the opt-in; both are
kept in the record (append-only list, atomically replaced file).

What is sent is fixed by followup.build_summary (derived values only), with every run, sample, file and output name
replaced by an opaque identifier (redact.py; category list 2). Coordinates, sequences, file contents, file names, paths
and reference files are never sent. Values derived from an experimental reference (DockQ, fnat, iRMSD, LRMSD and classes)
are excluded unless the opt-in itself records allow_reference_derived=True."""
import datetime
import hashlib
import json
import os

from rnplens import provenance as pv

SCHEMA = "rnplens.followup.consent.1"
CATEGORIES_VERSION = "followup-categories-2"      # 2 (0.4): identifiers replace every run, sample, file and output name
SCOPE = "project"
CATEGORIES = [
    ("question_text", "your question text, as you typed it"),
    ("derived_agreement_values", "agreement values computed by RNPLens Report (binding-surface agreement, contact-register "
                                 "agreement, RNA pose difference), with their evidence IDs"),
    ("contact_labels_positions", "contact labels with residue and nucleotide letters and construct positions (for example "
                                 "R18-A21), and the RNA and protein positions they involve"),
    ("counts", "counts: structures found, included and excluded, contacts per frequency band, construct lengths"),
    ("identifiers", "opaque identifiers instead of names: run_001, candidate_001 (a structure's sample), evidence_001, "
                    "output_001, and the RNPLens structure IDs (s001); the real run, folder, sample and file names and the "
                    "identifier map stay on this computer"),
]
NEVER_SENT = [
    "atomic coordinates or any structure file content",
    "protein or RNA sequences (the construct FASTA files are never read for the summary)",
    "the content of any input or output file, file paths, and file, folder, run or sample names taken from your files "
    "(they are replaced by identifiers; the map is kept in redaction_map.json in the follow-up folder)",
    "experimental reference structures or reference files, and their names or paths",
    "values derived from an experimental reference (DockQ, fnat, iRMSD, LRMSD, DockQ class), unless you opt in to them separately",
    "engine confidence values (for example ipTM) and API keys or account details",
]
REFERENCE_CATEGORY = ("reference_derived_values", "values derived from an experimental reference (DockQ, DockQ class, fnat, "
                                                  "iRMSD, LRMSD); the reference file itself is still never sent")


class ConsentRequired(Exception):
    """No current opt-in for this project: the follow-up stays local-only."""


def path(project):
    return os.path.join(os.path.abspath(project), ".rnplens", "consent.json")


def categories(allow_reference_derived=False):
    c = [k for k, _ in CATEGORIES]
    return c + [REFERENCE_CATEGORY[0]] if allow_reference_derived else c


def screen_text(allow_reference_derived=False):
    """The exact text shown before the opt-in (also stored, hashed, in the consent record)."""
    L = ["Ask Codex for a follow-up: what would be sent",
         "",
         "If you opt in, each follow-up request sends ONE planning message to your Codex (ChatGPT) account, through the",
         "RNPLens jail. It contains only:"]
    L += ["  - %s" % t for _, t in CATEGORIES]
    if allow_reference_derived:
        L.append("  - %s" % REFERENCE_CATEGORY[1])
    L += ["", "It never contains:"] + ["  - %s" % t for t in NEVER_SENT]
    L += ["", "The model only chooses one follow-up from a fixed list; RNPLens checks it, asks you before running it, and",
          "writes every number in the answer from its own records. Scope: this project only (%s)." % CATEGORIES_VERSION,
          "You can opt out at any time; without an opt-in, follow-ups are local suggestions and nothing is sent."]
    return "\n".join(L) + "\n"


def _load(project):
    p = path(project)
    if not os.path.isfile(p):
        return {"schema": SCHEMA, "records": []}
    with open(p, encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("schema") != SCHEMA or not isinstance(doc.get("records"), list):
        raise ValueError("%s is not an RNPLens consent record" % p)
    return doc


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _append(project, rec):
    doc = _load(project)
    rec["id"] = "consent-%04d-%s" % (len(doc["records"]) + 1, hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()[:8])
    doc["records"].append(rec)
    doc["current"] = rec["id"]
    doc["provenance"] = pv.block("followup_consent", [], "explicit opt-in/opt-out for the follow-up planning call; "
                                 "scope project; categories %s" % CATEGORIES_VERSION, {"categories_version": CATEGORIES_VERSION})
    pv.atomic_write_json(path(project), doc)
    return rec


def opt_in(project, method, allow_reference_derived=False):
    """Record an explicit opt-in. method: 'interactive' (the researcher answered yes to screen_text) or '--yes'
    (scripted/test use; recorded as such)."""
    if method not in ("interactive", "--yes"):
        raise ValueError("method must be 'interactive' or '--yes'")
    txt = screen_text(allow_reference_derived)
    return _append(project, {"action": "opt_in", "timestamp_utc": _now(), "categories_version": CATEGORIES_VERSION,
                             "categories": categories(allow_reference_derived), "never_sent": list(NEVER_SENT),
                             "allow_reference_derived": bool(allow_reference_derived), "scope": SCOPE,
                             "project": os.path.abspath(project), "method": method,
                             "screen_sha256": hashlib.sha256(txt.encode()).hexdigest()})


def opt_out(project, method="interactive"):
    return _append(project, {"action": "opt_out", "timestamp_utc": _now(), "categories_version": CATEGORIES_VERSION,
                             "scope": SCOPE, "project": os.path.abspath(project), "method": method})


def status(project):
    """-> (granted, record or None, reason). Granted only when the latest record is an opt-in for this project with the
    current category-list version."""
    try:
        doc = _load(project)
    except (OSError, ValueError) as ex:
        return False, None, "consent record unreadable: %s" % ex
    if not doc["records"]:
        return False, None, "no opt-in recorded for this project"
    r = doc["records"][-1]
    if r.get("action") != "opt_in":
        return False, r, "opted out (%s)" % r.get("timestamp_utc")
    if r.get("categories_version") != CATEGORIES_VERSION:
        return False, r, "the opt-in covers category list %s; the current list is %s" % (r.get("categories_version"), CATEGORIES_VERSION)
    if os.path.abspath(r.get("project", "")) != os.path.abspath(project):
        return False, r, "the opt-in was recorded for another project folder"
    return True, r, "opted in (%s, %s)" % (r["timestamp_utc"], r["method"])


def require(project):
    ok, r, why = status(project)
    if not ok:
        raise ConsentRequired(why)
    return r


def interactive_opt_in(project, ask, out=print, allow_reference_derived=False):
    """Show the screen and ask. Returns the record on 'yes', None otherwise (nothing recorded on 'no')."""
    out(screen_text(allow_reference_derived))
    a = ask("Send this to Codex for follow-up planning in this project? Type 'yes' to opt in: ")
    if (a or "").strip().lower() != "yes":
        out("Not opted in: follow-ups stay local and nothing is sent.")
        return None
    return opt_in(project, "interactive", allow_reference_derived)
