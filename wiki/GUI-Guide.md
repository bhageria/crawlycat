# GUI Guide

> **Prefer a browser-based interface?** See the [[Web UI Guide]] for an alternative that runs in your browser with the same features.

Launch the desktop GUI:

```bash
python -m crawler gui
```

## Interface layout

The GUI window has these sections from top to bottom:

### Toolbar

The top row contains input fields and controls:

| Control | Description |
|---------|-------------|
| **URL** | The starting URL to crawl |
| **Max Pages** | Maximum number of pages to crawl (default: 200) |
| **Timeout** | Request timeout in seconds (default: 15) |
| **Delay** | Seconds to wait between requests (default: 0.5) |
| **Fast (no JS)** | Checkbox to use raw HTTP instead of headless browser |
| **Start Crawl** | Begins the crawl |
| **Stop** | Stops the crawl after the current page finishes |
| **Open Report** | Opens the latest HTML report in your browser |

The second row contains:

| Control | Description |
|---------|-------------|
| **User-Agent** | The User-Agent string sent with every request. Defaults to a Chrome browser string. Change to a custom value (e.g. `CrawlyCat/1.0`) for your own sites where you've allowlisted it in Cloudflare or similar services. |

### Live Status

Shows the URL currently being checked and its result (status code or error).

### Live Log

A scrolling log of every URL checked and its result. Each line shows:

```
         200  https://example.com/page1
         404  https://example.com/broken-link
  fetch_failed  https://example.com/timeout-page
```

### Summary

After the crawl completes (or is stopped), shows:
- Run ID
- Status (completed or STOPPED by user)
- Pages crawled and total issues
- Status code breakdown
- External link counts
- Issue type breakdown
- List of saved files

### Status Tabs

Issues grouped into tabs for quick review:

| Tab | What it shows |
|-----|---------------|
| **404** | Pages returning 404 Not Found |
| **415** | Pages returning 415 Unsupported Media Type |
| **5xx** | Pages returning any 500-level server error |
| **Other 4xx** | Pages returning 4xx errors other than 404 and 415 |
| **Fetch Failed** | Pages that failed to load (timeout, connection error) |
| **External Links** | External URLs found on crawled pages (not crawled) |

Double-click any URL in a tab to open it in your browser.
Click any URL to see its issue details in the panel below.

### Selected URL Details

When you click a URL in any status tab, this panel shows all issues associated with that URL, including which pages link to it.

## Using the Stop button

Click **Stop** to halt the crawl after the current page finishes processing. The crawl will:

1. Complete the page currently being fetched
2. Skip all remaining pages in the queue
3. Run issue detection on all pages crawled so far
4. Save CSV, HTML report, and database as normal
5. Show the summary with "STOPPED by user" status

This is useful for large crawls where you've already seen enough data.

## Using the Open Report button

After a crawl completes, the **Open Report** button becomes active. Click it to open the HTML report in your default web browser. The report includes:

- **Tabbed categories** — 404, 5xx, Other 4xx, SEO Issues, Redirects, Fetch Failed, External Links
- **Grouped external links** — deduplicated by URL with source page count (instead of one row per occurrence)
- **Summary bar** — pages crawled, unique pages (200 OK), issue count, unique external links, severity badges
- **Sortable columns** — click any header to sort ascending/descending
- **Severity sorting** — sorts by severity rank (critical first), not alphabetically
- **Color-coded severity badges** — critical (red), high (orange), medium (yellow), low (blue), info (gray)
- **Clickable URLs** — click any URL to open it in a new tab
- **Footer link** — links back to the CrawlyCat GitHub repo

The report is a self-contained HTML file you can share with anyone — no server or dependencies needed.

## Output files

Every GUI crawl produces three files in the current working directory:

| File | Description |
|------|-------------|
| `issues.csv` | All issues in CSV format (overwritten each run) |
| `report_{domain}_{timestamp}.html` | HTML report (new file each run) |
| `crawl_history.db` | SQLite database (appended each run) |

See [[Reports]] for details on naming and contents.

## See also

- [[Web UI Guide]] for the browser-based alternative
- [[Settings and Configuration]] for what each setting does
- [[Reports]] for report file format and naming
