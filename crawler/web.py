"""Web UI for CrawlyCat — Flask app with SSE live progress."""

import csv
import io
import json
import os
import re
import sqlite3
import threading
import time
import webbrowser
from collections import Counter
from queue import Empty, Queue
from urllib.parse import urlparse

from flask import Flask, Response, jsonify, render_template, request, send_from_directory

from .cli import (
    DEFAULT_DELAY,
    DEFAULT_USER_AGENT,
    Issue,
    PageResult,
    crawl,
    init_db,
    normalize_url,
    save_issues,
    save_run,
    write_html_report,
)

app = Flask(__name__)

# ---------- global crawl state (single-user tool) ----------
_crawl_lock = threading.Lock()
_stop_event: threading.Event | None = None
_crawl_thread: threading.Thread | None = None


@app.route("/")
def index():
    return render_template("index.html", default_user_agent=DEFAULT_USER_AGENT)


@app.route("/api/crawl")
def crawl_sse():
    """Start a crawl and stream progress via Server-Sent Events."""
    global _stop_event, _crawl_thread

    if not _crawl_lock.acquire(blocking=False):
        return jsonify({"error": "A crawl is already running"}), 409

    url = request.args.get("url", "").strip()
    if not url:
        _crawl_lock.release()
        return jsonify({"error": "URL is required"}), 400

    max_pages = int(request.args.get("max_pages", 200))
    timeout = float(request.args.get("timeout", 15))
    delay = float(request.args.get("delay", DEFAULT_DELAY))
    fast = request.args.get("fast", "false").lower() == "true"
    check_resources = request.args.get("check_resources", "false").lower() == "true"
    user_agent = request.args.get("user_agent", "").strip() or DEFAULT_USER_AGENT

    _stop_event = threading.Event()
    progress_queue: Queue = Queue()

    def progress_callback(page_url: str, status: str):
        progress_queue.put(("progress", page_url, status))

    def crawl_worker():
        try:
            results, issues, external_link_notes = crawl(
                root_url=url,
                max_pages=max_pages,
                timeout=timeout,
                user_agent=user_agent,
                progress_callback=progress_callback,
                fast=fast,
                stop_event=_stop_event,
                delay=delay,
                check_resources=check_resources,
            )
            stopped = _stop_event.is_set()

            # Save outputs
            conn = sqlite3.connect("crawl_history.db")
            init_db(conn)
            run_id = save_run(conn, normalize_url(url), len(results))
            save_issues(conn, run_id, issues)
            conn.close()

            with open("issues.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["url", "issue_type", "severity", "details"])
                for i in issues:
                    writer.writerow([i.url, i.issue_type, i.severity, i.details])

            report_path = _report_filename(url)
            write_html_report(report_path, url, results, issues, external_link_notes)

            # Build summary
            summary = _build_summary(run_id, results, issues, stopped, report_path, external_link_notes)
            tabs = _build_tabs(results, issues, external_link_notes)

            progress_queue.put(("complete", summary, tabs))
        except Exception as exc:
            progress_queue.put(("error", str(exc), None))
        finally:
            _crawl_lock.release()

    _crawl_thread = threading.Thread(target=crawl_worker, daemon=True)
    _crawl_thread.start()

    def generate():
        while True:
            try:
                msg = progress_queue.get(timeout=1)
            except Empty:
                # SSE keepalive
                yield ":\n\n"
                continue

            if msg[0] == "progress":
                data = json.dumps({"type": "progress", "url": msg[1], "status": msg[2]})
                yield f"data: {data}\n\n"
            elif msg[0] == "complete":
                data = json.dumps({"type": "complete", "summary": msg[1], "tabs": msg[2]})
                yield f"data: {data}\n\n"
                return
            elif msg[0] == "error":
                data = json.dumps({"type": "error", "message": msg[1]})
                yield f"data: {data}\n\n"
                return

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/stop", methods=["POST"])
def stop_crawl():
    global _stop_event
    if _stop_event:
        _stop_event.set()
        return jsonify({"status": "stopping"})
    return jsonify({"status": "no crawl running"}), 404


@app.route("/api/report/<path:filename>")
def serve_report(filename):
    safe = re.sub(r"[^a-zA-Z0-9._-]", "", filename)
    return send_from_directory(os.getcwd(), safe)


# ---------- helpers ----------

def _report_filename(url: str) -> str:
    domain = urlparse(url).netloc or "unknown"
    domain = re.sub(r"[^a-zA-Z0-9]", "_", domain).strip("_")
    timestamp = time.strftime("%Y-%m-%d_%H%M%S")
    return f"report_{domain}_{timestamp}.html"


def _build_summary(run_id, results, issues, stopped, report_path, external_link_notes=None):
    status_counts = Counter(r.status_code for r in results)
    issue_counts = Counter(i.issue_type for i in issues)

    external_link_notes = external_link_notes or set()
    unique_external = {ext_url for _, ext_url in external_link_notes}

    return {
        "run_id": run_id,
        "stopped": stopped,
        "pages_crawled": len(results),
        "total_issues": len(issues),
        "status_counts": dict(sorted(status_counts.items())),
        "issue_counts": dict(issue_counts.most_common()),
        "external_mentions": len(external_link_notes),
        "unique_external": len(unique_external),
        "report_path": report_path,
        "files": ["issues.csv", report_path, "crawl_history.db"],
    }


def _build_tabs(results, issues, external_link_notes=None):
    seo_types = {
        "meta_title_missing", "meta_title_length",
        "meta_description_missing", "meta_description_length",
        "h1_missing", "h1_multiple", "internal_broken_link",
    }
    tabs = {
        "404": [],
        "415": [],
        "5xx": [],
        "Other 4xx": [],
        "SEO Issues": [],
        "Broken Resources": [],
        "Redirects": [],
        "Fetch Failed": [],
        "External Links": [],
    }
    issue_details = {}

    for issue in issues:
        issue_details.setdefault(issue.url, []).append(
            f"{issue.issue_type} ({issue.severity}): {issue.details}"
        )

    for page in results:
        code = page.status_code
        entry = {"code": code, "url": page.url}
        if code == 404:
            tabs["404"].append(entry)
        elif code == 415:
            tabs["415"].append(entry)
        elif 500 <= code <= 599:
            tabs["5xx"].append(entry)
        elif 400 <= code <= 499:
            tabs["Other 4xx"].append(entry)

    for issue in issues:
        if issue.issue_type == "fetch_failed":
            tabs["Fetch Failed"].append({"code": "FAIL", "url": issue.url})
        elif issue.issue_type == "redirect":
            tabs["Redirects"].append({"code": "REDIR", "url": issue.url, "details": issue.details})
        elif issue.issue_type.startswith("resource_"):
            # Extract status code from type like "resource_404" or use "FAIL"
            res_code = issue.issue_type.replace("resource_", "").upper()
            if res_code == "FETCH_FAILED":
                res_code = "FAIL"
            tabs["Broken Resources"].append({"code": res_code, "url": issue.details.split(": ", 1)[-1] if ": " in issue.details else issue.url})
            issue_details.setdefault(issue.details.split(": ", 1)[-1] if ": " in issue.details else issue.url, []).append(
                f"Found on: {issue.url}"
            )
        elif issue.issue_type in seo_types:
            tabs["SEO Issues"].append({"code": "SEO", "url": issue.url})

    external_links = set()
    for source_url, ext_url in (external_link_notes or set()):
        external_links.add(ext_url)
        issue_details.setdefault(ext_url, []).append(f"Found on: {source_url}")

    for ext_url in sorted(external_links):
        tabs["External Links"].append({"code": "OUT", "url": ext_url})

    return {"tabs": tabs, "issue_details": issue_details}


def main(port=5000):
    """Start the web UI server and open the browser."""
    print(f"CrawlyCat Web UI starting at http://127.0.0.1:{port}")
    threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    app.run(host="127.0.0.1", port=port, threaded=True)


if __name__ == "__main__":
    main()
