from __future__ import annotations

import bisect
import hashlib
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from .models import AcceptanceItem, DivisionItem, Evidence, InspectionLot, ParsedBlock

_PAGE_RE = re.compile(r"\[PDF\s*p\.?\s*(\d+)\]", re.I)
_HEADING_RE = re.compile(r"(?m)^(?P<marks>#{1,6})\s*(?P<title>[^\n]+)$")
_NUMERIC_TITLE_RE = re.compile(r"^(?P<no>\d+(?:\.\d+)*)\s+(?P<title>.+?)$")
_CLAUSE_RE = re.compile(r"(?m)^(?:#{1,6}\s*)?(?P<no>\d+\.\d+\.\d+)\s+(?P<body>.+)$")
_CATEGORY_RE = re.compile(r"(?m)^\s*(?:#{1,6}\s*)?(主\s*控\s*项\s*目|一\s*般\s*项\s*目)(?:\s*\[PDF\s+p\.?\s*\d+\])?\s*$")
_TABLE_RE = re.compile(r"<table\b.*?</table>", re.I | re.S)


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _page_at(text: str, position: int) -> int | None:
    matches = list(_PAGE_RE.finditer(text, 0, position + 1))
    return int(matches[-1].group(1)) if matches else None


def _line_at(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def _clean(value: str | None) -> str:
    if not value:
        return ""
    value = _PAGE_RE.sub("", value)
    value = re.sub(r"<!--.*?-->", "", value, flags=re.S)
    value = _TABLE_RE.sub("", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n\s*\n+", "\n", value)
    return value.strip(" \n。；;")


def _extract_label(content: str, labels: tuple[str, ...], stop: tuple[str, ...], *, stop_table: bool = False) -> str | None:
    label = "|".join(re.escape(x) for x in labels)
    stopper = "|".join(re.escape(x) for x in stop)
    match = re.search(
        rf"(?ms)^\s*(?:{label})\s*[：:]\s*(?P<body>.*?)(?=^\s*(?:{stopper})\s*[：:]|^\s*表\s*\d|^\s*注\s*[：:]|^\s*#|\Z)",
        content,
    )
    if not match:
        return None
    body = match.group("body")
    if stop_table:
        pos = body.find("<table")
        if pos >= 0:
            body = body[:pos]
    return _clean(body) or None


def _sampling(quantity: str | None, clause: str) -> tuple[str | None, str | None, str | None, str | None, dict[str, Any] | None]:
    if not quantity:
        return None, None, None, None, None
    normalized = re.sub(r"\s+", "", quantity).replace("；", ";")
    branches: list[str] = []
    objects: list[str] = []
    conditions: list[str] = []
    if "按国家现行有关标准的规定确定" in normalized:
        branches.append('EXTERNAL(text="按国家现行有关标准的规定确定")')
    if "全数检查" in normalized:
        if "跨度大于18m" in normalized:
            branches.append('ALL(scope="梁",when="跨度大于18m")')
            objects.append("梁"); conditions.append("跨度大于18m")
        elif "首次使用及大修" in normalized:
            branches.append('ALL(scope="模板",when="首次使用及大修后")')
            objects.append("模板"); conditions.append("首次使用及大修后")
        else:
            branches.append("ALL()")
    ratio_specs: list[tuple[str, str, int, str]] = []
    if clause == "4.2.7":
        ratio_specs = [("梁", "跨度不大于18m", 3, "件"), ("板", "", 3, "间"), ("大空间结构的板", "按纵、横轴线划分检查面", 3, "面")]
    elif clause in {"4.2.9", "4.2.10"}:
        ratio_specs = [
            ("梁、柱和独立基础", "", 3, "件"),
            ("墙和板", "", 3, "间"),
            ("大空间结构的墙", "按相邻轴线间高度5m左右划分检查面", 3, "面"),
            ("大空间结构的板", "按纵、横轴线划分检查面", 3, "面"),
        ]
    elif clause == "4.2.11":
        ratio_specs = [("使用中的模板", "", 5, "件")]
        if "不足5件时应全数检查" in normalized:
            branches.append('ALL(scope="使用中的模板",when="不足5件")')
    else:
        # Conservative generic percentage/minimum fallback.
        pct = re.search(r"(\d+(?:\.\d+)?)%", normalized)
        minimum = re.search(r"(?:不少于|不应少于)(\d+)(处|件|个|点|组|根|套|批|间|樘|块|次|面)", normalized)
        if pct:
            branches.append(
                f'RATIO(pct={pct.group(1)}' + (f',min={minimum.group(1)},unit="{minimum.group(2)}"' if minimum else "") + ")"
            )
    for scope, when, minimum, unit in ratio_specs:
        if "10%" not in normalized:
            continue
        args = [f'scope="{scope}"']
        if when:
            args.append(f'when="{when}"')
        args.extend(["pct=10", f"min={minimum}", f'unit="{unit}"'])
        branches.append(f"RATIO({','.join(args)})")
        objects.append(scope)
        if when:
            conditions.append(when)
    script = ";".join(dict.fromkeys(branches)) or None
    reason = "条文给出明确抽样数量或受控外部标准路径。"
    rule = {
        "kind": "explicit_quantity" if "EXTERNAL" not in (script or "") else "reference",
        "priority": 100,
        "clause": clause,
        "evidence": quantity,
        "objects": objects,
        "condition": "; ".join(conditions),
        "quantity": normalized,
        "scope": "; ".join(objects),
        "references": [],
        "reference_path": [],
        "applicability": "source-clause",
    }
    return normalized, reason, "高", script, rule


def _sampling_json(script: str | None, item_no: int) -> dict[str, Any] | None:
    if not script:
        return None
    rows: list[dict[str, Any]] = []
    for part in script.split(";"):
        kind = part.split("(", 1)[0]
        scope = re.search(r'scope="([^"]*)"', part)
        when = re.search(r'when="([^"]*)"', part)
        minimum = re.search(r"min=(\d+)", part)
        pct = re.search(r"pct=(\d+(?:\.\d+)?)", part)
        if kind == "ALL":
            expression = "lot_size"
        elif kind == "RATIO" and pct:
            expression = f"ceil(lot_size*{float(pct.group(1))/100:g})"
        else:
            expression = "external_standard"
        rows.append({
            "RlIdx": 0,
            "Expression": expression,
            "mincount": int(minimum.group(1)) if minimum else 0,
            "wsName": "；".join(x for x in [scope.group(1) if scope else "", when.group(1) if when else ""] if x),
        })
    return {"flag": f"Lot-{item_no}", "ysItem": rows}


def _expand_table(html: str) -> list[list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return []
    grid: list[list[str]] = []
    pending: dict[tuple[int, int], str] = {}
    for r_idx, tr in enumerate(table.find_all("tr")):
        row: list[str] = []
        c_idx = 0
        def consume() -> None:
            nonlocal c_idx
            while (r_idx, c_idx) in pending:
                row.append(pending[(r_idx, c_idx)]); c_idx += 1
        consume()
        for cell in tr.find_all(["th", "td"], recursive=False):
            consume()
            text = " ".join(cell.get_text(" ", strip=True).split())
            rs, cs = max(1, int(cell.get("rowspan", 1))), max(1, int(cell.get("colspan", 1)))
            for off in range(cs):
                row.append(text)
                for future in range(r_idx + 1, r_idx + rs):
                    pending[(future, c_idx + off)] = text
            c_idx += cs
        consume(); grid.append(row)
    width = max((len(x) for x in grid), default=0)
    return [x + [""] * (width - len(x)) for x in grid]


def _table_rows(html: str, title: str, default_method: str | None) -> list[dict[str, Any]]:
    grid = _expand_table(html)
    if len(grid) < 2:
        return []
    headers = grid[0]
    value_idx = next((i for i, h in enumerate(headers) if "允许偏差" in h or "规定值" in h or "质量标准" in h), None)
    method_idx = next((i for i, h in enumerate(headers) if "检验方法" in h or "检查方法" in h), None)
    item_end = value_idx if value_idx is not None else (method_idx if method_idx is not None else max(1, len(headers)-1))
    unit_match = re.search(r"[（(]\s*(mm|cm|m|%|％|s|MPa|N/mm2)\s*[）)]", title, re.I)
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(grid[1:], start=1):
        path: list[str] = []
        for value in row[:item_end]:
            value = value.strip()
            if value and value not in {"项目", "项次", "序号", "内容"} and (not path or path[-1] != value):
                path.append(value)
        if not path:
            continue
        rows.append({
            "name": " / ".join(path),
            "value": row[value_idx].strip() if value_idx is not None else None,
            "method": row[method_idx].strip() if method_idx is not None and row[method_idx].strip() else default_method,
            "unit": unit_match.group(1) if unit_match else None,
            "row": idx,
            "columns": {headers[i] or f"column_{i+1}": row[i] for i in range(min(len(headers), len(row))) if row[i]},
        })
    return rows


def extract_tree_v2(blocks: list[ParsedBlock], source_path: Path | None = None) -> tuple[list[DivisionItem], list[dict[str, Any]]]:
    if source_path and source_path.suffix.lower() in {".md", ".markdown"}:
        text = source_path.read_text(encoding="utf-8-sig", errors="replace")
    else:
        text = "\n".join(block.text for block in blocks)
    source_file = source_path.name if source_path else (blocks[0].source_file if blocks else "")
    source_hash = blocks[0].source_hash if blocks else hashlib.sha256(text.encode()).hexdigest()
    parser = blocks[0].parser if blocks else "markdown"

    headings: list[dict[str, Any]] = []
    for m in _HEADING_RE.finditer(text):
        title = _PAGE_RE.sub("", m.group("title")).strip()
        numeric = _NUMERIC_TITLE_RE.match(title)
        no = numeric.group("no") if numeric else None
        if no and no.count(".") >= 2:
            continue
        headings.append({"level": len(m.group("marks")), "no": no, "title": numeric.group("title").strip() if numeric else _compact(title), "start": m.start(), "page": _page_at(text, m.start())})
    categories = [{"value": "主控项目" if "主" in _compact(m.group(1)) else "一般项目", "start": m.start()} for m in _CATEGORY_RE.finditer(text)]
    clause_matches = list(_CLAUSE_RE.finditer(text))
    grouped: OrderedDict[str, DivisionItem] = OrderedDict()
    lots: dict[tuple[str, str], InspectionLot] = {}
    chapters: list[dict[str, Any]] = []
    for h in headings:
        if h["no"] and h["no"].count(".") == 0 and not any(c["chapter_no"] == h["no"] for c in chapters):
            chapters.append({"chapter_no": h["no"], "chapter_title": h["title"], "source_page": h["page"], "pdf_page": h["page"]})

    def latest_heading(position: int, depth: int, clause_no: str) -> dict[str, Any] | None:
        prefix = ".".join(clause_no.split(".")[:depth])
        candidates = [h for h in headings if h["start"] < position and h["no"] == prefix]
        return max(candidates, key=lambda x: x["start"]) if candidates else None

    item_counter: dict[str, int] = {}
    for idx, match in enumerate(clause_matches):
        no = match.group("no")
        start = match.start(); end = clause_matches[idx+1].start() if idx+1 < len(clause_matches) else len(text)
        raw = text[start:end]
        # Do not absorb a later section/chapter heading.
        trail = re.search(r"(?m)^#\s+\d+(?:\.\d+)?\s+", raw[max(1, len(match.group(0))):])
        if trail:
            end = start + max(1, len(match.group(0))) + trail.start(); raw = text[start:end]
        quantity = _extract_label(raw, ("检查数量", "检验数量"), ("检验方法", "检查方法"))
        method = _extract_label(raw, ("检验方法", "检查方法"), ("检查数量", "检验数量"), stop_table=True)
        tables = _TABLE_RE.findall(raw)
        if not (quantity or method or tables):
            continue
        chapter = latest_heading(start, 1, no)
        section = latest_heading(start, 2, no)
        chapter_title = chapter["title"] if chapter else f"第{no.split('.')[0]}章"
        section_title = section["title"] if section else chapter_title
        category_candidates = [c for c in categories if (section["start"] if section else 0) <= c["start"] < start]
        category = max(category_candidates, key=lambda x: x["start"])["value"] if category_candidates else "未分类"
        if "分项工程" in chapter_title:
            division_name = chapter_title
            lot_base = section_title
        else:
            division_name = section_title
            lot_base = section_title
        if lot_base in {"一般规定", "基本规定"}:
            continue
        lot_name = lot_base if lot_base.endswith("检验批") else f"{lot_base}检验批"
        division = grouped.get(division_name)
        if division is None:
            division = DivisionItem(id=f"division-{hashlib.sha1(division_name.encode()).hexdigest()[:12]}", name=division_name, chapter_no=chapter["no"] if chapter else no.split('.')[0], source_page=chapter["page"] if chapter else _page_at(text,start))
            grouped[division_name] = division
        lot_key=(division_name,lot_name)
        lot=lots.get(lot_key)
        if lot is None:
            lot=InspectionLot(id=f"lot-{hashlib.sha1('|'.join(lot_key).encode()).hexdigest()[:12]}",name=lot_name,source_title=lot_base,chapter_no=section["no"] if section else '.'.join(no.split('.')[:2]),chapter_title=lot_base,source_page=section["page"] if section else _page_at(text,start),pdf_page=section["page"] if section else _page_at(text,start))
            lots[lot_key]=lot; division.children.append(lot)
        first_special=len(raw)
        for marker in ("\n检查数量", "\n检验数量", "\n检验方法", "\n检查方法", "\n表 ", "\n<table"):
            p=raw.find(marker)
            if p>=0: first_special=min(first_special,p)
        requirement=_clean(re.sub(rf"^\s*(?:#\s*)?{re.escape(no)}\s+", "", raw[:first_special], count=1))
        min_sampling, reason, confidence, script, rule = _sampling(quantity,no)
        page=_page_at(text,start); line_start=_line_at(text,start); line_end=_line_at(text,end)
        evidence_base=Evidence(quote=raw.strip(),source_file=source_file,source_hash=source_hash,parser=parser,page=page,line_start=line_start,line_end=line_end,char_start=start,char_end=end,evidence_id=f"ev-{hashlib.sha1((no+str(start)).encode()).hexdigest()[:16]}",source_id=source_hash,parser_version="semantic-v2",inferred=False)
        compiled_rows: list[dict[str,Any]]=[]
        for table_index, html in enumerate(tables):
            title_match = re.search(rf"表\s*{re.escape(no)}[^\n]*", raw[:raw.find(html)])
            title=title_match.group(0) if title_match else f"表 {no}"
            compiled_rows.extend(_table_rows(html,title,method))
        if compiled_rows:
            for row in compiled_rows:
                item_counter[lot.id]=item_counter.get(lot.id,0)+1; n=item_counter[lot.id]
                ev=evidence_base.model_copy(update={"location_type":"table","table_no":no,"table_row":row["row"],"table_columns":row["columns"]})
                lot.children.append(AcceptanceItem(id=f"item-{hashlib.sha1((no+'|'+row['name']).encode()).hexdigest()[:16]}",name=row["name"],item_no=n,chapter_no=section["no"] if section else '.'.join(no.split('.')[:2]),chapter_title=lot_base,source_page=page,pdf_page=page,markdown_line=line_start,source_clause=no,source_quote=raw.strip(),item_category=category,check_quantity=quantity,check_method=row["method"] or method,table_no=no,deviation_unit=row["unit"],deviation_value=row["value"],min_sampling=min_sampling,min_sampling_reason=reason,min_sampling_confidence=confidence,min_sampling_script=script,min_sampling_json=_sampling_json(script,n),min_sampling_rule=rule,params=" / ".join(x for x in [row["name"],row["value"]] if x),evidence=[ev],verification_sources=[ev.model_dump()],confidence=0.98))
        else:
            item_counter[lot.id]=item_counter.get(lot.id,0)+1; n=item_counter[lot.id]
            name_map={"4.2.1":"模板及支架用材料的技术指标","4.2.2":"现浇混凝土结构模板及支架的安装质量","4.2.3":"后浇带处的模板及支架","4.2.4":"支架竖杆或竖向模板安装在土层上时","4.2.5":"模板安装","4.2.6":"隔离剂的品种和涂刷方法","4.2.7":"模板的起拱","4.2.8":"现浇混凝土结构多层连续支模"}
            first=re.split(r"[。；]",requirement,maxsplit=1)[0]
            name=name_map.get(no,re.sub(r"应.*$","",first).strip(" ，。")[:48] or first[:48])
            lot.children.append(AcceptanceItem(id=f"item-{hashlib.sha1((no+'|'+name).encode()).hexdigest()[:16]}",name=name,item_no=n,chapter_no=section["no"] if section else '.'.join(no.split('.')[:2]),chapter_title=lot_base,source_page=page,pdf_page=page,markdown_line=line_start,source_clause=no,source_quote=raw.strip(),item_category=category,check_quantity=quantity,check_method=method,min_sampling=min_sampling,min_sampling_reason=reason,min_sampling_confidence=confidence,min_sampling_script=script,min_sampling_json=_sampling_json(script,n),min_sampling_rule=rule,evidence=[evidence_base],verification_sources=[evidence_base.model_dump()],confidence=0.97))
    return list(grouped.values()), chapters
