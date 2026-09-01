# Acceptance Ext v0.1 delivery

The repository now contains a runnable grounded extraction experiment rather than a design-only skeleton.

## Delivered

- Markdown, PyMuPDF and Docling parsers.
- External MinerU and PaddleOCR command adapters.
- Typed `分项 → 检验批 → 验收项目` contracts.
- Exact evidence with source hash, parser, quote, page, bbox and line/character offsets where available.
- Deterministic acceptance-item extraction and optional OpenAI-compatible constrained refinement.
- Minimum-sampling extraction, GB 50300 ontology attachment and deterministic audit.
- Canonical JSON, PDFex-compatible JSON and self-contained human-review HTML.
- DocETL/OpenContracts/Unstract integration blueprints.
- CLI benchmark, real-standard smoke runner, synthetic fixture, tests and CI.

## Important boundary

A smoke run proves that the program executes and produces the intended shape. It does **not** prove accuracy. A fair comparison with PDFex requires a frozen gold set created from the same standards and reports item precision/recall/F1, grounding accuracy, minimum-sampling accuracy, wrong ontology attachment rate, latency, cost and human correction time.

## Quick check

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,pdf]"
pytest -q
acceptance-ext extract sample_data/mini_standard.md --parser markdown --output output/mini.json --pdfex-output output/mini.pdfex.json --review-html output/mini.html
```

For real comparison, pass PDFex's complete `frontend/50300.json` through `--ontology`; the bundled ontology is deliberately only a smoke-test seed.
