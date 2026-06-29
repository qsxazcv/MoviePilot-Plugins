# -*- coding: utf-8 -*-
"""节目预告页面抓取工具。"""

import re
import urllib.request

from .constants import UA


async def page_text(url, wait=5000):
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = await browser.new_page(user_agent=UA)
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(min(wait, 2500))
            text = await page.locator('body').inner_text(timeout=15000)
            await browser.close()
            return text
    except Exception:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            html = r.read().decode('utf-8', 'ignore')
        return re.sub(r'<[^>]+>', '\n', html)

async def page_html_text(url, wait=5000):
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = await browser.new_page(user_agent=UA)
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(min(wait, 2500))
            text = await page.locator('body').inner_text(timeout=15000)
            html = await page.content()
            await browser.close()
            return html, text
    except Exception:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            html = r.read().decode('utf-8', 'ignore')
        return html, re.sub(r'<[^>]+>', '\n', html)

async def iqiyi_filtered_page_html_text(url, wait=5000):
    """Load an iQIYI list page and activate the visible upcoming filter."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = await browser.new_page(user_agent=UA, viewport={'width': 1366, 'height': 900})
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(min(wait, 2500))
            for label in ('即将上线', '最热'):
                try:
                    loc = page.get_by_text(label, exact=True).first
                    if await loc.count():
                        await loc.click(timeout=2500)
                        await page.wait_for_timeout(1500)
                except Exception:
                    continue
            text = await page.locator('body').inner_text(timeout=15000)
            html = await page.content()
            await browser.close()
            return html, text
    except Exception:
        return await page_html_text(url, wait=wait)
