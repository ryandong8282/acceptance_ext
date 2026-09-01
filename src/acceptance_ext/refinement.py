from __future__ import annotations

import json
import os
from typing import Any

from .models import ResultDocument

SYSTEM_PROMPT = """You refine a grounded extraction of a Chinese construction acceptance standard.
Never invent an item. Preserve source_clause and source_quote exactly. You may improve names,
categories, check methods and minimum-sampling normalization only when supported by a quote.
Return one JSON object with a `tree` field matching the supplied shape."""


def openai_compatible_refine(document: ResultDocument) -> ResultDocument:
    if os.getenv("ACCEPTANCE_EXT_ENABLE_LLM", "false").lower() != "true":
        return document
    api_key = os.getenv("ACCEPTANCE_EXT_API_KEY", "")
    model = os.getenv("ACCEPTANCE_EXT_MODEL", "")
    if not api_key or not model:
        raise RuntimeError("ACCEPTANCE_EXT_API_KEY and ACCEPTANCE_EXT_MODEL are required")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install the llm extra: pip install -e '.[llm]'") from exc
    client = OpenAI(api_key=api_key, base_url=os.getenv("ACCEPTANCE_EXT_BASE_URL") or None)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": document.model_dump_json(exclude={"audit", "metrics"})},
        ],
    )
    payload: dict[str, Any] = json.loads(response.choices[0].message.content or "{}")
    candidate = document.model_copy(update={"tree": payload.get("tree", document.tree)})
    return ResultDocument.model_validate(candidate)


def langextract_available() -> bool:
    try:
        import langextract  # noqa: F401
    except ImportError:
        return False
    return True
