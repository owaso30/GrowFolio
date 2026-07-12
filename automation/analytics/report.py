"""GSC + GA4 を取得し data/analytics/ に保存する。"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from analytics.ga4_client import fetch_ga4_report
from analytics.gsc_client import fetch_gsc_report
from config_loader import DATA_DIR, load_env, load_json, load_yaml, save_json


def _period(days: int) -> tuple[date, date]:
    # GSC/GA4 とも当日データは不完全なことが多いので end は昨日
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    return start, end


def _opportunities(
    queries: list[dict[str, Any]],
    min_impressions: int,
    min_position: float,
    max_ctr: float,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for q in queries:
        impressions = int(q.get("impressions", 0))
        position = float(q.get("position", 0))
        ctr = float(q.get("ctr", 0))
        if impressions < min_impressions:
            continue
        reasons: list[str] = []
        if position >= min_position:
            reasons.append(f"順位{position}（改善余地）")
        if ctr <= max_ctr and impressions >= min_impressions:
            reasons.append(f"CTR {ctr:.2%}（タイトル/ディスクリ改善候補）")
        if not reasons:
            continue
        out.append({
            "query": q.get("query", ""),
            "clicks": q.get("clicks", 0),
            "impressions": impressions,
            "ctr": ctr,
            "position": position,
            "reasons": reasons,
        })
    out.sort(key=lambda x: (-x["impressions"], x["position"]))
    return out[:30]


def _monthly_pv_estimate(pageviews: int, days: int) -> int:
    if days <= 0:
        return 0
    return int(round(pageviews * (30 / days)))


def _kpi_status(monthly_pv: int, cfg: dict[str, Any], article_count: int) -> dict[str, Any]:
    targets = cfg.get("targets", {})
    t3_min = int(targets.get("month_3_pv_min", 1000))
    t3_max = int(targets.get("month_3_pv_max", 3000))
    if monthly_pv < t3_min:
        band = "below_3m_min"
    elif monthly_pv <= t3_max:
        band = "within_3m_target"
    else:
        band = "above_3m_target"
    return {
        "article_count": article_count,
        "monthly_pv_estimate": monthly_pv,
        "target_3m": [t3_min, t3_max],
        "band": band,
    }


def _render_summary(report: dict[str, Any]) -> str:
    period = report["period"]
    gsc = report.get("gsc") or {}
    ga4 = report.get("ga4") or {}
    kpi = report.get("kpi") or {}
    gsc_t = gsc.get("totals") or {}
    ga4_t = ga4.get("totals") or {}
    opps = gsc.get("opportunities") or []

    lines = [
        f"# 週次アナリティクスサマリー",
        "",
        f"- 取得日時: `{report.get('fetched_at', '')}`",
        f"- 期間: `{period.get('start')}` ~ `{period.get('end')}`（{period.get('days')}日）",
        "",
        "## KPI",
        "",
        f"- 公開記事数: **{kpi.get('article_count', '-')}**",
        f"- 月間PV換算（GA4 pageviews x 30/日数）: **{kpi.get('monthly_pv_estimate', '-')}**",
        f"- 3ヶ月目標帯: {kpi.get('target_3m', [])} / 判定: `{kpi.get('band', '')}`",
        "",
        "## Search Console",
        "",
        f"- クリック: **{gsc_t.get('clicks', 0)}**",
        f"- 表示回数: **{gsc_t.get('impressions', 0)}**",
        f"- CTR: **{float(gsc_t.get('ctr', 0)):.2%}**",
        f"- 平均順位: **{gsc_t.get('position', 0)}**",
        "",
        "### リライト候補（上位）",
        "",
    ]
    if not opps:
        lines.append("- （該当なし / データ不足）")
    else:
        for o in opps[:10]:
            reasons = " / ".join(o.get("reasons", []))
            lines.append(
                f"- `{o.get('query')}` - 表示{o.get('impressions')} / "
                f"CTR {float(o.get('ctr', 0)):.2%} / 順位{o.get('position')} - {reasons}"
            )

    lines.extend([
        "",
        "## GA4",
        "",
        f"- セッション: **{ga4_t.get('sessions', 0)}**",
        f"- ユーザー: **{ga4_t.get('totalUsers', 0)}**",
        f"- PV: **{ga4_t.get('screenPageViews', 0)}**",
        f"- 直帰率: **{float(ga4_t.get('bounceRate', 0)):.2%}**",
        "",
        "### チャネル",
        "",
    ])
    for ch in (ga4.get("channels") or [])[:8]:
        lines.append(
            f"- {ch.get('sessionDefaultChannelGroup', '?')}: "
            f"sessions={ch.get('sessions', 0)} / PV={ch.get('screenPageViews', 0)}"
        )

    lines.extend(["", "### ランディング（上位）", ""])
    for lp in (ga4.get("landings") or [])[:10]:
        lines.append(
            f"- `{lp.get('landingPagePlusQueryString', '')}` - "
            f"sessions={lp.get('sessions', 0)} / PV={lp.get('screenPageViews', 0)}"
        )
    lines.append("")
    return "\n".join(lines)


def _append_trend(report: dict[str, Any]) -> None:
    """週次の要約だけを trend.json に追記（最大52件）。"""
    trend_name = "analytics/trend.json"
    existing = load_json(trend_name)
    points = existing.get("points", []) if existing else []
    gsc_t = (report.get("gsc") or {}).get("totals") or {}
    ga4_t = (report.get("ga4") or {}).get("totals") or {}
    kpi = report.get("kpi") or {}
    point = {
        "fetched_at": report.get("fetched_at"),
        "period_end": report.get("period", {}).get("end"),
        "gsc_clicks": gsc_t.get("clicks", 0),
        "gsc_impressions": gsc_t.get("impressions", 0),
        "gsc_ctr": gsc_t.get("ctr", 0),
        "gsc_position": gsc_t.get("position", 0),
        "ga4_sessions": ga4_t.get("sessions", 0),
        "ga4_users": ga4_t.get("totalUsers", 0),
        "ga4_pageviews": ga4_t.get("screenPageViews", 0),
        "monthly_pv_estimate": kpi.get("monthly_pv_estimate", 0),
        "article_count": kpi.get("article_count", 0),
    }
    # 同日再実行は上書き
    points = [p for p in points if p.get("period_end") != point["period_end"]]
    points.append(point)
    points = points[-52:]
    save_json(trend_name, {"updated_at": report.get("fetched_at"), "points": points})


def fetch_analytics(days: int | None = None, dry_run: bool = False) -> dict[str, Any]:
    load_env()
    cfg = load_yaml("analytics.yaml")
    site = load_yaml("site.yaml")
    period_days = days or int(cfg.get("period_days", 28))
    start, end = _period(period_days)

    gsc_site = os.environ.get("GSC_SITE_URL", "").strip() or site["site"]["url"]
    ga4_property = os.environ.get("GA4_PROPERTY_ID", "").strip()

    published = load_json("published.json")
    article_count = len(published.get("posts", [])) if published else 0

    if dry_run:
        preview = {
            "dry_run": True,
            "period": {"start": start.isoformat(), "end": end.isoformat(), "days": period_days},
            "gsc_site_url": gsc_site,
            "ga4_property_id": ga4_property or "(unset)",
            "article_count": article_count,
        }
        print(preview)
        return preview

    if not ga4_property:
        raise RuntimeError("GA4_PROPERTY_ID を設定してください（例: 123456789）")

    gsc = fetch_gsc_report(
        gsc_site,
        start,
        end,
        row_limit=int(cfg.get("gsc", {}).get("row_limit", 100)),
    )
    opp_cfg = cfg.get("opportunity", {})
    gsc["opportunities"] = _opportunities(
        gsc.get("top_queries", []),
        min_impressions=int(opp_cfg.get("min_impressions", 20)),
        min_position=float(opp_cfg.get("min_position", 8.0)),
        max_ctr=float(opp_cfg.get("max_ctr", 0.03)),
    )

    ga4 = fetch_ga4_report(
        ga4_property,
        start,
        end,
        row_limit=int(cfg.get("ga4", {}).get("row_limit", 50)),
    )

    pageviews = int(ga4.get("totals", {}).get("screenPageViews", 0) or 0)
    monthly_pv = _monthly_pv_estimate(pageviews, period_days)
    kpi = _kpi_status(monthly_pv, cfg.get("kpi", {}), article_count)

    report: dict[str, Any] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "period": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": period_days,
        },
        "gsc": gsc,
        "ga4": ga4,
        "kpi": kpi,
    }

    save_json("analytics/latest.json", report)
    _append_trend(report)

    summary = _render_summary(report)
    summary_path = DATA_DIR / "analytics" / "summary.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary, encoding="utf-8")

    # Windows (cp932) コンソールでも落ちないようにする
    try:
        print(summary)
    except UnicodeEncodeError:
        print(summary.encode("cp932", errors="replace").decode("cp932"))
    print(f"\nSaved: {DATA_DIR / 'analytics' / 'latest.json'}")
    print(f"Saved: {summary_path}")
    print(f"Saved: {DATA_DIR / 'analytics' / 'trend.json'}")
    return report
