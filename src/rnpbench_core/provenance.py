"""Versions and hashes of the installed RNPBench toolkit components (descriptive)."""
import importlib
import platform
import sys

COMPONENTS = (
    ("rnpbench", "rnpbench", None),
    ("rnpbench-core", "rnpbench_core", None),
    ("rnpbench-evaluate", "rnpbench_evaluate", None),
    ("rnpbench-report", "rnpbench_report", ("rnpbench_report.agreement", "VERSION")),
    ("rnpbench-diagnose", "rnpbench_diagnose", ("rnpbench_diagnose", "__version__")),
)


def _dist_version(name):
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:
        return None


def components():
    out = {}
    for dist, mod, analysis in COMPONENTS:
        try:
            m = importlib.import_module(mod)
        except ImportError:
            out[dist] = {"installed": False}
            continue
        rec = {"installed": True, "distribution_version": _dist_version(dist), "module": mod, "module_file": m.__file__}
        if analysis:
            am = importlib.import_module(analysis[0])
            rec["analysis_implementation_version"] = getattr(am, analysis[1])
        out[dist] = rec
    return out


def frozen_sources():
    from . import frozen_loader
    man = frozen_loader.verify_sources()
    return {k: v["sha256"] for k, v in man["files"].items()}


def software_versions():
    out = {"python": sys.version.split()[0], "platform": platform.platform()}
    for name in ("DockQ", "gemmi", "Bio", "numpy", "scipy", "matplotlib"):
        try:
            out[name] = importlib.import_module(name).__version__
        except Exception:
            out[name] = None
    return out
