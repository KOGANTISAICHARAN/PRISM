from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_inspector
from ..db import get_db
from ..models import Cluster, Investigation, Report, ReportUpdate, RiskScore, User, Vendor
from ..serializers import cluster_dict, investigation_dict, report_detail, report_summary, vendor_dict
from ..services.clustering import similar_reports
from ..services.hotspots import hotspots
from ..services.risk import _aware, compute_vendor_risk

router = APIRouter(prefix="/inspector", tags=["inspector"])

OPEN_STATUSES = ("NEW", "UNDER_REVIEW", "INVESTIGATION_REQUIRED")


def _priority(report: Report, risk: RiskScore | None) -> tuple[int, str]:
    score = risk.score if risk else 0
    base = score + report.severity * 4
    band = "HIGH" if base >= 70 else "MEDIUM" if base >= 40 else "LOW"
    return base, band


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(require_inspector)):
    reports = db.scalars(select(Report)).all()
    risks = {r.vendor_id: r for r in db.scalars(select(RiskScore))}
    now = datetime.now(timezone.utc)
    bands = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for r in reports:
        if r.status in OPEN_STATUSES:
            bands[_priority(r, risks.get(r.vendor_id))[1]] += 1
    clusters = db.scalars(select(Cluster)).all()
    spots = hotspots(db)
    investigations = db.scalars(select(Investigation).where(Investigation.status == "IN_PROGRESS")).all()
    return {
        "new_reports": len([r for r in reports if r.status == "NEW"]),
        "high_priority": bands["HIGH"],
        "medium_priority": bands["MEDIUM"],
        "low_priority": bands["LOW"],
        "active_investigations": len(investigations),
        "potential_hotspots": len([h for h in spots if h["level"] == "red"]),
        "new_clusters": len([c for c in clusters if _aware(c.created_at) >= now - timedelta(days=7)]),
        "total_clusters": len(clusters),
        "total_reports": len(reports),
        "demo_data": any(r.is_demo for r in reports),
    }


@router.get("/cases")
def cases(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_inspector),
):
    risks = {r.vendor_id: r for r in db.scalars(select(RiskScore))}
    query = select(Report).order_by(Report.created_at.desc())
    rows = db.scalars(query).all()
    if status_filter:
        wanted = {s.strip().upper() for s in status_filter.split(",")}
        rows = [r for r in rows if r.status in wanted]

    out = []
    for r in rows:
        risk = risks.get(r.vendor_id)
        base, band = _priority(r, risk)
        cluster = db.get(Cluster, r.cluster_id) if r.cluster_id else None
        out.append(
            {
                **report_summary(r),
                "priority_score": base,
                "priority_band": band,
                "risk_score": risk.score if risk else 0,
                "risk_factors": risk.factors if risk else {},
                "cluster_label": cluster.label if cluster else None,
                "cluster_theme": cluster.theme if cluster else None,
                "evidence_count": len(r.evidence),
                "has_investigation": bool(
                    db.scalar(select(Investigation).where(Investigation.report_id == r.id))
                ),
            }
        )
    out.sort(key=lambda c: (-c["priority_score"], c["created_at"] or ""))
    return {"count": len(out), "cases": out}


@router.get("/cases/{report_id}")
def case_detail(report_id: str, db: Session = Depends(get_db), user: User = Depends(require_inspector)):
    report = db.get(Report, report_id) or db.scalar(
        select(Report).where(Report.reference == report_id.upper())
    )
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")

    detail = report_detail(db, report, include_confidential=True)
    vendor = db.get(Vendor, report.vendor_id) if report.vendor_id else None
    risk = compute_vendor_risk(db, vendor) if vendor else None
    vendor_reports = (
        db.scalars(
            select(Report).where(Report.vendor_id == vendor.id).order_by(Report.created_at.desc())
        ).all()
        if vendor
        else []
    )
    cluster = db.get(Cluster, report.cluster_id) if report.cluster_id else None
    cluster_reports = (
        db.scalars(select(Report).where(Report.cluster_id == cluster.id)).all() if cluster else []
    )
    similar = similar_reports(db, report)

    return {
        "report": detail,
        "vendor": vendor_dict(vendor) if vendor else None,
        "risk": risk,
        "vendor_reports": [report_summary(r) for r in vendor_reports],
        "cluster": cluster_dict(cluster, list(cluster_reports)) if cluster else None,
        "similar_reports": [{**report_summary(r), "similarity": round(s, 3)} for r, s in similar],
        "hotspots": [
            h
            for h in hotspots(db)
            if vendor
            and vendor.latitude
            and abs(h["latitude"] - vendor.latitude) < 0.05
            and abs(h["longitude"] - (vendor.longitude or 0)) < 0.05
        ],
        "investigations": [
            investigation_dict(i)
            for i in db.scalars(select(Investigation).where(Investigation.report_id == report.id))
        ],
    }


@router.post("/cases/{report_id}/review")
def mark_under_review(report_id: str, db: Session = Depends(get_db), user: User = Depends(require_inspector)):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    if report.status == "NEW":
        report.status = "UNDER_REVIEW"
        db.add(
            ReportUpdate(
                report_id=report.id,
                status="UNDER_REVIEW",
                message="An authorised reviewer has opened your report for review.",
                actor_role="inspector",
            )
        )
        db.commit()
    return report_detail(db, report, include_confidential=True)
