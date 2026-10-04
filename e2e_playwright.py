import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("Navigating to frontend...")
        await page.goto("http://127.0.0.1:5173")
        
        # Wait for the page to load
        await page.wait_for_timeout(2000)
        
        print("Page title:", await page.title())
        
        # We'll just take a screenshot to prove we opened it
        await page.screenshot(path="frontend_screenshot_1.png")
        print("Saved screenshot to frontend_screenshot_1.png")
        
        print("Checking if we need to register first account (Admin)")
        if await page.is_visible("text=Register"):
            print("Registering Admin...")
            await page.click("text=Register")
            await page.wait_for_timeout(1000)
            await page.fill("input[name='full_name']", "Playwright Admin")
            await page.fill("input[name='email']", "pwadmin@example.com")
            await page.fill("input[name='password']", "password")
            await page.click("button[type='submit']")
            await page.wait_for_timeout(2000)
            await page.screenshot(path="frontend_screenshot_2.png")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
