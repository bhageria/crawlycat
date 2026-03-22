# Website Crawler (GUI + CLI)

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

- **GUI mode** with live crawl progress
  - currently checked URL
  - status/result log
  - post-run summary
  - status tabs (`404`, `415`, `5xx`, `Other 4xx`, `External Links`)
  - selected URL details with link trace (`Found on: ...`)
- **CLI mode** for scripting and scheduling
- CSV output for quick sharing
- SQLite history for run-to-run tracking

## Project structure

- `crawler/cli.py` - crawl engine and CLI entry workflow
- `crawler/gui.py` - desktop GUI
- `crawler/__main__.py` - enables `python -m crawler`

## Requirements

- Python 3.10+
- Dependencies in `requirements.txt`

## Setup

```powershell
git clone <your-repo-url>
cd crawlycat
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

## Usage

### GUI

```powershell
python -m crawler.gui
```

### CLI

```powershell
python -m crawler --url https://example.com --max-pages 200 --csv-out issues.csv --db-path crawl_history.db
```

### Recommended first run

```powershell
python -m crawler --url https://example.com --max-pages 50 --csv-out issues.csv --db-path crawl_history.db
```

Then open:
- `issues.csv` for findings
- `crawl_history.db` for run history

## Output artifacts

- `issues.csv`
  - `url`
  - `issue_type`
  - `severity`
  - `details`
- `crawl_history.db`
  - `crawl_runs`
  - `issues`

## Issue types

- `http_4xx`
- `http_5xx`
- `redirect`
- `meta_title_missing`
- `meta_title_length`
- `meta_description_missing`
- `meta_description_length`
- `h1_missing`
- `h1_multiple`
- `internal_broken_link`
- `external_link_found`
- `fetch_failed`

## How link tracing works

- For failed URLs (`4xx`, `5xx`), details include referrer pages where available:
  - `Found on: <source page>`
- External URLs are not crawled; each is logged with its source page.

## URL handling policy

- URL fragments are removed (`#section` does not create a new crawl URL).
- `mailto:`, `tel:`, and `javascript:` links are ignored.
- Tracking params are dropped during normalization (for example `utm_*`, `gclid`, `fbclid`).
- Query parameter order is normalized to reduce duplicates.
- `www.` host variant is canonicalized to root host for dedupe.
- Default ports are canonicalized (`:80` for HTTP, `:443` for HTTPS).
- Risky internal paths are skipped and noted:
  - `logout`, `log-out`, `signout`, `sign-out`, `calendar`, `download`
- Query variant crawl is capped per path to avoid parameter explosions.

## Current limitations

- Internal links only (same host as start URL)
- No robots.txt enforcement yet
- No sitemap seeding yet
- No JavaScript rendering (single-pass static HTML parsing)
- No duplicate title/description detection across pages yet

## Roadmap ideas

- Robots and sitemap support
- Duplicate content/meta cluster checks
- Scheduled runs + alerting (email/Slack)
- Diff view: new issues vs previous run
- Export HTML report

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

## Disclaimer

This project is provided as-is, with no warranties and no liability accepted by the author or contributors. See `DISCLAIMER.md`.

## Contributing

If you would like to help fix bugs, improve checks, or extend features, contributions are very welcome. See `CONTRIBUTING.md`.
