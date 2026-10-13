"""Per-game configuration and the installation settings from .env."""
import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
# Resolved relative to the project, not the working directory, so cron runs behave the same.
OUTPUT_DIR = PROJECT_DIR / "downloads"


@dataclass(frozen=True)
class GameConfig:
    """Everything that differs between the games; the pipeline is the same for all of them."""

    name: str
    env_prefix: str
    page_url: str
    media_id: int
    filename_template: str
    log_file: Path
    # Selectors for the year dropdown of the results archive, in order of preference.
    dropdown_selectors: tuple[str, ...] = (".download select",)
    # Used when none of dropdown_selectors is visible. With several matches,
    # the one at fallback_index is picked.
    fallback_selector: str = "select[aria-label='Έτος']"
    fallback_index: int = 1

    def filename(self, year: str) -> str:
        """Fixed filename the app expects, regardless of the download source."""
        return self.filename_template.format(year=year)

    def direct_url(self, year: str) -> str:
        """URL of the file in the official media repository."""
        return f"https://media.opap.gr/Excel_xlsx/{self.media_id}/{self.filename(year)}"


@dataclass(frozen=True)
class Settings:
    """Installation settings of one game, read from the environment (.env)."""

    env_prefix: str
    dest_path: str | None
    cache_command: str | None
    main_dest_path: str | None
    owner: str | None
    group: str | None

    @classmethod
    def from_env(cls, env_prefix: str) -> "Settings":
        return cls(
            env_prefix=env_prefix,
            dest_path=os.getenv(f"{env_prefix}_DEST_PATH") or None,
            cache_command=os.getenv(f"{env_prefix}_CACHE_COMMAND") or None,
            main_dest_path=os.getenv("MAIN_DEST_PATH") or None,
            owner=os.getenv("OWNER") or None,
            group=os.getenv("GROUP") or None,
        )


EUROJACKPOT = GameConfig(
    name="Eurojackpot",
    env_prefix="EUROJACKPOT",
    page_url="https://www.allwyn.gr/el/eurojackpot/draws-results",
    media_id=5149,
    filename_template="Eurojackpot_{year}.xlsx",
    log_file=PROJECT_DIR / "log_eurojackpot.txt",
)

JOKER = GameConfig(
    name="Joker",
    env_prefix="JOKER",
    page_url="https://www.allwyn.gr/el/tzoker/draws-results",
    media_id=5104,
    filename_template="Joker_{year}.xlsx",
    log_file=PROJECT_DIR / "log_joker.txt",
)
