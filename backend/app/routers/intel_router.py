from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_user, require_inspector
from ..db import get_db
from ..models import Cluster, Report, RiskScore, User, Vendor
from ..serializers import cluster_dict, vendor_dict
from ..services.clustering import recompute_clusters, similar_reports
from ..services.embeddings import backend_in_use
from ..services.hotspots import hotspots
from ..services.risk import compute_vendor_risk, recompute_all

router = APIRouter(tags=["intelligence"])


@router.get("/risk/{vendor_id}")
def vendor_risk(vendor_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    vendor = db.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vendor not found")
    return compute_vendor_risk(db, vendor)


@router.get("/vendors")
def list_vendors(db: Session = Depends(get_db), user: User = Depends(require_inspector)):
    risks = {r.vendor_id: r for r in db.scalars(select(RiskScore))}
    vendors = db.scalars(select(Vendor)).all()
    data = [vendor_dict(v, risks.get(v.id)) for v in vendors]
    return {"vendors": sorted(data, key=lambda v: -(v.get("risk", {}) or {}).get("score", 0))}


@router.get("/clusters")
def list_clusters(db: Session = Depends(get_db), user: User = Depends(current_user)):
    clusters = db.scalars(select(Cluster).order_by(Cluster.report_count.desc())).all()
    return {
        "embedding_backend": backend_in_use(),
        "count": len(clusters),
        "clusters": [cluster_dict(c) for c in clusters],
    }


@router.get("/clusters/{cluster_id}")
def cluster_detail(cluster_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    cluster = db.get(Cluster, cluster_id) or db.scalar(select(Cluster).where(Cluster.label == cluster_id))
    if cluster is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cluster not found")
    reports = db.scalars(select(Report).where(Report.cluster_id == cluster.id)).all()
    return cluster_dict(cluster, list(reports))


@router.get("/hotspots")
def list_hotspots(days: int = 30, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return {"days": days, "hotspots": hotspots(db, days)}


@router.get("/reports/{report_id}/similar")
def report_similar(report_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    if user.role != "inspector" and report.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorised")
    pairs = similar_reports(db, report)
    from ..serializers import report_summary

    return {
        "count": len(pairs),
        "similar": [{**report_summary(r), "similarity": round(s, 3)} for r, s in pairs],
    }


@router.post("/intel/recompute")
def recompute(db: Session = Depends(get_db), user: User = Depends(require_inspector)):
    clusters = recompute_clusters(db)
    recompute_all(db)
    return {"clusters": len(clusters), "embedding_backend": backend_in_use(), "status": "ok"}
