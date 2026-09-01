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
