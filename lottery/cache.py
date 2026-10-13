"""Step 5: refresh the app cache with php artisan."""
import logging
import shlex
import subprocess
from pathlib import Path

from .config import Settings

log = logging.getLogger(__name__)


class CacheError(Exception):
    """The cache refresh failed or is not configured."""


def refresh_cache(settings: Settings) -> None:
    """Runs `php artisan <GAME>_CACHE_COMMAND` in MAIN_DEST_PATH, on every OS."""
    command = settings.cache_command
    if not command:
        raise CacheError(f"{settings.env_prefix}_CACHE_COMMAND is not set in .env")

    cwd = settings.main_dest_path
    if not cwd or not Path(cwd).is_dir():
        raise CacheError(f"MAIN_DEST_PATH in .env is not a valid directory: {cwd}")

    try:
        arguments = shlex.split(command)
    except ValueError as e:
        raise CacheError(f"{settings.env_prefix}_CACHE_COMMAND in .env cannot be parsed: {e}") from None

    try:
        result = subprocess.run(
            ["php", "artisan", *arguments],
            cwd=cwd,
            capture_output=True,
            # artisan writes UTF-8; the locale encoding (e.g. cp1253 on Windows) can't decode all of it.
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
    except FileNotFoundError:
        raise CacheError("The 'php' executable was not found on PATH.") from None
    except subprocess.TimeoutExpired:
        raise CacheError(f"Timed out running 'php artisan {command}'.") from None
    except OSError as e:
        raise CacheError(f"Could not run 'php artisan {command}': {e}") from e

    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        raise CacheError(f"Cache refresh failed (exit code {result.returncode}): {output}")

    log.info(f"[✓] Cache completed: php artisan {command}")
