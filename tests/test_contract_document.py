"""INPUT_CONTRACT.md must agree with the implemented CLI and contract."""
import os, re
import pytest
from rnpbench_evaluate import cli, contract, frozen_loader

DOC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "INPUT_CONTRACT.md")


def _doc():
    if not os.path.exists(DOC):
        pytest.skip("docs/ not present (installed without the source tree)")
    return open(DOC).read()


def _parser_options():
    import argparse
    opts = {}
    p = argparse.ArgumentParser()
    orig = argparse.ArgumentParser.parse_args
    captured = {}
    def fake(self, args=None, namespace=None):
        captured["p"] = self; raise SystemExit(0)
    argparse.ArgumentParser.parse_args = fake
    try:
        with pytest.raises(SystemExit):
            cli.main(["evaluate"])
    finally:
        argparse.ArgumentParser.parse_args = orig
    top = captured["p"]
    sub = [a for a in top._actions if isinstance(a, argparse._SubParsersAction)][0]
    for name, sp in sub.choices.items():
        opts[name] = {s for a in sp._actions for s in a.option_strings if s.startswith("--") and s != "--help"}
    return opts


def test_every_cli_option_is_documented():
    doc = _doc()
    missing = {(c, o) for c, os_ in _parser_options().items() for o in os_ if "`%s" % o not in doc and "[%s" % o not in doc}
    assert not missing, missing


def test_every_documented_option_exists():
    doc = _doc(); opts = set().union(*_parser_options().values())
    named = set(re.findall(r"`(--[a-z-]+)`", doc))
    assert named <= opts, named - opts


def test_documented_fields_and_reasons_exist():
    doc = _doc()
    src = open(contract.__file__).read()
    for f in ("contract", "target_id", "prediction", "reference", "construct", "protein_sequence", "rna_sequence", "options", "tolerance", "designated_output", "sha256"):
        assert f in doc and '"%s"' % f in src, f
    assert contract.CONTRACT_ID in doc
    frozen = "".join(open(os.path.join(frozen_loader.FROZEN, rel)).read() for rel in ("canonical/pos_adapter.py", "canonical/rf2na_scoring.py"))
    for reason in ("METRIC_REFUSED_THE_INPUT_BEFORE_ANY_CANDIDATE", "ADAPTER_NOT_APPLIED_NO_NUMBERS_REPORTED", "NO_ADMISSIBLE_CANDIDATE_SCORED"):
        assert reason in doc and reason in frozen, reason
    for stage in ("candidate_enumeration", "adapter_application", "candidate_evaluation"):
        assert stage in doc and stage in frozen, stage


def test_explicit_scope_statements_present():
    doc = _doc().lower()
    for s in ("one user-supplied prediction at a time", "does not run structure prediction", "does not select a designated output",
              "two separate frozen evaluation routes", "never assigns zero", "gtp"):
        assert s in doc, s
