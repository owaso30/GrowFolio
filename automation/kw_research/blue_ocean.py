"""ブルーオーシャンKW判定・スコアリング・ロングテール展開。"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Any

from config_loader import load_yaml
from seo.content_policy import get_intent_categories
from seo.keyword_safety import (
    has_specific_entity,
    is_generic_keyword,
    is_news_focus_keyword,
    is_procedure_keyword,
    is_reputation_framing_keyword,
    is_trend_focus_keyword,
)


def get_blue_ocean_config() -> dict:
    return load_yaml("content_policy.yaml").get("blue_ocean", {})


def _words(keyword: str) -> list[str]:
    return [w for w in re.split(r"[\s　]+", keyword.strip()) if w]


def has_intent_modifier(keyword: str) -> bool:
    cfg = get_blue_ocean_config()
    modifiers = cfg.get("intent_modifiers", [])
    kw = keyword.lower()
    return any(m.lower() in kw for m in modifiers)


def is_pure_head_term(keyword: str) -> bool:
    cfg = get_blue_ocean_config()
    heads = cfg.get("head_terms", [])
    words = _words(keyword)
    if len(words) <= 1:
        return True
    if len(words) == 2 and any(h.lower() in keyword.lower() for h in heads):
        return not has_intent_modifier(keyword)
    return False


def passes_blue_ocean_filter(keyword: str) -> bool:
    cfg = get_blue_ocean_config()
    kw = keyword.strip()
    if not kw:
        return False

    min_chars = cfg.get("min_chars", 10)
    min_words = cfg.get("min_words", 2)
    max_words = cfg.get("max_words", 10)
    words = _words(kw)

    if len(kw) < min_chars:
        return False
    if len(words) < min_words or len(words) > max_words:
        return False
    if is_pure_head_term(kw):
        return False

    for pattern in cfg.get("reject_patterns", []):
        if re.search(pattern, kw, re.IGNORECASE):
            return False

    # ニュース見出しそのまま（意図語なし・F相当）は除外 → ロングテール展開側で使う
    if cfg.get("reject_raw_news_headlines", True):
        if not has_intent_modifier(kw) and len(words) <= 4:
            news_markers = cfg.get("news_headline_markers", ["速報", "発表", "推移", "株価", "が発表", "へ"])
            if any(m in kw for m in news_markers):
                return False

    return True


def heuristic_competition_score(keyword: str, intent: str) -> tuple[float, str]:
    """SerpAPI なしでも使える競合推定。"""
    cfg = get_blue_ocean_config()
    score = 0.0
    words = _words(keyword)

    prefer_min = cfg.get("prefer_words_min", 3)
    if len(words) >= prefer_min:
        score += cfg.get("long_tail_bonus", 12)
    if has_intent_modifier(keyword):
        score += cfg.get("intent_modifier_bonus", 10)

    cats = get_intent_categories()
    cat = cats.get(intent, {})
    if intent in cfg.get("preferred_intents", ["A", "B", "C", "D", "E"]):
        score += cfg.get("high_intent_bonus", 8)

    if is_pure_head_term(keyword):
        score -= cfg.get("head_term_penalty", 25)

    level = "medium"
    if score >= 20:
        level = "low"
    elif score < 8:
        level = "high"
    return score, level


def analyze_serp(keyword: str) -> dict[str, Any] | None:
    key = os.environ.get("SERPAPI_KEY", "")
    if not key:
        return None

    cfg = get_blue_ocean_config().get("serp", {})
    q = urllib.parse.quote(keyword)
    url = f"https://serpapi.com/search.json?engine=google&q={q}&hl=ja&gl=jp&api_key={key}&num=10"
    timeout = float(os.environ.get("TREND_HTTP_TIMEOUT", "12"))
    retries = int(os.environ.get("TREND_HTTP_RETRIES", "2"))
    data: dict[str, Any] | None = None
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            break
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(attempt, 2))
    if data is None:
        print(f"  serp skip ({keyword[:40]}): {last_error}")
        return None

    organic = data.get("organic_results", [])
    authority = cfg.get("authority_domains", [])
    opportunity = cfg.get("opportunity_domains", [])

    auth_hits = 0
    opp_hits = 0
    for r in organic[:10]:
        link = (r.get("link") or "").lower()
        if any(d in link for d in authority):
            auth_hits += 1
        if any(d in link for d in opportunity):
            opp_hits += 1

    total = max(len(organic), 1)
    opp_ratio = opp_hits / total

    score_delta = 0.0
    score_delta += opp_hits * cfg.get("opportunity_domain_bonus", 4)
    score_delta -= auth_hits * cfg.get("authority_domain_penalty", 3)

    min_ratio = cfg.get("min_opportunity_ratio", 0.25)
    if opp_ratio >= min_ratio:
        score_delta += cfg.get("blue_ocean_serp_bonus", 15)
        level = "low"
    elif auth_hits >= cfg.get("red_ocean_authority_threshold", 6):
        score_delta -= cfg.get("red_ocean_serp_penalty", 20)
        level = "high"
    else:
        level = "medium"

    related = [r.get("query", "") for r in data.get("related_searches", []) if r.get("query")]
    paa = [q.get("question", "") for q in data.get("related_questions", []) if q.get("question")]

    return {
        "organic_count": len(organic),
        "authority_hits": auth_hits,
        "opportunity_hits": opp_hits,
        "opportunity_ratio": round(opp_ratio, 2),
        "score_delta": score_delta,
        "competition_level": level,
        "related_searches": related[:8],
        "people_also_ask": paa[:5],
    }


def score_keyword(
    keyword: str,
    intent: str,
    from_news: bool = False,
    serp: dict[str, Any] | None = None,
) -> tuple[float, dict[str, Any]]:
    cfg = get_blue_ocean_config()
    cats = get_intent_categories()
    cat = cats.get(intent, {"intent_depth": 2, "conversion": 2})

    base = cat.get("intent_depth", 2) * 10 + cat.get("conversion", 2) * 8
    base += min(len(keyword) / 20, 2)
    if from_news:
        base += cfg.get("trend_bonus", 5)
    if is_trend_focus_keyword(keyword) or is_news_focus_keyword(keyword):
        base += cfg.get("trend_focus_bonus", cfg.get("news_focus_bonus", 15))
    if has_specific_entity(keyword):
        base += cfg.get("specificity_bonus", 20)
    if is_procedure_keyword(keyword):
        base -= cfg.get("procedure_penalty", 40)
    if is_generic_keyword(keyword):
        base -= cfg.get("generic_penalty", 30)
    if is_reputation_framing_keyword(keyword):
        base -= cfg.get("reputation_penalty", 35)

    heuristic, level = heuristic_competition_score(keyword, intent)
    total = base + heuristic

    meta: dict[str, Any] = {
        "competition_level": level,
        "heuristic_score": round(heuristic, 1),
    }

    if serp:
        total += serp.get("score_delta", 0)
        meta["competition_level"] = serp.get("competition_level", level)
        meta["serp"] = {
            "authority_hits": serp.get("authority_hits"),
            "opportunity_hits": serp.get("opportunity_hits"),
            "opportunity_ratio": serp.get("opportunity_ratio"),
        }

    return round(total, 1), meta


def expand_long_tail_seeds(seeds: list[str], fetch_suggestions) -> list[str]:
    """トレンド種からロングテールKWを展開（サジェスト × 意図修飾語）。"""
    cfg = get_blue_ocean_config()
    modifiers = cfg.get("expansion_modifiers", [])
    max_per_seed = cfg.get("max_expansion_per_seed", 8)
    results: list[str] = []
    seen: set[str] = set()

    for seed in seeds:
        batch = [seed]
        for mod in modifiers[:10]:
            batch.append(f"{seed} {mod}".strip())
        for query in batch:
            for kw in fetch_suggestions(query)[:max_per_seed]:
                norm = kw.lower()
                if norm in seen:
                    continue
                seen.add(norm)
                results.append(kw)
    return results
