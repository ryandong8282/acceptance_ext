# Acceptance Ext

Acceptance Ext is a grounded A/B extraction laboratory for Chinese construction quality-acceptance standards. It is intentionally not another PDF-to-text wrapper. The experiment asks whether a pluggable stack inspired by Docling, LangExtract, DocETL, OpenContracts, Unstract and vertical systems such as GROBID can reproduce the useful output of PDFex:

```text
PDF / Markdown
  → layout-aware parsing
  → chapter and clause segmentation
  → division item / inspection lot / acceptance item extraction
  → GB 50300 ontology attachment
  → exact source evidence and minimum-sampling rules
  → audit, human review and PDFex-compatible JSON
```

## Integrated ideas

- Docling adapter for layout-aware PDF conversion; PyMuPDF and Markdown baselines for fast local experiments.
- LangExtract adapter and an OpenAI-compatible structured-refinement hook. The deterministic extractor remains runnable without an API key.
- DocETL-style declarative task specification: extraction rules live in JSON rather than being buried in prompts.
- OpenContracts-style evidence and review: every item keeps the exact quote, source line/character span, page, bounding box when available, parser and source hash.
- Unstract-style deployment surface: CLI, JSON contracts and optional FastAPI API.
- GROBID-style evaluation: precision, recall, F1 and provenance coverage are first-class outputs.

## Install

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev,pdf]"
```

For the broadest experiment:

```bash
pip install -e ".[all,dev]"
```

## Smoke test

```bash
acceptance-ext extract sample_data/mini_standard.md \
  --parser markdown \
  --output output/mini.result.json \
  --review-html output/mini.review.html
```

Run a real Markdown produced by MinerU:

```bash
acceptance-ext extract "04_GB_50206-2012_木结构工程施工质量验收规范.md" \
  --parser markdown \
  --ontology /path/to/pdf_extractor/frontend/50300.json \
  --output output/gb50206.result.json \
  --pdfex-output output/gb50206.pdfex.json
```

Run a PDF through Docling:

```bash
acceptance-ext extract "GB 50206-2012 木结构工程施工质量验收规范.pdf" \
  --parser docling \
  --ontology /path/to/50300.json \
  --output output/gb50206.docling.json
```

Use `--parser pymupdf` for the lightweight PDF baseline. MinerU and PaddleOCR are external-command adapters so their exact installed CLI releases can be configured independently.

## A/B benchmark

```bash
acceptance-ext benchmark sample_data/mini_standard.md \
  --parsers markdown \
  --extractors heuristic \
  --output output/benchmark.json
```

Add `--gold path/to/gold.json` for precision, recall and F1. The report also includes grounding rate, sampling coverage, ontology attachment rate and elapsed time.

## Output contract

The canonical result contains `分项 → 检验批 → 验收项目`, plus `source_clause`, `source_quote`, `item_category`, `check_method`, `min_sampling`, exact `evidence[]`, `mapped_50300_path`, audit findings and run metrics. `--pdfex-output` emits a compatibility shape for side-by-side comparison with PDFex.

Use the full `frontend/50300.json` from PDFex for serious comparison; the bundled seed is deliberately small and exists only for smoke tests.

## Honest status

v0.1 is a working experiment and baseline, not a claim that the generic stack already beats PDFex. The decisive test is a blinded run on the same standards and the same human-labelled gold set. See `docs/EVALUATION.md`.
