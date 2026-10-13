"""Downloads a game's yearly results file and installs it in the Laravel app."""
import argparse
import logging
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import date
from functools import partial
from pathlib import Path

from dotenv import load_dotenv

from .browser import download_via_browser
from .cache import CacheError, refresh_cache
from .config import OUTPUT_DIR, PROJECT_DIR, GameConfig, Settings
from .direct import download_direct
from .download import DownloadError
from .install import InstallError, change_owner, install_file
from .log import logging_to

log = logging.getLogger(__name__)

# How many days into the new year the previous year is downloaded again.
NEW_YEAR_GRACE_DAYS = 7

# Saves the file of (game, year) in output_dir and returns its path, or raises DownloadError.
Source = Callable[[GameConfig, str, Path], Path]


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


def year_argument(value: str) -> str:
    """argparse type for --year: a four-digit year, which also keeps it safe in paths and URLs."""
    if len(value) != 4 or not value.isdigit():
        raise argparse.ArgumentTypeError(f"expected a four-digit year such as 2026, got {value!r}")
    return value


def parse_args(game: GameConfig, argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Download the {game.name} results file from allwyn.gr")
    parser.add_argument("--year", type=year_argument, help="Draw year (default: the current year, plus the previous year during the first days of January)")
    parser.add_argument("--url", default=game.page_url, help="URL of the results page")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR, help="Directory to save the file in")
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run the browser in headless mode (default); --no-headless shows the browser window",
    )
    return parser.parse_args(argv)


def download(game: GameConfig, year: str, output_dir: Path, sources: Sequence[Source]) -> Path:
    """Tries the sources in order and returns the first valid file."""
    log.info(f"[*] Starting download of {game.name} draws for year {year}...")
    log.info(f"[*] Target page: {game.page_url}")
    output_dir.mkdir(parents=True, exist_ok=True)
    for source in sources:
        try:
            return source(game, year, output_dir)
        except DownloadError as e:
            log.info(f"[-] {e}")
    raise DownloadError(f"Could not download the file for year {year}.")


def download_and_install(
    game: GameConfig, year: str, settings: Settings, output_dir: Path, sources: Sequence[Source]
) -> Path:
    """Downloads the file of one year and installs it in <GAME>_DEST_PATH."""
    downloaded = download(game, year, output_dir, sources)
    log.info(f"[✓] Download completed. File: {downloaded}")
    return install_file(downloaded, settings)


def run(
    game: GameConfig,
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    sources: Sequence[Source] | None = None,
    today: date | None = None,
) -> int:
    """
    Entry point of the game scripts. Returns the exit code: 1 when a required year
    fails, when the cache refresh fails or when nothing was installed, else 0.
    """
    args = parse_args(game, argv)
    game = replace(game, page_url=args.url)
    if sources is None:
        sources = [partial(download_via_browser, headless=args.headless), download_direct]

    with logging_to(game.log_file):
        if settings is None:
            load_dotenv(PROJECT_DIR / ".env")
            settings = Settings.from_env(game.env_prefix)

        years = [(args.year, True)] if args.year else years_to_download(today or date.today())
        failed = False
        installed_any = False
        for year, required in years:
            try:
                installed = download_and_install(game, year, settings, args.output_dir, sources)
            except DownloadError as e:
                if required:
                    log.error(f"[!] {e}")
                    failed = True
                else:
                    log.info(f"[*] The {year} file is not available yet (expected early in the year).")
                continue
            except InstallError as e:
                log.error(f"[!] {e}")
                failed = True
                continue

            # The file is in place even if the owner change fails, so the cache is still refreshed.
            installed_any = True
            try:
                change_owner(installed, settings)
            except InstallError as e:
                log.error(f"[!] {e}")
                failed = True

        if installed_any:
            try:
                refresh_cache(settings)
            except CacheError as e:
                log.error(f"[!] {e}")
                failed = True

    return 1 if failed or not installed_any else 0
