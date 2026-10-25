"""Public-wrapper protection for Evaluate's four-axis geometry route (RNPLens 0.4, owner item 3A, 17 Oct 2026).

The frozen rc3 Evaluate component (``rnpbench_evaluate``) is unchanged and still computes its four-axis geometry.
Those values come from a residue correspondence with a known defect (letter matching, stop report 2026-10-14), so no
public RNPLens 0.4 entry point may show or write them as computed results. This module is the only place that
enforces it (see records/release/GEOMETRY_BLOCK_INVENTORY.md):

* ``rnplens evaluate run``: the component runs into a private temporary directory with its output captured; the
  published ``result.json``, ``result.csv`` and ``summary.txt`` and the printed text carry ``BLOCKED`` instead of any
  geometry value or alignment count; the temporary directory is deleted (no unfiltered copy is kept).
* ``rnplens evaluate selftest`` and ``rnplens selftest``: the regression checks still run on the frozen code and keep
  their verdict and exit code; the display shows ``geometry BLOCKED (checked, not shown)`` and masks numbers on
  every line that names a ``geometry.`` field.
* ``rnplens selftest`` and ``rnplens diagnose selftest`` (integrator follow-up to DOCS_AUDIT R3-C3): Diagnose's
  example regression runs the frozen Diagnose command on bundled data, which prints its interpretation statements
  (protein-side and RNA-side disagreement with band and percentile) and, outside the validated domain, an
  applicability warning. Diagnose is BLOCKED in 0.4, so the display replaces each with
  ``Diagnose interpretation BLOCKED (checked, not shown): <side>``; the checks, the verdict, the exit code and the
  ``--out`` self-test record (which holds no statement) are unchanged.
DockQ, DockQ class, fnat, iRMSD and LRMSD are passed through unchanged. They are DockQ quantities with their own
definitions, not replacements for the four-axis decomposition.
"""
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

STATUS = "BLOCKED"
RUN_RECORD_NOTE = ("written by the rnplens command after the tool finished; the result files are the frozen Evaluate "
                   "output with the four-axis geometry values withheld (geometry status BLOCKED, RNPLens 0.4); the "
                   "DockQ route is unchanged; result.json records the SHA-256 of the files before filtering")
CODE = "GEOMETRY_BLOCKED_IN_0.4"
REASON = ("Evaluate's four-axis geometry (protein-internal CA RMSD, RNA-internal C4' RMSD, RNA placement C4' RMSD and "
          "their aligned-position counts) is BLOCKED in RNPLens 0.4: its residue correspondence has a known defect "
          "(letter matching, stop report 2026-10-14). The values are not shown or written. DockQ, DockQ class, fnat, "
          "iRMSD and LRMSD are DockQ quantities with their own definitions and are not replacements for it.")
SUMMARY_LINE = "Structural geometry: BLOCKED in RNPLens 0.4 (residue-correspondence defect, 2026-10-14); no value is shown."
JSON_KEEP = ("configuration", "correspondence_note", "chains_used")       # identifiers and fixed text; schema-required
JSON_WITHHELD = ("prot_internal_ca_rmsd", "rna_internal_c4_rmsd", "rna_placement_c4_rmsd", "n_prot_aligned",
                 "n_prot_native", "n_prot_pose", "n_rna_aligned", "n_rna_native", "n_rna_pose", "exclusion",
                 "no_value_note", "status")
CSV_VALUE_COLUMNS = ("protein_internal_ca_rmsd", "rna_internal_c4_rmsd", "rna_placement_c4_rmsd", "n_protein_pairs",
                     "n_rna_pairs")
SECTION_HEAD = "Structural geometry"
_NUM = re.compile(r"(?<![\w.])-?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?(?![\w.])")
_COMPONENT = "import sys; from rnpbench import cli; sys.exit(cli.main(sys.argv[1:]))"
_TOOLKIT = "import sys; from rnpbench import toolkit; sys.exit(toolkit.main(sys.argv[1:]))"


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _frozen_hashes(name, data):
    """QA O7: hashes of one file the frozen component wrote, before filtering. content_sha256 is deterministic
    (DETERMINISM_CONTRACT_v1 content hash: sha256_json of the JSON with every volatile key such as created_utc removed;
    the byte hash of a non-JSON file); raw_file_sha256 is the byte hash, a declared volatile key of the contract,
    because the frozen result.json carries its own creation time."""
    raw, content = _sha(data), None
    if name.endswith(".json"):
        try:
            from . import canonical
            from . import provenance as pv
            content = pv.sha256_json(canonical.split_volatile(json.loads(data.decode("utf-8")))[0])
        except (ValueError, UnicodeDecodeError):
            content = None
    return {"content_sha256": content or raw, "raw_file_sha256": raw}


# ---------------------------------------------------------------- filters (pure functions; tested directly)
def filter_result_json(obj):
    """Evaluate result.json -> the same record with every geometry value, count and route text removed."""
    out = dict(obj)
    g = obj.get("geometry")
    if isinstance(g, dict):
        out["geometry"] = dict({k: g[k] for k in JSON_KEEP if k in g}, status=STATUS, blocked_code=CODE,
                               blocked_reason=REASON, fields_withheld=sorted(k for k in g if k not in JSON_KEEP))
    return out


def filter_result_csv(text):
    """Evaluate result.csv -> same header and DockQ columns; geometry values empty, geometry_status BLOCKED."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return text
    head = rows[0]
    idx = {c: i for i, c in enumerate(head)}
    for r in rows[1:]:
        for c in CSV_VALUE_COLUMNS:
            if c in idx and idx[c] < len(r):
                r[idx[c]] = ""
        if "geometry_status" in idx and idx["geometry_status"] < len(r):
            r[idx["geometry_status"]] = STATUS
        if "geometry_exclusion" in idx and idx["geometry_exclusion"] < len(r):
            r[idx["geometry_exclusion"]] = CODE
    buf = io.StringIO()
    w = csv.writer(buf)                                     # the component writes with the csv default (CRLF) dialect
    w.writerows(rows)
    return buf.getvalue()


def filter_summary_text(text):
    """Replace the 'Structural geometry ...' section (its heading up to the next blank line) by one BLOCKED line."""
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        if lines[i].startswith(SECTION_HEAD):
            out.append(SUMMARY_LINE)
            i += 1
            while i < len(lines) and lines[i].strip():
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


DIAGNOSE_MASK = "Diagnose interpretation BLOCKED (checked, not shown)"
# the frozen Diagnose command prints, per licensed statement, either its text (rnpbench_diagnose.diagnose: "<Scope> is
# consistent|variable across the candidates|engines: disagreement X A, <band> relative to the frozen development
# reference (...)") or "<statement>: not available" (rnpbench_diagnose.cli), and possibly an applicability warning
_DIAG_TEXT = re.compile(r"^(\s*)(The protein|The RNA)\b.*\bacross the (?:candidates|engines): disagreement\b")
_DIAG_ANY = re.compile(r"relative to the frozen development reference|development targets\)")
_DIAG_NA = re.compile(r"^(\s*)(protein_side|rna_side): not available\s*$")
_DIAG_WARN = re.compile(r"^(\s*)WARNING: outside the validated applicability domain")


def mask_diagnose_statements(line):
    """One display line -> the same line, or the BLOCKED mask if it is a Diagnose interpretation statement."""
    m = _DIAG_TEXT.match(line)
    if m:
        return "%s%s: %s side" % (m.group(1), DIAGNOSE_MASK, "protein" if m.group(2) == "The protein" else "RNA")
    m = _DIAG_NA.match(line)
    if m:
        return "%s%s: %s side" % (m.group(1), DIAGNOSE_MASK, "protein" if m.group(2) == "protein_side" else "RNA")
    m = _DIAG_WARN.match(line)
    if m:
        return "%s%s: applicability" % (m.group(1), DIAGNOSE_MASK)
    if _DIAG_ANY.search(line):                              # any other wording of a banded statement
        return "%s%s" % (re.match(r"\s*", line).group(0), DIAGNOSE_MASK)
    return line


def filter_selftest_text(text):
    """Self-test display: keep verdicts; never show a geometry value or a Diagnose interpretation statement."""
    out = []
    for line in text.split("\n"):
        line = re.sub(r"geometry (COMPUTED|NO_VALUE)", "geometry BLOCKED (checked, not shown)", line)
        if "geometry." in line:
            line = _NUM.sub("<withheld>", line)
        out.append(mask_diagnose_statements(line))
    return "\n".join(out)


# ---------------------------------------------------------------- entry points
def _opt_value(args, name):
    for i, a in enumerate(args):
        if a == name and i + 1 < len(args):
            return args[i + 1], i, False
        if a.startswith(name + "="):
            return a.split("=", 1)[1], i, True
    return None, None, None


def run_evaluate(rest, stdout=None, stderr=None):
    """``rnplens evaluate run ...`` with the geometry route blocked in everything shown or written. -> exit code."""
    stdout, stderr = stdout or sys.stdout, stderr or sys.stderr
    if any(a in ("-h", "--help") for a in rest):
        r = subprocess.run([sys.executable, "-c", _COMPONENT, "evaluate"] + list(rest), capture_output=True, text=True)
        stdout.write(r.stdout + "\nIn RNPLens 0.4 the four-axis geometry route is BLOCKED: " + REASON + "\n")
        stderr.write(r.stderr)
        return r.returncode
    out, i, joined = _opt_value(rest, "--out")
    if out is None:                                         # let the component report the missing option
        r = subprocess.run([sys.executable, "-c", _COMPONENT, "evaluate"] + list(rest), capture_output=True, text=True)
        stdout.write(filter_summary_text(r.stdout)); stderr.write(filter_summary_text(r.stderr))
        return r.returncode
    existing = [f for f in ("result.json", "result.csv", "summary.txt") if os.path.exists(os.path.join(out, f))]
    if existing:                                            # the component's own rule and message, checked here first
        stderr.write("rnplens evaluate: output directory already holds %s; choose a new directory (results are never "
                     "overwritten)\n" % existing)
        return 2
    workdir, _, _ = _opt_value(rest, "--workdir")
    tmp = tempfile.mkdtemp(prefix="rnplens_evaluate_private_", dir=workdir if workdir and os.path.isdir(workdir) else None)
    try:
        priv = os.path.join(tmp, "out")
        args = list(rest)
        if joined:
            args[i] = "--out=" + priv
        else:
            args[i + 1] = priv
        r = subprocess.run([sys.executable, "-c", _COMPONENT, "evaluate"] + args, capture_output=True, text=True)
        published, raw_sha = [], {}
        if os.path.isdir(priv):
            os.makedirs(out, exist_ok=True)
            for name in sorted(os.listdir(priv)):
                src = os.path.join(priv, name)
                if not os.path.isfile(src):
                    continue
                data = open(src, "rb").read()
                raw_sha[name] = _frozen_hashes(name, data)
                if name == "result.json":
                    obj = filter_result_json(json.loads(data.decode("utf-8")))
                    obj["rnplens_public_output"] = {
                        "filter": "rnplens.geometry_block (RNPLens 0.4): four-axis geometry BLOCKED; DockQ route unchanged",
                        "frozen_component_output_sha256_before_filtering": None}     # filled below
                    text = json.dumps(obj, indent=1)
                elif name == "result.csv":
                    text = filter_result_csv(data.decode("utf-8"))
                elif name == "summary.txt":
                    text = filter_summary_text(data.decode("utf-8"))
                else:
                    continue                                 # the component writes only the three files above
                dst = os.path.join(out, name)
                with open(dst, "x", encoding="utf-8", newline="") as fh:
                    fh.write(text)
                published.append(dst)
            rj = os.path.join(out, "result.json")
            if os.path.exists(rj):                           # record the unfiltered hashes (hashes only, no values)
                obj = json.load(open(rj, encoding="utf-8"))
                obj["rnplens_public_output"]["frozen_component_output_sha256_before_filtering"] = raw_sha
                with open(rj, "w", encoding="utf-8", newline="") as fh:
                    fh.write(json.dumps(obj, indent=1))
        so = filter_summary_text(r.stdout).replace(priv, out)
        se = filter_summary_text(r.stderr).replace(priv, out)
        stdout.write(so); stderr.write(se)
        return r.returncode
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def filter_selftest_record(obj):
    """Evaluate selftest_record.json -> the same record with the expected/observed values of every geometry check
    replaced by BLOCKED; check names, levels, ok and bit_exact flags, counts and verdict are kept (QA D3)."""
    out = dict(obj)
    for key in ("checks", "failures", "all_deviations"):
        if key not in obj:
            continue
        rows = []
        for c in obj.get(key) or []:
            if isinstance(c, dict) and "geometry." in str(c.get("check", "")):
                c = dict(c)
                for k in ("expected", "got", "abs_deviation"):
                    if k in c:
                        c[k] = STATUS
            rows.append(c)
        out[key] = rows
    out["rnplens_public_output"] = {"filter": "rnplens.geometry_block (RNPLens 0.4): four-axis geometry values BLOCKED "
                                              "(checked, not shown); verdict and checks unchanged"}
    return out


def _publish_selftest_out(priv, out):
    """Copy the frozen Evaluate self-test --out tree to ``out`` with every geometry value withheld (QA D3)."""
    for root, _, files in os.walk(priv):
        rel = os.path.relpath(root, priv)
        dst_dir = out if rel == "." else os.path.join(out, rel)
        os.makedirs(dst_dir, exist_ok=True)
        for name in sorted(files):
            data = open(os.path.join(root, name), "rb").read()
            if name == "result.json":
                obj = filter_result_json(json.loads(data.decode("utf-8")))
                obj["rnplens_public_output"] = {"filter": "rnplens.geometry_block (RNPLens 0.4): four-axis geometry "
                                                          "BLOCKED; DockQ route unchanged",
                                                "frozen_component_output_sha256_before_filtering": {name: _frozen_hashes(name, data)}}
                text = json.dumps(obj, indent=1)
            elif name == "result.csv":
                text = filter_result_csv(data.decode("utf-8"))
            elif name == "summary.txt":
                text = filter_summary_text(data.decode("utf-8"))
            elif name == "selftest_record.json":
                text = json.dumps(filter_selftest_record(json.loads(data.decode("utf-8"))), indent=1)
            else:
                with open(os.path.join(dst_dir, name), "wb") as fh:
                    fh.write(data)
                continue
            with open(os.path.join(dst_dir, name), "w", encoding="utf-8", newline="") as fh:
                fh.write(text)


def run_selftest(argv, toolkit=False, stdout=None, stderr=None, tool="evaluate"):
    """``rnplens evaluate selftest`` / ``rnplens diagnose selftest`` (component, ``tool``) or ``rnplens selftest``
    (toolkit), display filtered. With ``rnplens evaluate selftest --out DIR`` the frozen self-test writes into a private
    temporary directory, and its record and per-fixture results are published filtered; no unfiltered copy is kept.
    -> exit code."""
    stdout, stderr = stdout or sys.stdout, stderr or sys.stderr
    argv = list(argv)
    env = dict(os.environ, MPLBACKEND=os.environ.get("MPLBACKEND", "Agg"))
    out, i, joined = _opt_value(argv, "--out")
    if toolkit or tool != "evaluate" or out is None or any(a in ("-h", "--help") for a in argv):
        cmd = [sys.executable, "-c", _TOOLKIT] + argv if toolkit else [sys.executable, "-c", _COMPONENT, tool] + argv
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        stdout.write(filter_selftest_text(r.stdout)); stderr.write(filter_selftest_text(r.stderr))
        return r.returncode
    tmp = tempfile.mkdtemp(prefix="rnplens_selftest_private_")
    try:
        priv = os.path.join(tmp, "out")
        args = list(argv)
        if joined:
            args[i] = "--out=" + priv
        else:
            args[i + 1] = priv
        r = subprocess.run([sys.executable, "-c", _COMPONENT, tool] + args, capture_output=True, text=True, env=env)
        if os.path.isdir(priv):
            _publish_selftest_out(priv, out)
        stdout.write(filter_selftest_text(r.stdout).replace(priv, out))
        stderr.write(filter_selftest_text(r.stderr).replace(priv, out))
        return r.returncode
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
