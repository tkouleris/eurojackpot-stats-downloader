# Eurojackpot Stats Downloader

Downloads the yearly draw-result spreadsheets (`.xlsx`) of the Greek lottery games Eurojackpot, Joker and Lotto from Allwyn / OPAP, and installs them in a Laravel application that uses them.

| Script | Game | Results page | File |
|---|---|---|---|
| `eurojackpot.py` | Eurojackpot | `allwyn.gr/el/eurojackpot/draws-results` | `Eurojackpot_{year}.xlsx` |
| `joker.py` | Joker (Tzoker) | `allwyn.gr/el/tzoker/draws-results` | `Joker_{year}.xlsx` |
| `lotto.py` | Lotto | `allwyn.gr/el/lotto/draws-results` | `lotto_{year}.xlsx` |

## How it works

For each year, a script:

1. **Downloads the file with a browser.** It uses Playwright to open the results page, accept the cookie banner and select the year in the results archive, which starts the download. It tries Microsoft Edge, then Google Chrome, then Playwright's bundled Chromium.
2. **Falls back to a direct download** from the OPAP media repository (`media.opap.gr`) if the browser step fails.
3. **Installs the file** in the app's folder (`<GAME>_DEST_PATH`). The copy is atomic, so the app never reads a half-written file. An invalid download, such as an HTML error page, never replaces a good file.
4. **Changes the file owner** to `OWNER:GROUP`. This step runs on Linux only.
5. **Refreshes the app cache** by running `php artisan <GAME>_CACHE_COMMAND` in `MAIN_DEST_PATH`, once, after all years.

Without `--year`, a script downloads the current year. During the first 7 days of January it also downloads the previous year, so the last draws of December are picked up. In that period the previous year is required, and the new year is optional because its file doesn't exist before the first draw.

## Prerequisites

- Python 3.10+
- Microsoft Edge or Google Chrome, or Playwright's bundled Chromium
- PHP on `PATH`, for the cache refresh

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/tkouleris/eurojackpot-stats-downloader.git
   cd eurojackpot-stats-downloader
   ```

2. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright's Chromium.** This is only needed if neither Edge nor Chrome is installed:
   ```bash
   playwright install chromium
   ```

4. **Create the configuration:**
   ```bash
   cp .env.example .env
   ```
   Then fill in `.env`; see [Configuration](#configuration).

## Configuration

The scripts read `.env` from the project folder, wherever they are run from.

| Variable | Used by | Description |
|---|---|---|
| `EUROJACKPOT_DEST_PATH`, `JOKER_DEST_PATH`, `LOTTO_DEST_PATH` | the matching script | Folder of the app where the file is installed. It must already exist. |
| `EUROJACKPOT_CACHE_COMMAND`, `JOKER_CACHE_COMMAND`, `LOTTO_CACHE_COMMAND` | the matching script | Artisan command that refreshes the app cache, without `php artisan` (for example `app:cache-lotto`). |
| `MAIN_DEST_PATH` | all | Root folder of the Laravel app; the artisan command runs there. |
| `OWNER`, `GROUP` | all, Linux only | Owner and group the installed file is given (for example `www-data`). |

## Usage

```bash
python eurojackpot.py
python joker.py
python lotto.py
```

### CLI options

All three scripts take the same options.

| Option | Description | Default |
|---|---|---|
| `--year` | Year to download (four digits) | Current year, plus the previous year during January 1–7 |
| `--output-dir` | Folder where the downloaded files are kept | `downloads/` in the project folder |
| `--url` | URL of the results page | The game's results page |
| `--headless` / `--no-headless` | Run the browser hidden, or with a visible window | `--headless` |

### Examples

- **Download a specific year:**
  ```bash
  python eurojackpot.py --year 2025
  ```

- **Watch the browser, for example when the site changes:**
  ```bash
  python lotto.py --no-headless
  ```

- **Keep the downloads in another folder:**
  ```bash
  python joker.py --output-dir ./custom_folder
  ```

### Running from cron

```cron
0 5 * * * /path/to/venv/bin/python /path/to/eurojackpot-stats-downloader/eurojackpot.py
```

The exit code is `1` in these cases:

- a required year could not be downloaded
- an install or owner change failed
- the cache refresh failed
- nothing was installed

Otherwise the exit code is `0`.

## Output and logs

- **Downloads:** kept in `downloads/`, for example `downloads/Eurojackpot_2026.xlsx`.
- **Logs:** each game logs to its own file in the project folder (`log_eurojackpot.txt`, `log_joker.txt`, `log_lotto.txt`). Each line is timestamped as `[YYYY-MM-DD HH:MM:SS]`. The log also says whether a file came from the browser or from the direct download.

## Development

The three scripts are thin wrappers. The shared code is in the `lottery/` package:

| Module | Responsibility |
|---|---|
| `config.py` | `GameConfig` for each game, and the `.env` settings |
| `pipeline.py` | Command-line options, years to download, exit code |
| `browser.py` | Download through the results page (Playwright) |
| `direct.py` | Direct download from `media.opap.gr` |
| `install.py` | Atomic install and owner change |
| `cache.py` | `php artisan` cache refresh |
| `log.py` | Logging to the console and to the log file |

To add a game, define a `GameConfig` in `lottery/config.py` and add a wrapper script like `lotto.py`.

Run the tests with:

```bash
python -m unittest
```

They need no network and never touch the app. Running a script, by contrast, installs the file in `<GAME>_DEST_PATH` and runs `php artisan`.

## License

This project is licensed under the MIT License.
