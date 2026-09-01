from __future__ import annotations

import html
import json
from pathlib import Path

from .models import ResultDocument


def write_json(document: ResultDocument, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document.model_dump_json(indent=2), encoding="utf-8")


def pdfex_payload(document: ResultDocument) -> dict:
    tree: list[dict] = []
    next_id = 1
    for division in document.tree:
        division_id = next_id
        next_id += 1
        division_node = {
            "id": division_id,
            "pid": 0,
            "name": division.name,
            "type": 1,
            "type_name": "分项",
            "node_type": "分项",
            "mapped_50300_path": division.mapped_50300_path,
            "children": [],
        }
        for lot in division.children:
            lot_id = next_id
            next_id += 1
            lot_node = {
                "id": lot_id,
                "pid": division_id,
                "name": lot.name,
                "node_type": "检验批",
                "source_title": lot.source_title,
                "chapter_no": lot.chapter_no,
                "children": [],
            }
            for item in lot.children:
                item_id = next_id
                next_id += 1
                first_evidence = item.evidence[0] if item.evidence else None
                lot_node["children"].append(
                    {
                        "id": item_id,
                        "pid": lot_id,
                        "name": item.name,
                        "node_type": "验收项目",
                        "source_clause": item.source_clause,
                        "source_quote": item.source_quote,
                        "item_category": item.item_category,
                        "check_method": item.check_method,
                        "min_sampling": item.min_sampling,
                        "min_sampling_reason": item.min_sampling_reason,
                        "min_sampling_confidence": item.min_sampling_confidence,
                        "params": item.params,
                        "source_page": first_evidence.page if first_evidence else None,
                        "pdf_page": first_evidence.page if first_evidence else None,
                        "markdown_line": first_evidence.line_start if first_evidence else None,
                        "verification_sources": [e.model_dump() for e in item.evidence],
                        "children": [],
                    }
                )
            division_node["children"].append(lot_node)
        tree.append(division_node)
    return {
        "source_pdf": document.source_pdf,
        "standard_no": document.standard_no,
        "standard_name": document.standard_name,
        "extraction": {"mode": "acceptance_ext_v0.1", **document.metrics},
        "tree": tree,
        "audit": [finding.model_dump() for finding in document.audit],
    }


def write_pdfex(document: ResultDocument, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(pdfex_payload(document), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def write_review_html(document: ResultDocument, path: Path) -> None:
    rows: list[str] = []
    for division in document.tree:
        for lot in division.children:
            for item in lot.children:
                evidence = item.evidence[0] if item.evidence else None
                location = ""
                if evidence:
                    location = f"p.{evidence.page or '-'} / line {evidence.line_start or '-'}"
                rows.append(
                    "<tr>"
                    f"<td>{html.escape(division.name)}</td>"
                    f"<td>{html.escape(lot.name)}</td>"
                    f"<td>{html.escape(item.item_category)}</td>"
                    f"<td>{html.escape(item.source_clause or '')}</td>"
                    f"<td>{html.escape(item.name)}</td>"
                    f"<td>{html.escape(item.min_sampling or '')}</td>"
                    f"<td><mark>{html.escape(item.source_quote)}</mark>"
                    f"<small>{html.escape(location)}</small></td>"
                    "</tr>"
                )
    page = f"""<!doctype html><html lang='zh-CN'><meta charset='utf-8'>
<title>Acceptance Ext Review</title><style>
body{{font:14px/1.55 system-ui;margin:24px;color:#17202a}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccd1d1;padding:8px;vertical-align:top}}th{{position:sticky;top:0;background:#f4f6f6}}
mark{{background:#fff2a8}}small{{display:block;color:#5d6d7e;margin-top:4px}}
</style><h1>{html.escape(document.standard_no or '')} {html.escape(document.standard_name or '')}</h1>
<p>{html.escape(document.source_pdf)} · items={document.metrics.get('acceptance_item_count', 0)} · grounding={document.metrics.get('grounding_rate', 0)}</p>
<table><thead><tr><th>分项</th><th>检验批</th><th>类别</th><th>条文</th><th>项目</th><th>抽样</th><th>原文证据</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
