"""Browser-level automated verification for Task 2 (Citizen Reports & Status Tracking) using Playwright.
"""

import sys
import time
from playwright.sync_api import sync_playwright

def run_task2_browser_verification():
    errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844})  # Mobile viewport (iPhone 12/13/14)
        page = context.new_page()

        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(f"PageError: {err}"))
        page.on("console", lambda msg: page_errors.append(f"ConsoleError: {msg.text}") if msg.type == "error" else None)

        print("\n--- 1. Testing Unauthenticated Redirects ---")
        page.goto("http://localhost:3000/reports")
        page.wait_for_url("http://localhost:3000/login?next=%2Freports")
        print("[PASS] Unauthenticated access to /reports redirects to login")

        print("\n--- 2. Logging in as Demo Citizen ---")
        page.click("text=Demo citizen")
        page.wait_for_url("http://localhost:3000/reports")
        print("[PASS] Logged in and redirected to /reports")

        print("\n--- 3. Verifying /reports List ---")
        page.wait_for_selector("text=Submitted Reports")
        page.wait_for_selector("text=ABC Restaurant")
        reports = page.locator("a[href^='/reports/']")
        count = reports.count()
        print(f"[PASS] /reports list loaded {count} reports")
        if count == 0:
            errors.append("No reports found in /reports list")

        print("\n--- 4. Opening Report Detail (/reports/[id]) ---")
        first_report = reports.first
        href = first_report.get_attribute("href")
        print(f"    Opening report link: {href}")
        first_report.click()

        page.wait_for_selector("text=Status Timeline")
        page.wait_for_selector("text=Report Summary")
        print("[PASS] Report detail page loaded successfully")

        # Verify SHA-256 Integrity Verification Button if evidence exists
        verify_btn = page.locator("button:has-text('Verify SHA-256 Integrity')")
        if verify_btn.count() > 0:
            print("    Testing SHA-256 verification button...")
            verify_btn.first.click()
            page.wait_for_selector("text=SHA-256 Verified")
            print("[PASS] SHA-256 verification completed successfully")

        print("\n--- 5. Verifying Bottom Navigation & Profile Page ---")
        profile_link = page.locator("a[href='/profile']")
        profile_link.click()
        page.wait_for_selector("text=My Account")
        page.wait_for_selector("text=Demo Citizen")
        page.wait_for_selector("text=citizen@prism.demo")
        print("[PASS] Profile page loaded account details")

        print("\n--- 6. Testing Sign Out ---")
        page.click("text=Sign out of PRISM")
        page.wait_for_url("http://localhost:3000/")
        print("[PASS] Sign out successful and redirected home")

        browser.close()

        if page_errors:
            print("\nPage / Console warnings logged:", page_errors)

        if errors:
            print("\n[FAIL] Errors encountered:", errors)
            sys.exit(1)
        else:
            print("\n[SUCCESS] TASK 2 BROWSER-LEVEL VERIFICATION PASSED 100%!")

if __name__ == "__main__":
    run_task2_browser_verification()
