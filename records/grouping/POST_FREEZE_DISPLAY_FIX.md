# Post-freeze display fix to grouping.py (16 Oct 2026, integration)

**Change.** In the two-group difference map, the `fraction` string is now the unreduced count
`members_containing/denominator_resolved_members` (for example `0/26`). Before, it was the reduced fraction
(`0/1`), which hid the denominator.

**Unchanged.** `fraction_value` (the float), `frequent`, the counts, the grouping, the representatives and every
qualification number are unchanged. The qualification ran on the frozen code recorded in `CODE_FREEZE.md`. Only
this display string differs, so the sha256 of `grouping.py` now differs from the freeze table.

**Why.** The Grouping track flagged the reduced display as misleading, and deferred the fix because the code was
frozen.
