# CLI Reference

Run the crawler from the command line:

```bash
python -m crawler --url <URL> [options]
```

## Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--url` | string | **required** | Root URL to start crawling (e.g. `https://example.com`) |
| `--max-pages` | integer | `200` | Maximum number of pages to crawl |
| `--timeout` | float | `15.0` | HTTP request timeout in seconds |
| `--delay` | float | `0.5` | Seconds to wait between requests (rate limiting) |
| `--fast` | flag | off | Use raw HTTP requests instead of headless browser |
| `--csv-out` | string | `issues.csv` | File path for CSV output |
| `--html-out` | string | _(none)_ | File path for HTML report (not generated if omitted) |
| `--db-path` | string | `crawl_history.db` | File path for SQLite history database |
| `--user-agent` | string | Chrome 123 UA | Custom User-Agent string |

## Examples

### Basic crawl

```bash
python -m crawler --url https://example.com
```

Crawls up to 200 pages using the headless browser, saves `issues.csv` and `crawl_history.db`.

### Quick scan with HTML report

```bash
python -m crawler --url https://example.com --max-pages 50 --html-out report.html
```

### Fast mode (no JavaScript rendering)

```bash
python -m crawler --url https://example.com --fast
```

Skips the headless browser and uses raw HTTP requests. Much faster but cannot bypass bot-protection pages or crawl JavaScript-rendered content.

### Aggressive crawl (low delay)

```bash
python -m crawler --url https://example.com --delay 0.1 --max-pages 500
```

**Use with caution.** Low delay values may trigger rate limiting or IP bans on the target site.

### Gentle crawl (high delay)

```bash
python -m crawler --url https://example.com --delay 2.0
```

Waits 2 seconds between requests. Good for sites with strict rate limiting.

### Custom output paths

```bash
python -m crawler --url https://example.com --csv-out results/issues.csv --db-path results/history.db --html-out results/report.html
```

## Output

After a crawl, the CLI prints a summary:

```
Pages crawled: 47
Status counts:
  200: 42
  301: 3
  404: 2
Total issues: 15
Top issue types:
  external_link_found: 8
  meta_description_missing: 3
  redirect: 3
  http_4xx: 1
Run id: 5
Issues CSV: issues.csv
HTML report: report.html
History DB: crawl_history.db
```

## Exit behavior

The CLI runs to completion (or until `--max-pages` is reached). There is no built-in stop mechanism for the CLI. Use `Ctrl+C` to abort.

## See also

- [[Settings and Configuration]] for detailed explanation of each setting
- [[Reports]] for understanding output files
