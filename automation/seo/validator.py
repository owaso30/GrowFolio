"""SEO・法令チェック。"""
from __future__ import annotations

import re

from config_loader import load_yaml

NG_PATTERNS = [
    (r"絶対儲かる", "収益は保証されません"),
    (r"元本保証", "元本保証はありません"),
    (r"損しない", "損失のリスクがあります"),
    (r"必ず稼げ", "成果は保証されません"),
    (r"確実に儲", "成果は保証されません"),
]


def apply_legal_filter(text: str) -> str:
    for pattern, replacement in NG_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def validate_title(title: str, max_chars: int | None = None) -> str:
    """投稿タイトルを整形。省略記号（…）での切り詰めは行わない。"""
    title = title.strip()
    if max_chars is None:
        max_chars = int(load_yaml("site.yaml").get("content", {}).get("title_max_chars", 0))
    if max_chars > 0 and len(title) > max_chars:
        return title[:max_chars].rstrip()
    return title


def validate_meta(description: str, target: int = 120) -> str:
    description = description.strip()
    if len(description) <= target:
        return description
    return description[: target - 1] + "…"


def strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()
