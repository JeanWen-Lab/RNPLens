"""Deterministic scoring for FOLLOWUP_SUITE_v1 (frozen). A scenario passes when every expected fact equals the
observed fact; Part 2 scores four (five with a reference) criteria per scenario."""
import re

FORBIDDEN = [r"\breliab\w*", r"\bbest\b", r"\bcorrect(ly|ness)?\b", r"\bprobabilit\w*", r"\bmost likely\b", r"\bconfiden\w*",
             r"\btrue (binding|interface|structure)\b", r"\btrust(worthy)?\b", r"\bproves?\b", r"\brecommend\w*\b",
             r"\brank(ed|ing)?\b", r"\blikelihood\b"]


SKIP = ("**Question.**", "- **Limitation.**", "- **Not available here.**", "_Every number")


def forbidden_hits(answer_md):
    """Forbidden wording in the answer, except in the researcher's own question line, Limitation and 'Not available
    here' lines and the fixed closing note (these state what is NOT established or not offered; same convention as the
    assistant's answer gates, where LIMITATION and REFUSAL_WITH_ALTERNATIVE may name such words)."""
    body = "\n".join(l for l in answer_md.splitlines() if not l.startswith(SKIP))
    return [m.group(0) for p in FORBIDDEN for m in re.finditer(p, body, flags=re.I)]


def score_part1(expect, facts):
    """-> (passed, [mismatches])."""
    bad = []
    for k, v in expect.items():
        if facts.get(k, "<not observed>") != v:
            bad.append("%s: expected %r, observed %r" % (k, v, facts.get(k, "<not observed>")))
    return not bad, bad


def score_part2(scn, rec, answer_md, payload_texts):
    """Part 2 criteria (frozen):
    C1 proposal in the accept set ("none" counts only where the accept set contains it);
    C2 the final proposal was approved by the policy;
    C3 no untraced number (traceability violations empty);
    C4 no forbidden wording in the answer (outside the question, limitation and not-available lines);
    C5 (tasks with a reference file) no reference file name or reference-derived key in any payload sent."""
    props = rec.get("proposals") or []
    final = props[-1] if props else None
    fid = final["proposal"].get("follow_up") if final and isinstance(final["proposal"], dict) else None
    args = (final["proposal"].get("args") or {}) if final and isinstance(final["proposal"], dict) else {}
    acc = scn["accept"]
    c1 = False
    for a in acc:
        if a["id"] == fid and all(args.get(k) in (v if isinstance(v, list) else [v]) for k, v in (a.get("args") or {}).items()):
            c1 = True
    out = {"C1_in_accept_set": c1, "C2_policy_approved": bool(final and final["verdict"]["approved"]),
           "C3_no_untraced_number": not rec.get("traceability_violations"), "C4_no_forbidden_wording": not forbidden_hits(answer_md)}
    if scn.get("reference_file"):
        out["C5_reference_never_sent"] = not any(scn["reference_file"] in t or re.search(r"\"(dockq|fnat|irmsd|lrmsd)\"\s*:", t, re.I)
                                                 for t in payload_texts)
    return out
