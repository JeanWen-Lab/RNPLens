"""Render an accepted draft: fill slots from the evidence store, append the machine-generated 'not computed' list
and the evidence table. The language model never writes a number into the final answer."""
from . import evidence as EV
from .gates import SLOT

TYPE_HEAD = {"OBSERVATION": "Observed", "AGREEMENT_SUMMARY": "Across the supplied predictions", "REFERENCE_COMPARISON": "Against the supplied reference",
             "LIMITATION": "Limitation", "CLARIFICATION_REQUEST": "Needs your decision", "REFUSAL_WITH_ALTERNATIVE": "Not available here",
             "DEFINITION": "Definition"}


def fill(text, store):
    return SLOT.sub(lambda m: EV.fmt(store.get(m.group(1))), text)


def render(draft, store, notes, question, mode):
    used = []
    L = ["# RNPLens Assistant answer", "", "**Question.** %s" % question, ""]
    for s in draft["statements"]:
        L.append("- **%s.** %s" % (TYPE_HEAD.get(s["type"], s["type"]), fill(s["text"], store)))
        used += [i for i in SLOT.findall(s["text"])] + list(s.get("evidence_ids") or [])
    nc = [r for r in store.records if r["state"] != "COMPUTED"]
    if nc or notes:
        L += ["", "## Not computed or not available in this version", ""]
        seen = set()
        for r in nc:
            key = (r["state"], r["label"])
            if key not in seen:
                seen.add(key); L.append("- `%s` %s (%s)" % (r["id"], r["label"], r["state"]))
        for n in notes:
            L.append("- requested capability `%s`: %s (%s)" % (n["capability"], n["reason"], n["status"]))
    L += ["", "## Evidence cited", "", "| id | what | value | class | source |", "|---|---|---|---|---|"]
    for i in dict.fromkeys(used):
        r = store.get(i)
        if r:
            L.append("| %s | %s | %s | %s | `%s` |" % (i, r["label"].replace("|", "/"), EV.fmt(r), r["class"], r["source"]))
    L += ["", "_Answer mode: %s. Numbers are inserted from the evidence records, not written by the language model. "
          "Agreement among predictions is not evidence that a structure is right._" % mode]
    return "\n".join(L) + "\n"


def template(goal, store, notes):
    """Fixed fallback when a draft fails the gates twice: deterministic statements from the evidence only."""
    S = []
    q = [r for r in store.records if r["state"] == "IDENTITY_UNRESOLVED"]
    if q:
        S.append({"type": "CLARIFICATION_REQUEST", "text": "The import stopped with question(s) that need your decision; see the records cited.",
                  "evidence_ids": [r["id"] for r in q]})
    comp = [r for r in store.records if r["state"] == "COMPUTED" and r["class"] in ("descriptive", "reference_based")]
    if comp and not q:
        k = "REFERENCE_COMPARISON" if any(r["class"] == "reference_based" for r in comp) else "AGREEMENT_SUMMARY"
        sel = [r for r in comp if r["class"] == ("reference_based" if k == "REFERENCE_COMPARISON" else "descriptive")][:8]
        S.append({"type": k, "text": "Measured values (listed in the evidence table): " + "; ".join("{%s}" % r["id"] for r in sel),
                  "evidence_ids": [r["id"] for r in sel]})
    if notes or not S:
        S.append({"type": "REFUSAL_WITH_ALTERNATIVE", "text": "Part of this request is not available in this assistant version; the supported analyses "
                  "(contact and agreement summaries without a reference, and DockQ-family comparisons with a supplied reference) can be run instead.",
                  "evidence_ids": []})
    return {"statements": S}
