"""
main.py — News Aggregator & Visualisation Tool
Tkinter GUI entry point. Imports NewsAPIClient, WebScraping,
FrequentKeywords, and Visualiser. Handles caching and threading.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import json
import os
import hashlib
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

#Local classes made for the news aggregator
from news_api_client import NewsAPIClient
from web_scraper import WebScraping
from keyword_extractor import FrequentKeywords
from visualiser import Visualiser

# Constant values
NEWS_API_KEY = "6fbcc105837b458fb866d265fba9d767"
CATEGORIES = ["business", "entertainment", "general", "health", "science", "sports", "technology"]
CACHE_DIR = ".cache"
CACHE_TTL_HOURS = 6          # API cache expires after 6 hours
SCRAPE_CACHE_FILE = os.path.join(CACHE_DIR, "scrape_cache.json")
API_CACHE_FILE = os.path.join(CACHE_DIR, "api_cache.json")


#Cache helpers

def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_key(categories: list[str]) -> str:
    """Deterministic key based on sorted category list."""
    return hashlib.md5(",".join(sorted(categories)).encode()).hexdigest()


def load_api_cache(categories: list[str]) -> pd.DataFrame | None:
    """Return cached DataFrame if present and not expired, else None."""
    _ensure_cache_dir()
    if not os.path.exists(API_CACHE_FILE):
        return None
    try:
        with open(API_CACHE_FILE, "r") as f:
            store = json.load(f)
        key = _cache_key(categories)
        entry = store.get(key)
        if not entry:
            return None
        saved_at = datetime.fromisoformat(entry["saved_at"])
        if datetime.now() - saved_at > timedelta(hours=CACHE_TTL_HOURS):
            return None          # expired
        df = pd.DataFrame(entry["records"])
        # Restore bool column
        if "scraping_available" in df.columns:
            df["scraping_available"] = df["scraping_available"].astype(bool)
        return df
    except Exception:
        return None


def save_api_cache(categories: list[str], df: pd.DataFrame):
    _ensure_cache_dir()
    store = {}
    if os.path.exists(API_CACHE_FILE):
        try:
            with open(API_CACHE_FILE, "r") as f:
                store = json.load(f)
        except Exception:
            pass
    key = _cache_key(categories)
    store[key] = {
        "saved_at": datetime.now().isoformat(),
        "records": json.loads(df.to_json(orient="records"))
    }
    with open(API_CACHE_FILE, "w") as f:
        json.dump(store, f, indent=2)


def load_scrape_cache() -> dict:
    """Return {url: scraped_text | None} dict."""
    _ensure_cache_dir()
    if not os.path.exists(SCRAPE_CACHE_FILE):
        return {}
    try:
        with open(SCRAPE_CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_scrape_cache(cache: dict):
    _ensure_cache_dir()
    with open(SCRAPE_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


#MAIN APPLICATION WINDOW

class NewsAggregatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("News Aggregator & Visualisation Tool")
        self.geometry("1100x780")
        self.minsize(900, 650)
        self.configure(bg="#1a1a2e")

        # ── App state ─────────────────────────────────────────────────────────
        self.articles_df: pd.DataFrame = pd.DataFrame()
        self.filtered_df: pd.DataFrame = pd.DataFrame()
        self.news_client = NewsAPIClient(NEWS_API_KEY)
        self.scraper = WebScraping()
        self.keyword_extractor = FrequentKeywords()
        self.visualiser = Visualiser()
        self.scrape_cache: dict = load_scrape_cache()

        # ── Category checkbox vars ────────────────────────────────────────────
        self.cat_vars: dict[str, tk.BooleanVar] = {
            cat: tk.BooleanVar(value=True) for cat in CATEGORIES
        }

        # ── Filter state ──────────────────────────────────────────────────────
        self.filter_category = tk.StringVar(value="All")
        self.max_display = tk.StringVar(value="10")

        self._build_styles()
        self._build_ui()

    # ── Styles ────────────────────────────────────────────────────────────────

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        bg        = "#1a1a2e"
        panel     = "#16213e"
        accent    = "#0f3460"
        highlight = "#e94560"
        text_col  = "#eaeaea"
        muted     = "#8892a4"

        style.configure("TFrame",       background=bg)
        style.configure("Panel.TFrame", background=panel)
        style.configure("TLabel",       background=bg,    foreground=text_col, font=("Helvetica", 10))
        style.configure("Panel.TLabel", background=panel, foreground=text_col, font=("Helvetica", 10))
        style.configure("Muted.TLabel", background=panel, foreground=muted,    font=("Helvetica", 9))
        style.configure("Title.TLabel", background=bg,    foreground=text_col, font=("Helvetica", 13, "bold"))
        style.configure("Count.TLabel", background=panel, foreground=highlight, font=("Helvetica", 22, "bold"))

        style.configure("Accent.TButton",
            background=highlight, foreground="#ffffff",
            font=("Helvetica", 10, "bold"), relief="flat", padding=(12, 6))
        style.map("Accent.TButton",
            background=[("active", "#c73652"), ("disabled", "#555")])

        style.configure("Secondary.TButton",
            background=accent, foreground=text_col,
            font=("Helvetica", 10), relief="flat", padding=(10, 5))
        style.map("Secondary.TButton",
            background=[("active", "#1a5276"), ("disabled", "#333")])

        style.configure("TCheckbutton",
            background=panel, foreground=text_col, font=("Helvetica", 9))
        style.map("TCheckbutton", background=[("active", panel)])

        style.configure("TCombobox",
            fieldbackground=accent, background=accent,
            foreground=text_col, selectbackground=highlight)

        style.configure("TEntry",
            fieldbackground=accent, foreground=text_col,
            insertcolor=text_col)

        style.configure("TScrollbar", background=accent, troughcolor=bg)

        style.configure("TSeparator", background=accent)

        self._colors = {
            "bg": bg, "panel": panel, "accent": accent,
            "highlight": highlight, "text": text_col, "muted": muted
        }

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        c = self._colors

        # ── Top bar ───────────────────────────────────────────────────────────
        top_bar = tk.Frame(self, bg=c["panel"], height=50)
        top_bar.pack(fill="x", side="top")
        tk.Label(top_bar, text="📰  News Aggregator", bg=c["panel"],
                 fg=c["text"], font=("Helvetica", 14, "bold")).pack(side="left", padx=16, pady=10)
        self.status_label = tk.Label(top_bar, text="Ready", bg=c["panel"],
                                     fg=c["muted"], font=("Helvetica", 9))
        self.status_label.pack(side="right", padx=16)

        # ── Main paned layout ─────────────────────────────────────────────────
        paned = tk.PanedWindow(self, orient="horizontal", bg=c["bg"],
                               sashwidth=6, sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=8, pady=8)

        left  = self._build_left_panel(paned)
        right = self._build_right_panel(paned)

        paned.add(left,  minsize=280)
        paned.add(right, minsize=520)
        paned.paneconfigure(left,  width=320)

    # ── Left panel ────────────────────────────────────────────────────────────

    def _build_left_panel(self, parent) -> tk.Frame:
        c = self._colors

        # Outer container (what the PanedWindow sees)
        outer = tk.Frame(parent, bg=c["panel"])

        # Canvas + scrollbar for vertical scrolling
        canvas = tk.Canvas(outer, bg=c["panel"], highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Inner frame that holds all the actual widgets
        frame = tk.Frame(canvas, bg=c["panel"], padx=14, pady=12)
        frame_id = canvas.create_window((0, 0), window=frame, anchor="nw")

        # Resize canvas scroll region when inner frame changes size
        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfig(frame_id, width=event.width)

        frame.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse-wheel scrolling (Windows + Linux)
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_mousewheel_linux(event):
            canvas.yview_scroll(-1 if event.num == 4 else 1, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>",   _on_mousewheel_linux)
        canvas.bind_all("<Button-5>",   _on_mousewheel_linux)

        # ── Fetch section ─────────────────────────────────────────────────────
        tk.Label(frame, text="FETCH ARTICLES", bg=c["panel"], fg=c["highlight"],
                 font=("Helvetica", 9, "bold")).pack(anchor="w")
        ttk.Separator(frame).pack(fill="x", pady=(2, 8))

        tk.Label(frame, text="Categories", bg=c["panel"], fg=c["muted"],
                 font=("Helvetica", 8)).pack(anchor="w")

        cat_grid = tk.Frame(frame, bg=c["panel"])
        cat_grid.pack(fill="x", pady=(2, 8))
        for i, cat in enumerate(CATEGORIES):
            cb = ttk.Checkbutton(cat_grid, text=cat.capitalize(),
                                 variable=self.cat_vars[cat])
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=4, pady=1)

        self.fetch_btn = ttk.Button(frame, text="Fetch Articles",
                                    style="Accent.TButton",
                                    command=self._on_fetch)
        self.fetch_btn.pack(fill="x", pady=(4, 0))

        # Article count display
        count_frame = tk.Frame(frame, bg=c["panel"])
        count_frame.pack(fill="x", pady=(10, 0))
        tk.Label(count_frame, text="Articles fetched", bg=c["panel"],
                 fg=c["muted"], font=("Helvetica", 8)).pack(anchor="w")
        self.count_label = tk.Label(count_frame, text="—", bg=c["panel"],
                                    fg=c["highlight"], font=("Helvetica", 26, "bold"))
        self.count_label.pack(anchor="w")

        # Cache indicator
        self.cache_label = tk.Label(frame, text="", bg=c["panel"],
                                    fg=c["muted"], font=("Helvetica", 8))
        self.cache_label.pack(anchor="w")

        ttk.Separator(frame).pack(fill="x", pady=12)

        # ── Enrich section ────────────────────────────────────────────────────
        tk.Label(frame, text="ENRICH WITH WEB SCRAPING", bg=c["panel"],
                 fg=c["highlight"], font=("Helvetica", 9, "bold")).pack(anchor="w")
        ttk.Separator(frame).pack(fill="x", pady=(2, 8))

        self.enrich_btn = ttk.Button(frame, text="Initialise Enrichment",
                                     style="Secondary.TButton",
                                     command=self._on_enrich,
                                     state="disabled")
        self.enrich_btn.pack(fill="x")

        self.enrich_status = tk.Label(frame, text="Fetch articles first",
                                      bg=c["panel"], fg=c["muted"],
                                      font=("Helvetica", 8), wraplength=260,
                                      justify="left")
        self.enrich_status.pack(anchor="w", pady=(4, 0))

        self.enrich_progress = ttk.Progressbar(frame, mode="determinate", length=260)
        self.enrich_progress.pack(fill="x", pady=(6, 0))

        ttk.Separator(frame).pack(fill="x", pady=12)

        # ── Filter section ────────────────────────────────────────────────────
        tk.Label(frame, text="FILTER ARTICLES", bg=c["panel"], fg=c["highlight"],
                 font=("Helvetica", 9, "bold")).pack(anchor="w")
        ttk.Separator(frame).pack(fill="x", pady=(2, 8))

        tk.Label(frame, text="Category", bg=c["panel"], fg=c["muted"],
                 font=("Helvetica", 8)).pack(anchor="w")
        cat_options = ["All"] + [c.capitalize() for c in CATEGORIES]
        self.cat_combo = ttk.Combobox(frame, textvariable=self.filter_category,
                                      values=cat_options, state="readonly", width=22)
        self.cat_combo.pack(fill="x", pady=(2, 8))
        self.cat_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_filter())

        tk.Label(frame, text="Max articles to show", bg=c["panel"], fg=c["muted"],
                 font=("Helvetica", 8)).pack(anchor="w")
        max_entry = ttk.Entry(frame, textvariable=self.max_display, width=8)
        max_entry.pack(anchor="w", pady=(2, 8))
        max_entry.bind("<Return>", lambda e: self._apply_filter())

        ttk.Button(frame, text="Apply Filter", style="Secondary.TButton",
                   command=self._apply_filter).pack(fill="x")

        ttk.Separator(frame).pack(fill="x", pady=12)

        # ── Visualisation button ──────────────────────────────────────────────
        tk.Label(frame, text="VISUALISATIONS", bg=c["panel"], fg=c["highlight"],
                 font=("Helvetica", 9, "bold")).pack(anchor="w")
        ttk.Separator(frame).pack(fill="x", pady=(2, 8))

        ttk.Button(frame, text="Visualisation Options",
                   style="Accent.TButton",
                   command=self._open_visualisation_window).pack(fill="x")

        return outer

    # ── Right panel ───────────────────────────────────────────────────────────

    def _build_right_panel(self, parent) -> tk.Frame:
        c = self._colors
        frame = tk.Frame(parent, bg=c["bg"])

        # Split right panel vertically: list top, detail bottom
        top_right = tk.Frame(frame, bg=c["panel"])
        top_right.pack(fill="both", expand=True, padx=(6, 0), pady=(0, 6))

        tk.Label(top_right, text="ARTICLES", bg=c["panel"], fg=c["highlight"],
                 font=("Helvetica", 9, "bold")).pack(anchor="w", padx=10, pady=(8, 0))
        ttk.Separator(top_right).pack(fill="x", padx=10, pady=4)

        # Listbox with scrollbar
        list_frame = tk.Frame(top_right, bg=c["panel"])
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        scrollbar = tk.Scrollbar(list_frame, bg=c["accent"])
        scrollbar.pack(side="right", fill="y")

        self.article_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            bg=c["accent"], fg=c["text"],
            selectbackground=c["highlight"],
            selectforeground="#ffffff",
            font=("Helvetica", 10),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            activestyle="none"
        )
        self.article_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.article_listbox.yview)
        self.article_listbox.bind("<<ListboxSelect>>", self._on_article_select)

        # ── Detail panel ──────────────────────────────────────────────────────
        detail_outer = tk.Frame(frame, bg=c["panel"])
        detail_outer.pack(fill="both", expand=True, padx=(6, 0))

        tk.Label(detail_outer, text="ARTICLE DETAIL", bg=c["panel"], fg=c["highlight"],
                 font=("Helvetica", 9, "bold")).pack(anchor="w", padx=10, pady=(8, 0))
        ttk.Separator(detail_outer).pack(fill="x", padx=10, pady=4)

        # Meta row: title, source, author, date
        self.detail_title = tk.Label(detail_outer, text="Select an article", bg=c["panel"],
                                     fg=c["text"], font=("Helvetica", 12, "bold"),
                                     wraplength=680, justify="left")
        self.detail_title.pack(anchor="w", padx=12, pady=(0, 4))

        meta_frame = tk.Frame(detail_outer, bg=c["panel"])
        meta_frame.pack(anchor="w", padx=12, pady=(0, 4))

        self.detail_source = tk.Label(meta_frame, text="", bg=c["panel"],
                                      fg=c["highlight"], font=("Helvetica", 9, "bold"))
        self.detail_source.pack(side="left")

        self.detail_category = tk.Label(meta_frame, text="", bg=c["accent"],
                                        fg=c["text"], font=("Helvetica", 8, "bold"),
                                        padx=6, pady=2)
        self.detail_category.pack(side="left", padx=(8, 0))

        self.detail_author = tk.Label(meta_frame, text="", bg=c["panel"],
                                      fg=c["muted"], font=("Helvetica", 9))
        self.detail_author.pack(side="left", padx=(8, 0))

        self.detail_date = tk.Label(meta_frame, text="", bg=c["panel"],
                                    fg=c["muted"], font=("Helvetica", 9))
        self.detail_date.pack(side="left", padx=(8, 0))

        self.detail_url = tk.Label(detail_outer, text="", bg=c["panel"],
                                   fg="#4a9eff", font=("Helvetica", 9),
                                   cursor="hand2")
        self.detail_url.pack(anchor="w", padx=12, pady=(0, 6))
        self.detail_url.bind("<Button-1>", self._open_url)

        # Content tag indicator
        self.content_tag = tk.Label(detail_outer, text="", bg=c["panel"],
                                    fg=c["muted"], font=("Helvetica", 8))
        self.content_tag.pack(anchor="w", padx=12)

        # Scrollable content text
        self.detail_content = scrolledtext.ScrolledText(
            detail_outer,
            bg=c["accent"], fg=c["text"],
            font=("Helvetica", 10),
            relief="flat", borderwidth=0,
            wrap="word", state="disabled",
            height=10
        )
        self.detail_content.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        return frame

    # ══════════════════════════════════════════════════════════════════════════
    # Fetch logic
    # ══════════════════════════════════════════════════════════════════════════

    def _on_fetch(self):
        selected = [cat for cat, var in self.cat_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("No categories", "Please select at least one category.")
            return

        # Check cache first
        cached_df = load_api_cache(selected)
        if cached_df is not None:
            self.articles_df = cached_df
            self._post_fetch(from_cache=True)
            return

        self.fetch_btn.config(state="disabled")
        self._set_status("Fetching articles…")
        threading.Thread(target=self._fetch_worker, args=(selected,), daemon=True).start()

    def _fetch_worker(self, categories: list[str]):
        all_articles = []
        for cat in categories:
            response_data = self.news_client.fetch_articles(
                endpoint="top-headlines",
                query_params={"category": cat}
            )
            if response_data and response_data.get("status") == "ok":
                articles = response_data.get("articles", [])
                for a in articles:
                    a["fetched_category"] = cat
                all_articles.extend(articles)

        if all_articles:
            df = pd.DataFrame(all_articles)
            df["source_name"] = df["source"].apply(
                lambda x: x["name"] if isinstance(x, dict) and "name" in x else None
            )
            df = df.drop(columns=["source"], errors="ignore")
            df = df.rename(columns={"fetched_category": "category"})
            df = df.drop(columns=[c for c in ["country", "urlToImage"] if c in df.columns])
            self.articles_df = df
            save_api_cache(categories, df)

        self.after(0, lambda: self._post_fetch(from_cache=False))

    def _post_fetch(self, from_cache: bool):
        self.fetch_btn.config(state="normal")
        n = len(self.articles_df)
        self.count_label.config(text=str(n))
        tag = "  (from cache)" if from_cache else "  (live)"
        self.cache_label.config(text=tag)
        self._set_status(f"Fetched {n} articles{tag}")
        self.enrich_btn.config(state="normal")
        self.enrich_status.config(text="Ready to enrich with web scraping")
        self._apply_filter()

    # ══════════════════════════════════════════════════════════════════════════
    # Enrich logic
    # ══════════════════════════════════════════════════════════════════════════

    def _on_enrich(self):
        if self.articles_df.empty:
            return
        self.enrich_btn.config(state="disabled")
        self.enrich_progress["value"] = 0
        threading.Thread(target=self._enrich_worker, daemon=True).start()

    def _enrich_worker(self):
        df = self.articles_df

        # Step 1: Probe one article per unique source to confirm whether scraping is available
        unique_sources = df["source_name"].unique()
        total_sources = len(unique_sources)
        scraping_success_map = {}

        self.after(0, lambda: self.enrich_status.config(
            text=f"Probing {total_sources} unique sources…"))

        for i, source_name in enumerate(unique_sources):
            row = df[df["source_name"] == source_name].iloc[0]
            url = row["url"]

            try:
                if url in self.scrape_cache:
                    cached_text = self.scrape_cache[url]
                    scraping_success_map[source_name] = cached_text is not None
                else:
                    soup = self.scraper.fetch_and_parse(url)
                    text = None
                    if soup:
                        extracted = self.scraper.extract_full_text(soup)
                        if extracted:
                            ok, _ = self.scraper.cross_check_scraped_text(
                                extracted,
                                row.get("description"),
                                row.get("content")
                            )
                            if ok:
                                text = extracted
                    self.scrape_cache[url] = text
                    scraping_success_map[source_name] = text is not None
            except Exception as e:
                print(f"Skipping source '{source_name}' due to error: {e}")
                self.scrape_cache[url] = None
                scraping_success_map[source_name] = False

            progress = int(((i + 1) / total_sources) * 50)
            self.after(0, lambda p=progress: self.enrich_progress.config(value=p))

        self.articles_df["scraping_available"] = (
            self.articles_df["source_name"].map(scraping_success_map).fillna(False)
        )

        # Step 2: scrape full content for all articles from scraping-available sources
        scrapable = self.articles_df[self.articles_df["scraping_available"]]
        total_articles = len(scrapable)

        self.after(0, lambda: self.enrich_status.config(
            text=f"Scraping {total_articles} articles…"))

        content_map = {}
        for i, (idx, row) in enumerate(scrapable.iterrows()):
            url = row["url"]
            try:
                if url in self.scrape_cache and self.scrape_cache[url] is not None:
                    content_map[idx] = self.scrape_cache[url]
                else:
                    soup = self.scraper.fetch_and_parse(url)
                    text = None
                    if soup:
                        extracted = self.scraper.extract_full_text(soup)
                        if extracted:
                            ok, _ = self.scraper.cross_check_scraped_text(
                                extracted, row.get("description"), row.get("content")
                            )
                            if ok:
                                text = extracted
                    self.scrape_cache[url] = text
                    content_map[idx] = text
            except Exception as e:
                print(f"Skipping article at '{url}' due to error: {e}")
                content_map[idx] = None

            progress = 50 + int(((i + 1) / max(total_articles, 1)) * 50)
            self.after(0, lambda p=progress: self.enrich_progress.config(value=p))

        self.articles_df["content_scraping"] = self.articles_df.index.map(
            lambda idx: content_map.get(idx, np.nan)
        )

        save_scrape_cache(self.scrape_cache)

        scraped_count = self.articles_df["content_scraping"].notna().sum()
        self.after(0, lambda: self._post_enrich(scraped_count))

    def _post_enrich(self, scraped_count: int):
        self.enrich_btn.config(state="normal")
        self.enrich_progress["value"] = 100
        msg = f"Scraped {scraped_count} / {len(self.articles_df)} articles"
        self.enrich_status.config(text=msg)
        self._set_status(msg)
        self._apply_filter()

    # ══════════════════════════════════════════════════════════════════════════
    # Filter & listbox
    # ══════════════════════════════════════════════════════════════════════════

    def _apply_filter(self):
        if self.articles_df.empty:
            return

        cat = self.filter_category.get()
        df = self.articles_df.copy()

        if cat != "All":
            df = df[df["category"] == cat.lower()]

        try:
            max_n = int(self.max_display.get())
            max_n = max(1, max_n)
        except ValueError:
            max_n = 10

        self.filtered_df = df.head(max_n).reset_index(drop=True)
        self._populate_listbox()

    def _populate_listbox(self):
        self.article_listbox.delete(0, "end")
        for i, row in self.filtered_df.iterrows():
            title = row.get("title") or "(No title)"
            display = f"{i + 1}. {title}"
            self.article_listbox.insert("end", display)

    # ══════════════════════════════════════════════════════════════════════════
    # Article detail view
    # ══════════════════════════════════════════════════════════════════════════

    def _on_article_select(self, event):
        selection = self.article_listbox.curselection()
        if not selection or self.filtered_df.empty:
            return
        idx = selection[0]
        if idx >= len(self.filtered_df):
            return
        row = self.filtered_df.iloc[idx]
        self._display_article(row)

    def _display_article(self, row):
        title    = row.get("title")       or "No title"
        source   = row.get("source_name") or ""
        author   = row.get("author")      or ""
        date     = row.get("publishedAt") or ""
        url      = row.get("url")         or ""
        category = row.get("category")    or ""

        # Format date
        try:
            dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
            date = dt.strftime("%d %b %Y, %H:%M UTC")
        except Exception:
            pass

        # Content: If available, display scraped content. Otherwise, show API-fetched content
        scraped = row.get("content_scraping")
        api_content = row.get("content") or row.get("description") or "No content available."

        if pd.notna(scraped) and scraped:
            content = scraped
            tag = "● Scraped content"
            tag_color = "#4caf50"
        else:
            content = api_content
            tag = "○ API content"
            tag_color = self._colors["muted"]

        self.detail_title.config(text=title)
        self.detail_source.config(text=source)
        self.detail_category.config(text=category.capitalize() if category else "")
        self.detail_author.config(text=f"by {author}" if author else "")
        self.detail_date.config(text=date)
        self.detail_url.config(text=url)
        self.detail_url.url = url
        self.content_tag.config(text=tag, fg=tag_color)

        self.detail_content.config(state="normal")
        self.detail_content.delete("1.0", "end")
        self.detail_content.insert("end", content)
        self.detail_content.config(state="disabled")

    def _open_url(self, event):
        url = getattr(event.widget, "url", "")
        if url:
            import webbrowser
            webbrowser.open(url)

    # ══════════════════════════════════════════════════════════════════════════
    # Visualisation window
    # ══════════════════════════════════════════════════════════════════════════

    def _open_visualisation_window(self):
        if self.articles_df.empty:
            messagebox.showinfo("No data", "Please fetch articles first.")
            return

        c = self._colors
        win = tk.Toplevel(self)
        win.title("Visualisation Options")
        win.geometry("1000x620")
        win.minsize(800, 500)
        win.configure(bg=c["bg"])

        # ── Top bar ───────────────────────────────────────────────────────────
        top = tk.Frame(win, bg=c["panel"], pady=10)
        top.pack(fill="x")
        tk.Label(top, text="📊  Visualisations", bg=c["panel"],
                 fg=c["text"], font=("Helvetica", 13, "bold")).pack(side="left", padx=16)
        ttk.Button(top, text="✕  Close", style="Secondary.TButton",
                   command=win.destroy).pack(side="right", padx=12)

        # ── Body: controls left, chart right ─────────────────────────────────
        body = tk.Frame(win, bg=c["bg"])
        body.pack(fill="both", expand=True, padx=10, pady=10)

        # Controls strip
        ctrl = tk.Frame(body, bg=c["panel"], width=220, padx=14, pady=14)
        ctrl.pack(side="left", fill="y")
        ctrl.pack_propagate(False)

        # Chart area
        chart_area = tk.Frame(body, bg=c["bg"])
        chart_area.pack(side="left", fill="both", expand=True, padx=(10, 0))

        # Placeholder label shown before any chart is rendered
        placeholder = tk.Label(chart_area,
                               text="Select a visualisation option →",
                               bg=c["bg"], fg=c["muted"],
                               font=("Helvetica", 12))
        placeholder.pack(expand=True)

        def _show_pie():
            placeholder.pack_forget()
            self.visualiser.render_pie_chart(self.articles_df, chart_area)

        def _show_keywords():
            placeholder.pack_forget()
            chosen = kw_cat_var.get().lower()
            self.visualiser.render_keywords_chart(
                self.articles_df, chosen, self.keyword_extractor, chart_area
            )

        # ── Option 1 ──────────────────────────────────────────────────────────
        tk.Label(ctrl, text="CATEGORY DISTRIBUTION", bg=c["panel"],
                 fg=c["highlight"], font=("Helvetica", 8, "bold")).pack(anchor="w")
        ttk.Separator(ctrl).pack(fill="x", pady=(2, 8))
        ttk.Button(ctrl, text="📊  Pie Chart",
                   style="Accent.TButton",
                   command=_show_pie).pack(fill="x")

        ttk.Separator(ctrl).pack(fill="x", pady=14)

        # ── Option 2 ──────────────────────────────────────────────────────────
        tk.Label(ctrl, text="KEYWORDS BY CATEGORY", bg=c["panel"],
                 fg=c["highlight"], font=("Helvetica", 8, "bold")).pack(anchor="w")
        ttk.Separator(ctrl).pack(fill="x", pady=(2, 8))

        tk.Label(ctrl, text="Category", bg=c["panel"],
                 fg=c["muted"], font=("Helvetica", 8)).pack(anchor="w")
        kw_cat_var = tk.StringVar(value=CATEGORIES[0].capitalize())
        kw_combo = ttk.Combobox(ctrl, textvariable=kw_cat_var,
                                values=[cat.capitalize() for cat in CATEGORIES],
                                state="readonly", width=18)
        kw_combo.pack(fill="x", pady=(2, 8))

        ttk.Button(ctrl, text="☁  Word Cloud + Bar Chart",
                   style="Secondary.TButton",
                   command=_show_keywords).pack(fill="x")

    # ── Utility ───────────────────────────────────────────────────────────────

    def _set_status(self, msg: str):
        self.status_label.config(text=msg)


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = NewsAggregatorApp()
    app.mainloop()
