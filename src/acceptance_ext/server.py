import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from .jobs import JobManager, MAX_UPLOAD_BYTES, TERMINAL_STATUSES, resolve_parser
from .pipeline import ExtractionPipeline


def create_app(*, workspace: Path | None = None):
    try:
        from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
        from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        raise RuntimeError("Install the server extra: pip install -e '.[server]'") from exc

    app = FastAPI(
        title="Acceptance Ext Workbench",
        version="0.2.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    manager = JobManager(workspace=workspace)
    app.state.jobs = manager
    web_root = Path(__file__).with_name("web")

    def job_or_404(job_id: str) -> dict[str, Any]:
        try:
            return manager.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"job 不存在：{job_id}") from exc

    def public_error(exc: Exception, status_code: int = 400) -> HTTPException:
        return HTTPException(status_code=status_code, detail=str(exc) or exc.__class__.__name__)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "workspace": str(manager.workspace)}

    @app.get("/api/capabilities")
    def capabilities() -> dict[str, Any]:
        return {
            "parsers": ["auto", "markdown", "pymupdf", "docling", "mineru", "paddleocr"],
            "extractors": ["heuristic", "openai-compatible"],
            "max_upload_bytes": MAX_UPLOAD_BYTES,
            "workspace": str(manager.workspace),
            "features": {
                "jobs": True,
                "live_events": True,
                "result_editing": True,
                "source_preview": True,
                "pause_resume": False,
            },
        }

    @app.post("/extract")
    async def extract_document(
        file: UploadFile = File(...),
        parser: str = Form("auto"),
        extractor: str = Form("heuristic"),
    ) -> dict[str, Any]:
        suffix = Path(file.filename or "document.md").suffix or ".md"
        with tempfile.TemporaryDirectory(prefix="acceptance-ext-") as work:
            source = Path(work) / f"input{suffix}"
            source.write_bytes(await file.read())
            selected_parser = resolve_parser(parser, file.filename or source.name)
            document = ExtractionPipeline(parser=selected_parser, extractor=extractor).run(source)
            return document.model_dump(mode="json")

    @app.get("/api/jobs")
    def list_jobs() -> dict[str, Any]:
        jobs = manager.list_jobs()
        active = [job["job_id"] for job in jobs if job.get("status") == "running"]
        queued = [job["job_id"] for job in jobs if job.get("status") == "queued"]
        return {
            "jobs": jobs,
            "active": active[0] if active else None,
            "active_ids": active,
            "queued": queued,
        }

    @app.post("/api/jobs", status_code=201)
    async def create_job(
        file: UploadFile | None = File(None),
        pdf: UploadFile | None = File(None),
        parser: str = Form("auto"),
        extractor: str = Form("heuristic"),
    ) -> dict[str, Any]:
        upload = file or pdf
        if upload is None:
            raise HTTPException(status_code=422, detail="需要 multipart 文件字段 file（兼容 pdf）")
        try:
            return manager.create_job(
                filename=upload.filename or "document.md",
                content=await upload.read(),
                parser=parser,
                extractor=extractor,
            )
        except ValueError as exc:
            raise public_error(exc) from exc

    @app.post("/api/jobs/demo", status_code=201)
    def create_demo_job(
        parser: str = Query("markdown"),
        extractor: str = Query("heuristic"),
    ) -> dict[str, Any]:
        try:
            return manager.create_demo_job(parser=parser, extractor=extractor)
        except ValueError as exc:
            raise public_error(exc) from exc

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        return job_or_404(job_id)

    @app.get("/api/jobs/{job_id}/event-log")
    def get_event_log(
        job_id: str,
        cursor: int = Query(0, ge=0),
        limit: int = Query(200, ge=1, le=500),
    ) -> dict[str, Any]:
        job_or_404(job_id)
        return manager.get_events(job_id, cursor=cursor, limit=limit)

    @app.get("/api/jobs/{job_id}/events")
    async def stream_events(
        job_id: str,
        request: Request,
        cursor: int = Query(0, ge=0),
    ) -> StreamingResponse:
        job_or_404(job_id)
        header_cursor = request.headers.get("last-event-id", "").strip()
        if cursor == 0 and header_cursor.isdigit():
            cursor = int(header_cursor)

        async def event_stream():
            next_cursor = cursor
            idle_ticks = 0
            while True:
                page = manager.get_events(job_id, cursor=next_cursor, limit=200)
                for event in page["events"]:
                    next_cursor = int(event["seq"])
                    yield f"id: {event['seq']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                job = manager.get_job(job_id)
                if job["status"] in TERMINAL_STATUSES and next_cursor >= int(job.get("event_count", 0)):
                    terminal = {
                        "job_id": job_id,
                        "status": job["status"],
                        "event_count": job["event_count"],
                    }
                    yield f"event: terminal\ndata: {json.dumps(terminal, ensure_ascii=False)}\n\n"
                    break
                if not page["events"]:
                    idle_ticks += 1
                    if idle_ticks % 20 == 0:
                        yield ": keep-alive\n\n"
                else:
                    idle_ticks = 0
                await asyncio.sleep(0.5)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.get("/api/jobs/{job_id}/result")
    def get_result(job_id: str, download: bool = Query(False)):
        job_or_404(job_id)
        try:
            document = manager.get_result(job_id)
        except FileNotFoundError as exc:
            raise public_error(exc, status_code=404) from exc
        if download:
            path = manager.result_path(job_id)
            return FileResponse(path, media_type="application/json", filename=f"{job_id}.result.json")
        return JSONResponse(document.model_dump(mode="json"))

    @app.put("/api/jobs/{job_id}/result")
    def save_result(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        job_or_404(job_id)
        try:
            return manager.save_result(job_id, payload).model_dump(mode="json")
        except (ValueError, FileNotFoundError) as exc:
            raise public_error(exc, status_code=409) from exc

    @app.get("/api/jobs/{job_id}/source")
    def get_source(job_id: str, download: bool = Query(False)):
        job_or_404(job_id)
        try:
            path = manager.source_path(job_id)
        except FileNotFoundError as exc:
            raise public_error(exc, status_code=404) from exc
        media_type = "application/pdf" if path.suffix.lower() == ".pdf" else "text/plain; charset=utf-8"
        return FileResponse(
            path,
            media_type=media_type,
            filename=path.name if download else None,
            content_disposition_type="attachment" if download else "inline",
        )

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict[str, Any]:
        job_or_404(job_id)
        return manager.cancel_job(job_id)

    @app.post("/api/jobs/{job_id}/restart", status_code=201)
    def restart_job(job_id: str) -> dict[str, Any]:
        job_or_404(job_id)
        try:
            return manager.restart_job(job_id)
        except (ValueError, FileNotFoundError) as exc:
            raise public_error(exc) from exc

    @app.delete("/api/jobs/{job_id}")
    def delete_job(job_id: str) -> dict[str, bool]:
        job_or_404(job_id)
        try:
            manager.delete_job(job_id)
        except ValueError as exc:
            raise public_error(exc, status_code=409) from exc
        return {"ok": True}

    @app.get("/app.js", include_in_schema=False)
    def app_js() -> FileResponse:
        return FileResponse(web_root / "app.js", media_type="text/javascript; charset=utf-8")

    @app.get("/styles.css", include_in_schema=False)
    def styles_css() -> FileResponse:
        return FileResponse(web_root / "styles.css", media_type="text/css; charset=utf-8")

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon() -> FileResponse:
        return FileResponse(web_root / "favicon.svg", media_type="image/svg+xml")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/editor", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/jobs", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/jobs/{job_id}", response_class=HTMLResponse, include_in_schema=False)
    def workbench(job_id: str | None = None) -> HTMLResponse:
        del job_id
        return HTMLResponse((web_root / "index.html").read_text(encoding="utf-8"))

    @app.on_event("shutdown")
    def shutdown_job_manager() -> None:
        manager.shutdown(wait=False)

    return app


app = create_app()
