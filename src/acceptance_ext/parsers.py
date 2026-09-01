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
