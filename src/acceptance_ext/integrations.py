from __future__ import annotations

from .models import ResultDocument


def docetl_blueprint() -> dict:
    return {
        "operations": [
            {"name": "segment_clauses", "type": "map", "deterministic": True},
            {"name": "extract_acceptance_items", "type": "extract", "schema": "AcceptanceItem"},
            {"name": "resolve_references", "type": "resolve", "key": "source_clause"},
            {"name": "attach_50300", "type": "map", "deterministic": True},
            {"name": "audit", "type": "filter", "keep": "review-required"},
        ]
    }


def opencontracts_fieldset() -> dict:
    return {
        "name": "construction-acceptance-items",
        "fields": [
            {"name": "source_clause", "query": "Exact source clause number"},
            {"name": "source_quote", "query": "Verbatim supporting clause"},
            {"name": "item_category", "query": "主控项目 or 一般项目"},
            {"name": "min_sampling", "query": "Explicit minimum inspection quantity"},
        ],
        "human_review": True,
    }


def unstract_prompt() -> str:
    return (
        "Extract construction acceptance items as JSON. Every item must carry an exact "
        "source quote and clause number. Never infer a quantity when the source does not state it."
    )


def graph_rows(document: ResultDocument) -> list[dict]:
    rows: list[dict] = []
    for division in document.tree:
        rows.append(
            {
                "source": document.standard_no,
                "relation": "HAS_DIVISION_ITEM",
                "target": division.name,
            }
        )
        for lot in division.children:
            rows.append(
                {
                    "source": division.name,
                    "relation": "HAS_INSPECTION_LOT",
                    "target": lot.name,
                }
            )
            for item in lot.children:
                rows.append(
                    {
                        "source": lot.name,
                        "relation": "HAS_ACCEPTANCE_ITEM",
                        "target": item.id,
                    }
                )
                rows.append(
                    {
                        "source": item.id,
                        "relation": "GROUNDED_BY",
                        "target": item.source_clause,
                    }
                )
    return rows
