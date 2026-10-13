"""Step 1: download the file from the results page with Playwright."""
import logging
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page, Playwright, sync_playwright

from .config import GameConfig
from .download import USER_AGENT, DownloadError, keep_if_valid, partial_path

log = logging.getLogger(__name__)

# Installed Edge or Chrome first, then Playwright's bundled chromium (None).
CHANNELS = ("msedge", "chrome", None)
COOKIE_BUTTONS = (
    "button:has-text('Αποδοχή όλων')",
    "button:has-text('Αποδοχή')",
    "button:has-text('Συμφωνώ')",
    "button:has-text('Accept all')",
    "#onetrust-accept-btn-handler",
)


def download_via_browser(game: GameConfig, year: str, output_dir: Path, *, headless: bool = True) -> Path:
    """Selects the year in the results archive section, which triggers the download."""
    save_path = output_dir / game.filename(year)
    temp_path = partial_path(save_path)
    try:
        with sync_playwright() as p:
            browser = _launch(p, headless)
            try:
                context = browser.new_context(accept_downloads=True, locale="el-GR", user_agent=USER_AGENT)
                page = context.new_page()
                log.info("[*] Loading page...")
                page.goto(game.page_url, wait_until="domcontentloaded", timeout=45000)

                _accept_cookies(page)
                select = _find_year_dropdown(page, game)

                log.info(f"[*] Selecting year {year} in the results archive section...")
                with page.expect_download(timeout=15000) as download_info:
                    if is_option_selected(select, year):
                        # The year is already selected, so select_option would not
                        # fire a change event; dispatch it explicitly.
                        select.dispatch_event("change")
                    else:
                        select.select_option(year)
                download_info.value.save_as(temp_path)
            finally:
                browser.close()
    except PlaywrightError as e:
        temp_path.unlink(missing_ok=True)
        raise DownloadError(f"Browser step failed: {e}") from e

    keep_if_valid(temp_path, save_path)
    log.info(f"[✓] File downloaded via the browser: {save_path}")
    return save_path


def _launch(p: Playwright, headless: bool):
    errors = []
    for channel in CHANNELS:
        name = channel or "default chromium"
        try:
            browser = p.chromium.launch(
                headless=headless,
                channel=channel,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
        except PlaywrightError as e:
            errors.append(f"{name}: {str(e).splitlines()[0]}")
            continue
        log.info(f"[*] Browser launched (channel: {name}).")
        return browser
    raise DownloadError(f"No browser could be launched ({'; '.join(errors)})")


def _accept_cookies(page: Page) -> None:
    button = page.locator(", ".join(COOKIE_BUTTONS)).first
    if not is_visible_within(button, 5000):
        return
    log.info("[*] Accepting cookies...")
    try:
        button.click()
    except PlaywrightError as e:
        log.info(f"[-] Could not click the cookie button: {e}")
        return
    if not is_hidden_within(button, 5000):
        log.info("[-] The cookie banner did not close.")


def _find_year_dropdown(page: Page, game: GameConfig) -> Locator:
    """Finds the year dropdown in the results archive section ("Αρχείο Αποτελεσμάτων")."""
    preferred = [page.locator(selector).first for selector in game.dropdown_selectors]
    if is_visible_within(preferred[0], 10000):
        return preferred[0]
    # The page has rendered by now, so the other selectors don't need to wait.
    for locator in preferred[1:]:
        if locator.is_visible():
            return locator

    candidates = page.locator(game.fallback_selector)
    count = candidates.count()
    if count == 0:
        raise DownloadError("Year dropdown not found on the page")
    return candidates.nth(game.fallback_index) if count > 1 else candidates.first


def is_visible_within(locator: Locator, timeout: int) -> bool:
    """Waits up to `timeout` ms for the element to become visible (is_visible doesn't wait)."""
    try:
        locator.wait_for(state="visible", timeout=timeout)
        return True
    except PlaywrightError:
        return False


def is_hidden_within(locator: Locator, timeout: int) -> bool:
    """Waits up to `timeout` ms for the element to be hidden or removed."""
    try:
        locator.wait_for(state="hidden", timeout=timeout)
        return True
    except PlaywrightError:
        return False


def is_option_selected(select: Locator, value: str) -> bool:
    """Checks whether the selected option of the select has this value or label."""
    return select.evaluate(
        "(s, v) => { const o = s.options[s.selectedIndex];"
        " return !!o && (o.value === v || o.label.trim() === v); }",
        value,
    )
