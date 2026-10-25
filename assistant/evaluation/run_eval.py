"""Run the sealed evaluation (protocol v2 + Amendment 1). Resumable; refuses to start unless the sealed set and the
model catalog match their frozen hashes. Usage: run_eval.py SEALED_DIR RUNS_DIR [--max-trials N]

Order: all (task, arm, repeat) trials, including the uncounted regression task, shuffled with seed 20261022.
Before every trial, the usage guard checks every reported rate-limit window and the credits balance (codex_llm). It
also projects the remaining trials from the usage rise observed so far and stops before the projection crosses 85%.
Nothing here can buy credits or switch to API billing."""
import hashlib
import json
import os
import random
import subprocess
import sys
import time

from rnplens_assistant import ask, baseline_codex, codex_llm

FROZEN_CATALOG_SHA256 = "aad73e9b5e49738ce963efcfcfc6855ba25dbb6f9cf9470384a7f99c352d763f"
ORDER_SEED, REPEATS, GUARD = 20261022, 3, 85.0
CODEX = "/home/jwen/.local/bin/codex"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def verify_sealed(S):
    man = os.path.join(S, "SEALED_MANIFEST.json")
    want = open(os.path.join(S, "SEALED_MANIFEST.sha256")).read().split()[0]
    assert sha(man) == want, "REFUSING: SEALED_MANIFEST.json does not match its recorded hash"
    files = json.load(open(man))["files"]
    bad = [f for f, h in files.items() if not os.path.exists(os.path.join(S, f)) or sha(os.path.join(S, f)) != h]
    assert not bad, "REFUSING: %d sealed file(s) changed or missing, e.g. %s" % (len(bad), bad[:3])
    return want


def verify_catalog():
    p = subprocess.run([CODEX, "debug", "models"], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    h = hashlib.sha256(p.stdout.encode()).hexdigest()
    assert h == FROZEN_CATALOG_SHA256, "REFUSING: Codex model catalog changed (%s); the frozen model may differ" % h
    return h


def trials(S):
    tasks = sorted(os.listdir(os.path.join(S, "tasks")))
    T = [(t, arm, r) for t in tasks for arm in ("R", "G") for r in range(1, REPEATS + 1)]
    random.Random(ORDER_SEED).shuffle(T)
    return T


def usage_state(runs):
    """(first_used, last_used, n_trials_done_with_usage) from completed trial records, for projection."""
    recs = []
    for dp, dn, fn in os.walk(runs):
        if "trial_done.json" in fn:
            d = json.load(open(os.path.join(dp, "trial_done.json")))
            if d.get("plan_used_percent_max") is not None:
                recs.append((d["finished_epoch"], d["plan_used_percent_max"]))
    recs.sort()
    return (recs[0][1], recs[-1][1], len(recs)) if recs else (None, None, 0)


def main(S, runs, max_trials=None):
    seal = verify_sealed(S)
    cat = verify_catalog()
    os.makedirs(runs, exist_ok=True)
    meta = os.path.join(runs, "RUN_META.json")
    if not os.path.exists(meta):
        json.dump({"sealed_manifest_sha256": seal, "catalog_sha256": cat, "order_seed": ORDER_SEED, "config": codex_llm.CONFIG,
                   "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, open(meta, "w"), indent=1)
    else:
        m = json.load(open(meta))
        assert m["sealed_manifest_sha256"] == seal and m["catalog_sha256"] == cat, "REFUSING: resumed run differs from the started run"
    TR = trials(S); done = 0
    for n, (task, arm, rep) in enumerate(TR):
        rd = os.path.join(runs, task, arm, "rep%d" % rep)
        if os.path.exists(os.path.join(rd, "trial_done.json")):
            done += 1; continue
        if max_trials is not None and done >= max_trials:
            break
        first, last, k = usage_state(runs)
        if last is not None:
            if last >= GUARD:
                return stop(runs, "plan usage %.1f%% reached the guard" % last)
            rate = (last - first) / max(k - 1, 1)
            proj = last + rate * (len(TR) - k)
            if proj >= GUARD:
                return stop(runs, "projected usage %.1f%% at completion would cross the %.0f%% guard (rate %.3f%%/trial)" % (proj, GUARD, rate))
        key = json.load(open(os.path.join(S, "keys", task + ".json")))
        td = os.path.join(S, "tasks", task)
        attempt_log = []
        for attempt in (1, 2):
            if os.path.exists(rd):        # an interrupted or failed attempt is kept, never overwritten
                os.rename(rd, "%s.attempt_%d_%d" % (rd, attempt, int(time.time())))
            cl = codex_llm.CodexClient("ev_%s_%s_%d" % (task, arm, rep))
            t0 = time.time()
            try:
                rec = ask.run(td, key["question"], rd, cl) if arm == "R" else baseline_codex.run(td, key["question"], rd, cl)
                err = rec.get("error") if arm == "G" else None
                infra = err is not None            # comparator: Codex exited before giving its final answer
            except codex_llm.UsageGuard as ex:
                return stop(runs, "usage guard: %s" % ex)
            except Exception as ex:
                infra, err, rec = True, "%s: %s" % (type(ex).__name__, str(ex)[:300]), {}
            attempt_log.append({"attempt": attempt, "infra_failure": infra, "error": err, "wall_s": round(time.time() - t0, 1)})
            if not infra:
                break
        used = [c.get("plan_used_percent") for c in cl.calls if c.get("plan_used_percent") is not None]
        os.makedirs(rd, exist_ok=True)
        json.dump({"task": task, "arm": arm, "repeat": rep, "order_index": n, "attempts": attempt_log,
                   "trial_failed_infrastructure": attempt_log[-1]["infra_failure"], "codex_calls": len(cl.calls),
                   "plan_used_percent_max": max(used) if used else None,
                   "credits_balance": [c.get("credits_balance") for c in cl.calls][-1:] or None,
                   "models_returned": sorted({c.get("model_returned") for c in cl.calls if c.get("model_returned")}),
                   "finished_epoch": time.time()}, open(os.path.join(rd, "trial_done.json"), "w"), indent=1)
        done += 1
        print("[%d/%d] %s %s rep%d %s" % (done, len(TR), task, arm, rep, "INFRA-FAIL" if attempt_log[-1]["infra_failure"] else "ok"), flush=True)
    complete = all(os.path.exists(os.path.join(runs, t, a, "rep%d" % r, "trial_done.json")) for t, a, r in TR)
    if complete:
        json.dump({"complete": True, "n_trials": len(TR), "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, open(os.path.join(runs, "RUN_COMPLETE.json"), "w"), indent=1)
    print("trials done: %d of %d; complete: %s" % (done, len(TR), complete))
    return 0


def stop(runs, why):
    json.dump({"stopped": True, "reason": why, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, open(os.path.join(runs, "STOPPED.json"), "w"), indent=1)
    print("STOPPED:", why)
    return 3


if __name__ == "__main__":
    mt = int(sys.argv[sys.argv.index("--max-trials") + 1]) if "--max-trials" in sys.argv else None
    sys.exit(main(sys.argv[1], sys.argv[2], mt))
