# Eurojackpot Stats Downloader

A Python tool designed to automate the download of Eurojackpot draw results (.xlsx spreadsheets) from Allwyn / OPAP.

## Features

- **Automated Web Scraping**: Uses Playwright to navigate the Allwyn results page, accept cookie consent dialogs, and trigger year-specific Excel downloads.
- **Fallback Direct Download**: Automatically attempts direct download from the OPAP media storage repository if browser automation fails.
- **Timestamped File Logging**: Logs all actions and status messages to `log.txt` alongside console output.
- **Flexible CLI Configuration**: Customise target year, output folder, target URL, and headless/headed browser mode via command-line arguments.

## Prerequisites

- Python 3.10+
- Supported browser (Chromium, Google Chrome, or Microsoft Edge)

## Installation

1. **Clone or download the repository:**
   ```bash
   git clone <repository_url>
   cd EurojackpotStatsDownloader
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browser binaries (if Chromium is not installed):**
   ```bash
   playwright install chromium
   ```

## Usage

Run the script with default settings (downloads the current year's draws in headless mode to `./downloads`):

```bash
python main.py
```

### CLI Options

| Argument | Description | Default |
|---|---|---|
| `--year` | The target year of draw results to download | `2026` |
| `--output-dir` | Directory where downloaded files are saved | `./downloads` |
| `--url` | The URL of the results page | `https://www.allwyn.gr/el/eurojackpot/draws-results` |
| `--headless` | Run browser in headless mode (default) | `True` |
| `--no-headless` | Run browser with visible UI window | `False` |

### Examples

- **Download results for a specific year:**
  ```bash
  python main.py --year 2025
  ```

- **Download with a visible browser window:**
  ```bash
  python main.py --year 2026 --no-headless
  ```

- **Save to a custom directory:**
  ```bash
  python main.py --year 2026 --output-dir ./custom_folder
  ```

## Output & Logs

- **Excel Files:** Stored in the `downloads/` folder (e.g., `downloads/Eurojackpot_2026.xlsx`).
- **Logs:** Execution history and errors are saved to `log.txt` with timestamps formatted as `[YYYY-MM-DD HH:MM:SS]`.

## License

This project is licensed under the MIT License.
