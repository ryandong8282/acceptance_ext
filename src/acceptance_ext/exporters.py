from __future__ import annotations

import html
import json
from pathlib import Path

from .models import ResultDocument
from .pdfex_contract import pdfex_payload_exact


def write_json(document: ResultDocument, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document.model_dump_json(indent=2), encoding="utf-8")


def pdfex_payload(document: ResultDocument, ontology_path: Path | None = None) -> dict:
    """Emit the actual PDFex ResultDocument/ResultNode contract, including the 50300 path."""
    return pdfex_payload_exact(document, ontology_path)


def write_pdfex(document: ResultDocument, path: Path, ontology_path: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pdfex_payload(document, ontology_path), ensure_ascii=False, indent=2), encoding="utf-8")


def write_review_html(document: ResultDocument, path: Path) -> None:
    rows: list[str] = []
    for division in document.tree:
        for lot in division.children:
            for item in lot.children:
                evidence = item.evidence[0] if item.evidence else None
                location = f"p.{evidence.page or '-'} / line {evidence.line_start or '-'}" if evidence else ""
                rows.append("<tr>" + f"<td>{html.escape(division.name)}</td><td>{html.escape(lot.name)}</td>" + f"<td>{html.escape(item.item_category)}</td><td>{html.escape(item.source_clause or '')}</td>" + f"<td>{html.escape(item.name)}</td><td>{html.escape(item.min_sampling or '')}</td>" + f"<td><mark>{html.escape(item.source_quote)}</mark><small>{html.escape(location)}</small></td></tr>")
    page = f"""<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>Acceptance Ext Review</title><style>body{{font:14px/1.55 system-ui;margin:24px;color:#17202a}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccd1d1;padding:8px;vertical-align:top}}th{{position:sticky;top:0;background:#f4f6f6}}mark{{background:#fff2a8}}small{{display:block;color:#5d6d7e;margin-top:4px}}</style><h1>{html.escape(document.standard_no or '')} {html.escape(document.standard_name or '')}</h1><p>{html.escape(document.source_pdf)} · items={document.metrics.get('acceptance_item_count', 0)}</p><table><thead><tr><th>分项</th><th>检验批</th><th>类别</th><th>条文</th><th>项目</th><th>抽样</th><th>原文证据</th></tr></thead><tbody>{''.join(rows)}</tbody></table></html>"""
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(page, encoding="utf-8")
