"""Evidence Vault: immutable, hash-verified evidence records with an append-only audit log."""

from __future__ import annotations

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Evidence, EvidenceAuditLog, Report, User
from ..storage import extract_capture_timestamp, sha256_bytes, storage


def _validate(file: UploadFile, data: bytes) -> str:
    content_type = file.content_type or "application/octet-stream"
    if not any(content_type.startswith(p) for p in settings.allowed_mime_list):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"File type not allowed: {content_type}")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File exceeds {settings.max_upload_mb} MB limit")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    return content_type


def audit(db: Session, evidence_id: str, action: str, actor: User | None, detail: str | None = None) -> None:
    db.add(
        EvidenceAuditLog(
            evidence_id=evidence_id,
            action=action,
            actor_id=actor.id if actor else None,
            actor_label=f"{actor.name} ({actor.role})" if actor else "anonymous",
            detail=detail,
        )
    )
    db.commit()


def store_evidence(
    db: Session,
    report: Report,
    file: UploadFile,
    actor: User | None,
    kind: str = "citizen_photo",
    geo_lat: float | None = None,
    geo_lng: float | None = None,
) -> Evidence:
    data = file.file.read()
    content_type = _validate(file, data)
    digest = sha256_bytes(data)  # hashed server-side, before storage
    key, url = storage.put(data, file.filename or "evidence", content_type)

    record = Evidence(
        report_id=report.id,
        file_url=url,
        storage_key=key,
        file_name=file.filename or "evidence",
        file_type=content_type,
        file_size=len(data),
        sha256_hash=digest,
        kind=kind,
        uploaded_by=actor.id if actor else None,
        uploader_role=actor.role if actor else "citizen",
        geo_lat=geo_lat,
        geo_lng=geo_lng,
        capture_timestamp=extract_capture_timestamp(data, content_type),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    audit(db, record.id, "CREATE", actor, f"kind={kind}; sha256={digest[:16]}...")
    return record


def can_access(evidence: Evidence, user: User | None, report: Report) -> bool:
    if user is None:
        return False
    if user.role == "inspector":
        return True
    return report.user_id == user.id
