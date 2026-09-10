from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import Evidence, EvidenceAuditLog, Report, User
from ..serializers import evidence_dict
from ..services.evidence import audit, can_access, store_evidence
from ..storage import sha256_bytes, storage

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.post("", status_code=201)
def upload_evidence(
    report_id: str = Form(...),
    kind: str = Form("citizen_photo"),
    geo_lat: float | None = Form(None),
    geo_lng: float | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    if user.role != "inspector" and report.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorised for this report")
    if user.role == "citizen" and kind.startswith("inspection"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only inspectors may upload inspection evidence")
    record = store_evidence(db, report, file, user, kind=kind, geo_lat=geo_lat, geo_lng=geo_lng)
    return evidence_dict(record)


@router.get("/report/{report_id}")
def list_for_report(report_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    if user.role != "inspector" and report.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorised for this report")
    return {"evidence": [evidence_dict(e) for e in report.evidence]}


def _load(db: Session, evidence_id: str, user: User) -> tuple[Evidence, Report]:
    record = db.get(Evidence, evidence_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    report = db.get(Report, record.report_id)
    if not can_access(record, user, report):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorised for this evidence")
    return record, report


@router.get("/{evidence_id}")
def get_evidence(evidence_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    record, _ = _load(db, evidence_id, user)
    audit(db, record.id, "VIEW", user)
    logs = db.scalars(
        select(EvidenceAuditLog)
        .where(EvidenceAuditLog.evidence_id == record.id)
        .order_by(EvidenceAuditLog.created_at)
    ).all()
    return evidence_dict(record, include_audit=list(logs))


@router.get("/{evidence_id}/download")
def download_evidence(evidence_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    record, _ = _load(db, evidence_id, user)
    data = storage.read(record.storage_key)
    verified = sha256_bytes(data) == record.sha256_hash
    audit(db, record.id, "DOWNLOAD", user, f"integrity_verified={verified}")
    return Response(
        content=data,
        media_type=record.file_type,
        headers={
            "Content-Disposition": f'attachment; filename="{record.file_name}"',
            "X-PRISM-SHA256": record.sha256_hash,
            "X-PRISM-Integrity-Verified": str(verified).lower(),
        },
    )


@router.get("/{evidence_id}/verify")
def verify_evidence(evidence_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Recompute the SHA-256 of the stored bytes and compare with the recorded hash."""
    record, _ = _load(db, evidence_id, user)
    data = storage.read(record.storage_key)
    recomputed = sha256_bytes(data)
    audit(db, record.id, "EXPORT", user, "integrity verification")
    return {
        "evidence_id": record.id,
        "recorded_hash": record.sha256_hash,
        "recomputed_hash": recomputed,
        "integrity_verified": recomputed == record.sha256_hash,
        "checked_at": None,
    }


@router.get("/file/{key:path}")
def serve_file(key: str, db: Session = Depends(get_db)):
    """Serve locally-stored evidence bytes (inline preview). Requires a known storage key."""
    record = db.scalar(select(Evidence).where(Evidence.storage_key == key))
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence file not found")
    data = storage.read(key)
    return Response(content=data, media_type=record.file_type, headers={"Cache-Control": "private, max-age=300"})
