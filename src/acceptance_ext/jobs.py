from __future__ import annotations

import json
import os
import re
import shutil
import threading
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ResultDocument
from .pipeline import ExtractionPipeline, PipelineCancelled

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
RUNNABLE_STATUSES = {"queued", "running"}
ALLOWED_PARSERS = {"auto", "markdown", "pymupdf", "docling", "mineru", "paddleocr"}
ALLOWED_EXTRACTORS = {"heuristic", "deterministic", "openai", "openai-compatible", "llm"}
MAX_UPLOAD_BYTES = int(os.getenv("ACCEPTANCE_EXT_MAX_UPLOAD_BYTES", str(160 * 1024 * 1024)))

STAGE_DEFINITIONS = [
    ("queued", "等待执行"),
    ("parse", "解析文档"),
    ("segment", "识别标准与条款结构"),
    ("extract", "抽取验收结构"),
    ("ontology", "挂载 GB 50300"),
    ("refine", "模型结构化复核"),
    ("validate", "证据与结果审计"),
    ("persist", "保存结果"),
]

DEMO_STANDARD = """# GB 90000-2026 示例工程施工质量验收规范

## 4 模板工程

### 4.1 主控项目

4.1.1 模板及支架应符合设计文件要求。检查数量：全数检查。检验方法：观察、尺量。

4.1.2 模板起拱应符合施工方案要求。检查数量：同一检验批抽查构件数量的10%，且不少于3件。检验方法：水准仪或尺量。

### 4.2 一般项目

4.2.1 固定在模板上的预埋件和预留孔洞不得遗漏。检查数量：同一检验批抽查10%，且不少于3处。检验方法：观察、尺量。

## 5 钢筋工程

### 5.1 主控项目

5.1.1 钢筋进场时应按国家现行标准抽取试件作力学性能检验。检查数量：按进场批次全数检查质量证明文件。
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def safe_filename(name: str | None, fallback: str = "document.md") -> str:
    cleaned = Path(name or fallback).name.strip() or fallback
    cleaned = re.sub(r"[\x00-\x1f<>:\"/\\|?*]+", "_", cleaned)
    return cleaned[:180]


def resolve_parser(requested: str, filename: str) -> str:
    normalized = requested.lower().strip()
    if normalized not in ALLOWED_PARSERS:
        raise ValueError(f"不支持的 parser：{requested}")
    if normalized != "auto":
        return normalized
    suffix = Path(filename).suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        return "markdown"
    if suffix == ".pdf":
        return "pymupdf"
    raise ValueError("auto parser 只支持 PDF、Markdown 或 TXT 文件")


def validate_extractor(name: str) -> str:
    normalized = name.lower().strip()
    if normalized not in ALLOWED_EXTRACTORS:
        raise ValueError(f"不支持的 extractor：{name}")
    return normalized


def initial_stages() -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "label": label,
            "status": "pending",
            "progress": 0.0,
            "detail": None,
            "started_at": None,
            "finished_at": None,
        }
        for key, label in STAGE_DEFINITIONS
    ]


class JobManager:
    """Small file-backed job runner used by the workbench UI.

    The store intentionally stays transparent: each job directory contains the
    source file, ``job.json``, ``events.jsonl`` and (after success) ``result.json``.
    This keeps the experiment easy to inspect, copy and recover.
    """

    def __init__(self, workspace: Path | None = None, max_workers: int | None = None) -> None:
        configured = workspace or Path(os.getenv("ACCEPTANCE_EXT_WORKSPACE", ".acceptance_ext"))
        self.workspace = configured.expanduser().resolve()
        self.jobs_dir = self.workspace / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        workers = max_workers or max(1, int(os.getenv("ACCEPTANCE_EXT_WORKERS", "2")))
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="acceptance-ext")
        self._lock = threading.RLock()
        self._futures: dict[str, Future[None]] = {}
        self._recover_interrupted_jobs()

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def create_job(
        self,
        *,
        filename: str,
        content: bytes,
        parser: str = "auto",
        extractor: str = "heuristic",
    ) -> dict[str, Any]:
        if not content:
            raise ValueError("上传文件为空")
        if len(content) > MAX_UPLOAD_BYTES:
            raise ValueError(f"文件超过上传上限：{MAX_UPLOAD_BYTES // (1024 * 1024)} MB")

        name = safe_filename(filename)
        resolved_parser = resolve_parser(parser, name)
        resolved_extractor = validate_extractor(extractor)
        job_id = f"job-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}"
        job_dir = self.jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        source_path = job_dir / name
        source_path.write_bytes(content)
        now = utc_now()
        stages = initial_stages()
        stages[0].update(status="queued", progress=0.0, started_at=now, detail="任务已进入执行队列")
        job: dict[str, Any] = {
            "job_id": job_id,
            "kind": "acceptance_ext",
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "finished_at": None,
            "progress": 0.0,
            "current_stage": "queued",
            "cancel_requested": False,
            "event_count": 0,
            "result_revision": 0,
            "input": {
                "file_name": name,
                "size": len(content),
                "requested_parser": parser,
                "parser": resolved_parser,
                "extractor": resolved_extractor,
            },
            "output": {
                "result_url": f"/api/jobs/{job_id}/result",
                "source_url": f"/api/jobs/{job_id}/source",
                "download_url": f"/api/jobs/{job_id}/result?download=1",
            },
            "stages": stages,
            "metrics": None,
            "audit_count": None,
            "error": None,
            "error_detail": None,
        }
        self._write_job(job)
        self._append_event(
            job_id,
            kind="job_created",
            stage="queued",
            title="任务已创建",
            detail=f"{name} · {resolved_parser} · {resolved_extractor}",
            progress=0.0,
            state="queued",
        )
        self._futures[job_id] = self._executor.submit(self._run_job, job_id)
        return self.get_job(job_id)

    def create_demo_job(self, parser: str = "markdown", extractor: str = "heuristic") -> dict[str, Any]:
        return self.create_job(
            filename="GB90000-2026_执行体验示例.md",
            content=DEMO_STANDARD.encode("utf-8"),
            parser=parser,
            extractor=extractor,
        )

    def list_jobs(self) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        with self._lock:
            for path in self.jobs_dir.glob("*/job.json"):
                try:
                    jobs.append(json.loads(path.read_text(encoding="utf-8")))
                except (OSError, json.JSONDecodeError):
                    continue
        jobs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return jobs

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            path = self._job_path(job_id)
            if not path.exists():
                raise KeyError(job_id)
            return json.loads(path.read_text(encoding="utf-8"))

    def get_events(self, job_id: str, cursor: int = 0, limit: int = 200) -> dict[str, Any]:
        self.get_job(job_id)
        cursor = max(0, cursor)
        limit = max(1, min(limit, 500))
        path = self._events_path(job_id)
        events: list[dict[str, Any]] = []
        if path.exists():
            with self._lock, path.open("r", encoding="utf-8") as stream:
                for index, line in enumerate(stream):
                    if index < cursor:
                        continue
                    if len(events) >= limit:
                        break
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        total = self.get_job(job_id).get("event_count", cursor + len(events))
        next_cursor = cursor + len(events)
        return {
            "events": events,
            "cursor": cursor,
            "next_cursor": next_cursor if next_cursor < total else None,
            "total": total,
        }

    def get_result(self, job_id: str) -> ResultDocument:
        job = self.get_job(job_id)
        path = self._result_path(job_id)
        if not path.exists():
            raise FileNotFoundError(f"job {job_id} 还没有结果（当前状态：{job['status']}）")
        return ResultDocument.model_validate_json(path.read_text(encoding="utf-8"))

    def save_result(self, job_id: str, payload: dict[str, Any]) -> ResultDocument:
        job = self.get_job(job_id)
        if job["status"] != "succeeded":
            raise ValueError("只有已完成任务的结果可以编辑")
        document = ResultDocument.model_validate(payload)
        with self._lock:
            self._atomic_write_text(
                self._result_path(job_id),
                document.model_dump_json(indent=2),
            )
            job = self.get_job(job_id)
            job["result_revision"] = int(job.get("result_revision", 0)) + 1
            job["updated_at"] = utc_now()
            self._write_job(job)
        self._append_event(
            job_id,
            kind="result_saved",
            stage="persist",
            title="人工修订已保存",
            detail=f"结果修订版本 {job['result_revision']}",
            progress=1.0,
            state="done",
        )
        return document

    def source_path(self, job_id: str) -> Path:
        job = self.get_job(job_id)
        path = self._job_dir(job_id) / job["input"]["file_name"]
        if not path.exists():
            raise FileNotFoundError(path)
        return path

    def result_path(self, job_id: str) -> Path:
        self.get_job(job_id)
        path = self._result_path(job_id)
        if not path.exists():
            raise FileNotFoundError(path)
        return path

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self.get_job(job_id)
            if job["status"] in TERMINAL_STATUSES:
                return job
            job["cancel_requested"] = True
            job["updated_at"] = utc_now()
            self._write_job(job)
        self._append_event(
            job_id,
            kind="control",
            stage=job.get("current_stage") or "queued",
            title="已请求取消",
            detail="将在当前不可中断步骤完成后停止",
            progress=float(job.get("progress") or 0.0),
            state="cancelling",
        )
        return self.get_job(job_id)

    def restart_job(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        source = self.source_path(job_id)
        return self.create_job(
            filename=job["input"]["file_name"],
            content=source.read_bytes(),
            parser=job["input"].get("requested_parser") or job["input"]["parser"],
            extractor=job["input"]["extractor"],
        )

    def delete_job(self, job_id: str) -> None:
        with self._lock:
            job = self.get_job(job_id)
            if job["status"] not in TERMINAL_STATUSES:
                raise ValueError("运行中任务不能直接删除，请先取消")
            shutil.rmtree(self._job_dir(job_id))
            self._futures.pop(job_id, None)

    def _run_job(self, job_id: str) -> None:
        try:
            self._transition_running(job_id)
            job = self.get_job(job_id)
            pipeline = ExtractionPipeline(
                parser=job["input"]["parser"],
                extractor=job["input"]["extractor"],
            )
            document = pipeline.run(
                self.source_path(job_id),
                progress=lambda event: self._record_pipeline_event(job_id, event),
                cancelled=lambda: bool(self.get_job(job_id).get("cancel_requested")),
            )
            if self.get_job(job_id).get("cancel_requested"):
                raise PipelineCancelled("任务已取消")

            self._record_pipeline_event(
                job_id,
                {
                    "stage": "persist",
                    "title": "保存结果",
                    "state": "running",
                    "progress": 0.985,
                    "detail": "写入可编辑结果与运行元数据",
                },
            )
            self._atomic_write_text(self._result_path(job_id), document.model_dump_json(indent=2))
            self._record_pipeline_event(
                job_id,
                {
                    "stage": "persist",
                    "title": "保存结果",
                    "state": "done",
                    "progress": 1.0,
                    "detail": "result.json 已保存",
                },
            )
            with self._lock:
                job = self.get_job(job_id)
                job.update(
                    status="succeeded",
                    progress=1.0,
                    current_stage="persist",
                    finished_at=utc_now(),
                    updated_at=utc_now(),
                    metrics=document.metrics,
                    audit_count=len(document.audit),
                    error=None,
                    error_detail=None,
                )
                self._write_job(job)
            self._append_event(
                job_id,
                kind="summary",
                stage="persist",
                title="抽取完成",
                detail=self._summary_text(document),
                progress=1.0,
                state="done",
                payload={
                    "metrics": document.metrics,
                    "audit_count": len(document.audit),
                    "standard_no": document.standard_no,
                    "standard_name": document.standard_name,
                },
            )
        except PipelineCancelled as exc:
            self._finish_cancelled(job_id, str(exc))
        except Exception as exc:  # pragma: no cover - error path depends on optional parsers/models
            self._finish_failed(job_id, exc)

    def _transition_running(self, job_id: str) -> None:
        now = utc_now()
        with self._lock:
            job = self.get_job(job_id)
            if job.get("cancel_requested"):
                raise PipelineCancelled("任务在开始前已取消")
            job.update(status="running", started_at=now, updated_at=now, current_stage="queued")
            queued = self._stage(job, "queued")
            queued.update(status="done", progress=1.0, finished_at=now, detail="开始执行")
            self._write_job(job)
        self._append_event(
            job_id,
            kind="stage",
            stage="queued",
            title="开始执行",
            detail="后台工作线程已接管任务",
            progress=0.01,
            state="done",
        )

    def _record_pipeline_event(self, job_id: str, event: dict[str, Any]) -> None:
        stage_key = str(event.get("stage") or "extract")
        state = str(event.get("state") or "running")
        progress = float(event.get("progress") or 0.0)
        now = utc_now()
        with self._lock:
            job = self.get_job(job_id)
            if job.get("cancel_requested"):
                raise PipelineCancelled("任务已取消")
            stage = self._stage(job, stage_key)
            if state == "running" and not stage.get("started_at"):
                stage["started_at"] = now
            if state in {"done", "failed", "skipped", "cancelled"}:
                stage["finished_at"] = now
            stage["status"] = state
            stage["progress"] = 1.0 if state in {"done", "skipped"} else progress
            stage["detail"] = event.get("detail")
            job["current_stage"] = stage_key
            job["progress"] = max(float(job.get("progress") or 0.0), progress)
            job["updated_at"] = now
            self._write_job(job)
        payload = {
            key: value
            for key, value in event.items()
            if key not in {"stage", "title", "state", "progress", "detail"}
        }
        self._append_event(
            job_id,
            kind="stage",
            stage=stage_key,
            title=str(event.get("title") or stage.get("label") or stage_key),
            detail=event.get("detail"),
            progress=progress,
            state=state,
            payload=payload or None,
        )

    def _finish_cancelled(self, job_id: str, message: str) -> None:
        now = utc_now()
        with self._lock:
            job = self.get_job(job_id)
            job.update(
                status="cancelled",
                finished_at=now,
                updated_at=now,
                error=message or "任务已取消",
            )
            current = self._stage(job, job.get("current_stage") or "queued")
            if current["status"] not in {"done", "skipped"}:
                current.update(status="cancelled", finished_at=now)
            self._write_job(job)
        self._append_event(
            job_id,
            kind="summary",
            stage=job.get("current_stage") or "queued",
            title="任务已取消",
            detail=message,
            progress=float(job.get("progress") or 0.0),
            state="cancelled",
        )

    def _finish_failed(self, job_id: str, exc: Exception) -> None:
        now = utc_now()
        message = str(exc) or exc.__class__.__name__
        detail = traceback.format_exc(limit=20)
        with self._lock:
            job = self.get_job(job_id)
            job.update(
                status="failed",
                finished_at=now,
                updated_at=now,
                error=message,
                error_detail=detail,
            )
            current = self._stage(job, job.get("current_stage") or "queued")
            if current["status"] not in {"done", "skipped"}:
                current.update(status="failed", finished_at=now, detail=message)
            self._write_job(job)
        self._append_event(
            job_id,
            kind="error",
            stage=job.get("current_stage") or "queued",
            title="任务失败",
            detail=message,
            progress=float(job.get("progress") or 0.0),
            state="failed",
            payload={"traceback": detail},
        )

    def _append_event(
        self,
        job_id: str,
        *,
        kind: str,
        stage: str,
        title: str,
        detail: str | None,
        progress: float,
        state: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            job = self.get_job(job_id)
            seq = int(job.get("event_count", 0)) + 1
            event = {
                "seq": seq,
                "ts": utc_now(),
                "kind": kind,
                "stage": stage,
                "title": title,
                "detail": detail,
                "progress": round(max(0.0, min(1.0, progress)), 4),
                "state": state,
                "payload": payload,
            }
            with self._events_path(job_id).open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            job["event_count"] = seq
            job["updated_at"] = event["ts"]
            self._write_job(job)
            return event

    def _recover_interrupted_jobs(self) -> None:
        for job in self.list_jobs():
            if job.get("status") not in RUNNABLE_STATUSES:
                continue
            now = utc_now()
            job.update(
                status="failed",
                finished_at=now,
                updated_at=now,
                error="服务重启，原任务未能继续",
            )
            current = self._stage(job, job.get("current_stage") or "queued")
            current.update(status="failed", finished_at=now, detail=job["error"])
            self._write_job(job)
            self._append_event(
                job["job_id"],
                kind="error",
                stage=job.get("current_stage") or "queued",
                title="任务被服务重启中断",
                detail=job["error"],
                progress=float(job.get("progress") or 0.0),
                state="failed",
            )

    @staticmethod
    def _summary_text(document: ResultDocument) -> str:
        divisions = len(document.tree)
        lots = sum(len(division.children) for division in document.tree)
        items = sum(len(lot.children) for division in document.tree for lot in division.children)
        return (
            f"{document.standard_no or document.standard_name or document.source_pdf}："
            f"{divisions} 个分项，{lots} 个检验批，{items} 个验收项目"
        )

    @staticmethod
    def _stage(job: dict[str, Any], key: str) -> dict[str, Any]:
        for stage in job.get("stages", []):
            if stage.get("key") == key:
                return stage
        stage = {
            "key": key,
            "label": key,
            "status": "pending",
            "progress": 0.0,
            "detail": None,
            "started_at": None,
            "finished_at": None,
        }
        job.setdefault("stages", []).append(stage)
        return stage

    def _job_dir(self, job_id: str) -> Path:
        if not re.fullmatch(r"job-[A-Za-z0-9-]+", job_id):
            raise KeyError(job_id)
        return self.jobs_dir / job_id

    def _job_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "job.json"

    def _events_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "events.jsonl"

    def _result_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "result.json"

    def _write_job(self, job: dict[str, Any]) -> None:
        self._atomic_write_text(
            self._job_path(job["job_id"]),
            json.dumps(job, ensure_ascii=False, indent=2),
        )

    @staticmethod
    def _atomic_write_text(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
