import csv
import os
import re
import sqlite3
import threading
import time
import tkinter as tk
import webbrowser
from collections import Counter
from tkinter import messagebox, ttk
from urllib.parse import urlparse

from .cli import (
    DEFAULT_DELAY,
    DEFAULT_USER_AGENT,
    crawl,
    init_db,
    normalize_url,
    save_issues,
    save_run,
    write_html_report,
)


class CrawlerGUI:
    """Desktop GUI wrapper around the crawler engine."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CrawlyCat - Broken Link & SEO Checker")
        self.root.geometry("980x680")

        self.worker: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.results = []
        self.issues = []
        self.issue_details_by_url = {}
        self.latest_report_path: str | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root)
        top.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(top, text="URL:").pack(side=tk.LEFT)
        self.url_var = tk.StringVar(value="https://example.com")
        ttk.Entry(top, textvariable=self.url_var, width=45).pack(side=tk.LEFT, padx=(6, 10))

        ttk.Label(top, text="Max Pages:").pack(side=tk.LEFT)
        self.max_pages_var = tk.StringVar(value="200")
        ttk.Entry(top, textvariable=self.max_pages_var, width=8).pack(side=tk.LEFT, padx=(6, 10))

        ttk.Label(top, text="Timeout:").pack(side=tk.LEFT)
        self.timeout_var = tk.StringVar(value="15")
        ttk.Entry(top, textvariable=self.timeout_var, width=8).pack(side=tk.LEFT, padx=(6, 10))

        ttk.Label(top, text="Delay:").pack(side=tk.LEFT)
        self.delay_var = tk.StringVar(value=str(DEFAULT_DELAY))
        ttk.Entry(top, textvariable=self.delay_var, width=5).pack(side=tk.LEFT, padx=(6, 10))

        self.fast_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Fast (no JS)", variable=self.fast_var).pack(side=tk.LEFT, padx=(6, 10))

        self.check_resources_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Check Resources", variable=self.check_resources_var).pack(side=tk.LEFT, padx=(6, 10))

        self.start_btn = ttk.Button(top, text="Start Crawl", command=self.start_crawl)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.stop_btn = ttk.Button(top, text="Stop", command=self.stop_crawl, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.report_btn = ttk.Button(top, text="Open Report", command=self.open_report, state=tk.DISABLED)
        self.report_btn.pack(side=tk.LEFT)

        # Second row: User-Agent
        top2 = ttk.Frame(self.root)
        top2.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Label(top2, text="User-Agent:").pack(side=tk.LEFT)
        self.ua_var = tk.StringVar(value=DEFAULT_USER_AGENT)
        ttk.Entry(top2, textvariable=self.ua_var, width=100).pack(side=tk.LEFT, padx=(6, 0), fill=tk.X, expand=True)

        main_pane = ttk.Panedwindow(self.root, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        status = ttk.LabelFrame(main_pane, text="Live Status")
        log_frame = ttk.LabelFrame(main_pane, text="Live Log")
        summary = ttk.LabelFrame(main_pane, text="Summary")
        tabs_frame = ttk.LabelFrame(main_pane, text="Status Tabs")
        details_frame = ttk.LabelFrame(main_pane, text="Selected URL Details")

        main_pane.add(status, weight=1)
        main_pane.add(log_frame, weight=2)
        main_pane.add(summary, weight=2)
        main_pane.add(tabs_frame, weight=3)
        main_pane.add(details_frame, weight=2)

        self.current_url_var = tk.StringVar(value="-")
        self.current_result_var = tk.StringVar(value="-")
        self.count_var = tk.StringVar(value="Pages: 0 | Issues: 0")

        ttk.Label(status, text="Currently checking:").grid(row=0, column=0, sticky=tk.W, padx=8, pady=4)
        ttk.Label(status, textvariable=self.current_url_var).grid(row=0, column=1, sticky=tk.W, padx=8, pady=4)
        ttk.Label(status, text="Result:").grid(row=1, column=0, sticky=tk.W, padx=8, pady=4)
        ttk.Label(status, textvariable=self.current_result_var).grid(row=1, column=1, sticky=tk.W, padx=8, pady=4)
        ttk.Label(status, textvariable=self.count_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=8, pady=4)

        self.log = tk.Text(log_frame, height=14, wrap=tk.NONE)
        self.log.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.summary_text = tk.Text(summary, height=10, wrap=tk.WORD)
        self.summary_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.status_notebook = ttk.Notebook(tabs_frame)
        self.status_notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.status_tabs = {}
        self._create_status_tabs()

        self.details_text = tk.Text(details_frame, height=8, wrap=tk.WORD)
        self.details_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def _create_status_tabs(self) -> None:
        for tab_name in ["404", "415", "5xx", "Other 4xx", "SEO Issues", "Redirects", "Fetch Failed", "External Links"]:
            frame = ttk.Frame(self.status_notebook)
            self.status_notebook.add(frame, text=tab_name)
            listbox = tk.Listbox(frame)
            listbox.pack(fill=tk.BOTH, expand=True)
            listbox.bind("<Double-1>", self._open_selected_url)
            listbox.bind("<<ListboxSelect>>", self._show_selected_details)
            self.status_tabs[tab_name] = listbox

    def _clear_status_tabs(self) -> None:
        for listbox in self.status_tabs.values():
            listbox.delete(0, tk.END)
        self.issue_details_by_url = {}
        self.details_text.delete("1.0", tk.END)

    def _open_selected_url(self, event=None) -> None:
        widget = event.widget if event else None
        if widget is None:
            return
        selection = widget.curselection()
        if not selection:
            return
        line = widget.get(selection[0])
        url = line.split("  ", 1)[-1].strip()
        if url.startswith("http://") or url.startswith("https://"):
            webbrowser.open_new_tab(url)

    def _show_selected_details(self, event=None) -> None:
        widget = event.widget if event else None
        if widget is None:
            return
        selection = widget.curselection()
        if not selection:
            return
        line = widget.get(selection[0])
        url = line.split("  ", 1)[-1].strip()
        details = self.issue_details_by_url.get(url, [])
        self.details_text.delete("1.0", tk.END)
        if not details:
            self.details_text.insert("1.0", f"URL: {url}\nNo issue details recorded.")
            return
        rendered = [f"URL: {url}", ""]
        rendered.extend([f"- {d}" for d in details])
        self.details_text.insert("1.0", "\n".join(rendered))

    def _populate_status_tabs(self) -> None:
        self._clear_status_tabs()
        for issue in self.issues:
            self.issue_details_by_url.setdefault(issue.url, []).append(
                f"{issue.issue_type} ({issue.severity}): {issue.details}"
            )

        for page in self.results:
            code = page.status_code
            line = f"{code}  {page.url}"
            if code == 404:
                self.status_tabs["404"].insert(tk.END, line)
            elif code == 415:
                self.status_tabs["415"].insert(tk.END, line)
            elif 500 <= code <= 599:
                self.status_tabs["5xx"].insert(tk.END, line)
            elif 400 <= code <= 499:
                self.status_tabs["Other 4xx"].insert(tk.END, line)

        seo_types = {
            "meta_title_missing", "meta_title_length",
            "meta_description_missing", "meta_description_length",
            "h1_missing", "h1_multiple", "internal_broken_link",
        }
        for issue in self.issues:
            if issue.issue_type == "fetch_failed":
                self.status_tabs["Fetch Failed"].insert(tk.END, f"FAIL  {issue.url}")
                self.issue_details_by_url.setdefault(issue.url, []).append(issue.details)
            elif issue.issue_type == "redirect":
                self.status_tabs["Redirects"].insert(tk.END, f"REDIR  {issue.url}")
            elif issue.issue_type in seo_types:
                self.status_tabs["SEO Issues"].insert(tk.END, f"SEO  {issue.url}")

        external_links = set()
        for source_url, ext_url in getattr(self, 'external_link_notes', set()):
            external_links.add(ext_url)
            self.issue_details_by_url.setdefault(ext_url, []).append(
                f"Found on: {source_url}"
            )

        for external_url in sorted(external_links):
            self.status_tabs["External Links"].insert(tk.END, f"OUT  {external_url}")

    def _append_log(self, text: str) -> None:
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)

    def _on_progress(self, url: str, status: str) -> None:
        # Marshal worker-thread updates to Tk main thread.
        self.root.after(0, self._update_progress_ui, url, status)

    def _update_progress_ui(self, url: str, status: str) -> None:
        self.current_url_var.set(url)
        self.current_result_var.set(status)
        self._append_log(f"{status:>12}  {url}")

    def start_crawl(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("In Progress", "A crawl is already running.")
            return

        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Input Error", "Please provide a URL.")
            return

        try:
            max_pages = int(self.max_pages_var.get().strip())
            timeout = float(self.timeout_var.get().strip())
            delay = float(self.delay_var.get().strip())
        except ValueError:
            messagebox.showerror("Input Error", "Max Pages, Timeout, and Delay must be numeric.")
            return

        self.log.delete("1.0", tk.END)
        self.summary_text.delete("1.0", tk.END)
        self.current_url_var.set("-")
        self.current_result_var.set("-")
        self.count_var.set("Pages: 0 | Issues: 0")
        self._clear_status_tabs()
        self.stop_event.clear()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        fast = self.fast_var.get()
        check_resources = self.check_resources_var.get()

        self.worker = threading.Thread(
            target=self._run_crawl,
            args=(url, max_pages, timeout, fast, delay, check_resources),
            daemon=True,
        )
        self.worker.start()

    @staticmethod
    def _report_filename(url: str) -> str:
        """Generate a report filename like report_example_com_2026-03-22_143015.html."""
        domain = urlparse(url).netloc or "unknown"
        domain = re.sub(r"[^a-zA-Z0-9]", "_", domain).strip("_")
        timestamp = time.strftime("%Y-%m-%d_%H%M%S")
        return f"report_{domain}_{timestamp}.html"

    def open_report(self) -> None:
        if self.latest_report_path and os.path.isfile(self.latest_report_path):
            webbrowser.open_new_tab(f"file:///{os.path.abspath(self.latest_report_path)}")
        else:
            messagebox.showinfo("No Report", "No report available yet. Run a crawl first.")

    def stop_crawl(self) -> None:
        self.stop_event.set()
        self.stop_btn.config(state=tk.DISABLED)
        self._append_log("--- Stop requested, finishing current page... ---")

    def _run_crawl(self, url: str, max_pages: int, timeout: float, fast: bool = False, delay: float = DEFAULT_DELAY, check_resources: bool = False) -> None:
        stopped = False
        try:
            results, issues, external_link_notes = crawl(
                root_url=url,
                max_pages=max_pages,
                timeout=timeout,
                user_agent=self.ua_var.get().strip() or DEFAULT_USER_AGENT,
                progress_callback=self._on_progress,
                fast=fast,
                stop_event=self.stop_event,
                delay=delay,
                check_resources=check_resources,
            )
            self.results = results
            self.issues = issues
            self.external_link_notes = external_link_notes
            stopped = self.stop_event.is_set()

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

            report_path = self._report_filename(url)
            write_html_report(report_path, url, results, issues, external_link_notes)
            self.latest_report_path = report_path

            self.root.after(0, self._render_summary, run_id, stopped, report_path)
        except Exception as exc:
            self.root.after(0, lambda: messagebox.showerror("Crawl Failed", str(exc)))
        finally:
            self.root.after(0, self._on_crawl_finished)

    def _on_crawl_finished(self) -> None:
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        if self.latest_report_path and os.path.isfile(self.latest_report_path):
            self.report_btn.config(state=tk.NORMAL)

    def _render_summary(self, run_id: int, stopped: bool = False, report_path: str = "") -> None:
        """Render post-run rollup and status tabs."""
        status_counts = Counter([r.status_code for r in self.results])
        issue_counts = Counter([i.issue_type for i in self.issues])
        external_link_notes = getattr(self, 'external_link_notes', set())
        external_mentions = len(external_link_notes)
        unique_external_urls = {ext_url for _, ext_url in external_link_notes}

        status_label = f"Pages: {len(self.results)} | Issues: {len(self.issues)}"
        if stopped:
            status_label += " (stopped)"
        self.count_var.set(status_label)

        lines = [
            f"Run id: {run_id}",
            f"Status: {'STOPPED by user' if stopped else 'completed'}",
            f"Pages crawled: {len(self.results)}",
            f"Total issues: {len(self.issues)}",
            "",
            "Status counts:",
        ]
        for code, count in sorted(status_counts.items()):
            lines.append(f"  {code}: {count}")

        lines.append("")
        lines.append("External links:")
        lines.append(f"  mentions: {external_mentions}")
        lines.append(f"  unique: {len(unique_external_urls)}")

        lines.append("")
        lines.append("Issue types:")
        for issue_type, count in issue_counts.most_common():
            lines.append(f"  {issue_type}: {count}")

        lines.append("")
        lines.append("Saved files:")
        lines.append("  issues.csv")
        if report_path:
            lines.append(f"  {report_path}")
        lines.append("  crawl_history.db")

        self.summary_text.insert("1.0", "\n".join(lines))
        self._populate_status_tabs()


def main() -> None:
    root = tk.Tk()
    app = CrawlerGUI(root)
    _ = app
    root.mainloop()


if __name__ == "__main__":
    main()
