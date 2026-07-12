"""Google Search Console API クライアント。"""
from __future__ import annotations

from datetime import date
from typing import Any

from googleapiclient.discovery import build

from analytics.auth import get_credentials


def _service():
    return build("searchconsole", "v1", credentials=get_credentials(), cache_discovery=False)


def resolve_site_url(preferred: str) -> str:
    """登録済みプロパティ一覧から preferred に最も近い siteUrl を返す。"""
    svc = _service()
    sites = svc.sites().list().execute().get("siteEntry", [])
    urls = [s.get("siteUrl", "") for s in sites if s.get("siteUrl")]
    if not urls:
        raise RuntimeError(
            "Search Console にアクセス可能なプロパティがありません。"
            "サービスアカウントをプロパティのユーザー（閲覧者以上）に追加してください。"
        )

    preferred = preferred.rstrip("/") + "/"
    domain = preferred.replace("https://", "").replace("http://", "").rstrip("/")
    candidates = [
        preferred,
        preferred.rstrip("/"),
        f"sc-domain:{domain}",
        f"https://{domain}/",
        f"http://{domain}/",
    ]
    for c in candidates:
        if c in urls:
            return c

    # 部分一致フォールバック
    for u in urls:
        if domain in u:
            return u
    raise RuntimeError(
        f"GSC プロパティが見つかりません（希望: {preferred}）。利用可能: {urls}"
    )


def _query(
    site_url: str,
    start: date,
    end: date,
    dimensions: list[str],
    row_limit: int,
) -> list[dict[str, Any]]:
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": dimensions,
        "rowLimit": row_limit,
        "startRow": 0,
    }
    resp = (
        _service()
        .searchanalytics()
        .query(siteUrl=site_url, body=body)
        .execute()
    )
    rows = []
    for row in resp.get("rows", []):
        keys = row.get("keys", [])
        item: dict[str, Any] = {
            "clicks": int(row.get("clicks", 0)),
            "impressions": int(row.get("impressions", 0)),
            "ctr": round(float(row.get("ctr", 0)), 6),
            "position": round(float(row.get("position", 0)), 2),
        }
        for i, dim in enumerate(dimensions):
            item[dim] = keys[i] if i < len(keys) else ""
        rows.append(item)
    return rows


def fetch_gsc_report(
    site_url: str,
    start: date,
    end: date,
    row_limit: int = 100,
) -> dict[str, Any]:
    resolved = resolve_site_url(site_url)
    totals_rows = _query(resolved, start, end, [], 1)
    totals = totals_rows[0] if totals_rows else {
        "clicks": 0,
        "impressions": 0,
        "ctr": 0.0,
        "position": 0.0,
    }
    queries = _query(resolved, start, end, ["query"], row_limit)
    pages = _query(resolved, start, end, ["page"], row_limit)
    return {
        "site_url": resolved,
        "totals": {
            "clicks": totals.get("clicks", 0),
            "impressions": totals.get("impressions", 0),
            "ctr": totals.get("ctr", 0.0),
            "position": totals.get("position", 0.0),
        },
        "top_queries": queries,
        "top_pages": pages,
    }
