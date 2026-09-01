#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acceptance_ext.pipeline import ExtractionPipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Acceptance Ext against real GB Markdown/PDF files without committing sources."
    )
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--parser", default="markdown")
    parser.add_argument("--extractor", default="heuristic")
    parser.add_argument("--ontology", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/generated/real-smoke"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    started = time.perf_counter()
    for source in args.inputs:
        row: dict = {"source": source.name, "parser": args.parser, "extractor": args.extractor}
        try:
            output = args.output_dir / f"{source.stem}.{args.parser}.{args.extractor}.json"
            pdfex = args.output_dir / f"{source.stem}.{args.parser}.{args.extractor}.pdfex.json"
            review = args.output_dir / f"{source.stem}.{args.parser}.{args.extractor}.review.html"
            document, _ = ExtractionPipeline(
                parser=args.parser,
                extractor=args.extractor,
                ontology_path=args.ontology,
            ).run_to_files(source, output, pdfex, review)
            row.update({"status": "ok", **document.metrics, "audit_count": len(document.audit)})
        except Exception as exc:
            row.update({"status": "failed", "error": str(exc)})
        rows.append(row)

    aggregate = {
        "documents": len(rows),
        "succeeded": sum(row.get("status") == "ok" for row in rows),
        "failed": sum(row.get("status") == "failed" for row in rows),
        "acceptance_items": sum(int(row.get("acceptance_item_count", 0)) for row in rows),
        "elapsed_seconds": round(time.perf_counter() - started, 4),
        "note": "Smoke metrics measure pipeline behavior, not extraction accuracy. Accuracy requires a gold set.",
        "runs": rows,
    }
    report = args.output_dir / "summary.json"
    report.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))
    return 0 if aggregate["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
