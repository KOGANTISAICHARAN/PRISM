from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- status enums
REPORT_STATUSES = [
    "NEW",
    "UNDER_REVIEW",
    "INVESTIGATION_REQUIRED",
    "VERIFIED",
    "NOT_VERIFIED",
    "ACTIONED",
    "CLOSED",
]
ROLES = ["citizen", "inspector"]


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="citizen", index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    jurisdiction: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    reports: Mapped[list[Report]] = relationship(back_populates="reporter")


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), index=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    area: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    licence_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    verified_history_count: Mapped[int] = mapped_column(Integer, default=0)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    reports: Mapped[list[Report]] = relationship(back_populates="vendor")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    vendor_id: Mapped[str | None] = mapped_column(ForeignKey("vendors.id"), index=True, nullable=True)

    vendor_name: Mapped[str] = mapped_column(String(200))
    food_item: Mapped[str | None] = mapped_column(String(200), nullable=True)
    issue_type: Mapped[str] = mapped_column(String(60), index=True)
    user_description: Mapped[str] = mapped_column(Text, default="")
    incident_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    area: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_available: Mapped[str | None] = mapped_column(String(40), nullable=True)

    severity: Mapped[int] = mapped_column(Integer, default=2)  # 1 low .. 4 critical
    status: Mapped[str] = mapped_column(String(30), default="NEW", index=True)
    cluster_id: Mapped[str | None] = mapped_column(ForeignKey("clusters.id"), index=True, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    reporter: Mapped[User | None] = relationship(back_populates="reports")
    vendor: Mapped[Vendor | None] = relationship(back_populates="reports")
    evidence: Mapped[list[Evidence]] = relationship(back_populates="report")
    assessments: Mapped[list[AIAssessment]] = relationship(back_populates="report")
    updates: Mapped[list[ReportUpdate]] = relationship(back_populates="report")
    cluster: Mapped[Cluster | None] = relationship(back_populates="reports")


Index("ix_reports_vendor_created", Report.vendor_id, Report.created_at)


class Evidence(Base):
    """Immutable evidence record. Never updated after creation."""

    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    file_url: Mapped[str] = mapped_column(String(500))
    storage_key: Mapped[str] = mapped_column(String(500))
    file_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(120))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    sha256_hash: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(40), default="citizen_photo")
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploader_role: Mapped[str] = mapped_column(String(20), default="citizen")
    geo_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    geo_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    capture_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    report: Mapped[Report] = relationship(back_populates="evidence")


class EvidenceAuditLog(Base):
    """Append-only audit trail: CREATE / VIEW / EXPORT / DOWNLOAD."""

    __tablename__ = "evidence_audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), index=True)
    action: Mapped[str] = mapped_column(String(20), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_label: Mapped[str] = mapped_column(String(160), default="system")
    detail: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AIAssessment(Base):
    __tablename__ = "ai_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id: Mapped[str | None] = mapped_column(ForeignKey("reports.id"), index=True, nullable=True)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="vision")
    detected_issue: Mapped[str] = mapped_column(String(120))
    risk_level: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(80), default="demo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    report: Mapped[Report | None] = relationship(back_populates="assessments")


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    label: Mapped[str] = mapped_column(String(40), index=True)  # e.g. "#12"
    theme: Mapped[str] = mapped_column(String(200))
    criteria: Mapped[dict] = mapped_column(JSON, default=dict)
    report_count: Mapped[int] = mapped_column(Integer, default=0)
    dominant_vendor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dominant_area: Mapped[str | None] = mapped_column(String(120), nullable=True)
    avg_similarity: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    reports: Mapped[list[Report]] = relationship(back_populates="cluster")


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.id"), index=True)
    score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    band: Mapped[str] = mapped_column(String(20), default="LOW")
    factors: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    inspector_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    inspector_name: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(30), default="IN_PROGRESS")
    checklist: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(30), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ReportUpdate(Base):
    """Citizen-visible timeline entries."""

    __tablename__ = "report_updates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(String(400))
    actor_role: Mapped[str] = mapped_column(String(20), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    report: Mapped[Report] = relationship(back_populates="updates")
