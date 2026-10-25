"""Known-input checks for the aggregation statistics (before they touch real data)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evaluation"))
import aggregate  # noqa: E402


def test_bootstrap_constant_shift_is_exact_and_excludes_zero():
    r = aggregate.cluster_bootstrap([1 / 3] * 36, ["t%d" % i for i in range(36)])
    assert abs(r["mean"] - 1 / 3) < 1e-12 and abs(r["ci95"][0] - 1 / 3) < 1e-12 and r["ci95"][0] > 0


def test_bootstrap_zero_centred_includes_zero_and_is_seeded():
    d = [1.0, -1.0] * 18
    r1 = aggregate.cluster_bootstrap(d, ["t%d" % i for i in range(36)]); r2 = aggregate.cluster_bootstrap(d, ["t%d" % i for i in range(36)])
    assert r1["ci95"][0] < 0 < r1["ci95"][1] and r1 == r2


def test_bootstrap_resamples_clusters_not_items():
    r = aggregate.cluster_bootstrap([1.0, 1.0, 0.0, 0.0], ["a", "a", "b", "b"])
    assert r["n_clusters"] == 2 and r["n_tasks"] == 4


def test_mcnemar_and_clopper_pearson():
    assert aggregate.mcnemar_exact(0, 0) == 1.0
    assert abs(aggregate.mcnemar_exact(6, 0) - 0.03125) < 1e-12        # 2 * 0.5**6
    lo, hi = aggregate.clopper_pearson(20, 22)
    assert 0.70 < lo < 0.72 and 0.98 < hi < 0.99
