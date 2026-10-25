# `rnplens region`: contacts in an RNA region, compared between runs

Status: **DESCRIPTIVE** (RNPLens 0.4 development). The contact records it reads are Report's own, and the
filtering reuses that qualified route unchanged. The way runs are compared and presented is new and has been tested,
but its output is descriptive only.

`rnplens region` answers two menu questions:

- **B.** Which protein residues contact this RNA region, in which structures?
- **C.** Within this region, which contacts do all runs share, and which appear in only one run?

It does not predict, rank or select structures. A contact that recurs across predictions is not evidence of
correctness.

## Command

```
rnplens region PROJECT ANALYSIS --rna A-B [--protein C-D] [--runs RUN1,RUN2,...] [--replace]
```

- `PROJECT` is the directory written by `rnplens import`. `ANALYSIS` is the directory written by `rnplens analyse`
  for that project.
- `--rna A-B` sets the RNA range in **construct numbering**: 1-based and inclusive, counted on `construct_rna.fasta`.
  A range that is reversed, or that lies outside the declared construct, is refused with a message. For example,
  `RNA range 70-80 is outside the declared RNA construct (positions 1-60)`.
- `--protein C-D` is an optional protein range in construct numbering. When given, only contacts inside both ranges
  are listed.
- `--runs` limits the comparison to the named runs of the project manifest. The default is every run. A run name is
  qualified as `ENGINE:run` only when two engines share it.
- `--replace` writes the region directory again. Without it, an existing result is never overwritten; repeating
  the same request while its recorded inputs are unchanged reuses the existing result and prints it again.

### Outputs

Outputs are written to `ANALYSIS/region_<a>-<b>[_p<c>-<d>]/`. A non-default `--runs` selection adds the suffix
`_runs-<8 hex>`, a hash of the selected run names, so that two selections never share a directory.

| file | content |
|---|---|
| `region.json` | Top-level keys: `provenance`, `region`, `contact_definition`, `runs`, `contacts`, `summary`, `limits` and `figure`. Every structure, contact row and summary value carries an `evidence_id` of the form `region_13-23/region.json#/contacts/0`. |
| `region_contacts.tsv` | One row per contact and run. Each row gives the protein and RNA identifiers (`K14`, `G20`), the class, the run, the engine, the designated structure and sample, `k` of `n` structures, the not-observed count, and the additional samples. It also lists the `id:sample` of every structure that has the contact, and the row's evidence ID. |
| `region.html` | A readable page: structures compared, then the overview counts, then the contacts by run (shared, only in one run, present in some runs), then the contact map and its limits. The page passes the wording audit before it is written. |
| `region_map.png` | A protein-by-RNA contact map for each compared run, over the whole construct. Colour shows the fraction of the run's structures that list the contact, and the declared range is outlined. matplotlib is optional, as for the analysis summary. Without it the image is not drawn and the page says so. |

All files are written atomically.

## What is computed, and from what

The **only contact source** is `ANALYSIS/report/contacts_by_output.json`, which Report writes itself. It maps each
`ENGINE|run#sample` to a list of `[protein_position, rna_position]` pairs in construct numbering. The command filters
those lists to the range and joins them to `PROJECT/manifest.json` for provenance: structure id, engine, run, sample,
designated flag, used file and SHA-256. Residue letters come from the construct FASTA files.

The contact definition is copied verbatim from `summary.json` (`contacts.definition`):

> protein residue and RNA nucleotide with any heavy-atom pair within 5.0 A, in construct positions (Report's own
> contact lists)

Before anything is listed, the command runs these consistency checks. If any one fails, the request is refused and
no partial output is written:

- the construct FASTA files equal the manifest construct;
- the analysis was built from this project (same case, inventory and construct lengths);
- every key in `contacts_by_output.json` names an included structure;
- Report's per-output SHA-256 equals the manifest's `used_sha256`;
- every contact is a pair of construct positions;
- `contacts_by_output.json` is unchanged since Report wrote it (checked against `report/rnplens_run.json`).

### Per run, designated structure and additional samples

For each compared run and contact, the output gives three things:

- whether the run's **engine-designated structure** lists the contact. The designation and its rule come from the
  manifest, for example "highest Boltz-2 confidence_score". If the designated structure itself was excluded, it is
  named as *not compared*.
- **k of n**: k of the run's n compared structures list the contact.
- **additional samples**: k of n among the run's structures other than the designated one.

Structures that the import excluded, or that Report found ineligible, are listed under `not_compared` with the reason.
They never count in a denominator.

### Missingness: "not observed" is not "no contact"

For every compared structure, the used structure file is read with gemmi. The command checks that each RNA position
of the range is present with at least one heavy atom in **every** copy of the RNA chain that Report reads. It checks
the same for each protein position involved (the protein range, or the protein positions of the listed contacts).

The mapping from file residues to construct positions is accepted only when it is exact:

- the file's SHA-256 equals the manifest's;
- each recorded chain has exactly the construct length;
- residue *i* is numbered *i*, with no insertion codes;
- residue *i* carries the construct letter at position *i*. Modified nucleotides map through their parent, so PSU
  maps to U, and they are listed under `modified_nucleotides`.

Each structure then receives one coverage status:

| coverage | meaning |
|---|---|
| `COMPLETE` | Every position checked is resolved. |
| `PARTIAL` | The mapping is exact, but some positions have no heavy atom. They are listed. |
| `UNRESOLVED` | The mapping is not exact, and the reason is given. Nothing is guessed. |

A structure can fail to list a contact for two different reasons, and each is labelled differently:

- **absent**: both positions are resolved in that structure.
- **not observed**: one or both positions are unresolved, or the structure's coverage is `UNRESOLVED`.

Run-level counts state `of` (the structures compared), `not_observed` and `observable`. A run in which a contact was
not listed but could not be checked everywhere is `NOT_DETERMINED` for that contact. Such a contact is never counted
as "found only in" another run.

### Classes and counts (no agreement formula)

- **Shared by all runs.** Every compared run has at least one structure that lists the contact.
- **Found only in run X.** Run X lists the contact, and it is *absent* in every structure of every other run. Merely
  not observed does not qualify.
- **Present in some runs.** Every other case. The output gives the runs present, absent and not determined.

The summary also gives the number of contacts present in exactly *j* of *R* runs, for every *j*. The same listing is
used for two runs and for three or more. No agreement score (for example Jaccard or register agreement) is computed
for the region.

## Worked example (bundled 7K9D example, two Boltz-2 runs)

```
rnplens import examples/reference_free/report_7K9D/exec_A examples/reference_free/report_7K9D/exec_B \
    --protein-seq examples/reference_based/7K9D_protein.fasta --rna-seq examples/reference_based/7K9D_rna.fasta \
    --engine BOLTZ2 --case-id 7K9D_example --out p
rnplens analyse p --out r
rnplens region p r --rna 13-23
```

RNA 13-23 reads `GUUUGGUGACA`. Each run has one structure, which is also the run's designated structure: s001
(exec_A) and s002 (exec_B). Both structures have `COMPLETE` coverage of the range.

Report's lists contain 36 contacts in RNA 13-23. Of these 36 contacts, 32 are shared by both runs.

- Found only in run exec_A: R18-A21.
- Found only in run exec_B: R16-U14, D39-U15, R45-U15.

The designated structure of exec_A lists 33 of the 36 contacts, and that of exec_B lists 35. With one structure per
run there are no additional samples, so those columns read "none".

The command prints:

```
rnplens region: RNA 13-23; 2 run(s) compared (exec_A, exec_B); 2 structure(s)
  contacts in range: 36; shared by all runs: 32; present in some runs: 0; not determined somewhere: 0
  found only in run exec_A: 1 (R18-A21)
  found only in run exec_B: 3 (R16-U14, D39-U15, R45-U15)
  ...
  Recurrence among predictions is not evidence of correctness.
```

A test (`tests/test_region.py::test_worked_example_in_docs_matches`) checks these numbers against a fresh run. A
second test checks them against the frozen expectation in `tests/fixtures_v04/region/expected_7K9D_rna13-23.json`.

A parity test checks that the listing equals a direct filter of `contacts_by_output.json`. That test covers this
range, the whole RNA, and two combined RNA and protein ranges.

## Interpretation limits

- A contact that recurs among predictions is not evidence of correctness. The counts say how often the supplied
  predictions list a contact. They are not frequencies in the real complex, and they do not say how likely a contact
  is to exist.
- Predictions from the same model, or from the same run, are not independent. Several can share one error.
- "Not observed" means the contact could not be checked in that structure. It is not a negative result.
- "Shared" and "found only in one run" are listings with explicit counts. They do not measure how similar the runs
  are, and they depend on the contact definition above: a 5.0 A heavy-atom cutoff, with copies combined by union.
- A residue that has at least one heavy atom counts as resolved. A partly built residue can therefore miss contacts
  that its absent atoms would have made.
- A position missing in only one copy of a repeated chain makes that position unresolved for the structure. This is
  a conservative rule.
- Nothing here estimates which structure is closest to the experimental complex, the binding affinity, or whether the
  protein and RNA interact.

## Tests

The tests are in `tests/test_region.py` and `tests/test_region_edge.py`. Fixtures are edited copies of the bundled
7K9D example, written under `tmp_path` by `tests/fixtures_v04/region/builders.py`.

| area | what the tests cover |
|---|---|
| parity and regression | parity with the direct filter; set-operation classes; the frozen worked example |
| identifiers and provenance | construct letters; provenance and evidence IDs that resolve |
| input handling | range validation; run selection; malformed and tampered records; data access (only declared inputs are opened) |
| outputs | determinism (byte-identical apart from `created_utc`); refusal to overwrite; graceful degradation without matplotlib; wording-audit blocking; no agreement score; CLI and capability registration |
| numbering offsets | an offset copy, which import turns into a renumbered derived copy; an inexact numbering, which gives `UNRESOLVED` |
| modified nucleotides | U15 written as HETATM PSU |
| incomplete structures | residues 18-20 deleted: excluded at import; or, in a deliberately inconsistent project, `UNRESOLVED`. Also an excluded designated sample, and a nucleotide with no heavy atom (`PARTIAL`, "not observed") |
| other edge cases | no contacts in range; two RNA copies; incompatible constructs; a mutated sequence; three runs; one run with four samples (designated versus additional) |
