from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from .evaluation import evaluate
from .exporters import write_json, write_pdfex, write_review_html
from .extraction import attach_ontology, extract_tree, infer_standard, load_task_spec
from .models import ResultDocument
from .parsers import get_parser
from .refinement import openai_compatible_refine
from .validation import metrics, validate

ProgressCallback = Callable[[dict[str, Any]], None]
CancelCheck = Callable[[], bool]


class PipelineCancelled(RuntimeError):
    """Raised when a cooperative job cancellation is observed between stages."""


def _emit(
    callback: ProgressCallback | None,
    *,
    stage: str,
    title: str,
    state: str,
    progress: float,
    detail: str | None = None,
    **extra: Any,
) -> None:
    if callback is None:
        return
    callback(
        {
            "stage": stage,
            "title": title,
            "state": state,
            "progress": max(0.0, min(1.0, progress)),
            "detail": detail,
            **extra,
        }
    )


def _check_cancelled(cancelled: CancelCheck | None) -> None:
    if cancelled is not None and cancelled():
        raise PipelineCancelled("任务已取消")


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

    def run(
        self,
        source: Path,
        *,
        progress: ProgressCallback | None = None,
        cancelled: CancelCheck | None = None,
    ) -> ResultDocument:
        started = time.perf_counter()

        _check_cancelled(cancelled)
        _emit(
            progress,
            stage="parse",
            title="解析文档",
            state="running",
            progress=0.04,
            detail=f"使用 {self.parser_name} 读取 {source.name}",
        )
        parser = get_parser(self.parser_name)
        blocks = parser.parse(source)
        _emit(
            progress,
            stage="parse",
            title="解析文档",
            state="done",
            progress=0.24,
            detail=f"获得 {len(blocks)} 个可追溯文本块",
            block_count=len(blocks),
        )

        _check_cancelled(cancelled)
        _emit(
            progress,
            stage="segment",
            title="识别标准与条款结构",
            state="running",
            progress=0.29,
            detail="定位标准号、章节标题与条款边界",
        )
        standard_no, standard_name = infer_standard(blocks, source.name)
        task_spec = load_task_spec(self.task_spec_path)
        _emit(
            progress,
            stage="segment",
            title="识别标准与条款结构",
            state="done",
            progress=0.38,
            detail=standard_no or standard_name or "未从文档头部识别出标准号",
            standard_no=standard_no,
            standard_name=standard_name,
        )

        _check_cancelled(cancelled)
        _emit(
            progress,
            stage="extract",
            title="抽取验收结构",
            state="running",
            progress=0.43,
            detail="生成分项 → 检验批 → 验收项目结构",
        )
        tree = extract_tree(blocks, task_spec)
        division_count = len(tree)
        lot_count = sum(len(division.children) for division in tree)
        item_count = sum(
            len(lot.children)
            for division in tree
            for lot in division.children
        )
        _emit(
            progress,
            stage="extract",
            title="抽取验收结构",
            state="done",
            progress=0.65,
            detail=f"识别 {division_count} 个分项、{lot_count} 个检验批、{item_count} 个验收项目",
            division_count=division_count,
            lot_count=lot_count,
            item_count=item_count,
        )

        _check_cancelled(cancelled)
        _emit(
            progress,
            stage="ontology",
            title="挂载 GB 50300",
            state="running",
            progress=0.69,
            detail="将专业规范节点匹配到统一验收体系",
        )
        attach_ontology(tree, self.ontology_path)
        mapped_count = sum(bool(division.mapped_50300_path) for division in tree)
        _emit(
            progress,
            stage="ontology",
            title="挂载 GB 50300",
            state="done",
            progress=0.77,
            detail=f"已挂载 {mapped_count}/{division_count} 个分项",
            mapped_count=mapped_count,
        )

        document = ResultDocument(
            source_pdf=source.name,
            standard_no=standard_no,
            standard_name=standard_name,
            parser=self.parser_name,
            extractor=self.extractor_name,
            tree=tree,
        )

        _check_cancelled(cancelled)
        if self.extractor_name in {"openai", "openai-compatible", "llm"}:
            _emit(
                progress,
                stage="refine",
                title="模型结构化复核",
                state="running",
                progress=0.80,
                detail="使用 OpenAI-compatible 模型复核抽取字段",
            )
            document = openai_compatible_refine(document)
            _emit(
                progress,
                stage="refine",
                title="模型结构化复核",
                state="done",
                progress=0.88,
                detail="模型复核完成",
            )
        elif self.extractor_name in {"heuristic", "deterministic"}:
            _emit(
                progress,
                stage="refine",
                title="模型结构化复核",
                state="skipped",
                progress=0.80,
                detail="当前使用确定性抽取器，本阶段跳过",
            )
        else:
            raise ValueError("extractor must be heuristic or openai-compatible")

        _check_cancelled(cancelled)
        _emit(
            progress,
            stage="validate",
            title="证据与结果审计",
            state="running",
            progress=0.91,
            detail="检查证据覆盖、抽样规则和层级完整性",
        )
        document.audit = validate(document)
        document.metrics = metrics(document, time.perf_counter() - started)
        _emit(
            progress,
            stage="validate",
            title="证据与结果审计",
            state="done",
            progress=0.97,
            detail=f"完成审计，发现 {len(document.audit)} 条提示",
            audit_count=len(document.audit),
            metrics=document.metrics,
        )
        return document

    def run_to_files(
        self,
        source: Path,
        output: Path,
        pdfex_output: Path | None = None,
        review_html: Path | None = None,
        gold: Path | None = None,
        *,
        progress: ProgressCallback | None = None,
        cancelled: CancelCheck | None = None,
    ) -> tuple[ResultDocument, dict | None]:
        document = self.run(source, progress=progress, cancelled=cancelled)
        write_json(document, output)
        if pdfex_output:
            write_pdfex(document, pdfex_output)
        if review_html:
            write_review_html(document, review_html)
        score = evaluate(document, gold) if gold else None
        return document, score
