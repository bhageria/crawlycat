# Web UI Guide

Launch the Web UI:

```bash
python -m crawler web
```

Your default browser opens automatically at `http://127.0.0.1:5000`. The Web UI is a single-page app served entirely from Python (Flask) — no npm, node, or external build tools are needed. The only additional dependency beyond the base crawler is `flask`.

> **Prefer a native desktop window?** See the [GUI Guide](GUI-Guide.md) for the tkinter-based alternative with the same feature set.

## Interface layout

The Web UI provides a responsive layout with all controls, a live log, summary panel, and status tabs in one page.

### Toolbar

The top section contains input fields and controls:

| Control | Description |
|---------|-------------|
| **URL** | The starting URL to crawl |
| **Max Pages** | Maximum number of pages to crawl (default: 200) |
| **Timeout** | Request timeout in seconds (default: 15) |
| **Delay** | Seconds to wait between requests (default: 0.5) |
| **Fast (no JS)** | Checkbox to use raw HTTP instead of headless browser |
| **User-Agent** | The User-Agent string sent with every request. Defaults to a Chrome browser string. |
| **Start Crawl** | Begins the crawl |
| **Stop** | Stops the crawl after the current page finishes |
| **Open Report** | Opens the latest HTML report in a new browser tab |

### Live Log

A dark terminal-style panel that streams crawl results in real time via Server-Sent Events (SSE). Each line shows the status code (or error) and the URL checked. The log auto-scrolls to the latest entry and is capped at 500 lines.

### Summary Panel

Displayed side by side with the live log (responsive layout). After the crawl completes (or is stopped), shows:

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

- Click any URL in a tab to see its issue details.
- Double-click any URL to open it in your browser.

## Live updates via SSE

The Web UI uses Server-Sent Events to stream status updates from the server to the browser. This means:

- No page refreshes or polling — updates arrive instantly
- The connection is lightweight and one-directional (server to browser)
- If the browser tab is closed, the crawl continues running on the server

## Using the Stop button

Click **Stop** to halt the crawl after the current page finishes processing. The crawl will:

1. Complete the page currently being fetched
2. Skip all remaining pages in the queue
3. Run issue detection on all pages crawled so far
4. Save CSV, HTML report, and database as normal
5. Show the summary with "STOPPED by user" status

## Using the Open Report button

After a crawl completes, the **Open Report** button becomes active. Click it to open the HTML report in a new browser tab. The report is a self-contained HTML file you can save and share with anyone — no server or dependencies needed.

## Output files

Every Web UI crawl produces three files in the current working directory:

| File | Description |
|------|-------------|
| `issues.csv` | All issues in CSV format (overwritten each run) |
| `report_{domain}_{timestamp}.html` | HTML report (new file each run) |
| `crawl_history.db` | SQLite database (appended each run) |

See [Reports](Reports.md) for details on naming and contents.

## See also

- [GUI Guide](GUI-Guide.md) for the desktop alternative
- [Settings and Configuration](Settings-and-Configuration.md) for what each setting does
- [Reports](Reports.md) for report file format and naming
