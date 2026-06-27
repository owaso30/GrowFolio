"""直近のIT・金融ニューストレンド取得（記事生成・KW調査用）。"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests

from seo.content_policy import get_trend_config

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"


def _parse_rss(xml_text: str, limit: int = 5) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    for item in root.findall(".//item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        source = (item.findtext("source") or "").strip()
        if title:
            items.append({"title": title, "link": link, "pub_date": pub, "source": source})
    return items


def _fetch_google_news(query: str, limit: int = 5) -> list[dict[str, str]]:
    url = GOOGLE_NEWS_RSS.format(query=quote(query))
    r = requests.get(url, headers={"User-Agent": "GrowfolioBot/1.0"}, timeout=15)
    r.raise_for_status()
    return _parse_rss(r.text, limit=limit)


def _fetch_serpapi_news(query: str, limit: int = 5) -> list[dict[str, str]]:
    import os

    key = os.environ.get("SERPAPI_KEY", "")
    if not key:
        return []
    url = (
        f"https://serpapi.com/search.json?engine=google_news"
        f"&q={quote(query)}&hl=ja&gl=jp&api_key={key}"
    )
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    out: list[dict[str, str]] = []
    for item in data.get("news_results", [])[:limit]:
        out.append({
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "pub_date": item.get("date", ""),
            "source": item.get("source", ""),
        })
    return out


def fetch_news_headlines(query: str, limit: int = 5) -> list[dict[str, str]]:
    return _fetch_serpapi_news(query, limit=limit) or _fetch_google_news(query, limit=limit)


def headline_to_keyword(title: str) -> str:
    """ニュース見出しを記事KW候補に整形。"""
    t = re.split(r"\s[-–|｜]", title)[0].strip()
    t = re.sub(r"[\(（].*?[\)）]", "", t).strip()
    t = re.sub(r"\s+", " ", t)
    if len(t) > 55:
        t = t[:55].rsplit(" ", 1)[0] if " " in t[:55] else t[:55]
    return t


def collect_trend_keywords(max_per_query: int = 4) -> list[dict[str, Any]]:
    """設定された news_queries からトレンドKW候補を収集。"""
    cfg = get_trend_config()
    queries = cfg.get("news_queries", [])
    seen: set[str] = set()
    results: list[dict[str, Any]] = []

    for query in queries:
        for headline in fetch_news_headlines(query, limit=max_per_query):
            kw = headline_to_keyword(headline["title"])
            norm = kw.lower()
            if len(kw) < 6 or norm in seen:
                continue
            seen.add(norm)
            results.append({
                "keyword": kw,
                "source": "news",
                "news_query": query,
                "headline": headline["title"],
            })
    return results


def fetch_trend_context(keyword: str, max_items: int = 8) -> dict[str, Any]:
    """キーワードに関連する直近ニュースを収集し、記事生成用テキストを返す。"""
    queries = [keyword]
    cfg = get_trend_config()
    for q in cfg.get("news_queries", [])[:3]:
        if q not in queries:
            queries.append(q)

    seen_titles: set[str] = set()
    headlines: list[dict[str, str]] = []

    for q in queries:
        batch = fetch_news_headlines(q, limit=4)
        for item in batch:
            norm = re.sub(r"\s+", "", item["title"].lower())
            if norm in seen_titles:
                continue
            seen_titles.add(norm)
            headlines.append(item)
            if len(headlines) >= max_items:
                break
        if len(headlines) >= max_items:
            break

    lines = [
        f"収集日時（UTC）: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        "以下は公開前に収集したヘッドラインです。本文では出典を明記し、未確認の数値は断定しないこと。",
        "",
    ]
    for i, h in enumerate(headlines, 1):
        src = f"（{h['source']}）" if h.get("source") else ""
        date = f" [{h['pub_date']}]" if h.get("pub_date") else ""
        lines.append(f"{i}. {h['title']}{src}{date}")
        if h.get("link"):
            lines.append(f"   URL: {h['link']}")

    if not headlines:
        lines.append("（直近ニュースは取得できませんでした。キーワード周辺の一般的な業界動向を事実と考察に分けて記述してください。）")

    return {
        "headlines": headlines,
        "context_text": "\n".join(lines),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
