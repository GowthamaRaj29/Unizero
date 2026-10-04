import asyncio
from playwright.async_api import async_playwright
import os

async def run():
    async with async_playwright() as p:
        print("Launching Edge...")
        browser = await p.chromium.launch(channel="msedge", headless=True)
        page = await browser.new_page()
        
        # 1. Investigator login
        print("Logging in as Investigator...")
        await page.goto("http://127.0.0.1:5173")
        await page.wait_for_timeout(1000)
        await page.fill("input[name='email']", "invest@recon")
        await page.fill("input[name='password']", "password123")
        await page.click("button[type='submit']")
        await page.wait_for_timeout(2000)
        
        await page.screenshot(path="frontend_investigator.png")
        print("Investigator logged in!")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
