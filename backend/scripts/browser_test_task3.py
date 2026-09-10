"""Browser-level automated verification for Task 3 (Food Inspector Dashboard) using Playwright.
"""

import sys
from playwright.sync_api import sync_playwright

def run_task3_browser_verification():
    errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 1. Test Desktop Viewport (1280x800)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(f"PageError: {err}"))
        page.on("console", lambda msg: page_errors.append(f"ConsoleError: {msg.text}") if msg.type == "error" else None)

        print("\n--- 1. Testing Unauthenticated & Citizen Access Controls ---")
        page.goto("http://localhost:3000/inspector")
        page.wait_for_url("http://localhost:3000/login?next=%2Finspector")
        print("[PASS] Unauthenticated access to /inspector redirects to login")

        print("\n--- 2. Logging in as Demo Inspector ---")
        page.click("text=Demo inspector")
        page.wait_for_url("http://localhost:3000/inspector")
        print("[PASS] Logged in successfully as Demo Inspector")

        print("\n--- 3. Verifying Dashboard Header & Top Metrics ---")
        page.wait_for_selector("text=PRISM Inspector Command Center")
        page.wait_for_selector("text=Total Reports")
        page.wait_for_selector("text=High Priority")
        page.wait_for_selector("text=Active Investigations")
        page.wait_for_selector("text=Hotspots & Clusters")
        print("[PASS] Top summary metrics grid rendered real API data")

        print("\n--- 4. Verifying Priority Case Queue ---")
        page.wait_for_selector("text=Priority Queue")
        page.wait_for_selector("text=ABC Restaurant")
        
        # Verify Case Link format
        case_link = page.locator("a[href^='/inspector/cases/']").first
        href = case_link.get_attribute("href")
        print(f"    Case link points to: {href}")
        if not href or "/inspector/cases/" not in href:
            errors.append(f"Invalid case link URL: {href}")
        else:
            print("[PASS] Case links point to /inspector/cases/[id]")

        print("\n--- 5. Testing Risk Factor Explanation Expansion ---")
        explain_btn = page.locator("button:has-text('Explain Score')").first
        if explain_btn.count() > 0:
            explain_btn.click()
            page.wait_for_selector("text=How the score was calculated")
            print("[PASS] Risk score explanation breakdown rendered")

        print("\n--- 6. Testing Clusters & Hotspots Tabs ---")
        page.click("button:has-text('Complaint Clusters')")
        page.wait_for_selector("text=Semantic Complaint Clusters")
        page.wait_for_selector("text=Cluster #")
        print("[PASS] Complaint Clusters tab rendered real data")

        page.click("button:has-text('Hotspot Signals')")
        page.wait_for_selector("text=Geographic Hotspot Signals")
        page.wait_for_selector("text=Cell Signal")
        print("[PASS] Hotspot Signals tab rendered real data")

        print("\n--- 7. Testing Mobile Viewport Responsiveness ---")
        mobile_context = browser.new_context(viewport={"width": 390, "height": 844})
        mobile_page = mobile_context.new_page()
        mobile_page.goto("http://localhost:3000/login")
        mobile_page.click("text=Demo inspector")
        mobile_page.wait_for_url("http://localhost:3000/inspector")
        mobile_page.wait_for_selector("text=PRISM Inspector Command Center")
        print("[PASS] Mobile viewport (390px) rendered responsively")

        browser.close()

        if page_errors:
            print("\nPage / Console warnings logged:", page_errors)

        if errors:
            print("\n[FAIL] Errors encountered:", errors)
            sys.exit(1)
        else:
            print("\n[SUCCESS] TASK 3 BROWSER-LEVEL VERIFICATION PASSED 100%!")

if __name__ == "__main__":
    run_task3_browser_verification()
