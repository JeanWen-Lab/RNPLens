"""Opaque identifiers for every model payload (RNPLens 0.4; owner decision of 17 October 2026).

By default no model payload contains an original file name, a run-folder name taken from the filesystem, a sample
name derived from a file name, a reference file name, or any absolute or relative filesystem path. They are replaced by
identifiers assigned deterministically (sorted real names):

  natural-language planner  run_001 ... (top-level folders of the task), run_001/candidate_001 ... (structure files),
                            run_001/file_001 ... (other files inside a run folder), protein_sequence_001 /
                            rna_sequence_001 (top-level FASTA files, by alphabet), reference_001 ... (declared
                            references, reference-based tasks only)
  follow-up summary         run_001 ... (run names), candidate_001 ... (sample names, by structure ID order),
                            evidence_001 ... (evidence IDs, which are output paths), output_001 ... (analysis outputs)

The map from identifiers to real names is written only to the local records (redaction_map.json in the planner run
folder or the follow-up folder) and is never sent. Arguments the model returns are mapped back locally before the
policy and the tools see them; answers are rendered from local records, so they show the real names.

Reference rule (exact): a reference is an experimental reference only if task.json lists it in reference_files.
  * Reference-based task (at least one declared reference): the payload says that a reference is supplied and gives
    only its identifier (reference_001); never its file name, path or content.
  * Reference-free task (none declared): no reference is mentioned at all ("none"). Top-level files that are neither
    FASTA files nor declared references, which includes any undeclared or restricted reference, are omitted from the
    listing and from its file count, so neither their content nor their name nor their existence is sent.
Free text (the question, policy feedback) is passed through `text()`, which replaces exact occurrences of known real
names (word-bounded, longest first) by their identifiers. A target ID that a researcher types in a question and that is
not itself a file or folder name is sent as typed (the question is a declared category)."""
import json
import os
import re

SCHEMA = "rnplens.redaction_map.1"
STRUCTURE_EXT = (".pdb", ".cif", ".mmcif", ".ent", ".pdb.gz", ".cif.gz")
FASTA_EXT = (".fasta", ".fa", ".faa", ".fna", ".fas")
RNA_ALPHABET = set("ACGUTN")
MIN_TEXT_NAME = 3          # names shorter than this are mapped structurally but not replaced in free text


def _sorted(xs):
    return sorted(set(xs), key=lambda s: (s.lower(), s))


def _fasta_kind(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            seq = "".join(l.strip() for l in fh if l.strip() and not l.startswith(">")).upper()
    except OSError:
        return "sequence"
    if seq and set(seq) <= RNA_ALPHABET:
        return "rna_sequence"
    return "protein_sequence" if seq else "sequence"


def _name_like_stem(base):
    """The stem of a file name when it looks like a name (contains a digit or an underscore), else None: so that
    ordinary words such as 'protein' or 'reference' in a question are never replaced."""
    stem = (base or "").split(".")[0]
    return stem if stem != base and re.search(r"[0-9_]", stem) else None


class Map:
    """identifier <-> real name, plus free-text replacement."""
    def __init__(self, scope):
        self.scope, self.to_real, self.to_id, self._rx = scope, {}, {}, None

    def add(self, ident, real):
        self.to_real[ident] = real
        self.to_id.setdefault(real, ident)
        return ident

    def ident(self, real, default=None):
        return self.to_id.get(real, real if default is None else default)

    def real(self, ident):
        return self.to_real.get(ident, ident)

    def real_names(self, min_len=1):
        return sorted({r for r in self.to_id if isinstance(r, str) and len(r) >= min_len}, key=lambda s: (-len(s), s))

    def text(self, s):
        """Replace exact, word-bounded occurrences of real names (longest first) by their identifiers."""
        if not isinstance(s, str) or not s:
            return s
        names = self.real_names(MIN_TEXT_NAME)
        if not names:
            return s
        if self._rx is None or self._rx[0] != len(self.to_id):
            self._rx = (len(self.to_id), re.compile(r"(?<![A-Za-z0-9_.\-/])(" + "|".join(re.escape(n) for n in names) + r")(?![A-Za-z0-9_\-])"))
        return self._rx[1].sub(lambda x: self.to_id[x.group(1)], s)

    def text_ci(self, s):
        """QA fix #6: like text(), but case-insensitive (a researcher typing 'RUN_B' for the folder run_B)."""
        if not isinstance(s, str) or not s:
            return s
        names = self.real_names(MIN_TEXT_NAME)
        if not names:
            return s
        low = {}
        for n in names:
            low.setdefault(n.lower(), self.to_id[n])
        rx = re.compile(r"(?<![A-Za-z0-9_.\-/])(" + "|".join(re.escape(n) for n in names) + r")(?![A-Za-z0-9_\-])", re.I)
        return rx.sub(lambda x: low.get(x.group(1).lower(), x.group(1)), s)

    def doc(self, extra=None):
        d = {"schema": SCHEMA, "scope": self.scope, "never_sent": True,
             "identifiers": {k: self.to_real[k] for k in sorted(self.to_real)}}
        d.update(extra or {})
        return d

    def write(self, path, extra=None):
        from rnplens import provenance as pv
        pv.atomic_write_json(path, self.doc(extra))


# ---------------------------------------------------------------- natural-language planner (task folder)
def planner_view(task_dir, task):
    """-> (lines, n_listed, reference_ids, Map). lines are the identifiers listed to the planner."""
    m = Map("planner")
    m.undisclosed = []
    refs = list(task.get("reference_files") or [])
    top_dirs, top_files = [], []
    for e in sorted(os.listdir(task_dir)):
        if e.startswith(".") or e == "task.json":
            continue
        (top_dirs if os.path.isdir(os.path.join(task_dir, e)) else top_files).append(e)
    lines = []
    for i, d in enumerate(_sorted(top_dirs), 1):
        rid = m.add("run_%03d" % i, d)
        files = []
        for dp, dn, fn in os.walk(os.path.join(task_dir, d)):
            dn[:] = sorted(x for x in dn if not x.startswith("."))
            files += [os.path.relpath(os.path.join(dp, f), task_dir) for f in fn if not f.startswith(".")]
        nc = nf = 0
        for rel in _sorted(files):
            low = rel.lower()
            if low.endswith(STRUCTURE_EXT):
                nc += 1
                lines.append(m.add("%s/candidate_%03d" % (rid, nc), rel))
            else:
                nf += 1
                lines.append(m.add("%s/file_%03d" % (rid, nf), rel))
    kinds = {}
    for f in _sorted(top_files):
        if f in refs:
            continue
        if f.lower().endswith(FASTA_EXT):
            k = _fasta_kind(os.path.join(task_dir, f))
            kinds[k] = kinds.get(k, 0) + 1
            lines.append(m.add("%s_%03d" % (k, kinds[k]), f))
        # any other top-level file (including an undeclared or restricted reference) is omitted: not listed, not counted
        else:
            m.undisclosed.append(f)
    ref_ids = [m.add("reference_%03d" % i, r) for i, r in enumerate(_sorted(refs), 1)]
    for ident, real in list(m.to_real.items()):          # aliases for free text: basenames, and name-like stems
        base = os.path.basename(real)
        for alias in (base, _name_like_stem(base)):
            if alias and alias not in m.to_id and len(alias) >= MIN_TEXT_NAME:
                m.to_id[alias] = ident
    return lines, len(lines), ref_ids, m


def planner_user(question, task_dir, task):
    """(user message, Map): the planner's user message with identifiers only."""
    lines, n, ref_ids, m = planner_view(task_dir, task)
    question, m.question_redactions = scrub_user_text(question, task_dir, m)
    m.question_sent = question
    user = ("Question:\n%s\n\nTask inputs (%d files; opaque identifiers, the real names stay on this computer; use these "
            "identifiers as the paths in the plan):\n%s\n\nExperimental reference supplied with this task: %s\n"
            % (question, n, "\n".join(lines[:300]),
               ("yes (%s); reference-based metrics are available" % ", ".join(ref_ids)) if ref_ids else "none"))
    return user, m


# ---------------------------------------------------------------- QA fix #6: user-typed text before anything is sent
ABS_PATH = re.compile(r"(?<![\w.~])(?:~[\w.-]*)?/[^\s'\"<>()\[\]{},;/][^\s'\"<>()\[\]{},;]*|\b[A-Za-z]:\\[^\s'\"<>]+")
UNDISCLOSED = "<undisclosed file>"


class PrivacyRefused(Exception):
    """The outgoing message still contains a path or a real name after redaction: it is not sent."""


def _undisclosed_names(m):
    """Names of undisclosed top-level files and their name-like stems (with a digit or an underscore), so that an
    ordinary word such as 'reference' (the stem of reference.cif) is never redacted."""
    out = set()
    for f in getattr(m, "undisclosed", []) or []:
        out.add(f)
        st = _name_like_stem(f)
        if st:
            out.add(st)
    return sorted((x for x in out if len(x) >= MIN_TEXT_NAME), key=len, reverse=True)


def scrub_user_text(text, task_dir, m):
    """Redact user-typed text that would otherwise leave the computer: (1) absolute paths -> the identifier of the task
    item they name, else '<path>'; (2) real file, folder and run names in any letter case -> their identifiers;
    (3) names of top-level files that are not offered to the planner (undeclared or restricted references and any
    other undisclosed file), and their stems, -> '<undisclosed file>'. -> (text, [{"kind", "replacement"}])."""
    if not isinstance(text, str) or not text:
        return text, []
    acts = []
    root = os.path.realpath(task_dir) if task_dir else None

    def _path(mo):
        tok = mo.group(0)
        tail = ""
        while tok and tok[-1] in ".,:;?!":
            tail, tok = tok[-1] + tail, tok[:-1]
        rep = "<path>"
        if root:
            rp = os.path.realpath(os.path.expanduser(tok))
            if rp == root or rp.startswith(root + os.sep):
                rel = os.path.relpath(rp, root)
                rep = m.to_id.get(rel, "<task path>") if rel != "." else "<task folder>"
        acts.append({"kind": "absolute_path", "replacement": rep})
        return rep + tail
    out = ABS_PATH.sub(_path, text)
    names = _undisclosed_names(m)
    if names:
        rx = re.compile(r"(?<![A-Za-z0-9_\-])(" + "|".join(re.escape(n) for n in names) + r")(?![A-Za-z0-9_\-])", re.I)
        out, k = rx.subn(UNDISCLOSED, out)
        acts += [{"kind": "undisclosed_file_name", "replacement": UNDISCLOSED}] * k
    before = out
    out = m.text_ci(out)
    if out != before:
        acts.append({"kind": "real_name", "replacement": "identifier"})
    return out, acts


def payload_violations(text, task_dir, m):
    """The pre-send gate on the user-typed parts of an outgoing message (the question as it will be sent, and in a
    replan the plan echo and the rejection lines; the fixed message text is not user input): an absolute path, any
    real name of at least four characters in any letter case, or an undisclosed file name still present -> violations
    (the message is then not sent)."""
    v = []
    if ABS_PATH.search(text):
        v.append("an absolute path")
    low = text.lower()
    for n in m.real_names(4):
        if n in m.to_real:          # a real name that is itself an identifier string cannot be told apart
            continue
        if re.search(r"(?<![a-z0-9_])" + re.escape(n.lower()) + r"(?![a-z0-9_])", low):
            v.append("a real file, folder or run name"); break
    for n in _undisclosed_names(m):
        if re.search(r"(?<![a-z0-9_\-])" + re.escape(n.lower()) + r"(?![a-z0-9_\-])", low):
            v.append("an undisclosed file name"); break
    return v


PATH_ARGS = ("folders", "protein_fasta", "rna_fasta", "reference")


def planner_args_to_real(args, m):
    """-> (real args, unknown identifiers). Path arguments must be identifiers from the listing; `runs` (run names)
    map run_NNN to the real folder's basename."""
    a, bad = dict(args), []
    for k in PATH_ARGS:
        v = a.get(k)
        if v is None:
            continue
        vals = v if isinstance(v, list) else [v]
        out = []
        for x in vals:
            if x in m.to_real:
                out.append(m.to_real[x])
            else:
                bad.append(x)
                out.append(x)
        a[k] = out if isinstance(v, list) else out[0]
    if isinstance(a.get("runs"), list):
        a["runs"] = [os.path.basename(m.to_real[x]) if x in m.to_real else x for x in a["runs"]]
    return a, bad


# ---------------------------------------------------------------- follow-up evidence summary
def followup_map(summary, manifest):
    m = Map("followup")
    runs = [r.get("run") for r in manifest.get("runs") or []] + [s.get("run") for s in manifest.get("structures") or []]
    for i, r in enumerate(_sorted([r for r in runs if r]), 1):
        m.add("run_%03d" % i, r)
    m.candidates = {}
    for i, s in enumerate(sorted(manifest.get("structures") or [], key=lambda s: s.get("id") or ""), 1):
        cid = "candidate_%03d" % i
        m.candidates[s.get("id")] = cid
        m.to_real[cid] = s.get("sample")
        for real in (s.get("sample"), os.path.basename(s.get("used_path") or "") or None,
                     os.path.basename(s.get("path") or "") or None):
            if real:
                m.to_id.setdefault(real, cid)
                st = _name_like_stem(real)
                if st:
                    m.to_id.setdefault(st, cid)
    eids, outs = set(), set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "evidence_id" and isinstance(v, str):
                    eids.add(v)
                elif k == "output" and isinstance(v, str):
                    outs.add(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(summary)
    for i, e in enumerate(_sorted(eids), 1):
        m.add("evidence_%03d" % i, e)
    for i, o in enumerate(_sorted(outs), 1):
        m.add("output_%03d" % i, o)
    return m


RUN_LIST_KEYS = ("runs", "runs_compared", "runs_selected", "between")


def redact_summary(summary, m):
    """A copy of the summary with identifiers in place of run names, sample names, evidence IDs and output paths."""
    def tr(o, key=None):
        if isinstance(o, dict):
            out = {}
            for k, v in o.items():
                if k == "evidence_id" and isinstance(v, str):
                    out[k] = m.ident(v)
                elif k == "output" and isinstance(v, str):
                    out[k] = m.ident(v)
                elif k == "run" and isinstance(v, str):
                    out[k] = m.ident(v)
                elif k == "sample":
                    out[k] = m.candidates.get(o.get("id"), m.ident(v) if isinstance(v, str) else v)
                elif k in RUN_LIST_KEYS and isinstance(v, list):
                    out[k] = [m.ident(x) if isinstance(x, str) else tr(x) for x in v]
                else:
                    out[k] = tr(v, k)
            return out
        if isinstance(o, list):
            return [tr(v, key) for v in o]
        if isinstance(o, str):
            return m.text(o)
        return o
    return tr(summary)


def followup_args_to_real(args, m):
    a = dict(args or {})
    if isinstance(a.get("runs"), list):
        a["runs"] = [m.real(x) if isinstance(x, str) else x for x in a["runs"]]
    if isinstance(a.get("evidence_id"), str):
        a["evidence_id"] = m.real(a["evidence_id"])
    return a


def followup_args_to_ids(args, m):
    """The model's own arguments as echoed back in a replan: any real name it may contain becomes its identifier."""
    a = dict(args or {})
    for k, v in list(a.items()):
        if k == "runs" and isinstance(v, list):
            a[k] = [m.ident(x) if isinstance(x, str) else x for x in v]
        elif k == "evidence_id" and isinstance(v, str):
            a[k] = m.ident(v)
        elif isinstance(v, str):
            a[k] = m.text(v)
    return a


def plan_echo(plan, m):
    """The planner's previous plan as echoed back in a replan, with any real name replaced by its identifier."""
    return m.text(json.dumps(plan))


def leaked_names(text, m, min_len=4):
    """Real names (at least min_len characters) that occur in text: a privacy violation of the redacted payload."""
    hits = []
    for n in m.real_names(min_len):
        if re.search(r"(?<![A-Za-z0-9_])" + re.escape(n) + r"(?![A-Za-z0-9_])", text):
            hits.append(n)
    return hits
