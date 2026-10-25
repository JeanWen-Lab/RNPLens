"""U3 (QA outside-user-viewer, fix round): the menu's RNA-range prompt gives an example inside the construct, built
from its length, instead of the fixed "e.g. 40-60" (outside a 4-nt or 20-nt RNA)."""
from rnplens import assist


def _ctx(rna, prot=100):
    return {"manifest": {"construct": {"rna_length": rna, "protein_length": prot}, "runs": [{"run": "run_A"}, {"run": "run_B"}]}}


def test_rna_prompt_example_lies_inside_the_construct():
    assert assist.prompt_text("rna_range", _ctx(4)) == "RNA range (construct positions 1-4, e.g. 1-4)"
    assert assist.prompt_text("rna_range", _ctx(60)) == "RNA range (construct positions 1-60, e.g. 1-20)"
    for n in (1, 3, 20, 21, 500):
        t = assist.prompt_text("rna_range", _ctx(n))
        lo, hi = t.split("e.g. ")[1].rstrip(")").split("-")
        assert 1 <= int(lo) <= int(hi) <= n and "40-60" not in t


def test_other_prompts_unchanged():
    assert assist.prompt_text("protein_range", _ctx(4, 98)) == "protein range (construct positions 1-98, e.g. 10-30)"
    assert assist.prompt_text("two_runs", _ctx(4)) == "two runs, comma-separated (1=run_A, 2=run_B)"
