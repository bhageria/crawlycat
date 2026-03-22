"""CLI crawler engine for technical website audits.

The crawler performs a bounded BFS over internal links and records:
- status/redirect issues
- basic on-page SEO checks
- broken internal link references
- external links (not crawled, only noted)
"""

import argparse
import csv
import sqlite3
import threading
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urldefrag, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Browser, BrowserContext
from playwright_stealth import Stealth


DEFAULT_TIMEOUT = 15.0
DEFAULT_DELAY = 0.5
CRAWLYCAT_USER_AGENT = "CrawlyCat/1.0 (+https://github.com/bhageria/crawlycat)"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}
SKIP_PATH_KEYWORDS = {"logout", "log-out", "signout", "sign-out", "calendar", "download"}
TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_EXACT = {
    "gclid",
    "fbclid",
    "msclkid",
    "yclid",
    "mc_cid",
    "mc_eid",
    "_ga",
    "_gl",
}
MAX_QUERY_VARIANTS_PER_PATH = 5


@dataclass
class PageResult:
    url: str
    status_code: int
    final_url: str
    redirect_count: int
    redirect_chain: str
    content_type: str
    title: str
    meta_description: str
    h1_count: int
    html: str


@dataclass
class Issue:
    url: str
    issue_type: str
    severity: str
    details: str


def normalize_url(url: str) -> str:
    """Normalize URL for dedupe and queueing."""
    cleaned, _fragment = urldefrag(url.strip())
    parsed = urlparse(cleaned)
    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    netloc = parsed.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    normalized_query_pairs: List[Tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lower_key = key.lower()
        if lower_key.startswith(TRACKING_QUERY_PREFIXES) or lower_key in TRACKING_QUERY_EXACT:
            continue
        normalized_query_pairs.append((key, value))
    normalized_query_pairs.sort(key=lambda item: (item[0], item[1]))
    normalized_query = urlencode(normalized_query_pairs, doseq=True)
    return f"{scheme}://{netloc}{path}" + (f"?{normalized_query}" if normalized_query else "")


def is_internal(url: str, root_domain: str) -> bool:
    """Return True when URL belongs to the same host/domain."""
    parsed = urlparse(url)
    return parsed.netloc.lower() == root_domain.lower()


def extract_links(base_url: str, html: str) -> List[str]:
    """Extract and normalize absolute HTTP(S) links from page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []
    for tag in soup.find_all("a", href=True):
        absolute = urljoin(base_url, tag.get("href", ""))
        if absolute.startswith("http://") or absolute.startswith("https://"):
            links.append(normalize_url(absolute))
    return links


def split_internal_external_links(
    links: List[str],
    root_domain: str,
) -> Tuple[List[str], List[str]]:
    internal: List[str] = []
    external: List[str] = []
    for link in links:
        if is_internal(link, root_domain):
            internal.append(link)
        else:
            external.append(link)
    return internal, external


def should_skip_internal_url(url: str) -> bool:
    """Skip non-crawl-safe URLs like logout/download/calendar paths."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    return any(keyword in path for keyword in SKIP_PATH_KEYWORDS)


def parse_page_fields(html: str) -> Tuple[str, str, int]:
    """Read title, meta description, and H1 count from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = meta_tag.get("content", "").strip() if meta_tag else ""
    h1_count = len(soup.find_all("h1"))
    return title, meta_description, h1_count


def fetch_robots(root_url: str, user_agent: str) -> Optional[RobotFileParser]:
    """Fetch and parse robots.txt for the given root URL. Returns None on failure.

    Uses httpx with the crawler's user-agent instead of urllib (which sends
    ``Python-urllib/X.Y`` and gets blocked by Cloudflare Browser Integrity Check).
    """
    parsed = urlparse(root_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = httpx.get(
            robots_url,
            headers={**DEFAULT_HEADERS, "User-Agent": user_agent},
            timeout=10,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.parse(resp.text.splitlines())
        return rp
    except Exception:
        return None


def fetch_page(client: httpx.Client, url: str) -> Optional[PageResult]:
    """Fetch one URL with a fallback request profile for WAF-sensitive sites."""
    try:
        response = client.get(url)
        if response.status_code in {403, 406, 415, 429}:
            # Some sites/WAFs reject "crawler-like" requests unless headers look browser-like.
            response = client.get(
                url,
                headers={
                    "Accept": "*/*",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                },
            )
    except httpx.HTTPError:
        return None

    history_codes = [r.status_code for r in response.history]
    redirect_chain = " -> ".join([str(c) for c in history_codes + [response.status_code]])
    content_type = response.headers.get("content-type", "")
    html = response.text if "text/html" in content_type.lower() else ""
    title, meta_description, h1_count = parse_page_fields(html) if html else ("", "", 0)

    return PageResult(
        url=url,
        status_code=response.status_code,
        final_url=str(response.url),
        redirect_count=len(response.history),
        redirect_chain=redirect_chain,
        content_type=content_type,
        title=title,
        meta_description=meta_description,
        h1_count=h1_count,
        html=html,
    )


CHALLENGE_TITLES = {"one moment, please...", "just a moment...", "attention required"}


def fetch_page_browser(context: BrowserContext, url: str, timeout: float) -> Optional[PageResult]:
    """Fetch one URL using a headless browser to bypass JS challenges."""
    page = context.new_page()
    Stealth().apply_stealth_sync(page)
    try:
        response = page.goto(url, timeout=timeout * 1000)
        if response is None:
            return None

        # If we hit a bot-protection challenge page, wait for it to resolve.
        if page.title().lower().strip() in CHALLENGE_TITLES:
            try:
                titles_js = " && ".join(
                    f'document.title.toLowerCase().trim() !== "{t}"'
                    for t in CHALLENGE_TITLES
                )
                page.wait_for_function(titles_js, timeout=30000)
            except Exception:
                pass  # Proceed with whatever we have.

        # Let the page settle after challenge resolution.
        page.wait_for_timeout(2000)

        status_code = response.status
        final_url = page.url
        html = page.content()
        content_type = response.headers.get("content-type", "")

        # Playwright follows redirects automatically; redirect details are not
        # exposed the same way as httpx, so we infer from URL change.
        redirected = normalize_url(url) != normalize_url(final_url)
        redirect_count = 1 if redirected else 0
        redirect_chain = f"{status_code}" if not redirected else f"-> {status_code}"

        title, meta_description, h1_count = parse_page_fields(html) if html else ("", "", 0)

        return PageResult(
            url=url,
            status_code=status_code,
            final_url=final_url,
            redirect_count=redirect_count,
            redirect_chain=redirect_chain,
            content_type=content_type,
            title=title,
            meta_description=meta_description,
            h1_count=h1_count,
            html=html,
        )
    except Exception:
        return None
    finally:
        page.close()


def detect_issues(
    result: PageResult,
    incoming_broken_links: List[str],
    referrers: List[str],
) -> List[Issue]:
    """Convert a crawled page result into normalized issue rows."""
    issues: List[Issue] = []
    status = result.status_code

    if 500 <= status <= 599:
        details = f"Returned status {status}"
        if referrers:
            details += f" | Found on: {', '.join(sorted(referrers)[:5])}"
        issues.append(Issue(result.url, "http_5xx", "critical", details))
    elif 400 <= status <= 499:
        details = f"Returned status {status}"
        if referrers:
            details += f" | Found on: {', '.join(sorted(referrers)[:5])}"
        issues.append(Issue(result.url, "http_4xx", "high", details))

    if result.redirect_count > 0:
        severity = "medium" if result.redirect_count == 1 else "high"
        issues.append(
            Issue(
                result.url,
                "redirect",
                severity,
                f"Redirect chain ({result.redirect_count}): {result.redirect_chain}",
            )
        )

    if status == 200 and "text/html" in result.content_type.lower():
        title_len = len(result.title)
        meta_len = len(result.meta_description)
        if not result.title:
            issues.append(Issue(result.url, "meta_title_missing", "medium", "Missing <title>"))
        elif title_len < 15 or title_len > 65:
            issues.append(
                Issue(
                    result.url,
                    "meta_title_length",
                    "low",
                    f"Title length {title_len} (recommended 15-65)",
                )
            )

        if not result.meta_description:
            issues.append(
                Issue(result.url, "meta_description_missing", "medium", "Missing meta description")
            )
        elif meta_len < 50 or meta_len > 160:
            issues.append(
                Issue(
                    result.url,
                    "meta_description_length",
                    "low",
                    f"Description length {meta_len} (recommended 50-160)",
                )
            )

        if result.h1_count == 0:
            issues.append(Issue(result.url, "h1_missing", "medium", "No <h1> found"))
        elif result.h1_count > 1:
            issues.append(Issue(result.url, "h1_multiple", "low", f"Found {result.h1_count} <h1> tags"))

    for broken in incoming_broken_links:
        issues.append(Issue(result.url, "internal_broken_link", "high", f"Links to broken URL {broken}"))

    return issues


def init_db(conn: sqlite3.Connection) -> None:
    """Create SQLite tables used for run history and findings."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crawl_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            root_url TEXT NOT NULL,
            pages_crawled INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            issue_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            details TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES crawl_runs(id)
        )
        """
    )
    conn.commit()


def save_run(conn: sqlite3.Connection, root_url: str, pages_crawled: int) -> int:
    """Insert a crawl run and return generated run id."""
    started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        "INSERT INTO crawl_runs (started_at, root_url, pages_crawled) VALUES (?, ?, ?)",
        (started_at, root_url, pages_crawled),
    )
    conn.commit()
    return int(cur.lastrowid)


def save_issues(conn: sqlite3.Connection, run_id: int, issues: Iterable[Issue]) -> None:
    """Persist all issues for a run in one batch."""
    created_at = time.strftime("%Y-%m-%d %H:%M:%S")
    rows = [(run_id, i.url, i.issue_type, i.severity, i.details, created_at) for i in issues]
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO issues (run_id, url, issue_type, severity, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


def write_csv(path: str, issues: List[Issue]) -> None:
    """Write issues to CSV for quick sharing and filtering."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "issue_type", "severity", "details"])
        for i in issues:
            writer.writerow([i.url, i.issue_type, i.severity, i.details])


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_html_report(path: str, root_url: str, results: List[PageResult], issues: List[Issue], external_link_notes: Optional[set] = None) -> None:
    """Write a self-contained HTML report with tabs, grouped external links, and sortable columns."""
    severity_colors = {
        "critical": "#dc3545",
        "high": "#fd7e14",
        "medium": "#ffc107",
        "low": "#17a2b8",
        "info": "#6c757d",
    }

    # Count unique pages (200 OK HTML responses)
    unique_pages = [r for r in results if r.status_code == 200 and "text/html" in r.content_type.lower()]
    severity_counts = Counter([i.severity for i in issues])

    # Categorize issues into tabs
    tab_404 = []
    tab_5xx = []
    tab_other_4xx = []
    tab_seo = []
    tab_fetch_failed = []
    tab_redirects = []

    # Group external links: {external_url: [source_pages]}
    external_links_grouped: dict = {}
    for source_url, ext_url in (external_link_notes or set()):
        external_links_grouped.setdefault(ext_url, []).append(source_url)

    for i in issues:
        if i.issue_type == "fetch_failed":
            tab_fetch_failed.append(i)
        elif i.issue_type == "redirect":
            tab_redirects.append(i)
        elif i.issue_type == "http_5xx":
            tab_5xx.append(i)
        elif i.issue_type == "http_4xx":
            status_in_details = "404" in i.details
            if status_in_details:
                tab_404.append(i)
            else:
                tab_other_4xx.append(i)
        elif i.issue_type in {
            "meta_title_missing", "meta_title_length",
            "meta_description_missing", "meta_description_length",
            "h1_missing", "h1_multiple", "internal_broken_link",
        }:
            tab_seo.append(i)

    def _issue_table(issue_list: List[Issue], table_id: str) -> str:
        if not issue_list:
            return '<p class="empty">No issues found.</p>'
        rows = []
        for i in issue_list:
            color = severity_colors.get(i.severity, "#6c757d")
            rows.append(
                f"<tr>"
                f'<td><a href="{i.url}" target="_blank">{_esc(i.url)}</a></td>'
                f"<td>{i.issue_type}</td>"
                f'<td><span class="badge" style="background:{color}">{i.severity}</span></td>'
                f"<td>{_esc(i.details)}</td>"
                f"</tr>"
            )
        return f"""<table class="sortable" id="{table_id}">
      <thead><tr>
        <th onclick="sortTable('{table_id}',0)">URL</th>
        <th onclick="sortTable('{table_id}',1)">Issue Type</th>
        <th onclick="sortTable('{table_id}',2)">Severity</th>
        <th onclick="sortTable('{table_id}',3)">Details</th>
      </tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>"""

    def _external_links_table() -> str:
        if not external_links_grouped:
            return '<p class="empty">No external links found.</p>'
        rows = []
        for ext_url in sorted(external_links_grouped.keys()):
            sources = sorted(set(external_links_grouped[ext_url]))
            source_list = ", ".join(f'<a href="{s}" target="_blank">{_esc(s)}</a>' for s in sources[:10])
            if len(sources) > 10:
                source_list += f" ... and {len(sources) - 10} more"
            rows.append(
                f"<tr>"
                f'<td><a href="{ext_url}" target="_blank">{_esc(ext_url)}</a></td>'
                f"<td>{len(sources)}</td>"
                f"<td>{source_list}</td>"
                f"</tr>"
            )
        return f"""<table class="sortable" id="extTable">
      <thead><tr>
        <th onclick="sortTable('extTable',0)">External URL</th>
        <th onclick="sortTable('extTable',1)">Found on # pages</th>
        <th>Source pages</th>
      </tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>"""

    # Build tab definitions: (id, label, count, content)
    tabs = [
        ("tab-404", f"404 ({len(tab_404)})", _issue_table(tab_404, "tbl404")),
        ("tab-5xx", f"5xx ({len(tab_5xx)})", _issue_table(tab_5xx, "tbl5xx")),
        ("tab-4xx", f"Other 4xx ({len(tab_other_4xx)})", _issue_table(tab_other_4xx, "tbl4xx")),
        ("tab-seo", f"SEO Issues ({len(tab_seo)})", _issue_table(tab_seo, "tblSeo")),
        ("tab-redirects", f"Redirects ({len(tab_redirects)})", _issue_table(tab_redirects, "tblRedir")),
        ("tab-failed", f"Fetch Failed ({len(tab_fetch_failed)})", _issue_table(tab_fetch_failed, "tblFail")),
        ("tab-ext", f"External Links ({len(external_links_grouped)})", _external_links_table()),
    ]

    tab_buttons = []
    tab_panels = []
    for idx, (tid, label, content) in enumerate(tabs):
        active_cls = " active" if idx == 0 else ""
        tab_buttons.append(f'<button class="tab-btn{active_cls}" onclick="openTab(\'{tid}\')">{label}</button>')
        display = "block" if idx == 0 else "none"
        tab_panels.append(f'<div class="tab-panel" id="{tid}" style="display:{display}">{content}</div>')

    # Summary
    summary_items = [
        f"<li><strong>Pages crawled:</strong> {len(results)}</li>",
        f"<li><strong>Unique pages (200 OK):</strong> {len(unique_pages)}</li>",
        f"<li><strong>Issues:</strong> {len(issues)}</li>",
        f"<li><strong>Unique external links:</strong> {len(external_links_grouped)}</li>",
    ]
    for sev in ["critical", "high", "medium", "low"]:
        count = severity_counts.get(sev, 0)
        if count > 0:
            color = severity_colors[sev]
            summary_items.append(f'<li><span class="badge" style="background:{color}">{sev}</span> {count}</li>')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CrawlyCat Report - {root_url}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #f5f5f5; color: #333; padding: 20px; }}
  .container {{ max-width: 1400px; margin: 0 auto; }}
  h1 {{ font-size: 1.6em; margin-bottom: 4px; }}
  .subtitle {{ color: #666; margin-bottom: 20px; }}
  .summary {{ background: #fff; border-radius: 8px; padding: 16px 20px;
              margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .summary ul {{ list-style: none; display: flex; flex-wrap: wrap; gap: 16px; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px;
            color: #fff; font-size: 0.85em; font-weight: 600; }}
  .tab-bar {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 0; }}
  .tab-btn {{ padding: 8px 16px; border: 1px solid #ddd; border-bottom: none;
              background: #e9ecef; cursor: pointer; border-radius: 6px 6px 0 0;
              font-size: 0.9em; font-weight: 500; }}
  .tab-btn.active {{ background: #fff; border-bottom: 1px solid #fff; margin-bottom: -1px; font-weight: 700; }}
  .tab-btn:hover {{ background: #f8f9fa; }}
  .tab-panel {{ background: #fff; border: 1px solid #ddd; border-radius: 0 8px 8px 8px;
                padding: 16px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .empty {{ color: #999; padding: 20px; text-align: center; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #343a40; color: #fff; padding: 10px 12px; text-align: left;
       cursor: pointer; user-select: none; }}
  th:hover {{ background: #495057; }}
  th::after {{ content: '\\2195'; margin-left: 6px; font-size: 0.8em; opacity: 0.5; }}
  th.asc::after {{ content: '\\2191'; opacity: 1; }}
  th.desc::after {{ content: '\\2193'; opacity: 1; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #eee; word-break: break-word; }}
  tr:hover {{ background: #f8f9fa; }}
  a {{ color: #0066cc; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .footer {{ text-align: center; color: #999; font-size: 0.85em; margin-top: 24px; }}
</style>
</head>
<body>
<div class="container">
  <h1>CrawlyCat Report</h1>
  <p class="subtitle">{_esc(root_url)} &mdash; {time.strftime('%Y-%m-%d %H:%M:%S')}</p>

  <div class="summary">
    <ul>{''.join(summary_items)}</ul>
  </div>

  <div class="tab-bar">
    {''.join(tab_buttons)}
  </div>
  {''.join(tab_panels)}

  <p class="footer">Generated by <a href="https://github.com/bhageria/crawlycat">CrawlyCat</a></p>
</div>

<script>
function openTab(id) {{
  document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(id).style.display = 'block';
  event.target.classList.add('active');
}}
function sortTable(tableId, col) {{
  const table = document.getElementById(tableId);
  const thead = table.querySelector('thead');
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const th = thead.querySelectorAll('th')[col];
  const asc = !th.classList.contains('asc');
  thead.querySelectorAll('th').forEach(h => h.classList.remove('asc','desc'));
  th.classList.add(asc ? 'asc' : 'desc');
  const severityOrder = {{critical:0, high:1, medium:2, low:3, info:4}};
  rows.sort((a, b) => {{
    let av = a.cells[col].textContent.trim().toLowerCase();
    let bv = b.cells[col].textContent.trim().toLowerCase();
    if (th.textContent.trim().startsWith('Severity')) {{ av = severityOrder[av] ?? 5; bv = severityOrder[bv] ?? 5; return asc ? av - bv : bv - av; }}
    if (th.textContent.trim().startsWith('Found on')) {{ return asc ? parseInt(av) - parseInt(bv) : parseInt(bv) - parseInt(av); }}
    return asc ? av.localeCompare(bv) : bv.localeCompare(av);
  }});
  rows.forEach(r => tbody.appendChild(r));
}}
</script>
</body>
</html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def crawl(
    root_url: str,
    max_pages: int,
    timeout: float,
    user_agent: str,
    progress_callback: Optional[Callable[[str, str], None]] = None,
    fast: bool = False,
    stop_event: Optional[threading.Event] = None,
    delay: float = DEFAULT_DELAY,
    respect_robots: bool = True,
) -> Tuple[List[PageResult], List[Issue], set]:
    """Crawl internal pages up to max_pages and return results + issues.

    When fast=False (default), uses a headless browser (Playwright) to render
    JavaScript and bypass bot-protection challenge pages.
    When fast=True, uses raw HTTP requests (httpx) which is faster but cannot
    handle JS-rendered pages or bot challenges.
    If stop_event is set, the crawl stops after the current page and returns
    partial results collected so far.
    delay controls seconds to wait between requests (default 0.5).
    respect_robots controls whether robots.txt rules are honored (default True).
    """
    root = normalize_url(root_url)
    root_domain = urlparse(root).netloc

    robots: Optional[RobotFileParser] = None
    if respect_robots:
        robots = fetch_robots(root, user_agent)
        if robots and not robots.can_fetch(user_agent, root):
            if progress_callback:
                progress_callback(root, "blocked by robots.txt")
            return [], [Issue(root, "robots_blocked", "info", "Root URL disallowed by robots.txt")]

    visited: Set[str] = set()
    queued: Set[str] = {root}
    queue = deque([root])
    results: List[PageResult] = []
    all_issues: List[Issue] = []
    external_link_notes: Set[Tuple[str, str]] = set()
    link_sources = defaultdict(set)
    skipped_internal_notes: Set[Tuple[str, str]] = set()
    query_variants_count = defaultdict(set)

    first_request = True

    def _crawl_loop(fetcher):
        nonlocal first_request
        while queue and len(visited) < max_pages:
            if stop_event and stop_event.is_set():
                break
            if not first_request and delay > 0:
                time.sleep(delay)
            first_request = False
            url = queue.popleft()
            visited.add(url)
            if progress_callback:
                progress_callback(url, "checking")

            page = fetcher(url)
            if page is None:
                all_issues.append(Issue(url, "fetch_failed", "high", "Request failed or timed out"))
                if progress_callback:
                    progress_callback(url, "fetch_failed")
                continue

            results.append(page)
            if progress_callback:
                progress_callback(url, str(page.status_code))

            if page.status_code == 200 and "text/html" in page.content_type.lower():
                found_links = extract_links(page.final_url, page.html)
                internal_links, external_links = split_internal_external_links(found_links, root_domain)

                for external in external_links:
                    external_link_notes.add((page.url, external))
                    link_sources[external].add(page.url)

                for link in internal_links:
                    link_sources[link].add(page.url)
                    base_no_query = f"{urlparse(link).scheme}://{urlparse(link).netloc}{urlparse(link).path or '/'}"
                    query_variants_count[base_no_query].add(urlparse(link).query)

                    if should_skip_internal_url(link):
                        skipped_internal_notes.add((page.url, link))
                        continue

                    if robots and not robots.can_fetch(user_agent, link):
                        skipped_internal_notes.add((page.url, link))
                        continue

                    if (
                        len(query_variants_count[base_no_query]) > MAX_QUERY_VARIANTS_PER_PATH
                        and urlparse(link).query
                    ):
                        all_issues.append(
                            Issue(
                                page.url,
                                "url_parameter_explosion_skipped",
                                "info",
                                f"Skipped crawl for {link} after {MAX_QUERY_VARIANTS_PER_PATH} query variants for {base_no_query}",
                            )
                        )
                        continue

                    if link not in visited and link not in queued and len(visited) + len(queue) < max_pages:
                        queued.add(link)
                        queue.append(link)

    if fast:
        headers = {**DEFAULT_HEADERS, "User-Agent": user_agent}
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            headers=headers,
        ) as client:
            _crawl_loop(lambda url: fetch_page(client, url))
    else:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(user_agent=user_agent)
        try:
            _crawl_loop(lambda url: fetch_page_browser(context, url, timeout))
        finally:
            context.close()
            browser.close()
            pw.stop()

    broken_targets = {r.url for r in results if 400 <= r.status_code <= 599}
    for page in results:
        incoming_broken_links: List[str] = []
        if page.status_code == 200 and "text/html" in page.content_type.lower():
            # Evaluate broken-link references after crawl once we know all bad targets.
            for link in extract_links(page.final_url, page.html):
                if link in broken_targets:
                    incoming_broken_links.append(link)
        page_referrers = list(link_sources.get(page.url, set()))
        all_issues.extend(detect_issues(page, incoming_broken_links, page_referrers))

    for source_url, skipped_url in sorted(skipped_internal_notes):
        all_issues.append(
            Issue(
                source_url,
                "internal_link_skipped_pattern",
                "info",
                f"Internal link skipped by pattern: {skipped_url}",
            )
        )

    return results, all_issues, external_link_notes


def print_summary(results: List[PageResult], issues: List[Issue]) -> None:
    """Print compact CLI summary for a crawl run."""
    status_counts = Counter([r.status_code for r in results])
    type_counts = Counter([i.issue_type for i in issues])
    print(f"Pages crawled: {len(results)}")
    print("Status counts:")
    for code, count in sorted(status_counts.items()):
        print(f"  {code}: {count}")
    print(f"Total issues: {len(issues)}")
    print("Top issue types:")
    for issue_type, count in type_counts.most_common(10):
        print(f"  {issue_type}: {count}")


def main() -> None:
    """Parse CLI args, run crawl, persist artifacts, print summary."""
    parser = argparse.ArgumentParser(description="Simple website crawler for SEO/technical checks")
    parser.add_argument("--url", required=True, help="Root URL to start crawl, e.g. https://example.com")
    parser.add_argument("--max-pages", type=int, default=200, help="Maximum pages to crawl")
    parser.add_argument("--db-path", default="crawl_history.db", help="SQLite DB path")
    parser.add_argument("--csv-out", default="issues.csv", help="CSV output path for issues")
    parser.add_argument("--html-out", default="", help="HTML report output path (e.g. report.html)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Request timeout in seconds")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="Crawler user-agent string")
    parser.add_argument("--fast", action="store_true", help="Use raw HTTP requests instead of headless browser (faster but cannot bypass JS challenges)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="Seconds to wait between requests (default 0.5)")
    args = parser.parse_args()

    results, issues, external_link_notes = crawl(
        root_url=args.url,
        max_pages=args.max_pages,
        timeout=args.timeout,
        user_agent=args.user_agent,
        fast=args.fast,
        delay=args.delay,
    )

    conn = sqlite3.connect(args.db_path)
    init_db(conn)
    run_id = save_run(conn, normalize_url(args.url), len(results))
    save_issues(conn, run_id, issues)
    conn.close()

    write_csv(args.csv_out, issues)
    if args.html_out:
        write_html_report(args.html_out, args.url, results, issues, external_link_notes)
    print_summary(results, issues)
    print(f"Run id: {run_id}")
    print(f"Issues CSV: {args.csv_out}")
    if args.html_out:
        print(f"HTML report: {args.html_out}")
    print(f"History DB: {args.db_path}")


if __name__ == "__main__":
    main()
