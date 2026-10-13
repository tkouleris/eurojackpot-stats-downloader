import contextlib
import io
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest import mock

from lottery.cache import CacheError
from lottery.config import LOTTO, Settings
from lottery.download import DownloadError
from lottery.install import InstallError
from lottery.pipeline import run
from tests.helpers import enter, write_xlsx

EARLY_JANUARY = date(2026, 1, 3)  # 2025 required, 2026 optional
OCTOBER = date(2026, 10, 13)  # 2026 required


def working_source(game, year, output_dir):
    return write_xlsx(output_dir / game.filename(year))


def failing_source(game, year, output_dir):
    raise DownloadError("no file")


def source_for(*available_years):
    def source(game, year, output_dir):
        if year not in available_years:
            raise DownloadError(f"no file for {year}")
        return working_source(game, year, output_dir)

    return source


class RunTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(enter(self, tempfile.TemporaryDirectory()))
        self.dest = self.dir / "dest"
        self.dest.mkdir()
        self.game = replace(LOTTO, log_file=self.dir / "log.txt")
        self.settings = Settings("LOTTO", str(self.dest), "cache:lotto", str(self.dir), None, None)
        self.refresh_cache = enter(self, mock.patch("lottery.pipeline.refresh_cache"))
        self.change_owner = enter(self, mock.patch("lottery.pipeline.change_owner"))

    def run_pipeline(self, sources, today=OCTOBER, argv=(), settings=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return run(
                self.game,
                ["--output-dir", str(self.dir / "downloads"), *argv],
                settings=settings or self.settings,
                sources=sources,
                today=today,
            )

    def installed(self):
        return sorted(p.name for p in self.dest.iterdir())

    def test_success(self):
        self.assertEqual(self.run_pipeline([working_source]), 0)
        self.assertEqual(self.installed(), ["lotto_2026.xlsx"])
        self.refresh_cache.assert_called_once_with(self.settings)

    def test_falls_back_to_the_next_source_and_logs_why(self):
        self.assertEqual(self.run_pipeline([failing_source, working_source]), 0)
        self.assertIn("[-] no file", self.game.log_file.read_text(encoding="utf-8"))

    def test_required_year_fails(self):
        self.assertEqual(self.run_pipeline([failing_source]), 1)
        self.refresh_cache.assert_not_called()

    def test_optional_new_year_may_be_missing_in_early_january(self):
        self.assertEqual(self.run_pipeline([source_for("2025")], today=EARLY_JANUARY), 0)
        self.assertEqual(self.installed(), ["lotto_2025.xlsx"])
        self.assertIn("The 2026 file is not available yet", self.game.log_file.read_text(encoding="utf-8"))

    def test_required_previous_year_fails_in_early_january(self):
        self.assertEqual(self.run_pipeline([source_for("2026")], today=EARLY_JANUARY), 1)
        self.refresh_cache.assert_called_once()  # 2026 was installed

    def test_explicit_year_is_required(self):
        self.assertEqual(self.run_pipeline([source_for("2026")], argv=["--year", "2024"]), 1)

    def test_install_failure(self):
        settings = replace(self.settings, dest_path=None)
        self.assertEqual(self.run_pipeline([working_source], settings=settings), 1)
        self.refresh_cache.assert_not_called()

    def test_owner_change_failure_fails_the_run_but_still_refreshes_the_cache(self):
        self.change_owner.side_effect = InstallError("OWNER is not set in .env")
        self.assertEqual(self.run_pipeline([working_source]), 1)
        self.assertEqual(self.installed(), ["lotto_2026.xlsx"])
        self.refresh_cache.assert_called_once()

    def test_cache_failure(self):
        self.refresh_cache.side_effect = CacheError("php not found")
        self.assertEqual(self.run_pipeline([working_source]), 1)

    def test_url_option_reaches_the_sources(self):
        seen = []

        def source(game, year, output_dir):
            seen.append(game.page_url)
            return working_source(game, year, output_dir)

        self.run_pipeline([source], argv=["--url", "https://example.test/results"])
        self.assertEqual(seen, ["https://example.test/results"])


if __name__ == "__main__":
    unittest.main()
