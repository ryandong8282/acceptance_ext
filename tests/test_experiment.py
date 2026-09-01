import json
from pathlib import Path

from acceptance_ext.experiment import run_experiment


FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic_standard.md"


def test_baseline_experiment_bundle(tmp_path):
    out = tmp_path / "experiment"
    manifest = run_experiment(FIXTURE, out_dir=out, parser="markdown")

    assert manifest["status"] == "completed"
    assert manifest["steps"]["baseline"]["acceptance_item_count"] == 4
    assert (out / "baseline" / "result.json").exists()
    assert (out / "baseline" / "result.pdfex.json").exists()
    assert (out / "baseline" / "review.html").exists()
    persisted = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert persisted["steps"]["baseline"]["status"] == "succeeded"
