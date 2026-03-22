# Reports

CrawlyCat generates three types of output after every crawl.

## CSV report (`issues.csv`)

A simple comma-separated file with all issues found. Good for importing into spreadsheets or processing with scripts.

**Columns:**

| Column | Description |
|--------|-------------|
| `url` | The URL where the issue was found |
| `issue_type` | Machine-readable issue identifier (e.g. `http_4xx`, `h1_missing`) |
| `severity` | One of: `critical`, `high`, `medium`, `low`, `info` |
| `details` | Human-readable description of the issue |

**CLI:** Always generated. Default path: `issues.csv`. Change with `--csv-out`.

**GUI / Web UI:** Always generated as `issues.csv` in the current directory. Overwritten each run.

## HTML report

A self-contained HTML file you can open in any browser and share with anyone. No server or dependencies needed.

### Features

- **Tabbed categories** - issues are grouped into tabs matching the GUI: 404, 5xx, Other 4xx, SEO Issues, Redirects, Fetch Failed, External Links
- **Grouped external links** - instead of one row per occurrence, external links are deduplicated by URL showing the number of source pages where each was found (with links to up to 10 source pages)
- **Summary bar** - pages crawled, unique pages (200 OK), issue count (excluding external links), unique external link count, and severity badges
- **Sortable columns** - click any column header to sort ascending/descending
- **Severity sorting** - sorts by severity rank (critical first), not alphabetically
- **Color-coded severity badges** - critical (red), high (orange), medium (yellow), low (blue), info (gray)
- **Clickable URLs** - click any URL to open it in a new tab
- **Footer link** - links back to the CrawlyCat GitHub repo

### Naming convention

**CLI:** You choose the filename with `--html-out`. Not generated if omitted.

```bash
python -m crawler --url https://example.com --html-out report.html
```

**GUI / Web UI:** Automatically generated with a timestamped name:

```
report_{domain}_{date}_{time}.html
```

**Format breakdown:**

| Part | Source | Example |
|------|--------|---------|
| `report_` | Fixed prefix | `report_` |
| `{domain}` | Domain from URL, non-alphanumeric chars replaced with `_` | `nerdyelectronics_com` |
| `{date}` | Date in `YYYY-MM-DD` format | `2026-03-22` |
| `{time}` | Time in `HHMMSS` format | `143015` |

**Full example:**

```
report_nerdyelectronics_com_2026-03-22_143015.html
```

Each GUI / Web UI crawl creates a **new file** (never overwrites previous reports), so you keep a history of all runs.

### Opening reports

- **Web UI:** Click the **Open Report** button after a crawl completes; opens the report in a new browser tab
- **GUI:** Click the **Open Report** button after a crawl completes
- **CLI:** Open the file in your browser manually
- **Sharing:** Send the `.html` file to anyone; it works offline with no dependencies

## SQLite database (`crawl_history.db`)

A persistent database that stores all crawl runs and their issues. Unlike CSV and HTML reports, the database is **appended to** (not overwritten) with each run, giving you a history of all crawls.

### Tables

#### `crawl_runs`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-incrementing run ID |
| `started_at` | TEXT | Timestamp when the crawl started (`YYYY-MM-DD HH:MM:SS`) |
| `root_url` | TEXT | The starting URL that was crawled |
| `pages_crawled` | INTEGER | Total pages visited in this run |

#### `issues`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-incrementing issue ID |
| `run_id` | INTEGER | Foreign key to `crawl_runs.id` |
| `url` | TEXT | URL where the issue was found |
| `issue_type` | TEXT | Issue identifier |
| `severity` | TEXT | Issue severity |
| `details` | TEXT | Human-readable description |
| `created_at` | TEXT | Timestamp when the issue was recorded |

### Querying the database

You can query the database directly with any SQLite client:

```sql
-- All issues from the latest run
SELECT * FROM issues
WHERE run_id = (SELECT MAX(id) FROM crawl_runs);

-- Compare issue counts between runs
SELECT cr.id, cr.started_at, cr.pages_crawled, COUNT(i.id) as issue_count
FROM crawl_runs cr
LEFT JOIN issues i ON i.run_id = cr.id
GROUP BY cr.id
ORDER BY cr.id DESC;

-- Find all 404 errors across all runs
SELECT cr.started_at, i.url, i.details
FROM issues i
JOIN crawl_runs cr ON cr.id = i.run_id
WHERE i.issue_type = 'http_4xx' AND i.details LIKE '%404%'
ORDER BY cr.started_at DESC;
```

**CLI:** Default path: `crawl_history.db`. Change with `--db-path`.

**GUI / Web UI:** Always saved as `crawl_history.db` in the current directory.

## Which report to use

| Need | Use |
|------|-----|
| Share findings with a non-technical person | HTML report |
| Import into a spreadsheet or script | CSV |
| Track issues over time across multiple runs | SQLite database |
| Quick review after a crawl | GUI or Web UI summary and status tabs |

## See also

- [Issue Types Reference](Issue-Types-Reference.md) for what each issue type means
- [CLI Reference](CLI-Reference.md) for output path options
