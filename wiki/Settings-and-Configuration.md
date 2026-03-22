# Settings and Configuration

## Crawl settings

### URL

The starting point of the crawl. The crawler will discover and follow internal links from this page outward.

- Must be a full URL including `https://` or `http://`
- Only pages on the **same domain** as this URL are crawled
- External links are logged but never followed
- CLI: `--url https://example.com`
- GUI / Web UI: **URL** field

### Max Pages

The maximum number of pages the crawler will visit.

- Once this limit is reached, the crawl stops even if there are more pages to visit
- Pages that fail to load still count toward this limit
- Set lower (e.g. 50) for a quick scan, higher (e.g. 500+) for a full audit
- Default: **200**
- CLI: `--max-pages 200`
- GUI / Web UI: **Max Pages** field

### Timeout

How long to wait for a single page to respond before giving up.

- Applies per request, not to the entire crawl
- If a page exceeds this timeout, it is logged as `fetch_failed`
- In browser mode, this also limits how long Playwright waits for the page to load
- Increase for slow sites (e.g. 30); decrease for fast sites (e.g. 5)
- Default: **15 seconds**
- CLI: `--timeout 15`
- GUI / Web UI: **Timeout** field

### Delay

Seconds to wait between consecutive requests (rate limiting).

- The first request has no delay; all subsequent requests wait this amount
- Prevents overwhelming the target server and reduces the chance of IP bans or WAF blocks
- Set to `0` for maximum speed (not recommended for production sites)
- Set to `2.0` or higher for gentle crawling of sensitive sites
- Default: **0.5 seconds**
- CLI: `--delay 0.5`
- GUI / Web UI: **Delay** field

### Fast mode (no JS)

Controls whether the crawler uses a headless browser or raw HTTP requests.

| | Browser mode (default) | Fast mode |
|---|---|---|
| **How it works** | Launches headless Chromium via Playwright | Direct HTTP requests via httpx |
| **JavaScript** | Executed | Not executed |
| **Bot protection** | Can bypass Cloudflare and similar challenges | Cannot bypass; may see challenge pages |
| **Speed** | ~2-5 seconds per page | ~0.2-0.5 seconds per page |
| **Resource usage** | High (runs a browser process) | Low |
| **Redirect tracking** | Simplified (detects if URL changed) | Full redirect chain with all status codes |
| **Best for** | Sites with JS rendering or bot protection | Static sites, quick scans, CI pipelines |

- CLI: `--fast` flag
- GUI / Web UI: **Fast (no JS)** checkbox

### User-Agent

The User-Agent string sent with every request. Defaults to a Chrome browser string to appear as a regular browser visit.

Changing this is useful if:
- You want the crawl to identify itself (e.g. `CrawlyCat/1.0`)
- The target site serves different content based on User-Agent
- You want to test how the site responds to specific bots

Default: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36`

- CLI: `--user-agent "custom string"`
- GUI / Web UI: **User-Agent** field

## Robots.txt

The crawler automatically fetches and honors `robots.txt` before crawling. This means:

- If the root URL is disallowed by `robots.txt`, the crawl returns immediately with a `robots_blocked` issue
- Internal links disallowed by `robots.txt` are silently skipped
- If `robots.txt` cannot be fetched (404, timeout, etc.), it is ignored and all URLs are allowed

The `robots.txt` request uses the crawler's configured User-Agent (not Python's default `Python-urllib` agent), so it is not blocked by services like Cloudflare Browser Integrity Check.

This behavior cannot be disabled. Respecting `robots.txt` is considered good practice and prevents crawling paths the site owner has explicitly restricted.

## Built-in safety rules

These are hardcoded behaviors that protect both the crawler and the target site:

### Skipped URL patterns

Internal URLs containing these path keywords are never crawled:

- `logout`, `log-out`
- `signout`, `sign-out`
- `calendar`
- `download`

These paths could trigger side effects (logging users out, downloading large files) and are skipped as a safety measure.

### Query parameter explosion cap

If the crawler encounters more than **5 different query string variants** for the same base path, it stops enqueuing new variants for that path. This prevents infinite crawling of paginated or filtered URLs like:

```
/products?page=1
/products?page=2
/products?page=3
...
```

Skipped URLs are logged as `url_parameter_explosion_skipped` issues.

### Bot-protection challenge detection (browser mode only)

When using the headless browser, the crawler detects challenge pages with these titles:

- "One moment, please..."
- "Just a moment..."
- "Attention Required"

If detected, it waits up to 30 seconds for the challenge to resolve before proceeding. This handles Cloudflare and similar services, though success is not guaranteed for all protection types.

## See also

- [[CLI Reference]] for the full argument list
- [[GUI Guide]] for the desktop interface
- [[Web UI Guide]] for the browser-based interface
- [[URL Handling]] for normalization details
