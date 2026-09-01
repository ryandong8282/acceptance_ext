from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .models import AcceptanceItem, DivisionItem, Evidence, InspectionLot, ParsedBlock

_HEADING_RE = re.compile(r"^\s*#{1,6}\s*(?:(\d+(?:\.\d+)*)\s*)?(.+?)\s*$")
_PLAIN_HEADING_RE = re.compile(r"^\s*(\d+(?:\.\d+){0,2})\s+([^。；;]{2,60})\s*$")
_CLAUSE_RE = re.compile(r"^\s*(\d+(?:\.\d+){1,5})\s+(.+)$", re.S)
_STANDARD_RE = re.compile(r"\b(GB(?:/T|／T)?\s*\d{5}(?:\.\d+)?[-—－]\d{4})\b", re.I)
_MODAL_RE = re.compile(r"应当|必须|严禁|不得|不应|应|宜|可")
_SAMPLING_PATTERNS = [
    re.compile(r"(?:抽查|抽检|检查|检验)[^。；;]{0,36}?(\d+(?:\.\d+)?\s*%)(?:[^。；;]{0,24})"),
    re.compile(r"(不少于\s*\d+\s*(?:处|件|个|点|组|根|套|批|间|樘|块|次))"),
    re.compile(r"(不应少于\s*\d+\s*(?:处|件|个|点|组|根|套|批|间|樘|块|次))"),
    re.compile(r"(每\s*\d+\s*(?:m²|m2|㎡|米|件|个|处|间|批)[^。；;]{0,28}?(?:抽查|检查|检验)[^。；;]{0,20})"),
    re.compile(r"(全数(?:检查|检验|观察)?)"),
]
_CHECK_RE = re.compile(r"(?:检查方法|检验方法|检查数量)\s*[：:]\s*([^。；;]+)")


def normalize(text: str) -> str:
    return re.sub(r"[\s，。；：、（）()【】\[\]《》<>·—－_-]+", "", text).lower()


def item_name(body: str) -> str:
    body = re.split(r"(?:检查方法|检验方法|检查数量)\s*[：:]", body)[0]
    first = re.split(r"[。；;]", body, maxsplit=1)[0].strip()
    first = _MODAL_RE.sub("", first)
    first = re.sub(r"^(?:其|该|本|对)", "", first).strip(" ，。：；")
    if len(first) > 48:
        first = first[:48].rstrip(" ，、")
    return first or body[:32].strip()


def sampling_rule(text: str) -> tuple[str | None, str | None, str | None]:
    for pattern in _SAMPLING_PATTERNS:
        match = pattern.search(text)
        if match:
            value = match.group(1).strip()
            return value, f"条文中存在明确抽样数量：{value}", "高"
    return None, None, None


def check_method(text: str) -> str | None:
    match = _CHECK_RE.search(text)
    return match.group(1).strip() if match else None


def is_acceptance_clause(text: str) -> bool:
    return bool(
        re.search(r"应|必须|不得|严禁|符合.*规定|验收|检查|检验|允许偏差", text)
        and len(text) >= 8
    )


def category_from_headings(headings: list[str]) -> str:
    joined = " / ".join(headings[-3:])
    if "主控项目" in joined:
        return "主控项目"
    if "一般项目" in joined:
        return "一般项目"
    return "未分类"


def evidence_from(block: ParsedBlock, quote: str) -> Evidence:
    local = block.text.find(quote)
    char_start = block.char_start + local if block.char_start is not None and local >= 0 else block.char_start
    char_end = char_start + len(quote) if char_start is not None else block.char_end
    return Evidence(
        quote=quote,
        source_file=block.source_file,
        source_hash=block.source_hash,
        parser=block.parser,
        page=block.page,
        bbox=block.bbox,
        line_start=block.line_start,
        line_end=block.line_end,
        char_start=char_start,
        char_end=char_end,
    )


def load_task_spec(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def extract_tree(blocks: list[ParsedBlock], task_spec: dict[str, Any] | None = None) -> list[DivisionItem]:
    del task_spec
    headings: list[tuple[int, str, str | None]] = []
    grouped: dict[tuple[str, str | None], list[AcceptanceItem]] = defaultdict(list)

    for block in blocks:
        for raw_line in block.text.splitlines():
            line = raw_line.strip()
            heading = _HEADING_RE.match(line)
            if heading:
                level = len(line) - len(line.lstrip("#"))
                title = heading.group(2).strip()
                headings[:] = [entry for entry in headings if entry[0] < level]
                headings.append((level, title, heading.group(1)))
                continue
            plain_heading = _PLAIN_HEADING_RE.match(line)
            if plain_heading and not _CLAUSE_RE.match(line):
                headings[:] = [entry for entry in headings if entry[0] < 2]
                headings.append((2, plain_heading.group(2).strip(), plain_heading.group(1)))
                continue
            clause = _CLAUSE_RE.match(line)
            if not clause:
                continue
            clause_no, body = clause.group(1), clause.group(2).strip()
            quote = f"{clause_no} {body}".strip()
            if not is_acceptance_clause(body):
                continue
            heading_titles = [entry[1] for entry in headings]
            meaningful = [
                entry
                for entry in headings
                if entry[1] not in {"主控项目", "一般项目", "基本规定", "一般规定"}
            ]
            division_title = meaningful[-1][1] if meaningful else f"第{clause_no.split('.')[0]}章"
            chapter_no = meaningful[-1][2] if meaningful else clause_no.split(".")[0]
            sampling, reason, confidence = sampling_rule(body)
            stable = hashlib.sha1(f"{clause_no}|{normalize(body)}".encode()).hexdigest()[:12]
            grouped[(division_title, chapter_no)].append(
                AcceptanceItem(
                    id=f"item-{stable}",
                    name=item_name(body),
                    source_clause=clause_no,
                    source_quote=quote,
                    item_category=category_from_headings(heading_titles),
                    check_method=check_method(body),
                    min_sampling=sampling,
                    min_sampling_reason=reason,
                    min_sampling_confidence=confidence,
                    evidence=[evidence_from(block, quote if quote in block.text else line)],
                    confidence=0.85 if category_from_headings(heading_titles) != "未分类" else 0.72,
                )
            )

    tree: list[DivisionItem] = []
    for index, ((title, chapter_no), items) in enumerate(grouped.items(), start=1):
        lot = InspectionLot(
            id=f"lot-{index}",
            name=f"{title}检验批",
            source_title=title,
            chapter_no=chapter_no,
            children=items,
        )
        tree.append(
            DivisionItem(
                id=f"division-{index}",
                name=title,
                chapter_no=chapter_no,
                children=[lot],
            )
        )
    return tree


def load_ontology(path: Path | None) -> list[tuple[list[str], str]]:
    if path is None or not path.exists():
        path = Path(__file__).parent / "resources" / "50300_seed.json"
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    candidates: list[tuple[list[str], str]] = []

    def walk(nodes: list[dict[str, Any]], prefix: list[str]) -> None:
        for node in nodes:
            name = str(node.get("name", "")).strip()
            current = [*prefix, name] if name else prefix
            if node.get("node_type") == "分项" or node.get("type_name") == "分项":
                candidates.append((current, name))
            children = node.get("children") or []
            if isinstance(children, list):
                walk(children, current)

    walk(raw if isinstance(raw, list) else raw.get("tree", []), [])
    return candidates


def attach_ontology(tree: list[DivisionItem], ontology_path: Path | None) -> None:
    candidates = load_ontology(ontology_path)
    for division in tree:
        best_path: list[str] = []
        best_score = 0.0
        source = normalize(division.name)
        for path, name in candidates:
            target = normalize(name)
            score = SequenceMatcher(None, source, target).ratio()
            if source and target and (source in target or target in source):
                score = max(score, 0.92)
            if score > best_score:
                best_path, best_score = path, score
        if best_score >= 0.42:
            division.mapped_50300_path = best_path
            division.mapping_score = round(best_score, 4)


def infer_standard(blocks: list[ParsedBlock], filename: str) -> tuple[str | None, str | None]:
    preview = "\n".join(block.text for block in blocks[:60])
    match = _STANDARD_RE.search(f"{filename}\n{preview}")
    standard_no = re.sub(r"\s+", " ", match.group(1)).replace("／", "/") if match else None
    title_match = re.search(r"([^\n#]{2,40}(?:施工质量验收规范|工程验收规范|施工规范))", preview)
    return standard_no, title_match.group(1).strip() if title_match else None
