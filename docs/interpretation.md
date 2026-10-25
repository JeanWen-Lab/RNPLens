# Interpreting RNPLens results

RNPLens is built on distinctions that the accompanying study found easy to blur. Keep them apart when reading
any output.

| keep apart | why |
|---|---|
| **structural accuracy** (Evaluate) and **physical validity** (Diagnose `validity`) | an output can be a well-formed structure and still be far from the experimental complex, or close in RMSD and physically implausible |
| **RNA conformation** and **RNA placement** | Evaluate's geometry route measures them separately; a correct RNA shape in the wrong position, and the reverse, both occur |
| **binding-surface agreement** and **contact-register agreement** | outputs can use the same protein surface yet pair different residues with different nucleotides; the register is the stricter question |
| **reference-free agreement** (Report, Diagnose) and **known accuracy** (Evaluate) | agreement is descriptive; engines and samples can agree and be wrong together |
| **available** structural outputs and **scoreable** outputs | a file that exists may lack a polymer, an interface or usable numbering; such outputs get named outcomes, never zero |
| **native-informed diagnostics** and **deployable** workflows | analyses in the manuscript that use the experimental structure (for example best-of-N oracles) describe headroom; they are not something you can run on a new target |

## Reading Evaluate

- DockQ and fnat describe the interface; the geometry route describes the RNA and the protein separately. In 0.4
  the geometry route is blocked (residue-correspondence defect; [limitations.md](limitations.md)); only the DockQ
  route is a qualified tool.
- A `NO_VALUE` status is a result: read its stage and reason. Never average it in as zero.
- Whole-construct protein RMSD reflects domain arrangement; do not read it as a fold-accuracy measure.
- Missing experimental positions are unknown, not non-contacts.
- The result depends on the reference representation: one NMR model versus the ensemble, or deposited
  coordinates versus map density, can change the conclusion for an individual target.

## Reading Report

- Support is a count of engines; confidences are per engine and are not comparable across engines.
- Interface hypotheses are alternatives, not a vote; the largest group is not implied to be correct.
- With one engine, only repeat agreement is available.

## Reading Diagnose

- A band places a value in a frozen development reference, not among your structures.
- High disagreement is a reason to look more closely; low disagreement is not evidence of accuracy.
- The protein-side statement is complementary to, not independent of, the engine's own confidence.
- The RNA-side statement has not been validated out of sample.

## What RNPLens does not do

It does not predict complexes from sequence, select the best structure, give calibrated probabilities of
correctness, independently validate every structure, establish physical or induced-fit mechanisms, replace
experimental structure determination, or identify a universally best prediction engine.

## Words used by the 0.4 outputs, and what they do not mean

- **"support", "contact support", "supports the contact".** These count the predictions that list a contact. They
  are a property of the supplied predictions, not evidence that the contact exists in the real complex.
  ("contact_support" is the field name of the qualified Report tool.)
- **"representative of group k" (register medoid).** This is the member most similar to the others in its group.
  Ties are broken by a file checksum, so the choice carries no preference. It is not the best, preferred or most
  accurate structure.
- **Groups holding the engine-designated structure are shown first.** This is for orientation only, so that you can
  find the structure the engine itself picked. It is not a priority or a ranking.
- **"not observed".** A position that is not resolved in a structure. It is never counted as "no contact".
