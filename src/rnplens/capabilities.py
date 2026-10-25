"""Capability registry for the question menu and the assistant (contracts document, section 4).

Each 0.4 module declares CAPABILITIES = [ {...}, ... ] with:
  id           stable identifier (e.g. "region_contacts")
  menu         menu letter A-F, or None if not shown in the menu
  label        researcher-facing label
  status       "QUALIFIED" (route qualified earlier), "DESCRIPTIVE" (new, tested, descriptive output),
               "EXPERIMENTAL" (needs further evidence; shown with a warning) or "UNAVAILABLE" (never offered)
  needs        list of required inputs: "project", "analysis", "rna_range", "two_runs", "reference", "run_record", ...
  call         "module:function" taking keyword arguments and returning a dict with an "outputs" list
  limits       one-sentence interpretation limit shown with the result
The menu shows only capabilities whose module imports and whose status is not UNAVAILABLE; it lists the
UNAVAILABLE ones separately with the reason."""
import importlib

MODULES = ["overview", "region", "evidence_query", "methods_export", "clarify", "incremental", "grouping", "doctor"]

# Diagnose is BLOCKED in the public 0.4 interface until it is re-qualified (owner decision, 17 Oct 2026). The public
# commands refuse with this status and exit code; the frozen rc3 component itself is unchanged and its internal
# contract checks still run in `rnplens selftest` (they are software checks, not interpretation of user structures).
DIAGNOSE_BLOCKED_STATUS = "DIAGNOSE_BLOCKED"
DIAGNOSE_BLOCKED_EXIT = 5
DIAGNOSE_BLOCKED_MESSAGE = (
    "Diagnose is BLOCKED in RNPLens 0.4 until it is re-qualified: its statements and its validated domain rest on "
    "evidence that is being recomputed under the corrected residue correspondence. Nothing was run and nothing was "
    "written. Report and Evaluate's DockQ route are available; 'rnplens selftest' still runs Diagnose's internal "
    "contract checks.")
DIAGNOSE_BLOCKED_VERBS = ("run", "preflight", "validity")


class DiagnoseBlocked(Exception):
    """Raised when a caller asks for Diagnose in the public 0.4 interface."""


def diagnose_blocked_text(context):
    return "rnplens %s: %s: %s" % (context, DIAGNOSE_BLOCKED_STATUS, DIAGNOSE_BLOCKED_MESSAGE)


BLOCKED = [
    {"id": "diagnose_interpretation", "label": "Diagnose (user-facing workflow: diagnose run, preflight, validity and "
     "its interpretation)", "status": "UNAVAILABLE",
     "reason": "BLOCKED in 0.4 until re-qualification (the commands refuse with exit 5): licensing evidence is being "
               "recomputed under the corrected correspondence"},
    {"id": "geometry_four_axis", "label": "Evaluate four-axis geometry", "status": "UNAVAILABLE",
     "reason": "known residue-correspondence defect (SequenceMatcher autojunk; stop report 2026-10-14)"},
    {"id": "rna_conformation_difference", "label": "RNA conformation difference between candidates (Spec B 'Q')",
     "status": "UNAVAILABLE", "reason": "uses the same correspondence route as the blocked geometry axes"},
    {"id": "ranking", "label": "Candidate ranking or selection", "status": "UNAVAILABLE",
     "reason": "RNPLens Rank closed with outcome STOP (2026-10-14)"},
    {"id": "structure_prediction", "label": "New structure prediction", "status": "UNAVAILABLE",
     "reason": "RNPLens does not predict structures"},
    {"id": "mutation_advice", "label": "Mutation or experiment advice", "status": "UNAVAILABLE",
     "reason": "outside the scope of the evidence RNPLens computes"},
]


def available():
    """(capabilities offered, capabilities not offered with reasons). Import failures are reported, not hidden."""
    offered, missing = [], list(BLOCKED)
    for m in MODULES:
        try:
            mod = importlib.import_module("rnplens." + m)
        except ImportError as ex:
            missing.append({"id": m, "label": m, "status": "UNAVAILABLE", "reason": "module not installed: %s" % ex})
            continue
        for c in getattr(mod, "CAPABILITIES", []):
            (missing if c["status"] == "UNAVAILABLE" else offered).append(dict(c, module=m))
    return offered, missing


def resolve(call):
    mod, fn = call.split(":")
    return getattr(importlib.import_module(mod), fn)
