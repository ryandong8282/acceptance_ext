# Acceptance Ext v0.1 build status

This repository is the A/B experiment implementation for grounded extraction of Chinese construction acceptance standards.

## v0.1 scope

- Pluggable document parsers: Markdown, PyMuPDF, Docling, MinerU CLI and PaddleOCR CLI adapters.
- Typed acceptance schema: chapter → division item → inspection lot → acceptance item.
- Exact evidence/provenance: source quote, page, bounding box, line/character span, parser and source hash.
- Deterministic extraction baseline plus optional OpenAI-compatible and LangExtract refinement.
- GB 50300 ontology mapping.
- Minimum-sampling rule extraction and reference detection.
- Audit/validation, human-review JSONL/HTML, PDFex-compatible export and A/B evaluation.
- Optional DocETL, OpenContracts and Unstract payload adapters.
- Synthetic tests and real-GB smoke-run scripts; source standards are intentionally not committed.

## Verification target

The project must not claim that a model is stronger merely because it runs. A valid comparison uses the same PDF/Markdown inputs and a human-labelled gold set, then reports item precision/recall/F1, grounding rate, sampling-rule accuracy, ontology attachment rate, latency and cost.

The canonical implementation is under `src/acceptance_ext/`; `reports/VERIFICATION.md` records local test and smoke-run results when present.
