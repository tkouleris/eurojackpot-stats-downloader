import argparse
from datetime import date, datetime
import io
import os
import sys
import time
import urllib.request
from pathlib import Path
import shutil
import platform
import subprocess
import shlex
import zipfile
from dotenv import load_dotenv

from helpers import log_to_file

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

URL = "https://www.allwyn.gr/el/tzoker/draws-results"
TARGET_YEAR = str(datetime.now().year)
OUTPUT_DIR = Path(__file__).parent / "downloads"
LOG_FILE = Path(__file__).parent / "log_joker.txt"
# How many days into the new year the previous year is downloaded again.
NEW_YEAR_GRACE_DAYS = 7

load_dotenv()

DEST_PATH = os.getenv("JOKER_DEST_PATH")
CACHE_COMMAND = os.getenv("JOKER_CACHE_COMMAND")
MAIN_DEST_PATH = os.getenv("MAIN_DEST_PATH")
DEST_OWNER = os.getenv("OWNER")
DEST_GROUP = os.getenv("GROUP")


def is_valid_download(file_path: Path | None) -> bool:
    """Checks that the file exists and is a valid xlsx (zip) file."""
    return file_path is not None and file_path.is_file() and zipfile.is_zipfile(file_path)


def target_filename(year: str) -> str:
    """Fixed filename the app expects, regardless of the download source."""
    return f"Joker_{year}.xlsx"


def years_to_download(today: date) -> list[tuple[str, bool]]:
    """
    Returns the years to download as (year, required) pairs.

    During the first days of January the previous year is downloaded again, so that
    the draws of the last days of December are picked up. The new year is optional
    then, because its file doesn't exist before the first draw.
    """
    current = str(today.year)
    if today.month == 1 and today.day <= NEW_YEAR_GRACE_DAYS:
        return [(str(today.year - 1), True), (current, False)]
    return [(current, True)]


def is_visible_within(locator, timeout: int) -> bool:
    """Waits up to `timeout` ms for the element to become visible (is_visible doesn't wait)."""
    try:
        locator.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False


def is_option_selected(select, value: str) -> bool:
    """Checks whether the selected option of the select has this value or label."""
    return select.evaluate(
        "(s, v) => { const o = s.options[s.selectedIndex];"
        " return !!o && (o.value === v || o.label.trim() === v); }",
        value,
    )


def download_joker_draws(
    url: str = URL,
    year: str = TARGET_YEAR,
    output_dir: Path = OUTPUT_DIR,
    headless: bool = True
) -> Path | None:
    """
    Visits the page https://www.allwyn.gr/el/tzoker/draws-results
    and downloads the Joker draws file for the selected year (e.g. 2026).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] Starting download of Joker draws for year {year}...")
    log_to_file(f"[*] Starting download of Joker draws for year {year}...", LOG_FILE)
    print(f"[*] Target page: {url}")
    log_to_file(f"[*] Target page: {url}", LOG_FILE)

    downloaded_file_path = None

    # 1. Try to download through browser automation (Playwright)
    try:
        with sync_playwright() as p:
            browser = None
            # Pick an available browser/channel
            for channel in ["msedge", "chrome", None]:
                try:
                    launch_args = {
                        "headless": headless,
                        "args": [
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox"
                        ]
                    }
                    if channel:
                        launch_args["channel"] = channel
                    browser = p.chromium.launch(**launch_args)
                    print(f"[*] Browser launched (channel: {channel or 'default chromium'}).")
                    log_to_file(f"[*] Browser launched (channel: {channel or 'default chromium'}).", LOG_FILE)
                    break
                except Exception:
                    continue

            if browser:
                context = browser.new_context(
                    accept_downloads=True,
                    locale="el-GR",
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                try:
                    print("[*] Loading page...")
                    log_to_file("[*] Loading page...", LOG_FILE)
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    time.sleep(2)

                    # Handle the cookie banner
                    cookie_buttons = [
                        "button:has-text('Αποδοχή όλων')",
                        "button:has-text('Αποδοχή')",
                        "button:has-text('Συμφωνώ')",
                        "button:has-text('Accept all')",
                        "#onetrust-accept-btn-handler"
                    ]
                    btn = page.locator(", ".join(cookie_buttons)).first
                    if is_visible_within(btn, 5000):
                        try:
                            print("[*] Accepting cookies...")
                            log_to_file("[*] Accepting cookies...", LOG_FILE)
                            btn.click()
                            time.sleep(1)
                        except Exception:
                            pass

                    # Find the year dropdown in the results archive section (.download select)
                    download_select = page.locator(".download select, div.download select").first
                    if not is_visible_within(download_select, 10000):
                        # Fallback lookup for the year dropdown
                        candidates = page.locator("select[aria-label='Έτος']")
                        if candidates.count() > 1:
                            download_select = candidates.nth(1)
                        elif candidates.count() == 1:
                            download_select = candidates.first

                    if download_select and download_select.count() > 0:
                        print(f"[*] Selecting year {year} in the results archive section...")
                        log_to_file(f"[*] Selecting year {year} in the results archive section...", LOG_FILE)
                        try:
                            with page.expect_download(timeout=15000) as download_info:
                                if is_option_selected(download_select, year):
                                    # The year is already selected, so select_option would not
                                    # fire a change event; dispatch it explicitly.
                                    download_select.dispatch_event("change")
                                else:
                                    download_select.select_option(year)
                            download = download_info.value
                            save_path = output_dir / target_filename(year)
                            download.save_as(save_path)
                            if is_valid_download(save_path):
                                downloaded_file_path = save_path
                                print(f"[✓] File downloaded via the browser: {save_path}")
                                log_to_file(f"[✓] File downloaded via the browser: {save_path}", LOG_FILE)
                            else:
                                print(f"[-] Browser download is not a valid xlsx: {save_path}")
                                log_to_file(f"[-] Browser download is not a valid xlsx: {save_path}", LOG_FILE)
                        except Exception as e:
                            print(f"[-] Waiting for download event failed: {e}")
                            log_to_file(f"[-] Waiting for download event failed: {e}", LOG_FILE)

                except Exception as e:
                    print(f"[!] Navigation error: {e}")
                    log_to_file(f"[!] Navigation error: {e}", LOG_FILE)
                finally:
                    browser.close()

    except Exception as e:
        print(f"[!] Playwright startup error: {e}")
        log_to_file(f"[!] Playwright startup error: {e}", LOG_FILE)

    # 2. Fall back to a direct download from the official media repository if the browser step failed
    if not is_valid_download(downloaded_file_path):
        direct_url = f"https://media.opap.gr/Excel_xlsx/5104/{target_filename(year)}"
        print(f"[*] Trying direct download from: {direct_url}")
        log_to_file(f"[*] Trying direct download from: {direct_url}", LOG_FILE)
        try:
            req = urllib.request.Request(
                direct_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
            )
            save_path = output_dir / target_filename(year)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read() if resp.status == 200 else b""
                if not zipfile.is_zipfile(io.BytesIO(data)):
                    print("[-] Direct download did not return a valid xlsx file.")
                    log_to_file("[-] Direct download did not return a valid xlsx file.", LOG_FILE)
                else:
                    save_path.write_bytes(data)
                    downloaded_file_path = save_path
                    print(f"[✓] File downloaded directly: {save_path} ({len(data)} bytes)")
                    log_to_file(f"[✓] File downloaded directly: {save_path} ({len(data)} bytes)", LOG_FILE)
        except Exception as e:
            print(f"[-] Direct download error: {e}")
            log_to_file(f"[-] Direct download error: {e}", LOG_FILE)

    if not is_valid_download(downloaded_file_path):
        return None

    return downloaded_file_path


def copy_to_env_path(file_path: Path) -> Path | None:
    """Copies the downloaded file to the path set in .env."""
    if not DEST_PATH:
        print("[!] JOKER_DEST_PATH is not set in .env")
        log_to_file("[!] JOKER_DEST_PATH is not set in .env", LOG_FILE)
        return None

    try:
        destination_dir = Path(DEST_PATH)
        destination_dir.mkdir(parents=True, exist_ok=True)

        destination_file = destination_dir / file_path.name
        temp_file = destination_dir / f".{file_path.name}.tmp"

        # Copy to a temp file and replace atomically, so the
        # destination is never left half-written.
        try:
            shutil.copy2(file_path, temp_file)
            os.replace(temp_file, destination_file)
        finally:
            temp_file.unlink(missing_ok=True)

        print(f"[✓] File copied to: {destination_file}")
        log_to_file(f"[✓] File copied to: {destination_file}", LOG_FILE)

        return destination_file

    except Exception as e:
        print(f"[-] File copy error: {e}")
        log_to_file(f"[-] File copy error: {e}", LOG_FILE)
        return None

def change_file_owner(file_path: Path) -> None:
    """Changes the file owner, on Linux only."""
    if platform.system() != "Linux":
        return

    if not DEST_OWNER:
        print("[!] OWNER is not set in .env")
        log_to_file("[!] OWNER is not set in .env", LOG_FILE)
        return

    if not DEST_GROUP:
        print("[!] GROUP is not set in .env")
        log_to_file("[!] GROUP is not set in .env", LOG_FILE)
        return

    try:
        import pwd
        import grp

        uid = pwd.getpwnam(DEST_OWNER).pw_uid
        gid = grp.getgrnam(DEST_GROUP).gr_gid

        os.chown(file_path, uid, gid)

        print(f"[✓] File owner changed to: {DEST_OWNER}")
        log_to_file(f"[✓] File owner changed to: {DEST_OWNER}", LOG_FILE)
    except KeyError:
        print(f"[-] User '{DEST_OWNER}' does not exist on this system.")
        log_to_file(f"[-] User '{DEST_OWNER}' does not exist on this system.", LOG_FILE)
    except Exception as e:
        print(f"[-] Owner change error: {e}")
        log_to_file(f"[-] Owner change error: {e}", LOG_FILE)

def refresh_cache() -> bool:
    """Runs the artisan command that refreshes the app cache, on every OS."""
    if not CACHE_COMMAND:
        print("[!] JOKER_CACHE_COMMAND is not set in .env")
        log_to_file("[!] JOKER_CACHE_COMMAND is not set in .env", LOG_FILE)
        return False

    if not MAIN_DEST_PATH or not Path(MAIN_DEST_PATH).is_dir():
        print(f"[!] MAIN_DEST_PATH in .env is not a valid directory: {MAIN_DEST_PATH}")
        log_to_file(f"[!] MAIN_DEST_PATH in .env is not a valid directory: {MAIN_DEST_PATH}", LOG_FILE)
        return False

    try:
        result = subprocess.run(
            ["php", "artisan", *shlex.split(CACHE_COMMAND)],
            cwd=MAIN_DEST_PATH,
            capture_output=True,
            text=True,
            timeout=300
        )
    except FileNotFoundError:
        print("[-] The 'php' executable was not found on PATH.")
        log_to_file("[-] The 'php' executable was not found on PATH.", LOG_FILE)
        return False
    except subprocess.TimeoutExpired:
        print(f"[-] Timed out running 'php artisan {CACHE_COMMAND}'.")
        log_to_file(f"[-] Timed out running 'php artisan {CACHE_COMMAND}'.", LOG_FILE)
        return False

    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        print(f"[-] Cache refresh failed (exit code {result.returncode}): {output}")
        log_to_file(f"[-] Cache refresh failed (exit code {result.returncode}): {output}", LOG_FILE)
        return False

    print(f"[✓] Cache completed: php artisan {CACHE_COMMAND}")
    log_to_file(f"[✓] Cache completed: php artisan {CACHE_COMMAND}", LOG_FILE)
    return True

def download_and_install(year: str, url: str, output_dir: Path, headless: bool) -> Path | None:
    """Downloads the file for one year and installs it in JOKER_DEST_PATH."""
    result = download_joker_draws(
        url=url,
        year=year,
        output_dir=output_dir,
        headless=headless
    )

    if not is_valid_download(result):
        print(f"\n[!] Could not download the file for year {year}.")
        log_to_file(f"[!] Could not download the file for year {year}.", LOG_FILE)
        return None

    print(f"\n[✓] Download completed. File: {result}")
    log_to_file(f"[✓] Download completed. File: {result}", LOG_FILE)

    destination_file = copy_to_env_path(result)
    if destination_file:
        change_file_owner(destination_file)
    return destination_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the Joker results file from allwyn.gr")
    parser.add_argument("--year", help="Draw year (default: the current year, plus the previous year during the first days of January)")
    parser.add_argument("--url", default=URL, help="URL of the results page")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Directory to save the file in")
    parser.add_argument("--headless", action="store_true", default=True, help="Run the browser in headless mode")
    parser.add_argument("--no-headless", dest="headless", action="store_false", help="Run with a visible browser window")

    args = parser.parse_args()

    years = [(args.year, True)] if args.year else years_to_download(date.today())
    output_directory = Path(args.output_dir)

    failed = False
    installed_any = False
    for year, required in years:
        if download_and_install(year, args.url, output_directory, args.headless):
            installed_any = True
        elif required:
            failed = True
        else:
            print(f"[*] The {year} file is not available yet (expected early in the year).")
            log_to_file(f"[*] The {year} file is not available yet (expected early in the year).", LOG_FILE)

    if installed_any and not refresh_cache():
        failed = True

    return 1 if failed or not installed_any else 0


if __name__ == "__main__":
    sys.exit(main())
