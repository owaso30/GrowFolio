"""自動投稿の対象キーワード判定。"""
from __future__ import annotations

from config_loader import load_yaml
from seo.keyword_safety import is_desired_for_auto, is_safe_for_auto


def get_auto_policy() -> dict:
    return load_yaml("content_policy.yaml").get("auto_publish", {})


def get_editorial_policy() -> dict:
    return load_yaml("content_policy.yaml").get("editorial", {})


def get_trend_config() -> dict:
    return load_yaml("content_policy.yaml").get("trend_research", {})


def get_intent_categories() -> dict:
    return load_yaml("content_policy.yaml").get("intent_categories", {})


def is_allowed_for_auto(keyword: str) -> bool:
    kw = (keyword or "").strip()
    if not kw:
        return False
    if not is_safe_for_auto(kw):
        return False
    if not is_desired_for_auto(kw):
        return False
    topics = get_auto_policy().get("topic_keywords", [])
    if not topics:
        return True
    kw_lower = kw.lower()
    return any(t.lower() in kw_lower for t in topics)


def filter_auto_keywords(keywords: list[dict]) -> list[dict]:
    """コンセプト外の pending を除外。done / rewrite_candidate は履歴として保持。"""
    kept: list[dict] = []
    for k in keywords:
        status = k.get("status")
        if status in ("done", "rewrite_candidate"):
            kept.append(k)
            continue
        if status == "pending" and is_allowed_for_auto(k.get("keyword", "")):
            kept.append(k)
    return kept
