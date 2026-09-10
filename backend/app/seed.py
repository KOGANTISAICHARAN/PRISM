"""Synthetic DEMO DATA for PRISM.

Everything created here is clearly flagged with ``is_demo=True`` and rendered in the
UI under a "DEMO DATA" label. It does not represent real citizens or real businesses.
"""

from __future__ import annotations

import io
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .auth import hash_password
from .db import SessionLocal
from .models import (
    AIAssessment,
    Evidence,
    EvidenceAuditLog,
    Investigation,
    Report,
    ReportUpdate,
    User,
    Vendor,
)
from .storage import sha256_bytes, storage

DEMO_PASSWORD = "demo1234"

DEMO_USERS = [
    ("citizen@prism.demo", "Demo Citizen", "citizen"),
    ("citizen2@prism.demo", "Aarti Rao (demo)", "citizen"),
    ("inspector@prism.demo", "Inspector R. Menon", "inspector"),
]

VENDORS = [
    ("ABC Restaurant", "Banjara Hills, Hyderabad", "Banjara Hills", 17.4126, 78.4392),
    ("City Biryani", "Ameerpet, Hyderabad", "Ameerpet", 17.4374, 78.4487),
    ("Fresh Bites", "Gachibowli, Hyderabad", "Gachibowli", 17.4401, 78.3489),
    ("Food Corner", "Madhapur, Hyderabad", "Madhapur", 17.4485, 78.3908),
]

ABC_SIMILAR = [
    "Found a hard plastic piece inside my chicken biryani from ABC Restaurant.",
    "There was a small plastic fragment in the biryani I ordered from ABC Restaurant.",
    "I bit into something hard in the biryani, looked like plastic packaging material.",
    "Foreign plastic-like object in chicken biryani parcel from ABC Restaurant.",
    "My biryani had a piece of plastic wrapper mixed in the rice.",
    "Sharp plastic bit found while eating chicken biryani from ABC.",
    "Plastic-looking object in the biryani gravy, stopped eating immediately.",
    "Found a foreign object that looked like plastic in the mutton biryani.",
    "A plastic shred was inside my biryani box from ABC Restaurant.",
]

ABC_OTHER = [
    ("The chicken curry smelled sour and stale.", "spoilage_discoloration", "Chicken Curry"),
    ("Kitchen area looked unclean when I collected my order.", "hygiene_concern", "Chicken Biryani"),
    ("Packaging was torn and gravy had leaked in the bag.", "packaging_damage", "Mutton Biryani"),
    ("Saw a fly inside the food display counter.", "pest_evidence", "Chicken Biryani"),
    ("Curd served with biryani tasted sour and off.", "spoilage_discoloration", "Curd"),
]

OTHER_REPORTS = [
    ("City Biryani", "Chicken tasted spoiled and had a bad smell.", "spoilage_discoloration", "Chicken Biryani", 6),
    ("City Biryani", "Bad smell from the chicken pieces in the biryani.", "spoilage_discoloration", "Chicken Biryani", 4),
    ("City Biryani", "Food had a strange smell, could not finish it.", "spoilage_discoloration", "Biryani", 2),
    ("City Biryani", "Rice looked slimy and smelled sour.", "spoilage_discoloration", "Biryani", 1),
    ("Fresh Bites", "Green mold-like patches on the sandwich bread.", "mold_like_growth", "Veg Sandwich", 3),
    ("Fresh Bites", "White furry growth visible on the pastry.", "mold_like_growth", "Pastry", 9),
    ("Food Corner", "Cockroach seen near the food preparation counter.", "pest_evidence", "Noodles", 5),
    ("Food Corner", "Juice bottle seal was broken and it was leaking.", "leakage", "Fruit Juice", 12),
]


def _demo_image(text: str, seed: int) -> bytes:
    from PIL import Image, ImageDraw

    rnd = random.Random(seed)
    img = Image.new("RGB", (640, 480), (rnd.randint(180, 230), rnd.randint(150, 200), rnd.randint(110, 160)))
    draw = ImageDraw.Draw(img)
    for _ in range(160):  # food-like texture
        x, y = rnd.randint(0, 620), rnd.randint(60, 470)
        draw.ellipse([x, y, x + rnd.randint(6, 22), y + rnd.randint(6, 16)], fill=(rnd.randint(200, 245), rnd.randint(180, 225), rnd.randint(120, 170)))
    draw.rectangle([250, 220, 340, 260], fill=(40, 40, 46))  # the "foreign object"
    draw.rectangle([0, 0, 640, 46], fill=(17, 24, 39))
    draw.text((12, 16), f"PRISM SYNTHETIC DEMO IMAGE - {text[:40]}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _add_evidence(db, report: Report, uploader: User, label: str, seed: int, kind: str = "citizen_photo") -> Evidence:
    data = _demo_image(label, seed)
    digest = sha256_bytes(data)
    key, url = storage.put(data, f"demo_{seed}.jpg", "image/jpeg")
    ev = Evidence(
        report_id=report.id,
        file_url=url,
        storage_key=key,
        file_name=f"demo_{seed}.jpg",
        file_type="image/jpeg",
        file_size=len(data),
        sha256_hash=digest,
        kind=kind,
        uploaded_by=uploader.id,
        uploader_role=uploader.role,
        geo_lat=report.latitude,
        geo_lng=report.longitude,
        uploaded_at=report.created_at,
        is_demo=True,
    )
    db.add(ev)
    db.flush()
    db.add(
        EvidenceAuditLog(
            evidence_id=ev.id,
            action="CREATE",
            actor_id=uploader.id,
            actor_label=f"{uploader.name} ({uploader.role})",
            detail=f"demo seed; sha256={digest[:16]}...",
            created_at=report.created_at,
        )
    )
    return ev


def seed_if_empty() -> dict:
    db = SessionLocal()
    try:
        if db.scalar(select(Report).where(Report.is_demo == True)):  # noqa: E712
            return {"seeded": False, "reason": "demo data already present"}

        users = {}
        for email, name, role in DEMO_USERS:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email,
                    name=name,
                    role=role,
                    password_hash=hash_password(DEMO_PASSWORD),
                    jurisdiction="Hyderabad (demo)" if role == "inspector" else None,
                    is_demo=True,
                )
                db.add(user)
                db.flush()
            users[role if role == "inspector" else email] = user
        citizen = users["citizen@prism.demo"]
        citizen2 = users["citizen2@prism.demo"]
        inspector = users["inspector"]

        vendors: dict[str, Vendor] = {}
        for name, address, area, lat, lng in VENDORS:
            v = db.scalar(select(Vendor).where(Vendor.name == name))
            if v is None:
                v = Vendor(
                    name=name,
                    address=address,
                    area=area,
                    city="Hyderabad",
                    latitude=lat,
                    longitude=lng,
                    licence_ref=f"DEMO-LIC-{random.randint(10000, 99999)}",
                    is_demo=True,
                )
                db.add(v)
                db.flush()
            vendors[name] = v

        rnd = random.Random(42)
        now = datetime.now(timezone.utc)
        used_refs: set[str] = set()

        def make_report(vendor: Vendor, text: str, issue: str, food: str, days_ago: int, reporter: User, hours=None) -> Report:
            from .ai.engine import SEVERITY

            while True:
                ref = f"PR-{rnd.randint(10000, 99999)}"
                if ref not in used_refs and not db.scalar(select(Report).where(Report.reference == ref)):
                    used_refs.add(ref)
                    break
            created = now - timedelta(days=days_ago, hours=hours if hours is not None else rnd.randint(0, 12))
            r = Report(
                reference=ref,
                user_id=reporter.id,
                vendor_id=vendor.id,
                vendor_name=vendor.name,
                food_item=food,
                issue_type=issue,
                user_description=text,
                incident_datetime=created - timedelta(hours=2),
                location_text=vendor.address,
                area=vendor.area,
                latitude=(vendor.latitude or 0) + rnd.uniform(-0.004, 0.004),
                longitude=(vendor.longitude or 0) + rnd.uniform(-0.004, 0.004),
                evidence_available="photo",
                severity=SEVERITY.get(issue, 1),
                status="NEW",
                created_at=created,
                updated_at=created,
                is_demo=True,
            )
            db.add(r)
            db.flush()
            db.add(
                ReportUpdate(
                    report_id=r.id,
                    status="NEW",
                    message="Report submitted and evidence recorded in the Evidence Vault. (DEMO DATA)",
                    actor_role="system",
                    created_at=created,
                )
            )
            return r

        abc = vendors["ABC Restaurant"]
        abc_reports: list[Report] = []
        # 9 semantically similar foreign-object reports; 8 of all ABC reports inside 7 days
        similar_days = [0, 1, 2, 3, 4, 5, 6, 6, 11]
        for i, (text, days) in enumerate(zip(ABC_SIMILAR, similar_days)):
            reporter = citizen if i % 2 == 0 else citizen2
            r = make_report(abc, text, "foreign_object", "Chicken Biryani", days, reporter)
            db.add(
                AIAssessment(
                    report_id=r.id,
                    source="vision",
                    detected_issue="Possible foreign object",
                    risk_level="High",
                    confidence=round(rnd.uniform(0.78, 0.93), 2),
                    explanation="Foreign-object-like structure appears visible in the submitted image. Indicative only.",
                    model="prism-demo-vision",
                    created_at=r.created_at,
                )
            )
            if i < 5:
                _add_evidence(db, r, reporter, text, seed=100 + i)
            abc_reports.append(r)

        for i, (text, issue, food) in enumerate(ABC_OTHER):
            days = [2, 9, 12, 16, 21][i]
            r = make_report(abc, text, issue, food, days, citizen2)
            abc_reports.append(r)

        for vendor_name, text, issue, food, days in OTHER_REPORTS:
            make_report(vendors[vendor_name], text, issue, food, days, citizen2)

        db.commit()

        # a demo investigation already in progress on one City Biryani case
        city_case = db.scalar(
            select(Report).where(Report.vendor_id == vendors["City Biryani"].id).order_by(Report.created_at.desc())
        )
        if city_case:
            from .routers.investigations_router import CHECKLIST_ITEMS

            inv = Investigation(
                report_id=city_case.id,
                inspector_id=inspector.id,
                inspector_name=inspector.name,
                status="IN_PROGRESS",
                checklist={item: idx < 3 for idx, item in enumerate(CHECKLIST_ITEMS)},
                notes="Demo investigation: site visit scheduled, storage temperature log requested.",
                is_demo=True,
            )
            city_case.status = "INVESTIGATION_REQUIRED"
            db.add(inv)
            db.add(
                ReportUpdate(
                    report_id=city_case.id,
                    status="UNDER_REVIEW",
                    message="An authorised reviewer has opened your report for review. (DEMO DATA)",
                    actor_role="inspector",
                )
            )
            db.add(
                ReportUpdate(
                    report_id=city_case.id,
                    status="INVESTIGATION_REQUIRED",
                    message="An inspection has been initiated for your report. (DEMO DATA)",
                    actor_role="inspector",
                )
            )
            db.commit()

        from .services.clustering import recompute_clusters
        from .services.risk import recompute_all

        recompute_clusters(db)
        recompute_all(db)

        total = db.scalar(select(Report).where(Report.is_demo == True)) is not None  # noqa: E712
        return {"seeded": total, "vendors": len(vendors), "users": len(users)}
    finally:
        db.close()


if __name__ == "__main__":
    from .db import init_db

    init_db()
    print(seed_if_empty())
