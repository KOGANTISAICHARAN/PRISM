from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_inspector
from ..db import get_db
from ..models import Investigation, Report, ReportUpdate, User
from ..serializers import evidence_dict, investigation_dict
from ..services.evidence import store_evidence

router = APIRouter(tags=["investigations"])

CHECKLIST_ITEMS = [
    "visit_establishment",
    "verify_licence_details",
    "inspect_kitchen_hygiene",
    "inspect_storage_conditions",
    "inspect_food_handling",
    "record_observations",
    "collect_inspection_evidence",
    "determine_further_investigation",
]

CITIZEN_MESSAGES = {
    "INVESTIGATION_REQUIRED": "An inspection has been initiated for your report.",
    "VERIFIED": "Inspection completed. The reported issue was verified by an inspector.",
    "NOT_VERIFIED": "Inspection completed. The reported issue was not verified during inspection.",
    "ACTIONED": "Inspection completed and action has been recorded by the authority.",
    "CLOSED": "Your report has been closed.",
}

DECISION_STATUSES = ["VERIFIED", "NOT_VERIFIED", "ACTIONED", "CLOSED"]


class StartIn(BaseModel):
    report_id: str
    notes: str = ""


@router.post("/investigations", status_code=201)
def start_investigation(payload: StartIn, db: Session = Depends(get_db), user: User = Depends(require_inspector)):
    report = db.get(Report, payload.report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    existing = db.scalar(select(Investigation).where(Investigation.report_id == report.id))
    if existing:
        return investigation_dict(existing)

    inv = Investigation(
        report_id=report.id,
        inspector_id=user.id,
        inspector_name=user.name,
        status="IN_PROGRESS",
        checklist={item: False for item in CHECKLIST_ITEMS},
        notes=payload.notes,
    )
    report.status = "INVESTIGATION_REQUIRED"
    db.add(inv)
    db.add(
        ReportUpdate(
            report_id=report.id,
            status="INVESTIGATION_REQUIRED",
            message=CITIZEN_MESSAGES["INVESTIGATION_REQUIRED"],
            actor_role="inspector",
        )
    )
    db.commit()
    db.refresh(inv)
    return investigation_dict(inv)


class UpdateIn(BaseModel):
    checklist: dict[str, bool] | None = None
    notes: str | None = None
    findings: str | None = None
    status: str | None = None


@router.patch("/investigations/{investigation_id}")
def update_investigation(
    investigation_id: str,
    payload: UpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_inspector),
):
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigation not found")
    if payload.checklist is not None:
        inv.checklist = {**(inv.checklist or {}), **{k: bool(v) for k, v in payload.checklist.items()}}
    if payload.notes is not None:
        inv.notes = payload.notes
    if payload.findings is not None:
        inv.findings = payload.findings
    if payload.status is not None:
        if payload.status not in ("IN_PROGRESS", "COMPLETED"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "status must be IN_PROGRESS or COMPLETED")
        inv.status = payload.status
    db.commit()
    db.refresh(inv)
    return investigation_dict(inv)


@router.post("/investigations/{investigation_id}/evidence", status_code=201)
def upload_inspection_evidence(
    investigation_id: str,
    kind: str = Form("inspection_photo"),
    geo_lat: float | None = Form(None),
    geo_lng: float | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_inspector),
):
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigation not found")
    report = db.get(Report, inv.report_id)
    if not kind.startswith("inspection"):
        kind = f"inspection_{kind}"
    record = store_evidence(db, report, file, user, kind=kind, geo_lat=geo_lat, geo_lng=geo_lng)
    return evidence_dict(record)


class DecisionIn(BaseModel):
    status: str
    decision_note: str
    findings: str | None = None


@router.post("/investigations/{investigation_id}/decision")
def record_decision(
    investigation_id: str,
    payload: DecisionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_inspector),
):
    """Human decision. AI never sets these statuses."""
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigation not found")
    if payload.status not in DECISION_STATUSES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"status must be one of {DECISION_STATUSES}")
    if not payload.decision_note.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A decision note is required")

    report = db.get(Report, inv.report_id)
    inv.decision = payload.status
    inv.decision_note = payload.decision_note.strip()
    inv.findings = payload.findings or inv.findings
    inv.decided_at = datetime.now(timezone.utc)
    inv.status = "COMPLETED"
    report.status = payload.status
    if payload.status in ("VERIFIED", "ACTIONED"):
        vendor = report.vendor
        if vendor:
            vendor.verified_history_count += 1
    db.add(
        ReportUpdate(
            report_id=report.id,
            status=payload.status,
            message=CITIZEN_MESSAGES.get(payload.status, "Your report status has been updated."),
            actor_role="inspector",
        )
    )
    db.commit()
    db.refresh(inv)
    return {"investigation": investigation_dict(inv), "report_status": report.status}


@router.get("/investigations/report/{report_id}")
def by_report(report_id: str, db: Session = Depends(get_db), user: User = Depends(require_inspector)):
    rows = db.scalars(select(Investigation).where(Investigation.report_id == report_id)).all()
    return {"investigations": [investigation_dict(i) for i in rows]}
