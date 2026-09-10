"""Hotspot aggregation.

Reports are bucketed into ~1.1 km geo cells. A red cell is a signal for
investigation, never proof that businesses in that area are unsafe. Exact
citizen coordinates are not returned - only aggregated cell centroids.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Report, RiskScore, Vendor
from .risk import _aware

CELL = 0.01  # ~1.1 km


def hotspots(db: Session, days: int = 30) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    reports = [
        r
        for r in db.scalars(select(Report))
        if r.latitude and r.longitude and _aware(r.created_at) >= since
    ]
    risk_by_vendor = {r.vendor_id: r for r in db.scalars(select(RiskScore))}
    vendors = {v.id: v for v in db.scalars(select(Vendor))}

    cells: dict[tuple[int, int], list[Report]] = defaultdict(list)
    for r in reports:
        cells[(round(r.latitude / CELL), round(r.longitude / CELL))].append(r)

    now = datetime.now(timezone.utc)
    out = []
    for (gy, gx), group in cells.items():
        last7 = [r for r in group if _aware(r.created_at) >= now - timedelta(days=7)]
        prev7 = [r for r in group if now - timedelta(days=14) <= _aware(r.created_at) < now - timedelta(days=7)]
        growth = ((len(last7) - len(prev7)) / len(prev7) * 100) if prev7 else (100.0 * len(last7) if last7 else 0.0)
        vendor_ids = {r.vendor_id for r in group if r.vendor_id}
        max_risk = max((risk_by_vendor[v].score for v in vendor_ids if v in risk_by_vendor), default=0)
        count = len(group)
        level = "red" if (count >= 6 or max_risk >= 70) else "yellow" if (count >= 3 or max_risk >= 40) else "green"
        out.append(
            {
                "id": f"{gy}_{gx}",
                "latitude": round(gy * CELL, 5),
                "longitude": round(gx * CELL, 5),
                "report_count": count,
                "reports_last_7_days": len(last7),
                "growth_pct": round(growth, 1),
                "level": level,
                "max_vendor_risk": max_risk,
                "area": next((r.area for r in group if r.area), "Unspecified area"),
                "establishments": sorted({vendors[v].name for v in vendor_ids if v in vendors}),
                "issue_types": sorted({r.issue_type for r in group}),
                "clusters": sorted({r.cluster_id for r in group if r.cluster_id}),
                "note": "Aggregated signal for investigation prioritisation. Not proof of any violation.",
            }
        )
    return sorted(out, key=lambda h: (-h["report_count"], h["area"]))
