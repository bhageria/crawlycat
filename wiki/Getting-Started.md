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

### Using the Web UI

```bash
python -m crawler web
```

1. Your browser opens automatically at `http://127.0.0.1:5000`
2. Enter a URL (e.g. `https://example.com`)
3. Set **Max Pages** to a small number for your first run (e.g. `50`)
4. Click **Start Crawl**
5. Watch the live log and status tabs update in real time
6. When done, click **Open Report** to view the HTML report

### Using the GUI (desktop)

```bash
python -m crawler gui
```

1. Enter a URL in the **URL** field (e.g. `https://example.com`)
2. Set **Max Pages** to a small number for your first run (e.g. `50`)
3. Click **Start Crawl**
4. Watch the live log as pages are checked
5. When done, click **Open Report** to view the HTML report in your browser

### Using the CLI

```bash
python -m crawler --url https://example.com --max-pages 50 --html-out report.html
```

This will crawl up to 50 pages and produce:
- `report.html` - tabbed HTML report (sortable, grouped external links)
- `issues.csv` - all issues found
- `crawl_history.db` - SQLite database with run history

## Dependencies

| Package | Purpose |
|---------|---------|
| `httpx` | Fast HTTP requests (used in `--fast` mode) |
| `beautifulsoup4` | HTML parsing for link extraction and SEO checks |
| `playwright` | Headless browser for JS rendering and bot-protection bypass |
| `playwright-stealth` | Stealth patches to avoid headless browser detection |
| `flask` | Web UI server with SSE support |

## Cloudflare / bot-protection note

If you are crawling your own site behind Cloudflare, the crawler's robots.txt request and page fetches use the configured User-Agent (defaults to a Chrome browser string). If Cloudflare's Bot Fight Mode still blocks requests, the simplest fix is to allowlist your IP address in Cloudflare (Security > WAF > Tools > IP Access Rules).

Alternatively, set a custom User-Agent (e.g. `CrawlyCat/1.0`) via the CLI `--user-agent` flag or the User-Agent field in the GUI/Web UI, and create a matching WAF rule in Cloudflare to skip checks for that agent.

## Next steps

- [[CLI Reference]] for all command-line options
- [[GUI Guide]] for the desktop interface
- [[Web UI Guide]] for the browser-based interface
- [[Settings and Configuration]] to understand what each setting does
