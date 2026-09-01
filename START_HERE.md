# Start here

Acceptance Ext v0.1 is a runnable A/B experiment for grounded extraction of Chinese construction acceptance standards.

- Project guide: [`docs/PROJECT.md`](docs/PROJECT.md)
- Delivery scope: [`reports/DELIVERY.md`](reports/DELIVERY.md)
- Evaluation protocol: [`docs/EVALUATION.md`](docs/EVALUATION.md)
- Core pipeline: [`src/acceptance_ext/pipeline.py`](src/acceptance_ext/pipeline.py)
- Declarative task spec: [`config/gb_acceptance.json`](config/gb_acceptance.json)
- Synthetic smoke source: [`sample_data/mini_standard.md`](sample_data/mini_standard.md)

Quick run:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev,pdf]"
pytest -q
acceptance-ext extract sample_data/mini_standard.md --parser markdown --output output/mini.json --pdfex-output output/mini.pdfex.json --review-html output/mini.html
```

For a fair comparison, pass PDFex's complete `frontend/50300.json` through `--ontology`, run the same standard through both systems, and score against one frozen human-labelled gold result.
