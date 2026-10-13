"""Compatibility alias: RNPBench Predict is now RNPBench Report (``rnpbench_report``).

``import rnpbench_predict`` and ``import rnpbench_predict.<submodule>`` return the corresponding
``rnpbench_report`` module objects, the same objects and not copies. No scientific code lives here.
New code should import ``rnpbench_report``.
"""
import importlib
import importlib.abc
import importlib.util
import sys

_OLD, _NEW = "rnpbench_predict", "rnpbench_report"


class _AliasFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == _OLD + ".__main__":
            return None                         # rnpbench_predict's own __main__.py (python -m rnpbench_predict)
        if fullname.startswith(_OLD + "."):
            new = _NEW + fullname[len(_OLD):]
            if importlib.util.find_spec(new) is None:
                return None
            return importlib.util.spec_from_loader(fullname, self)
        return None

    def create_module(self, spec):
        return importlib.import_module(_NEW + spec.name[len(_OLD):])

    def exec_module(self, module):
        pass


if not any(isinstance(f, _AliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _AliasFinder())

from rnpbench_report import *  # noqa: E402,F401,F403
from rnpbench_report import VERSION, ContractError, SCHEMA_VERSION, load, run, validate, write  # noqa: E402,F401
