"""Steps 3 and 4: install the file in <GAME>_DEST_PATH and hand it to OWNER:GROUP."""
import logging
import os
import platform
import shutil
from pathlib import Path

from .config import Settings

log = logging.getLogger(__name__)


class InstallError(Exception):
    """The file could not be installed in the app."""


def install_file(file_path: Path, settings: Settings) -> Path:
    """Copies the file to <GAME>_DEST_PATH and returns the installed path."""
    if not settings.dest_path:
        raise InstallError(f"{settings.env_prefix}_DEST_PATH is not set in .env")

    destination_dir = Path(settings.dest_path)
    destination_file = destination_dir / file_path.name
    temp_file = destination_dir / f".{file_path.name}.tmp"
    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
        # Copy to a temp file and replace atomically, so the
        # destination is never left half-written.
        try:
            shutil.copy2(file_path, temp_file)
            os.replace(temp_file, destination_file)
        finally:
            temp_file.unlink(missing_ok=True)
    except OSError as e:
        raise InstallError(f"File copy error: {e}") from e

    log.info(f"[✓] File copied to: {destination_file}")
    return destination_file


def change_owner(file_path: Path, settings: Settings) -> None:
    """Changes the file owner to OWNER:GROUP, on Linux only."""
    if platform.system() != "Linux":
        return

    if not settings.owner:
        raise InstallError("OWNER is not set in .env")
    if not settings.group:
        raise InstallError("GROUP is not set in .env")

    import grp
    import pwd

    try:
        uid = pwd.getpwnam(settings.owner).pw_uid
    except KeyError:
        raise InstallError(f"User '{settings.owner}' does not exist on this system.") from None
    try:
        gid = grp.getgrnam(settings.group).gr_gid
    except KeyError:
        raise InstallError(f"Group '{settings.group}' does not exist on this system.") from None
    try:
        os.chown(file_path, uid, gid)
    except OSError as e:
        raise InstallError(f"Owner change error: {e}") from e
    log.info(f"[✓] File owner changed to: {settings.owner}:{settings.group}")
