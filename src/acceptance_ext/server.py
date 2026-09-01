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
