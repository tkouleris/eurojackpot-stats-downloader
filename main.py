import argparse
import os
import sys
import time
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

URL = "https://www.allwyn.gr/el/eurojackpot/draws-results"
TARGET_YEAR = "2026"
OUTPUT_DIR = Path(__file__).parent / "downloads"


def download_eurojackpot_draws(
    url: str = URL,
    year: str = TARGET_YEAR,
    output_dir: Path = OUTPUT_DIR,
    headless: bool = True
) -> Path | None:
    """
    Επισκέπτεται τη σελίδα https://www.allwyn.gr/el/eurojackpot/draws-results
    και κατεβάζει το αρχείο κληρώσεων Eurojackpot για το επιλεγμένο έτος (π.χ. 2026).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] Εκκίνηση διαδικασίας λήψης κληρώσεων Eurojackpot για το έτος {year}...")
    print(f"[*] Σελίδα στόχος: {url}")

    downloaded_file_path = None

    # 1. Προσπάθεια λήψης μέσω αυτοματοποιημένης περιήγησης (Playwright)
    try:
        with sync_playwright() as p:
            browser = None
            # Επιλογή κατάλληλου browser/channel
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
                    print(f"[*] Επιτυχής εκκίνηση προγράμματος περιήγησης (channel: {channel or 'default chromium'}).")
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
                    print("[*] Φόρτωση της σελίδας...")
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    time.sleep(2)

                    # Διαχείριση cookie banner
                    cookie_buttons = [
                        "button:has-text('Αποδοχή όλων')",
                        "button:has-text('Αποδοχή')",
                        "button:has-text('Συμφωνώ')",
                        "button:has-text('Accept all')",
                        "#onetrust-accept-btn-handler"
                    ]
                    for selector in cookie_buttons:
                        try:
                            btn = page.locator(selector).first
                            if btn.is_visible(timeout=1500):
                                print("[*] Αποδοχή cookies...")
                                btn.click()
                                time.sleep(1)
                                break
                        except Exception:
                            pass

                    # Εντοπισμός του dropdown επιλογής έτους στο πεδίο «Αρχείο Αποτελεσμάτων» (.download select)
                    download_select = page.locator(".download select, div.download select").first
                    if not download_select.is_visible(timeout=2000):
                        # Εναλλακτικός εντοπισμός επιλογέα έτους
                        candidates = page.locator("select[aria-label='Έτος']")
                        if candidates.count() > 1:
                            download_select = candidates.nth(1)
                        elif candidates.count() == 1:
                            download_select = candidates.first

                    if download_select and download_select.count() > 0:
                        print(f"[*] Επιλογή έτους {year} στο τμήμα «Αρχείο Αποτελεσμάτων»...")
                        try:
                            with page.expect_download(timeout=15000) as download_info:
                                download_select.select_option(year)
                            download = download_info.value
                            suggested_filename = download.suggested_filename or f"Eurojackpot_{year}.xlsx"
                            save_path = output_dir / suggested_filename
                            download.save_as(save_path)
                            downloaded_file_path = save_path
                            print(f"[✓] Το αρχείο κατέβηκε επιτυχώς μέσω του browser: {save_path}")
                        except Exception as e:
                            print(f"[-] Αναμονή download event: {e}")

                except Exception as e:
                    print(f"[!] Σφάλμα κατά την πλοήγηση: {e}")
                finally:
                    browser.close()

    except Exception as e:
        print(f"[!] Σφάλμα εκκίνησης Playwright: {e}")

    # 2. Εναλλακτική άμεση λήψη από το επίσημο media repository αν δεν ολοκληρώθηκε μέσω browser
    if not downloaded_file_path or not downloaded_file_path.exists() or downloaded_file_path.stat().st_size == 0:
        direct_url = f"https://media.opap.gr/Excel_xlsx/5149/Eurojackpot_{year}.xlsx"
        print(f"[*] Δοκιμή άμεσης λήψης από: {direct_url}")
        try:
            req = urllib.request.Request(
                direct_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
            )
            save_path = output_dir / f"Eurojackpot_{year}.xlsx"
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    data = resp.read()
                    save_path.write_bytes(data)
                    downloaded_file_path = save_path
                    print(f"[✓] Το αρχείο λήφθηκε επιτυχώς: {save_path} ({len(data)} bytes)")
        except Exception as e:
            print(f"[-] Σφάλμα άμεσης λήψης: {e}")

    return downloaded_file_path


def main():
    parser = argparse.ArgumentParser(description="Λήψη αρχείου αποτελεσμάτων Eurojackpot από το allwyn.gr")
    parser.add_argument("--year", default=TARGET_YEAR, help="Το έτος των κληρώσεων (προεπιλογή: 2026)")
    parser.add_argument("--url", default=URL, help="Το URL της σελίδας αποτελεσμάτων")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Φάκελος αποθήκευσης του αρχείου")
    parser.add_argument("--headless", action="store_true", default=True, help="Εκτέλεση του browser σε headless mode")
    parser.add_argument("--no-headless", dest="headless", action="store_false", help="Εκτέλεση με ορατό παράθυρο browser")

    args = parser.parse_args()

    output_directory = Path(args.output_dir)
    result = download_eurojackpot_draws(
        url=args.url,
        year=args.year,
        output_dir=output_directory,
        headless=args.headless
    )

    if result and os.path.exists(result):
        print(f"\n[✓] Η διαδικασία ολοκληρώθηκε επιτυχώς. Αρχείο: {result}")
    else:
        print("\n[!] Δεν ήταν δυνατή η λήψη του αρχείου.")


if __name__ == "__main__":
    main()
