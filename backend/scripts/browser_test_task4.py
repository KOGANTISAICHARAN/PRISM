"""Browser-level automated verification for Task 4 (Inspector Case Detail & Investigation Workspace) using Playwright.
"""

import sys
from playwright.sync_api import sync_playwright

def run_task4_browser_verification():
    errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(f"PageError: {err}"))
        page.on("console", lambda msg: page_errors.append(f"ConsoleError: {msg.text}") if msg.type == "error" else None)

        print("\n--- 1. Logging in as Demo Inspector ---")
        page.goto("http://localhost:3000/login")
        page.wait_for_selector("text=Demo inspector")
        page.click("text=Demo inspector")
        page.wait_for_url("http://localhost:3000/inspector")
        print("[PASS] Logged in successfully as Demo Inspector")

        print("\n--- 2. Opening Case Detail Page ---")
        page.wait_for_selector("text=ABC Restaurant")
        case_link = page.locator("a[href^='/inspector/cases/']").first
        href = case_link.get_attribute("href")
        print(f"    Navigating to case: {href}")
        case_link.click()

        page.wait_for_selector("text=Case & Establishment Profile")
        print("[PASS] Inspector case investigation page loaded")

        print("\n--- 3. Verifying Case Profile & Evidence Vault ---")
        page.wait_for_selector("text=ABC Restaurant")
        page.wait_for_selector("text=Evidence Vault & Integrity Records")
        page.wait_for_selector("text=SHA-256 Immutable Hash")
        print("[PASS] Case profile and Evidence Vault records loaded")

        # Test SHA-256 verification
        verify_btn = page.locator("button:has-text('Verify SHA-256 Integrity')")
        if verify_btn.count() > 0:
            verify_btn.first.click()
            page.wait_for_selector("text=SHA-256 Verified")
            print("[PASS] Evidence SHA-256 hash verified")

        print("\n--- 4. Verifying AI Visual Signal & Explainable Risk Score ---")
        page.wait_for_selector("text=AI Visual Analysis Signal")
        page.wait_for_selector("text=Explainable Risk Engine Signal")
        page.wait_for_selector("text=How the score was calculated")
        print("[PASS] AI visual signal and risk factor list rendered")

        print("\n--- 5. Testing Investigation Checklist & Notes ---")
        # If 'Start Inspection' button exists, click it
        start_btn = page.locator("button:has-text('Start Inspection')")
        if start_btn.count() > 0:
            start_btn.click()
            page.wait_for_selector("text=8-Item Inspection Checklist")

        # Check off a checklist item
        checkbox = page.locator("input[type='checkbox']").first
        if not checkbox.is_checked():
            checkbox.check()
            time.sleep(0.5)
            print("[PASS] Toggled investigation checklist item")

        # Save inspector notes
        notes_field = page.locator("textarea#inspectorNotes")
        notes_field.fill("Site visit performed. Verified storage temperature log and kitchen cleanliness.")
        page.click("button:has-text('Save Notes & Findings')")
        page.wait_for_selector("text=Investigator notes and findings saved")
        print("[PASS] Investigator notes and findings saved")

        print("\n--- 6. Testing Human Case Decision Confirmation ---")
        page.select_option("select#decisionStatus", "ACTIONED")
        page.fill("textarea#decisionNoteInput", "Inspection completed. Notice served to rectify storage temperatures.")
        page.click("button:has-text('Record Final Decision')")
        
        page.wait_for_selector("text=Confirm Human Inspector Decision")
        page.click("button:has-text('Confirm Decision')")

        page.wait_for_selector("text=Case decision recorded: ACTIONED", timeout=10000)
        print("[PASS] Human case decision recorded & status updated to ACTIONED")

        print("\n--- 7. Testing Citizen Access Control Protection ---")
        page.goto("http://localhost:3000/login")
        page.click("text=Demo citizen")
        page.wait_for_url("http://localhost:3000/")

        # Attempt to access inspector case detail as citizen
        page.goto(f"http://localhost:3000{href}")
        page.wait_for_url("http://localhost:3000/")
        print("[PASS] Citizen account blocked from inspector case detail page")

        browser.close()

        if page_errors:
            print("\nPage / Console warnings logged:", page_errors)

        if errors:
            print("\n[FAIL] Errors encountered:", errors)
            sys.exit(1)
        else:
            print("\n[SUCCESS] TASK 4 BROWSER-LEVEL VERIFICATION PASSED 100%!")

if __name__ == "__main__":
    run_task4_browser_verification()
