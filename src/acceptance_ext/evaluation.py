from __future__ import annotations

import json
import re
from pathlib import Path

from .models import ResultDocument


def _norm(value: str | None) -> str:
    return re.sub(r"\W+", "", value or "", flags=re.UNICODE).lower()


def _keys(document: ResultDocument) -> set[tuple[str, str]]:
    return {
        (_norm(item.source_clause), _norm(item.name))
        for division in document.tree
        for lot in division.children
        for item in lot.children
    }


def evaluate(prediction: ResultDocument, gold_path: Path) -> dict[str, float | int]:
    raw = json.loads(gold_path.read_text(encoding="utf-8-sig"))
    gold = ResultDocument.model_validate(raw)
    predicted_keys = _keys(prediction)
    gold_keys = _keys(gold)
    true_positive = len(predicted_keys & gold_keys)
    precision = true_positive / len(predicted_keys) if predicted_keys else 0.0
    recall = true_positive / len(gold_keys) if gold_keys else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positive": true_positive,
        "predicted": len(predicted_keys),
        "gold": len(gold_keys),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
