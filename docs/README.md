# RNPLens documentation

## Getting started
- [Which analysis should I use?](which_analysis_should_i_use.md). This guide is also the Assistant's frozen
  reference text; Diagnose, which it describes, is not available in 0.4.0.
- [Installation](installation.md): [Linux](install_linux.md), [macOS](install_macos.md)
- [Quick start](quickstart.md): the two worked examples, their outputs and how to read them

## Reference-based evaluation
- [Evaluate](evaluate.md): the DockQ route (the four-axis geometry route is not available in 0.4.0)
- [Evaluate input contract](INPUT_CONTRACT.md)
- [Output formats](output_formats.md) and [output schemas](schemas/)

## Reference-free analysis
- [Report](report.md): surface, contact-register and RNA-pose agreement
- [Working from engine output folders](workflow.md): `import`, `analyse`, `compare`
- [Contacts in an RNA region](region.md)
- [Binding-proposal grouping](grouping.md)
- [Evidence lookup and Methods export](evidence_and_methods.md)
- [Managed projects: update, clarify, relink](project_state.md)
- [Diagnose](diagnose.md) (not available in 0.4.0; qualification ongoing)

## Viewer and question menu
- [Viewer guide and nucleotide contact explorer](viewer.md)
- [Question menu and viewer commands](assist.md) (`rnplens assist`, `rnplens view`)

## RNPLens Assistant (optional, experimental)
- [Assistant README](../assistant/README.md): status, limitations and use
- [Setup, requirements and privacy](setup_and_privacy.md)
- [Model use and privacy](model_and_privacy.md)
- [Supported platforms and the two modes](platforms.md)
- [Follow-ups](followup.md)

## Interpreting results
- [Interpretation](interpretation.md)
- [Limitations](limitations.md)
- [Capabilities](capabilities.md): what each command does, how to interpret it, and the scope of 0.4.0

## Reproducibility, provenance and release
- [Reproducibility](reproducibility.md)
- [Software availability versus reproducibility of the study](paper_reproducibility.md)
- [Bundled example data: provenance and terms](example_data_provenance.md)
- [Dependencies and third-party terms](dependencies.md)
- [Historical internal identifiers](identifiers.md)
- [Release status](release_conditions.md)
- [Code availability](code_availability.md)

## Development and qualification records
These records document how RNPLens was developed, tested and qualified. They are kept unchanged as evidence; many
of them describe pre-release versions.
- [validation/](validation/): out-of-sample validation protocol and results
- [dev/specs/](dev/specs/): design specifications
- [Release manifest verifier](release_manifest.md) (`tools/release_manifest.py`; a development tool)
- [`records/`](../records/README.md): release, replay, viewer, grouping, platform and integration records
- [`demos/`](../demos/README.md) and [`qualification_v04/`](../qualification_v04/README.md): demonstration and
  qualification scripts for 0.4 development
