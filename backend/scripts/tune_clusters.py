"""Diagnostic: show cluster sizes for a range of DBSCAN eps values on current data."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from sklearn.cluster import DBSCAN
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Report
from app.services.clustering import report_text
from app.services.embeddings import cosine_matrix, embed

db = SessionLocal()
reports = list(db.scalars(select(Report).order_by(Report.created_at)))
vecs = embed([report_text(r) for r in reports])
sim = cosine_matrix(vecs)
dist = np.maximum(1.0 - sim, 0.0)
np.fill_diagonal(dist, 0.0)

print(f"{len(reports)} reports")
for eps in (0.35, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7):
    labels = DBSCAN(eps=eps, min_samples=2, metric="precomputed").fit_predict(dist)
    counts = Counter(int(x) for x in labels if x >= 0)
    noise = sum(1 for x in labels if x < 0)
    print(f"eps={eps}: clusters={len(counts)} sizes={sorted(counts.values(), reverse=True)} noise={noise}")
    if eps in (0.55, 0.6):
        for label, _ in counts.most_common(3):
            members = [reports[i] for i, x in enumerate(labels) if x == label]
            print("   ", Counter(m.vendor_name for m in members).most_common(2), Counter(m.issue_type for m in members).most_common(2))
db.close()
