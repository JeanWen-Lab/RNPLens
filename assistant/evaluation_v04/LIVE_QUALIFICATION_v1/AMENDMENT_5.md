# Amendment 5 to LIVE_QUALIFICATION_v1 (2026-10-17, Canberra): re-pin assist.py (menu exit status) and followup.py (evidence hash v2)

Cause: round 3. The owner note of 17 October 2026 approves "Two remaining pinned-file fixes" for the 0.4 development
branch, "with an amendment and fresh checksums before any live call". Both fixes are in integration head `14faecd`
(`589485b` plus track/replay-r3 `3c89f97` plus track/release-docs-r3 `2757444`). This amendment is written and frozen
on branch `track/codex-harness-r3` (from `14faecd`) **before any run of this suite at this head, mocked or live**. No
Codex or other language-model call has been made; the real `codex` binary has only been run as `codex --version`.

## 1. The two changes (exact diffs below, against the Amendment 4 versions at `6b958c5`)

**`src/rnplens/assist.py`**, commit `5c04c00` (release-docs track; records/release/PINNED_SOURCE_AMENDMENT_R3_PROPOSAL.md).
- In the question menu, a BLOCKED capability now exits with **5**. This covers `capabilities.DiagnoseBlocked` raised,
  or a result whose status is BLOCKED or DIAGNOSE_BLOCKED. It is reported as `BLOCKED: …` and distinguished from a
  function that ran and refused or failed (`CapabilityFailed`, exit **4**).
- A `StateError` raised by a function is now reported as a refusal (exit 4) instead of propagating.
- Unchanged:
  - the `--nl` path, `NL_PRIVACY`, the `--followup` entry, consent handling and every other exit code;
  - the planner's and the follow-up's payloads. assist.py builds neither.

**`assistant/rnplens_assistant/followup.py`**, commits `78e7334` and `401771f` (replay track).
- `evidence_hash` gains a version argument. Definition `rnplens.followup.evidence.2` additionally replaces a raw
  SHA-256 of a project or analysis record by the hash of that record's canonical projection (`rnplens.projection`), so
  the evidence hash does not depend on where the project is.
- New follow-ups write `evidence_hash_version: rnplens.followup.evidence.2` in the plan and the record. `replay_plan`
  replays under the recorded definition, with records without the field using definition 1.
- `replay_plan` first runs `rnplens.portability.check_manifest(P, man, "read", "replay-followup")`, so a replay refuses
  when the recorded structure files are not usable.
- Unchanged:
  - summary construction, the redaction (identifiers), `prompt_system`/`prompt_user`, `privacy_check`;
  - the consent check, `policy_check` (F1–F9), the tool budget and the session rules.

Review result: neither change alters a guard, a privacy rule or the construction of any payload, beyond what is
stated above. The payload bytes confirm this (section 3).

Diff sha256 (output of `git diff 6b958c5 14faecd -- <file>`): assist.py
`a82f92b22d70e93fc691d27057773250e53d6e6dcc08a161537544decf5d99fa`, followup.py
`dfffc059233fed86a1cb3374a6892c135406afa3e52251c5b326c9a958cbf4a0`.

## 2. Pins (scenarios.json `pinned_sources`)

| source | before (Amendment 4) | after |
|---|---|---|
| src/rnplens/assist.py | `2e504d658a0dd052791bb7a0fbb1bf98f031fb6efe22989849c09988dd68955a` | `03fda9de46f1b78d9b94eb0f15207403f768192aa3b427d71d45ea1b336c4507` |
| assistant/rnplens_assistant/followup.py | `b97e4820faddbc9e021b794d1a0d773c2bdc771bfcf2a53045572a49430e4e5f` | `af54f0a3b1eedb6d918c1a4ad2348513c363311843a07c24a2515b708789cfa7` |

All other pins are unchanged and verified at `14faecd`:
- `freeze_refusals()` at `14faecd` listed exactly these two files;
- ask.py, redact.py, consent.py, codex_llm.py, policy, tools, templates, gates, render, evidence, replay, llm, guide,
  registry, the three prompts, the guide document, the jail and doctor.py are unchanged.

The previous hash of scenarios.json was `64c1fbd77b31c39e7f42365e7b809183d70db0ba3ccf320aba41b21991ae741f`.

Not pinned, as before: the modules followup.py now imports (`rnplens.projection`, `rnplens.portability`), and the
other merged round-3 changes. These are the public Evaluate geometry block (`src/rnplens/geometry_block.py`,
`cli.py`), the selftest Diagnose masking, and the portability checks and refusals (exit 6, NOT SELF-CONTAINED notices,
`rnplens relink`). They enter the payloads only through analysis outputs; section 3 shows the payload bytes are
unchanged.

## 3. Premise check at `14faecd` (no model, no Codex)

`premise_check_r2.py` was run unchanged on karyon, in the neutral clone at `14faecd`, on the real development tasks
d1–d5.
- Its record is **byte-identical** to the frozen `premise_check_r2_karyon.json`: sha256
  `358ae79ce8f5ee6777cd9506a3267ee70d6dbcf85f586b1d9bd395ff2ddc894a`.
- All 26 payload sha256 values equal the expected table in results/LIVE_QUALIFICATION_READINESS.md: 11 planner first
  calls, 11 planner replans, 3 follow-up first calls and 1 follow-up replan.
- The independent reconstruction equals the assistant's planner payload for all 11 tasks. Gate findings 0,
  `followup.privacy_check` findings 0, real names found 0.
- No expected value changes. The gate is not changed.

## 4. Expectations

No scenario, question, allowed-tool list, require entry, threshold, guard value, budget (max 24 live calls, nominal
12), scoring or decision rule changed.
- **Z1** expects exit 3 from `rnplens assist --nl` with the language-model functions off. **H4** expects exit 0 from
  `--nl`. The `--nl` path is not the menu-item path the exit-status change touches.
- **FH2** compares `replay-followup` with the record. Both use the recorded hash definition (2 for this suite's
  follow-ups).
- **P06** (four-axis geometry) and **F-L11** (`explain_unavailable_metric` for `geometry_four_axis`) expect the
  capability to be reported as not available. The public geometry block makes Evaluate's geometry status BLOCKED;
  it does not make the capability available.
- These are checked, after this freeze, by the fake-Codex end-to-end runs (macOS, and karyon's real jail in the
  neutral clone). The outcome is recorded in results/LIVE_QUALIFICATION_READINESS.md, not here. If an expectation
  fails, it is reported and not edited in this amendment.

## Unchanged

DESIGN.md, run_live.py, score_live.py, privacy.py, fake_codex.py, premise_check.py, premise_check_r2.py, both premise
records, AMENDMENT_1–4, and FOLLOWUP_SUITE_v1.

## Exact diffs

```diff
diff --git a/src/rnplens/assist.py b/src/rnplens/assist.py
index 198b22d..66e9ca5 100644
--- a/src/rnplens/assist.py
+++ b/src/rnplens/assist.py
@@ -60,6 +60,15 @@ class CapabilityFailed(RuntimeError):
     """The function ran and refused or failed; the menu reports it and exits non-zero."""
 
 
+class CapabilityBlocked(RuntimeError):
+    """The function is BLOCKED in this version (for example Diagnose); the menu reports it and exits with code 5.
+    Distinct from CapabilityFailed (exit 4): a function that ran and refused or failed."""
+
+
+EXIT_BLOCKED = capabilities.DIAGNOSE_BLOCKED_EXIT          # 5
+BLOCKED_STATES = {"BLOCKED", capabilities.DIAGNOSE_BLOCKED_STATUS}
+
+
 class InputError(ValueError):
     pass
 
@@ -333,6 +342,10 @@ def result_failed(result):
     return isinstance(result, dict) and str(result.get("status", "")).upper() in FAILED_STATES
 
 
+def result_blocked(result):
+    return isinstance(result, dict) and str(result.get("status", "")).upper() in BLOCKED_STATES
+
+
 def show_result(cap, result, ctx, out=print, as_json=False):
     outs, ev = summarise(result, ctx)
     rstat = (result or {}).get("status") if isinstance(result, dict) else None
@@ -341,7 +354,7 @@ def show_result(cap, result, ctx, out=print, as_json=False):
         out(json.dumps({"capability": cap["id"], "route_status": cap["status"], "result_status": rstat,
                         "message": msg, "outputs": outs, "evidence_ids": ev, "limits": cap.get("limits")}, indent=1))
         return outs, ev
-    if result_failed(result):
+    if result_failed(result) or result_blocked(result):
         out("\n%s: %s\n  %s" % (cap["label"], rstat, msg or "(no message)"))
         return outs, ev
     lines = ["", "%s [%s]" % (cap["label"], cap["status"])]
@@ -400,9 +413,22 @@ def run_item(item, ctx, given, ask=None, out=print, cap_id=None, allow_experimen
         if (ask("run it anyway? [y/N]: ") or "").strip().lower() not in ("y", "yes"):
             return None
     vals = collect(cap, ctx, given, ask=ask, out=out)
-    result = run_capability(cap, vals, out=out)
-    ctx["last_result"] = {"kind": "menu_item", "capability": cap["id"], "label": cap["label"], "ok": not result_failed(result)}
+    try:
+        result = run_capability(cap, vals, out=out)
+    except capabilities.DiagnoseBlocked as ex:           # a BLOCKED capability is exit 5, never a refusal (exit 4)
+        ctx["last_result"] = {"kind": "menu_item", "capability": cap["id"], "label": cap["label"], "ok": False}
+        raise CapabilityBlocked("%s: %s (%s)" % (cap["id"], capabilities.diagnose_blocked_text("assist"), ex))
+    except Exception as ex:                              # a refusal raised by the function (e.g. a clarification answer
+        from .state import StateError                    # it cannot accept) is a refusal: exit 4
+        if not isinstance(ex, StateError):
+            raise
+        ctx["last_result"] = {"kind": "menu_item", "capability": cap["id"], "label": cap["label"], "ok": False}
+        raise CapabilityFailed("%s: refused: %s" % (cap["id"], ex))
+    ctx["last_result"] = {"kind": "menu_item", "capability": cap["id"], "label": cap["label"],
+                          "ok": not (result_failed(result) or result_blocked(result))}
     show_result(cap, result, ctx, out=out, as_json=as_json)
+    if result_blocked(result):
+        raise CapabilityBlocked("%s: %s: %s" % (cap["id"], result.get("status"), (result or {}).get("message") or ""))
     if result_failed(result):
         raise CapabilityFailed("%s: %s" % (cap["id"], (result or {}).get("message") or result.get("status")))
     return result
@@ -441,6 +467,8 @@ def interactive(items, not_available, ctx, ask=input, out=print):
                 out(FOLLOWUP_HINT % (FOLLOWUP_CODEX_HINT if has_consent else ""))
         except (InputError, Unavailable) as ex:
             out("  not run: %s" % ex)
+        except CapabilityBlocked as ex:
+            out("  BLOCKED: %s" % ex)
         except Exception as ex:          # a failing function is reported, the menu stays open
             out("  the function failed: %s: %s" % (type(ex).__name__, ex))
 
@@ -630,6 +658,9 @@ def main(argv=None, ask=None, out=print):
         except InputError as ex:
             print("rnplens assist: %s" % ex, file=sys.stderr)
             return 2
+        except CapabilityBlocked as ex:
+            print("rnplens assist: %s" % ex, file=sys.stderr)
+            return EXIT_BLOCKED
         except CapabilityFailed as ex:
             print("rnplens assist: %s" % ex, file=sys.stderr)
             return 4
diff --git a/assistant/rnplens_assistant/followup.py b/assistant/rnplens_assistant/followup.py
index daed090..e023293 100644
--- a/assistant/rnplens_assistant/followup.py
+++ b/assistant/rnplens_assistant/followup.py
@@ -935,15 +935,37 @@ def check_traceable(statements, analysis, args, tool_log, tokens, suggestions=No
     return v
 
 
-def evidence_hash(statements, tool_log, project, analysis):
-    """Hash of the measured content of the follow-up (run-time fields and absolute roots excluded)."""
+#: definitions of the evidence hash; a record states the one it used (records without the field use definition 1)
+EVIDENCE_HASH_V1 = "rnplens.followup.evidence.1"
+EVIDENCE_HASH_V2 = "rnplens.followup.evidence.2"
+EVIDENCE_HASH_VERSION = EVIDENCE_HASH_V2          # written by new follow-ups
+_HEX64 = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
+
+
+def evidence_hash(statements, tool_log, project, analysis, version=None):
+    """Hash of the measured content of the follow-up (run-time fields and absolute roots excluded).
+
+    version None or EVIDENCE_HASH_V1: absolute paths reduced to their last component (definition 1, unchanged).
+    EVIDENCE_HASH_V2: in addition, a 64-hex value in a statement slot or tool-log message that is the raw SHA-256 of
+    a JSON/text record of the project or analysis is replaced by the hash of that record's canonical projection
+    (rnplens.projection; records/replay/PORTABILITY_TEST_v1.md section 3), so the hash does not depend on where the
+    project is or when its records were written."""
+    if version not in (None, EVIDENCE_HASH_V1, EVIDENCE_HASH_V2):
+        raise ValueError("unknown evidence hash definition %r" % version)
+    if version == EVIDENCE_HASH_V2:
+        from rnplens.projection import location_independent_mapper
+        mp = location_independent_mapper(project, analysis)
+        f = lambda x: _HEX64.sub(lambda m: mp(m.group(0)), x) if isinstance(x, str) else x
+        norm = lambda x: f(_norm(x, project, analysis))
+    else:
+        norm = lambda x: _norm(x, project, analysis)
     keep = []
     for st in statements:
         keep.append({"type": st["type"], "text": st["text"],
-                     "slots": {n: {k: _norm(x, project, analysis) for k, x in s.items()} for n, s in sorted(st["slots"].items())},
+                     "slots": {n: {k: norm(x) for k, x in s.items()} for n, s in sorted(st["slots"].items())},
                      "cites": st["cites"]})
     log = [{"tool": e["tool"], "call": e["call"], "status": e["status"], "outputs": e.get("outputs"),
-            "message": _norm(e.get("message"), project, analysis)} for e in tool_log]
+            "message": norm(e.get("message"))} for e in tool_log]
     return hashlib.sha256(json.dumps({"statements": keep, "tool_log": log}, sort_keys=True, default=str).encode()).hexdigest()
 
 
@@ -1179,8 +1201,9 @@ def run(project, analysis, question, mode="local", initial=None, choice=None, ye
     note = {"codex": "proposed by %s, approved by the RNPLens policy" % _by, "local": "local rule, no language model"}.get(
         (chosen or {}).get("source"), "no follow-up run")
     md = render(question, rec["initial_result"], (chosen or {}).get("id", "none"), statements, note, viol or rec["wording_audit"])
-    ehash = evidence_hash(core, rec["tool_log"], P, A)
+    ehash = evidence_hash(core, rec["tool_log"], P, A, version=EVIDENCE_HASH_VERSION)
     plan = {"schema": "rnplens.followup.plan.1", "question_sha256": qsha, "source": (chosen or {}).get("source"),
+            "evidence_hash_version": EVIDENCE_HASH_VERSION,
             "follow_up": (chosen or {}).get("id"), "args": (chosen or {}).get("args"), "rule": (chosen or {}).get("rule"),
             "rule_slots": (chosen or {}).get("rule_slots"), "tool_calls": (chosen or {}).get("verdict", {}).get("tool_calls") or [],
             "executed": bool(rec["tool_log"]), "evidence_sha256": ehash}
@@ -1188,7 +1211,7 @@ def run(project, analysis, question, mode="local", initial=None, choice=None, ye
     pv.atomic_write_json(os.path.join(fdir, "followup_answer.json"), {"statements": statements, "rendered": [fill(s) for s in statements],
                                                                      "traceability_violations": viol})
     pv.atomic_write_text(os.path.join(fdir, "followup_answer.md"), md)
-    rec.update(evidence_sha256=ehash, n_tool_calls=session["tool_calls"], outputs={
+    rec.update(evidence_sha256=ehash, evidence_hash_version=EVIDENCE_HASH_VERSION, n_tool_calls=session["tool_calls"], outputs={
         "record": "followup_record.json", "plan": "followup_plan.json", "answer": "followup_answer.md", "summary": "evidence_summary.json"},
         dir=os.path.relpath(fdir, A).replace(os.sep, "/"))
     rec["provenance"] = pv.block("followup", [os.path.join(A, "summary.json"), os.path.join(P, "manifest.json")],
@@ -1221,16 +1244,19 @@ def replay_plan(plan_path, project, analysis):
         plan = json.load(fh)
     P, A = os.path.abspath(project), os.path.abspath(analysis)
     man = json.load(open(os.path.join(P, "manifest.json"), encoding="utf-8"))
+    from rnplens import portability as PT       # a replay vouches for the evidence: the recorded files must be usable
+    PT.check_manifest(P, man, "read", "replay-followup")
     session = {"model_calls": 0, "tool_calls": 0, "rejected": [], "done": set(), "all_runs": [r["run"] for r in man["runs"]]}
     log = []
     fid, args = plan.get("follow_up"), plan.get("args") or _blank()
+    ver = plan.get("evidence_hash_version") or EVIDENCE_HASH_V1     # the definition the record was written under
     if fid is None:
-        return evidence_hash([], log, P, A), log
+        return evidence_hash([], log, P, A, version=ver), log
     statements = reason_statement(fid, args, plan.get("rule"), plan.get("rule_slots"))
     if plan.get("executed") or fid == "none":
         results = execute(plan["tool_calls"], P, A, session, log)
         statements += statements_for(fid, args, results, A)
-    return evidence_hash(statements, log, P, A), log
+    return evidence_hash(statements, log, P, A, version=ver), log
 
 
 def from_assistant_run(run_dir):
```
