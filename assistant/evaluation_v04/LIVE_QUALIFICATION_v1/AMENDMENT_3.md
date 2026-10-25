# Amendment 3 to LIVE_QUALIFICATION_v1 (2026-10-17, Canberra): unique CodexClient call folders

## Measurement
Integration run at `ec3d467` on karyon (mocked; fake Codex only): `test_first_call_pause_refuses_a_second_call_and_
ledger_cap_stops` stopped with HARD_CRITERION instead of BUDGET. The Codex harness track traced it (readiness report
addendum, commit `b072038`): `codex_llm.CodexClient` names its call folder `<tag>_<YYYYmmddTHHMMSS>_<pid>` (one-second
resolution), so a second client with the same tag created in the same second in one process raised FileExistsError
before any subprocess. No call can be spent by it, but a live scenario could be scored as a hard failure.

## Change (pinned source `assistant/rnplens_assistant/codex_llm.py`)
If the folder exists, a numeric suffix `_2`, `_3`, ... is appended until `os.makedirs` succeeds. Nothing else in
`codex_llm.py` changed: no guard, credit/usage reading, model, jail, schema or subprocess argument.

```diff
diff --git a/assistant/rnplens_assistant/codex_llm.py b/assistant/rnplens_assistant/codex_llm.py
index 3d35902..f5cce40 100644
--- a/assistant/rnplens_assistant/codex_llm.py
+++ b/assistant/rnplens_assistant/codex_llm.py
@@ -82,8 +82,16 @@ def read_session(call_dir):
 class CodexClient:
     def __init__(self, run_tag, config=None, mcp=None):
         self.config = dict(CONFIG, **(config or {}))
-        self.root = os.path.join(CALLS_ROOT, "%s_%s_%d" % (run_tag, time.strftime("%Y%m%dT%H%M%S"), os.getpid()))
-        os.makedirs(self.root)
+        base = os.path.join(CALLS_ROOT, "%s_%s_%d" % (run_tag, time.strftime("%Y%m%dT%H%M%S"), os.getpid()))
+        root, n = base, 1
+        while True:     # unique call folder: two clients with one tag in one second must not collide (0.4 fix)
+            try:
+                os.makedirs(root)
+                break
+            except FileExistsError:
+                n += 1
+                root = "%s_%d" % (base, n)
+        self.root = root
         self.calls, self.last_limits, self.credits0 = [], None, None
         self.mcp = mcp          # optional {"relay": path, "socket": path} for the general-agent arm
 
```

Pin: `e14bd7d008323f6c376c2330112d8c474351e78213a71588e3b80e04adbd8119` -> `15c9167f6e928f8b4b295710fca6142b9ed0735d223daa983308a0c988063e8f`. The strict-xfail test that documented the collision is now an ordinary test asserting two
distinct folders.

## Unchanged
DESIGN.md, run_live.py, score_live.py, privacy.py, fake_codex.py, premise_check.py and its record, every scenario,
expectation, guard threshold, the budget (max 24 live calls), the decision rule and every other pin. Written before any
live run; no live call has been made.
