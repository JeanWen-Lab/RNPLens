# Amendment 2 to LIVE_QUALIFICATION_v1 (2026-10-17, Canberra): re-pin two help-text edits at integration

## Reason
Integration commit `4628da8` on dev/0.4-interactive (after the four qualification tracks were merged) edited two
pinned sources to state 0.4 status in user-facing text (release-docs audit items C1 and C5). `run_live.py` then refused
with "pinned source changed since the freeze" for both files, as designed. No live call, mocked or real, has been
made against the changed files. The live qualification is meant to test the code proposed for release, so the pins are
moved to the integration versions instead of reverting the text.

## Exact change in the pinned sources (`git diff cf81acd 4628da8`)
Message strings only: the `rnplens assist` description gains "(EXPERIMENTAL; not live-qualified)", and the doctor
platform message distinguishes Linux x86_64 (tested interactive environment) from Darwin arm64 (toolkit runs, not
fully qualified). No status code, branch condition affecting a READY/ACTION verdict, guard, prompt, tool, policy or
payload construction changed. The planner prompt payload does not include either string.

```diff
diff --git a/src/rnplens/assist.py b/src/rnplens/assist.py
index e841422..3de6942 100644
--- a/src/rnplens/assist.py
+++ b/src/rnplens/assist.py
@@ -565,7 +565,8 @@ def natural_language(question, ctx, task=None, nl_out=None, out=print, ask=None,
 def main(argv=None, ask=None, out=print):
     ap = argparse.ArgumentParser(prog="rnplens assist", description="Question menu over an RNPLens project. Every item "
                                  "runs a deterministic RNPLens function; no language model is used and nothing leaves "
-                                 "this computer. --nl optionally hands a question to the Codex-backed assistant.")
+                                 "this computer. --nl optionally hands a question to the Codex-backed assistant "
+                                 "(EXPERIMENTAL; not live-qualified).")
     ap.add_argument("--project", required=True, help="project folder written by 'rnplens import'")
     ap.add_argument("--analysis", help="analysis folder written by 'rnplens analyse --out'")
     ap.add_argument("--list", action="store_true", help="print the menu (with unavailable items and reasons) and exit")
diff --git a/src/rnplens/doctor.py b/src/rnplens/doctor.py
index 4f28dc4..b190e94 100644
--- a/src/rnplens/doctor.py
+++ b/src/rnplens/doctor.py
@@ -154,7 +154,12 @@ def platform_status(env):
     sysname, mach = env.system(), env.machine()
     where = "%s %s" % (sysname, mach)
     if (sysname, mach) in QUALIFIED_TOOLKIT:
-        tk = _c("platform_toolkit", "Platform (toolkit)", READY, "%s is a qualified platform" % where)
+        if sysname == "Darwin":
+            msg = ("%s: toolkit runs; not fully qualified for 0.4 (one known numerical parity difference; "
+                   "Linux x86_64 is the tested interactive environment)" % where)
+        else:
+            msg = "%s is a qualified platform (the tested interactive environment for 0.4)" % where
+        tk = _c("platform_toolkit", "Platform (toolkit)", READY, msg)
     elif sysname in ("Linux", "Darwin"):
         tk = _c("platform_toolkit", "Platform (toolkit)", ACTION, "%s is not one of the qualified platforms (Linux x86_64, macOS arm64)" % where,
                 "run 'rnplens selftest' and keep its output with your results before relying on numbers")
```

## Replacement pins (scenarios.json `pinned_sources`)
| file | before | after |
|---|---|---|
| `src/rnplens/assist.py` | `b4ceabb9ac43ac3e34da4afcf7d425a0ad65fb5937d29ae4ab992ebc23e4c306` | `5849c3dd5bcde304c31e5aa3ae6953865a55ba30200bc90ef56811243d4c5e8f` |
| `src/rnplens/doctor.py` | `c6151cd598fa1477638a8609684b4524d4ea4658d8b7c26b12bff5e4f62ff274` | `9fd702196b20239f90daba58b95dd1eb2e36ae46b65c549dfedb5156b140b85a` |

## Unchanged
DESIGN.md, run_live.py, score_live.py, privacy.py, fake_codex.py, premise_check.py and its karyon record, every
scenario, expectation, guard threshold, budget (max 24 live calls), the decision rule and every other pinned source.
The pre-freeze premise check was not re-run for this amendment (it builds planner payloads, which neither edited string
enters); the integrator re-runs the suite's mocked tests after this amendment.
