"""Probe for records/release/MACOS_NUMERICAL_DIFFERENCE.md (read-only; writes one JSON to the path given).

Recomputes Report's repeat-agreement RNA pose difference for the bundled 7K9D example (exec_A vs exec_B, the
two designated Boltz-2 outputs) through Report's own frozen functions, and records every intermediate of
geometry.kabsch_rmsd bit-exactly (float.hex), plus the same arithmetic with BLAS-free numpy (einsum,
optimize=False) and the linear-algebra build information. It changes no file of the repository.
Usage: python records/release/macos_float_probe.py OUT.json  (PYTHONPATH=<checkout>/src; RNPLENS_CHECKOUT=<checkout>
when the script is run from outside the checkout)
"""
import hashlib, json, os, platform, sys
import numpy as np
from rnpbench_report import geometry as G

ROOT = os.environ.get("RNPLENS_CHECKOUT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EX = os.path.join(ROOT, "examples", "reference_free", "report_7K9D")


def tracks(path):
    prot, rna, _ = G.split_chains(G.parse_model(path))
    ca, c4 = G.backbone_tracks(prot, rna)
    return {"ca": ca, "c4": c4}


def hx(a):
    return [float(v).hex() for v in np.asarray(a, dtype=np.float64).ravel()]


def sha(a):
    return hashlib.sha256(np.ascontiguousarray(a, dtype="<f8").tobytes()).hexdigest()


def main(out):
    o1, o2 = tracks(os.path.join(EX, "exec_A", "7K9D_model_0.pdb")), tracks(os.path.join(EX, "exec_B", "7K9D_model_0.pdb"))
    pose, capped = G.rna_pose_difference(o1, o2)
    # identical selection to rna_pose_difference for 1 protein copy and 1 RNA copy (identity permutation)
    P = np.array([u for u, v in zip(o1["ca"][0], o2["ca"][0]) if u is not None and v is not None])
    Q = np.array([v for u, v in zip(o1["ca"][0], o2["ca"][0]) if u is not None and v is not None])
    X = np.array([u for u, v in zip(o1["c4"][0], o2["c4"][0]) if u is not None and v is not None])
    Y = np.array([v for u, v in zip(o1["c4"][0], o2["c4"][0]) if u is not None and v is not None])
    rec = {"platform": platform.platform(), "machine": platform.machine(), "python": sys.version.split()[0],
           "numpy": np.__version__, "n_protein_pairs": len(P), "n_rna_pairs": len(X),
           "input_sha256": {k: sha(v) for k, v in (("P", P), ("Q", Q), ("X", X), ("Y", Y))},
           "report_value": pose, "report_value_repr": repr(pose), "report_value_hex": float(pose).hex(), "capped": capped}
    # step by step, exactly as geometry.kabsch_rmsd
    Pc, Qc = P.mean(0), Q.mean(0)
    H = (P - Pc).T @ (Q - Qc)
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    Rm = Vt.T @ np.diag([1, 1, d]) @ U.T
    M = (X - Pc) @ Rm.T + Qc - Y
    r = float(np.sqrt((M ** 2).sum(1).mean()))
    rec["steps"] = {"Pc": hx(Pc), "Qc": hx(Qc), "H": hx(H), "S": hx(S), "U": hx(U), "Vt": hx(Vt), "d": float(d),
                    "Rm": hx(Rm), "M_sha256": sha(M), "r_hex": r.hex(), "equals_report_value": r == pose}
    # BLAS-free variants: einsum without optimisation uses numpy's own loops, not BLAS
    H2 = np.einsum("ni,nj->ij", P - Pc, Q - Qc, optimize=False)
    U2, S2, Vt2 = np.linalg.svd(H2)
    d2 = np.sign(np.linalg.det(Vt2.T @ U2.T))
    R2 = np.einsum("ij,jk,kl->il", Vt2.T, np.diag([1, 1, d2]), U2.T, optimize=False)
    M2 = np.einsum("nj,ij->ni", X - Pc, R2, optimize=False) + Qc - Y
    r2 = float(np.sqrt((M2 ** 2).sum(1).mean()))
    rec["blas_free"] = {"H": hx(H2), "H_equals_blas_H": bool((H2 == H).all()), "S": hx(S2), "Rm": hx(R2),
                        "Rm_equals_blas_Rm": bool((R2 == Rm).all()), "r_repr": repr(r2), "r_hex": r2.hex()}
    # mixed: BLAS H (as Report) with BLAS-free final transform, to localise the step
    M3 = np.einsum("nj,ij->ni", X - Pc, Rm, optimize=False) + Qc - Y
    rec["blas_H_einsum_apply"] = repr(float(np.sqrt((M3 ** 2).sum(1).mean())))
    try:
        cfg = np.show_config(mode="dicts")
        rec["numpy_build"] = {"blas": cfg.get("Build Dependencies", {}).get("blas"),
                              "lapack": cfg.get("Build Dependencies", {}).get("lapack"),
                              "simd": cfg.get("SIMD Extensions")}
    except Exception as ex:  # older numpy
        rec["numpy_build"] = "unavailable: %s" % ex
    try:
        import threadpoolctl
        rec["threadpools"] = threadpoolctl.threadpool_info()
    except Exception as ex:
        rec["threadpools"] = "threadpoolctl unavailable: %s" % type(ex).__name__
    # exact inputs for an independent high-precision recomputation
    rec["inputs_hex"] = {"P": hx(P), "Q": hx(Q), "X": hx(X), "Y": hx(Y)}
    with open(out, "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True, default=str)
    print(json.dumps({k: rec[k] for k in ("platform", "report_value_repr", "n_protein_pairs", "n_rna_pairs")}))
    print("blas_free", rec["blas_free"]["r_repr"], "H_eq", rec["blas_free"]["H_equals_blas_H"], "Rm_eq",
          rec["blas_free"]["Rm_equals_blas_Rm"], "blasH_einsum_apply", rec["blas_H_einsum_apply"])


if __name__ == "__main__":
    main(sys.argv[1])
