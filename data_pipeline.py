"""
data_pipeline.py — NewsPipeline class
Owns all data fetching, enrichment, caching, and filtering logic.
"""

import json
import os
import hashlib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from news_api_client import NewsAPIClient
from web_scraper import WebScraping

# ── Constants ─────────────────────────────────────────────────────────────────
CATEGORIES        = ["business", "entertainment", "general", "health", "science", "sports", "technology"]
CACHE_DIR         = ".cache"
CACHE_TTL_HOURS   = 6
API_CACHE_FILE    = os.path.join(CACHE_DIR, "api_cache.json")
SCRAPE_CACHE_FILE = os.path.join(CACHE_DIR, "scrape_cache.json")


class NewsPipeline:
    """
    Manages the full data lifecycle:
      - Fetching articles from the NewsAPI and building the DataFrame
      - Enriching articles with full text via web scraping
      - Caching both API responses and scraping results to disk
      - Filtering the DataFrame for display
      - Resolving the correct content field for a given article
    """

    def __init__(self, api_key: str):
        self.news_client  = NewsAPIClient(api_key)
        self.scraper      = WebScraping()
        self.articles_df  = pd.DataFrame()
        self.filtered_df  = pd.DataFrame()
        self.scrape_cache = self._load_scrape_cache()

    # ══════════════════════════════════════════════════════════════════════════
    # Cache helpers
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _ensure_cache_dir():
        os.makedirs(CACHE_DIR, exist_ok=True)

    @staticmethod
    def _cache_key(categories: list) -> str:
        """Deterministic hash key based on sorted category list."""
        return hashlib.md5(",".join(sorted(categories)).encode()).hexdigest()

    def load_api_cache(self, categories: list):
        """Return cached DataFrame if present and not expired, else None."""
        self._ensure_cache_dir()
        if not os.path.exists(API_CACHE_FILE):
            return None
        try:
            with open(API_CACHE_FILE, "r") as f:
                store = json.load(f)
            entry = store.get(self._cache_key(categories))
            if not entry:
                return None
            if datetime.now() - datetime.fromisoformat(entry["saved_at"]) > timedelta(hours=CACHE_TTL_HOURS):
                return None
            df = pd.DataFrame(entry["records"])
            if "scraping_available" in df.columns:
                df["scraping_available"] = df["scraping_available"].astype(bool)
            return df
        except Exception:
            return None

    def save_api_cache(self, categories: list, df: pd.DataFrame):
        self._ensure_cache_dir()
        store = {}
        if os.path.exists(API_CACHE_FILE):
            try:
                with open(API_CACHE_FILE, "r") as f:
                    store = json.load(f)
            except Exception:
                pass
        store[self._cache_key(categories)] = {
            "saved_at": datetime.now().isoformat(),
            "records":  json.loads(df.to_json(orient="records"))
        }
        with open(API_CACHE_FILE, "w") as f:
            json.dump(store, f, indent=2)

    def _load_scrape_cache(self) -> dict:
        """Return {url: scraped_text | None} dict from disk."""
        self._ensure_cache_dir()
        if not os.path.exists(SCRAPE_CACHE_FILE):
            return {}
        try:
            with open(SCRAPE_CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_scrape_cache(self):
        self._ensure_cache_dir()
        with open(SCRAPE_CACHE_FILE, "w") as f:
            json.dump(self.scrape_cache, f, indent=2)

    # ══════════════════════════════════════════════════════════════════════════
    # Fetch articles
    # ══════════════════════════════════════════════════════════════════════════

    def fetch_articles(self, categories: list) -> tuple:
        """
        Fetch articles for the given categories from the NewsAPI.
        Sets self.articles_df and saves to cache on a live fetch.
        """
        cached = self.load_api_cache(categories)
        if cached is not None:
            self.articles_df = cached
            return self.articles_df, True

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
            self.save_api_cache(categories, df)
        else:
            self.articles_df = pd.DataFrame()

        return self.articles_df, False

    # ══════════════════════════════════════════════════════════════════════════
    # Enrich articles with web scraping
    # ══════════════════════════════════════════════════════════════════════════

    def enrich_articles(self, progress_callback=None) -> int:
        """
        Run both scraping phases against self.articles_df.
        progress_callback is called with 0-100 as work progresses.
        Returns the number of articles successfully scraped.
        """
        df = self.articles_df

        # ── Phase 1: probe one article per unique source ──────────────────────
        unique_sources   = df["source_name"].unique()
        total_sources    = len(unique_sources)
        scraping_success_map = {}

        for i, source_name in enumerate(unique_sources):
            row = df[df["source_name"] == source_name].iloc[0]
            url = row["url"]
            try:
                if url in self.scrape_cache:
                    scraping_success_map[source_name] = self.scrape_cache[url] is not None
                else:
                    text = self._scrape_url(url, row)
                    self.scrape_cache[url] = text
                    scraping_success_map[source_name] = text is not None
            except Exception as e:
                print(f"Skipping source '{source_name}' due to error: {e}")
                self.scrape_cache[url] = None
                scraping_success_map[source_name] = False

            if progress_callback:
                progress_callback(int(((i + 1) / total_sources) * 50))

        self.articles_df["scraping_available"] = (
            self.articles_df["source_name"].map(scraping_success_map).fillna(False)
        )

        # ── Phase 2: scrape full content for all scrapable articles ───────────
        scrapable      = self.articles_df[self.articles_df["scraping_available"]]
        total_articles = len(scrapable)
        content_map    = {}

        for i, (idx, row) in enumerate(scrapable.iterrows()):
            url = row["url"]
            try:
                if url in self.scrape_cache and self.scrape_cache[url] is not None:
                    content_map[idx] = self.scrape_cache[url]
                else:
                    text = self._scrape_url(url, row)
                    self.scrape_cache[url] = text
                    content_map[idx] = text
            except Exception as e:
                print(f"Skipping article at '{url}' due to error: {e}")
                content_map[idx] = None

            if progress_callback:
                progress_callback(50 + int(((i + 1) / max(total_articles, 1)) * 50))

        self.articles_df["content_scraping"] = self.articles_df.index.map(
            lambda idx: content_map.get(idx, np.nan)
        )

        self.save_scrape_cache()
        return int(self.articles_df["content_scraping"].notna().sum())

    def _scrape_url(self, url: str, row: pd.Series):
        """Fetch, extract, and cross-check one URL. Returns text or None."""
        soup = self.scraper.fetch_and_parse(url)
        if not soup:
            return None
        extracted = self.scraper.extract_full_text(soup)
        if not extracted:
            return None
        ok, _ = self.scraper.cross_check_scraped_text(
            extracted, row.get("description"), row.get("content")
        )
        return extracted if ok else None

    # ══════════════════════════════════════════════════════════════════════════
    # Filtering
    # ══════════════════════════════════════════════════════════════════════════

    def filter_articles(self, category: str = "All", max_n: int = 10) -> pd.DataFrame:
        """
        Filter self.articles_df by category and row limit.
        Sets and returns self.filtered_df.
        """
        if self.articles_df.empty:
            self.filtered_df = pd.DataFrame()
            return self.filtered_df

        df = self.articles_df.copy()
        if category != "All":
            df = df[df["category"] == category.lower()]

        self.filtered_df = df.head(max(1, max_n)).reset_index(drop=True)
        return self.filtered_df

    # ══════════════════════════════════════════════════════════════════════════
    # Content resolution
    # ══════════════════════════════════════════════════════════════════════════

    def get_article_content(self, row: pd.Series) -> tuple:
        """
        Return (content_text, is_scraped).
        Prefers scraped content; falls back to API content or description.
        """
        scraped = row.get("content_scraping")
        if pd.notna(scraped) and scraped:
            return scraped, True
        api_content = row.get("content") or row.get("description") or "No content available."
        return api_content, False
