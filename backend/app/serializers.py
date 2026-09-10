from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ai.engine import DISCLAIMER, ISSUE_LABELS
from .models import Cluster, Evidence, EvidenceAuditLog, Investigation, Report, RiskScore, Vendor

STATUS_FLOW = ["NEW", "UNDER_REVIEW", "INVESTIGATION_REQUIRED", "VERIFIED", "ACTIONED", "CLOSED"]

CITIZEN_STATUS_LABELS = {
    "NEW": "Report Submitted",
    "UNDER_REVIEW": "Under Review",
    "INVESTIGATION_REQUIRED": "Investigation Required",
    "VERIFIED": "Verified by Inspector",
    "NOT_VERIFIED": "Not Verified During Inspection",
    "ACTIONED": "Actioned",
    "CLOSED": "Closed",
}


def iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def evidence_dict(e: Evidence, include_audit: list[EvidenceAuditLog] | None = None) -> dict:
    data = {
        "id": e.id,
        "report_id": e.report_id,
        "file_url": e.file_url,
        "file_name": e.file_name,
        "file_type": e.file_type,
        "file_size": e.file_size,
        "sha256_hash": e.sha256_hash,
        "kind": e.kind,
        "uploader_role": e.uploader_role,
        "geo_lat": e.geo_lat,
        "geo_lng": e.geo_lng,
        "capture_timestamp": iso(e.capture_timestamp),
        "uploaded_at": iso(e.uploaded_at),
        "is_demo": e.is_demo,
    }
    if include_audit is not None:
        data["audit_log"] = [
            {
                "id": a.id,
                "action": a.action,
                "actor": a.actor_label,
                "detail": a.detail,
                "timestamp": iso(a.created_at),
            }
            for a in include_audit
        ]
    return data


def assessment_dict(a) -> dict:
    return {
        "id": a.id,
        "source": a.source,
        "detected_issue": a.detected_issue,
        "risk_level": a.risk_level,
        "confidence": round(a.confidence, 2),
        "explanation": a.explanation,
        "model": a.model,
        "created_at": iso(a.created_at),
        "disclaimer": DISCLAIMER,
    }


def cluster_dict(c: Cluster, reports: list[Report] | None = None) -> dict:
    data = {
        "id": c.id,
        "label": c.label,
        "theme": c.theme,
        "report_count": c.report_count,
        "dominant_vendor": c.dominant_vendor,
        "dominant_area": c.dominant_area,
        "avg_similarity": round(c.avg_similarity, 2),
        "criteria": c.criteria,
        "created_at": iso(c.created_at),
        "note": "Clustering identifies patterns between reports. It is not proof of a violation.",
    }
    if reports is not None:
        data["reports"] = [report_summary(r) for r in reports]
    return data


def report_summary(r: Report) -> dict:
    return {
        "id": r.id,
        "reference": r.reference,
        "vendor_name": r.vendor_name,
        "vendor_id": r.vendor_id,
        "food_item": r.food_item,
        "issue_type": r.issue_type,
        "issue_label": ISSUE_LABELS.get(r.issue_type, r.issue_type),
        "status": r.status,
        "status_label": CITIZEN_STATUS_LABELS.get(r.status, r.status),
        "area": r.area,
        "location_text": r.location_text,
        "latitude": r.latitude,
        "longitude": r.longitude,
        "severity": r.severity,
        "incident_datetime": iso(r.incident_datetime),
        "created_at": iso(r.created_at),
        "cluster_id": r.cluster_id,
        "is_demo": r.is_demo,
        "description_preview": (r.user_description or "")[:160],
    }


def timeline(report: Report) -> list[dict]:
    reached = {u.status for u in report.updates} | {"NEW"}
    current_index = STATUS_FLOW.index(report.status) if report.status in STATUS_FLOW else 1
    steps = []
    for i, status in enumerate(STATUS_FLOW):
        if status in reached or i < current_index:
            state = "done"
        elif status == report.status:
            state = "current"
        else:
            state = "pending"
        steps.append({"status": status, "label": CITIZEN_STATUS_LABELS[status], "state": state})
    if report.status == "NOT_VERIFIED":
        steps.append({"status": "NOT_VERIFIED", "label": CITIZEN_STATUS_LABELS["NOT_VERIFIED"], "state": "current"})
    return steps


def report_detail(db: Session, r: Report, include_confidential: bool = False) -> dict:
    data = report_summary(r)
    data.update(
        {
            "user_description": r.user_description,
            "evidence_available": r.evidence_available,
            "evidence": [evidence_dict(e) for e in r.evidence],
            "ai_assessments": [assessment_dict(a) for a in r.assessments],
            "updates": [
                {"status": u.status, "message": u.message, "actor_role": u.actor_role, "timestamp": iso(u.created_at)}
                for u in sorted(r.updates, key=lambda u: u.created_at)
            ],
            "timeline": timeline(r),
            "cluster": None,
            "risk": None,
            "disclaimer": DISCLAIMER,
        }
    )
    if r.cluster_id:
        cluster = db.get(Cluster, r.cluster_id)
        if cluster:
            data["cluster"] = cluster_dict(cluster)
    if r.vendor_id:
        risk = db.scalar(select(RiskScore).where(RiskScore.vendor_id == r.vendor_id))
        if risk:
            data["risk"] = {"score": risk.score, "band": risk.band, "factors": risk.factors}
    if include_confidential:
        inv = db.scalars(select(Investigation).where(Investigation.report_id == r.id)).all()
        data["investigations"] = [investigation_dict(i) for i in inv]
        data["reporter"] = {"name": r.reporter.name, "email": r.reporter.email} if r.reporter else None
    return data


def investigation_dict(i: Investigation) -> dict:
    return {
        "id": i.id,
        "report_id": i.report_id,
        "inspector_name": i.inspector_name,
        "status": i.status,
        "checklist": i.checklist,
        "notes": i.notes,
        "findings": i.findings,
        "decision": i.decision,
        "decision_note": i.decision_note,
        "decided_at": iso(i.decided_at),
        "created_at": iso(i.created_at),
        "updated_at": iso(i.updated_at),
    }


def vendor_dict(v: Vendor, risk: RiskScore | None = None) -> dict:
    data = {
        "id": v.id,
        "name": v.name,
        "address": v.address,
        "area": v.area,
        "city": v.city,
        "latitude": v.latitude,
        "longitude": v.longitude,
        "licence_ref": v.licence_ref,
        "is_demo": v.is_demo,
    }
    if risk:
        data["risk"] = {"score": risk.score, "band": risk.band, "factors": risk.factors}
    return data
