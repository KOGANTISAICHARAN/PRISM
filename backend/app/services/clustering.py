"""Semantic complaint clustering.

Reports are embedded (sentence-transformers all-MiniLM-L6-v2 when available,
TF-IDF fallback otherwise) and grouped with DBSCAN using cosine distance.
Vendor and area metadata are appended to the text so that semantically similar
complaints about the same establishment group together.

Clustering identifies *patterns*, not proof.
"""

from __future__ import annotations

import re
from collections import Counter

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.engine import ISSUE_LABELS
from ..models import Cluster, Report
from .embeddings import backend_in_use, cosine_matrix, embed

MIN_SAMPLES = 2
# Thresholds are backend-dependent: transformer embeddings score related sentences
# much higher than sparse TF-IDF vectors, so each backend gets tuned values.
_TUNING = {
    "sentence-transformers": {"eps": 0.35, "similarity": 0.62},
    "tfidf": {"eps": 0.60, "similarity": 0.45},
}


def _tuning() -> dict[str, float]:
    return _TUNING["sentence-transformers" if backend_in_use().startswith("sentence") else "tfidf"]

_STOP = {
    "the", "and", "was", "were", "with", "from", "this", "that", "there", "have", "had", "for",
    "which", "when", "then", "into", "found", "some", "very", "they", "them", "after", "about",
    "restaurant", "hotel", "order", "ordered", "purchased", "bought", "food", "item", "issue",
}


def report_text(report: Report) -> str:
    parts = [
        report.user_description or "",
        ISSUE_LABELS.get(report.issue_type, report.issue_type or ""),
        report.food_item or "",
        report.vendor_name or "",
        report.area or report.location_text or "",
    ]
    return " ".join(p for p in parts if p).strip()


def _theme(reports: list[Report]) -> str:
    issue = Counter(r.issue_type for r in reports).most_common(1)[0][0]
    words = Counter()
    for r in reports:
        for w in re.findall(r"[a-z]{4,}", f"{r.user_description or ''} {r.food_item or ''}".lower()):
            if w not in _STOP:
                words[w] += 1
    keywords = [w for w, _ in words.most_common(2)]
    label = ISSUE_LABELS.get(issue, issue).replace("Possible ", "").strip()
    if keywords:
        return f"{label.capitalize()} reported in {' / '.join(keywords)}"
    return label.capitalize()


def recompute_clusters(db: Session) -> list[Cluster]:
    """Recluster all reports. Returns the current cluster set."""
    from sklearn.cluster import DBSCAN

    reports = list(db.scalars(select(Report).order_by(Report.created_at)))
    if len(reports) < MIN_SAMPLES:
        return []

    vecs = embed([report_text(r) for r in reports])
    eps = _tuning()["eps"]
    distance = 1.0 - cosine_matrix(vecs)
    np.fill_diagonal(distance, 0.0)
    labels = DBSCAN(eps=eps, min_samples=MIN_SAMPLES, metric="precomputed").fit_predict(
        np.maximum(distance, 0.0)
    )

    # reset assignments, then rebuild cluster rows
    for r in reports:
        r.cluster_id = None
    for existing in db.scalars(select(Cluster)):
        db.delete(existing)
    db.flush()

    clusters: list[Cluster] = []
    for n, label in enumerate(sorted({int(x) for x in labels if x >= 0}), start=1):
        idx = [i for i, x in enumerate(labels) if x == label]
        members = [reports[i] for i in idx]
        sub = cosine_matrix(vecs[idx])
        pairwise = sub[np.triu_indices(len(idx), k=1)]
        vendor = Counter(m.vendor_name for m in members).most_common(1)[0][0]
        area = Counter(m.area or m.location_text or "Unknown" for m in members).most_common(1)[0][0]
        cluster = Cluster(
            label=f"#{n + 10}",
            theme=_theme(members),
            report_count=len(members),
            dominant_vendor=vendor,
            dominant_area=area,
            avg_similarity=float(pairwise.mean()) if pairwise.size else 1.0,
            criteria={
                "algorithm": "DBSCAN(cosine)",
                "eps": eps,
                "min_samples": MIN_SAMPLES,
                "embedding_backend": backend_in_use(),
                "issue_types": sorted({m.issue_type for m in members}),
            },
        )
        db.add(cluster)
        db.flush()
        for m in members:
            m.cluster_id = cluster.id
        clusters.append(cluster)

    db.commit()
    return clusters


def similar_reports(db: Session, report: Report, limit: int = 8) -> list[tuple[Report, float]]:
    """Semantically similar reports for the same vendor scope, most similar first."""
    others = [
        r
        for r in db.scalars(select(Report).order_by(Report.created_at.desc()).limit(400))
        if r.id != report.id
    ]
    if not others:
        return []
    vecs = embed([report_text(report), *[report_text(o) for o in others]])
    sims = (vecs[1:] @ vecs[0]).tolist()
    ranked = sorted(zip(others, sims), key=lambda p: p[1], reverse=True)
    return [(r, float(s)) for r, s in ranked if s >= _tuning()["similarity"]][:limit]


def similar_count_for_vendor(db: Session, vendor_id: str) -> tuple[int, float]:
    """(number of reports in the vendor's largest similar group, mean similarity)."""
    reports = list(db.scalars(select(Report).where(Report.vendor_id == vendor_id)))
    if len(reports) < 2:
        return (0, 0.0)
    vecs = embed([report_text(r) for r in reports])
    sim = cosine_matrix(vecs)
    np.fill_diagonal(sim, 0.0)
    adjacency = sim >= _tuning()["similarity"]
    best_size, best_mean = 0, 0.0
    for i in range(len(reports)):
        group = [j for j in range(len(reports)) if adjacency[i][j]]
        if len(group) + 1 > best_size:
            best_size = len(group) + 1
            best_mean = float(sim[i][group].mean()) if group else 0.0
    return (best_size if best_size > 1 else 0, best_mean)
