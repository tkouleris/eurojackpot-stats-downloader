"""Pieces shared by the download sources (browser and direct)."""
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
