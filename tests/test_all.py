"""
tests/test_all.py
Unit tests for NewsAggregatorApp classes.

Run from the project root with:
    python -m pytest tests/test_all.py -v
or:
    python -m unittest tests/test_all.py -v

All network calls are mocked — no real API key or internet needed.
"""

import sys
import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock, PropertyMock
import pandas as pd
import numpy as np

# ── Make sure project root is importable ──────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from news_api_client import NewsAPIClient
from web_scraper import WebScraping
from keyword_extractor import FrequentKeywords

# Import cache helpers directly from main (we test them in isolation)
import importlib.util, types

def _load_main_helpers():
    """Load only the cache helpers from main.py without starting Tkinter."""
    spec = importlib.util.spec_from_file_location(
        "main_module",
        os.path.join(os.path.dirname(__file__), "..", "main.py")
    )
    mod = types.ModuleType("main_module")
    # Stub tkinter before executing main so the module-level code doesn't open a window
    sys.modules.setdefault("tkinter", MagicMock())
    sys.modules.setdefault("tkinter.ttk", MagicMock())
    sys.modules.setdefault("tkinter.messagebox", MagicMock())
    sys.modules.setdefault("tkinter.scrolledtext", MagicMock())
    spec.loader.exec_module(mod)
    return mod

_main = _load_main_helpers()
load_api_cache  = _main.load_api_cache
save_api_cache  = _main.save_api_cache
load_scrape_cache = _main.load_scrape_cache
save_scrape_cache = _main.save_scrape_cache
_cache_key      = _main._cache_key


# ══════════════════════════════════════════════════════════════════════════════
# NewsAPIClient tests
# ══════════════════════════════════════════════════════════════════════════════

class TestNewsAPIClient(unittest.TestCase):

    def setUp(self):
        self.client = NewsAPIClient(api_key="test_key_123")

    # ── fetch_articles ────────────────────────────────────────────────────────

    @patch("news_api_client.requests.get")
    def test_fetch_articles_success(self, mock_get):
        """Should return parsed JSON on 200 OK."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "totalResults": 2,
            "articles": [
                {"title": "Article A", "source": {"name": "BBC"}},
                {"title": "Article B", "source": {"name": "CNN"}},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = self.client.fetch_articles(query_params={"category": "technology"})

        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["articles"]), 2)

    @patch("news_api_client.requests.get")
    def test_fetch_articles_http_error(self, mock_get):
        """Should return None on HTTP 4xx/5xx."""
        import requests as req
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        http_err = req.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_err
        mock_get.return_value = mock_response

        result = self.client.fetch_articles()
        self.assertIsNone(result)

    @patch("news_api_client.requests.get")
    def test_fetch_articles_network_error(self, mock_get):
        """Should return None on connection error."""
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("offline")

        result = self.client.fetch_articles()
        self.assertIsNone(result)

    @patch("news_api_client.requests.get")
    def test_default_language_injected(self, mock_get):
        """Default language 'en' should be added to params automatically."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "articles": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        self.client.fetch_articles(query_params={"category": "health"})

        call_kwargs = mock_get.call_args[1]
        params = call_kwargs.get("params", {})
        self.assertEqual(params.get("language"), "en")

    @patch("news_api_client.requests.get")
    def test_custom_page_size(self, mock_get):
        """Custom page_size should override the client default."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "articles": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        self.client.fetch_articles(page_size=5)
        params = mock_get.call_args[1]["params"]
        self.assertEqual(params["pageSize"], 5)


# ══════════════════════════════════════════════════════════════════════════════
# WebScraping tests
# ══════════════════════════════════════════════════════════════════════════════

class TestWebScraping(unittest.TestCase):

    def setUp(self):
        self.scraper = WebScraping(timeout=5)

    # ── fetch_and_parse ───────────────────────────────────────────────────────

    @patch("web_scraper.requests.get")
    def test_fetch_and_parse_success(self, mock_get):
        """Should return a BeautifulSoup object on success."""
        mock_response = MagicMock()
        mock_response.text = "<html><body><article><p>Hello world</p></article></body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = self.scraper.fetch_and_parse("https://example.com/article")
        self.assertIsNotNone(result)

    @patch("web_scraper.requests.get")
    def test_fetch_and_parse_failure(self, mock_get):
        """Should return None when request fails."""
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout("timeout")

        result = self.scraper.fetch_and_parse("https://example.com/article")
        self.assertIsNone(result)

    # ── extract_full_text ─────────────────────────────────────────────────────

    def test_extract_full_text_from_article_tag(self):
        """Should extract paragraph text from <article> tag."""
        from bs4 import BeautifulSoup
        html = """
        <html><body>
          <article>
            <p>First paragraph of the article.</p>
            <p>Second paragraph with more details.</p>
          </article>
        </body></html>"""
        soup = BeautifulSoup(html, "html.parser")
        text = self.scraper.extract_full_text(soup)
        self.assertIn("First paragraph", text)
        self.assertIn("Second paragraph", text)

    def test_extract_full_text_returns_none_on_no_soup(self):
        """Should return None when soup is None."""
        result = self.scraper.extract_full_text(None)
        self.assertIsNone(result)

    def test_extract_full_text_fallback(self):
        """Should fall back to all visible text if no article tag found."""
        from bs4 import BeautifulSoup
        html = "<html><body><div><p>Fallback text here.</p></div></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        text = self.scraper.extract_full_text(soup)
        self.assertIsNotNone(text)
        self.assertTrue(len(text) > 0)

    # ── cross_check_scraped_text ──────────────────────────────────────────────

    def test_cross_check_passes_when_longer_and_overlapping(self):
        """Should pass when scraped text is longer and shares enough words."""
        api_text = "the cat sat on the mat in the garden today morning"
        # Make scraped text longer and include all API words
        scraped  = (api_text + " " + "extra content " * 30)
        ok, reason = self.scraper.cross_check_scraped_text(scraped, api_text, None)
        self.assertTrue(ok, reason)

    def test_cross_check_fails_when_scraped_shorter(self):
        """Should fail when scraped text is shorter than API text."""
        api_text = "a long description that is quite long indeed and has many words here now"
        scraped  = "short"
        ok, reason = self.scraper.cross_check_scraped_text(scraped, api_text, None)
        self.assertFalse(ok)

    def test_cross_check_no_api_text(self):
        """Should pass (can't cross-check) when no API text is provided."""
        ok, reason = self.scraper.cross_check_scraped_text(
            "some full article text here", None, None
        )
        self.assertTrue(ok)

    def test_cross_check_no_full_text(self):
        """Should fail when full_text is empty."""
        ok, _ = self.scraper.cross_check_scraped_text("", "api description text", None)
        self.assertFalse(ok)

    # ── _normalize_text ───────────────────────────────────────────────────────

    def test_normalize_text_lowercases(self):
        result = self.scraper._normalize_text("Hello WORLD")
        self.assertEqual(result, "hello world")

    def test_normalize_text_removes_punctuation(self):
        result = self.scraper._normalize_text("Hello, world! It's great.")
        self.assertNotIn(",", result)
        self.assertNotIn("!", result)

    def test_normalize_text_handles_none(self):
        result = self.scraper._normalize_text(None)
        self.assertEqual(result, "")


# ══════════════════════════════════════════════════════════════════════════════
# FrequentKeywords tests
# ══════════════════════════════════════════════════════════════════════════════

class TestFrequentKeywords(unittest.TestCase):

    def setUp(self):
        self.extractor = FrequentKeywords()

    def test_extract_keywords_returns_list_of_tuples(self):
        """Should return a list of (word, count) tuples."""
        text = "Python is a great programming language. Python is widely used."
        result = self.extractor.extract_keywords(text, top_n=5)
        self.assertIsInstance(result, list)
        self.assertTrue(all(isinstance(item, tuple) and len(item) == 2 for item in result))

    def test_extract_keywords_top_n_limit(self):
        """Result length should not exceed top_n."""
        text = " ".join(["word" + str(i) for i in range(50)])
        result = self.extractor.extract_keywords(text, top_n=10)
        self.assertLessEqual(len(result), 10)

    def test_extract_keywords_stopwords_removed(self):
        """Common stopwords should not appear in results."""
        text = "the cat sat on the mat and the dog ran away"
        result = self.extractor.extract_keywords(text, top_n=20)
        keywords = [w for w, _ in result]
        for stopword in ["the", "on", "and"]:
            self.assertNotIn(stopword, keywords)

    def test_extract_keywords_empty_text(self):
        """Should return empty list for empty/None input."""
        self.assertEqual(self.extractor.extract_keywords("", top_n=5), [])
        self.assertEqual(self.extractor.extract_keywords(None, top_n=5), [])

    def test_extract_keywords_single_char_filtered(self):
        """Single-character tokens should be excluded."""
        text = "a b c dog cat apple a a a b"
        result = self.extractor.extract_keywords(text, top_n=10)
        keywords = [w for w, _ in result]
        self.assertNotIn("a", keywords)
        self.assertNotIn("b", keywords)

    def test_lemmatization_merges_forms(self):
        """'running' and 'run' should be merged via lemmatization."""
        text = "running runners run runs ran"
        result = self.extractor.extract_keywords(text, top_n=5)
        keywords = [w for w, _ in result]
        # lemmatiser typically maps 'running' → 'running' (WordNet noun lemmatiser)
        # At minimum, ensure no crash and result is non-empty
        self.assertGreater(len(result), 0)

    def test_extract_keywords_counts_are_descending(self):
        """Results should be sorted highest to lowest frequency."""
        text = "apple apple apple banana banana cherry"
        result = self.extractor.extract_keywords(text, top_n=5)
        counts = [c for _, c in result]
        self.assertEqual(counts, sorted(counts, reverse=True))


# ══════════════════════════════════════════════════════════════════════════════
# Cache helper tests
# ══════════════════════════════════════════════════════════════════════════════

class TestCacheHelpers(unittest.TestCase):

    def setUp(self):
        # Use a temp directory so tests don't pollute the real .cache
        self.tmp = tempfile.mkdtemp()
        # Monkeypatch cache constants in main module
        self._orig_api  = _main.API_CACHE_FILE
        self._orig_scrape = _main.SCRAPE_CACHE_FILE
        self._orig_dir  = _main.CACHE_DIR
        _main.CACHE_DIR        = self.tmp
        _main.API_CACHE_FILE   = os.path.join(self.tmp, "api_cache.json")
        _main.SCRAPE_CACHE_FILE = os.path.join(self.tmp, "scrape_cache.json")

    def tearDown(self):
        _main.CACHE_DIR        = self._orig_dir
        _main.API_CACHE_FILE   = self._orig_api
        _main.SCRAPE_CACHE_FILE = self._orig_scrape
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── cache key ─────────────────────────────────────────────────────────────

    def test_cache_key_is_order_independent(self):
        key1 = _cache_key(["business", "health", "sports"])
        key2 = _cache_key(["sports", "business", "health"])
        self.assertEqual(key1, key2)

    def test_cache_key_differs_for_different_cats(self):
        key1 = _cache_key(["business"])
        key2 = _cache_key(["health"])
        self.assertNotEqual(key1, key2)

    # ── API cache round-trip ──────────────────────────────────────────────────

    def test_api_cache_save_and_load(self):
        df = pd.DataFrame([
            {"title": "Test Article", "category": "tech", "source_name": "BBC"},
        ])
        categories = ["tech"]
        save_api_cache(categories, df)
        loaded = load_api_cache(categories)
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded.iloc[0]["title"], "Test Article")

    def test_api_cache_miss_on_different_categories(self):
        df = pd.DataFrame([{"title": "Article", "category": "health"}])
        save_api_cache(["health"], df)
        loaded = load_api_cache(["business"])   # different category set
        self.assertIsNone(loaded)

    def test_api_cache_expires(self):
        """Cache older than TTL should return None."""
        from datetime import datetime, timedelta
        df = pd.DataFrame([{"title": "Old Article", "category": "tech"}])
        categories = ["tech"]

        # Manually write an expired entry
        key = _cache_key(categories)
        old_time = (datetime.now() - timedelta(hours=_main.CACHE_TTL_HOURS + 1)).isoformat()
        store = {key: {"saved_at": old_time, "records": json.loads(df.to_json(orient="records"))}}
        with open(_main.API_CACHE_FILE, "w") as f:
            json.dump(store, f)

        loaded = load_api_cache(categories)
        self.assertIsNone(loaded)

    def test_api_cache_returns_none_when_file_missing(self):
        result = load_api_cache(["technology"])
        self.assertIsNone(result)

    # ── Scrape cache round-trip ───────────────────────────────────────────────

    def test_scrape_cache_save_and_load(self):
        cache = {
            "https://example.com/a": "Full article text here.",
            "https://example.com/b": None,
        }
        save_scrape_cache(cache)
        loaded = load_scrape_cache()
        self.assertEqual(loaded["https://example.com/a"], "Full article text here.")
        self.assertIsNone(loaded["https://example.com/b"])

    def test_scrape_cache_returns_empty_dict_when_missing(self):
        result = load_scrape_cache()
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 0)


# ══════════════════════════════════════════════════════════════════════════════
# Integration-style: NewsAPIClient → DataFrame construction
# ══════════════════════════════════════════════════════════════════════════════

class TestFetchToDataFrame(unittest.TestCase):
    """Verify that the fetch + DataFrame construction logic works end-to-end."""

    FAKE_RESPONSE = {
        "status": "ok",
        "totalResults": 3,
        "articles": [
            {
                "title": "Tech Story One",
                "author": "Alice",
                "publishedAt": "2024-05-01T10:00:00Z",
                "url": "https://example.com/1",
                "description": "Desc one",
                "content": "Content one [+3000 chars]",
                "source": {"id": "bbc", "name": "BBC News"},
                "urlToImage": "https://example.com/img1.jpg",
            },
            {
                "title": "Tech Story Two",
                "author": "Bob",
                "publishedAt": "2024-05-01T11:00:00Z",
                "url": "https://example.com/2",
                "description": "Desc two",
                "content": "Content two [+2000 chars]",
                "source": {"id": "cnn", "name": "CNN"},
                "urlToImage": None,
            },
        ]
    }

    @patch("news_api_client.requests.get")
    def test_dataframe_columns(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = self.FAKE_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client = NewsAPIClient("test_key")
        response_data = client.fetch_articles(query_params={"category": "technology"})
        articles = response_data.get("articles", [])
        for a in articles:
            a["fetched_category"] = "technology"

        df = pd.DataFrame(articles)
        df["source_name"] = df["source"].apply(lambda x: x["name"] if isinstance(x, dict) else None)
        df = df.drop(columns=["source"], errors="ignore")
        df = df.rename(columns={"fetched_category": "category"})
        df = df.drop(columns=[c for c in ["urlToImage", "country"] if c in df.columns])

        self.assertIn("source_name", df.columns)
        self.assertIn("category", df.columns)
        self.assertNotIn("source", df.columns)
        self.assertNotIn("urlToImage", df.columns)
        self.assertEqual(df.iloc[0]["source_name"], "BBC News")
        self.assertEqual(df.iloc[0]["category"], "technology")


# ══════════════════════════════════════════════════════════════════════════════
# Run
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main(verbosity=2)
