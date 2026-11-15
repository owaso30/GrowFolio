"""旬に合わせた保険KW。pending が枯れたときの投入口。"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from seo.content_policy import get_auto_policy, is_allowed_for_auto
from seo.fingerprint import classify_cluster, find_cannibal_match, intent_fingerprint
from kw_research.blue_ocean import passes_blue_ocean_filter, score_keyword


JST = ZoneInfo("Asia/Tokyo")


def current_month(*, now: datetime | None = None) -> int:
    stamp = now or datetime.now(JST)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=JST)
    return stamp.astimezone(JST).month


def seasonal_seed_keywords(*, month: int | None = None) -> list[str]:
    cfg = get_auto_policy().get("seasonal_keyword_seeds") or {}
    key = str(month or current_month())
    seeds = cfg.get(key) or cfg.get(int(key)) or []
    return [str(s).strip() for s in seeds if str(s).strip()]


def build_pending_entry(keyword: str, *, source: str = "seasonal_seed", score: float | None = None) -> dict[str, Any]:
    intent = "F"
    total, meta = score_keyword(keyword, intent, from_news=False, serp=None)
    return {
        "keyword": keyword,
        "intent": intent,
        "score": float(score if score is not None else max(total, 90.0)),
        "status": "pending",
        "source": source,
        "competition": meta.get("competition_level", "medium"),
        "cluster": classify_cluster(keyword),
        "fingerprint": sorted(intent_fingerprint(keyword)),
    }


def ensure_seasonal_pending(
    queue_items: list[dict[str, Any]],
    published: list[dict[str, Any]],
    *,
    month: int | None = None,
    min_pending: int = 3,
) -> list[dict[str, Any]]:
    """
    pending が足りないとき、今月の旬シードを pending に足す。
    既存の done / rewrite_candidate / pending と同じ文言は入れない。
    """
    items = list(queue_items)
    pending_count = sum(
        1
        for k in items
        if k.get("status") == "pending" and is_allowed_for_auto(k.get("keyword", ""))
    )
    if pending_count >= min_pending:
        return items

    existing = {str(k.get("keyword") or "").strip() for k in items if k.get("keyword")}
    added = 0
    for seed in seasonal_seed_keywords(month=month):
        if seed in existing:
            continue
        if not is_allowed_for_auto(seed):
            continue
        if not passes_blue_ocean_filter(seed):
            continue
        match = find_cannibal_match(
            seed,
            published,
            queue_items=items,
            queue_statuses=("done", "rewrite_candidate"),
        )
        if match:
            print(f"  seasonal skip cannibal: {seed[:50]} -> {match.get('slug') or match.get('title', '')[:40]}")
            continue
        items.append(build_pending_entry(seed))
        existing.add(seed)
        added += 1
        pending_count += 1
        print(f"  seasonal pending: {seed}")
        if pending_count >= min_pending:
            break

    if added:
        print(f"Seasonal seeds added: {added} (pending now {pending_count})")
    return items
