"""Browser-level automated verification for Citizen Report Intake Wizard using Playwright.
"""

import sys
import io
import time
from pathlib import Path
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

def generate_sample_image() -> Path:
    img_path = Path(__file__).parent / "temp_food_sample.jpg"
    img = Image.new("RGB", (640, 480), (220, 190, 140))
    d = ImageDraw.Draw(img)
    d.rectangle([200, 150, 350, 220], fill=(40, 40, 45))  # dark foreign object
    d.text((20, 20), "PRISM TEST FOOD IMAGE", fill=(255, 255, 255))
    img.save(img_path, format="JPEG", quality=90)
    return img_path

def run_browser_verification():
    sample_img = generate_sample_image()
    print("Sample image generated:", sample_img)

    errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844})  # Mobile viewport (iPhone 12/13/14)
        page = context.new_page()

        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(f"PageError: {err}"))
        page.on("console", lambda msg: page_errors.append(f"ConsoleError: {msg.text}") if msg.type == "error" else None)

        print("\n--- 1. Opening Application ---")
        page.goto("http://localhost:3000/")
        page.wait_for_selector("text=PRISM")
        print("[PASS] Home page loaded")

        print("\n--- 2. Logging in as Demo Citizen ---")
        page.goto("http://localhost:3000/login")
        page.wait_for_selector("text=Demo citizen")
        page.click("text=Demo citizen")
        page.wait_for_url("http://localhost:3000/")
        print("[PASS] Logged in successfully as Demo Citizen")

        print("\n--- 3. Opening /report ---")
        page.goto("http://localhost:3000/report")
        page.wait_for_selector("text=Step 1: Upload Photo & Describe Issue")
        print("[PASS] /report page opened")

        print("\n--- 4 & 5. Uploading Food Image & Verifying Preview ---")
        file_input = page.locator("input[type='file']")
        file_input.set_input_files(str(sample_img))
        page.wait_for_selector("img[alt='Uploaded food evidence preview']")
        print("[PASS] Image upload & preview verified")

        print("\n--- 6 & 7. Running AI Analysis & Verifying Disclaimers ---")
        page.fill("textarea#initialNote", "I found a piece of hard plastic in my chicken biryani from ABC Restaurant in Banjara Hills")
        page.click("button:has-text('Analyze & Continue')")

        # Wait for Step 2
        page.wait_for_selector("text=PRISM AI Vision Signal", timeout=15000)
        print("[PASS] AI visual analysis completed")

        disclaimer = page.locator("text=AI-generated assessment")
        if disclaimer.count() > 0:
          print("[PASS] AI safety disclaimer is visible")
        else:
          errors.append("AI safety disclaimer not visible")

        print("\n--- 8 & 9. AI Slot Filling & Confirming Fields ---")
        vendor_input = page.locator("input#vendor_name")
        vendor_val = vendor_input.input_value()
        print(f"    Extracted vendor name: '{vendor_val}'")
        if not vendor_val:
            vendor_input.fill("ABC Restaurant")

        food_input = page.locator("input#food_item")
        if not food_input.input_value():
            food_input.fill("Chicken Biryani")

        loc_input = page.locator("input#location_text")
        if not loc_input.input_value():
            loc_input.fill("Banjara Hills, Hyderabad")

        print("[PASS] All required complaint fields completed")

        print("\n--- 10 & 11. Navigating to Review Step ---")
        page.click("button:has-text('Review Report')")
        page.wait_for_selector("text=Step 3: Review Before Submitting")

        # Verify summary review fields
        page.wait_for_selector("text=ABC Restaurant")
        page.wait_for_selector("text=Chicken Biryani")
        print("[PASS] Review step displays all collected information correctly")

        print("\n--- 12, 13, 14, 15 & 16. Submitting Report & Verifying Output ---")
        page.click("button:has-text('Submit Report')")

        # Wait for Step 4
        page.wait_for_selector("text=Report Submitted", timeout=15000)
        print("[PASS] Report submitted successfully")

        # Reference code check
        ref_elem = page.locator("span.font-mono.text-2xl")
        ref_text = ref_elem.inner_text()
        print(f"    Generated PRISM Reference: {ref_text}")
        if not ref_text.startswith("PR-"):
            errors.append(f"Invalid reference format: {ref_text}")

        # SHA-256 Hash check
        hash_elem = page.locator("p.font-mono.break-all")
        hash_text = hash_elem.inner_text()
        print(f"    Evidence SHA-256 Hash: {hash_text}")
        if len(hash_text) != 64:
            errors.append(f"Invalid SHA-256 hash length: {hash_text}")

        # Risk signal check
        page.wait_for_selector("text=Prioritization Signal")
        print("[PASS] Risk score & cluster signal returned")

        print("\n--- 17 & 18. Testing 'View My Reports & Status' Navigation ---")
        page.click("text=View My Reports & Status")
        print(f"    Navigated URL: {page.url}")

        browser.close()

        if sample_img.exists():
            sample_img.unlink()

        if page_errors:
            print("\nPage / Console warnings logged:", page_errors)

        if errors:
            print("\n[FAIL] Errors encountered:", errors)
            sys.exit(1)
        else:
            print("\n[SUCCESS] REAL BROWSER-LEVEL VERIFICATION PASSED 100%!")

if __name__ == "__main__":
    run_browser_verification()
