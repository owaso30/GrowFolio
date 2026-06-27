"""LLM 応答から記事 JSON を安全にパース。"""
from __future__ import annotations

import json
from typing import Any

from json_repair import repair_json

from seo.validator import strip_markdown_fences


def _candidates(text: str) -> list[str]:
    text = text.strip()
    out = [text]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        sliced = text[start : end + 1]
        if sliced != text:
            out.append(sliced)
    return out


def parse_llm_json(raw: str) -> dict[str, Any]:
    text = strip_markdown_fences(raw)
    if text and not text.lstrip().startswith("{"):
        text = "{" + text.lstrip()

    last_error: json.JSONDecodeError | None = None
    for candidate in _candidates(text):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError as exc:
            last_error = exc

    try:
        repaired = repair_json(text)
        data = json.loads(repaired)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        if isinstance(exc, json.JSONDecodeError):
            last_error = exc

    msg = str(last_error) if last_error else "unknown JSON error"
    raise ValueError(f"LLM JSON parse failed: {msg}") from last_error
