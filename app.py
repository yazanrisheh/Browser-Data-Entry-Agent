import asyncio
from browser_use import Browser

async def export():
    browser = Browser(cdp_url="http://localhost:9222")
    await browser.start()
    await browser.export_storage_state('auth.json')
    await browser.stop()

asyncio.run(export())