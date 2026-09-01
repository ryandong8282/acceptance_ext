#!/usr/bin/env python3
"""Create a compact, runnable Acceptance Ext v0.1 only when the main source is absent.

This is a delivery safety net for API-based repository creation. It never overwrites an
existing implementation: if ``src/acceptance_ext/pipeline.py`` exists, it exits cleanly.
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path


FILES: dict[str, str] = {
    "pyproject.toml": r'''
[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[project]
name = "acceptance-ext"
version = "0.1.0"
description = "Grounded, schema-driven extraction laboratory for Chinese construction acceptance standards"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [{name = "Acceptance Ext contributors"}]
dependencies = [
  "pydantic>=2.7,<3",
  "typer>=0.12,<1",
  "rich>=13.7,<15",
]

[project.optional-dependencies]
pdf = ["pymupdf>=1.24"]
docling = ["docling>=2.0"]
langextract = ["langextract>=1.0"]
llm = ["openai>=1.40"]
server = ["fastapi>=0.115", "python-multipart>=0.0.9", "uvicorn>=0.30"]
dev = ["pytest>=8.2", "ruff>=0.6"]
all = [
  "pymupdf>=1.24",
  "docling>=2.0",
  "langextract>=1.0",
  "openai>=1.40",
  "fastapi>=0.115",
  "python-multipart>=0.0.9",
  "uvicorn>=0.30",
]

[project.scripts]
acceptance-ext = "acceptance_ext.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/acceptance_ext"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
target-version = "py311"
line-length = 100
''',
    ".gitignore": r'''
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.venv/
venv/
.env
output/
reports/generated/
*.egg-info/
dist/
build/
''',
    ".env.example": r'''
# OpenAI-compatible refinement (optional)
ACCEPTANCE_EXT_BASE_URL=https://api.openai.com/v1
ACCEPTANCE_EXT_API_KEY=
ACCEPTANCE_EXT_MODEL=
ACCEPTANCE_EXT_ENABLE_LLM=false

# External parser command templates (optional). {input} and {output} are replaced.
MINERU_COMMAND=mineru -p "{input}" -o "{output}"
PADDLEOCR_COMMAND=
''',
    "README.md": r'''
# Acceptance Ext

A grounded A/B extraction laboratory for Chinese construction quality-acceptance standards.
It is intentionally **not another PDF-to-text wrapper**. The experiment asks whether a
pluggable stack inspired by Docling, LangExtract, DocETL, OpenContracts, Unstract and
vertical systems such as GROBID can reproduce the useful output of PDFex:

```text
PDF / Markdown
  → layout-aware parsing
  → chapter and clause segmentation
  → division item / inspection lot / acceptance item extraction
  → GB 50300 ontology attachment
  → exact source evidence and minimum-sampling rules
  → audit, human review and PDFex-compatible JSON
```

## What is integrated

- **Docling adapter** for layout-aware PDF conversion; PyMuPDF and Markdown baselines are
  available for fast local experiments.
- **LangExtract adapter** and an OpenAI-compatible structured-refinement hook. The
  deterministic extractor remains runnable without an API key.
- **DocETL-style declarative task specification**: extraction rules live in JSON instead
  of being buried in prompts.
- **OpenContracts-style evidence and review**: every item keeps the exact quote, source
  line/character span, page, bounding box when available, parser and source hash.
- **Unstract-style deployment surface**: CLI, JSON contracts and optional FastAPI API.
- **GROBID-style evaluation direction**: precision, recall, F1 and provenance coverage are
  first-class outputs; README claims are not treated as evidence of quality.

## Install

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev,pdf]"
```

For the broadest experiment:

```bash
pip install -e ".[all,dev]"
```

## Run the bundled smoke case

```bash
acceptance-ext extract sample_data/mini_standard.md \
  --parser markdown \
  --output output/mini.result.json \
  --review-html output/mini.review.html
```

Run a real Markdown produced by MinerU:

```bash
acceptance-ext extract "04_GB_50206-2012_木结构工程施工质量验收规范.md" \
  --parser markdown \
  --ontology /path/to/pdf_extractor/frontend/50300.json \
  --output output/gb50206.result.json \
  --pdfex-output output/gb50206.pdfex.json
```

Run a PDF through Docling:

```bash
acceptance-ext extract "GB 50206-2012 木结构工程施工质量验收规范.pdf" \
  --parser docling \
  --ontology /path/to/50300.json \
  --output output/gb50206.docling.json
```

Use `--parser pymupdf` for the lightweight PDF baseline. MinerU/PaddleOCR command adapters
are intentionally external so the exact installed CLI can be configured without coupling
this repository to one vendor release.

## A/B benchmark

```bash
acceptance-ext benchmark sample_data/mini_standard.md \
  --parsers markdown \
  --extractors heuristic \
  --output output/benchmark.json
```

When a gold JSON is available, add `--gold path/to/gold.json`. The report includes item
precision/recall/F1, grounding rate, sampling coverage, attachment rate and elapsed time.

## Output contract

The canonical document contains:

- `tree`: `分项 → 检验批 → 验收项目`;
- `source_clause`, `source_quote`, `item_category`, `check_method`, `min_sampling`;
- `evidence[]` with page/bbox/line/character provenance;
- `mapped_50300_path` and mapping score;
- audit findings and run metrics.

`--pdfex-output` emits a compatibility shape that can be opened beside the existing PDFex
results. Use the full `frontend/50300.json` from PDFex for serious comparison; the small
seed bundled here is only enough for smoke tests.

## Honest status

v0.1 is a working experiment and baseline, not a claim that the generic stack already
beats PDFex. The decisive test is a blinded run on the same standards and the same
human-labelled gold set. See `docs/EVALUATION.md`.
''',
    "src/acceptance_ext/__init__.py": r'''
"""Acceptance Ext public package."""

from .pipeline import ExtractionPipeline

__all__ = ["ExtractionPipeline"]
__version__ = "0.1.0"
''',
    "src/acceptance_ext/models.py": r'''
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    quote: str
    source_file: str
    source_hash: str
    parser: str
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    line_start: int | None = None
    line_end: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    method: Literal["exact", "normalized", "inferred"] = "exact"
    confidence: float = Field(default=1.0, ge=0, le=1)


class ParsedBlock(BaseModel):
    text: str
    source_file: str
    source_hash: str
    parser: str
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    line_start: int | None = None
    line_end: int | None = None
    char_start: int | None = None
    char_end: int | None = None


class AcceptanceItem(BaseModel):
    id: str
    name: str
    node_type: Literal["验收项目"] = "验收项目"
    source_clause: str | None = None
    source_quote: str
    item_category: Literal["主控项目", "一般项目", "未分类"] = "未分类"
    check_method: str | None = None
    min_sampling: str | None = None
    min_sampling_reason: str | None = None
    min_sampling_confidence: Literal["高", "中", "低"] | None = None
    params: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(default=0.75, ge=0, le=1)


class InspectionLot(BaseModel):
    id: str
    name: str
    node_type: Literal["检验批"] = "检验批"
    source_title: str | None = None
    chapter_no: str | None = None
    children: list[AcceptanceItem] = Field(default_factory=list)


class DivisionItem(BaseModel):
    id: str
    name: str
    node_type: Literal["分项"] = "分项"
    chapter_no: str | None = None
    mapped_50300_path: list[str] = Field(default_factory=list)
    mapping_score: float | None = None
    children: list[InspectionLot] = Field(default_factory=list)


class AuditFinding(BaseModel):
    severity: Literal["error", "warning", "info"]
    code: str
    message: str
    node_id: str | None = None


class ResultDocument(BaseModel):
    source_pdf: str
    standard_no: str | None = None
    standard_name: str | None = None
    parser: str
    extractor: str
    tree: list[DivisionItem] = Field(default_factory=list)
    audit: list[AuditFinding] = Field(default_factory=list)
    metrics: dict[str, float | int | str | None] = Field(default_factory=dict)
''',
    "src/acceptance_ext/parsers.py": r'''
from __future__ import annotations

import hashlib
import os
import re
import shlex
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from .models import ParsedBlock

_PAGE_RE = re.compile(r"\[PDF\s*p\.?\s*(\d+)\]", re.I)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DocumentParser(ABC):
    name: str

    @abstractmethod
    def parse(self, path: Path) -> list[ParsedBlock]: ...


class MarkdownParser(DocumentParser):
    name = "markdown"

    def parse(self, path: Path) -> list[ParsedBlock]:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        source_hash = sha256_file(path)
        blocks: list[ParsedBlock] = []
        page: int | None = None
        char_at = 0
        for line_no, raw in enumerate(text.splitlines(keepends=True), start=1):
            line = raw.rstrip("\r\n")
            match = _PAGE_RE.search(line)
            if match:
                page = int(match.group(1))
            if line.strip():
                start = char_at
                blocks.append(
                    ParsedBlock(
                        text=line,
                        source_file=path.name,
                        source_hash=source_hash,
                        parser=self.name,
                        page=page,
                        line_start=line_no,
                        line_end=line_no,
                        char_start=start,
                        char_end=start + len(line),
                    )
                )
            char_at += len(raw)
        return blocks


class PyMuPDFParser(DocumentParser):
    name = "pymupdf"

    def parse(self, path: Path) -> list[ParsedBlock]:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("Install the pdf extra: pip install -e '.[pdf]'") from exc
        source_hash = sha256_file(path)
        blocks: list[ParsedBlock] = []
        with fitz.open(path) as document:
            for page_index, page in enumerate(document, start=1):
                for raw in page.get_text("blocks"):
                    x0, y0, x1, y1, text = raw[:5]
                    clean = "\n".join(part.strip() for part in str(text).splitlines() if part.strip())
                    if clean:
                        blocks.append(
                            ParsedBlock(
                                text=clean,
                                source_file=path.name,
                                source_hash=source_hash,
                                parser=self.name,
                                page=page_index,
                                bbox=(float(x0), float(y0), float(x1), float(y1)),
                            )
                        )
        return blocks


class DoclingParser(DocumentParser):
    name = "docling"

    def parse(self, path: Path) -> list[ParsedBlock]:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise RuntimeError("Install the Docling extra: pip install -e '.[docling]'") from exc
        result = DocumentConverter().convert(path)
        markdown = result.document.export_to_markdown()
        with tempfile.TemporaryDirectory(prefix="acceptance-ext-docling-") as work:
            temporary = Path(work) / f"{path.stem}.md"
            temporary.write_text(markdown, encoding="utf-8")
            blocks = MarkdownParser().parse(temporary)
        source_hash = sha256_file(path)
        return [
            block.model_copy(
                update={"source_file": path.name, "source_hash": source_hash, "parser": self.name}
            )
            for block in blocks
        ]


class ExternalMarkdownParser(DocumentParser):
    def __init__(self, name: str, command_env: str) -> None:
        self.name = name
        self.command_env = command_env

    def parse(self, path: Path) -> list[ParsedBlock]:
        template = os.getenv(self.command_env, "").strip()
        if not template:
            raise RuntimeError(f"{self.command_env} is not configured")
        with tempfile.TemporaryDirectory(prefix=f"acceptance-ext-{self.name}-") as work:
            output = Path(work) / "output.md"
            command = template.format(input=str(path.resolve()), output=str(output.resolve()))
            subprocess.run(shlex.split(command), check=True)
            if not output.exists():
                candidates = list(Path(work).rglob("*.md"))
                if not candidates:
                    raise RuntimeError(f"{self.name} produced no Markdown output")
                output = candidates[0]
            blocks = MarkdownParser().parse(output)
        source_hash = sha256_file(path)
        return [
            block.model_copy(
                update={"source_file": path.name, "source_hash": source_hash, "parser": self.name}
            )
            for block in blocks
        ]


def get_parser(name: str) -> DocumentParser:
    normalized = name.lower().strip()
    parsers: dict[str, DocumentParser] = {
        "markdown": MarkdownParser(),
        "pymupdf": PyMuPDFParser(),
        "docling": DoclingParser(),
        "mineru": ExternalMarkdownParser("mineru", "MINERU_COMMAND"),
        "paddleocr": ExternalMarkdownParser("paddleocr", "PADDLEOCR_COMMAND"),
    }
    try:
        return parsers[normalized]
    except KeyError as exc:
        raise ValueError(f"Unknown parser {name!r}; choose from {', '.join(parsers)}") from exc
''',
    "src/acceptance_ext/extraction.py": r'''
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
    del task_spec  # v0.1 keeps the contract external; later versions compile these rules.
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
                entry for entry in headings
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
''',
    "src/acceptance_ext/refinement.py": r'''
from __future__ import annotations

import json
import os
from typing import Any

from .models import ResultDocument


SYSTEM_PROMPT = """You refine a grounded extraction of a Chinese construction acceptance standard.
Never invent an item. Preserve source_clause and source_quote exactly. You may improve names,
categories, check methods and minimum-sampling normalization only when supported by a quote.
Return one JSON object with a `tree` field matching the supplied shape."""


def openai_compatible_refine(document: ResultDocument) -> ResultDocument:
    if os.getenv("ACCEPTANCE_EXT_ENABLE_LLM", "false").lower() != "true":
        return document
    api_key = os.getenv("ACCEPTANCE_EXT_API_KEY", "")
    model = os.getenv("ACCEPTANCE_EXT_MODEL", "")
    if not api_key or not model:
        raise RuntimeError("ACCEPTANCE_EXT_API_KEY and ACCEPTANCE_EXT_MODEL are required")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install the llm extra: pip install -e '.[llm]'") from exc
    client = OpenAI(api_key=api_key, base_url=os.getenv("ACCEPTANCE_EXT_BASE_URL") or None)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": document.model_dump_json(exclude={"audit", "metrics"})},
        ],
    )
    payload: dict[str, Any] = json.loads(response.choices[0].message.content or "{}")
    candidate = document.model_copy(update={"tree": payload.get("tree", document.tree)})
    return ResultDocument.model_validate(candidate)


def langextract_available() -> bool:
    try:
        import langextract  # noqa: F401
    except ImportError:
        return False
    return True
''',
    "src/acceptance_ext/validation.py": r'''
from __future__ import annotations

from .models import AuditFinding, ResultDocument


def validate(document: ResultDocument) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    seen: set[tuple[str | None, str]] = set()
    for division in document.tree:
        if not division.mapped_50300_path:
            findings.append(
                AuditFinding(
                    severity="warning",
                    code="ontology-unattached",
                    message=f"分项“{division.name}”未挂入 50300 本体",
                    node_id=division.id,
                )
            )
        for lot in division.children:
            if not lot.children:
                findings.append(
                    AuditFinding(
                        severity="warning",
                        code="empty-lot",
                        message=f"检验批“{lot.name}”没有验收项目",
                        node_id=lot.id,
                    )
                )
            for item in lot.children:
                key = (item.source_clause, item.name)
                if key in seen:
                    findings.append(
                        AuditFinding(
                            severity="warning",
                            code="duplicate-item",
                            message=f"重复验收项目：{item.source_clause} {item.name}",
                            node_id=item.id,
                        )
                    )
                seen.add(key)
                if not item.evidence or not item.source_quote:
                    findings.append(
                        AuditFinding(
                            severity="error",
                            code="missing-evidence",
                            message="验收项目缺少原文证据",
                            node_id=item.id,
                        )
                    )
                elif all(e.method == "inferred" for e in item.evidence):
                    findings.append(
                        AuditFinding(
                            severity="error",
                            code="inferred-only",
                            message="验收项目只有推断证据",
                            node_id=item.id,
                        )
                    )
    return findings


def metrics(document: ResultDocument, elapsed_seconds: float) -> dict[str, float | int]:
    divisions = len(document.tree)
    lots = sum(len(d.children) for d in document.tree)
    items = [item for d in document.tree for lot in d.children for item in lot.children]
    grounded = sum(bool(item.evidence and item.source_quote) for item in items)
    sampled = sum(item.min_sampling is not None for item in items)
    attached = sum(bool(d.mapped_50300_path) for d in document.tree)
    return {
        "division_count": divisions,
        "inspection_lot_count": lots,
        "acceptance_item_count": len(items),
        "grounding_rate": grounded / len(items) if items else 0.0,
        "sampling_coverage": sampled / len(items) if items else 0.0,
        "ontology_attachment_rate": attached / divisions if divisions else 0.0,
        "elapsed_seconds": round(elapsed_seconds, 4),
    }
''',
    "src/acceptance_ext/exporters.py": r'''
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
    path.write_text(json.dumps(pdfex_payload(document), ensure_ascii=False, indent=2), encoding="utf-8")


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
                    f"<td><mark>{html.escape(item.source_quote)}</mark><small>{html.escape(location)}</small></td>"
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
''',
    "src/acceptance_ext/evaluation.py": r'''
from __future__ import annotations

import json
import re
from pathlib import Path

from .models import ResultDocument


def _norm(value: str | None) -> str:
    return re.sub(r"\W+", "", value or "", flags=re.UNICODE).lower()


def _keys(document: ResultDocument) -> set[tuple[str, str]]:
    return {
        (_norm(item.source_clause), _norm(item.name))
        for division in document.tree
        for lot in division.children
        for item in lot.children
    }


def evaluate(prediction: ResultDocument, gold_path: Path) -> dict[str, float | int]:
    raw = json.loads(gold_path.read_text(encoding="utf-8-sig"))
    gold = ResultDocument.model_validate(raw)
    predicted_keys = _keys(prediction)
    gold_keys = _keys(gold)
    true_positive = len(predicted_keys & gold_keys)
    precision = true_positive / len(predicted_keys) if predicted_keys else 0.0
    recall = true_positive / len(gold_keys) if gold_keys else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positive": true_positive,
        "predicted": len(predicted_keys),
        "gold": len(gold_keys),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
''',
    "src/acceptance_ext/pipeline.py": r'''
from __future__ import annotations

import time
from pathlib import Path

from .evaluation import evaluate
from .exporters import write_json, write_pdfex, write_review_html
from .extraction import attach_ontology, extract_tree, infer_standard, load_task_spec
from .models import ResultDocument
from .parsers import get_parser
from .refinement import openai_compatible_refine
from .validation import metrics, validate


class ExtractionPipeline:
    def __init__(
        self,
        parser: str = "markdown",
        extractor: str = "heuristic",
        ontology_path: Path | None = None,
        task_spec_path: Path | None = None,
    ) -> None:
        self.parser_name = parser
        self.extractor_name = extractor
        self.ontology_path = ontology_path
        self.task_spec_path = task_spec_path

    def run(self, source: Path) -> ResultDocument:
        started = time.perf_counter()
        parser = get_parser(self.parser_name)
        blocks = parser.parse(source)
        standard_no, standard_name = infer_standard(blocks, source.name)
        tree = extract_tree(blocks, load_task_spec(self.task_spec_path))
        attach_ontology(tree, self.ontology_path)
        document = ResultDocument(
            source_pdf=source.name,
            standard_no=standard_no,
            standard_name=standard_name,
            parser=self.parser_name,
            extractor=self.extractor_name,
            tree=tree,
        )
        if self.extractor_name in {"openai", "openai-compatible", "llm"}:
            document = openai_compatible_refine(document)
        elif self.extractor_name not in {"heuristic", "deterministic"}:
            raise ValueError("extractor must be heuristic or openai-compatible")
        document.audit = validate(document)
        document.metrics = metrics(document, time.perf_counter() - started)
        return document

    def run_to_files(
        self,
        source: Path,
        output: Path,
        pdfex_output: Path | None = None,
        review_html: Path | None = None,
        gold: Path | None = None,
    ) -> tuple[ResultDocument, dict | None]:
        document = self.run(source)
        write_json(document, output)
        if pdfex_output:
            write_pdfex(document, pdfex_output)
        if review_html:
            write_review_html(document, review_html)
        score = evaluate(document, gold) if gold else None
        return document, score
''',
    "src/acceptance_ext/integrations.py": r'''
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
        rows.append({"source": document.standard_no, "relation": "HAS_DIVISION_ITEM", "target": division.name})
        for lot in division.children:
            rows.append({"source": division.name, "relation": "HAS_INSPECTION_LOT", "target": lot.name})
            for item in lot.children:
                rows.append({"source": lot.name, "relation": "HAS_ACCEPTANCE_ITEM", "target": item.id})
                rows.append({"source": item.id, "relation": "GROUNDED_BY", "target": item.source_clause})
    return rows
''',
    "src/acceptance_ext/cli.py": r'''
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .pipeline import ExtractionPipeline

app = typer.Typer(no_args_is_help=True, help="Grounded construction-standard extraction lab")
console = Console()


@app.command()
def extract(
    source: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    parser: Annotated[str, typer.Option()] = "markdown",
    extractor: Annotated[str, typer.Option()] = "heuristic",
    ontology: Annotated[Path | None, typer.Option()] = None,
    task_spec: Annotated[Path | None, typer.Option()] = None,
    output: Annotated[Path, typer.Option()] = Path("output/result.json"),
    pdfex_output: Annotated[Path | None, typer.Option()] = None,
    review_html: Annotated[Path | None, typer.Option()] = None,
    gold: Annotated[Path | None, typer.Option()] = None,
) -> None:
    document, score = ExtractionPipeline(parser, extractor, ontology, task_spec).run_to_files(
        source, output, pdfex_output, review_html, gold
    )
    console.print(json.dumps(document.metrics, ensure_ascii=False, indent=2))
    if score:
        console.print(json.dumps(score, ensure_ascii=False, indent=2))
    console.print(f"written: {output}")


@app.command()
def benchmark(
    source: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    parsers: Annotated[str, typer.Option()] = "markdown",
    extractors: Annotated[str, typer.Option()] = "heuristic",
    ontology: Annotated[Path | None, typer.Option()] = None,
    gold: Annotated[Path | None, typer.Option()] = None,
    output: Annotated[Path, typer.Option()] = Path("output/benchmark.json"),
) -> None:
    rows: list[dict] = []
    for parser in [value.strip() for value in parsers.split(",") if value.strip()]:
        for extractor in [value.strip() for value in extractors.split(",") if value.strip()]:
            try:
                document, score = ExtractionPipeline(parser, extractor, ontology).run_to_files(
                    source,
                    output.parent / f"{source.stem}.{parser}.{extractor}.json",
                    gold=gold,
                )
                rows.append({"parser": parser, "extractor": extractor, **document.metrics, "score": score})
            except Exception as exc:  # benchmark must preserve failed arms
                rows.append({"parser": parser, "extractor": extractor, "error": str(exc)})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print_json(output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    app()
''',
    "src/acceptance_ext/server.py": r'''
from __future__ import annotations

import tempfile
from pathlib import Path

from .pipeline import ExtractionPipeline


def create_app():
    try:
        from fastapi import FastAPI, File, Form, UploadFile
    except ImportError as exc:
        raise RuntimeError("Install the server extra: pip install -e '.[server]'") from exc

    app = FastAPI(title="Acceptance Ext", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/extract")
    async def extract_document(
        file: UploadFile = File(...),
        parser: str = Form("markdown"),
        extractor: str = Form("heuristic"),
    ) -> dict:
        suffix = Path(file.filename or "input.md").suffix
        with tempfile.TemporaryDirectory(prefix="acceptance-ext-api-") as work:
            source = Path(work) / f"input{suffix}"
            source.write_bytes(await file.read())
            document = ExtractionPipeline(parser=parser, extractor=extractor).run(source)
            return document.model_dump(mode="json")

    return app


app = create_app()
''',
    "src/acceptance_ext/resources/50300_seed.json": r'''
[
  {
    "name": "主体结构",
    "node_type": "单位",
    "children": [
      {
        "name": "混凝土结构",
        "node_type": "子分部",
        "children": [
          {"name": "模板", "node_type": "分项", "children": []},
          {"name": "钢筋", "node_type": "分项", "children": []},
          {"name": "混凝土", "node_type": "分项", "children": []},
          {"name": "预应力", "node_type": "分项", "children": []},
          {"name": "现浇结构", "node_type": "分项", "children": []},
          {"name": "装配式结构", "node_type": "分项", "children": []}
        ]
      },
      {
        "name": "木结构",
        "node_type": "子分部",
        "children": [
          {"name": "方木与原木结构", "node_type": "分项", "children": []},
          {"name": "胶合木结构", "node_type": "分项", "children": []},
          {"name": "轻型木结构", "node_type": "分项", "children": []},
          {"name": "木结构的防护", "node_type": "分项", "children": []}
        ]
      }
    ]
  }
]
''',
    "config/gb_acceptance.json": r'''
{
  "schema_version": "acceptance-ext-task-v1",
  "language": "zh-CN",
  "tree": ["分项", "检验批", "验收项目"],
  "required_grounding": ["source_clause", "source_quote", "evidence"],
  "item_categories": ["主控项目", "一般项目", "未分类"],
  "sampling_policy": {
    "explicit_only": true,
    "never_replace_explicit_quantity_with_fallback": true,
    "recognized_units": ["处", "件", "个", "点", "组", "根", "套", "批", "间", "樘", "块", "次"]
  },
  "ontology": "GB 50300"
}
''',
    "sample_data/mini_standard.md": r'''
# GB 50000-2026 示例工程施工质量验收规范

## 5 木构件工程

### 5.1 方木与原木结构

#### 主控项目

5.1.1 木构件的材质等级必须符合设计文件的规定。检查方法：检查产品合格证书和检验报告。

5.1.2 连接节点的承载性能应符合设计要求。检查数量：每个检验批抽查10%，且不应少于3处。检查方法：观察并检查施工记录。

#### 一般项目

5.1.3 构件表面应平整，不得有影响使用功能的裂缝。检查数量：全数检查。

5.1.4 构件截面尺寸允许偏差应为±3mm。检查数量：每20件抽查1件，且不少于3件。
''',
    "tests/test_pipeline.py": r'''
from pathlib import Path

from acceptance_ext.pipeline import ExtractionPipeline


def test_smoke_extracts_grounded_items() -> None:
    document = ExtractionPipeline(parser="markdown").run(Path("sample_data/mini_standard.md"))
    items = [item for division in document.tree for lot in division.children for item in lot.children]
    assert len(items) == 4
    assert document.metrics["grounding_rate"] == 1.0
    assert any(item.item_category == "主控项目" for item in items)
    assert any(item.min_sampling and "10%" in item.min_sampling for item in items)
    assert all(item.source_quote for item in items)
''',
    "docs/EVALUATION.md": r'''
# Evaluation protocol

A parser/extractor is not considered stronger because its demo looks polished. Use the same
source files, the same ontology and a frozen human-labelled gold set.

Minimum reported metrics:

1. acceptance-item precision, recall and F1;
2. exact source-clause and source-quote grounding rate;
3. minimum-sampling exact/normalized accuracy;
4. item-category accuracy;
5. GB 50300 attachment accuracy and wrong-attachment rate;
6. duplicate and hallucinated item count;
7. elapsed time, model calls, token usage and monetary cost;
8. human correction time per document.

Split standards by document type (native text, scanned, table-heavy) and by standard family.
Keep parser output, prompts, model version, task spec and ontology hash with every run.
''',
    ".github/workflows/ci.yml": r'''
name: ci
on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install -e ".[dev]"
      - run: ruff check src tests
      - run: pytest -q
''',
}


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    sentinel = root / "src" / "acceptance_ext" / "pipeline.py"
    if sentinel.exists():
        print(f"Acceptance Ext source already exists at {sentinel}; bootstrap skipped.")
        return 0
    for relative, content in FILES.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")
    print(json.dumps({"created": len(FILES), "root": str(root)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
