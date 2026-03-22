# CrawlyCat — Detailed Documentation

![Issues Welcome](https://img.shields.io/badge/issues-welcome-brightgreen.svg)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

I run [nerdyelectronics.com](https://nerdyelectronics.com). I wanted a quick way to check broken links, technical issues, and general SEO health, but most tools were paid or too restrictive for frequent checks. I built this tool first for my own workflow, and I am sharing it in case it helps you too.

Fast technical website crawler for periodic audits. It is designed to surface issues quicker than waiting for search console recrawl cycles.

## What it checks

- HTTP status issues (`4xx`, `5xx`)
- Redirect chains
- Title and meta description quality checks
- Missing or multiple `h1`
- Internal broken-link references
- External links (not crawled, only noted)

## Features

- **Browser mode** (default) — launches headless Chromium via Playwright to render JavaScript and bypass Cloudflare/bot-protection challenge pages
- **Fast mode** — uses raw HTTP requests via httpx; ~10x faster but cannot handle JS-rendered pages or bot challenges
- **Web UI mode** — browser-based interface powered by Flask + Server-Sent Events
  - Same controls as GUI: URL, Max Pages, Timeout, Delay, Fast mode, User-Agent
  - Live log with dark terminal-style panel (auto-scroll, capped at 500 lines)
  - Live status updates via SSE (no polling)
  - Summary panel with run details
  - Status tabs (`404`, `415`, `5xx`, `Other 4xx`, `Fetch Failed`, `External Links`)
  - Click URL in tabs to see details, double-click to open in browser
  - Responsive layout (log and summary side by side)
  - Start/Stop/Open Report buttons
  - Single-page app served from Python (no npm/node)
  - Opens browser automatically at `http://127.0.0.1:5000`
- **GUI mode** (desktop) with live crawl progress
  - Currently checked URL and result
  - Status/result log
  - Post-run summary (with stopped status if applicable)
  - Status tabs (`404`, `415`, `5xx`, `Other 4xx`, `Fetch Failed`, `External Links`)
  - Selected URL details with link trace (`Found on: ...`)
  - Configurable User-Agent field
  - Stop button to halt crawl mid-run
  - Open Report button for one-click HTML report viewing
- **CLI mode** for scripting, CI pipelines, and scheduled runs
- **Rate limiting** — configurable delay between requests (default 0.5s)
- **Robots.txt** — automatically respected; cannot be disabled
- **CSV output** for quick sharing
- **HTML report** — self-contained, tabbed, sortable report with grouped external links
- **SQLite history** for run-to-run tracking

## Project structure

- `crawler/cli.py` - crawl engine, issue detection, report generation, and CLI entry point
- `crawler/gui.py` - desktop GUI (tkinter)
- `crawler/web.py` - Flask web UI with SSE
- `crawler/templates/index.html` - web UI template
- `crawler/__main__.py` - entry point with subcommands (`web`, `gui`, or CLI)

## Requirements

- Python 3.10+
- Dependencies in `requirements.txt`

## Setup

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

## Usage

CrawlyCat has three launch modes: Web UI, desktop GUI, and CLI.

### Web UI

```bash
python -m crawler web
```

Opens your browser at `http://127.0.0.1:5000`. Provides the same controls as the desktop GUI in a browser-based interface with live log updates via Server-Sent Events.

### GUI (desktop)

```bash
python -m crawler gui
```

### CLI

```bash
python -m crawler --url https://example.com --max-pages 200 --html-out report.html
```

### All CLI options

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--url` | string | **required** | Root URL to start crawling |
| `--max-pages` | integer | `200` | Maximum number of pages to crawl |
| `--timeout` | float | `15.0` | HTTP request timeout in seconds |
| `--delay` | float | `0.5` | Seconds to wait between requests (rate limiting) |
| `--fast` | flag | off | Use raw HTTP requests instead of headless browser |
| `--csv-out` | string | `issues.csv` | File path for CSV output |
| `--html-out` | string | _(none)_ | File path for HTML report (not generated if omitted) |
| `--db-path` | string | `crawl_history.db` | File path for SQLite history database |
| `--user-agent` | string | Chrome 123 UA | Custom User-Agent string |

### Recommended first run

```bash
python -m crawler --url https://example.com --max-pages 50 --html-out report.html
```

Then open:
- `report.html` for the visual report
- `issues.csv` for raw findings
- `crawl_history.db` for run history

## Output artifacts

### CSV (`issues.csv`)

| Column | Description |
|--------|-------------|
| `url` | The URL where the issue was found |
| `issue_type` | Machine-readable issue identifier |
| `severity` | One of: `critical`, `high`, `medium`, `low`, `info` |
| `details` | Human-readable description |

### HTML report

A self-contained HTML file with:
- **Tabbed categories** — 404, 5xx, Other 4xx, SEO Issues, Redirects, Fetch Failed, External Links
- **Grouped external links** — deduplicated by URL with source page count
- **Summary bar** — pages crawled, unique pages (200 OK), issue count, external link count, severity badges
- **Sortable columns** — click any header to sort
- **Color-coded severity badges**
- **Clickable URLs** — open any URL in a new tab
- **Footer link** — links back to the CrawlyCat GitHub repo

CLI: generated only when `--html-out` is provided.
GUI / Web UI: automatically generated with a timestamped filename (`report_{domain}_{date}_{time}.html`).

### SQLite database (`crawl_history.db`)

- `crawl_runs` — one row per crawl run
- `issues` — all issues with foreign key to run

## Issue types

| Type | Severity | Description |
|------|----------|-------------|
| `http_4xx` | high | 400-level client error (404, 403, etc.) |
| `http_5xx` | critical | 500-level server error |
| `redirect` | medium/high | Redirect chain (high if 2+ hops) |
| `meta_title_missing` | medium | No `<title>` tag |
| `meta_title_length` | low | Title outside 15-65 character range |
| `meta_description_missing` | medium | No `<meta description>` tag |
| `meta_description_length` | low | Description outside 50-160 character range |
| `h1_missing` | medium | No `<h1>` tag |
| `h1_multiple` | low | More than one `<h1>` tag |
| `internal_broken_link` | high | Link to an internal page that returned 4xx/5xx |
| `fetch_failed` | high | Page could not be loaded at all |
| `robots_blocked` | info | Root URL disallowed by robots.txt |
| `url_parameter_explosion_skipped` | info | Too many query variants for a path (cap: 5) |

## How link tracing works

- For failed URLs (`4xx`, `5xx`), details include up to 5 referrer pages.
- External URLs are not crawled; each is logged with its source page.

## URL handling policy

- URL fragments are removed (`#section` does not create a new crawl URL).
- `mailto:`, `tel:`, and `javascript:` links are ignored.
- Tracking params are dropped during normalization (`utm_*`, `gclid`, `fbclid`, `msclkid`, `yclid`, `mc_cid`, `mc_eid`, `_ga`, `_gl`).
- Query parameter order is normalized to reduce duplicates.
- `www.` host variant is canonicalized to root host for dedupe.
- Default ports are canonicalized (`:80` for HTTP, `:443` for HTTPS).
- Risky internal paths are skipped: `logout`, `log-out`, `signout`, `sign-out`, `calendar`, `download`.
- Query variant crawl is capped at 5 per base path to avoid parameter explosions.

## Built-in safety rules

- **Robots.txt** is automatically fetched and honored. If the root URL is disallowed, the crawl returns immediately. Internal links disallowed by robots.txt are silently skipped. This cannot be disabled.
- **Rate limiting** defaults to 0.5 seconds between requests. Set `--delay 0` for maximum speed (not recommended for production sites).
- **Bot-protection bypass** (browser mode only) — detects Cloudflare challenge pages ("One moment, please...", "Just a moment...", "Attention Required") and waits up to 30 seconds for them to resolve.
- **Skipped URL patterns** — paths containing `logout`, `signout`, `calendar`, `download` (and variants) are never crawled.
- **Query explosion cap** — stops enqueuing after 5 query variants per base path.

## Current limitations

- Internal links only (same host as start URL)
- No sitemap seeding yet
- No duplicate title/description detection across pages yet

## Roadmap ideas

- Sitemap support
- Duplicate content/meta cluster checks
- Scheduled runs + alerting (email/Slack)
- Diff view: new issues vs previous run

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

## Disclaimer

This project is provided as-is, with no warranties and no liability accepted by the author or contributors. See `DISCLAIMER.md`.

## Contributing

If you would like to help fix bugs, improve checks, or extend features, contributions are very welcome. See `CONTRIBUTING.md`.
