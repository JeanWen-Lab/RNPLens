"""``rnplens assist --project P [--analysis A]``: a question menu over the capability registry. No language model.

The menu has exactly six items (A-F). Each item lists the registered capabilities whose ``menu`` letter it carries
(rnplens.capabilities). An item with no offered capability is shown as unavailable, with the reason, and cannot be
run; the capabilities that are never offered (capabilities.BLOCKED and any UNAVAILABLE or uninstalled module) are
listed under "Not available". Inputs are collected with typed prompts (ranges are checked against the construct,
runs are chosen from the project manifest). Choosing an item calls the deterministic function named in the registry
directly. Nothing leaves the machine.

Non-interactive use (scripting, tests):  rnplens assist --project P --analysis A --item B --rna 40-60 --runs a,b
Optional natural-language mode:          rnplens assist --project P --task T --nl "question"
  hands the question to the existing assistant (rnplens_assistant.ask) only when ``rnplens doctor --agent`` is READY;
  otherwise it says why and offers the menu.
Follow-ups (0.4, EXPERIMENTAL):                    ... --item C --rna 13-23 --runs a,b --followup local [--yes]
  after a result, one bounded follow-up: deterministic local suggestions (no language model), or, with a recorded
  opt-in and ``rnplens doctor --agent`` READY, one Codex planning call checked by the RNPLens policy
  (rnplens_assistant.followup; docs/followup.md). In the interactive menu, type s (local) or ac (ask Codex) after a
  result. The assistant package is imported only when a follow-up is requested."""
import argparse
import inspect
import json
import os
import re
import sys
import time

from . import capabilities, result_links, trace

ITEMS = [("A", "Compare binding surfaces and contacts"),
         ("B", "Inspect contacts in an RNA region"),
         ("C", "Compare two prediction runs or model versions"),
         ("D", "Explain an existing result"),
         ("E", "Group distinct binding hypotheses"),
         ("F", "Export results and Methods")]
LETTERS = [k for k, _ in ITEMS]
MODULE_HINT = {"B": "region", "D": "evidence_query", "E": "grouping", "F": "methods_export"}
EXPERIMENTAL_NOTE = "EXPERIMENTAL: needs further evidence; read its limits before using the result"
MENU_PRIVACY = "The question menu runs RNPLens functions on this computer only; nothing is sent anywhere."
FOLLOWUP_HINT = ("Follow-up (EXPERIMENTAL): type s for suggested follow-ups (local, nothing is sent)%s.")
FOLLOWUP_CODEX_HINT = "; ac to ask Codex for a follow-up (uses your recorded opt-in)"
NL_PRIVACY = ("Natural-language mode sends to your Codex (ChatGPT) account: the question (file, folder and run names in it, in "
              "any letter case, replaced by identifiers; absolute paths and the names of undisclosed files redacted; the "
              "message is checked again and not sent if anything remains), opaque identifiers for the task's run folders, structure files and sequence files "
              "(run_001, run_001/candidate_001, protein_sequence_001), whether an experimental reference is supplied (as "
              "reference_001, only for reference-based tasks) and the RNPLens documentation. It never sends file or folder "
              "names, paths, coordinates, sequences or computed values; the identifier map stays in the run folder "
              "(redaction_map.json).")

# input name -> keyword names a capability function may use for it (first match in its signature wins)
ALIASES = {"project": ["project", "project_dir", "project_root"],
           "analysis": ["analysis", "analysis_dir", "analysis_root"],
           "rna_range": ["rna_range", ("rna_start", "rna_end")],
           "protein_range": ["protein_range", ("protein_start", "protein_end")],
           "runs": ["runs", ("run_a", "run_b")],
           "run": ["run"], "reference": ["reference", "reference_path"], "run_record": ["run_record", "record"],
           "evidence_id": ["evidence_id", "evidence"]}
CANONICAL = {"two_runs": "runs", "analysis_new": "analysis"}


class CapabilityFailed(RuntimeError):
    """The function ran and refused or failed; the menu reports it and exits non-zero."""


class CapabilityBlocked(RuntimeError):
    """The function is BLOCKED in this version (for example Diagnose); the menu reports it and exits with code 5.
    Distinct from CapabilityFailed (exit 4): a function that ran and refused or failed."""


EXIT_BLOCKED = capabilities.DIAGNOSE_BLOCKED_EXIT          # 5
BLOCKED_STATES = {"BLOCKED", capabilities.DIAGNOSE_BLOCKED_STATUS}


class InputError(ValueError):
    pass


class Unavailable(RuntimeError):
    pass


# ---------------------------------------------------------------- registry -> menu

def build_menu(offered=None, missing=None):
    if offered is None:
        offered, missing = capabilities.available()
    items = []
    for letter, label in ITEMS:
        caps = [c for c in offered if c.get("menu") == letter]
        reasons = ["%s: %s" % (m.get("label", m["id"]), m.get("reason", "not offered")) for m in missing if m.get("menu") == letter]
        hint = MODULE_HINT.get(letter)
        reasons += [m["reason"] for m in missing if hint and m["id"] == hint and m.get("reason")]
        if not caps and not reasons:
            reasons = ["no function for this item is installed in this configuration"]
        items.append({"letter": letter, "label": label, "available": bool(caps), "capabilities": caps,
                      "reasons": [] if caps else reasons})
    return items, list(missing)


def render_menu(items, not_available, project=None):
    out = ["RNPLens question menu%s" % (" - project %s" % project if project else ""), MENU_PRIVACY, ""]
    for it in items:
        if it["available"]:
            out.append("  %s  %s" % (it["letter"], it["label"]))
            for c in it["capabilities"]:
                tag = " [%s]" % c["status"]
                out.append("       - %s%s%s" % (c["label"], tag, ("  " + EXPERIMENTAL_NOTE) if c["status"] == "EXPERIMENTAL" else ""))
        else:
            out.append("  %s  %s  (unavailable: %s)" % (it["letter"], it["label"], "; ".join(it["reasons"])))
    out += ["", "Not available:"]
    for m in not_available:
        out.append("  - %s: %s" % (m.get("label", m["id"]), m.get("reason", "")))
    return "\n".join(out)


# ---------------------------------------------------------------- typed inputs

def load_manifest(project):
    p = os.path.join(project, "manifest.json")
    if not os.path.isfile(p):
        raise InputError("%s is not an RNPLens project (no manifest.json); create one with 'rnplens import'" % project)
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def parse_range(text, length, what):
    t = str(text).strip().replace(" ", "")
    m = re.fullmatch(r"(-?\d+)(?:-(-?\d+))?", t)
    if not m:
        raise InputError("%s range %r: write it as start-end, for example 40-60" % (what, text))
    a = int(m.group(1)); b = int(m.group(2)) if m.group(2) is not None else a
    if a > b:
        raise InputError("%s range %r: start is after end" % (what, text))
    if a < 1 or b > length:
        raise InputError("%s range %r: positions must lie within 1-%d (construct numbering)" % (what, text, length))
    return (a, b)


def parse_runs(text, runs, n=None):
    names = [r["run"] for r in runs]
    picked = []
    for tok in [t.strip() for t in str(text).split(",") if t.strip()]:
        if tok.isdigit() and 1 <= int(tok) <= len(names) and tok not in names:
            tok = names[int(tok) - 1]
        if tok not in names:
            raise InputError("run %r is not in this project (runs: %s)" % (tok, ", ".join(names)))
        if tok in picked:
            raise InputError("run %r given twice" % tok)
        picked.append(tok)
    if n is not None and len(picked) != n:
        raise InputError("choose exactly %d run(s) from: %s" % (n, ", ".join(names)))
    if not picked:
        raise InputError("choose at least one run from: %s" % ", ".join(names))
    return picked


def parse_value(need, text, ctx):
    man = ctx["manifest"]
    if need == "rna_range":
        return parse_range(text, man["construct"]["rna_length"], "RNA")
    if need == "protein_range":
        return parse_range(text, man["construct"]["protein_length"], "protein")
    if need == "two_runs":
        return parse_runs(text, man["runs"], 2)
    if need == "runs":
        return parse_runs(text, man["runs"])
    if need == "run":
        return parse_runs(text, man["runs"], 1)[0]
    if need in ("reference", "run_record"):
        p = os.path.abspath(os.path.expanduser(str(text).strip()))
        if not os.path.isfile(p):
            raise InputError("%s %r is not a file" % (need.replace("_", " "), text))
        return p
    if need == "analysis_new":       # item A: an analysis folder that may not exist yet (it is created)
        p = os.path.abspath(os.path.expanduser(str(text).strip()))
        if os.path.exists(p) and not os.path.isfile(os.path.join(p, "summary.json")) and os.listdir(p):
            raise InputError("%s exists, is not empty and has no summary.json" % text)
        if not os.path.isdir(os.path.dirname(p)):
            raise InputError("the parent folder of %s does not exist" % text)
        return p
    if need == "analysis":
        p = os.path.abspath(os.path.expanduser(str(text).strip()))
        if not os.path.isfile(os.path.join(p, "summary.json")):
            raise InputError("%s is not an analysis folder (no summary.json); create one with 'rnplens analyse'" % text)
        return p
    if need == "evidence_id":
        t = str(text).strip()
        if not re.fullmatch(r"[^#\s]+#/\S*", t):
            raise InputError("evidence ID %r: expected <file>#/<pointer>, for example region_40-60/region.json#/contacts/3" % text)
        return t
    t = str(text).strip()
    if not t:
        raise InputError("%s: a value is required" % need)
    return t


PROMPTS = {"rna_range": "RNA range (construct positions 1-{rna}, e.g. {rna_example})",
           "protein_range": "protein range (construct positions 1-{prot}, e.g. 10-30)",
           "two_runs": "two runs, comma-separated ({runs})", "runs": "runs, comma-separated ({runs})",
           "run": "one run ({runs})", "reference": "experimental reference structure file",
           "run_record": "execution record file (JSON)", "analysis": "analysis folder (written by rnplens analyse)",
           "evidence_id": "evidence ID (<file>#/<pointer>)"}


def prompt_text(need, ctx):
    man = ctx["manifest"]
    runs = ", ".join("%d=%s" % (i + 1, r["run"]) for i, r in enumerate(man["runs"]))
    base = PROMPTS.get(need, need.replace("_", " "))
    rna = man["construct"]["rna_length"]
    example = "1-%d" % min(int(rna), 20) if isinstance(rna, int) and rna >= 1 else "1-20"   # always inside the construct
    return base.format(rna=rna, prot=man["construct"]["protein_length"], runs=runs, rna_example=example)


def collect(cap, ctx, given, ask=None, out=print):
    """Values for every input the capability needs. `given` holds non-interactive values (strings); `ask` is a
    prompt function (None in non-interactive mode, where a missing required input is an error)."""
    vals = {}
    for raw in cap.get("needs", []):
        optional = raw.endswith("?")
        need = raw.rstrip("?")
        if need == "project":
            vals["project"] = ctx["project"]
            continue
        if need == "analysis_new" and (given.get("analysis") or ctx.get("analysis")):
            vals["analysis_new"] = parse_value("analysis_new", given.get("analysis") or ctx["analysis"], ctx)
            continue
        if need == "analysis" and ctx.get("analysis") and "analysis" not in given:
            vals["analysis"] = parse_value("analysis", ctx["analysis"], ctx)
            continue
        if need in given and given[need] not in (None, ""):
            vals[need] = parse_value(need, given[need], ctx)
            continue
        if ask is None:
            if optional:
                continue
            raise InputError("missing input for %s: %s (%s)" % (cap["id"], need, _flag_for(need)))
        while True:
            text = ask("%s%s: " % (prompt_text(need, ctx), " [optional, Enter to skip]" if optional else ""))
            if text is None:
                raise InputError("input ended")
            if optional and not text.strip():
                break
            try:
                vals[need] = parse_value(need, text, ctx)
                break
            except InputError as ex:
                out("  " + str(ex))
    return vals


def _flag_for(need):
    return {"rna_range": "--rna", "protein_range": "--protein", "two_runs": "--runs", "runs": "--runs", "run": "--run",
            "reference": "--reference", "run_record": "--run-record", "analysis": "--analysis",
            "evidence_id": "--evidence"}.get(need, "--param %s=VALUE" % need)


def to_kwargs(fn, vals):
    """Map collected inputs to the function's keyword names (see ALIASES); refuse inputs it cannot take."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        sig = None
    params = sig.parameters if sig else {}
    var_kw = sig is None or any(p.kind == p.VAR_KEYWORD for p in params.values())
    kw = {}
    for need, v in vals.items():
        name = CANONICAL.get(need, need)
        placed = False
        for alias in ALIASES.get(name, [name]):
            if isinstance(alias, tuple):
                if all(a in params for a in alias) and isinstance(v, (list, tuple)) and len(v) == len(alias):
                    kw.update(dict(zip(alias, v)))
                    placed = True
                    break
            elif alias in params:
                kw[alias] = list(v) if isinstance(v, tuple) else v
                placed = True
                break
        if not placed:
            if var_kw:
                kw[name] = list(v) if isinstance(v, tuple) else v
            else:
                raise Unavailable("the registered function does not accept the input %r" % need)
    return kw


# ---------------------------------------------------------------- running and showing a result

def _evidence_in(obj, acc, limit=100000):
    stack = [obj]
    while stack and len(acc) < limit:
        o = stack.pop()
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "evidence_id" and isinstance(v, str):
                    acc.append(v)
                elif k == "evidence_ids" and isinstance(v, list):
                    acc.extend(x for x in v if isinstance(x, str))
                else:
                    stack.append(v)
        elif isinstance(o, list):
            stack.extend(reversed(o))
    return acc


def summarise(result, ctx):
    """(output paths, evidence ids) from a capability result, reading output JSON files for evidence ids when the
    result itself lists none."""
    outs = []
    for o in (result or {}).get("outputs", []) or []:
        if isinstance(o, str):
            outs.append(o)
        elif isinstance(o, dict):
            p = o.get("path") or o.get("file")
            if p:
                outs.append(p)
    ev = []
    _evidence_in({k: v for k, v in (result or {}).items() if k != "outputs"}, ev)
    _evidence_in([o for o in (result or {}).get("outputs", []) or [] if isinstance(o, dict)], ev)
    if not ev:
        for p in outs:
            q = p if os.path.isabs(p) else os.path.join(ctx.get("analysis") or ctx["project"], p)
            if q.endswith(".json") and os.path.isfile(q):
                try:
                    with open(q, encoding="utf-8") as fh:
                        _evidence_in(json.load(fh), ev)
                except (OSError, ValueError):
                    pass
    seen, uniq = set(), []
    for e in ev:
        if e not in seen:
            seen.add(e); uniq.append(e)
    return outs, uniq


def run_capability(cap, vals, out=print):
    fn = capabilities.resolve(cap["call"])
    kw = to_kwargs(fn, vals)
    return fn(**kw)


FAILED_STATES = {"REFUSED", "FAILED", "ERROR", "UNAVAILABLE", "NEEDS_CLARIFICATION", "STOPPED"}


def result_failed(result):
    return isinstance(result, dict) and str(result.get("status", "")).upper() in FAILED_STATES


def result_blocked(result):
    return isinstance(result, dict) and str(result.get("status", "")).upper() in BLOCKED_STATES


def show_result(cap, result, ctx, out=print, as_json=False):
    outs, ev = summarise(result, ctx)
    rstat = (result or {}).get("status") if isinstance(result, dict) else None
    msg = (result or {}).get("message") if isinstance(result, dict) else None
    links = None
    if cap.get("menu") in result_links.CONTACT_ITEMS and not (result_failed(result) or result_blocked(result)):
        links = result_links.links(ctx.get("project"), ctx.get("analysis"))
    if as_json:
        out(json.dumps({"capability": cap["id"], "route_status": cap["status"], "result_status": rstat,
                        "message": msg, "outputs": outs, "evidence_ids": ev, "limits": cap.get("limits"),
                        "result_links": links}, indent=1))
        return outs, ev
    if result_failed(result) or result_blocked(result):
        out("\n%s: %s\n  %s" % (cap["label"], rstat, msg or "(no message)"))
        return outs, ev
    lines = ["", "%s [%s]" % (cap["label"], cap["status"])]
    if cap["status"] == "EXPERIMENTAL":
        lines.append("  " + EXPERIMENTAL_NOTE)
    lines.append("  results written to:")
    lines += ["    %s" % p for p in outs] or ["    (no files)"]
    lines.append("  evidence IDs (%d):" % len(ev))
    lines += ["    %s" % e for e in ev[:10]]
    if len(ev) > 10:
        lines.append("    ... and %d more (in the files above)" % (len(ev) - 10))
    if links:
        lines += result_links.text(links)
    if cap.get("limits"):
        lines.append("  limits: %s" % cap["limits"])
    text = "\n".join(lines)
    bad = trace.wording_audit(text.replace(cap.get("limits") or "\x00", " "))
    if bad:
        text += "\n  note: the capability label or output names contain wording RNPLens does not use for results: %d hit(s)" % len(bad)
    out(text)
    return outs, ev


def choose_capability(item, cap_id=None):
    caps = item["capabilities"]
    if cap_id:
        for c in caps:
            if c["id"] == cap_id:
                return c
        raise InputError("item %s has no capability %r (available: %s)" % (item["letter"], cap_id, ", ".join(c["id"] for c in caps)))
    if len(caps) == 1:
        return caps[0]
    return None


def run_item(item, ctx, given, ask=None, out=print, cap_id=None, allow_experimental=False, as_json=False):
    if not item["available"]:
        raise Unavailable("%s %s is unavailable: %s" % (item["letter"], item["label"], "; ".join(item["reasons"])))
    cap = choose_capability(item, cap_id)
    if cap is None:
        if ask is None:
            raise InputError("item %s offers several functions; choose one with --capability (%s)"
                             % (item["letter"], ", ".join(c["id"] for c in item["capabilities"])))
        for i, c in enumerate(item["capabilities"]):
            out("  %d  %s [%s]" % (i + 1, c["label"], c["status"]))
        while cap is None:
            t = ask("function number: ")
            if t is None:
                raise InputError("input ended")
            if t.strip().isdigit() and 1 <= int(t) <= len(item["capabilities"]):
                cap = item["capabilities"][int(t) - 1]
            else:
                out("  choose 1-%d" % len(item["capabilities"]))
    if cap["status"] == "EXPERIMENTAL" and not allow_experimental:
        if ask is None:
            raise InputError("%s is EXPERIMENTAL; add --allow-experimental to run it" % cap["id"])
        out("  " + EXPERIMENTAL_NOTE)
        if (ask("run it anyway? [y/N]: ") or "").strip().lower() not in ("y", "yes"):
            return None
    vals = collect(cap, ctx, given, ask=ask, out=out)
    try:
        result = run_capability(cap, vals, out=out)
    except capabilities.DiagnoseBlocked as ex:           # a BLOCKED capability is exit 5, never a refusal (exit 4)
        ctx["last_result"] = {"kind": "menu_item", "capability": cap["id"], "label": cap["label"], "ok": False}
        raise CapabilityBlocked("%s: %s (%s)" % (cap["id"], capabilities.diagnose_blocked_text("assist"), ex))
    except Exception as ex:                              # a refusal raised by the function (e.g. a clarification answer
        from .state import StateError                    # it cannot accept) is a refusal: exit 4
        if not isinstance(ex, StateError):
            raise
        ctx["last_result"] = {"kind": "menu_item", "capability": cap["id"], "label": cap["label"], "ok": False}
        raise CapabilityFailed("%s: refused: %s" % (cap["id"], ex))
    ctx["last_result"] = {"kind": "menu_item", "capability": cap["id"], "label": cap["label"],
                          "ok": not (result_failed(result) or result_blocked(result))}
    show_result(cap, result, ctx, out=out, as_json=as_json)
    if result_blocked(result):
        raise CapabilityBlocked("%s: %s: %s" % (cap["id"], result.get("status"), (result or {}).get("message") or ""))
    if result_failed(result):
        raise CapabilityFailed("%s: %s" % (cap["id"], (result or {}).get("message") or result.get("status")))
    return result


def interactive(items, not_available, ctx, ask=input, out=print):
    out(render_menu(items, not_available, ctx["project"]))
    while True:
        try:
            t = ask("\nChoose A-F (q to quit): ")
        except EOFError:
            return 0
        if t is None or t.strip().lower() in ("q", "quit", "exit"):
            return 0
        if t.strip().lower() in ("s", "ac"):
            if not (ctx.get("last_result") or {}).get("ok") or not ctx.get("analysis"):
                out("  a follow-up needs a result first (and an analysis folder)")
                continue
            try:
                followup(ctx, "local" if t.strip().lower() == "s" else "codex", ask=_eof_safe(ask), out=out)
            except Exception as ex:
                out("  the follow-up failed: %s: %s" % (type(ex).__name__, ex))
            continue
        letter = t.strip().upper()
        item = next((i for i in items if i["letter"] == letter), None)
        if item is None:
            out("  choose one of A-F, or q")
            continue
        if not item["available"]:
            out("  %s is unavailable: %s" % (letter, "; ".join(item["reasons"])))
            continue
        try:
            run_item(item, ctx, {}, ask=_eof_safe(ask), out=out)
            if (ctx.get("last_result") or {}).get("ok") and ctx.get("analysis"):
                has_consent = os.path.isfile(os.path.join(ctx["project"], ".rnplens", "consent.json"))
                out(FOLLOWUP_HINT % (FOLLOWUP_CODEX_HINT if has_consent else ""))
        except (InputError, Unavailable) as ex:
            out("  not run: %s" % ex)
        except CapabilityBlocked as ex:
            out("  BLOCKED: %s" % ex)
        except Exception as ex:          # a failing function is reported, the menu stays open
            out("  the function failed: %s: %s" % (type(ex).__name__, ex))


def _eof_safe(ask):
    def f(prompt):
        try:
            return ask(prompt)
        except EOFError:
            return None
    return f


# ---------------------------------------------------------------- follow-ups (0.4, EXPERIMENTAL)

def _make_followup_client():
    from rnplens_assistant import codex_llm      # imported only for a Codex follow-up
    return codex_llm.CodexClient("followup_%s" % time.strftime("%H%M%S"))


def followup(ctx, mode, question=None, yes=False, choice=None, ask=None, out=print, project=None, analysis=None,
             initial=None, client_factory=None, agent_status=None):
    """One bounded follow-up on the last result (rnplens_assistant.followup.run). Codex mode needs the recorded opt-in
    (offered here when missing and interactive) and 'rnplens doctor --agent' READY; otherwise it is local-only."""
    try:
        from rnplens_assistant import consent, followup as FU     # imported only when a follow-up is requested
    except ImportError:
        out("rnplens assist: follow-ups need the RNPLens assistant package, which is not installed. Install it with "
            "'pip install ./assistant' from the RNPLens source folder (docs/installation.md). No follow-up was run.")
        return 3
    from . import doctor
    project, analysis = project or ctx["project"], analysis or ctx.get("analysis")
    if not analysis or not os.path.isfile(os.path.join(analysis, "summary.json")):
        out("rnplens assist: a follow-up needs an analysis folder with summary.json")
        return 2
    initial = initial or {k: v for k, v in (ctx.get("last_result") or {}).items() if k in ("kind", "capability")}
    if question is None:
        q = ask("Your follow-up question (Enter to use the item's label): ") if ask else None
        question = (q or "").strip() or (ctx.get("last_result") or {}).get("label") or "follow-up"
    if mode == "codex":
        ok, _, why = consent.status(ctx["project"])
        if not ok and ask is not None and not yes:
            out("No opt-in for Codex follow-ups in this project (%s)." % why)
            consent.interactive_opt_in(ctx["project"], ask, out=out)
        elif not ok:
            out("No opt-in for Codex follow-ups in this project (%s): local suggestions only, nothing is sent." % why)
    rec = FU.run(project, analysis, question, mode=mode, initial=initial, choice=choice, yes=yes, ask=ask, out=out,
                 client_factory=client_factory or _make_followup_client, agent_status=agent_status or doctor.agent_status,
                 consent_project=ctx["project"])
    out("follow-up record: %s (replay without any language model: python -m rnplens_assistant replay-followup %s "
        "--project %s --analysis %s)" % (os.path.join(analysis, rec["dir"], "followup_record.json"),
                                         os.path.join(analysis, rec["dir"], "followup_plan.json"), project, analysis))
    if rec["traceability_violations"]:
        return 4
    return 0 if rec["stop"] is None or rec["stop"]["kind"] in ("NO_CONSENT", "REJECTED", "NOT_CONFIRMED", "AGENT_NOT_READY") else 4


# ---------------------------------------------------------------- natural-language mode (gated)

def _make_client():
    from rnplens_assistant import codex_llm      # imported only in natural-language mode
    return codex_llm.CodexClient("assist_%s" % time.strftime("%H%M%S"))


def natural_language(question, ctx, task=None, nl_out=None, out=print, ask=None, client_factory=None, agent_status=None,
                     followup_mode=None, yes=False, followup_choice=None):
    from . import doctor
    ready, reasons = (agent_status or doctor.agent_status)()
    if not ready:
        out("Natural-language mode is not available here, so the question was not sent anywhere:")
        out("\n".join("  - " + r for r in reasons))
        out("The question menu answers the same kinds of questions without a language model:")
        out("  rnplens assist --project %s" % ctx["project"])
        if ask is not None and (ask("Open the question menu now? [y/N]: ") or "").strip().lower() in ("y", "yes"):
            return "menu"
        return 3
    if not task or not os.path.isdir(task):
        out("rnplens assist --nl needs --task FOLDER: the folder holding the prediction folders and FASTA files. "
            "The planner receives opaque identifiers for the files in that folder (never their names), so give the folder "
            "that holds only the inputs of this question.")
        return 2
    run_dir = os.path.abspath(nl_out or os.path.join(ctx.get("analysis") or ctx["project"], "assist_nl_%s" % time.strftime("%Y%m%dT%H%M%S")))
    if os.path.exists(run_dir):
        out("rnplens assist: %s already exists; give a new --nl-out folder" % run_dir)
        return 2
    out(NL_PRIVACY)
    out(doctor.NOTICE)
    from rnplens_assistant import ask as assistant
    client = (client_factory or _make_client)()
    rec = assistant.run(task, question, run_dir, client)
    ev = []
    p = os.path.join(run_dir, "evidence.jsonl")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                try:
                    ev.append(json.loads(line)["id"])
                except (ValueError, KeyError):
                    pass
    out("answer: %s" % os.path.join(run_dir, "answer.md"))
    out("run record: %s (replay without any language model: python -m rnplens_assistant replay %s --task %s --out NEW)"
        % (os.path.join(run_dir, "run_record.json"), os.path.join(run_dir, "plan.json"), task))
    out("evidence IDs (%d): %s" % (len(ev), ", ".join(ev[:10]) + (" ..." if len(ev) > 10 else "")))
    try:                                           # 0.4 usability: link the contact tables and the viewer page
        from rnplens_assistant import followup as _FU
        found = _FU.from_assistant_run(run_dir)
    except Exception:
        found = None
    if found:
        L = result_links.links(found[0], found[1])
        for line in result_links.text(L):
            out(line.strip() if line.startswith("  ") and not line.startswith("    ") else line)
        with open(os.path.join(run_dir, "result_links.json"), "w", encoding="utf-8") as fh:
            json.dump(L, fh, indent=1)
    mode = followup_mode
    if mode is None and ask is not None:
        t = (_eof_safe(ask)("Follow-up? s = suggested (local), ac = ask Codex, Enter = none: ") or "").strip().lower()
        mode = {"s": "local", "ac": "codex"}.get(t)
    if mode:
        try:
            from rnplens_assistant import followup as FU
        except ImportError:
            out("rnplens assist: follow-ups need the RNPLens assistant package ('pip install ./assistant'). No follow-up was run.")
            return 3
        found = FU.from_assistant_run(run_dir)
        if not found:
            out("No analysis was produced by the assistant run, so there is nothing to follow up.")
        else:
            p, a, initial = found
            followup(ctx, mode, question=question, yes=yes, choice=followup_choice, ask=_eof_safe(ask) if ask else None,
                     out=out, project=p, analysis=a, initial=initial, agent_status=agent_status)
    return 0 if rec else 1


# ---------------------------------------------------------------- command line

def main(argv=None, ask=None, out=print):
    ap = argparse.ArgumentParser(prog="rnplens assist", description="Question menu over an RNPLens project. Every item "
                                 "runs a deterministic RNPLens function; no language model is used and nothing leaves "
                                 "this computer. --nl optionally hands a question to the Codex-backed assistant "
                                 "(EXPERIMENTAL; not live-qualified).")
    ap.add_argument("--project", required=True, help="project folder written by 'rnplens import'")
    ap.add_argument("--analysis", help="analysis folder written by 'rnplens analyse --out'")
    ap.add_argument("--list", action="store_true", help="print the menu (with unavailable items and reasons) and exit")
    ap.add_argument("--item", choices=LETTERS + [x.lower() for x in LETTERS], help="run one item without prompts")
    ap.add_argument("--capability", help="function id when an item offers more than one")
    ap.add_argument("--rna", help="RNA range in construct positions, e.g. 40-60")
    ap.add_argument("--protein", help="protein range in construct positions, e.g. 10-30")
    ap.add_argument("--runs", help="runs, comma-separated (names from the project manifest)")
    ap.add_argument("--run", help="one run")
    ap.add_argument("--reference", help="experimental reference structure file")
    ap.add_argument("--run-record", help="execution record file")
    ap.add_argument("--evidence", help="evidence ID, <file>#/<pointer>")
    ap.add_argument("--param", action="append", default=[], metavar="NAME=VALUE", help="any other input a function needs")
    ap.add_argument("--allow-experimental", action="store_true", help="allow running an EXPERIMENTAL function non-interactively")
    ap.add_argument("--json", action="store_true", help="print the result (outputs, evidence IDs) as JSON")
    ap.add_argument("--nl", metavar="QUESTION", help="natural-language question (needs 'rnplens doctor --agent' READY)")
    ap.add_argument("--task", help="with --nl: folder with the prediction folders and FASTA files")
    ap.add_argument("--nl-out", help="with --nl: run folder to create")
    ap.add_argument("--followup", choices=["local", "codex"], help="after the result, one bounded follow-up (EXPERIMENTAL; docs/followup.md)")
    ap.add_argument("--question", help="with --followup: the follow-up question (default: the item's label)")
    ap.add_argument("--followup-choice", type=int, help="with --followup local: which suggestion to run (default 1)")
    ap.add_argument("--yes", action="store_true", help="confirm the follow-up without a prompt (tests and scripted use; recorded)")
    a = ap.parse_args(argv)
    try:
        man = load_manifest(a.project)
    except InputError as ex:
        print("rnplens assist: %s" % ex, file=sys.stderr)
        return 2
    ctx = {"project": os.path.abspath(a.project), "analysis": os.path.abspath(a.analysis) if a.analysis else None, "manifest": man}
    items, not_available = build_menu()
    if a.nl:
        rc = natural_language(a.nl, ctx, task=a.task, nl_out=a.nl_out, out=out,
                              ask=(ask or input) if (ask or sys.stdin.isatty()) and not a.item else None,
                              followup_mode=a.followup, yes=a.yes, followup_choice=a.followup_choice)
        if rc != "menu":
            return rc
        return interactive(items, not_available, ctx, ask=ask or input, out=out)
    if a.list:
        out(render_menu(items, not_available, ctx["project"]))
        return 0
    if a.item:
        given = {"rna_range": a.rna, "protein_range": a.protein, "two_runs": a.runs, "runs": a.runs, "run": a.run,
                 "reference": a.reference, "run_record": a.run_record, "evidence_id": a.evidence}
        for p in a.param:
            if "=" not in p:
                print("rnplens assist: --param needs NAME=VALUE, got %r" % p, file=sys.stderr)
                return 2
            k, v = p.split("=", 1)
            given[k.strip()] = v
        if a.analysis:
            given["analysis"] = a.analysis
        item = next(i for i in items if i["letter"] == a.item.upper())
        try:
            run_item(item, ctx, given, ask=None, out=out, cap_id=a.capability, allow_experimental=a.allow_experimental, as_json=a.json)
        except Unavailable as ex:
            print("rnplens assist: %s" % ex, file=sys.stderr)
            return 3
        except InputError as ex:
            print("rnplens assist: %s" % ex, file=sys.stderr)
            return 2
        except CapabilityBlocked as ex:
            print("rnplens assist: %s" % ex, file=sys.stderr)
            return EXIT_BLOCKED
        except CapabilityFailed as ex:
            print("rnplens assist: %s" % ex, file=sys.stderr)
            return 4
        if a.followup:
            return followup(ctx, a.followup, question=a.question, yes=a.yes, choice=a.followup_choice,
                            ask=None if (a.yes or not (ask or sys.stdin.isatty())) else (ask or input), out=out)
        return 0
    return interactive(items, not_available, ctx, ask=ask or input, out=out)
