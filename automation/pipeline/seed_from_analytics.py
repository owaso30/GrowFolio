"""GSC opportunities を keyword_queue へ流す。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config_loader import load_json, save_json
from seo.content_policy import filter_auto_keywords, is_allowed_for_auto
from seo.fingerprint import classify_cluster, find_cannibal_match, intent_fingerprint
from kw_research.research import classify_intent


GSC_BASE_SCORE = 9000  # 通常の research スコアより高く、優先公開させる


def seed_from_analytics(*, max_items: int = 10) -> dict[str, Any]:
    """
    analytics/latest.json の opportunities をキューへマージ。
    - 既存記事と同意図なら rewrite_candidate
    - そうでなければ pending（高スコア）
    """
    analytics = load_json("analytics/latest.json")
    published = load_json("published.json").get("posts", [])
    queue = load_json("keyword_queue.json")
    items = list(queue.get("keywords", []))
    by_kw = {k.get("keyword"): k for k in items if k.get("keyword")}

    opportunities = (analytics.get("gsc") or {}).get("opportunities") or []
    added_pending = 0
    added_rewrite = 0

    for opp in opportunities[: max_items * 2]:
        query = str(opp.get("query") or "").strip()
        if not query:
            continue
        if not is_allowed_for_auto(query):
            continue

        impressions = int(opp.get("impressions") or 0)
        position = float(opp.get("position") or 0)
        ctr = float(opp.get("ctr") or 0)
        score = GSC_BASE_SCORE + impressions - int(position * 10) - int(ctr * 1000)
        cluster = classify_cluster(query)
        fingerprint = sorted(intent_fingerprint(query))

        match = find_cannibal_match(query, published, queue_items=items)
        if match:
            entry = {
                "keyword": query,
                "intent": classify_intent(query),
                "score": score,
                "status": "rewrite_candidate",
                "source": "gsc_opportunity",
                "cluster": cluster,
                "fingerprint": fingerprint,
                "existing_slug": match.get("slug") or "",
                "existing_title": match.get("title") or "",
                "reason": " / ".join(opp.get("reasons") or []) or match.get("reason") or "",
                "gsc": {
                    "impressions": impressions,
                    "clicks": opp.get("clicks", 0),
                    "ctr": ctr,
                    "position": position,
                },
                "noted_at": datetime.now(timezone.utc).isoformat(),
            }
            existing = by_kw.get(query)
            if existing and existing.get("status") == "done":
                continue
            by_kw[query] = entry
            added_rewrite += 1
            continue

        entry = {
            "keyword": query,
            "intent": classify_intent(query),
            "score": score,
            "status": "pending",
            "source": "gsc_opportunity",
            "cluster": cluster,
            "fingerprint": fingerprint,
            "competition": "low",
            "gsc": {
                "impressions": impressions,
                "clicks": opp.get("clicks", 0),
                "ctr": ctr,
                "position": position,
            },
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        existing = by_kw.get(query)
        if existing and existing.get("status") == "done":
            continue
        if existing and existing.get("status") == "pending" and float(existing.get("score") or 0) >= score:
            continue
        by_kw[query] = entry
        added_pending += 1
        if added_pending >= max_items:
            break

    merged = list(by_kw.values())
    merged = filter_auto_keywords(merged)
    merged.sort(
        key=lambda x: (
            0 if x.get("status") == "pending" else 1,
            -float(x.get("score") or 0),
        )
    )
    result = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "keywords": merged,
    }
    save_json("keyword_queue.json", result)
    summary = {
        "added_pending": added_pending,
        "added_rewrite": added_rewrite,
        "pending_total": sum(1 for k in merged if k.get("status") == "pending"),
        "rewrite_total": sum(1 for k in merged if k.get("status") == "rewrite_candidate"),
    }
    print(f"seed-from-analytics: {summary}")
    return summary
