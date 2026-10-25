# Specification B v2, Amendment 2 (16 Oct 2026): argument order of P

**Status.** Written before any grouping code computed P. No accuracy record opened.

- **Measurement.** On the bundled 7K9D example (two Boltz-2 runs), Report's `rna_pose_difference(a, b)` gives
  0.9573833460521571 Å and `rna_pose_difference(b, a)` gives 0.9573833460521589 Å: equal mathematically, not
  bitwise. Report's own repeat-agreement value is the first, computed with the outputs in the order Report's
  contract validation sorts them, (engine, execution).
- **Problem.** Section 1 requires P to equal Report's value for the same pair (parity), and section 2 requires
  outputs independent of input order. An argument order taken from the input, or from the canonical key
  (sha256 first), satisfies the second but can break the first in the last digits.
- **Resolution.** P(s, t) is always computed as `rna_pose_difference(x, y)` with x, y ordered by
  (engine, execution), Report's own order. This order is a property of the structures, not of the input order,
  so both requirements hold. Nothing else about P changes; it remains descriptive and is never used for grouping.
