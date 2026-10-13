"""Pieces shared by the download sources (browser and direct)."""
import os
import zipfile
from pathlib import Path

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class DownloadError(Exception):
    """A download source could not produce a valid file."""


def is_valid_xlsx(file_path: Path) -> bool:
    """Checks that the file exists and is a valid xlsx (zip) file."""
    return file_path.is_file() and zipfile.is_zipfile(file_path)


def partial_path(save_path: Path) -> Path:
    """Where a download is written before it is checked."""
    return save_path.with_name(f".{save_path.name}.part")


def keep_if_valid(temp_path: Path, save_path: Path) -> None:
    """
    Moves a finished download to save_path if it is a valid xlsx, else deletes it.
    An empty file or an HTML error page never replaces an earlier good download.
    """
    try:
        if not is_valid_xlsx(temp_path):
            raise DownloadError(f"Downloaded file is not a valid xlsx: {save_path.name}")
        os.replace(temp_path, save_path)
    except OSError as e:
        raise DownloadError(f"Could not save {save_path}: {e}") from e
    finally:
        temp_path.unlink(missing_ok=True)
