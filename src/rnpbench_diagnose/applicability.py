"""Validated applicability domain of the Diagnose statements (RNPLens 0.2.0rc3).

The reference distributions and the correlations behind each statement were measured on particular inputs. This
module states those conditions and checks a run against them, so that a configuration nobody validated is never
presented as if it were. It changes no computation: the disagreement values, bands and statement text are
produced exactly as before. Outside the domain, Diagnose refuses unless the user explicitly accepts running
outside it, and the report then says so prominently.

Sources, frozen before this check was written (docs/validation/):
  within_engine  development cohort P: 65 targets, Boltz-2, 50 candidates per target; depth control at 5
                 candidates on the same cohort; out-of-sample cohort: 807 targets, Boltz-2, 5 candidates each.
  cross_engine   development cohort E: 59 targets, one designated output from each of Boltz-2, Chai-1, RF3 and
                 RoseTTAFold2NA (AlphaFold 3 excluded); no out-of-sample test (13 eligible targets only).
  both           every benchmark construct is one protein chain and one RNA chain.
"""
# accepted spellings of the validated engines (case, spaces, "-" and "_" are ignored)
ENGINE_ALIASES = {"BOLTZ2": "BOLTZ2", "CHAI1": "CHAI1", "RF3": "RF3", "ROSETTAFOLD3": "RF3",
                  "RF2NA": "RF2NA", "ROSETTAFOLD2NA": "RF2NA"}

DOMAIN = {
    "within_engine": {
        "engines": ["BOLTZ2"],
        "candidates_min": 5, "candidates_max": 50,
        "chains": "one protein chain and one RNA chain per structure",
        "evidence": "development: 65 targets (58 protein clusters), Boltz-2, 50 candidates per target, depth control "
                    "at 5 candidates; out of sample: 807 targets (456 protein clusters), Boltz-2, 5 candidates per target",
    },
    "cross_engine": {
        "engines": ["BOLTZ2", "CHAI1", "RF2NA", "RF3"],
        "engines_min": 3,
        "chains": "one protein chain and one RNA chain per structure",
        "evidence": "development only: 59 targets (59 protein clusters), one designated output from each of Boltz-2, "
                    "Chai-1, RF3 and RoseTTAFold2NA; AlphaFold 3 was excluded; not tested out of sample",
    },
}


def canonical_engine(label):
    """The validated engine a label names, or None."""
    key = "".join(c for c in str(label).upper() if c not in " -_")
    return ENGINE_ALIASES.get(key)


def chain_counts(path):
    """(protein chains, RNA chains) of the first model, by polymer type."""
    import gemmi
    st = gemmi.read_structure(path)
    st.setup_entities()
    n_p = n_r = 0
    for ch in st[0]:
        pt = ch.get_polymer().check_polymer_type()
        if pt in (gemmi.PolymerType.PeptideL, gemmi.PolymerType.PeptideD):
            n_p += 1
        elif pt == gemmi.PolymerType.Rna:
            n_r += 1
    return n_p, n_r


def assess(mode, valid_paths, engine_of=None, declared_engine=None):
    """Return the applicability record of one run.

    valid_paths  the structures classified VALID (the ones the statements are computed from)
    engine_of    cross_engine: {path: declared label}
    declared_engine  within_engine: the declared label of the engine that produced every candidate, or None
    """
    d = DOMAIN[mode]
    reasons = []
    if mode == "within_engine":
        eng = canonical_engine(declared_engine) if declared_engine else None
        if declared_engine is None:
            reasons.append("the engine that produced the candidates was not declared (--engine); the reference and the "
                           "validation are for Boltz-2 candidates")
        elif eng not in d["engines"]:
            reasons.append("candidates from %r: the reference and the validation are for Boltz-2 candidates only"
                           % declared_engine)
        n = len(valid_paths)
        if n < d["candidates_min"]:
            reasons.append("%d valid candidates: validated with 5 and with 50 candidates per target, not fewer than 5" % n)
        if n > d["candidates_max"]:
            reasons.append("%d valid candidates: validated with up to 50 candidates per target" % n)
        engines = [eng or declared_engine] if declared_engine else []
    else:
        labels = [engine_of[p] for p in valid_paths]
        canon = [canonical_engine(x) for x in labels]
        bad = sorted({lab for lab, c in zip(labels, canon) if c not in d["engines"]})
        if bad:
            reasons.append("engine label(s) %s: the cross-engine reference covers Boltz-2, Chai-1, RF3 and RoseTTAFold2NA "
                           "only (AlphaFold 3 and other engines were not included)" % ", ".join(repr(b) for b in bad))
        engines = [c or lab for lab, c in zip(labels, canon)]
    multi = []
    for p in valid_paths:
        try:
            n_p, n_r = chain_counts(p)
        except Exception as ex:                       # validity already loaded the file; keep the reason, do not guess
            multi.append("%s (chains not determined: %s)" % (p, type(ex).__name__)); continue
        if (n_p, n_r) != (1, 1):
            multi.append("%s (%d protein, %d RNA chains)" % (p, n_p, n_r))
    if multi:
        reasons.append("%d structure(s) are not one protein chain and one RNA chain, the composition of every validated "
                       "construct: %s" % (len(multi), "; ".join(multi[:5]) + (" ..." if len(multi) > 5 else "")))
    return {"status": "inside_validated_domain" if not reasons else "outside_validated_domain",
            "mode": mode, "engines_declared": engines, "n_structures_used": len(valid_paths),
            "reasons_outside": reasons,
            "validated_domain": {k: v for k, v in d.items()},
            "outside_domain_accepted_by_user": False}
