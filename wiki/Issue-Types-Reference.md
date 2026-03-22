# Issue Types Reference

Every issue found by CrawlyCat has a type, severity, and details string. This page explains each one.

## Severity levels

| Severity | Color | Meaning |
|----------|-------|---------|
| **critical** | Red | Site is broken for users; fix immediately |
| **high** | Orange | Significant problem affecting SEO or user experience |
| **medium** | Yellow | Notable issue worth investigating |
| **low** | Blue | Minor optimization opportunity |
| **info** | Gray | Informational; no action required |

## HTTP status issues

### `http_5xx` (critical)

**What:** A page returned a 500-level server error (500, 502, 503, etc.).

**Why it matters:** Server errors mean the page is broken. Users see an error page, and search engines may drop the page from their index.

**Details include:** The specific status code and up to 5 referrer pages that link to this URL.

**How to fix:** Check server logs for the specific URL. Common causes: application bugs, database errors, misconfigured server rules.

---

### `http_4xx` (high)

**What:** A page returned a 400-level client error (400, 401, 403, 404, 410, etc.).

**Why it matters:** 404s are broken links that frustrate users and waste crawl budget. 403s may indicate access control issues.

**Details include:** The specific status code and up to 5 referrer pages that link to this URL.

**How to fix:**
- **404:** Remove or update links pointing to this page, or create a redirect to the correct URL
- **403:** Check access permissions; the page may be unintentionally restricted
- **410:** Intentionally removed; ensure links are cleaned up

---

## Redirect issues

### `redirect` (medium or high)

**What:** A page redirected to a different URL before serving content.

**Severity:**
- **medium** if the chain has 1 redirect (e.g. HTTP to HTTPS)
- **high** if the chain has 2+ redirects

**Why it matters:** Redirect chains slow down page loads and dilute SEO link equity. Multiple redirects compound the problem.

**Details include:** The number of redirects and the full chain (e.g. `301 -> 301 -> 200`).

**How to fix:** Update links to point directly to the final destination URL. Eliminate intermediate redirects where possible.

---

## SEO issues

### `meta_title_missing` (medium)

**What:** The page has no `<title>` tag.

**Why it matters:** The title tag is the most important on-page SEO element. It appears in search results and browser tabs. Missing titles hurt click-through rates and rankings.

**How to fix:** Add a unique, descriptive `<title>` tag to the page's `<head>`.

---

### `meta_title_length` (low)

**What:** The title tag exists but its length is outside the recommended range.

**Recommended range:** 15-65 characters.

**Why it matters:** Titles shorter than 15 characters are likely too vague. Titles longer than 65 characters get truncated in search results.

**How to fix:** Rewrite the title to be descriptive and within 15-65 characters.

---

### `meta_description_missing` (medium)

**What:** The page has no `<meta name="description">` tag.

**Why it matters:** Meta descriptions appear as the snippet in search results. Without one, search engines generate their own (often poorly).

**How to fix:** Add a `<meta name="description" content="...">` tag to the page's `<head>`.

---

### `meta_description_length` (low)

**What:** The meta description exists but its length is outside the recommended range.

**Recommended range:** 50-160 characters.

**Why it matters:** Descriptions shorter than 50 characters miss an opportunity to attract clicks. Descriptions longer than 160 characters get truncated.

**How to fix:** Rewrite the description to summarize the page in 50-160 characters.

---

### `h1_missing` (medium)

**What:** The page has no `<h1>` tag.

**Why it matters:** The h1 tag is the main heading of the page. Search engines use it to understand the page's topic. Screen readers rely on it for accessibility.

**Note:** Large, bold text styled with CSS is not the same as an `<h1>` tag. The crawler checks the HTML structure, not visual appearance. If your page looks like it has a heading but this issue is reported, the heading is likely a styled `<div>` or `<p>` tag instead of a proper `<h1>`.

**How to fix:** Wrap the page's main heading in `<h1>` tags.

---

### `h1_multiple` (low)

**What:** The page has more than one `<h1>` tag.

**Why it matters:** While HTML5 technically allows multiple h1 tags, best practice for SEO is to have exactly one h1 per page to clearly signal the page's primary topic.

**How to fix:** Keep the most important heading as `<h1>` and change the others to `<h2>` or lower.

---

## Link issues

### `internal_broken_link` (high)

**What:** This page contains a link to another internal page that returned a 4xx or 5xx error.

**Why it matters:** Broken internal links create dead ends for users and search engine crawlers.

**Details include:** The target URL that is broken.

**How to fix:** Update or remove the broken link on the source page.

---

---

## Crawl issues

### `fetch_failed` (high)

**What:** The crawler could not load the page at all (connection error, timeout, DNS failure, etc.).

**Why it matters:** If the crawler can't reach the page, users and search engines may not be able to either.

**How to fix:** Check if the URL is correct and the server is reachable. May be a temporary issue — try again later.

---

### `robots_blocked` (info)

**What:** The root URL is disallowed by the site's `robots.txt` file.

**Why it matters:** The crawler respects `robots.txt` and will not crawl URLs that are disallowed. If this appears, the crawl could not proceed.

**How to fix:** If you own the site, update `robots.txt` to allow your crawler's User-Agent. If you don't own the site, respect the site owner's wishes.

---

### `url_parameter_explosion_skipped` (info)

**What:** The crawler found more than 5 query string variants for the same base URL path and stopped enqueuing new variants.

**Why it matters:** This prevents infinite crawling of paginated or filtered URLs (e.g. `/products?page=1`, `/products?page=2`, ...).

**Details include:** The URL that was skipped and the base path that triggered the cap.

---

### `internal_link_skipped_pattern` (info)

**What:** An internal link was found but skipped because it matched a safety pattern (logout, signout, calendar, download) or was blocked by `robots.txt`.

**Why it matters:** These URLs are intentionally not crawled to avoid side effects.

## See also

- [Reports](Reports.md) for how issues appear in output files
- [Settings and Configuration](Settings-and-Configuration.md) for crawl behavior settings
