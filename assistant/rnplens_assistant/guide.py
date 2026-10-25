"""The RNPLens analysis guide shared by both arms, read from the package itself, so that a source checkout and a
pip-installed copy give the same text (Amendment 4). A missing guide is an error, never an empty string."""
import os

GUIDE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "which_analysis_should_i_use.md")


def guide_text():
    if not os.path.exists(GUIDE):
        raise RuntimeError("RNPLens analysis guide missing from the installed package: %s" % GUIDE)
    return open(GUIDE).read()
