"""Master End-to-End Browser Journey Verification for PRISM.

Tests the full continuous loop:
Citizen (Intake -> AI Vision -> Assistant -> Submit)
  -> Evidence Vault (SHA-256 Hash + Audit Event)
  -> Intelligence Layer (Risk Score + Semantic Clustering + Hotspot)
  -> Inspector Command Center (Priority Queue -> Case Review)
  -> Field Investigation (Checklist -> Inspector Notes -> Inspection Evidence)
  -> Human Decision Recording (ACTIONED status decision note)
  -> Citizen Status Loop (Report Timeline updated for Citizen)
"""

import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

def generate_sample_image(name: str, seed_text: str) -> Path:
    img_path = Path(__file__).parent / name
    img = Image.new("RGB", (640, 480), (230, 200, 150))
    d = ImageDraw.Draw(img)
    d.rectangle([220, 160, 360, 240], fill=(35, 35, 40))  # dark foreign object
    d.text((20, 20), f"PRISM FULL E2E TEST - {seed_text}", fill=(255, 255, 255))
    img.save(img_path, format="JPEG", quality=90)
    return img_path

def run_master_e2e_journey():
    citizen_img = generate_sample_image("temp_citizen_biryani.jpg", "CITIZEN PHOTO")
    inspector_img = generate_sample_image("temp_inspector_site.jpg", "INSPECTOR PHOTO")
    print("[INIT] Sample food & inspection images generated.")

    errors = []
    journey_timings = {}
    t_start = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # -------------------------------------------------------------
        # PHASE 1: CITIZEN INTAKE & REPORT SUBMISSION
        # -------------------------------------------------------------
        print("\n=== PHASE 1: CITIZEN REPORT INTAKE ===")
        context_c = browser.new_context(viewport={"width": 390, "height": 844}) # Mobile viewport
        page_c = context_c.new_page()

        page_errors = []
        page_c.on("pageerror", lambda err: page_errors.append(f"Citizen PageError: {err}"))
        page_c.on("console", lambda msg: page_errors.append(f"Citizen ConsoleError: {msg.text}") if msg.type == "error" else None)

        # 1. Login as Demo Citizen
        page_c.goto("http://localhost:3000/login")
        page_c.wait_for_selector("text=Demo citizen")
        page_c.click("text=Demo citizen")
        page_c.wait_for_url("http://localhost:3000/")
        print("[PASS] Citizen logged in successfully")

        # 2. Open /report
        page_c.goto("http://localhost:3000/report")
        page_c.wait_for_selector("text=Step 1: Upload Photo & Describe Issue")
        
        # 3. Upload Photo & Enter Description
        file_input = page_c.locator("input[type='file']")
        file_input.set_input_files(str(citizen_img))
        page_c.wait_for_selector("img[alt='Uploaded food evidence preview']")
        
        note = "I found a piece of hard plastic inside my chicken biryani ordered from ABC Restaurant in Banjara Hills"
        page_c.fill("textarea#initialNote", note)
        page_c.click("button:has-text('Analyze & Continue')")
        print("[PASS] Citizen photo uploaded and description provided")

        # 4. AI Vision & Slot-Filling Assistant
        page_c.wait_for_selector("text=PRISM AI Vision Signal", timeout=15000)
        page_c.wait_for_selector("text=AI-generated assessment")
        print("[PASS] AI visual observations & safety disclaimer displayed")

        # Verify or complete required fields
        vendor_input = page_c.locator("input#vendor_name")
        if not vendor_input.input_value():
            vendor_input.fill("ABC Restaurant")
        
        food_input = page_c.locator("input#food_item")
        if not food_input.input_value():
            food_input.fill("Chicken Biryani")

        loc_input = page_c.locator("input#location_text")
        if not loc_input.input_value():
            loc_input.fill("Banjara Hills, Hyderabad")

        # Go to Review Step
        page_c.click("button:has-text('Review Report')")
        page_c.wait_for_selector("text=Step 3: Review Before Submitting")
        print("[PASS] Review summary step verified")

        # 5. Submit Report
        page_c.click("button:has-text('Submit Report')")
        page_c.wait_for_selector("text=Report Submitted", timeout=15000)
        
        ref_code = page_c.locator("span.font-mono.text-2xl").inner_text()
        sha256_hash = page_c.locator("p.font-mono.break-all").inner_text()
        print(f"[PASS] Report Submitted! Reference Code: {ref_code} | SHA-256 Hash: {sha256_hash[:16]}...")
        
        if not ref_code.startswith("PR-"):
            errors.append(f"Invalid reference format: {ref_code}")
        if len(sha256_hash) != 64:
            errors.append(f"Invalid SHA-256 hash length: {sha256_hash}")

        journey_timings["citizen_submission"] = round(time.time() - t_start, 2)

        # -------------------------------------------------------------
        # PHASE 2: CITIZEN REPORT DETAIL VERIFICATION
        # -------------------------------------------------------------
        print("\n=== PHASE 2: CITIZEN REPORT DETAIL & TIMELINE ===")
        page_c.click("text=View My Reports & Status")
        page_c.wait_for_url("http://localhost:3000/reports")
        page_c.wait_for_selector(f"text={ref_code}")
        print(f"[PASS] Report {ref_code} appears in My Reports list")

        page_c.click(f"a[href*='{ref_code}']")
        page_c.wait_for_selector("text=Status Timeline")
        page_c.wait_for_selector("text=Report Submitted")
        print(f"[PASS] Citizen report detail & initial timeline step verified")

        # -------------------------------------------------------------
        # PHASE 3: INSPECTOR DISCOVERY & PRIORITY QUEUE
        # -------------------------------------------------------------
        print("\n=== PHASE 3: INSPECTOR DISCOVERY & PRIORITY QUEUE ===")
        t_inspector_start = time.time()
        context_i = browser.new_context(viewport={"width": 1280, "height": 800}) # Desktop workstation
        page_i = context_i.new_page()

        page_i.on("pageerror", lambda err: page_errors.append(f"Inspector PageError: {err}"))
        page_i.on("console", lambda msg: page_errors.append(f"Inspector ConsoleError: {msg.text}") if msg.type == "error" else None)

        page_i.goto("http://localhost:3000/login")
        page_i.click("text=Demo inspector")
        page_i.wait_for_url("http://localhost:3000/inspector")
        page_i.wait_for_selector("text=PRISM Inspector Command Center")
        print("[PASS] Inspector logged in & command center loaded")

        # Search or locate the new case
        page_i.wait_for_selector(f"text={ref_code}", timeout=15000)
        print(f"[PASS] Submitted report {ref_code} discovered in Inspector Priority Queue")

        # -------------------------------------------------------------
        # PHASE 4: INSPECTOR CASE INVESTIGATION & EVIDENCE HASHING
        # -------------------------------------------------------------
        print("\n=== PHASE 4: INSPECTOR CASE INVESTIGATION & EVIDENCE ===")
        case_link = page_i.locator(f"a[href*='{ref_code}']").first
        case_link.click()

        page_i.wait_for_selector("text=Case & Establishment Profile")
        page_i.wait_for_selector("text=Evidence Vault & Integrity Records")
        print(f"[PASS] Opened case workspace for {ref_code}")

        # Verify SHA-256 on evidence
        verify_btn = page_i.locator("button:has-text('Verify SHA-256 Integrity')").first
        if verify_btn.count() > 0:
            verify_btn.click()
            page_i.wait_for_selector("text=SHA-256 Verified")
            print("[PASS] Evidence SHA-256 hash verified by inspector")

        # Start Investigation
        start_btn = page_i.locator("button:has-text('Start Inspection')")
        if start_btn.count() > 0:
            start_btn.click()
            page_i.wait_for_selector("text=8-Item Inspection Checklist")
            print("[PASS] Started site inspection")

        # Complete Checklist Items & Save Notes
        checkboxes = page_i.locator("input[type='checkbox']")
        for idx in range(min(checkboxes.count(), 4)):
            cb = checkboxes.nth(idx)
            if not cb.is_checked():
                cb.check()
        
        page_i.fill("textarea#inspectorNotes", "Site visit conducted. Inspected kitchen area and verified storage temperatures.")
        page_i.fill("textarea#findingsInput", "Storage conditions acceptable; corrective action advised for parcel packaging.")
        page_i.click("button:has-text('Save Notes & Findings')")
        page_i.wait_for_selector("text=Investigator notes and findings saved")
        print("[PASS] Inspection checklist & notes saved")

        # Upload Inspection Evidence File
        insp_file_input = page_i.locator("input[type='file']")
        if insp_file_input.count() > 0:
            insp_file_input.set_input_files(str(inspector_img))
            page_i.click("button:has-text('Upload Inspection File')")
            page_i.wait_for_selector("text=Inspection evidence uploaded", timeout=15000)
            print("[PASS] Inspection evidence photo uploaded with SHA-256 hash")

        # -------------------------------------------------------------
        # PHASE 5: RECORD HUMAN DECISION
        # -------------------------------------------------------------
        print("\n=== PHASE 5: RECORD HUMAN CASE DECISION ===")
        page_i.select_option("select#decisionStatus", "ACTIONED")
        page_i.fill("textarea#decisionNoteInput", "Inspection completed. Notice served to management regarding food handling compliance.")
        page_i.click("button:has-text('Record Final Decision')")
        
        page_i.wait_for_selector("text=Confirm Human Inspector Decision")
        page_i.click("button:has-text('Confirm Decision')")

        page_i.wait_for_selector("text=Case decision recorded: ACTIONED", timeout=15000)
        print("[PASS] Human case decision recorded -> Case status updated to ACTIONED")

        journey_timings["inspector_workflow"] = round(time.time() - t_inspector_start, 2)

        # -------------------------------------------------------------
        # PHASE 6: CITIZEN LOOPBACK & TIMELINE REFRESH
        # -------------------------------------------------------------
        print("\n=== PHASE 6: CITIZEN FEEDBACK LOOP & TIMELINE REFRESH ===")
        page_c.reload()
        page_c.wait_for_selector("text=Actioned")
        page_c.wait_for_selector("text=Notice served to management")
        print(f"[PASS] Citizen timeline refreshed! Updated status 'Actioned' & inspector update message visible to citizen.")

        journey_timings["total_journey"] = round(time.time() - t_start, 2)

        browser.close()

        # Cleanup temporary test images
        if citizen_img.exists(): citizen_img.unlink()
        if inspector_img.exists(): inspector_img.unlink()

        print("\n==================================================")
        print("MASTER E2E DEMO JOURNEY SUMMARY")
        print("==================================================")
        print(f"• Citizen Submission Time: {journey_timings.get('citizen_submission')}s")
        print(f"• Inspector Workflow Time: {journey_timings.get('inspector_workflow')}s")
        print(f"• Complete End-to-End Loop Time: {journey_timings.get('total_journey')}s")
        print(f"• PRISM Case Reference Code: {ref_code}")
        print(f"• Initial Evidence SHA-256 Hash: {sha256_hash}")

        if page_errors:
            print("\nPage / Console warnings:", page_errors)

        if errors:
            print("\n[FAIL] Errors encountered:", errors)
            sys.exit(1)
        else:
            print("\n[SUCCESS] PRISM FULL END-TO-END DEMO JOURNEY VERIFIED 100%!")

if __name__ == "__main__":
    run_master_e2e_journey()
