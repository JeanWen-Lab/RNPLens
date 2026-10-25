"""Discoverable pytest form of the 18 established Diagnose contract checks.

tests/test_contract.py is byte-identical to the qualified RNPBench-Diagnose 0.2.1 file. Its checks are
plain functions named ``t_*``, which pytest does not collect, and it is run as a script. This module imports
that file unchanged and turns each ``t_*`` function into one parametrised test. The assertion in each
function is the check, so meaning and outcome are those of the original script.
"""
import importlib.util
import os

import pytest

_SPEC = importlib.util.spec_from_file_location("rnpbench_diagnose_contract_checks",
                                               os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_contract.py"))
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
CHECKS = sorted((k[2:], v) for k, v in vars(_MOD).items() if k.startswith("t_") and callable(v))


def test_the_established_number_of_checks_is_present():
    assert len(CHECKS) == 18, [n for n, _ in CHECKS]


@pytest.mark.parametrize("name,fn", CHECKS, ids=[n for n, _ in CHECKS])
def test_contract_check(name, fn):
    fn()
