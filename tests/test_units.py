import argparse
import tempfile
import unittest
from datetime import date
from pathlib import Path

from lottery.cache import CacheError, refresh_cache
from lottery.config import EUROJACKPOT, LOTTO, Settings
from lottery.download import DownloadError, keep_if_valid
from lottery.install import InstallError, install_file
from lottery.pipeline import year_argument, years_to_download
from tests.helpers import enter, write_xlsx


def settings(**overrides) -> Settings:
    values = dict(env_prefix="LOTTO", dest_path=None, cache_command=None, main_dest_path=None, owner=None, group=None)
    values.update(overrides)
    return Settings(**values)


class YearsToDownloadTest(unittest.TestCase):
    def test_current_year_only_after_the_grace_days(self):
        self.assertEqual(years_to_download(date(2026, 1, 8)), [("2026", True)])
        self.assertEqual(years_to_download(date(2026, 10, 13)), [("2026", True)])

    def test_previous_year_required_and_new_year_optional_in_early_january(self):
        self.assertEqual(years_to_download(date(2026, 1, 1)), [("2025", True), ("2026", False)])
        self.assertEqual(years_to_download(date(2026, 1, 7)), [("2025", True), ("2026", False)])


class YearArgumentTest(unittest.TestCase):
    def test_accepts_four_digit_years(self):
        self.assertEqual(year_argument("2026"), "2026")

    def test_rejects_anything_else(self):
        for value in ("26", "20266", "../x", "2026 ", "abcd"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                year_argument(value)


class GameConfigTest(unittest.TestCase):
    def test_filename_and_direct_url(self):
        self.assertEqual(LOTTO.filename("2026"), "lotto_2026.xlsx")
        self.assertEqual(
            EUROJACKPOT.direct_url("2025"),
            "https://media.opap.gr/Excel_xlsx/5149/Eurojackpot_2025.xlsx",
        )


class KeepIfValidTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(enter(self, tempfile.TemporaryDirectory()))
        self.save_path = self.dir / "lotto_2026.xlsx"
        self.temp_path = self.dir / ".lotto_2026.xlsx.part"

    def test_moves_a_valid_file_into_place(self):
        write_xlsx(self.temp_path)
        keep_if_valid(self.temp_path, self.save_path)
        self.assertTrue(self.save_path.is_file())
        self.assertFalse(self.temp_path.exists())

    def test_invalid_file_is_deleted_and_the_previous_one_kept(self):
        write_xlsx(self.save_path)
        previous = self.save_path.read_bytes()
        self.temp_path.write_text("<html>error</html>")
        with self.assertRaises(DownloadError):
            keep_if_valid(self.temp_path, self.save_path)
        self.assertEqual(self.save_path.read_bytes(), previous)
        self.assertFalse(self.temp_path.exists())


class InstallFileTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(enter(self, tempfile.TemporaryDirectory()))
        self.source = write_xlsx(self.dir / "lotto_2026.xlsx")

    def test_copies_the_file_without_leaving_a_temp_file(self):
        dest = self.dir / "dest"
        dest.mkdir()
        installed = install_file(self.source, settings(dest_path=str(dest)))
        self.assertEqual(installed, dest / "lotto_2026.xlsx")
        self.assertEqual(installed.read_bytes(), self.source.read_bytes())
        self.assertEqual([p.name for p in dest.iterdir()], ["lotto_2026.xlsx"])

    def test_unset_dest_path(self):
        with self.assertRaisesRegex(InstallError, "LOTTO_DEST_PATH is not set"):
            install_file(self.source, settings())

    def test_missing_dest_directory_is_not_created(self):
        dest = self.dir / "typo"
        with self.assertRaisesRegex(InstallError, "not an existing directory"):
            install_file(self.source, settings(dest_path=str(dest)))
        self.assertFalse(dest.exists())


class RefreshCacheTest(unittest.TestCase):
    def test_unset_command(self):
        with self.assertRaisesRegex(CacheError, "LOTTO_CACHE_COMMAND is not set"):
            refresh_cache(settings())

    def test_main_dest_path_must_exist(self):
        with self.assertRaisesRegex(CacheError, "MAIN_DEST_PATH"):
            refresh_cache(settings(cache_command="cache:lotto", main_dest_path="/does/not/exist"))

    def test_unparsable_command(self):
        with tempfile.TemporaryDirectory() as cwd:
            with self.assertRaisesRegex(CacheError, "cannot be parsed"):
                refresh_cache(settings(cache_command="cache:lotto 'unclosed", main_dest_path=cwd))


if __name__ == "__main__":
    unittest.main()
