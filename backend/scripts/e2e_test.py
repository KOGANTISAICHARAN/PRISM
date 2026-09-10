"""End-to-end smoke test of the full PRISM demo flow against a running backend.

Usage:  python scripts/e2e_test.py [base_url]
"""

from __future__ import annotations

import io
import sys
import uuid

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OK, FAIL = "[PASS]", "[FAIL]"
failures: list[str] = []


def check(label: str, condition: bool, extra: str = "") -> None:
    print(f"{OK if condition else FAIL} {label} {extra if not condition else ''}".rstrip())
    if not condition:
        failures.append(label)


def png_bytes() -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (400, 300), (210, 180, 140))
    d = ImageDraw.Draw(img)
    d.rectangle([150, 120, 240, 170], fill=(30, 30, 35))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


c = httpx.Client(base_url=BASE, timeout=120)

# 1. health
h = c.get("/health").json()
check("health endpoint", h.get("status") == "ok", str(h))
print("    backend:", h)

# 2. citizen signup + login
email = f"e2e_{uuid.uuid4().hex[:8]}@prism-e2e.com"
r = c.post("/auth/register", json={"email": email, "password": "test1234", "name": "E2E Citizen"})
check("citizen registration", r.status_code == 201, r.text)
citizen_token = r.json()["access_token"]
CH = {"Authorization": f"Bearer {citizen_token}"}

r = c.post("/auth/login", json={"email": "inspector@prism.demo", "password": "demo1234"})
check("inspector demo login", r.status_code == 200, r.text)
IH = {"Authorization": f"Bearer {r.json()['access_token']}"}
check("inspector role", r.json()["user"]["role"] == "inspector")

# 3. AI vision analysis
img = png_bytes()
r = c.post(
    "/ai/analyze-image",
    files={"file": ("food.jpg", img, "image/jpeg")},
    data={"hint": "I found a plastic piece in my chicken biryani from ABC Restaurant"},
    headers=CH,
)
check("AI image analysis", r.status_code == 200, r.text)
vision = r.json()
check("vision returns issue + risk + confidence", all(k in vision for k in ("detected_issue", "risk_level", "confidence", "explanation")))
check("vision hedged language / disclaimer", "does not confirm" in vision["disclaimer"])
print("    vision:", vision["detected_issue"], vision["risk_level"], vision["confidence"])

# 4. Complaint assistant slot filling
messages = [{"role": "user", "content": "I found a plastic piece in my chicken biryani from ABC Restaurant in Banjara Hills"}]
r = c.post("/ai/structure-complaint", json={"messages": messages, "known_fields": {}, "vision": vision}, headers=CH)
check("assistant turn 1", r.status_code == 200, r.text)
a1 = r.json()
check("assistant extracted issue_type from vision/text", bool(a1["fields"].get("issue_type")))
check("assistant asks only missing fields", a1["next_question"] is not None and not a1["complete"])
print("    missing:", a1["missing_fields"], "| asks:", a1["next_question"])

messages += [
    {"role": "assistant", "content": a1["next_question"]},
    {"role": "user", "content": "Today at 8:30 pm, I have a photo and the bill"},
]
r = c.post("/ai/structure-complaint", json={"messages": messages, "known_fields": a1["fields"], "vision": vision}, headers=CH)
a2 = r.json()
print("    after turn 2 fields:", {k: v for k, v in a2["fields"].items() if k != "user_description"})
check("assistant fills incident_datetime", bool(a2["fields"].get("incident_datetime")))

fields = {
    "vendor_name": a2["fields"].get("vendor_name") or "ABC Restaurant",
    "food_item": a2["fields"].get("food_item") or "Chicken Biryani",
    "issue_type": a2["fields"].get("issue_type") or "foreign_object",
    "user_description": a2["fields"].get("user_description"),
    "incident_datetime": "2026-09-10T20:30",
    "location_text": "Banjara Hills, Hyderabad",
    "area": "Banjara Hills",
    "latitude": 17.4126,
    "longitude": 78.4392,
    "evidence_available": a2["fields"].get("evidence_available") or "both",
    "ai_assessment": vision,
}

# 5. Submit report
r = c.post("/reports", json=fields, headers=CH)
check("report creation", r.status_code == 201, r.text)
report = r.json()
report_id, reference = report["id"], report["reference"]
check("report reference generated (PR-xxxxx)", reference.startswith("PR-"), reference)
print("    report:", reference)

# 6. Evidence upload + SHA-256
r = c.post(
    "/evidence",
    data={"report_id": report_id, "kind": "citizen_photo", "geo_lat": 17.4126, "geo_lng": 78.4392},
    files={"file": ("food.jpg", img, "image/jpeg")},
    headers=CH,
)
check("evidence upload", r.status_code == 201, r.text)
ev = r.json()
check("sha256 hash recorded", len(ev["sha256_hash"]) == 64, ev.get("sha256_hash", ""))
print("    sha256:", ev["sha256_hash"])

r = c.get(f"/evidence/{ev['id']}/verify", headers=CH)
check("evidence integrity verification", r.json().get("integrity_verified") is True, r.text)

r = c.get(f"/evidence/{ev['id']}", headers=CH)
actions = [a["action"] for a in r.json()["audit_log"]]
check("audit log records CREATE/VIEW/EXPORT", {"CREATE", "VIEW", "EXPORT"} <= set(actions), str(actions))

# immutability: citizens cannot delete evidence
r = c.request("DELETE", f"/evidence/{ev['id']}", headers=CH)
check("evidence deletion not possible", r.status_code in (404, 405), str(r.status_code))

# 7. intelligence pass
r = c.post(f"/reports/{report_id}/finalize", headers=CH)
check("finalize (clustering + risk)", r.status_code == 200, r.text)
final = r.json()
check("report joined a cluster", final.get("cluster") is not None, str(final.get("cluster")))
check("vendor risk score computed", (final.get("risk") or {}).get("score", 0) > 0, str(final.get("risk")))
if final.get("cluster"):
    print("    cluster:", final["cluster"]["label"], "|", final["cluster"]["theme"], "| reports:", final["cluster"]["report_count"])
if final.get("risk"):
    print("    risk:", final["risk"]["score"], final["risk"]["band"])

# 8. citizen visibility
r = c.get("/reports", headers=CH)
check("my reports list", any(x["reference"] == reference for x in r.json()["reports"]))
r = c.get(f"/reports/{reference}", headers=CH)
check("report lookup by reference", r.status_code == 200)
check("citizen timeline present", len(r.json()["timeline"]) >= 5)

# 9. inspector dashboard
r = c.get("/inspector/summary", headers=IH)
check("inspector summary", r.status_code == 200, r.text)
print("    summary:", r.json())
r = c.get("/inspector/cases", headers=IH)
check("inspector priority queue", r.status_code == 200 and r.json()["count"] > 0)
cases = r.json()["cases"]
check("queue sorted by priority", cases[0]["priority_score"] >= cases[-1]["priority_score"])
print("    top case:", cases[0]["vendor_name"], "risk", cases[0]["risk_score"], cases[0]["priority_band"])

r = c.get(f"/inspector/cases/{report_id}", headers=IH)
check("inspector case view", r.status_code == 200, r.text)
case = r.json()
check("case includes risk factors", bool(case["risk"]["factors"]["components"]))
check("case includes similar reports", len(case["similar_reports"]) > 0, str(len(case["similar_reports"])))
check("case includes evidence with hash", bool(case["report"]["evidence"][0]["sha256_hash"]))

r = c.get("/clusters", headers=IH)
check("clusters endpoint", r.json()["count"] > 0, r.text)
print("    clusters:", r.json()["count"], "| embeddings:", r.json()["embedding_backend"])
r = c.get("/hotspots", headers=IH)
check("hotspots endpoint", len(r.json()["hotspots"]) > 0, r.text)
print("    hotspots:", [(h["area"], h["level"], h["report_count"]) for h in r.json()["hotspots"]][:4])

# 10. RBAC
r = c.get("/inspector/cases", headers=CH)
check("citizen blocked from inspector API", r.status_code == 403, str(r.status_code))
r = c.get("/inspector/cases")
check("unauthenticated blocked", r.status_code in (401, 403), str(r.status_code))

# 11. investigation + inspector evidence + human decision
r = c.post("/inspector/cases/" + report_id + "/review", headers=IH)
check("mark under review", r.json()["status"] in ("UNDER_REVIEW", "INVESTIGATION_REQUIRED"), r.text)
r = c.post("/investigations", json={"report_id": report_id, "notes": "Site visit planned."}, headers=IH)
check("start investigation", r.status_code == 201, r.text)
inv = r.json()
r = c.patch(
    f"/investigations/{inv['id']}",
    json={"checklist": {"visit_establishment": True, "inspect_kitchen_hygiene": True}, "notes": "Kitchen inspected."},
    headers=IH,
)
check("update investigation checklist", r.json()["checklist"]["visit_establishment"] is True, r.text)

r = c.post(
    f"/investigations/{inv['id']}/evidence",
    data={"kind": "inspection_photo"},
    files={"file": ("inspection.jpg", png_bytes(), "image/jpeg")},
    headers=IH,
)
check("inspector evidence upload with hash", r.status_code == 201 and len(r.json()["sha256_hash"]) == 64, r.text)

r = c.post(
    f"/investigations/{inv['id']}/decision",
    json={"status": "ACTIONED", "decision_note": "Inspection completed. Corrective action recorded.", "findings": "Storage practices corrected."},
    headers=IH,
)
check("human decision recorded", r.status_code == 200 and r.json()["report_status"] == "ACTIONED", r.text)

# citizens cannot make decisions
r = c.post(f"/investigations/{inv['id']}/decision", json={"status": "CLOSED", "decision_note": "x"}, headers=CH)
check("citizen cannot record decisions", r.status_code == 403, str(r.status_code))

# 12. citizen sees updated status
r = c.get(f"/reports/{reference}", headers=CH)
final = r.json()
check("citizen sees final status", final["status"] == "ACTIONED", final["status"])
check("citizen sees status updates", len(final["updates"]) >= 3, str(len(final["updates"])))
print("    citizen timeline:", [(s["label"], s["state"]) for s in final["timeline"]])

print()
if failures:
    print(f"{len(failures)} CHECK(S) FAILED: {failures}")
    sys.exit(1)
print("ALL CHECKS PASSED - full PRISM flow works end to end.")
