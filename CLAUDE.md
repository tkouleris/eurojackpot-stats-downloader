# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Three Python entry scripts that download yearly draw-result spreadsheets (`.xlsx`) for Greek lottery games from allwyn.gr / OPAP, then install them into a PHP (Laravel) application that consumes them:

| Script | Game | Results page | Direct-download fallback | Env prefix | Log file |
|---|---|---|---|---|---|
| `eurojackpot.py` | Eurojackpot | `/el/eurojackpot/draws-results` | `media.opap.gr/Excel_xlsx/5149/Eurojackpot_{year}.xlsx` | `EUROJACKPOT_` | `log_eurojackpot.txt` |
| `joker.py` | Joker (Tzoker) | `/el/tzoker/draws-results` | `.../5104/Joker_{year}.xlsx` | `JOKER_` | `log_joker.txt` |
| `lotto.py` | Lotto | `/el/lotto/draws-results` | `.../5103/lotto_{year}.xlsx` | `LOTTO_` | `log_lotto.txt` |

The entry scripts are five-line wrappers: `raise SystemExit(run(LOTTO))`. All logic lives in the `lottery/` package, and everything that differs between the games is a `GameConfig` in `lottery/config.py` (URL, media id, filename template, env prefix, log file, dropdown selectors). Adding a game means adding a `GameConfig` and a wrapper script.

Comments, docstrings, log messages and CLI help are written in English. Greek text that matches the site (cookie button labels, `aria-label='Έτος'`) must stay Greek.

## Commands

```bash
pip install -r requirements.txt      # note: requirements.txt is UTF-16 encoded
playwright install chromium          # only if no Edge/Chrome is installed

python eurojackpot.py                # current year (plus previous year during Jan 1–7)
python eurojackpot.py --year 2025 --no-headless
python joker.py --year 2026 --output-dir ./custom_folder
python lotto.py
```

Shared CLI flags: `--year`, `--url`, `--output-dir`, `--headless` / `--no-headless`.

The default output directory, the log files and `.env` are resolved relative to the project (`PROJECT_DIR` in `lottery/config.py`), not the current working directory, so the scripts behave the same when run from cron. `--year` accepts only four-digit years.

The code needs Python 3.10+ (it uses `Path | None`; the tests avoid the 3.11-only `enterContext`). A local virtualenv lives in `.venv` (`.venv/Scripts/python` on Windows).

`requirements.txt` lists more than the scripts use. Only `playwright` and `python-dotenv` are imported; `pandas`, `numpy`, `openpyxl`, `beautifulsoup4` and `requests` are unused.

## Testing changes

```bash
python -m unittest        # no network, never touches the app
```

The tests replace the download sources, `refresh_cache` and `change_owner` with fakes (`run()` takes `settings`, `sources` and `today` as keyword arguments for this). There is no linter config or build step.

**Running a script has side effects on the real app.** With the local `.env`, a run copies the file into `<GAME>_DEST_PATH` and runs `php artisan` in the Laravel app. To test only the download against the live site, call the sources directly; they write only to the given folder:

```bash
python -c "from pathlib import Path; from lottery.config import LOTTO; from lottery.browser import download_via_browser as d; print(d(LOTTO, '2026', Path('scratch')))"
```

## Conventions

- Commits use conventional commits: `fix: ...` for the shared package, with the game as scope only when one game changes (`fix(lotto): ...`), `docs: ...`, `test: ...`. One commit per logical change.
- `core.autocrlf=true`: files are checked out with CRLF line endings.
- Logging uses stdlib `logging` via `logging.getLogger(__name__)`; `logging_to(log_file)` in `lottery/log.py` sends the `lottery` logger to stdout and, timestamped, to the game's log file. Don't `print`. Message prefixes: `[*]` progress, `[✓]` success, `[-]` a step failed, `[!]` configuration problem or serious error.
- Errors: each step raises its own exception (`DownloadError`, `InstallError`, `CacheError`) with a message meant for the log; only `run()` in `lottery/pipeline.py` logs them and decides the exit code. Catch specific exceptions (`PlaywrightError`, `OSError`), not `Exception`.

## Debugging

- **Start with the logs.** `log_<game>.txt` holds the full history of runs, one timestamped line per message. The files are append-only and never rotated.
- **The browser step depends on allwyn.gr's HTML.** If it breaks, run with `--no-headless` to watch the page. The direct-download fallback hides browser failures, so a successful run doesn't mean the browser step worked; the log says which source the file came from ("File downloaded via the browser" vs "File downloaded directly"; older log lines use the Greek "μέσω του browser" vs "λήφθηκε επιτυχώς").

## Pipeline (`lottery/pipeline.py`)

`run(game)` builds the list of years with `years_to_download(date.today())`: the current year, plus the previous year during the first `NEW_YEAR_GRACE_DAYS` (7) of January, when the previous year is required and the new year is optional (its file doesn't exist before the first draw). An explicit `--year` downloads only that year, as required. For each year, `download` tries the sources in order (logging why each one failed), then `install_file` and `change_owner` run:

1. **Browser download (`lottery/browser.py`, Playwright sync API).** Tries the Chromium channels `msedge` → `chrome` → bundled chromium. It waits up to 5 s for the cookie banner, then up to 10 s for the year `<select>` in the "Αρχείο Αποτελεσμάτων" section: `GameConfig.dropdown_selectors` in order of preference, then `fallback_selector` with `fallback_index` (Lotto also tries `select.archive` and picks the last match). Playwright's `is_visible(timeout=...)` ignores the timeout, so waits use `wait_for` (`is_visible_within`). Selecting the year triggers the download. If the year is already selected, `select_option` would not fire a `change` event, so the script dispatches one explicitly (`is_option_selected`).
2. **Fallback (`lottery/direct.py`).** If the browser step fails, the file is fetched directly from `media.opap.gr` with `urllib`.
3. **Install (`lottery/install.py`).** Copies the file to `<GAME>_DEST_PATH`, which must be an existing directory, atomically (temp file, then `os.replace`).
4. **Linux only.** `chown`s the file to `OWNER:GROUP` from `.env`. A failure (including unset `OWNER`/`GROUP`) makes the exit code 1, but the file stays installed and the cache is still refreshed.
5. **Cache refresh (`lottery/cache.py`).** After all years, if at least one file was installed, `refresh_cache` runs `php artisan <GAME>_CACHE_COMMAND` once, with `cwd=MAIN_DEST_PATH`, on every OS. The command is split with `shlex`, `MAIN_DEST_PATH` must be an existing directory, the output is decoded as UTF-8, and a non-zero return code counts as failure.

Both sources write to a `.part` file that `keep_if_valid` moves into place only if it is a valid xlsx (`zipfile.is_zipfile`), so empty files or HTML error pages never overwrite an earlier download or the destination. Files are always saved as `GameConfig.filename(year)`, never as Playwright's `suggested_filename`, because the app expects a fixed name.

**Exit code:** `run()` returns 1 when a required year fails to download, when any install or owner change fails (including an empty `<GAME>_DEST_PATH`), when the cache refresh fails, or when nothing was installed. Otherwise it returns 0.

Configuration comes from `.env` (see `.env.example`), loaded via `python-dotenv` inside `run()` into a `Settings` object (`Settings.from_env(prefix)`), not at import time.

