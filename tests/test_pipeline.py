from pathlib import Path

from acceptance_ext.pipeline import ExtractionPipeline


def test_smoke_extracts_grounded_items() -> None:
    document = ExtractionPipeline(parser="markdown").run(Path("sample_data/mini_standard.md"))
    items = [
        item
        for division in document.tree
        for lot in division.children
        for item in lot.children
    ]
    assert len(items) == 4
    assert document.metrics["grounding_rate"] == 1.0
    assert any(item.item_category == "主控项目" for item in items)
    assert any(item.min_sampling and "10%" in item.min_sampling for item in items)
    assert all(item.source_quote for item in items)
