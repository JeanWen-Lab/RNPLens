"""QA install-science fix round: docs/workflow.md documents the manifest fields added for O3 and O4."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_workflow_docs_list_the_new_manifest_fields():
    t = open(os.path.join(ROOT, "docs", "workflow.md"), encoding="utf-8").read()
    for k in ("skipped_files", "counts.skipped_structure_like", "designated_included", "designated_note", "excluded at import; not analysed"):
        assert k in t, k
