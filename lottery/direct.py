"""Step 2 (fallback): download the file directly from the official media repository."""
import logging
import urllib.request
from http.client import HTTPException
from pathlib import Path

from .config import GameConfig
from .download import USER_AGENT, DownloadError, keep_if_valid, partial_path

log = logging.getLogger(__name__)


def download_direct(game: GameConfig, year: str, output_dir: Path) -> Path:
    url = game.direct_url(year)
    log.info(f"[*] Trying direct download from: {url}")
    save_path = output_dir / game.filename(year)
    temp_path = partial_path(save_path)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            temp_path.write_bytes(response.read())
    except (OSError, HTTPException) as e:
        temp_path.unlink(missing_ok=True)
        raise DownloadError(f"Direct download error: {e}") from e

    keep_if_valid(temp_path, save_path)
    log.info(f"[✓] File downloaded directly: {save_path} ({save_path.stat().st_size} bytes)")
    return save_path
