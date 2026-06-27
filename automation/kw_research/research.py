"""トレンド × ブルーオーシャンKW調査。"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

from rapidfuzz import fuzz

from config_loader import load_json, save_json
from content.trends import collect_trend_keywords, headline_to_keyword
from kw_research.blue_ocean import (
    analyze_serp,
    expand_long_tail_seeds,
    get_blue_ocean_config,
    passes_blue_ocean_filter,
    score_keyword,
)
from seo.content_policy import get_trend_config, is_allowed_for_auto

SUGGEST_URL = "https://suggestqueries.google.com/complete/search?client=firefox&hl=ja&q="


def fetch_suggestions(seed: str) -> list[str]:
    import requests
    import urllib.parse

    url = SUGGEST_URL + urllib.parse.quote(seed)
    r = requests.get(url, headers={"User-Agent": "GrowfolioBot/1.0"}, timeout=15)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    data = r.json()
    return [s for s in data[1] if isinstance(s, str)]


def classify_intent(keyword: str) -> str:
    kw = keyword.lower()
    if any(x in kw for x in ["できない", "エラー", "反映されない", "対処", "トラブル", "ログイン"]):
        return "A"
    if any(x in kw for x in ["税金", "確定申告", "雑所得"]):
        return "B"
    if any(x in kw for x in ["怪しい", "危険", "比較", "vs", "やめた", "評判"]):
        return "D"
    if any(x in kw for x in ["運用報告", "実際", "レビュー", "体験", "口コミ"]):
        return "E"
    if any(x in kw for x in ["始め方", "やり方", "手順", "方法", "設定", "初心者"]):
        return "C"
    return "F"


def is_duplicate(keyword: str, published: list[dict], threshold: int = 75) -> bool:
    for post in published:
        title = post.get("title", "")
        if fuzz.partial_ratio(keyword, title) >= threshold:
            return True
        for tag in post.get("keywords", []):
            if fuzz.ratio(keyword, tag) >= threshold:
                return True
    return False


def _try_add(
    candidates: dict[str, dict[str, Any]],
    keyword: str,
    published: list[dict],
    existing: set[str],
    *,
    from_news: bool = False,
    source: str = "suggest",
    serp: dict[str, Any] | None = None,
) -> bool:
    kw = keyword.strip()
    if not kw or kw in existing or is_duplicate(kw, published):
        return False
    if not is_allowed_for_auto(kw):
        return False
    if not passes_blue_ocean_filter(kw):
        return False

    intent = classify_intent(kw)
    total_score, meta = score_keyword(kw, intent, from_news=from_news, serp=serp)

    cfg = get_blue_ocean_config()
    if serp and meta.get("competition_level") == "high" and cfg.get("reject_high_competition", True):
        if serp.get("authority_hits", 0) >= cfg.get("serp", {}).get("red_ocean_authority_threshold", 6):
            return False

    if kw in candidates and candidates[kw]["score"] >= total_score:
        return False

    entry: dict[str, Any] = {
        "keyword": kw,
        "intent": intent,
        "score": total_score,
        "status": "pending",
        "source": source,
        "competition": meta.get("competition_level", "medium"),
    }
    if meta.get("serp"):
        entry["serp"] = meta["serp"]
    candidates[kw] = entry
    existing.add(kw)
    return True


def _rescore_with_serp(candidates: dict[str, dict[str, Any]], limit: int = 25) -> None:
    if not os.environ.get("SERPAPI_KEY"):
        return

    ranked = sorted(candidates.values(), key=lambda x: x["score"], reverse=True)[:limit]
    for item in ranked:
        serp = analyze_serp(item["keyword"])
        if not serp:
            continue
        intent = item["intent"]
        total, meta = score_keyword(
            item["keyword"],
            intent,
            from_news=item.get("source", "").startswith("trend"),
            serp=serp,
        )
        cfg = get_blue_ocean_config()
        if meta.get("competition_level") == "high" and cfg.get("reject_high_competition", True):
            if serp.get("authority_hits", 0) >= cfg.get("serp", {}).get("red_ocean_authority_threshold", 6):
                candidates.pop(item["keyword"], None)
                continue
        item["score"] = total
        item["competition"] = meta.get("competition_level", "medium")
        if meta.get("serp"):
            item["serp"] = meta["serp"]


def _collect_trend_seeds() -> list[str]:
    """ニュース見出し → ロングテール展開用の種（見出しそのものは基本KWにしない）。"""
    seeds: list[str] = []
    seen: set[str] = set()
    trend_cfg = get_trend_config()

    for item in collect_trend_keywords(max_per_query=4):
        kw = item["keyword"]
        if passes_blue_ocean_filter(kw):
            norm = kw.lower()
            if norm not in seen:
                seeds.append(kw)
                seen.add(norm)
        else:
            topic = headline_to_keyword(item.get("headline", kw))
            for part in re_split_topic(topic):
                norm = part.lower()
                if norm not in seen and len(part) >= 4:
                    seeds.append(part)
                    seen.add(norm)

    for seed in trend_cfg.get("suggest_seeds", []):
        norm = seed.lower()
        if norm not in seen:
            seeds.append(seed)
            seen.add(norm)

    return seeds[:30]


def re_split_topic(topic: str) -> list[str]:
    parts = re.split(r"[\s　、・]+", topic)
    return [p.strip() for p in parts if len(p.strip()) >= 3]


def _ingest_related_from_serp(
    candidates: dict[str, dict[str, Any]],
    published: list[dict],
    existing: set[str],
) -> None:
    """SerpAPI の related searches / PAA から追加ロングテールを拾う。"""
    if not os.environ.get("SERPAPI_KEY"):
        return

    cfg = get_blue_ocean_config()
    if not cfg.get("use_serp_related", True):
        return

    for kw, item in list(candidates.items())[:15]:
        serp = analyze_serp(kw)
        if not serp:
            continue
        for related in serp.get("related_searches", []) + serp.get("people_also_ask", []):
            _try_add(candidates, related, published, existing, source="serp_related")


def run_research(max_keywords: int = 10) -> dict[str, Any]:
    published = load_json("published.json").get("posts", [])
    queue = load_json("keyword_queue.json")
    existing = {k["keyword"] for k in queue.get("keywords", []) if k.get("status") != "done"}
    trend_cfg = get_trend_config()

    candidates: dict[str, dict[str, Any]] = {}

    trend_seeds = _collect_trend_seeds()
    for kw in expand_long_tail_seeds(trend_seeds, fetch_suggestions):
        _try_add(candidates, kw, published, existing, from_news=True, source="trend_expand")

    for seed in trend_cfg.get("news_queries", []) + trend_cfg.get("suggest_seeds", []):
        for kw in fetch_suggestions(seed)[:15]:
            _try_add(candidates, kw, published, existing, source="suggest")

    _ingest_related_from_serp(candidates, published, existing)

    _rescore_with_serp(candidates)

    ranked = sorted(candidates.values(), key=lambda x: x["score"], reverse=True)
    new_items = ranked[:max_keywords]

    merged = [
        k for k in queue.get("keywords", [])
        if k.get("status") == "pending" and is_allowed_for_auto(k.get("keyword", ""))
    ]
    seen = {k["keyword"] for k in merged}
    for item in new_items:
        if item["keyword"] not in seen:
            merged.append(item)
            seen.add(item["keyword"])

    merged.sort(key=lambda x: x.get("score", 0), reverse=True)
    result = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "keywords": merged,
    }
    save_json("keyword_queue.json", result)
    return result
