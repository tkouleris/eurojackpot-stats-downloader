import argparse
from datetime import date, datetime
import os
import sys
import time
import urllib.request
from pathlib import Path
import shutil
import platform
import subprocess
import shlex
import io
import zipfile
from dotenv import load_dotenv

from helpers import log_to_file

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

URL = "https://www.allwyn.gr/el/eurojackpot/draws-results"
TARGET_YEAR = str(datetime.now().year)
OUTPUT_DIR = Path(__file__).parent / "downloads"
LOG_FILE = Path(__file__).parent / "log_eurojackpot.txt"
# Πόσες μέρες μετά την αλλαγή του έτους ξανακατεβαίνει και το προηγούμενο έτος.
NEW_YEAR_GRACE_DAYS = 7

load_dotenv()

DEST_PATH = os.getenv("EUROJACKPOT_DEST_PATH")
CACHE_COMMAND = os.getenv("EUROJACKPOT_CACHE_COMMAND")
MAIN_DEST_PATH = os.getenv("MAIN_DEST_PATH")
DEST_OWNER = os.getenv("OWNER")
DEST_GROUP = os.getenv("GROUP")


def is_valid_download(file_path: Path | None) -> bool:
    """Ελέγχει ότι το αρχείο υπάρχει και είναι έγκυρο xlsx (zip) αρχείο."""
    return file_path is not None and file_path.is_file() and zipfile.is_zipfile(file_path)


def target_filename(year: str) -> str:
    """Σταθερό όνομα αρχείου που περιμένει η εφαρμογή, ανεξάρτητα από την πηγή λήψης."""
    return f"Eurojackpot_{year}.xlsx"


def years_to_download(today: date) -> list[tuple[str, bool]]:
    """
    Επιστρέφει τα έτη προς λήψη ως ζεύγη (έτος, υποχρεωτικό).

    Τις πρώτες μέρες του Ιανουαρίου κατεβαίνει ξανά το προηγούμενο έτος, ώστε να
    περαστούν οι κληρώσεις των τελευταίων ημερών του Δεκεμβρίου. Το νέο έτος είναι
    τότε προαιρετικό, αφού το αρχείο του δεν υπάρχει πριν από την πρώτη κλήρωση.
    """
    current = str(today.year)
    if today.month == 1 and today.day <= NEW_YEAR_GRACE_DAYS:
        return [(str(today.year - 1), True), (current, False)]
    return [(current, True)]


def is_visible_within(locator, timeout: int) -> bool:
    """Περιμένει έως `timeout` ms να γίνει ορατό το στοιχείο (το is_visible δεν περιμένει)."""
    try:
        locator.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False


def is_option_selected(select, value: str) -> bool:
    """Ελέγχει αν η επιλεγμένη option του select έχει αυτή την τιμή ή ετικέτα."""
    return select.evaluate(
        "(s, v) => { const o = s.options[s.selectedIndex];"
        " return !!o && (o.value === v || o.label.trim() === v); }",
        value,
    )


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
    log_to_file(f"[*] Εκκίνηση διαδικασίας λήψης κληρώσεων Eurojackpot για το έτος {year}...", LOG_FILE)
    print(f"[*] Σελίδα στόχος: {url}")
    log_to_file(f"[*] Σελίδα στόχος: {url}", LOG_FILE)

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
                    log_to_file(f"[*] Επιτυχής εκκίνηση προγράμματος περιήγησης (channel: {channel or 'default chromium'}).", LOG_FILE)
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
                    log_to_file("[*] Φόρτωση της σελίδας...", LOG_FILE)
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
                    btn = page.locator(", ".join(cookie_buttons)).first
                    if is_visible_within(btn, 5000):
                        try:
                            print("[*] Αποδοχή cookies...")
                            log_to_file("[*] Αποδοχή cookies...", LOG_FILE)
                            btn.click()
                            time.sleep(1)
                        except Exception:
                            pass

                    # Εντοπισμός του dropdown επιλογής έτους στο πεδίο «Αρχείο Αποτελεσμάτων» (.download select)
                    download_select = page.locator(".download select, div.download select").first
                    if not is_visible_within(download_select, 10000):
                        # Εναλλακτικός εντοπισμός επιλογέα έτους
                        candidates = page.locator("select[aria-label='Έτος']")
                        if candidates.count() > 1:
                            download_select = candidates.nth(1)
                        elif candidates.count() == 1:
                            download_select = candidates.first

                    if download_select and download_select.count() > 0:
                        print(f"[*] Επιλογή έτους {year} στο τμήμα «Αρχείο Αποτελεσμάτων»...")
                        log_to_file(f"[*] Επιλογή έτους {year} στο τμήμα «Αρχείο Αποτελεσμάτων»...", LOG_FILE)
                        try:
                            with page.expect_download(timeout=15000) as download_info:
                                if is_option_selected(download_select, year):
                                    # Το έτος είναι ήδη επιλεγμένο, οπότε το select_option δεν
                                    # θα προκαλούσε change event· το στέλνουμε ρητά.
                                    download_select.dispatch_event("change")
                                else:
                                    download_select.select_option(year)
                            download = download_info.value
                            save_path = output_dir / target_filename(year)
                            download.save_as(save_path)
                            if is_valid_download(save_path):
                                downloaded_file_path = save_path
                                print(f"[✓] Το αρχείο κατέβηκε επιτυχώς μέσω του browser: {save_path}")
                                log_to_file(f"[✓] Το αρχείο κατέβηκε επιτυχώς μέσω του browser: {save_path}", LOG_FILE)
                            else:
                                print(f"[-] Το αρχείο του browser δεν είναι έγκυρο xlsx: {save_path}")
                                log_to_file(f"[-] Το αρχείο του browser δεν είναι έγκυρο xlsx: {save_path}", LOG_FILE)
                        except Exception as e:
                            print(f"[-] Αναμονή download event: {e}")
                            log_to_file(f"[-] Αναμονή download event: {e}", LOG_FILE)

                except Exception as e:
                    print(f"[!] Σφάλμα κατά την πλοήγηση: {e}")
                    log_to_file(f"[!] Σφάλμα κατά την πλοήγηση: {e}", LOG_FILE)
                finally:
                    browser.close()

    except Exception as e:
        print(f"[!] Σφάλμα εκκίνησης Playwright: {e}")
        log_to_file(f"[!] Σφάλμα εκκίνησης Playwright: {e}", LOG_FILE)

    # 2. Εναλλακτική άμεση λήψη από το επίσημο media repository αν δεν ολοκληρώθηκε μέσω browser
    if not is_valid_download(downloaded_file_path):
        direct_url = f"https://media.opap.gr/Excel_xlsx/5149/{target_filename(year)}"
        print(f"[*] Δοκιμή άμεσης λήψης από: {direct_url}")
        log_to_file(f"[*] Δοκιμή άμεσης λήψης από: {direct_url}", LOG_FILE)
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
                    print("[-] Η άμεση λήψη δεν επέστρεψε έγκυρο αρχείο xlsx.")
                    log_to_file("[-] Η άμεση λήψη δεν επέστρεψε έγκυρο αρχείο xlsx.", LOG_FILE)
                else:
                    save_path.write_bytes(data)
                    downloaded_file_path = save_path
                    print(f"[✓] Το αρχείο λήφθηκε επιτυχώς: {save_path} ({len(data)} bytes)")
                    log_to_file(f"[✓] Το αρχείο λήφθηκε επιτυχώς: {save_path} ({len(data)} bytes)", LOG_FILE)
        except Exception as e:
            print(f"[-] Σφάλμα άμεσης λήψης: {e}")
            log_to_file(f"[-] Σφάλμα άμεσης λήψης: {e}", LOG_FILE)

    if not is_valid_download(downloaded_file_path):
        return None

    return downloaded_file_path


def copy_to_env_path(file_path: Path) -> Path | None:
    """Αντιγράφει το κατεβασμένο αρχείο στο path που ορίζεται στο .env."""
    if not DEST_PATH:
        print("[!] Δεν έχει οριστεί το EUROJACKPOT_DEST_PATH στο .env")
        log_to_file("[!] Δεν έχει οριστεί το EUROJACKPOT_DEST_PATH στο .env", LOG_FILE)
        return None

    try:
        destination_dir = Path(DEST_PATH)
        destination_dir.mkdir(parents=True, exist_ok=True)

        destination_file = destination_dir / file_path.name
        temp_file = destination_dir / f".{file_path.name}.tmp"

        # Αντιγραφή σε προσωρινό αρχείο και ατομική αντικατάσταση, ώστε ο
        # προορισμός να μην μείνει ποτέ μισογραμμένος.
        try:
            shutil.copy2(file_path, temp_file)
            os.replace(temp_file, destination_file)
        finally:
            temp_file.unlink(missing_ok=True)

        print(f"[✓] Το αρχείο αντιγράφηκε στο: {destination_file}")
        log_to_file(f"[✓] Το αρχείο αντιγράφηκε στο: {destination_file}", LOG_FILE)

        return destination_file

    except Exception as e:
        print(f"[-] Σφάλμα αντιγραφής αρχείου: {e}")
        log_to_file(f"[-] Σφάλμα αντιγραφής αρχείου: {e}", LOG_FILE)
        return None

def change_file_owner(file_path: Path) -> None:
    """Αλλάζει τον owner του αρχείου μόνο σε Linux."""
    if platform.system() != "Linux":
        return

    if not DEST_OWNER:
        print("[!] Δεν έχει οριστεί το OWNER στο .env")
        log_to_file("[!] Δεν έχει οριστεί το OWNER στο .env", LOG_FILE)
        return

    if not DEST_GROUP:
        print("[!] Δεν έχει οριστεί το GROUP στο .env")
        log_to_file("[!] Δεν έχει οριστεί το GROUP στο .env", LOG_FILE)
        return

    try:
        import pwd
        import grp

        uid = pwd.getpwnam(DEST_OWNER).pw_uid
        gid = grp.getgrnam(DEST_GROUP).gr_gid

        os.chown(file_path, uid, gid)

        print(f"[✓] Ο owner του αρχείου άλλαξε σε: {DEST_OWNER}")
        log_to_file(f"[✓] Ο owner του αρχείου άλλαξε σε: {DEST_OWNER}", LOG_FILE)

    except KeyError:
        print(f"[-] Ο χρήστης '{DEST_OWNER}' δεν υπάρχει στο σύστημα.")
        log_to_file(f"[-] Ο χρήστης '{DEST_OWNER}' δεν υπάρχει στο σύστημα.", LOG_FILE)
    except Exception as e:
        print(f"[-] Σφάλμα αλλαγής owner: {e}")
        log_to_file(f"[-] Σφάλμα αλλαγής owner: {e}", LOG_FILE)


def refresh_cache() -> bool:
    """Εκτελεί την εντολή artisan που ανανεώνει το cache της εφαρμογής."""
    if not CACHE_COMMAND:
        print("[!] Δεν έχει οριστεί το EUROJACKPOT_CACHE_COMMAND στο .env")
        log_to_file("[!] Δεν έχει οριστεί το EUROJACKPOT_CACHE_COMMAND στο .env", LOG_FILE)
        return False

    if not MAIN_DEST_PATH or not Path(MAIN_DEST_PATH).is_dir():
        print(f"[!] Το MAIN_DEST_PATH στο .env δεν είναι έγκυρος φάκελος: {MAIN_DEST_PATH}")
        log_to_file(f"[!] Το MAIN_DEST_PATH στο .env δεν είναι έγκυρος φάκελος: {MAIN_DEST_PATH}", LOG_FILE)
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
        print("[-] Το εκτελέσιμο 'php' δεν βρέθηκε στο PATH.")
        log_to_file("[-] Το εκτελέσιμο 'php' δεν βρέθηκε στο PATH.", LOG_FILE)
        return False
    except subprocess.TimeoutExpired:
        print(f"[-] Λήξη χρόνου κατά την εκτέλεση του 'php artisan {CACHE_COMMAND}'.")
        log_to_file(f"[-] Λήξη χρόνου κατά την εκτέλεση του 'php artisan {CACHE_COMMAND}'.", LOG_FILE)
        return False

    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        print(f"[-] Αποτυχία cache (exit code {result.returncode}): {output}")
        log_to_file(f"[-] Αποτυχία cache (exit code {result.returncode}): {output}", LOG_FILE)
        return False

    print(f"[✓] Cache completed: php artisan {CACHE_COMMAND}")
    log_to_file(f"[✓] Cache completed: php artisan {CACHE_COMMAND}", LOG_FILE)
    return True

def download_and_install(year: str, url: str, output_dir: Path, headless: bool) -> Path | None:
    """Κατεβάζει το αρχείο ενός έτους και το εγκαθιστά στο EUROJACKPOT_DEST_PATH."""
    result = download_eurojackpot_draws(
        url=url,
        year=year,
        output_dir=output_dir,
        headless=headless
    )

    if not is_valid_download(result):
        print(f"\n[!] Δεν ήταν δυνατή η λήψη του αρχείου για το έτος {year}.")
        log_to_file(f"[!] Δεν ήταν δυνατή η λήψη του αρχείου για το έτος {year}.", LOG_FILE)
        return None

    print(f"\n[✓] Η λήψη ολοκληρώθηκε επιτυχώς. Αρχείο: {result}")
    log_to_file(f"[✓] Η λήψη ολοκληρώθηκε επιτυχώς. Αρχείο: {result}", LOG_FILE)

    destination_file = copy_to_env_path(result)
    if destination_file:
        change_file_owner(destination_file)
    return destination_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Λήψη αρχείου αποτελεσμάτων Eurojackpot από το allwyn.gr")
    parser.add_argument("--year", help="Το έτος των κληρώσεων (προεπιλογή: τρέχον έτος, και το προηγούμενο τις πρώτες μέρες του Ιανουαρίου)")
    parser.add_argument("--url", default=URL, help="Το URL της σελίδας αποτελεσμάτων")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Φάκελος αποθήκευσης του αρχείου")
    parser.add_argument("--headless", action="store_true", default=True, help="Εκτέλεση του browser σε headless mode")
    parser.add_argument("--no-headless", dest="headless", action="store_false", help="Εκτέλεση με ορατό παράθυρο browser")

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
            print(f"[*] Το αρχείο του {year} δεν είναι ακόμη διαθέσιμο (αναμενόμενο στις αρχές του έτους).")
            log_to_file(f"[*] Το αρχείο του {year} δεν είναι ακόμη διαθέσιμο (αναμενόμενο στις αρχές του έτους).", LOG_FILE)

    if installed_any and not refresh_cache():
        failed = True

    return 1 if failed or not installed_any else 0


if __name__ == "__main__":
    sys.exit(main())
