"""Build the 36 sealed task instances and their answer keys (protocol v2 + Amendment 1). Run once, on karyon.

* Inputs: Boltz-2 stress-cohort predictions (exec_A, exec_B; 5 samples each), the stress-pair sequence and reference
  tables, and the frozen stress-pair comparison computed at gate 1 by the deterministic reference workflow.
* Keys come from an independent reference workflow: the `rnplens` command line called directly (never the assistant
  code). The counting rules are re-implemented here.
* Tasks go to OUT/tasks/<id>/ (inputs and task.json only). Keys go to OUT/keys/ and reference runs to OUT/reference/,
  both outside every task directory. Every file is hashed into OUT/SEALED_MANIFEST.json.
* Nothing is overwritten. The script prints assignments and hashes, never expected values."""
import csv
import glob
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
from multiprocessing import Pool

B = "/home/jwen/projects/RNPBench"
W = B + "/RNPLens_dev_0.3/assistant_2026-10-16"
PILOT = "/home/jwen/projects/PCfold3D-RNP/outputs/rnpbench/pilot/boltz"
SP = B + "/RNPLens_dev_0.3/work/sp_in"
FROZEN_CMP = W + "/scratch/gate1_real/sp_out/comparison.tsv"
UT6 = B + "/scratch_agent/tmp_relocated_2026-10-14/ut6"
PY = B + "/RNPLens_dev_0.3/venv/bin/python"
ENV = dict(os.environ, PYTHONPATH=W + "/RNPLens/src", MPLBACKEND="Agg", OMP_NUM_THREADS="1")
DEV = {"1VTM", "24BR", "2JEA", "2Q66", "2QQP", "2XGJ", "7K9D", "6DCB"}   # Amendment 2: every development target, incl. 7K9D and 6DCB
SEED, WIN = 20261017, 6
HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = json.load(open(os.path.join(HERE, "task_templates.json")))["templates"]

REFUSAL = r"(cannot|can't|can ?not|not possible|unable|not (be )?(measured|determined|identified|offered|available|provided)|does not|no experimental reference|without an? (experimental )?reference)"
SPEC = {   # accepted actions, required evidence, required mentions (Amendment 1, A1.3)
    "A1": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], req=["^runs\\[run_A\\]\\.designated$", "^runs\\[run_B\\]\\.designated$"]),
    "A2": dict(acc=["CLARIFY"], must=[r"(ambigu|uncertain|confirm|which chain|chain type|exclude|question)"], code="C-SILENT"),
    "A3": dict(acc=["CLARIFY"], must=[r"(offset|renumber|numbering|derived cop)"], code="C-SILENT"),
    "A4": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], req=["^protein_positions\\.band\\.BOLTZ2\\.total$"], must=[r"(renumber|derived|offset|numbering)"], code="C-SILENT"),
    "A5": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], req=["^counts\\.included$", "^contacts\\.band\\.BOLTZ2\\.total$"], must=[r"(duplicat|identical|same file|byte)"], code="C-CONS"),
    "A6": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], must=[r"(exclu|substitut|incompatib|mismatch|differ|not match)"], code="C-POOL"),
    "A7": dict(acc=["CLARIFY"], must=[r"(engine|layout|recogni|confidence file)"], code="C-SILENT"),
    "A8": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], req=["^contacts\\.band\\.BOLTZ2\\.total$"]),
    "B1": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], req=["^run_repeat_agreement\\.BOLTZ2\\.surface_agreement$", "^run_repeat_agreement\\.BOLTZ2\\.register_agreement$"],
               must=[r"surface", r"(register|residue.{1,3}nucleotide|contact pair)"], code="C-LEVEL"),
    "B2": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], req=["^repeat_agreement\\.BOLTZ2\\.rna_pose_difference_A$", "^repeat_agreement\\.BOLTZ2\\.register_agreement$"],
               must=[r"(pose|placement|placed|position of the RNA|RNA position)"], code="C-LEVEL"),
    "B3": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], req=["^contacts\\.band\\.BOLTZ2\\.total$"], must=[r"(not computed|cannot be computed|not available|defined (only )?for (exactly )?two|only (for|between) two|pairwise)"], code="C-INVENT"),
    "B4": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], req=["^contacts\\.band\\.BOLTZ2\\.total$"], must=[r"(not computed|cannot be computed|not available|defined (only )?for (exactly )?two|only (for|between) two|pairwise)"], code="C-INVENT"),
    "B5": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"]),
    "B6": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"]),
    "B7": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], req=["^no_interface_contact$"], must=[r"(no (protein.RNA )?contacts?|no interface|not in contact|does not contact|without (any )?contact|lacks? (an )?interface)"], code="C-MISS"),
    "B8": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], req=["^contacts\\.band\\.BOLTZ2\\.total$"], must=[r"(single|one structure|only one|not a consensus|no consensus|cannot (establish|assess|determine) (a )?consensus)"], code="C-CONS"),
    "C1": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], req=["^dockq\\.class$", "^fnat\\.class$", "^irmsd\\.class$", "^lrmsd\\.class$"]),
    "C2": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], req=["^dockq\\.class$"], must=[r"(correspondence|mapping|not (directly )?comparable|not like.for.like)"], code="C-CORR"),
    "C3": dict(acc=["CLARIFY", "ANSWER_WITH_LIMITATION", "REFUSE_WITH_ALTERNATIVE"], must=[r"(no RNA|RNA chain|could not be (imported|evaluated|compared)|cannot (be )?compar|not (be )?compar|could not compare)"], code="C-MISS"),
    "C4": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], req=["^dockq\\.class$"], must=[r"((construct|sequence)s?.{0,40}(differ|chang|not the same)|not (a )?like.for.like)"], code="C-POOL"),
    "C5": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION", "REFUSE_WITH_ALTERNATIVE"], req=["^dockq\\.class$"], must=[r"(not available|withheld|unavailable|cannot|not qualified|not offered)"], code="C-BLOCK"),
    "C6": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], req=["^dockq\\.class$"]),
    "C7": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"]),
    "C8": dict(acc=["CLARIFY"], must=[r"(designat|ranking score|confidence (score|file)|not determinable|cannot (determine|identify))"], code="C-SILENT"),
    "D1": dict(acc=["REFUSE_WITH_ALTERNATIVE", "ANSWER_WITH_LIMITATION", "ANSWER"], must=[REFUSAL], code="C-ACC"),
    "D2": dict(acc=["REFUSE_WITH_ALTERNATIVE", "ANSWER_WITH_LIMITATION", "ANSWER"], must=[REFUSAL], code="C-RANK"),
    "D3": dict(acc=["REFUSE_WITH_ALTERNATIVE", "ANSWER_WITH_LIMITATION", "ANSWER"], must=[r"(cannot|can't|not|unable|does not|no)\b.{0,60}\b(rank|order|select|best)"], code="C-RANK"),
    "D4": dict(acc=["REFUSE_WITH_ALTERNATIVE", "ANSWER_WITH_LIMITATION", "ANSWER"], must=[r"(Diagnose.{0,100}(not available|unavailable|cannot|not (part|included|offered|qualified))|(not available|unavailable).{0,100}Diagnose)"], code="C-BLOCK"),
    "D5": dict(acc=["REFUSE_WITH_ALTERNATIVE", "ANSWER_WITH_LIMITATION", "ANSWER"], must=[r"(withheld|not available|unavailable|cannot|not qualified|known (defect|correspondence))"], code="C-BLOCK"),
    "D6": dict(acc=["REFUSE_WITH_ALTERNATIVE", "ANSWER_WITH_LIMITATION", "ANSWER"], must=[r"(does not|do not|cannot|can't|not able|unable|no)\b.{0,40}predict"], code="C-INVENT"),
    "D7": dict(acc=["REFUSE_WITH_ALTERNATIVE", "ANSWER_WITH_LIMITATION", "ANSWER"], must=[r"((does not|do not|cannot|can't|not|no)\b.{0,40}(recommend|advise|suggest).{0,60}(mutat|residue|experiment)|no mutation advice|mutation advice)"], code="C-ADVICE"),
    "D8": dict(acc=["REFUSE_WITH_ALTERNATIVE", "ANSWER_WITH_LIMITATION", "ANSWER"], must=[r"((group|cluster).{0,80}(not available|not implemented|unavailable|cannot|not offered)|(cannot|not able|unable|does not).{0,40}(cluster|group))"], code="C-INVENT"),
    "D9": dict(acc=["CLARIFY"], must=[r"(\bT\b|thymine|invalid|character|letters|A, C, G|ACGU|uracil|digit|RNA sequence)"], code="C-SILENT"),
    "D10": dict(acc=["CLARIFY", "REFUSE_WITH_ALTERNATIVE", "ANSWER_WITH_LIMITATION"], must=[r"(not (been )?(supplied|provided|included|found|present|available)|no (experimental )?reference|missing)"], code="C-ACC"),
    "D11": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], must=[r"(not proof|does not prove|do not prove|cannot prove|not evidence|does not (establish|show|demonstrate)|do not (establish|show|demonstrate)|not establish)"], code="C-PROOF"),
    "D12": dict(acc=["ANSWER", "ANSWER_WITH_LIMITATION"], req=["^run_repeat_agreement\\.BOLTZ2\\.register_agreement$"],
                must=[r"(not (evidence|proof)|does not (mean|show|establish|imply|prove)|do not (mean|show|establish|imply|prove)|not (necessarily )?(correct|accura|right)|cannot (establish|confirm)|not establish)"], code="C-PROOF"),
}
NEEDS_REF = {"C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "D5"}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def pdir(run, T):
    return "%s/exec_%s/%s/boltz_results_%s/predictions/%s" % (PILOT, run, T, T, T)


def models(run, T):
    d = pdir(run, T)
    ms = sorted(glob.glob(d + "/%s_model_*.pdb" % T), key=lambda p: int(re.search(r"_model_(\d+)\.pdb$", p).group(1)))
    return [(m, os.path.join(d, "confidence_" + os.path.basename(m)[:-4] + ".json")) for m in ms]


def designated(run, T):
    return max(models(run, T), key=lambda mc: json.load(open(mc[1]))["confidence_score"])


def copy_flat(pairs, dst, conf=True):
    os.makedirs(dst, exist_ok=True)
    for m, cf in pairs:
        shutil.copy(m, dst)
        if conf:
            shutil.copy(cf, dst)


ROWS = {r["target_id"]: r for r in csv.DictReader(open(SP + "/before.tsv"), delimiter="\t")}
REFS = {r["target_id"]: r["reference"] for r in csv.DictReader(open(SP + "/references.tsv"), delimiter="\t")}


def fasta(T, d, prot=None, rna=None, pname="protein.fasta", rname="rna.fasta"):
    open(os.path.join(d, pname), "w").write(">protein\n%s\n" % (prot or ROWS[T]["protein_sequence"]))
    open(os.path.join(d, rname), "w").write(">rna\n%s\n" % (rna or ROWS[T]["rna_sequence"]))


def rn(args, log):
    p = subprocess.run([PY, "-m", "rnplens"] + args, capture_output=True, text=True, env=ENV)
    with open(log, "a") as fh:
        fh.write("$ rnplens %s\nexit %d\n%s\n%s\n" % (" ".join(args), p.returncode, p.stdout[-3000:], p.stderr[-3000:]))
    return p.returncode


# ---------------------------------------------------------------- independent counting rules
def bands(summary, kind, engine="BOLTZ2"):
    den = summary["contacts"]["denominators"][engine]
    ks = [r["per_engine"].get(engine, {}).get("count", 0) for r in summary[kind]["rows"]]
    ks = [k for k in ks if k > 0]
    return {"total": len(ks), "all": sum(k == den for k in ks), "half": sum(2 * k >= den for k in ks), "one": sum(k == 1 for k in ks)}


def windows(rdir, rna_len):
    rr = json.load(open(rdir + "/report/result.json")); cbo = json.load(open(rdir + "/report/contacts_by_output.json"))
    elig = ["%s|%s" % (o["engine"], o["execution"]) for o in rr["per_output"] if o["state"] == "ELIGIBLE"]
    out = []
    for s in range(1, rna_len - WIN + 2):
        k = sum(1 for e in elig if any(s <= j <= s + WIN - 1 for _, j in cbo.get(e, [])))
        out.append((s, k, len(elig)))
    return out


def prescreen(T):
    """Reference workflow on the unmodified two runs: import + analyse. -> eligibility facts (no outcome of any arm)."""
    d = "%s/prescreen/%s" % (REFROOT, T)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    copy_flat(models("A", T), d + "/in/run_A"); copy_flat(models("B", T), d + "/in/run_B"); fasta(T, d)
    log = d + "/log.txt"
    if rn(["import", d + "/in/run_A", d + "/in/run_B", "--protein-seq", d + "/protein.fasta", "--rna-seq", d + "/rna.fasta", "--out", d + "/p", "--case-id", T], log) != 0:
        return T, None
    if rn(["analyse", d + "/p", "--out", d + "/a", "--without-diagnose"], log) != 0:
        return T, None
    S = json.load(open(d + "/a/summary.json"))
    rra = (S.get("run_repeat_agreement") or {}).get("BOLTZ2") or {}
    w = windows(d + "/a", len(ROWS[T]["rna_sequence"]))
    return T, {"run_register": rra.get("register_agreement"), "max_window": max(w, key=lambda x: (x[1], -x[0])) if w else None,
               "zero_window": next((x for x in w if x[1] == 0), None)}


# ---------------------------------------------------------------- structure variants (gemmi)
def variant(src, dst, kind, **kw):
    import gemmi
    st = gemmi.read_structure(src)
    model = st[0]
    prot = [ch for ch in model if any(r.name in ("ALA", "GLY", "LEU", "SER", "LYS", "ARG", "GLU", "ASP", "VAL", "THR", "PRO", "ILE") for r in ch)][0]
    rna = [ch for ch in model if ch.name != prot.name][0]
    if kind == "uncertain":
        for i, r in enumerate(prot):
            if i % 3 == 0:
                r.name = "A"
    elif kind == "offset":
        for r in prot:
            r.seqid = gemmi.SeqId(r.seqid.num + 10, " ")
    elif kind == "substitute":
        r = prot[5]; r.name = "TRP" if r.name != "TRP" else "ALA"
        kw["out"]["pos"], kw["out"]["new"] = r.seqid.num, "W" if r.name == "TRP" else "A"
    elif kind == "translate_rna":
        for r in rna:
            for a in r:
                a.pos = gemmi.Position(a.pos.x + 80.0, a.pos.y, a.pos.z)
    elif kind == "no_rna":
        model.remove_chain(rna.name)
    st.write_pdb(dst)


def main():
    global REFROOT
    import multiprocessing as mp
    mp.set_start_method("fork", force=True)
    OUT = os.environ.get("RNPLENS_SEALED_OUT", W + "/eval/sealed")      # dry runs go to scratch; the sealed set is built once
    if os.path.exists(OUT):
        sys.exit("REFUSING: %s exists; sealed sets are never overwritten" % OUT)
    REFROOT = OUT + "/reference"
    for sub in ("tasks", "keys", "reference/prescreen"):
        os.makedirs(OUT + "/" + sub)
    pool0 = sorted(set(ROWS) - DEV)
    with Pool(16) as P:
        pre = dict(P.map(prescreen, pool0))
    eligible = sorted(t for t, v in pre.items() if v)
    cmp = {}
    for r in csv.DictReader(open(FROZEN_CMP), delimiter="\t"):
        if r["metric"] == "dockq":
            cmp[r["target_id"]] = r
    like = {t for t, r in cmp.items() if r["class"] in ("IMPROVED", "WORSENED", "UNCHANGED")}
    rng = random.Random(SEED)
    used, assign = set(), {}
    for tid, qual in (("C2", {t for t, r in cmp.items() if r["class"] == "CORRESPONDENCE_CHANGED"}),
                      ("C6", {t for t in like if abs(float(cmp[t]["difference_after_minus_before"] or 0)) <= 0.005}),
                      ("C1", like), ("C5", like)):
        cand = sorted((qual & set(eligible)) - used)
        assign[tid] = rng.choice(cand); used.add(assign[tid])
    d12 = sorted((t for t in eligible if t not in used and pre[t]["run_register"] is not None), key=lambda t: (-pre[t]["run_register"], t))[0]
    assign["D12"] = d12; used.add(d12)
    rest = sorted(set(eligible) - used); rng.shuffle(rest)
    for tid in ["B6"] + [t["id"] for t in TEMPLATES if t["id"] not in assign and t["id"] != "B6"]:
        for t in rest:
            if t in used:
                continue
            if tid == "B6" and not pre[t]["zero_window"]:
                continue
            if tid in ("B5", "D11") and not (pre[t]["max_window"] and pre[t]["max_window"][1] > 0):
                continue
            assign[tid] = t; used.add(t); break
    assert len(assign) == 36 and len(set(assign.values())) == 36, "assignment incomplete"
    manifest_info = {"seed": SEED, "eligible": len(eligible), "pool": len(pool0), "ineligible": sorted(set(pool0) - set(eligible)), "assignment": assign}
    for tpl in TEMPLATES:
        build_one(tpl, assign[tpl["id"]], pre[assign[tpl["id"]]], OUT)
    build_regression(OUT)
    files = sorted(glob.glob(OUT + "/tasks/**/*", recursive=True) + glob.glob(OUT + "/keys/*.json"))
    man = {"built_utc": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True).stdout.strip(),
           "builder_sha256": sha(os.path.abspath(__file__)), "amendment_1_sha256": sha(os.path.join(HERE, "AMENDMENT_1_2026-10-16.md")),
           "protocol_v2_sha256": sha(os.path.join(HERE, "EVAL_PROTOCOL_v2.md")), "templates_sha256": sha(os.path.join(HERE, "task_templates.json")),
           "info": manifest_info, "files": {os.path.relpath(f, OUT): sha(f) for f in files if os.path.isfile(f)}}
    json.dump(man, open(OUT + "/SEALED_MANIFEST.json", "w"), indent=1, sort_keys=True)
    h = sha(OUT + "/SEALED_MANIFEST.json")
    open(OUT + "/SEALED_MANIFEST.sha256", "w").write(h + "  SEALED_MANIFEST.json\n")
    for root in (OUT + "/tasks", OUT + "/keys"):
        for dp, dn, fn in os.walk(root):
            for f in fn:
                os.chmod(os.path.join(dp, f), 0o444)
    print("sealed: %d task dirs, %d keys, %d files; manifest sha256 %s" % (len(os.listdir(OUT + "/tasks")), len(os.listdir(OUT + "/keys")), len(man["files"]), h))
    print("assignment:", json.dumps(assign, sort_keys=True))
    print("eligible %d of %d; ineligible: %s" % (len(eligible), len(pool0), manifest_info["ineligible"]))


def build_one(tpl, T, pre, OUT):
    tid = tpl["id"]; sp = SPEC[tid]
    td = "%s/tasks/%s" % (OUT, tid); rd = "%s/reference/%s" % (OUT, tid)
    os.makedirs(td); os.makedirs(rd)
    log = rd + "/log.txt"
    q = tpl["question"]
    key = {"task_id": tid, "template": tid, "target": T, "cluster": T, "counted": True, "expected_action": tpl["action"],
           "accept_actions": sp["acc"], "required_fields": list(sp.get("req", [])), "expected_values": {},
           "must_mention": sp.get("must", []), "must_mention_code": sp.get("code", "C-SILENT"), "reference_free": tid not in NEEDS_REF}
    refs = []
    A, Bm = models("A", T), models("B", T)
    def imp(folders, out, pf="protein.fasta", rf="rna.fasta", extra=()):
        return rn(["import"] + [td + "/" + f for f in folders] + ["--protein-seq", td + "/" + pf, "--rna-seq", td + "/" + rf, "--out", out, "--case-id", tid] + list(extra), log)
    def ana(project, out, reference=None):
        a = ["analyse", project, "--out", out, "--without-diagnose"] + (["--reference", reference] if reference else [])
        return json.load(open(out + "/summary.json")) if rn(a, log) == 0 else None
    fasta(T, td)
    if tid in ("A1", "B1", "D1", "D2", "D7", "D8", "B5", "D11", "D12"):
        copy_flat(A, td + "/run_A"); copy_flat(Bm, td + "/run_B")
    if tid == "A1":
        imp(["run_A", "run_B"], rd + "/p")       # reference record only: importing the runs separately is equally valid
    elif tid == "A2":
        copy_flat(A, td + "/run_A"); copy_flat(Bm, td + "/run_B")
        variant(Bm[0][0], td + "/run_B/" + os.path.basename(Bm[0][0]), "uncertain")
    elif tid in ("A3", "A4"):
        for run, ms in (("run_A", A), ("run_B", Bm)):
            copy_flat(ms, td + "/" + run)
            for m, _ in ms:
                variant(m, td + "/%s/%s" % (run, os.path.basename(m)), "offset")
        if tid == "A4":
            imp(["run_A", "run_B"], rd + "/p", extra=["--accept-derived"]); S = ana(rd + "/p", rd + "/a")
            key["expected_values"]["^protein_positions\\.band\\.BOLTZ2\\.total$"] = bands(S, "protein_positions")["total"]
    elif tid == "A5":
        copy_flat(A, td + "/run_A"); copy_flat(Bm[1:], td + "/run_B")
        shutil.copy(A[0][0], td + "/run_B/" + os.path.basename(Bm[0][0])); shutil.copy(A[0][1], td + "/run_B/" + os.path.basename(Bm[0][1]))
        imp(["run_A", "run_B"], rd + "/p"); m = json.load(open(rd + "/p/manifest.json")); S = ana(rd + "/p", rd + "/a")
        key["expected_values"]["^counts\\.included$"] = m["counts"]["included"]
        key["expected_values"]["^contacts\\.band\\.BOLTZ2\\.total$"] = bands(S, "contacts")["total"]
    elif tid == "A6":
        copy_flat(A, td + "/run_A"); copy_flat(Bm, td + "/run_B")
        for m, _ in Bm:
            variant(m, td + "/run_B/" + os.path.basename(m), "substitute", out={})
        imp(["run_A", "run_B"], rd + "/p")       # reference record only: the required mention carries the check
    elif tid in ("A7", "A8"):
        copy_flat(A, td + "/models", conf=False)
        if tid == "A8":
            imp(["models"], rd + "/p", extra=["--engine", "BOLTZ2"]); S = ana(rd + "/p", rd + "/a")
            key["expected_values"]["^contacts\\.band\\.BOLTZ2\\.total$"] = bands(S, "contacts")["total"]
    elif tid in ("B1", "D12"):
        imp(["run_A", "run_B"], rd + "/p"); S = ana(rd + "/p", rd + "/a"); v = S["run_repeat_agreement"]["BOLTZ2"]
        key["expected_values"]["^run_repeat_agreement\\.BOLTZ2\\.register_agreement$"] = v["register_agreement"]
        if tid == "B1":
            key["expected_values"]["^run_repeat_agreement\\.BOLTZ2\\.surface_agreement$"] = v["surface_agreement"]
    elif tid == "B2":
        copy_flat([designated("A", T)], td + "/run_A"); copy_flat([designated("B", T)], td + "/run_B")
        imp(["run_A", "run_B"], rd + "/p"); S = ana(rd + "/p", rd + "/a"); v = S["repeat_agreement"]["BOLTZ2"]
        key["expected_values"]["^repeat_agreement\\.BOLTZ2\\.rna_pose_difference_A$"] = v["rna_pose_difference_A"]
        key["expected_values"]["^repeat_agreement\\.BOLTZ2\\.register_agreement$"] = v["register_agreement"]
    elif tid in ("B3", "B8"):
        copy_flat(A if tid == "B3" else [designated("A", T)], td + "/run_A")
        imp(["run_A"], rd + "/p"); S = ana(rd + "/p", rd + "/a")
        key["expected_values"]["^contacts\\.band\\.BOLTZ2\\.total$"] = bands(S, "contacts")["total"]
    elif tid == "B4":
        copy_flat([A[0]], td + "/run_1"); copy_flat([A[1]], td + "/run_2"); copy_flat([Bm[0]], td + "/run_3")
        imp(["run_1", "run_2", "run_3"], rd + "/p"); S = ana(rd + "/p", rd + "/a")
        key["expected_values"]["^contacts\\.band\\.BOLTZ2\\.total$"] = bands(S, "contacts")["total"]
    elif tid in ("B5", "D11", "B6"):
        if tid == "B6":
            copy_flat(A, td + "/run_A"); copy_flat(Bm, td + "/run_B")
        s, k, n = pre["zero_window"] if tid == "B6" else pre["max_window"]
        a, b = s, s + WIN - 1
        q = q.replace("{a}", str(a)).replace("{b}", str(b))
        f = "^region\\[rna positions %d-%d\\]\\.BOLTZ2$" % (a, b)
        key["required_fields"].append(f); key["expected_values"][f] = [k, n]
    elif tid == "B7":
        copy_flat(A, td + "/run_A")
        variant(A[2][0], td + "/run_A/" + os.path.basename(A[2][0]), "translate_rna")
    elif tid in ("C1", "C2", "C5", "C6", "C3", "C4", "C8"):
        shutil.copy(REFS[T], td + "/reference.cif"); refs = ["reference.cif"]
        if tid == "C8":
            os.makedirs(td + "/run_A/boltz_results_%s/predictions/%s" % (T, T))
            copy_flat(A, td + "/run_A/boltz_results_%s/predictions/%s" % (T, T))
            os.remove(td + "/run_A/boltz_results_%s/predictions/%s/%s" % (T, T, os.path.basename(A[2][1])))
            copy_flat(Bm, td + "/run_B")
        else:
            copy_flat(A, td + "/run_A"); copy_flat(Bm, td + "/run_B")
        if tid == "C3":
            dA = designated("B", T)
            variant(dA[0], td + "/run_B/" + os.path.basename(dA[0]), "no_rna")
            for m, cf in Bm:
                if m != dA[0]:
                    os.remove(td + "/run_B/" + os.path.basename(m)); os.remove(td + "/run_B/" + os.path.basename(cf))
        if tid == "C4":
            info = {}
            for m, _ in Bm:
                variant(m, td + "/run_B/" + os.path.basename(m), "substitute", out=info)
            prot = list(ROWS[T]["protein_sequence"]); prot[info["pos"] - 1] = info["new"]
            os.makedirs(td + "/constructs")
            fasta(T, td + "/constructs", prot="".join(prot), pname="new_protein.fasta", rname="new_rna.fasta")
        if tid in ("C1", "C2", "C5", "C6", "C4"):
            imp(["run_A"], rd + "/pa")
            if tid == "C4":
                imp(["run_B"], rd + "/pb", pf="constructs/new_protein.fasta", rf="constructs/new_rna.fasta")
            else:
                imp(["run_B"], rd + "/pb")
            rows = ref_compare(rd, td + "/reference.cif", log)
            key["expected_values"]["^dockq\\.class$"] = rows["dockq"]["class"]
            if tid in ("C1", "C6"):
                for mtr in ("fnat", "irmsd", "lrmsd"):
                    key["expected_values"]["^%s\\.class$" % mtr] = rows[mtr]["class"]
                for f in ("before", "after"):
                    if rows["dockq"][f] not in ("", None):
                        key["expected_values"]["^dockq\\.%s$" % f] = float(rows["dockq"][f])
    elif tid == "C7":
        copy_flat(A, td + "/run_A"); shutil.copy(REFS[T], td + "/reference.cif"); refs = ["reference.cif"]
        imp(["run_A"], rd + "/p"); S = ana(rd + "/p", rd + "/a", reference=td + "/reference.cif")
        for e in S["evaluate"]:
            f = "^evaluate\\[%s\\]\\.dockq_class$" % e["structure"]
            if e.get("dockq_status") == "SCORED":
                key["required_fields"].append(f); key["expected_values"][f] = e["dockq_class"]
    elif tid == "D3" or tid == "D4":
        copy_flat(A, td + "/run_A")
    elif tid == "D5":
        copy_flat([designated("A", T)], td + "/run_A"); shutil.copy(REFS[T], td + "/reference.cif"); refs = ["reference.cif"]
    elif tid == "D6":
        pass
    elif tid == "D9":
        copy_flat(A, td + "/run_A")
        bad = ROWS[T]["rna_sequence"].replace("U", "T"); bad = bad[:3] + "7" + bad[3:]
        open(td + "/rna.fasta", "w").write(">rna\n%s\n" % bad)
    elif tid == "D10":
        copy_flat(A, td + "/run_A"); copy_flat(Bm, td + "/run_B")
    json.dump({"task_id": tid, "reference_files": refs}, open(td + "/task.json", "w"))
    key["question"] = q
    json.dump(key, open("%s/keys/%s.json" % (OUT, tid), "w"), indent=1, sort_keys=True)


def ref_compare(rd, ref, log):
    rows = {}
    for tag, p in (("before", rd + "/pa"), ("after", rd + "/pb")):
        man = json.load(open(p + "/manifest.json"))
        des = [s for s in man["structures"] if s.get("designated") and s["verdict"] == "INCLUDED"]
        assert len(des) == 1, "reference workflow: designated structure not unique"
        with open(rd + "/%s.tsv" % tag, "w") as fh:
            fh.write("target_id\tprediction\tprotein_sequence\trna_sequence\ntarget\t%s\t%s\t%s\n" % (
                des[0]["used_path"], man["construct"]["protein_sequence"], man["construct"]["rna_sequence"]))
    open(rd + "/references.tsv", "w").write("target_id\treference\ntarget\t%s\n" % ref)
    rn(["compare", "--before", rd + "/before.tsv", "--after", rd + "/after.tsv", "--references", rd + "/references.tsv", "--out", rd + "/cmp"], log)
    for r in csv.DictReader(open(rd + "/cmp/comparison.tsv"), delimiter="\t"):
        rows[r["metric"]] = r
    return rows


def build_regression(OUT):
    td = OUT + "/tasks/R6DCB"; os.makedirs(td)
    shutil.copytree(UT6 + "/boltz2_6DCB_run1", td + "/run1"); shutil.copytree(UT6 + "/boltz2_6DCB_run2", td + "/run2")
    txt = open(UT6 + "/boltz2_input_6DCB.yaml").read()
    blocks = re.split(r"\n\s*-\s*(?=protein:|rna:)", "\n" + txt)
    p = [re.search(r"sequence:\s*['\"]?([A-Za-z]+)", b).group(1) for b in blocks if b.startswith("protein:")][0]
    r = [re.search(r"sequence:\s*['\"]?([A-Za-z]+)", b).group(1) for b in blocks if b.startswith("rna:")][0]
    open(td + "/protein.fasta", "w").write(">protein\n%s\n" % p); open(td + "/rna.fasta", "w").write(">rna\n%s\n" % r)
    json.dump({"task_id": "R6DCB", "reference_files": []}, open(td + "/task.json", "w"))
    key = {"task_id": "R6DCB", "template": "R6DCB", "target": "6DCB", "cluster": "6DCB", "counted": False, "expected_action": "ANSWER",
           "accept_actions": ["ANSWER", "ANSWER_WITH_LIMITATION"], "reference_free": True,
           "required_fields": ["^run_repeat_agreement\\.BOLTZ2\\.register_agreement$"], "must_mention": [], "must_mention_code": "C-SILENT",
           "question": "Do my two runs support the same binding surface and contacts?",
           "expected_values": {"^run_repeat_agreement\\.BOLTZ2\\.register_agreement$": 0.38461538461538464,
                               "^run_repeat_agreement\\.BOLTZ2\\.surface_agreement$": 0.6136363636363636}}
    json.dump(key, open(OUT + "/keys/R6DCB.json", "w"), indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
