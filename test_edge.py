import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        print("Launching Edge...")
        browser = await p.chromium.launch(channel="msedge", headless=True)
        page = await browser.new_page()
        await page.goto("http://127.0.0.1:5173")
        print("Title:", await page.title())
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
