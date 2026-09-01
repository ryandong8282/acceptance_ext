from pathlib import Path

from acceptance_ext.audit import audit_result
from acceptance_ext.config import load_profile
from acceptance_ext.extractors import DeterministicExtractor
from acceptance_ext.parsers.markdown import MarkdownParser


FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic_standard.md"


def test_audit_grounding():
    ir = MarkdownParser().parse(FIXTURE)
    result = DeterministicExtractor().extract(ir, load_profile())
    report = audit_result(result, source_text=ir.markdown)
    assert report["metrics"]["grounded_rate"] == 1.0
    assert report["metrics"]["error_count"] == 0
