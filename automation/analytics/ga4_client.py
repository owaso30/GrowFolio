"""GA4 Data API クライアント。"""
from __future__ import annotations

from datetime import date
from typing import Any

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)

from analytics.auth import get_credentials


def _client() -> BetaAnalyticsDataClient:
    return BetaAnalyticsDataClient(credentials=get_credentials())


def _property_path(property_id: str) -> str:
    pid = property_id.strip()
    if pid.startswith("properties/"):
        return pid
    return f"properties/{pid}"


def _run(
    property_id: str,
    start: date,
    end: date,
    dimensions: list[str],
    metrics: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    request = RunReportRequest(
        property=_property_path(property_id),
        date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=m) for m in metrics],
        limit=limit,
    )
    response = _client().run_report(request)
    metric_names = [h.name for h in response.metric_headers]
    dim_names = [h.name for h in response.dimension_headers]
    rows: list[dict[str, Any]] = []
    for row in response.rows:
        item: dict[str, Any] = {}
        for i, name in enumerate(dim_names):
            item[name] = row.dimension_values[i].value
        for i, name in enumerate(metric_names):
            raw = row.metric_values[i].value
            try:
                if "." in raw:
                    item[name] = round(float(raw), 4)
                else:
                    item[name] = int(raw)
            except ValueError:
                item[name] = raw
        rows.append(item)
    return rows


def fetch_ga4_report(
    property_id: str,
    start: date,
    end: date,
    row_limit: int = 50,
) -> dict[str, Any]:
    totals_rows = _run(
        property_id,
        start,
        end,
        dimensions=[],
        metrics=["sessions", "totalUsers", "screenPageViews", "bounceRate", "averageSessionDuration"],
        limit=1,
    )
    totals = totals_rows[0] if totals_rows else {
        "sessions": 0,
        "totalUsers": 0,
        "screenPageViews": 0,
        "bounceRate": 0.0,
        "averageSessionDuration": 0.0,
    }
    channels = _run(
        property_id,
        start,
        end,
        dimensions=["sessionDefaultChannelGroup"],
        metrics=["sessions", "totalUsers", "screenPageViews"],
        limit=row_limit,
    )
    landings = _run(
        property_id,
        start,
        end,
        dimensions=["landingPagePlusQueryString"],
        metrics=["sessions", "totalUsers", "screenPageViews", "bounceRate"],
        limit=row_limit,
    )
    daily = _run(
        property_id,
        start,
        end,
        dimensions=["date"],
        metrics=["sessions", "screenPageViews", "totalUsers"],
        limit=400,
    )
    daily_sorted = sorted(daily, key=lambda r: r.get("date", ""))
    return {
        "property_id": _property_path(property_id),
        "totals": totals,
        "channels": channels,
        "landings": landings,
        "daily": daily_sorted,
    }
