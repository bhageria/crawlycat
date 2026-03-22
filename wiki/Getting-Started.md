# Getting Started

## Requirements

- Python 3.10 or newer
- pip (Python package manager)

## Installation

### Linux / macOS

```bash
git clone https://github.com/bhageria/crawlycat.git
cd crawlycat
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

### Windows PowerShell

```powershell
git clone https://github.com/bhageria/crawlycat.git
cd crawlycat
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

The `playwright install chromium` step downloads a bundled Chromium browser (~150 MB) used for JavaScript rendering and bypassing bot-protection pages. This is a one-time download.

## Your first crawl

### Using the GUI

```bash
python -m crawler.gui
```

1. Enter a URL in the **URL** field (e.g. `https://example.com`)
2. Set **Max Pages** to a small number for your first run (e.g. `50`)
3. Click **Start Crawl**
4. Watch the live log as pages are checked
5. When done, click **Open Report** to view the HTML report in your browser

### Using the CLI

```bash
python -m crawler --url https://example.com --max-pages 50
```

This will crawl up to 50 pages and produce:
- `issues.csv` - all issues found
- `crawl_history.db` - SQLite database with run history

To also generate an HTML report:

```bash
python -m crawler --url https://example.com --max-pages 50 --html-out report.html
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `httpx` | Fast HTTP requests (used in `--fast` mode) |
| `beautifulsoup4` | HTML parsing for link extraction and SEO checks |
| `playwright` | Headless browser for JS rendering and bot-protection bypass |
| `playwright-stealth` | Stealth patches to avoid headless browser detection |

## Next steps

- [[CLI Reference]] for all command-line options
- [[GUI Guide]] for the desktop interface
- [[Settings and Configuration]] to understand what each setting does
