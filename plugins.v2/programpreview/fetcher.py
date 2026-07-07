# -*- coding: utf-8 -*-
"""节目预告页面抓取工具。"""

import asyncio
import os
import re
import urllib.request
from pathlib import Path

from .constants import UA

try:
    from app.log import logger
except Exception:
    import logging
    logger = logging.getLogger(__name__)


_PLAYWRIGHT_BROWSER_AVAILABLE = None
_PLAYWRIGHT_BROWSER_WARNING_EMITTED = False
_CLOAKBROWSER_AVAILABLE = None
_CLOAKBROWSER_WARNING_EMITTED = False
_PLAYWRIGHT_BROWSER_MISSING_MARKERS = (
    "Executable doesn't exist",
    "playwright install",
    "chromium_headless_shell",
    "chrome-headless-shell",
)


def is_playwright_browser_missing_error(err):
    text = str(err or "")
    return any(marker in text for marker in _PLAYWRIGHT_BROWSER_MISSING_MARKERS)


def mark_playwright_browser_unavailable(err=None):
    global _PLAYWRIGHT_BROWSER_AVAILABLE, _PLAYWRIGHT_BROWSER_WARNING_EMITTED
    _PLAYWRIGHT_BROWSER_AVAILABLE = False
    if err is not None and not _PLAYWRIGHT_BROWSER_WARNING_EMITTED:
        _PLAYWRIGHT_BROWSER_WARNING_EMITTED = True
        logger.warning("Playwright 浏览器内核缺失，本轮优先尝试 MP CloakBrowser，仍不可用时改用静态页面/API 降级抓取；如需 Playwright 动态渲染，请在 MoviePilot 容器内安装 Playwright 浏览器。")


def playwright_browser_available():
    return _PLAYWRIGHT_BROWSER_AVAILABLE is not False


def mark_cloakbrowser_unavailable(err=None):
    global _CLOAKBROWSER_AVAILABLE, _CLOAKBROWSER_WARNING_EMITTED
    _CLOAKBROWSER_AVAILABLE = False
    if err is not None and not _CLOAKBROWSER_WARNING_EMITTED:
        _CLOAKBROWSER_WARNING_EMITTED = True
        logger.debug(f'MP CloakBrowser 动态抓取不可用，本轮改用静态页面/API 降级：{err!r}')


def cloakbrowser_available():
    return _CLOAKBROWSER_AVAILABLE is not False


def browser_args():
    return [
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-blink-features=AutomationControlled',
        '--lang=zh-CN',
    ]


def prepare_cloakbrowser_env():
    if os.environ.get('CLOAKBROWSER_CACHE_DIR') or os.environ.get('CLOAKBROWSER_BINARY_PATH'):
        return
    for cache_dir in (Path('/core/.cloakbrowser'), Path('/moviepilot/.cloakbrowser')):
        if not cache_dir.exists():
            continue
        binaries = sorted(cache_dir.glob('chromium-*/chrome'), reverse=True)
        if binaries:
            os.environ['CLOAKBROWSER_CACHE_DIR'] = str(cache_dir)
            return


def _sync_wait(page, timeout):
    try:
        page.wait_for_timeout(max(0, int(timeout or 0)))
    except Exception:
        pass


def _launch_cloakbrowser_context(viewport=None):
    from cloakbrowser import launch_context

    prepare_cloakbrowser_env()
    context = launch_context(
        headless=True,
        args=browser_args(),
        locale='zh-CN',
        viewport=viewport or {'width': 1366, 'height': 900},
        stealth_args=True,
    )
    try:
        context.set_extra_http_headers({
            'User-Agent': UA,
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.1',
        })
    except Exception:
        pass
    return context


def cloakbrowser_page_html_text_sync(url, wait=5000, viewport=None, activate_labels=None, scroll_labels=False):
    if not cloakbrowser_available():
        return None
    context = None
    try:
        context = _launch_cloakbrowser_context(viewport=viewport)
        page = context.new_page()
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        _sync_wait(page, min(wait, 2500))
        for label in activate_labels or ():
            try:
                loc = page.get_by_text(label, exact=True).first
                if loc.count():
                    if scroll_labels:
                        try:
                            loc.scroll_into_view_if_needed(timeout=2500)
                        except Exception:
                            pass
                    loc.click(timeout=2500, force=True)
                    _sync_wait(page, 1500)
            except Exception:
                continue
        text = page.locator('body').inner_text(timeout=15000)
        html = page.content()
        return html, text
    except Exception as err:
        mark_cloakbrowser_unavailable(err)
        return None
    finally:
        try:
            if context:
                context.close()
        except Exception:
            pass


async def cloakbrowser_page_html_text(url, wait=5000, viewport=None, activate_labels=None, scroll_labels=False):
    return await asyncio.to_thread(
        cloakbrowser_page_html_text_sync,
        url,
        wait,
        viewport,
        activate_labels,
        scroll_labels,
    )


def cloakbrowser_evaluate_sync(url, script, wait=1800, viewport=None):
    if not cloakbrowser_available():
        return None
    context = None
    try:
        context = _launch_cloakbrowser_context(viewport=viewport)
        page = context.new_page()
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        _sync_wait(page, wait)
        return page.evaluate(script)
    except Exception as err:
        mark_cloakbrowser_unavailable(err)
        return None
    finally:
        try:
            if context:
                context.close()
        except Exception:
            pass


def _static_html(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode('utf-8', 'ignore')


def _html_to_text(html):
    return re.sub(r'<[^>]+>', '\n', html)


async def _dynamic_html_text(url, wait=5000, viewport=None):
    if not playwright_browser_available():
        return None
    browser = None
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            page_args = {'user_agent': UA}
            if viewport:
                page_args['viewport'] = viewport
            page = await browser.new_page(**page_args)
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(min(wait, 2500))
            text = await page.locator('body').inner_text(timeout=15000)
            html = await page.content()
            await browser.close()
            return html, text
    except Exception as err:
        if is_playwright_browser_missing_error(err):
            mark_playwright_browser_unavailable(err)
        else:
            logger.warning(f'动态页面抓取失败，降级为静态页面：{url}，原因：{err!r}')
        try:
            if browser:
                await browser.close()
        except Exception:
            pass
        return None


async def page_text(url, wait=5000):
    result = await _dynamic_html_text(url, wait=wait)
    if not result:
        result = await cloakbrowser_page_html_text(url, wait=wait)
    if result:
        return result[1]
    return _html_to_text(_static_html(url))

async def page_html_text(url, wait=5000):
    result = await _dynamic_html_text(url, wait=wait)
    if not result:
        result = await cloakbrowser_page_html_text(url, wait=wait)
    if result:
        return result
    html = _static_html(url)
    return html, _html_to_text(html)

async def iqiyi_filtered_page_html_text(url, wait=5000):
    """Load an iQIYI list page and activate the visible upcoming filter."""
    if not playwright_browser_available():
        result = await cloakbrowser_page_html_text(
            url,
            wait=wait,
            viewport={'width': 1366, 'height': 900},
            activate_labels=('即将上线', '最热'),
        )
        if result:
            return result
        return await page_html_text(url, wait=wait)
    browser = None
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
    except Exception as err:
        if is_playwright_browser_missing_error(err):
            mark_playwright_browser_unavailable(err)
        try:
            if browser:
                await browser.close()
        except Exception:
            pass
        result = await cloakbrowser_page_html_text(
            url,
            wait=wait,
            viewport={'width': 1366, 'height': 900},
            activate_labels=('即将上线', '最热'),
        )
        if result:
            return result
        return await page_html_text(url, wait=wait)
