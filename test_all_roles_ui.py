import asyncio
import os
import sys
from playwright.async_api import async_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ARTIFACTS_DIR = r"C:\Users\gowth\.gemini\antigravity-ide\brain\b31cada1-aba3-4edb-850b-040421bd012c"
BASE_UI_URL = "http://127.0.0.1:5173"

async def run():
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        print("[UI TEST 1] Login Screen...")
        await page.goto(f"{BASE_UI_URL}/login")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "ui_1_login.png"))
        print("  ✓ Saved ui_1_login.png")

        # -------------------------------------------------------------
        # ROLE 1: ADMIN
        # -------------------------------------------------------------
        print("[UI TEST 2] Admin Dashboard...")
        await page.fill("input[name='email']", "testinvest@recon")
        await page.fill("input[name='password']", "password123")
        await page.click("button[type='submit']")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "ui_2_admin_dashboard.png"))
        print("  ✓ Saved ui_2_admin_dashboard.png")

        print("[UI TEST 3] Admin Users Management...")
        await page.goto(f"{BASE_UI_URL}/admin/users")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "ui_3_admin_users.png"))
        print("  ✓ Saved ui_3_admin_users.png")

        print("[UI TEST 4] Admin Audit Logs...")
        await page.goto(f"{BASE_UI_URL}/admin/audit-logs")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "ui_4_admin_audit.png"))
        print("  ✓ Saved ui_4_admin_audit.png")

        # Logout
        await page.evaluate("localStorage.clear()")

        # -------------------------------------------------------------
        # ROLE 2: INVESTIGATOR
        # -------------------------------------------------------------
        print("[UI TEST 5] Investigator Dashboard...")
        await page.goto(f"{BASE_UI_URL}/login")
        await page.wait_for_timeout(500)
        await page.fill("input[name='email']", "invest@recon")
        await page.fill("input[name='password']", "password123")
        await page.click("button[type='submit']")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "ui_5_investigator_dashboard.png"))
        print("  ✓ Saved ui_5_investigator_dashboard.png")

        print("[UI TEST 6] Investigator Field Mapping...")
        await page.goto(f"{BASE_UI_URL}/investigator/mapping")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "ui_6_investigator_mapping.png"))
        print("  ✓ Saved ui_6_investigator_mapping.png")

        print("[UI TEST 7] Investigator Breaks...")
        await page.goto(f"{BASE_UI_URL}/investigator/breaks")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "ui_7_investigator_breaks.png"))
        print("  ✓ Saved ui_7_investigator_breaks.png")

        # Logout
        await page.evaluate("localStorage.clear()")

        # -------------------------------------------------------------
        # ROLE 3: APPROVER
        # -------------------------------------------------------------
        print("[UI TEST 8] Approver Dashboard...")
        await page.goto(f"{BASE_UI_URL}/login")
        await page.wait_for_timeout(500)
        await page.fill("input[name='email']", "testapprover@recon")
        await page.fill("input[name='password']", "password123")
        await page.click("button[type='submit']")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "ui_8_approver_dashboard.png"))
        print("  ✓ Saved ui_8_approver_dashboard.png")

        print("[UI TEST 9] Approver Approval History...")
        await page.goto(f"{BASE_UI_URL}/approver/approval-history")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "ui_9_approver_history.png"))
        print("  ✓ Saved ui_9_approver_history.png")

        await browser.close()
        print("\nAll 9 UI screenshots captured successfully!")

if __name__ == "__main__":
    asyncio.run(run())
