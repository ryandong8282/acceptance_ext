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
                rows.append(
                    {
                        "parser": parser,
                        "extractor": extractor,
                        **document.metrics,
                        "score": score,
                    }
                )
            except Exception as exc:
                rows.append({"parser": parser, "extractor": extractor, "error": str(exc)})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print_json(output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    app()
