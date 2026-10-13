"""Step 2 (fallback): download the file directly from the official media repository."""
import io
import logging
import urllib.request
import zipfile
from http.client import HTTPException
from pathlib import Path

from .config import GameConfig
from .download import USER_AGENT, DownloadError

log = logging.getLogger(__name__)


def download_direct(game: GameConfig, year: str, output_dir: Path) -> Path:
    url = game.direct_url(year)
    log.info(f"[*] Trying direct download from: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read()
    except (OSError, HTTPException) as e:
        raise DownloadError(f"Direct download error: {e}") from e

    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise DownloadError("Direct download did not return a valid xlsx file.")

    save_path = output_dir / game.filename(year)
    try:
        save_path.write_bytes(data)
    except OSError as e:
        raise DownloadError(f"Could not save the direct download: {e}") from e
    log.info(f"[✓] File downloaded directly: {save_path} ({len(data)} bytes)")
    return save_path
