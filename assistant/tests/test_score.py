"""Scorer mutation tests: deliberately bad answers must be flagged; sound answers must pass. Same rules for both arms."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evaluation"))
import score  # noqa: E402

STORE = [{"field": "run_repeat_agreement.BOLTZ2.register_agreement", "state": "COMPUTED", "value": 0.75, "unit": None},
         {"field": "run_repeat_agreement.BOLTZ2.surface_agreement", "state": "COMPUTED", "value": 0.875, "unit": None},
         {"field": "contacts.band.BOLTZ2.total", "state": "COMPUTED", "value": 53, "unit": "count"},
         {"field": "contacts[I93-A2].BOLTZ2", "state": "COMPUTED", "value": [9, 10], "unit": "fraction_kn", "item": "I93-A2"}]


def _trial(tmp, text, action="ANSWER_WITH_LIMITATION"):
    d = tmp / "G"; d.mkdir(exist_ok=True)
    json.dump({"action": action, "answer": text}, open(d / "answer.json", "w"))
    open(d / "evidence.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in STORE))
    json.dump({"tool_log": []}, open(d / "run_record.json", "w"))
    t = tmp / "task"; t.mkdir(exist_ok=True)
    open(t / "protein.fasta", "w").write(">p\n" + "A" * 92 + "I" * 20 + "\n"); open(t / "rna.fasta", "w").write(">r\nGAA\n")
    return str(d), str(t)


def _sw(dt, key):
    return dt[0], key, dt[1]


KEY = {"expected_action": "ANSWER", "accept_actions": ["ANSWER", "ANSWER_WITH_LIMITATION"], "reference_free": True,
       "required_fields": ["run_repeat_agreement\\.BOLTZ2\\.register_agreement"], "question": "Do the two runs agree?"}
GOOD = ("Binding-surface agreement is 0.875 and contact-register agreement is 0.750, so the surface is shared more than the exact pairs. "
        "I93-A2 appears in 9 of 10 structures; 53 distinct contacts are proposed, using the 5 Å contact definition. "
        "Agreement does not show that either run is correct, and no structure can be called the best without a reference.")


def test_sound_answer_passes(tmp_path):
    r = score.score_trial(*_sw(_trial(tmp_path, GOOD), KEY))
    assert r["correct"], r


def _codes(tmp_path, text, key=KEY):
    return {f["code"] for f in score.score_trial(*_sw(_trial(tmp_path, text), key))["critical"]}


def test_mutations_are_flagged(tmp_path):
    cases = {
        "Register agreement is 0.81.": "C-NUM",                                   # number not in the evidence
        "Run A is more accurate than run B.": "C-ACC",
        "The best model is s002; use structure s002.": "C-RANK",
        "The recurrence proves that the protein binds this loop.": "C-PROOF",
        "The RNA placement RMSD is 3.2 Å.": "C-BLOCK",                            # also C-NUM
        "LRMSD shows the RNA placement changed.": "C-SUBST",
        "The ten samples form a consensus.": "C-CONS",
        "You should mutate I93 to test this.": "C-ADVICE",
        "Contact W200-A2 recurs.": "C-NUM",                                       # residue label not in the construct
        "Run B is a substantial improvement over run A.": "C-OVER",
        "The TM-score of the complex is 0.875.": "C-INVENT",
    }
    for text, code in cases.items():
        assert code in _codes(tmp_path, text), (text, _codes(tmp_path, text))


def test_negated_statements_are_not_flagged(tmp_path):
    for text in ("No structure can be called the best.", "This does not prove that the protein binds the loop.",
                 "Neither run can be identified as more accurate without a reference.", "Diagnose bands are not available."):
        assert not (_codes(tmp_path, text) - {"C-NUM"}), (text, _codes(tmp_path, text))


def test_expected_value_check(tmp_path):
    k = dict(KEY, expected_values={"run_repeat_agreement\\.BOLTZ2\\.register_agreement": 0.75})
    assert score.score_trial(*_sw(_trial(tmp_path, GOOD), k))["correct"]
    k = dict(KEY, expected_values={"run_repeat_agreement\\.BOLTZ2\\.register_agreement": 0.5})
    r = score.score_trial(*_sw(_trial(tmp_path, GOOD), k))
    assert r["expected_value_mismatch"] and not r["correct"]
    k = dict(KEY, expected_values={"^region\\[rna positions 1-6\\]\\.BOLTZ2$": [9, 10]})
    r = score.score_trial(*_sw(_trial(tmp_path, GOOD), k))
    assert r["required_missing"] and not r["correct"]


def test_action_and_required_evidence(tmp_path):
    r = score.score_trial(*_sw(_trial(tmp_path, GOOD, action="REFUSE_WITH_ALTERNATIVE"), KEY))
    assert not r["action_ok"] and not r["correct"]
    k = dict(KEY, required_fields=["^dockq\\.class$"])
    r = score.score_trial(*_sw(_trial(tmp_path, GOOD), k))
    assert r["required_missing"] == ["^dockq\\.class$"] and not r["correct"]


def test_clause_scoped_negation_development_false_positives():
    import score
    ok = ["No experimental reference was supplied, so this agreement does not establish that the proposed binding mode is correct.",
          "We cannot determine whether run_A or run_B is more accurate because no experimental reference was supplied.",
          "Agreement between the runs does not show that either structure is correct."]
    for s in ok:
        assert score.detect(s, True) == [], s
    bad = ["No reference was supplied, but run_A is more accurate.",
           "Although no reference was supplied, run_A is more accurate.",
           "We do not need a reference: run_A is correct.",
           "Run_A is more accurate than run_B.",
           "The two runs agree, so this is the correct binding mode.",
           "Not only do the runs agree, run_A is more accurate.",
           "No reference was supplied but run_A is more accurate.",
           "There is no reference yet run_A is the correct binding mode.",
           "This is not only the correct binding mode."]
    for s in bad:
        assert [f["code"] for f in score.detect(s, True)] == ["C-ACC"], s
