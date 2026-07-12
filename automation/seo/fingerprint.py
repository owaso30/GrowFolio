"""意図指紋・クラスター判定・重複ガード。"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from rapidfuzz import fuzz

from config_loader import load_yaml


def get_auto_publish_config() -> dict[str, Any]:
    return load_yaml("content_policy.yaml").get("auto_publish", {}) or {}


def _normalize_text(*parts: str) -> str:
    text = " ".join(p for p in parts if p).lower()
    text = text.replace("-", " ").replace("_", " ").replace("　", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_entities(*parts: str) -> set[str]:
    """テキストから正規化エンティティ集合を抽出。"""
    cfg = get_auto_publish_config()
    aliases: dict[str, list[str]] = cfg.get("entity_aliases", {}) or {}
    text = _normalize_text(*parts)
    found: set[str] = set()
    for canonical, variants in aliases.items():
        keys = [canonical] + list(variants or [])
        # 長い表記からマッチ
        for variant in sorted({_normalize_text(v) for v in keys}, key=len, reverse=True):
            if variant and variant in text:
                found.add(canonical)
                break
    return found


def intent_fingerprint(*parts: str) -> frozenset[str]:
    return frozenset(extract_entities(*parts))


def classify_cluster(keyword: str, title: str = "", slug: str = "") -> str:
    """bitradex / tax / it / other を返す。"""
    cfg = get_auto_publish_config()
    clusters: dict[str, Any] = cfg.get("clusters", {}) or {}
    text = _normalize_text(keyword, title, slug)
    # 優先順: bitradex > tax > it
    for name in ("bitradex", "tax", "it"):
        spec = clusters.get(name) or {}
        for token in spec.get("match_any", []) or []:
            if _normalize_text(token) in text:
                return name
    return "other"


def _token_set(text: str) -> set[str]:
    tokens = re.split(r"[\s　、・|/｜]+", _normalize_text(text))
    return {t for t in tokens if len(t) >= 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_cannibal_match(
    keyword: str,
    published: list[dict[str, Any]],
    *,
    queue_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """
    同意図の既存記事（またはキュー済み）を返す。
    戻り値例: {"slug": "...", "title": "...", "reason": "..."}
    """
    cfg = get_auto_publish_config().get("fingerprint", {}) or {}
    min_shared = int(cfg.get("min_shared_entities", 2))
    fuzzy_threshold = int(cfg.get("fuzzy_threshold", 72))
    fuzzy_entity = int(cfg.get("fuzzy_with_entity_threshold", 55))
    jaccard_threshold = float(cfg.get("jaccard_threshold", 0.45))

    kw_entities = extract_entities(keyword)
    kw_tokens = _token_set(keyword)

    corpus: list[dict[str, Any]] = []
    for post in published:
        corpus.append({
            "slug": post.get("slug", ""),
            "title": post.get("title", ""),
            "keywords": post.get("keywords") or [],
            "source": "published",
        })
    for item in queue_items or []:
        if item.get("status") not in ("pending", "done", "rewrite_candidate"):
            continue
        corpus.append({
            "slug": item.get("existing_slug") or item.get("slug") or "",
            "title": item.get("keyword", ""),
            "keywords": [item.get("keyword", "")],
            "source": "queue",
        })

    for row in corpus:
        title = str(row.get("title") or "")
        slug = str(row.get("slug") or "")
        tags = [str(t) for t in (row.get("keywords") or [])]
        blob = " ".join([title, slug, *tags])
        row_entities = extract_entities(blob)
        shared = kw_entities & row_entities

        fuzzy_title = fuzz.partial_ratio(keyword, title) if title else 0
        fuzzy_tag = max((fuzz.ratio(keyword, t) for t in tags), default=0)
        fuzzy_best = max(fuzzy_title, fuzzy_tag)
        jacc = _jaccard(kw_tokens, _token_set(blob))

        if len(shared) >= min_shared:
            return {
                "slug": slug,
                "title": title,
                "reason": f"shared_entities={sorted(shared)}",
                "source": row.get("source"),
            }
        if shared and fuzzy_best >= fuzzy_entity:
            return {
                "slug": slug,
                "title": title,
                "reason": f"entity+fuzzy shared={sorted(shared)} fuzzy={fuzzy_best}",
                "source": row.get("source"),
            }
        if fuzzy_best >= fuzzy_threshold and (shared or jacc >= jaccard_threshold):
            return {
                "slug": slug,
                "title": title,
                "reason": f"fuzzy={fuzzy_best} jaccard={jacc:.2f}",
                "source": row.get("source"),
            }
        if jacc >= max(jaccard_threshold, 0.6):
            return {
                "slug": slug,
                "title": title,
                "reason": f"jaccard={jacc:.2f}",
                "source": row.get("source"),
            }
    return None


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def count_cluster_publishes(
    queue_items: list[dict[str, Any]],
    published: list[dict[str, Any]],
    *,
    days: int,
) -> dict[str, int]:
    """直近 N 日の自動投稿クラスター件数。"""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    counts = {"bitradex": 0, "tax": 0, "it": 0, "other": 0}

    for item in queue_items:
        if item.get("status") != "done":
            continue
        ts = _parse_iso(item.get("published_at"))
        if not ts or ts < since:
            continue
        cluster = item.get("cluster") or classify_cluster(item.get("keyword", ""))
        counts[cluster] = counts.get(cluster, 0) + 1

    # published.json の source=auto も補完（published_at が無い場合は直近扱いしない）
    for post in published:
        if post.get("source") != "auto":
            continue
        ts = _parse_iso(post.get("published_at"))
        if ts and ts < since:
            continue
        if not ts:
            continue
        cluster = classify_cluster(
            " ".join(post.get("keywords") or []),
            str(post.get("title") or ""),
            str(post.get("slug") or ""),
        )
        counts[cluster] = counts.get(cluster, 0) + 1

    return counts


def quota_allows(cluster: str, queue_items: list[dict], published: list[dict]) -> tuple[bool, str]:
    """週次／月次クォータを満たすか。"""
    cfg = get_auto_publish_config()
    weekly = cfg.get("weekly_quota") or {}
    monthly = cfg.get("monthly_quota") or {}

    week_counts = count_cluster_publishes(queue_items, published, days=7)
    month_counts = count_cluster_publishes(queue_items, published, days=30)

    if cluster in weekly:
        limit = int(weekly.get(cluster, 0))
        used = int(week_counts.get(cluster, 0))
        if used >= limit:
            return False, f"weekly_quota {cluster} {used}/{limit}"

    if cluster in monthly:
        limit = int(monthly.get(cluster, 0))
        used = int(month_counts.get(cluster, 0))
        if used >= limit:
            return False, f"monthly_quota {cluster} {used}/{limit}"

    # weekly に無いクラスター（other 等）で weekly.other が 0 なら拒否
    if cluster == "other" and "other" in weekly and int(weekly.get("other", 0)) <= 0:
        return False, "weekly_quota other=0"

    if cluster == "it" and "it" not in weekly:
        # IT は weekly 未定義でも monthly のみ
        if "it" in monthly and int(month_counts.get("it", 0)) >= int(monthly.get("it", 0)):
            return False, f"monthly_quota it {month_counts.get('it', 0)}/{monthly.get('it', 0)}"

    return True, "ok"
