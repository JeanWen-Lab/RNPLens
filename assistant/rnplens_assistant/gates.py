"""S8: deterministic checks on a drafted answer. A draft is accepted only when every gate passes.

The gates check form and evidential basis: that numbers come from computed evidence, that each statement type cites
the kind of evidence it may cite, that agreement at one level is not propagated to another, that accuracy wording
appears only with reference-based evidence, that no forbidden or unavailable capability is asserted, and that the
answer addresses its goal. They cannot establish that an interpretation is biologically right; expert review does
that."""
import re

TYPES = {  # statement type -> evidence classes it may cite (empty set: may cite none)
    "OBSERVATION": {"observed"},
    "AGREEMENT_SUMMARY": {"descriptive", "observed"},
    "REFERENCE_COMPARISON": {"reference_based", "observed"},
    "LIMITATION": {"not_computed", "documentation", "observed", "descriptive", "reference_based"},
    "CLARIFICATION_REQUEST": {"not_computed", "observed"},
    "REFUSAL_WITH_ALTERNATIVE": {"not_computed", "documentation", "observed"},
    "DEFINITION": {"documentation"},
}
NEEDS_EVIDENCE = {"OBSERVATION", "AGREEMENT_SUMMARY", "REFERENCE_COMPARISON", "DEFINITION"}
SLOT = re.compile(r"\{(E\d+)\}")
BANNED = [r"\breliab\w*", r"\bbest\b", r"\bcorrect(ly|ness)?\b", r"\bprobabilit\w*", r"\baccura(te|cy)\b", r"\bmost likely\b",
          r"\bconfidence of\b", r"\btrue (binding|interface|structure)\b", r"\btrust(worthy)?\b", r"\bvalidated (binding|mechanism|interaction)\b",
          r"\bconfirm(s|ed)? (the )?(binding|mechanism|interaction)\b", r"\bproves?\b", r"\brecommend\w*\b", r"\bmutat\w*\b"]
ACCURACY_WORDS = [r"\bimprov\w*", r"\bworse\w*", r"\bbetter\b", r"\bcloser to the (experimental|reference)", r"\bnative-like\b",
                  r"\bDockQ\b", r"\bfnat\b", r"\biRMSD\b", r"\bLRMSD\b", r"\bacceptable\b", r"\bincorrect\b", r"\bhigh quality\b", r"\bmedium quality\b"]
UNAVAILABLE_WORDS = [r"\bband\b", r"\bpercentile\b", r"\bDiagnose (shows|indicates|found|reports)\b", r"\bRNA[- ]internal RMSD\b",
                     r"\bplacement RMSD\b", r"\bprotein[- ]internal RMSD\b", r"\brank(ed|ing)?\b", r"\btop[- ]ranked\b"]
REGISTER_WORDS = [r"\bregister\b", r"\bresidue[-–]nucleotide\b", r"\bcontact pairs?\b", r"\bpairings?\b", r"\bexact contacts?\b"]
SURFACE_WORDS = [r"\bsurface\b"]
GOAL_TYPES = {"AGREEMENT": {"AGREEMENT_SUMMARY"}, "REGION_CLAIM": {"AGREEMENT_SUMMARY"}, "COMPARE": {"REFERENCE_COMPARISON"},
              "WHICH_ANALYSIS": {"REFUSAL_WITH_ALTERNATIVE", "LIMITATION", "CLARIFICATION_REQUEST", "AGREEMENT_SUMMARY", "REFERENCE_COMPARISON"},
              "EXPLAIN_METRIC": {"DEFINITION"}, "UNSUPPORTED": {"REFUSAL_WITH_ALTERNATIVE", "CLARIFICATION_REQUEST"}}


def _any(pats, text):
    return [m.group(0) for p in pats for m in re.finditer(p, text, flags=re.I)]


def check(draft, store, goal, allowed_tokens, reference_supplied):
    """-> list of violations (empty = accepted). allowed_tokens: identifiers that may contain digits (run names,
    structure ids, engine names, file names) because they come from the inventory, not from a measurement."""
    v = []
    sts = draft.get("statements") or []
    if not sts:
        return ["A0 no statements"]
    types = {s.get("type") for s in sts}
    unresolved = [r for r in store.records if r["state"] == "IDENTITY_UNRESOLVED"]
    for k, s in enumerate(sts):
        t, text, ids = s.get("type"), s.get("text") or "", s.get("evidence_ids") or []
        tag = "statement %d (%s)" % (k + 1, t)
        if t not in TYPES:
            v.append("A2 %s: unknown statement type" % tag); continue
        slots = SLOT.findall(text)
        cited = set(ids) | set(slots)
        recs = {i: store.get(i) for i in cited}
        for i, r in recs.items():
            if r is None:
                v.append("A1 %s: cites %s, which is not in the evidence store" % (tag, i))
        recs = {i: r for i, r in recs.items() if r is not None}
        for i in slots:
            r = recs.get(i)
            if r is not None and r["state"] != "COMPUTED":
                v.append("A1 %s: slot {%s} is a %s record and cannot supply a value" % (tag, i, r["state"]))
        bare = SLOT.sub(" ", text)
        for tok in allowed_tokens:
            bare = bare.replace(tok, " ")
        digits = re.findall(r"[^\s]*\d[^\s]*", bare)
        if digits:
            v.append("A1 %s: number(s) written outside evidence slots: %s" % (tag, ", ".join(digits[:5])))
        if t in NEEDS_EVIDENCE and not recs:
            v.append("A2 %s: cites no evidence" % tag)
        for i, r in recs.items():
            if r["class"] not in TYPES[t]:
                v.append("A2 %s: %s is %s evidence, which a %s statement may not cite" % (tag, i, r["class"], t))
        levels = {r["level"] for r in recs.values()}
        if _any(REGISTER_WORDS, bare) and t in ("AGREEMENT_SUMMARY", "OBSERVATION") and "EXACT_CONTACT" not in levels:
            v.append("A3 %s: speaks of contact pairs/register but cites no exact-contact evidence" % tag)
        if _any(SURFACE_WORDS, bare) and t in ("AGREEMENT_SUMMARY",) and not levels & {"PROTEIN_SURFACE", "EXACT_CONTACT"}:
            v.append("A3 %s: speaks of a binding surface but cites no surface evidence" % tag)
        acc = _any(ACCURACY_WORDS, bare)
        if acc and t not in ("REFERENCE_COMPARISON", "LIMITATION", "REFUSAL_WITH_ALTERNATIVE", "DEFINITION", "CLARIFICATION_REQUEST"):
            v.append("A4 %s: reference-based wording (%s) outside a reference comparison" % (tag, ", ".join(sorted(set(acc)))))
        if t == "REFERENCE_COMPARISON" and (not reference_supplied or not any(r["class"] == "reference_based" for r in recs.values())):
            v.append("A4 %s: a reference comparison needs a supplied reference and reference-based evidence" % tag)
        ban = _any(BANNED, bare)
        if ban and t not in ("LIMITATION", "REFUSAL_WITH_ALTERNATIVE"):
            v.append("A5 %s: forbidden wording: %s" % (tag, ", ".join(sorted(set(ban)))))
        un = _any(UNAVAILABLE_WORDS, bare)
        if un and t not in ("LIMITATION", "REFUSAL_WITH_ALTERNATIVE"):
            v.append("A6 %s: refers to an unavailable capability: %s" % (tag, ", ".join(sorted(set(un)))))
    if unresolved and "CLARIFICATION_REQUEST" not in types:
        v.append("A8 identity questions are open but no CLARIFICATION_REQUEST statement asks them")
    need = GOAL_TYPES.get(goal, set())
    if not unresolved and need and not types & need and not types & {"REFUSAL_WITH_ALTERNATIVE", "CLARIFICATION_REQUEST"}:
        v.append("A8 the answer has no statement of a type that addresses goal %s (%s)" % (goal, "/".join(sorted(need))))
    for s in sts:
        if s.get("type") == "REFUSAL_WITH_ALTERNATIVE" and not re.search(r"\b(can|could|instead|available|offer)\b", s.get("text") or "", re.I):
            v.append("A9 a refusal must name the supported alternative")
    return v
