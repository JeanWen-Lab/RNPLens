# Amendment 8 to LIVE_QUALIFICATION_v1 (2026-10-19, Canberra): call-specific authorisation, bound to the exact inputs

Approved by the owner on 2026-10-19 for implementation (owner decisions of 19 October 2026, section 2: "a live-call
authorization is valid only for the exact: full source commit; model and reasoning configuration; model-visible
payload checksum; scientific tool and security configuration; approved input/project identity; maximum number of
model calls. The launcher must reject an authorization issued for a different source or experiment.").
Implemented on `rc/0.4-candidate` from head `8c64601` (Amendment 7). It extends the earlier proposal
(`AMENDMENT_8_BINDING.PROPOSED.patch`, 6 fields) to the owner's full list.

Frozen **before any run of this suite at this head, mocked or live**. No Codex or other language-model call has been
made for RNPLens 0.4. Earlier approvals and records are kept unmodified as historical records: the earlier one-call
approval for a 2JEA development test, `LIVE_CALL_AUTHORISATION_RECORD_8c64601.md`, and AMENDMENT_1–7. **None of them
authorises a call under this amendment.**

## 1. What changes (run_live.py only)

The owner's confirmation file becomes a **call-specific authorisation**. Besides the existing lines (header, date,
statement, credit_balance, weekly_usage_percent, optional acknowledge_abort), it must name **all 18** of the following
values, each exactly once:

| field | the driver recomputes it as |
|---|---|
| `experiment` | `LIVE_QUALIFICATION_v1` |
| `mode` | `first-call` or `continue-after-first`: the mode being invoked |
| `run_id` | the `--run-id` being invoked |
| `scenario` | first-call: the first-call scenario (`P01`); continue: the remaining scenario ids, in order |
| `task` | the development task(s) of those scenarios |
| `target` | the target(s) named in the task id (`d1_7K9D_agreement` → `7K9D`) |
| `task_sha256` | content identity of the task folder(s): sha256 over sorted `relative path<TAB>sha256` lines; several tasks: sha256 of their `name digest` lines |
| `commit` | the checkout's full `git rev-parse HEAD` |
| `model`, `reasoning_effort` | `codex_llm.CONFIG` (`gpt-6.1-sol`, `medium`; also checked against the suite's MODEL/EFFORT, as before) |
| `payload_sha256` | the model-visible first planning payload of the scenario, reconstructed with no model (system + separator + user); several scenarios: sha256 of their `id sha256` lines |
| `registry_sha256` | `assistant/rnplens_assistant/registry.json` (the scientific tools the planner may use) |
| `jail_sha256` | the jail script `codex_jail.sh` |
| `freeze_sha256` | this suite's FREEZE.md, which transitively pins scenarios.json and its 22 pinned sources |
| `codex_sha256` | the Codex binary the jail runs (`RNPLENS_CODEX_BIN`, else `$CODEX_HOME/packages/standalone/current/bin/codex`; never PATH) |
| `bwrap_sha256` | `bwrap` |
| `python_sha256` | the running interpreter (`sys.executable`, resolved) |
| `max_model_calls` | first-call `1`; continue `23` (`LEDGER_CAP - 1`) |

Checks:
- **Preflight**, before anything is created or called. Every value is recomputed. A missing field ("authorisation X
  missing"), a wrong value ("authorisation X … does not match …: an authorisation for other inputs or another
  experiment does not cover this one") or any extra line ("unknown line") refuses with exit 3. Nothing is written,
  and nothing is attempted in the ledger.
- **Reuse is refused.** Mode and run id are bound, so a first-call authorisation cannot be used for
  `--continue-after-first` or for another run. Scenario, task, target and task content are bound, so an approval
  worded for 2JEA cannot cover P01 on 7K9D.
- **Guard**, before each call. The sha256 of the actual prompt of a planning call must equal the authorised payload
  for its scenario, in addition to the existing exact-bytes reconstruction check. The number of model calls in the
  invocation may not exceed `max_model_calls`. Either failure refuses with `AUTHORISATION`, before anything is sent.
- **Record.** `run_record.json` stores the bound values (`authorisation_bound`); a continue invocation keeps the
  previous one in `authorisation_history`.
- **`--plan --run-id ID`** (no call, nothing written) prints the exact values for both modes, so the owner can be
  shown what will be bound.
- **Follow-up payloads** (Part F) depend on the analysis and cannot be reconstructed before the run. They remain
  covered by the pre-send gate and the frozen premise record, not by `payload_sha256`. The single P01 first call has
  no follow-up call.

`run_live.py`: `173d266e78bb33431585ba696042f9e9c621b74b8987239ba097ab52d39cd184` → `015a75452c64223e79cb0a88676178bc2dd1cfe62c44f524f2feae10b1c3f440`. Diff (below) sha256 `2310cd99b40e42967ebba3a2c36ea472853a621f2ac19e2f709fc272b2505fe3`.
Tests (`assistant/tests/test_live_qualification.py`, not a frozen file;  1 file changed, 106 insertions(+), 7 deletions(-)):
- every mocked run uses an authorisation computed for its own mode and run id;
- new tests: each of the 18 fields wrong, and missing, is refused with no ledger attempt; an extra field; another
  experiment (run id, mode, scenario, a 2JEA task or target, the experiment, the call count); a first-call
  authorisation reused to continue; changed task content; the Guard's payload and call-count refusals; the values
  printed by `--plan`;
- the karyon real-jail tests use separate first-call and continue authorisations.

## 2. Pins and freeze

- **Pins unchanged.** No pinned source changed: scenarios.json and all 22 pins are unchanged, and scenarios.json is
  still `5c957e334e53c1962e735964ac1507d15285afd1a4050db984c388d587957a5e`.
- **FREEZE.md.** It gains this paragraph and the new hashes of run_live.py and AMENDMENT_8.md. Previous FREEZE.md:
  `edceda7892913e215fb5384f0d3a3275ba877c9deda800f5d86bdc01ccab104d`.
- **Payloads unchanged.** No prompt, guide, planner, redaction or follow-up code changed. The premise check is rerun
  at this head and recorded in the readiness report.

## 3. Unchanged

- **Expectations.** No scenario, question, expectation, threshold, guard value, budget (max 24 live calls, nominal
  12), scoring or decision rule changed.
- **Owner steps.** The one-call-then-inspection rule and the go-ahead file are unchanged.
- **Suite files.** DESIGN.md, score_live.py, privacy.py, fake_codex.py, the premise scripts and records,
  AMENDMENT_1–7 and FOLLOWUP_SUITE_v1.

## 4. Development note

- Before this freeze, the draft was exercised once in a throw-away scratch worktree: `test_live_qualification.py`,
  61 passed and 2 skipped on macOS. That worktree's FREEZE.md row was edited for that run only, and nothing of it was
  committed.
- The suite runs at this head follow this freeze.

## Exact diff of run_live.py

```diff
diff --git a/assistant/evaluation_v04/LIVE_QUALIFICATION_v1/run_live.py b/assistant/evaluation_v04/LIVE_QUALIFICATION_v1/run_live.py
index 25998fc..590b33a 100644
--- a/assistant/evaluation_v04/LIVE_QUALIFICATION_v1/run_live.py
+++ b/assistant/evaluation_v04/LIVE_QUALIFICATION_v1/run_live.py
@@ -188,6 +188,86 @@ def parse_decimal(x):
     return decimal.Decimal(s)
 
 
+# ---------------------------------------------------------------- Amendment 8: call-specific authorisation binding
+AUTH_KEYS = ("experiment", "mode", "run_id", "scenario", "task", "target", "task_sha256", "commit", "model",
+             "reasoning_effort", "payload_sha256", "registry_sha256", "jail_sha256", "freeze_sha256", "codex_sha256",
+             "bwrap_sha256", "python_sha256", "max_model_calls")
+MODE_NAMES = {"first": "first-call", "continue": "continue-after-first"}
+REGISTRY_REL = "assistant/rnplens_assistant/registry.json"
+TASK_TARGET = re.compile(r"^d[0-9]+_([0-9][A-Za-z0-9]{3})_")
+
+
+def runtime_hashes(env=None):
+    """sha256 of the executables a call would use: the Codex binary the jail runs (RNPLENS_CODEX_BIN, else
+    $CODEX_HOME/packages/standalone/current/bin/codex; never PATH), bubblewrap, and this Python interpreter."""
+    env = os.environ if env is None else env
+    home = env.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
+    cx = env.get("RNPLENS_CODEX_BIN") or os.path.join(home, "packages", "standalone", "current", "bin", "codex")
+    bw = shutil.which("bwrap")
+    f = lambda p: sha_file(os.path.realpath(p)) if p and os.path.isfile(p) else "missing"
+    return {"codex_sha256": f(cx), "bwrap_sha256": f(bw), "python_sha256": f(sys.executable)}
+
+
+def task_digest(task_dir):
+    """Content identity of a development task folder: sha256 over 'relative path<TAB>sha256' lines, sorted."""
+    lines = []
+    for dp, dn, fn in os.walk(task_dir):
+        dn[:] = sorted(x for x in dn if not x.startswith(".") and x != "__pycache__")
+        for f in fn:
+            if not f.startswith("."):
+                pth = os.path.join(dp, f)
+                lines.append("%s\t%s" % (os.path.relpath(pth, task_dir).replace(os.sep, "/"), sha_file(pth)))
+    return sha_text("\n".join(sorted(lines)) + "\n")
+
+
+def _scenario_tasks(S):
+    m = {s["id"]: s["task"] for s in S["part_P"] + S["part_Z"]}
+    pf = S["part_F"]
+    S2 = json.load(open(os.path.join(ROOT, pf["source"]), encoding="utf-8"))
+    for s in S2["scenarios"]:
+        if s["id"] in pf["ids"]:
+            m["F-" + s["id"]] = s["task"]
+    return m
+
+
+def authorisation_values(mode, run_id, tasks, S, head, runtime):
+    """-> (values, detail). The exact values a call-specific authorisation must name for this mode and run (Amendment
+    8). first-call: the first-call scenario only, at most 1 model call. continue-after-first: the remaining scenarios,
+    at most LEDGER_CAP - 1 calls. payload_sha256 is the model-visible first planning payload (reconstructed with no
+    model); for several scenarios, the sha256 of their 'id sha256' lines. Follow-up payloads depend on the analysis and
+    are covered by the pre-send gate and the frozen premise record, not by this value."""
+    from rnplens_assistant import codex_llm
+    first = S["first_call_scenario"]
+    sids = [first] if mode == "first" else S["order"][S["order"].index(first) + 1:]
+    stask = _scenario_tasks(S)
+    tnames = sorted({stask[x] for x in sids})
+    targets = sorted({(TASK_TARGET.match(x) or [None, "unknown"])[1] for x in tnames})
+    pmap = {}
+    for s in S["part_P"]:
+        if s["id"] in sids:
+            system, user = expected_nl_payload(s["question"], os.path.join(tasks, s["task"]))
+            pmap[s["id"]] = sha_text(system + "\n\n---\n\n" + user)
+    tdig = {x: task_digest(os.path.join(tasks, x)) for x in tnames}
+    one = lambda d: list(d.values())[0] if len(d) == 1 else sha_text("".join("%s %s\n" % kv for kv in sorted(d.items())))
+    v = {"experiment": SUITE, "mode": MODE_NAMES[mode], "run_id": run_id or "", "scenario": ",".join(sids),
+         "task": ",".join(tnames), "target": ",".join(targets), "task_sha256": one(tdig), "commit": head or "",
+         "model": codex_llm.CONFIG.get("model"), "reasoning_effort": codex_llm.CONFIG.get("reasoning_effort"),
+         "payload_sha256": one(pmap) if pmap else "none", "registry_sha256": sha_file(os.path.join(ROOT, REGISTRY_REL)),
+         "jail_sha256": sha_file(os.path.join(ROOT, JAIL_REL)), "freeze_sha256": sha_file(os.path.join(HERE, "FREEZE.md")),
+         "max_model_calls": str(1 if mode == "first" else LEDGER_CAP - 1)}
+    v.update(runtime)
+    return v, {"scenario_payloads": pmap, "task_digests": tdig}
+
+
+def authorisation_refusals(conf, want):
+    R = []
+    for key in AUTH_KEYS:
+        if conf.get(key) and conf.get(key) != want.get(key):
+            R.append("authorisation %s %r does not match this run's %r: an authorisation for other inputs or another "
+                     "experiment does not cover this one" % (key, conf.get(key)[:24], str(want.get(key))[:24]))
+    return R
+
+
 def parse_confirmation(path, today):
     """-> (fields, refusals). Format (one 'key: value' per line after the header):
     date, statement (exact text), credit_balance (as shown in Codex Usage & Billing), weekly_usage_percent (as
@@ -206,7 +286,7 @@ def parse_confirmation(path, today):
         k, v = k.strip(), v.strip()
         if k == "acknowledge_abort":
             F["acknowledge_abort"].append(v)
-        elif k in ("date", "statement", "credit_balance", "weekly_usage_percent"):
+        elif k in ("date", "statement", "credit_balance", "weekly_usage_percent") + AUTH_KEYS:
             if k in F:
                 R.append("confirmation file: %s given twice" % k)
             F[k] = v
@@ -219,6 +299,9 @@ def parse_confirmation(path, today):
                  "risk accepted, or a hard spending block)")
     else:
         F["precondition"] = "hard spending block" if F["statement"] == STATEMENT_BLOCK else "auto-reload off; one-call risk accepted"
+    for key in AUTH_KEYS:                     # Amendment 8: the authorisation names every bound value
+        if not F.get(key):
+            R.append("authorisation %s missing: the confirmation file must name every bound value (Amendment 8)" % key)
     if parse_decimal(F.get("credit_balance")) is None:
         R.append("confirmation credit_balance %r is not a number" % F.get("credit_balance"))
     w = F.get("weekly_usage_percent")
@@ -460,6 +543,15 @@ def preflight(mode, a, env, hooks, S):
         ctx["git_head"] = head
     else:
         ctx["git_head"] = git_state()[0]
+    if conf:
+        try:
+            want, detail = authorisation_values(mode, a.run_id, a.tasks, S, ctx.get("git_head"),
+                                                (hooks.get("runtime_hashes") or runtime_hashes)())
+        except Exception as ex:                       # e.g. a missing task: refused, never guessed
+            R.append("authorisation values cannot be computed: %s: %s" % (type(ex).__name__, ex))
+        else:
+            R += authorisation_refusals(conf, want)
+            ctx["authorisation"] = {"values": want, "scenario_payloads": detail["scenario_payloads"]}
     enc = locale.getpreferredencoding(False).lower().replace("-", "")
     if enc != "utf8":
         R.append("preferred encoding is %s, not UTF-8: the bytes sent could not be certified" % enc)
@@ -617,6 +709,14 @@ class Guard:
             self._refuse(entry, "FIRST_CALL_PAUSE", "the first invocation makes exactly one call", abort=False)
         if not sc:
             self._refuse(entry, "NO_SCENARIO", "a call outside any scenario")
+        auth = self.run.rec.get("authorisation_bound") or {}
+        if auth:                                       # Amendment 8: the authorised experiment only
+            if self.calls_invocation >= int(auth["values"]["max_model_calls"]):
+                self._refuse(entry, "AUTHORISATION", "the authorisation allows %s model call(s) in this invocation"
+                             % auth["values"]["max_model_calls"])
+            want = auth["scenario_payloads"].get(sc.get("id"))
+            if kind == "plan" and want and sha_text(prompt) != want:
+                self._refuse(entry, "AUTHORISATION", "the %s planning payload is not the authorised payload" % sc.get("id"))
         if sc["calls"] >= sc["max_calls"]:
             self._refuse(entry, "SCENARIO_CALL_LIMIT", "scenario %s (%s) allows %d call(s)" % (sc["id"], sc["phase"], sc["max_calls"]))
         now = (self.hooks.get("now") or (lambda: datetime.datetime.now(datetime.timezone.utc)))()
@@ -1103,7 +1203,7 @@ def finish(c, state, reason=None):
 
 def plan_doc(S):
     return {"suite": SUITE, "order": S["order"], "budget": S["budget"], "first_call_scenario": S["first_call_scenario"],
-            "guards": {"env": "%s=%s or %s" % (LIVE_ENV, LIVE_TOKEN, LIVE_TOKEN_BLOCK), "confirmation": "--confirmation FILE (header %r; date, statement, credit_balance, weekly_usage_percent)" % CONFIRM_HEADER,
+            "guards": {"env": "%s=%s or %s" % (LIVE_ENV, LIVE_TOKEN, LIVE_TOKEN_BLOCK), "confirmation": "--confirmation FILE (header %r; date, statement, credit_balance, weekly_usage_percent, and the Amendment 8 authorisation fields %s)" % (CONFIRM_HEADER, ", ".join(AUTH_KEYS)),
                        "date_block": "%s .. %s %s, +/- %s" % (BLOCK_FROM, BLOCK_TO, TZ, BLOCK_MARGIN), "calls_root": LIVE_ROOT,
                        "weekly_usage": "<= start + %.0f points and < %.0f%%" % (WEEKLY_MAX_RISE, USAGE_CEILING),
                        "balance": "any change from the confirmation's credit_balance aborts", "model": MODEL, "ledger_cap": LEDGER_CAP,
@@ -1126,6 +1226,11 @@ def main(argv=None, hooks=None, out=print):
     S = load_scenarios()
     out(json.dumps(plan_doc(S), indent=1))
     if a.plan:
+        if a.run_id:                              # Amendment 8: the exact values an authorisation must name
+            head = git_state()[0]
+            rt = (hooks.get("runtime_hashes") or runtime_hashes)()
+            out(json.dumps({"authorisation_values": {MODE_NAMES[m]: authorisation_values(m, a.run_id, a.tasks, S, head, rt)[0]
+                                                     for m in ("first", "continue")}}, indent=1))
         return 0
     mode = "first" if a.first_call else "continue"
     refusals, pre = preflight(mode, a, os.environ, hooks, S)
@@ -1148,6 +1253,7 @@ def main(argv=None, hooks=None, out=print):
                    "git_head": pre.get("git_head"), "freeze_sha256": sha_file(os.path.join(HERE, "FREEZE.md")),
                    "confirmation": {k: conf[k] for k in ("path", "sha256", "date", "credit_balance", "weekly_usage_percent", "acknowledge_abort")},
                    "precondition": conf.get("precondition"),
+                   "authorisation_bound": pre.get("authorisation"),
                    "baseline": {"balance": str(parse_decimal(conf["credit_balance"])), "weekly_used_percent": conf["weekly_usage_percent_value"],
                                 "source": "owner confirmation"},
                    "model": MODEL, "tasks": os.path.realpath(a.tasks), "invocations": [], "calls": [], "refused_calls": [],
@@ -1161,6 +1267,8 @@ def main(argv=None, hooks=None, out=print):
             run.rec.setdefault("confirmation_history", []).append(run.rec["confirmation"])
             run.rec["confirmation"] = {k: conf[k] for k in ("path", "sha256", "date", "credit_balance", "weekly_usage_percent", "acknowledge_abort")}
             run.rec["go_ahead"] = pre.get("go_ahead")
+            run.rec.setdefault("authorisation_history", []).append(run.rec.get("authorisation_bound"))
+            run.rec["authorisation_bound"] = pre.get("authorisation")
             todo = [x for x in S["order"] if x not in run.rec["scenarios"]]
         run.rec["invocations"].append({"mode": mode, "started_utc": pre["now_utc"], "pid": os.getpid(), "confirmation_sha256": conf["sha256"],
                                        "ledger_attempts_before": pre["ledger_attempts"], "git_head": pre.get("git_head")})
```
