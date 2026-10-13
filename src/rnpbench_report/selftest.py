"""Public self-test of RNPBench Report (added in toolkit 0.2.0.dev1; no analysis code is changed).

Specification: selftest_data/profiles/report_public_selftest_spec_v1.json (RNPBENCH_REPORT_PUBLIC_SELFTEST_SPEC_V1,
frozen before this code first ran). Uses only bundled, distributable data; needs no internal file.

  1. installation      every module imports; analysis implementation version; dependency versions recorded
  2. input validation  the bundled example contract is accepted; eleven minimal invalid edits of it are refused
  3. example regression Report's own `run` on the bundled 7K9D example (two Boltz-2 executions), compared with the
                       outputs of the original RNPBench Predict 1.0.0 under the frozen toolkit example-regression
                       profile; HTML compared as text with embedded images and the environment line normalised
  4. output protection re-running into the example's output directory is refused and changes nothing

The 888-check acceptance suite and the 9,108-result frozen-cohort reproduction are internal qualification gates
and are run only when the internal overlay is supplied (``--acceptance-store DIR --overlay DIR``).
"""
import copy
import hashlib
import importlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "selftest_data")
EXAMPLE = os.path.join(DATA, "report_7K9D")
EXPECTED = os.path.join(DATA, "expected")
PROFILE_PATH = os.path.join(DATA, "profiles", "toolkit_example_regression_profile_v1.json")
SPEC_PATH = os.path.join(DATA, "profiles", "report_public_selftest_spec_v1.json")
PINNED = {PROFILE_PATH: "f5ddd3d6e66e84bfeba7e071408aa8dcc5586f5e3e50fdef26438e70dce1b2df",
          SPEC_PATH: "af0aa8b46bea3e3b"}
PORTABLE_FLOAT_TOL = 1e-5          # as frozen in the profile
INVALID_CASES = ("not_an_object", "missing_outputs", "wrong_schema_version", "non_positive_length", "unknown_engine",
                 "duplicate_engine_execution", "relative_structure_path", "missing_structure_file", "wrong_extension",
                 "digest_mismatch", "other_without_native_confidence")


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def check_pins():
    for p, want in PINNED.items():
        if not _sha(p).startswith(want):
            raise RuntimeError("self-test specification file differs from the version frozen before testing: %s" % p)
    return json.load(open(SPEC_PATH))


# ------------------------------------------------------------------ comparison (profile-defined)
def normalise(obj, examples_dir, drop=()):
    s = json.dumps(obj)
    for d in {examples_dir, os.path.realpath(examples_dir)}:
        s = s.replace(d.rstrip("/"), "<EXAMPLES>")
    o = json.loads(s)
    for k in drop:
        o.pop(k, None)
    return o


def compare(exp, got, profile, where="$"):
    """-> list of (path, expected, got, abs_dev or None, ok)."""
    out = []
    if isinstance(exp, dict) and isinstance(got, dict):
        for k in sorted(set(exp) | set(got)):
            if k not in exp or k not in got:
                out.append(("%s.%s" % (where, k), exp.get(k, "<absent>"), got.get(k, "<absent>"), None, False))
            else:
                out += compare(exp[k], got[k], profile, "%s.%s" % (where, k))
        return out
    if isinstance(exp, list) and isinstance(got, list):
        if len(exp) != len(got):
            return [(where + ".length", len(exp), len(got), None, False)]
        for i, (a, b) in enumerate(zip(exp, got)):
            out += compare(a, b, profile, "%s[%d]" % (where, i))
        return out
    if isinstance(exp, float) and isinstance(got, float) and not isinstance(exp, bool):
        dev = abs(exp - got)
        ok = exp == got if profile == "reference" else dev <= PORTABLE_FLOAT_TOL
        return [(where, exp, got, dev, ok)]
    return [(where, exp, got, None, exp == got and type(exp) is type(got))]


def summarise(name, comps):
    bad = [c for c in comps if not c[4]]
    devs = [c[3] for c in comps if c[3]]
    return {"check": name, "n_values": len(comps), "n_failed": len(bad), "n_floats_not_bit_identical": len(devs),
            "max_abs_deviation": max(devs) if devs else 0.0, "failures": [list(map(str, c[:3])) for c in bad[:10]], "ok": not bad}


_IMG = re.compile(r"data:image/png;base64,[A-Za-z0-9+/=]+")
_ENV = re.compile(r"Environment: .*?\. Structure digests", re.S)


def html_normalise(text):
    n_img = len(_IMG.findall(text))
    return _ENV.sub("Environment: <ENVIRONMENT>. Structure digests", _IMG.sub("<EMBEDDED_PNG>", text)), n_img


# ------------------------------------------------------------------ helpers
def write_example_contract(examples_dir, out_path):
    """Write the bundled example's contract with absolute structure paths and their digests."""
    from . import contract as C
    t = json.load(open(os.path.join(examples_dir, "contract_template.json")))
    for o in t["outputs"]:
        o["structure_path"] = o["structure_path"].replace("<EXAMPLES>", os.path.abspath(os.path.dirname(examples_dir)))   # template paths: <EXAMPLES>/report_7K9D/...
        o["sha256"] = C.sha256(o["structure_path"])
    json.dump(t, open(out_path, "w"), indent=1)
    return out_path


def _invalid(case, valid, tmp):
    c = copy.deepcopy(valid)
    if case == "not_an_object":
        return [c]
    if case == "missing_outputs":
        c.pop("outputs"); return c
    if case == "wrong_schema_version":
        c["schema_version"] = "rnpbench-predict-contract-0"; return c
    if case == "non_positive_length":
        c["construct"]["protein_length"] = 0; return c
    if case == "unknown_engine":
        c["outputs"][0]["engine"] = "ALPHAFOLD"; return c
    if case == "duplicate_engine_execution":
        c["outputs"][1]["engine"], c["outputs"][1]["execution"] = c["outputs"][0]["engine"], c["outputs"][0]["execution"]; return c
    if case == "relative_structure_path":
        c["outputs"][0]["structure_path"] = os.path.relpath(c["outputs"][0]["structure_path"], tmp); return c
    if case == "missing_structure_file":
        c["outputs"][0]["structure_path"] = os.path.join(tmp, "absent", "7K9D_model_0.pdb"); return c
    if case == "wrong_extension":
        p = os.path.join(tmp, "7K9D_model_0.txt"); shutil.copy(c["outputs"][0]["structure_path"], p)
        c["outputs"][0]["structure_path"] = p; return c
    if case == "digest_mismatch":
        c["outputs"][0]["sha256"] = "0" * 64; return c
    if case == "other_without_native_confidence":
        c["outputs"][0]["engine"] = "OTHER"
        for k in ("native_confidence", "native_confidence_kind"):
            c["outputs"][0].pop(k, None)
        return c
    raise KeyError(case)


def _snapshot(d):
    return {os.path.relpath(os.path.join(dp, f), d): (_sha(os.path.join(dp, f)), os.stat(os.path.join(dp, f)).st_mtime_ns)
            for dp, _, fs in os.walk(d) for f in fs}


def _quiet(fn, *a):
    import contextlib, io
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        rc = fn(*a)
    return rc, o.getvalue(), e.getvalue()


# ------------------------------------------------------------------ checks
def check_installation():
    mods = ["agreement", "contract", "geometry", "native", "cli"]
    have_mpl = importlib.util.find_spec("matplotlib") is not None
    if have_mpl:
        mods.append("report")
    bad = []
    for m in mods:
        try:
            importlib.import_module("rnpbench_report." + m)
        except Exception as ex:          # recorded, never hidden
            bad.append("%s: %s" % (m, ex))
    from . import agreement
    vers = {}
    from importlib import metadata
    for d in ("rnpbench-report", "numpy", "biopython", "matplotlib"):
        try:
            vers[d] = metadata.version(d)
        except metadata.PackageNotFoundError:
            vers[d] = None
    ok = not bad and agreement.VERSION == "rnpbench-predict-1.0.0"
    return {"check": "report.installation", "modules": mods, "import_failures": bad, "analysis_implementation": agreement.VERSION,
            "versions": vers, "python": sys.version.split()[0], "html_available": have_mpl, "ok": ok}


def check_validation(tmp):
    from . import cli, contract as C
    spec = json.load(open(SPEC_PATH))["checks"]["input_validation"]
    want = list(spec.values())[1]
    ex = os.path.join(tmp, "validation", "report_7K9D"); shutil.copytree(EXAMPLE, ex)
    cp = write_example_contract(ex, os.path.join(tmp, "valid_contract.json"))
    valid = json.load(open(cp))
    res = {"accepted": None, "refused": {}}
    try:
        C.load(cp); rc, out, _ = _quiet(cli.main, ["validate", cp])
        res["accepted"] = {"ok": rc == 0 and '"CONTRACT_VALID"' in out, "exit": rc}
    except C.ContractError as e:
        res["accepted"] = {"ok": False, "error": str(e)}
    for case in INVALID_CASES:
        p = os.path.join(tmp, "invalid_%s.json" % case)
        json.dump(_invalid(case, valid, tmp), open(p, "w"), indent=1)
        try:
            C.load(p); msg = None
        except C.ContractError as e:
            msg = str(e)
        rc, _, err = _quiet(cli.main, ["validate", p])
        res["refused"][case] = {"message": msg, "expected_text": want[case], "exit": rc,
                                "ok": msg is not None and want[case] in msg and rc == 2}
    ok = res["accepted"]["ok"] and all(v["ok"] for v in res["refused"].values())
    return {"check": "report.input_validation", "n_cases": 1 + len(res["refused"]),
            "n_failed": (0 if res["accepted"]["ok"] else 1) + sum(not v["ok"] for v in res["refused"].values()), "detail": res, "ok": ok}


def check_example(tmp, profile, html_available):
    from . import cli
    ex = os.path.join(tmp, "examples", "report_7K9D"); shutil.copytree(EXAMPLE, ex)
    cp = write_example_contract(ex, os.path.join(tmp, "report_contract.json"))
    out = os.path.join(tmp, "report_out")
    argv = ["run", cp, "--outdir", out] + ([] if html_available else ["--no-report"])
    rc, _, err = _quiet(cli.main, argv)
    checks = [{"check": "report.example_7K9D.run_exit", "exit": rc, "ok": rc == 0, "stderr_tail": err[-300:]}]
    if rc != 0:
        return checks, out
    examples_root = os.path.dirname(ex)
    comps = []
    for fn, drop in (("result.json", ("wall_s", "environment")), ("contacts_by_output.json", ())):
        got = normalise(json.load(open(os.path.join(out, fn))), examples_root, drop=drop)
        comps += compare(json.load(open(os.path.join(EXPECTED, "report_7K9D_" + fn))), got, profile, "$" + fn)
    checks.append(summarise("report.example_7K9D.result_and_contacts", comps))
    if html_available:
        hs = [f for f in os.listdir(out) if f.endswith(".html")]
        e_txt, e_n = html_normalise(open(os.path.join(EXPECTED, "report_7K9D_example.html")).read())
        if len(hs) != 1:
            checks.append({"check": "report.example_7K9D.html", "ok": False, "html_files": hs})
        else:
            g_txt, g_n = html_normalise(open(os.path.join(out, hs[0])).read())
            diff = [l for l in __import__("difflib").unified_diff(e_txt.splitlines(), g_txt.splitlines(), lineterm="", n=0)
                    if not l.startswith(("---", "+++", "@@"))]
            checks.append({"check": "report.example_7K9D.html", "file": hs[0], "embedded_images": [e_n, g_n],
                           "n_text_lines_differing": len(diff), "first_differences": diff[:6], "ok": g_n == e_n and not diff})
    else:
        checks.append({"check": "report.example_7K9D.html", "ok": True, "status": "NOT_RUN (matplotlib not installed)"})
    return checks, out


def check_output_protection(out, contract_path):
    from . import cli
    before = _snapshot(out)
    rc, _, err = _quiet(cli.main, ["run", contract_path, "--outdir", out])
    after = _snapshot(out)
    return {"check": "report.output_protection", "exit": rc, "refusal_message": err.strip()[:200],
            "files_unchanged": before == after, "n_files": len(before), "ok": rc == 2 and before == after and "REFUSED" in err}


def internal_acceptance(store, overlay, outdir):
    """Original acceptance suite, unchanged (internal qualification only; not distributed)."""
    import rnpbench_report
    ov = os.path.join(os.path.abspath(overlay), "rnpbench_report")
    if ov not in rnpbench_report.__path__:
        rnpbench_report.__path__.append(ov)
    os.environ["RNPBENCH_PREDICT_FROZEN"] = os.path.abspath(store)
    from rnpbench_report import acceptance
    rc = acceptance.main(outdir)
    rec = json.load(open(os.path.join(outdir, "acceptance.json"))) if outdir and os.path.exists(os.path.join(outdir, "acceptance.json")) else {}
    n = sum(g["n_checks"] for g in rec.get("groups", {}).values()); f = sum(g["n_failed"] for g in rec.get("groups", {}).values())
    return {"check": "report.internal_acceptance_suite", "verdict": rec.get("VERDICT"), "n_checks": n, "n_failed": f, "exit": rc,
            "groups": {k: (v["n_checks"], v["n_failed"]) for k, v in rec.get("groups", {}).items()}, "ok": rc == 0 and rec.get("VERDICT") == "ACCEPTANCE_PASS"}


# ------------------------------------------------------------------ driver
def run(profile="portable", out=None, acceptance_store=None, overlay=None, verbose=True):
    """-> (exit code, record). 0 PASS, 4 FAIL, 2 refused invocation."""
    if profile not in ("reference", "portable"):
        raise ValueError("profile must be 'reference' or 'portable'")
    if out and os.path.exists(out):
        print("REFUSED: %s exists (self-test records are never overwritten)" % out, file=sys.stderr)
        return 2, None
    if bool(acceptance_store) != bool(overlay):
        print("REFUSED: --acceptance-store and --overlay are needed together (internal acceptance suite)", file=sys.stderr)
        return 2, None
    spec = check_pins()
    if out:
        os.makedirs(out)
    tmp = tempfile.mkdtemp(prefix="rnpbench_report_selftest_")
    try:
        inst = check_installation()
        checks = [inst, check_validation(tmp)]
        ex_checks, outdir = check_example(tmp, profile, inst["html_available"])
        checks += ex_checks
        if ex_checks[0]["ok"]:
            checks.append(check_output_protection(outdir, os.path.join(tmp, "report_contract.json")))
        if acceptance_store:
            checks.append(internal_acceptance(acceptance_store, overlay, os.path.join(out or tmp, "acceptance")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    rec = {"tool": "rnpbench-report", "selftest": spec["spec_id"], "profile": profile, "sets": "public" + ("+internal_acceptance" if acceptance_store else ""),
           "checks": checks, "verdict": "PASS" if all(c["ok"] for c in checks) else "FAIL"}
    if verbose:
        for c in checks:
            print("  %-40s %s  %s" % (c["check"], "ok  " if c["ok"] else "FAIL", ", ".join("%s=%s" % (k, c[k]) for k in (
                "n_cases", "n_values", "n_failed", "n_floats_not_bit_identical", "max_abs_deviation", "embedded_images",
                "n_text_lines_differing", "files_unchanged", "status", "verdict", "n_checks", "analysis_implementation") if k in c)))
        print("%s: rnpbench-report selftest (profile %s, %s)" % (rec["verdict"], profile, rec["sets"]))
    if out:
        json.dump(rec, open(os.path.join(out, "selftest_record.json"), "w"), indent=1)
    return (0 if rec["verdict"] == "PASS" else 4), rec
