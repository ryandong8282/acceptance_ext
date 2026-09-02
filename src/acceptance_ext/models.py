from __future__ import annotations

from typing import Any, Literal

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
    evidence_id: str | None = None
    source_id: str | None = None
    parser_version: str | None = None
    location_type: Literal["text", "table", "image"] = "text"
    table_no: str | None = None
    table_row: int | None = None
    table_columns: dict[str, str] | None = None
    inferred: bool = False


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
    type_name: str | None = "验收项目"
    item_no: int | None = None
    chapter_no: str | None = None
    chapter_title: str | None = None
    source_page: int | None = None
    pdf_page: int | None = None
    markdown_line: int | None = None
    source_clause: str | None = None
    source_quote: str
    item_category: Literal["主控项目", "一般项目", "未分类"] = "未分类"
    check_quantity: str | None = None
    check_method: str | None = None
    table_no: str | None = None
    deviation_unit: str | None = None
    deviation_value: str | None = None
    min_sampling: str | None = None
    min_sampling_reason: str | None = None
    min_sampling_confidence: Literal["高", "中", "低"] | None = None
    min_sampling_script: str | None = None
    min_sampling_json: dict[str, Any] | None = None
    min_sampling_rule: dict[str, Any] | None = None
    min_sampling_rule_guarded: bool | None = None
    params: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    verification_sources: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.75, ge=0, le=1)
    children: list[Any] = Field(default_factory=list)


class InspectionLot(BaseModel):
    id: str
    name: str
    node_type: Literal["检验批"] = "检验批"
    source_title: str | None = None
    chapter_no: str | None = None
    chapter_title: str | None = None
    source_page: int | None = None
    pdf_page: int | None = None
    children: list[AcceptanceItem] = Field(default_factory=list)


class DivisionItem(BaseModel):
    id: str
    name: str
    node_type: Literal["分项"] = "分项"
    chapter_no: str | None = None
    source_page: int | None = None
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
    chapters: list[dict[str, Any]] = Field(default_factory=list)
    tree: list[DivisionItem] = Field(default_factory=list)
    page_count: int | None = None
    markdown_file: str | None = None
    audit: list[AuditFinding] = Field(default_factory=list)
    metrics: dict[str, float | int | str | None] = Field(default_factory=dict)
