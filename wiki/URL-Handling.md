# URL Handling

CrawlyCat normalizes, deduplicates, and filters URLs to avoid redundant crawling and ensure consistent issue reporting.

## URL normalization

Every URL discovered during a crawl is normalized before being queued or compared. This prevents the same page from being crawled multiple times under slightly different URLs.

### Normalization steps (in order)

| Step | Before | After |
|------|--------|-------|
| Remove fragments | `https://example.com/page#section` | `https://example.com/page` |
| Lowercase scheme | `HTTP://example.com` | `http://example.com` |
| Lowercase host | `https://Example.COM/page` | `https://example.com/page` |
| Remove default ports | `https://example.com:443/page` | `https://example.com/page` |
| | `http://example.com:80/page` | `http://example.com/page` |
| Remove `www.` prefix | `https://www.example.com/page` | `https://example.com/page` |
| Normalize path | `https://example.com/page/` | `https://example.com/page` |
| | `https://example.com` | `https://example.com/` |
| Strip tracking params | `https://example.com/page?utm_source=twitter&id=1` | `https://example.com/page?id=1` |
| Sort query params | `https://example.com/page?z=1&a=2` | `https://example.com/page?a=2&z=1` |

### Tracking parameters removed

These query parameters are automatically stripped because they are used for analytics tracking and do not change page content:

**Prefix match (any parameter starting with):**
- `utm_` (covers `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`)

**Exact match:**
- `gclid` (Google Ads)
- `fbclid` (Facebook)
- `msclkid` (Microsoft Ads)
- `yclid` (Yandex)
- `mc_cid`, `mc_eid` (Mailchimp)
- `_ga`, `_gl` (Google Analytics)

## Link discovery

Links are extracted from crawled HTML pages using these rules:

1. Only `<a href="...">` tags are followed
2. Relative URLs are resolved against the page's final URL (after redirects)
3. Only `http://` and `https://` links are kept
4. `mailto:`, `tel:`, and `javascript:` links are ignored
5. All discovered links are normalized before deduplication

## Internal vs external classification

A link is considered **internal** if its host (after normalization) matches the root URL's host. Everything else is **external**.

- Internal links are queued for crawling
- External links are logged as `external_link_found` issues but never crawled

**Example:** If the root URL is `https://nerdyelectronics.com`:

| URL | Classification |
|-----|---------------|
| `https://nerdyelectronics.com/about` | Internal |
| `https://www.nerdyelectronics.com/about` | Internal (www. stripped) |
| `https://blog.nerdyelectronics.com/post` | **External** (different subdomain) |
| `https://google.com` | External |

## Skipped URL patterns

Internal URLs containing these keywords in their path are never crawled:

| Keyword | Reason |
|---------|--------|
| `logout` | Could log users out of active sessions |
| `log-out` | Same as above |
| `signout` | Could end authenticated sessions |
| `sign-out` | Same as above |
| `calendar` | Often generates infinite date-based URLs |
| `download` | Could trigger large file downloads |

These are substring matches on the URL path. For example, `/user/logout` and `/auth/sign-out/confirm` would both be skipped.

## Query parameter explosion cap

When the crawler encounters more than **5 different query string variants** for the same base path, it stops enqueuing new variants. This prevents infinite crawling of URLs like:

```
/search?q=term1
/search?q=term2
/search?q=term3
/search?q=term4
/search?q=term5
/search?q=term6  <-- skipped, logged as url_parameter_explosion_skipped
```

The base path is determined by stripping the query string. So `/products?page=1` and `/products?category=shoes` are both variants of `/products`.

## Robots.txt filtering

After all other filters, URLs are checked against `robots.txt` rules (if available). Disallowed URLs are skipped and logged as `internal_link_skipped_pattern`.

See [Settings and Configuration](Settings-and-Configuration.md) for more on robots.txt behavior.

## See also

- [Issue Types Reference](Issue-Types-Reference.md) for issues related to URL handling
- [Settings and Configuration](Settings-and-Configuration.md) for configurable limits
