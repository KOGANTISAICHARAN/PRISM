"""Transparent risk engine (0-100).

The score is a TRIAGE / PRIORITISATION signal for human reviewers only. It is not
a legal or scientific determination. Every component is returned with its raw
value, normalised value and weight so the inspector UI can explain the score.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.engine import SEVERITY
from ..models import Evidence, Report, RiskScore, Vendor
from .clustering import similar_count_for_vendor

WEIGHTS = {
    "recent_volume": 0.25,
    "similarity": 0.20,
    "growth": 0.20,
    "severity": 0.15,
    "geo_concentration": 0.10,
    "verification_history": 0.10,
}


def _aware(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def band_for(score: int) -> str:
    return "HIGH" if score >= 70 else "MEDIUM" if score >= 40 else "LOW"


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def compute_vendor_risk(db: Session, vendor: Vendor, persist: bool = True) -> dict:
    reports = list(db.scalars(select(Report).where(Report.vendor_id == vendor.id)))
    now = datetime.now(timezone.utc)
    total = len(reports)
    last7 = [r for r in reports if _aware(r.created_at) >= now - timedelta(days=7)]
    prev7 = [r for r in reports if now - timedelta(days=14) <= _aware(r.created_at) < now - timedelta(days=7)]

    growth_pct = (
        ((len(last7) - len(prev7)) / len(prev7) * 100.0)
        if prev7
        else (100.0 * len(last7) if last7 else 0.0)
    )

    similar_count, mean_similarity = similar_count_for_vendor(db, vendor.id)

    severities = [SEVERITY.get(r.issue_type, 1) for r in reports] or [0]
    avg_severity = sum(severities) / len(severities)

    # geographic concentration: share of reports within 2 km of the vendor location
    concentrated = 0
    located = [r for r in reports if r.latitude and r.longitude]
    if located and vendor.latitude and vendor.longitude:
        concentrated = sum(
            1
            for r in located
            if _haversine_km(vendor.latitude, vendor.longitude, r.latitude, r.longitude) <= 2.0
        )
    geo_share = concentrated / len(located) if located else 0.0

    report_ids = [r.id for r in reports]
    with_evidence = 0
    if report_ids:
        with_evidence = len(
            {
                e.report_id
                for e in db.scalars(select(Evidence).where(Evidence.report_id.in_(report_ids)))
            }
        )
    evidence_share = with_evidence / total if total else 0.0
    verified = len([r for r in reports if r.status in ("VERIFIED", "ACTIONED")]) + vendor.verified_history_count

    norm = {
        "recent_volume": min(len(last7) / 10.0, 1.0),
        "similarity": min(similar_count / 10.0, 1.0) * 0.6 + min(mean_similarity, 1.0) * 0.4,
        "growth": min(max(growth_pct, 0.0) / 200.0, 1.0),
        "severity": min(avg_severity / 4.0, 1.0),
        "geo_concentration": geo_share,
        "verification_history": min(verified / 3.0, 1.0) * 0.6 + evidence_share * 0.4,
    }
    score = round(sum(norm[k] * WEIGHTS[k] for k in WEIGHTS) * 100)
    score = max(0, min(100, int(score)))

    factors = {
        "total_reports": total,
        "reports_last_7_days": len(last7),
        "reports_previous_7_days": len(prev7),
        "similar_reports": similar_count,
        "mean_similarity": round(mean_similarity, 2),
        "growth_pct": round(growth_pct, 1),
        "avg_severity": round(avg_severity, 2),
        "geo_concentration_pct": round(geo_share * 100, 1),
        "reports_with_evidence": with_evidence,
        "verified_history": verified,
        "components": [
            {
                "key": key,
                "label": key.replace("_", " ").title(),
                "weight_pct": round(WEIGHTS[key] * 100),
                "normalised": round(norm[key], 3),
                "contribution": round(norm[key] * WEIGHTS[key] * 100, 1),
            }
            for key in WEIGHTS
        ],
        "explanations": _explanations(total, len(last7), similar_count, growth_pct, geo_share, with_evidence),
        "disclaimer": (
            "Risk score is a prioritisation signal for human review only. It does not confirm "
            "contamination or establish legal responsibility."
        ),
    }

    row = db.scalar(select(RiskScore).where(RiskScore.vendor_id == vendor.id))
    if persist:
        if row is None:
            row = RiskScore(vendor_id=vendor.id)
            db.add(row)
        row.score = score
        row.band = band_for(score)
        row.factors = factors
        db.commit()

    return {"vendor_id": vendor.id, "vendor_name": vendor.name, "score": score, "band": band_for(score), "factors": factors}


def _explanations(total, last7, similar, growth, geo_share, with_evidence) -> list[str]:
    out = [f"{total} total report(s) associated with this establishment"]
    if similar:
        out.append(f"{similar} report(s) describe a semantically similar issue")
    if last7:
        out.append(f"{last7} report(s) received in the last 7 days")
    if growth > 0:
        out.append(f"Complaint activity change: +{growth:.0f}%")
    if geo_share:
        out.append(f"{geo_share * 100:.0f}% of located reports are concentrated within 2 km")
    if with_evidence:
        out.append(f"{with_evidence} report(s) include supporting evidence")
    return out


def recompute_all(db: Session) -> None:
    for vendor in db.scalars(select(Vendor)):
        compute_vendor_risk(db, vendor)
