from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..ai.engine import ISSUE_LABELS, ISSUE_TYPES, SEVERITY
from ..auth import current_user
from ..db import get_db
from ..models import AIAssessment, Report, ReportUpdate, User, Vendor
from ..serializers import report_detail, report_summary
from ..services.clustering import recompute_clusters
from ..services.risk import compute_vendor_risk

router = APIRouter(tags=["reports"])


def next_reference(db: Session) -> str:
    for _ in range(30):
        ref = f"PR-{random.randint(10000, 99999)}"
        if not db.scalar(select(Report).where(Report.reference == ref)):
            return ref
    return f"PR-{int(datetime.now(timezone.utc).timestamp()) % 100000}"


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip()[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def resolve_vendor(db: Session, name: str, area: str | None, lat: float | None, lng: float | None) -> Vendor:
    vendor = db.scalar(select(Vendor).where(func.lower(Vendor.name) == name.strip().lower()))
    if vendor is None:
        vendor = Vendor(name=name.strip(), area=area, latitude=lat, longitude=lng, address=area)
        db.add(vendor)
        db.flush()
    else:
        if vendor.latitude is None and lat is not None:
            vendor.latitude, vendor.longitude = lat, lng
        if not vendor.area and area:
            vendor.area = area
    return vendor


class ReportIn(BaseModel):
    vendor_name: str = Field(min_length=2, max_length=200)
    food_item: str | None = None
    issue_type: str = "other_visible_condition"
    user_description: str = Field(default="", max_length=4000)
    incident_datetime: str | None = None
    location_text: str | None = None
    area: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    evidence_available: str | None = None
    ai_assessment: dict[str, Any] | None = None


@router.post("/reports", status_code=201)
def create_report(payload: ReportIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    issue_type = payload.issue_type if payload.issue_type in ISSUE_TYPES else "other_visible_condition"
    area = payload.area or (payload.location_text.split(",")[-1].strip() if payload.location_text else None)
    vendor = resolve_vendor(db, payload.vendor_name, area, payload.latitude, payload.longitude)

    report = Report(
        reference=next_reference(db),
        user_id=user.id,
        vendor_id=vendor.id,
        vendor_name=vendor.name,
        food_item=payload.food_item,
        issue_type=issue_type,
        user_description=payload.user_description,
        incident_datetime=parse_dt(payload.incident_datetime),
        location_text=payload.location_text,
        area=area,
        latitude=payload.latitude,
        longitude=payload.longitude,
        evidence_available=payload.evidence_available,
        severity=SEVERITY.get(issue_type, 1),
        status="NEW",
    )
    db.add(report)
    db.flush()

    if payload.ai_assessment:
        a = payload.ai_assessment
        db.add(
            AIAssessment(
                report_id=report.id,
                source="vision",
                detected_issue=a.get("detected_issue") or ISSUE_LABELS.get(issue_type, issue_type),
                risk_level=a.get("risk_level") or "Moderate",
                confidence=float(a.get("confidence") or 0.0),
                explanation=a.get("explanation") or "",
                model=a.get("model") or "prism-demo-vision",
            )
        )
    db.add(
        ReportUpdate(
            report_id=report.id,
            status="NEW",
            message="Report submitted and evidence recorded in the Evidence Vault.",
            actor_role="system",
        )
    )
    db.commit()
    db.refresh(report)
    return report_detail(db, report)


@router.post("/reports/{report_id}/finalize")
def finalize_report(report_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Run intelligence passes (clustering + risk) after evidence upload completes."""
    report = db.get(Report, report_id)
    if report is None or (user.role != "inspector" and report.user_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    recompute_clusters(db)
    if report.vendor_id:
        compute_vendor_risk(db, db.get(Vendor, report.vendor_id))
    db.refresh(report)
    return report_detail(db, report)


@router.get("/reports")
def my_reports(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(
        select(Report).where(Report.user_id == user.id).order_by(Report.created_at.desc())
    ).all()
    return {"count": len(rows), "reports": [report_summary(r) for r in rows]}


@router.get("/reports/{identifier}")
def get_report(identifier: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    report = db.get(Report, identifier) or db.scalar(
        select(Report).where(Report.reference == identifier.upper())
    )
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    if user.role != "inspector" and report.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only view your own reports")
    return report_detail(db, report, include_confidential=user.role == "inspector")
