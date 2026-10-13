# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Three standalone Python scripts that download yearly draw-result spreadsheets (`.xlsx`) for Greek lottery games from allwyn.gr / OPAP, then install them into a PHP (Laravel) application that consumes them:

| Script | Game | Results page | Direct-download fallback | Env prefix | Log file |
|---|---|---|---|---|---|
| `eurojackpot.py` | Eurojackpot | `/el/eurojackpot/draws-results` | `media.opap.gr/Excel_xlsx/5149/Eurojackpot_{year}.xlsx` | `EUROJACKPOT_` | `log_eurojackpot.txt` |
| `joker.py` | Joker (Tzoker) | `/el/tzoker/draws-results` | `.../5104/Joker_{year}.xlsx` | `JOKER_` | `log_joker.txt` |
| `lotto.py` | Lotto | `/el/lotto/draws-results` | `.../5103/lotto_{year}.xlsx` | `LOTTO_` | `log_lotto.txt` |

`helpers.py` only holds `log_to_file(message, log_file)`. Comments, docstrings, prints, log messages and CLI help are written in English in `eurojackpot.py` and `joker.py`; `lotto.py` still has them in Greek. Greek text that matches the site (cookie button labels, `aria-label='Έτος'`) must stay Greek.

The README is out of date. It refers to `main.py`, which doesn't exist, and to `log.txt`. Run the individual scripts instead.

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

The default output directory and the log files are resolved relative to the script (`Path(__file__).parent / "downloads"`), not the current working directory, so the scripts behave the same when run from cron.

The code needs Python 3.10+ (it uses `Path | None`). A local virtualenv lives in `.venv` (`.venv/Scripts/python` on Windows).

`requirements.txt` lists more than the scripts use. Only `playwright` and `python-dotenv` are imported; `pandas`, `numpy`, `openpyxl`, `beautifulsoup4` and `requests` are unused.

## Testing changes

There are no tests, linter config or build step.

**Running a script has side effects on the real app.** With the local `.env`, a run copies the file into `<GAME>_DEST_PATH` and runs `php artisan` in the Laravel app. To test only the download, leave `<GAME>_DEST_PATH` empty (the run then ends with exit code 1 after downloading) or point it at a scratch folder.

Cheap checks without running anything:

```bash
python -c "import ast; ast.parse(open('joker.py', encoding='utf-8').read())"   # syntax check

# Compare two scripts after normalising game names, to spot logic that has diverged
diff <(sed 's/[Jj]oker\|JOKER\|5104\|tzoker/X/g' joker.py) \
     <(sed 's/[Ee]urojackpot\|EUROJACKPOT\|5149/X/g' eurojackpot.py)
```

## Conventions

- Commits use conventional commits with the game as scope: `fix(joker): ...`, `fix(eurojackpot): ...`, `docs: ...`. One commit per logical change and per script.
- `core.autocrlf=true`: files are checked out with CRLF line endings.
- Every `print` is paired with a `log_to_file` call carrying the same text. Message prefixes: `[*]` progress, `[✓]` success, `[-]` a step failed, `[!]` configuration problem or serious error.
- `log_to_file(message, log_file)` has no default for `log_file`. Always pass the module's `LOG_FILE`; forgetting it is an easy mistake when copying code between scripts. The resulting `TypeError` is often swallowed by a broad `except` (`lotto.py` had three such calls).

## Debugging

- **Start with the logs.** `log_<game>.txt` holds the full history of runs, one timestamped line per message. The files are append-only and never rotated.
- **The browser step depends on allwyn.gr's HTML.** If it breaks, run with `--no-headless` to watch the page. The direct-download fallback hides browser failures, so a successful run doesn't mean the browser step worked; the log says which source the file came from ("File downloaded via the browser" vs "File downloaded directly"; older log lines and `lotto.py` use the Greek "μέσω του browser" vs "λήφθηκε επιτυχώς").

## Pipeline (per script)

`main()` builds the list of years with `years_to_download(date.today())`: the current year, plus the previous year during the first `NEW_YEAR_GRACE_DAYS` (7) of January, when the previous year is required and the new year is optional (its file doesn't exist before the first draw). An explicit `--year` downloads only that year, as required. For each year, `download_and_install` runs steps 1–4:

1. **Browser download (Playwright, sync API).** Tries the Chromium channels `msedge` → `chrome` → bundled chromium. It accepts the cookie banner, then finds the year `<select>` in the "Αρχείο Αποτελεσμάτων" section (`.download select`, falling back to `select[aria-label='Έτος']`; lotto also tries `select.archive`). Selecting the year triggers the download. If the year is already selected, `select_option` would not fire a `change` event, so the script dispatches one explicitly (`is_option_selected`).
2. **Fallback.** If the browser step fails, the script fetches the file directly from `media.opap.gr` with `urllib`.
3. **Install.** Copies the file to `<GAME>_DEST_PATH` atomically (temp file, then `os.replace`).
4. **Linux only.** `chown`s the file to `OWNER:GROUP` from `.env`.
5. **Cache refresh.** After all years, if at least one file was installed, `refresh_cache` runs `php artisan <GAME>_CACHE_COMMAND` once, with `cwd=MAIN_DEST_PATH`, on every OS. The command is split with `shlex`, `MAIN_DEST_PATH` must be an existing directory, and a non-zero return code counts as failure.

Every downloaded file is checked with `is_valid_download` (`zipfile.is_zipfile`), so empty files or HTML error pages never overwrite the destination. Files are always saved as `target_filename(year)`, never as Playwright's `suggested_filename`, because the app expects a fixed name.

**Exit code:** `main()` returns 1 when a required year fails (download or install, including an empty `<GAME>_DEST_PATH`), when the cache refresh fails, or when nothing was installed. Otherwise it returns 0.

Configuration comes from `.env` (see `.env.example`), loaded via `python-dotenv` at import time into module-level constants.

## The scripts are copy-pasted, not shared

There is no shared module besides `helpers.py`. Fixes went into `eurojackpot.py` first and were then ported to `joker.py` and `lotto.py`, so the pipeline above is the same in all three. When fixing something in one script, apply the same fix to the others. Use the `diff` command from "Testing changes" to check.

Remaining differences in `lotto.py` (browser step only):

- **Fallback selector:** it also looks for `select.archive`, and its fallback picks `candidates.last` instead of `candidates.nth(1)`.
- **No `is_visible_within`:** Playwright's `locator.is_visible(timeout=...)` ignores the timeout and returns immediately. `eurojackpot.py` and `joker.py` therefore wait with `wait_for(state="visible")` (5 s for the cookie banner, 10 s for the dropdown). `lotto.py` still calls `is_visible(timeout=...)` and checks the cookie selectors one by one, so on a slow page it can miss the banner or skip to the fallback selector.
- Messages, comments and CLI help are in Greek.

## Known open issues (all three scripts)

- `change_file_owner` catches `KeyError` from both `pwd.getpwnam` and `grp.getgrnam`, but always reports that the *user* doesn't exist, even when the group is missing.
- When no year dropdown is found, the browser step falls through to the direct download without logging why.
- `browser.new_context()` / `new_page()` sit outside the `try/finally` that closes the browser (`sync_playwright` still closes it on exit).
- Waits are fixed `time.sleep` calls after page load and after the cookie click.
