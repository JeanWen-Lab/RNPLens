"""Score and aggregate the sealed evaluation (protocol v2 §5-§7 + Amendment 1). Refuses unless every trial is
complete and the sealed set is unchanged; `--partial` produces a report labelled INCOMPLETE that is not a result.
Usage: aggregate.py SEALED_DIR RUNS_DIR OUT_JSON [--partial] [--install-record PATH]"""
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score                     # noqa: E402
from run_eval import trials, verify_sealed   # noqa: E402

ACTIONABLE = {"ANSWER", "ANSWER_WITH_LIMITATION"}
BOOT_SEED, NBOOT = 20261023, 10000
INVALID = {"REFUSED", "NEEDS_CONFIRMATION", "BUDGET_EXHAUSTED"}   # tool requests the policy or server did not execute


def clopper_pearson(k, n, a=0.05):
    from scipy.stats import beta
    lo = 0.0 if k == 0 else beta.ppf(a / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - a / 2, k + 1, n - k)
    return [float(lo), float(hi)]


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value on discordant counts b (R only) and c (G only)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def cluster_bootstrap(diffs, clusters, seed=BOOT_SEED, nboot=NBOOT):
    """Mean paired difference with a percentile interval resampling clusters (targets)."""
    groups = {}
    for d, c in zip(diffs, clusters):
        groups.setdefault(c, []).append(d)
    keys = sorted(groups)
    rng = random.Random(seed); means = []
    for _ in range(nboot):
        s = [x for k in (rng.choice(keys) for _ in keys) for x in groups[k]]
        means.append(sum(s) / len(s))
    means.sort()
    return {"mean": sum(diffs) / len(diffs), "ci95": [means[int(0.025 * nboot)], means[int(0.975 * nboot) - 1]], "n_clusters": len(keys), "n_tasks": len(diffs)}


def main(S, runs, out, partial=False, install_record=None):
    seal = verify_sealed(S)
    complete = os.path.exists(os.path.join(runs, "RUN_COMPLETE.json"))
    if not complete and not partial:
        sys.exit("REFUSING: the run is not complete (no RUN_COMPLETE.json). Use --partial for a labelled, non-result report.")
    TR = trials(S)
    keys = {t: json.load(open(os.path.join(S, "keys", t + ".json"))) for t in sorted(os.listdir(os.path.join(S, "tasks")))}
    rows = []
    for t, arm, rep in sorted(TR):
        rd = os.path.join(runs, t, arm, "rep%d" % rep)
        done = os.path.join(rd, "trial_done.json")
        if not os.path.exists(done):
            rows.append({"task": t, "arm": arm, "repeat": rep, "status": "NOT_RUN"}); continue
        td = json.load(open(done))
        if td["trial_failed_infrastructure"] or not os.path.exists(os.path.join(rd, "answer.json")):
            rows.append({"task": t, "arm": arm, "repeat": rep, "status": "INFRA_FAILED", "correct": False, "critical": []}); continue
        r = score.score_trial(rd, keys[t], os.path.join(S, "tasks", t))
        rec = json.load(open(os.path.join(rd, "run_record.json")))
        r.update(task=t, repeat=rep, status="SCORED", codex_calls=td["codex_calls"],
                 attempted_invalid=len(rec.get("rejected_steps") or []) + sum(1 for x in rec.get("tool_log", []) if x.get("status") in INVALID or x.get("error")),
                 tokens_in=sum(c.get("input_tokens") or 0 for c in rec.get("llm_calls", [])), tokens_out=sum(c.get("output_tokens") or 0 for c in rec.get("llm_calls", [])),
                 latency_s=sum(c.get("latency_s") or 0 for c in rec.get("llm_calls", [])))
        rows.append(r)
    devset = bool(json.load(open(os.path.join(S, "SEALED_MANIFEST.json"))).get("development_set"))
    label = "RESULT" if complete else "INCOMPLETE - NOT A RESULT"
    if devset:
        label = "DEVELOPMENT SET (machinery check, not the sealed evaluation) - " + label
    res = {"label": label, "development_set": devset, "sealed_manifest_sha256": seal, "n_trials": len(TR),
           "n_scored": sum(r["status"] == "SCORED" for r in rows), "n_infra_failed": sum(r["status"] == "INFRA_FAILED" for r in rows),
           "n_not_run": sum(r["status"] == "NOT_RUN" for r in rows), "arms": {}}
    counted = [t for t in keys if keys[t].get("counted", True)]
    frac = {}
    for arm in ("R", "G"):
        per = {}
        for t in counted:
            rs = [r for r in rows if r["task"] == t and r["arm"] == arm]
            ok = [bool(r.get("correct")) for r in rs if r["status"] != "NOT_RUN"]
            per[t] = {"fraction": (sum(ok) / len(ok)) if ok else None, "n_repeats": len(ok), "all_three": len(ok) == 3 and all(ok)}
        frac[arm] = per
        A = [t for t in counted if keys[t]["expected_action"] in ACTIONABLE]
        Bd = [t for t in counted if keys[t]["expected_action"] not in ACTIONABLE]
        def summ(ts):
            fs = [per[t]["fraction"] for t in ts if per[t]["fraction"] is not None]
            return {"n_tasks": len(ts), "mean_completion": (sum(fs) / len(fs)) if fs else None,
                    "tasks_all_three": sum(per[t]["all_three"] for t in ts), "per_task": {t: per[t] for t in ts}}
        crit = [f for r in rows if r["arm"] == arm and r["status"] == "SCORED" for f in r["critical"]]
        codes = {}
        for f in crit:
            codes[f["code"]] = codes.get(f["code"], 0) + 1
        sc = [r for r in rows if r["arm"] == arm and r["status"] == "SCORED"]
        res["arms"][arm] = {"actionable": summ(A), "boundary": summ(Bd), "critical_by_code": codes,
                            "critical_trials": sorted({(r["task"], r["repeat"]) for r in sc if r["critical"]}),
                            "untraced_number_trials": sum(1 for r in sc if r.get("untraced_numbers")),
                            "expected_value_mismatch_trials": sum(1 for r in sc if r.get("expected_value_mismatch")),
                            "required_missing_trials": sum(1 for r in sc if r.get("required_missing")),
                            "attempted_invalid_actions": sum(r.get("attempted_invalid", 0) for r in sc),
                            "attempted_refused_reads": sum(r.get("attempted_refused_reads", 0) for r in sc),
                            "codex_calls": sum(r.get("codex_calls", 0) for r in sc), "tokens_in": sum(r.get("tokens_in", 0) for r in sc),
                            "tokens_out": sum(r.get("tokens_out", 0) for r in sc), "latency_s": round(sum(r.get("latency_s", 0) for r in sc), 1),
                            "action_class_agreement_across_repeats": sum(1 for t in counted if len({r.get("action") for r in sc if r["task"] == t}) == 1) / max(len(counted), 1)}
    ts = [t for t in counted if frac["R"][t]["fraction"] is not None and frac["G"][t]["fraction"] is not None]
    if ts:
        diffs = [frac["R"][t]["fraction"] - frac["G"][t]["fraction"] for t in ts]
        maj = {a: {t: frac[a][t]["fraction"] >= 2 / 3 for t in ts} for a in ("R", "G")}
        b = sum(maj["R"][t] and not maj["G"][t] for t in ts); c = sum(maj["G"][t] and not maj["R"][t] for t in ts)
        res["R_vs_G"] = {"paired_difference": cluster_bootstrap(diffs, [keys[t]["cluster"] for t in ts]),
                         "mcnemar_majority": {"R_only": b, "G_only": c, "p_exact": mcnemar_exact(b, c)},
                         "note": "secondary; descriptive with 36 tasks; reported whatever its direction"}
    RA = res["arms"]["R"]["actionable"]
    gate = {"valid_task_completion": RA["mean_completion"], "completion_ge_0_90": (RA["mean_completion"] or 0) >= 0.90,
            "zero_R_critical": not res["arms"]["R"]["critical_by_code"],
            "R_traceability_100pct_in_correct": all(not r.get("untraced_numbers") for r in rows if r["arm"] == "R" and r.get("correct")),
            "all_trials_scored": res["n_scored"] == len(TR), "install_test_passed": None, "R_replay_all_match": None,
            "clopper_pearson_at_20_of_22": clopper_pearson(20, 22)}
    if install_record and os.path.exists(install_record):
        gate["install_test_passed"] = bool(json.load(open(install_record)).get("passed"))
    rp = os.path.join(runs, "REPLAY.json")
    if os.path.exists(rp):
        R = json.load(open(rp))
        gate["R_replay_all_match"] = bool(R["all_match"] and R["sealed_manifest_sha256"] == seal and R["n"] == sum(1 for x in TR if x[1] == "R"))
        gate["R_replay_counts"] = [R["n_match"], R["n"]]
    gate["inclusion"] = bool(not devset and complete and gate["R_replay_all_match"] and gate["completion_ge_0_90"] and gate["zero_R_critical"] and gate["R_traceability_100pct_in_correct"]
                             and gate["all_trials_scored"] and gate["install_test_passed"])
    res["gate"] = gate
    res["trials"] = rows
    json.dump(res, open(out, "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in res.items() if k not in ("trials", "arms")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    a = sys.argv
    ir = a[a.index("--install-record") + 1] if "--install-record" in a else None
    sys.exit(main(a[1], a[2], a[3], "--partial" in a, ir))
