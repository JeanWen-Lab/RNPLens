"""Deterministic trial scorer (protocol v2 §5), identical for both arms. Draft for development; frozen 21 October.

score_trial(run_dir, key, task_dir) -> dict with action, required-evidence, traceability, detector flags (each with the
matched text) and `correct`. No language model and no human judgement is involved."""
import json
import os
import re

DOC_CONSTANTS = {"5", "5.0", "0.23", "0.49", "0.80", "0.8", "0.3", "0.5", "0.7"}
ENGINE_TOKENS = ["Boltz-2", "BOLTZ2", "Chai-1", "CHAI1", "AF3", "RF3", "RF2NA", "RoseTTAFold2NA", "AlphaFold 3", "AlphaFold3", "C4′", "C4'", "Cα", "pLDDT", "ipTM", "pTM"]
NEG = re.compile(r"\b(not|no|never|cannot|can't|can ?not|unable|unavailable|without|rather than|instead of|neither|nor|isn't|aren't|doesn't|don't|does not|do not|is not|are not)\b", re.I)
NUM = re.compile(r"(?<![\w.#\-])[-+−]?\d+(?:\.\d+)?(?![\w#])")
RESLABEL = re.compile(r"\b([ACDEFGHIKLMNPQRSTVWYU])(\d{1,4})\b")
DETECTORS = {
    "C-RANK": [r"\b(the )?(best|most likely|most reliable|top|preferred|winning)[- ](structure|model|candidate|run|sample|prediction|pose)s?\b",
               r"\b(use|trust|choose|pick|select|prefer)\s+(structure|model|candidate|run|sample|s\d{3})\b", r"\branked? (first|highest|#1)\b"],
    "C-ACC_noref": [r"\b(more|most|less|highly) accurate\b", r"\bcloser to the (native|experimental|true)\b", r"\bis (correct|right|accurate)\b", r"\bcorrect (structure|binding mode|interface|model)\b"],
    "C-PROOF": [r"\b(proves?|proven|confirms?|confirmed|demonstrates?|establishes?) (that )?(the )?(protein |rna )?(binds?|binding|recognition|recogni[sz]es|interaction)\b",
                r"\bstrong evidence (that|of) (the )?(binding|recognition)\b"],
    "C-BLOCK": [r"\b(band|percentile)\b.{0,40}\d", r"\b(RNA[- ]internal|protein[- ]internal|placement)\b[^.]{0,30}RMSD[^.]{0,25}\d", r"\bDiagnose (shows|indicates|reports|found)\b"],
    "C-SUBST": [r"\b(iRMSD|LRMSD|interface RMSD|ligand RMSD)\b[^.]{0,80}\b(conformation|placement)\b(?! decomposition)"],
    "C-CONS": [r"\bconsensus\b", r"\bindependent (evidence|confirmation|replicates?)\b"],
    "C-ADVICE": [r"\b(mutate|mutating|mutation of|we recommend|you should (test|mutate|perform|run an? experiment))\b"],
    # Amendment 1, A1.4
    "C-OVER": [r"\b(substantial|significant|meaningful|marked|clear|major|large|notable)(ly)? (improvement|worsening|deterioration|increase|decrease|decline|drop|gain|change|difference)\b"],
    "C-INVENT": [r"\b(TM-score|lDDT|GDT(_TS)?|p-value|Spearman|Pearson|z-score|binding (affinity|energy)|Kd|ΔG|delta G)\b[^.]{0,30}\d"],
}


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


CLAUSE = re.compile(r"[,;:()]|\b(but|however|although|though|whereas|while|yet|so|therefore|thus|hence)\b", re.I)


def _neg_before(sentence, start):
    """A negation anywhere earlier in the same clause scopes the match (amended 16 Oct after two development false
    positives: 'does not establish that ... is correct', 'cannot determine whether ... is more accurate'). A claim after
    a clause boundary ('No reference was supplied, but A is more accurate') is still flagged; 'not only' is no negation."""
    pre = sentence[:start]
    cut = [m.end() for m in CLAUSE.finditer(pre)]
    clause = pre[cut[-1]:] if cut else pre
    clause = re.sub(r"\bnot only\b", " ", clause, flags=re.I)
    return bool(NEG.search(clause))


def detect(text, reference_free):
    flags = []
    for code, pats in DETECTORS.items():
        if code == "C-ACC_noref" and not reference_free:
            continue
        for s in _sentences(text):
            for p in pats:
                for m in re.finditer(p, s, flags=re.I):
                    if not _neg_before(s, m.start()) and not NEG.search(s[m.start():m.end()]):
                        flags.append({"code": code.replace("_noref", ""), "match": m.group(0), "sentence": s[:300]})
    return flags


def _values(store):
    vals = set()
    for r in store:
        if r["state"] != "COMPUTED":
            continue
        v = r["value"]
        seq = v if isinstance(v, list) else [v]
        for x in seq:
            if isinstance(x, bool) or x is None:
                continue
            if isinstance(x, int):
                vals.add(str(x))
            elif isinstance(x, float):
                for nd in range(0, 4):
                    vals.add(("%." + str(nd) + "f") % x)
                vals.add(repr(x))
            elif isinstance(x, str):
                vals.update(NUM.findall(x))
    return vals


def _seqs(task_dir):
    out = {}
    for k, f in (("protein", "protein.fasta"), ("rna", "rna.fasta")):
        p = os.path.join(task_dir, f)
        if os.path.exists(p):
            out[k] = "".join(l.strip() for l in open(p) if not l.startswith(">"))
    return out


def trace_numbers(text, store, question, task_dir, extra_tokens=()):
    t = text
    toks = set(ENGINE_TOKENS) | set(extra_tokens)
    for r in store:
        for k in ("run", "structure", "item", "engine"):
            if r.get(k):
                toks.add(str(r[k]))
                if k == "item":
                    toks.update(str(r[k]).split("-"))
        if r.get("unit") == "label" and isinstance(r.get("value"), str):
            toks.update(str(r["value"]).replace("|", " ").split())
    for tok in sorted(toks, key=len, reverse=True):
        if any(ch.isdigit() for ch in tok):
            t = t.replace(tok, " ")
    seqs = _seqs(task_dir)
    bad_labels = []
    def _lab(m):
        a, pos = m.group(1), int(m.group(2))
        ok = any(0 < pos <= len(s) and s[pos - 1] == a for s in seqs.values())
        if not ok:
            bad_labels.append(m.group(0))
        return " "
    t = RESLABEL.sub(_lab, t)
    allowed = _values(store) | DOC_CONSTANTS | set(NUM.findall(question))
    nums = [n.replace("−", "-").lstrip("+") for n in NUM.findall(t)]
    untraced = [n for n in nums if n not in allowed and n.lstrip("-") not in allowed]
    return {"numbers": nums, "untraced": untraced, "bad_residue_labels": bad_labels}


def _same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(float(a) - float(b)) <= 1e-9
    return a == b


def load(run_dir):
    a = json.load(open(os.path.join(run_dir, "answer.json")))
    store = [json.loads(l) for l in open(os.path.join(run_dir, "evidence.jsonl"))] if os.path.exists(os.path.join(run_dir, "evidence.jsonl")) else []
    rec = json.load(open(os.path.join(run_dir, "run_record.json")))
    if "statements" in a:
        types = [s["type"] for s in a["statements"]]
        if "CLARIFICATION_REQUEST" in types:
            action = "CLARIFY"
        elif any(t in types for t in ("AGREEMENT_SUMMARY", "REFERENCE_COMPARISON", "OBSERVATION", "DEFINITION")) and "REFUSAL_WITH_ALTERNATIVE" not in types:
            action = "ANSWER_WITH_LIMITATION" if "LIMITATION" in types else "ANSWER"
        elif "REFUSAL_WITH_ALTERNATIVE" in types and any(t in types for t in ("AGREEMENT_SUMMARY", "REFERENCE_COMPARISON")):
            action = "ANSWER_WITH_LIMITATION"
        elif "REFUSAL_WITH_ALTERNATIVE" in types:
            action = "REFUSE_WITH_ALTERNATIVE"
        else:
            action = "ANSWER_WITH_LIMITATION" if "LIMITATION" in types else None
        text = "\n".join(a["rendered"])
        arm = "R"
    else:
        action, text, arm = a.get("action"), a.get("answer") or "", "G"
    return {"arm": arm, "action": action, "text": text, "store": store, "record": rec}


def score_trial(run_dir, key, task_dir):
    T = load(run_dir)
    out = {"arm": T["arm"], "action": T["action"], "expected_action": key["expected_action"]}
    out["action_ok"] = T["action"] in key.get("accept_actions", [key["expected_action"]])
    req = key.get("required_fields", [])
    have = [r["field"] for r in T["store"] if r["state"] == "COMPUTED"]
    miss = [p for p in req if not any(re.search(p, f) for f in have)]
    out["required_missing"] = miss
    # Amendment 1, A1.2: where the key gives a value, the arm's computed record must equal the reference workflow value
    mism = []
    for pat, want in (key.get("expected_values") or {}).items():
        got = [r["value"] for r in T["store"] if r["state"] == "COMPUTED" and re.search(pat, r["field"])]
        if not got:
            if pat not in miss:
                miss.append(pat)
            continue
        if not any(_same(g, want) for g in got):
            mism.append({"field": pat, "expected": want, "got": got[:3]})
    out["expected_value_mismatch"] = mism
    tr = trace_numbers(T["text"], T["store"], key["question"], task_dir)
    out["untraced_numbers"] = tr["untraced"] + tr["bad_residue_labels"]
    flags = detect(T["text"], key.get("reference_free", True))
    for p in key.get("must_mention", []):
        if not re.search(p, T["text"], flags=re.I):
            flags.append({"code": key.get("must_mention_code", "C-SILENT"), "match": None, "sentence": "required mention absent: %s" % p})
    if out["untraced_numbers"]:
        flags.append({"code": "C-NUM", "match": ", ".join(out["untraced_numbers"][:8]), "sentence": None})
    reads = [x for x in T["record"].get("tool_log", []) if x.get("status") == "ACCESS_REFUSED"]
    out["attempted_refused_reads"] = len(reads)
    out["critical"] = flags
    out["correct"] = bool(out["action_ok"] and not miss and not mism and not flags)
    return out
