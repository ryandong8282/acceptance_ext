from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .models import AcceptanceItem, ResultDocument


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha1(value.encode()).hexdigest()[:16]}"


def _load_ontology(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        path = Path(__file__).parent / "resources" / "50300_seed.json"
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    return raw if isinstance(raw, list) else raw.get("tree", [])


def _find_path(nodes: list[dict[str, Any]], names: list[str]) -> list[dict[str, Any]]:
    if not names:
        return []
    def walk(current: list[dict[str, Any]], depth: int, prefix: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for node in current:
            if str(node.get("name", "")).strip() != names[depth]:
                continue
            next_prefix = [*prefix, node]
            if depth == len(names) - 1:
                return next_prefix
            found = walk(node.get("children") or [], depth + 1, next_prefix)
            if found:
                return found
        return []
    return walk(nodes, 0, [])


def _fallback_path(names: list[str]) -> list[dict[str, Any]]:
    types = [(3, "分部", "单位"), (2, "子分部", "子分部"), (1, "分项", "分项")]
    out=[]; parent: int | str=0
    for i,name in enumerate(names[:3]):
        type_no,type_name,node_type=types[min(i,2)]
        node_id=_stable_id("ontology", "/".join(names[:i+1]))
        out.append({"id":node_id,"pid":parent,"name":name,"type":type_no,"type_name":type_name,"node_type":node_type,"children":[]})
        parent=node_id
    return out


def _item_payload(item: AcceptanceItem, parent_id: int | str, standard_no: str | None, standard_name: str | None) -> dict[str, Any]:
    first = item.evidence[0] if item.evidence else None
    verification = item.verification_sources or [e.model_dump() for e in item.evidence]
    return {
        "id": item.id,
        "pid": parent_id,
        "name": item.name,
        "type_name": item.type_name or "验收项目",
        "node_type": "验收项目",
        "standard_no": standard_no,
        "standard_name": standard_name,
        "chapter_no": item.chapter_no,
        "chapter_title": item.chapter_title,
        "source_page": item.source_page if item.source_page is not None else (first.page if first else None),
        "pdf_page": item.pdf_page if item.pdf_page is not None else (first.page if first else None),
        "markdown_line": item.markdown_line if item.markdown_line is not None else (first.line_start if first else None),
        "item_no": item.item_no,
        "item_category": item.item_category,
        "deviation_unit": item.deviation_unit,
        "deviation_value": item.deviation_value,
        "check_method": item.check_method,
        "table_no": item.table_no,
        "source_clause": item.source_clause,
        "source_quote": item.source_quote,
        "min_sampling": item.min_sampling,
        "min_sampling_reason": item.min_sampling_reason,
        "min_sampling_confidence": item.min_sampling_confidence,
        "min_sampling_script": item.min_sampling_script,
        "min_sampling_json": item.min_sampling_json,
        "min_sampling_rule": item.min_sampling_rule,
        "min_sampling_rule_guarded": item.min_sampling_rule_guarded,
        "params": item.params,
        "verification_sources": verification,
        "children": [],
    }


def pdfex_payload_exact(document: ResultDocument, ontology_path: Path | None = None) -> dict[str, Any]:
    ontology = _load_ontology(ontology_path)
    roots: dict[str, dict[str, Any]] = {}
    item_count=0
    for division in document.tree:
        names = division.mapped_50300_path or [division.name]
        path = _find_path(ontology, names) or _fallback_path(names)
        if not path:
            continue
        clones=[]
        for node in path:
            clone={k:deepcopy(v) for k,v in node.items() if k != "children"}
            clone.setdefault("id",_stable_id("ontology","/".join(names[:len(clones)+1])))
            clone.setdefault("pid",clones[-1]["id"] if clones else 0)
            clone.setdefault("type",max(1,3-len(clones)))
            clone.setdefault("type_name",("分部","子分部","分项")[min(len(clones),2)])
            clone.setdefault("node_type",("单位","子分部","分项")[min(len(clones),2)])
            clone["children"]=[]; clones.append(clone)
        root=roots.setdefault(str(clones[0]["id"]),clones[0])
        parent=root
        for clone in clones[1:]:
            existing=next((x for x in parent["children"] if x.get("id")==clone["id"]),None)
            if existing is None:
                parent["children"].append(clone); existing=clone
            parent=existing
        for lot in division.children:
            lot_node={
                "id":lot.id,"pid":parent["id"],"name":lot.name,"node_type":"检验批",
                "standard_no":document.standard_no,"standard_name":document.standard_name,
                "chapter_no":lot.chapter_no,"chapter_title":lot.chapter_title or lot.source_title,
                "source_page":lot.source_page,"pdf_page":lot.pdf_page or lot.source_page,
                "source_title":lot.source_title,"children":[],
            }
            for item in lot.children:
                lot_node["children"].append(_item_payload(item,lot.id,document.standard_no,document.standard_name)); item_count+=1
            parent["children"].append(lot_node)
    page_count=document.page_count
    if page_count is None:
        pages=[e.page for d in document.tree for l in d.children for i in l.children for e in i.evidence if e.page]
        page_count=max(pages) if pages else None
    return {
        "source_pdf":document.source_pdf,
        "standard_no":document.standard_no,
        "standard_name":document.standard_name,
        "extraction":{
            "mode":"acceptance_ext_v0.2_pdfex_exact",
            "chapter_count":len(document.chapters) or len(document.tree),
            "attached_chapter_count":sum(bool(d.mapped_50300_path) for d in document.tree),
            "has_division_item_table":False,
            "acceptance_item_count":item_count,
            **document.metrics,
        },
        "chapters":document.chapters,
        "tree":list(roots.values()),
        "page_count":page_count,
        "markdown_file":document.markdown_file,
    }
