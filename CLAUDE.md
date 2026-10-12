# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Three standalone Python scripts that download yearly draw-result spreadsheets (`.xlsx`) for Greek lottery games from allwyn.gr / OPAP, then install them into a PHP (Laravel) application that consumes them:

| Script | Game | Results page | Direct-download fallback | Env prefix | Log file |
|---|---|---|---|---|---|
| `eurojackpot.py` | Eurojackpot | `/el/eurojackpot/draws-results` | `media.opap.gr/Excel_xlsx/5149/Eurojackpot_{year}.xlsx` | `EUROJACKPOT_` | `log_eurojackpot.txt` |
| `joker.py` | Joker (Tzoker) | `/el/tzoker/draws-results` | `.../5104/Joker_{year}.xlsx` | `JOKER_` | `log_joker.txt` |
| `lotto.py` | Lotto | `/el/lotto/draws-results` | `.../5103/Lotto_{year}.xlsx` | `LOTTO_` | `log_lotto.txt` |

`helpers.py` only holds `log_to_file(message, log_file)`. User-facing messages, comments and docstrings are written in Greek. Keep that convention.

The README is out of date. It refers to `main.py`, which doesn't exist, and to `log.txt`. Run the individual scripts instead.

## Commands

```bash
pip install -r requirements.txt      # note: requirements.txt is UTF-16 encoded
playwright install chromium          # only if no Edge/Chrome is installed

python eurojackpot.py                # current year (plus previous year during Jan 1–7)
python eurojackpot.py --year 2025 --no-headless
python joker.py --year 2026 --output-dir ./custom_folder
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
- `log_to_file(message, log_file)` has no default for `log_file`. Always pass the module's `LOG_FILE`; forgetting it is an easy mistake when copying code between scripts (see the `lotto.py` bugs below).

## Debugging

- **Start with the logs.** `log_<game>.txt` holds the full history of runs, one timestamped line per message. The files are append-only and never rotated.
- **The browser step depends on allwyn.gr's HTML.** If it breaks, run with `--no-headless` to watch the page. The direct-download fallback hides browser failures, so a successful run doesn't mean the browser step worked; the log says which source the file came from ("μέσω του browser" vs "λήφθηκε επιτυχώς").

## Pipeline (per script)

1. **Browser download (Playwright, sync API).** Tries the Chromium channels `msedge` → `chrome` → bundled chromium. It accepts the cookie banner, then finds the year `<select>` in the "Αρχείο Αποτελεσμάτων" section (`.download select`, falling back to `select[aria-label='Έτος']`; lotto also tries `select.archive`). Selecting the year triggers the download.
2. **Fallback.** If the browser step fails, the script fetches the file directly from `media.opap.gr` with `urllib`.
3. **Install.** Copies the file to `<GAME>_DEST_PATH`.
4. **Linux only.** `chown`s the file to `OWNER:GROUP` from `.env`.
5. **Cache refresh.** Runs `php artisan <GAME>_CACHE_COMMAND` with `cwd=MAIN_DEST_PATH`.

Configuration comes from `.env` (see `.env.example`), loaded via `python-dotenv` at import time into module-level constants.

## The scripts have diverged: `eurojackpot.py` and `joker.py` are hardened, `lotto.py` is not

The scripts are copy-pasted rather than sharing code. Recent fixes went into `eurojackpot.py` and were then ported to `joker.py`, so the two now have the same logic. `lotto.py` still has the older behaviour. When fixing something in one script, check whether the same fix applies to the others. Things `eurojackpot.py` and `joker.py` do but `lotto.py` doesn't:

- **Validates downloads as xlsx** with `zipfile.is_zipfile`, for both the browser and the direct download. This stops empty files or HTML error pages from overwriting the destination.
- **Uses a fixed output filename** (`target_filename(year)`) instead of Playwright's `suggested_filename`.
- **Copies atomically:** writes to a temp file, then `os.replace`.
- **Handles an already-selected year:** if the target year is already selected in the dropdown, it dispatches a `change` event explicitly, because `select_option` would not fire one.
- **Rolls over the year:** `years_to_download` also re-fetches the previous year during the first `NEW_YEAR_GRACE_DAYS` of January. The new year is optional during that window, because its file doesn't exist before the first draw.
- **Refreshes the cache separately** (`refresh_cache`) instead of inside `change_file_owner`. As a result it runs on every OS, splits the command with `shlex`, validates `MAIN_DEST_PATH` and checks the return code. In `lotto.py`, the artisan call sits inside the Linux-only chown function, so it is skipped on other platforms.
- **Returns a non-zero exit code** from `main()` when a required year fails or the cache refresh fails. `lotto.py` always exits 0.

Other differences in `lotto.py`:

- It also looks for `select.archive`, and its fallback picks `candidates.last` instead of `candidates.nth(1)`.
- **Known bugs:** two `log_to_file` calls omit the `LOG_FILE` argument, so they raise `TypeError`:
  - `lotto.py:104` (cookie banner): the error is swallowed by `except Exception: pass`, so `btn.click()` never runs and the cookie banner is never accepted.
  - `lotto.py:170` (direct-download `except`): the error is raised inside the `except` itself, so any direct-download failure crashes the script.
