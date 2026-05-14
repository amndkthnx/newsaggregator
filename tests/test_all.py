"""
tests/test_all.py
Unit tests for all classes and the NewsPipeline data layer.

Run from the project root with:
    python -m unittest tests.test_all -v
"""

import sys
import os
import json
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

# Make sure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from news_api_client import NewsAPIClient
from web_scraper import WebScraping
from keyword_extractor import FrequentKeywords
from data_pipeline import NewsPipeline, CATEGORIES


# ══════════════════════════════════════════════════════════════════════════════
# NewsAPIClient tests
# ══════════════════════════════════════════════════════════════════════════════

class TestNewsAPIClient(unittest.TestCase):

    def setUp(self):
        self.client = NewsAPIClient(api_key="test_key_123")

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
        mock_response.raise_for_status.side_effect = req.exceptions.HTTPError(response=mock_response)
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
        params = mock_get.call_args[1]["params"]
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
        self.assertIsNone(self.scraper.extract_full_text(None))

    def test_extract_full_text_fallback(self):
        """Should fall back to all visible text if no article tag found."""
        from bs4 import BeautifulSoup
        html = "<html><body><div><p>Fallback text here.</p></div></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        text = self.scraper.extract_full_text(soup)
        self.assertIsNotNone(text)
        self.assertGreater(len(text), 0)

    def test_cross_check_passes_when_longer_and_overlapping(self):
        """Should pass when scraped text is longer and shares enough words."""
        api_text = "the cat sat on the mat in the garden today morning"
        scraped  = api_text + " " + "extra content " * 30
        ok, reason = self.scraper.cross_check_scraped_text(scraped, api_text, None)
        self.assertTrue(ok, reason)

    def test_cross_check_fails_when_scraped_shorter(self):
        """Should fail when scraped text is shorter than API text."""
        api_text = "a long description that is quite long indeed and has many words here now"
        ok, _ = self.scraper.cross_check_scraped_text("short", api_text, None)
        self.assertFalse(ok)

    def test_cross_check_no_api_text(self):
        """Should pass when no API text is provided."""
        ok, _ = self.scraper.cross_check_scraped_text("some full article text here", None, None)
        self.assertTrue(ok)

    def test_cross_check_no_full_text(self):
        """Should fail when full_text is empty."""
        ok, _ = self.scraper.cross_check_scraped_text("", "api description text", None)
        self.assertFalse(ok)

    def test_cross_check_nan_api_fields(self):
        """Should handle NaN floats from pandas without crashing."""
        ok, _ = self.scraper.cross_check_scraped_text("some article text here", float("nan"), float("nan"))
        self.assertTrue(ok)

    def test_normalize_text_lowercases(self):
        self.assertEqual(self.scraper._normalize_text("Hello WORLD"), "hello world")

    def test_normalize_text_removes_punctuation(self):
        result = self.scraper._normalize_text("Hello, world! It's great.")
        self.assertNotIn(",", result)
        self.assertNotIn("!", result)

    def test_normalize_text_handles_none(self):
        self.assertEqual(self.scraper._normalize_text(None), "")

    def test_normalize_text_handles_nan(self):
        """Should return empty string for NaN float, not crash."""
        self.assertEqual(self.scraper._normalize_text(float("nan")), "")


# ══════════════════════════════════════════════════════════════════════════════
# FrequentKeywords tests
# ══════════════════════════════════════════════════════════════════════════════

class TestFrequentKeywords(unittest.TestCase):

    def setUp(self):
        self.extractor = FrequentKeywords()

    def test_extract_keywords_returns_list_of_tuples(self):
        """Should return a list of (word, count) tuples."""
        result = self.extractor.extract_keywords("Python is a great programming language.", top_n=5)
        self.assertIsInstance(result, list)
        self.assertTrue(all(isinstance(item, tuple) and len(item) == 2 for item in result))

    def test_extract_keywords_top_n_limit(self):
        """Result length should not exceed top_n."""
        text   = " ".join(["word" + str(i) for i in range(50)])
        result = self.extractor.extract_keywords(text, top_n=10)
        self.assertLessEqual(len(result), 10)

    def test_extract_keywords_stopwords_removed(self):
        """Common stopwords should not appear in results."""
        result   = self.extractor.extract_keywords("the cat sat on the mat and the dog ran away", top_n=20)
        keywords = [w for w, _ in result]
        for sw in ["the", "on", "and"]:
            self.assertNotIn(sw, keywords)

    def test_extract_keywords_empty_text(self):
        """Should return empty list for empty or None input."""
        self.assertEqual(self.extractor.extract_keywords("", top_n=5), [])
        self.assertEqual(self.extractor.extract_keywords(None, top_n=5), [])

    def test_extract_keywords_nan_input(self):
        """Should return empty list for NaN float input."""
        self.assertEqual(self.extractor.extract_keywords(float("nan"), top_n=5), [])

    def test_extract_keywords_single_char_filtered(self):
        """Single-character tokens should be excluded."""
        result   = self.extractor.extract_keywords("a b c dog cat apple a a a b", top_n=10)
        keywords = [w for w, _ in result]
        self.assertNotIn("a", keywords)
        self.assertNotIn("b", keywords)

    def test_extract_keywords_counts_are_descending(self):
        """Results should be sorted highest to lowest frequency."""
        result = self.extractor.extract_keywords("apple apple apple banana banana cherry", top_n=5)
        counts = [c for _, c in result]
        self.assertEqual(counts, sorted(counts, reverse=True))


# ══════════════════════════════════════════════════════════════════════════════
# NewsPipeline — cache helper tests
# ══════════════════════════════════════════════════════════════════════════════

class TestNewsPipelineCache(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # Patch the module-level path constants inside data_pipeline
        import data_pipeline as dp
        self._dp = dp
        self._orig_cache_dir         = dp.CACHE_DIR
        self._orig_api_cache_file    = dp.API_CACHE_FILE
        self._orig_scrape_cache_file = dp.SCRAPE_CACHE_FILE
        dp.CACHE_DIR         = self.tmp
        dp.API_CACHE_FILE    = os.path.join(self.tmp, "api_cache.json")
        dp.SCRAPE_CACHE_FILE = os.path.join(self.tmp, "scrape_cache.json")
        self.pipeline = NewsPipeline.__new__(NewsPipeline)
        self.pipeline.scrape_cache = {}

    def tearDown(self):
        dp = self._dp
        dp.CACHE_DIR         = self._orig_cache_dir
        dp.API_CACHE_FILE    = self._orig_api_cache_file
        dp.SCRAPE_CACHE_FILE = self._orig_scrape_cache_file
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cache_key_is_order_independent(self):
        key1 = NewsPipeline._cache_key(["business", "health", "sports"])
        key2 = NewsPipeline._cache_key(["sports", "business", "health"])
        self.assertEqual(key1, key2)

    def test_cache_key_differs_for_different_cats(self):
        self.assertNotEqual(
            NewsPipeline._cache_key(["business"]),
            NewsPipeline._cache_key(["health"])
        )

    def test_api_cache_save_and_load(self):
        df         = pd.DataFrame([{"title": "Test Article", "category": "tech", "source_name": "BBC"}])
        categories = ["tech"]
        self.pipeline.save_api_cache(categories, df)
        loaded = self.pipeline.load_api_cache(categories)
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded.iloc[0]["title"], "Test Article")

    def test_api_cache_miss_on_different_categories(self):
        df = pd.DataFrame([{"title": "Article", "category": "health"}])
        self.pipeline.save_api_cache(["health"], df)
        self.assertIsNone(self.pipeline.load_api_cache(["business"]))

    def test_api_cache_expires(self):
        """Cache older than TTL should return None."""
        from datetime import datetime, timedelta
        import data_pipeline as dp
        df  = pd.DataFrame([{"title": "Old Article", "category": "tech"}])
        cats = ["tech"]
        key  = NewsPipeline._cache_key(cats)
        old  = (datetime.now() - timedelta(hours=dp.CACHE_TTL_HOURS + 1)).isoformat()
        store = {key: {"saved_at": old, "records": json.loads(df.to_json(orient="records"))}}
        with open(dp.API_CACHE_FILE, "w") as f:
            json.dump(store, f)
        self.assertIsNone(self.pipeline.load_api_cache(cats))

    def test_api_cache_returns_none_when_file_missing(self):
        self.assertIsNone(self.pipeline.load_api_cache(["technology"]))

    def test_scrape_cache_save_and_load(self):
        self.pipeline.scrape_cache = {
            "https://example.com/a": "Full article text here.",
            "https://example.com/b": None,
        }
        self.pipeline.save_scrape_cache()
        loaded = self.pipeline._load_scrape_cache()
        self.assertEqual(loaded["https://example.com/a"], "Full article text here.")
        self.assertIsNone(loaded["https://example.com/b"])

    def test_scrape_cache_returns_empty_dict_when_missing(self):
        result = self.pipeline._load_scrape_cache()
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 0)


# ══════════════════════════════════════════════════════════════════════════════
# NewsPipeline — fetch and DataFrame construction
# ══════════════════════════════════════════════════════════════════════════════

class TestNewsPipelineFetch(unittest.TestCase):

    FAKE_RESPONSE = {
        "status": "ok",
        "totalResults": 2,
        "articles": [
            {
                "title": "Tech Story One", "author": "Alice",
                "publishedAt": "2024-05-01T10:00:00Z",
                "url": "https://example.com/1",
                "description": "Desc one", "content": "Content one [+3000 chars]",
                "source": {"id": "bbc", "name": "BBC News"},
                "urlToImage": "https://example.com/img1.jpg",
            },
            {
                "title": "Tech Story Two", "author": "Bob",
                "publishedAt": "2024-05-01T11:00:00Z",
                "url": "https://example.com/2",
                "description": "Desc two", "content": "Content two [+2000 chars]",
                "source": {"id": "cnn", "name": "CNN"},
                "urlToImage": None,
            },
        ]
    }

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        import data_pipeline as dp
        self._dp = dp
        self._orig_cache_dir         = dp.CACHE_DIR
        self._orig_api_cache_file    = dp.API_CACHE_FILE
        self._orig_scrape_cache_file = dp.SCRAPE_CACHE_FILE
        dp.CACHE_DIR         = self.tmp
        dp.API_CACHE_FILE    = os.path.join(self.tmp, "api_cache.json")
        dp.SCRAPE_CACHE_FILE = os.path.join(self.tmp, "scrape_cache.json")

    def tearDown(self):
        dp = self._dp
        dp.CACHE_DIR         = self._orig_cache_dir
        dp.API_CACHE_FILE    = self._orig_api_cache_file
        dp.SCRAPE_CACHE_FILE = self._orig_scrape_cache_file
        shutil.rmtree(self.tmp, ignore_errors=True)

    @patch("news_api_client.requests.get")
    def test_fetch_builds_correct_dataframe(self, mock_get):
        """DataFrame should have source_name and category columns; source and urlToImage removed."""
        mock_response = MagicMock()
        mock_response.json.return_value = self.FAKE_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        pipeline = NewsPipeline("test_key")
        df, from_cache = pipeline.fetch_articles(["technology"])

        self.assertFalse(from_cache)
        self.assertIn("source_name", df.columns)
        self.assertIn("category", df.columns)
        self.assertNotIn("source", df.columns)
        self.assertNotIn("urlToImage", df.columns)
        self.assertEqual(df.iloc[0]["source_name"], "BBC News")
        self.assertEqual(df.iloc[0]["category"], "technology")

    @patch("news_api_client.requests.get")
    def test_fetch_returns_from_cache_on_second_call(self, mock_get):
        """Second call with same categories should load from cache without hitting the API."""
        mock_response = MagicMock()
        mock_response.json.return_value = self.FAKE_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        pipeline = NewsPipeline("test_key")
        pipeline.fetch_articles(["technology"])       # live fetch + save cache
        mock_get.reset_mock()
        _, from_cache = pipeline.fetch_articles(["technology"])  # should hit cache

        self.assertTrue(from_cache)
        mock_get.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# NewsPipeline — filter_articles and get_article_content
# ══════════════════════════════════════════════════════════════════════════════

class TestNewsPipelineFilter(unittest.TestCase):

    def setUp(self):
        self.pipeline = NewsPipeline.__new__(NewsPipeline)
        self.pipeline.scrape_cache = {}
        self.pipeline.articles_df = pd.DataFrame([
            {"title": "A", "category": "technology", "source_name": "BBC",
             "content": "api content A", "description": "desc A", "content_scraping": "scraped A"},
            {"title": "B", "category": "health",     "source_name": "CNN",
             "content": "api content B", "description": "desc B", "content_scraping": float("nan")},
            {"title": "C", "category": "technology", "source_name": "Reuters",
             "content": "api content C", "description": "desc C", "content_scraping": float("nan")},
        ])
        self.pipeline.filtered_df = pd.DataFrame()

    def test_filter_all_categories(self):
        result = self.pipeline.filter_articles(category="All", max_n=10)
        self.assertEqual(len(result), 3)

    def test_filter_by_category(self):
        result = self.pipeline.filter_articles(category="Technology", max_n=10)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(r == "technology" for r in result["category"]))

    def test_filter_respects_max_n(self):
        result = self.pipeline.filter_articles(category="All", max_n=2)
        self.assertEqual(len(result), 2)

    def test_filter_empty_dataframe(self):
        self.pipeline.articles_df = pd.DataFrame()
        result = self.pipeline.filter_articles()
        self.assertTrue(result.empty)

    def test_get_article_content_prefers_scraped(self):
        row = self.pipeline.articles_df.iloc[0]
        content, is_scraped = self.pipeline.get_article_content(row)
        self.assertTrue(is_scraped)
        self.assertEqual(content, "scraped A")

    def test_get_article_content_falls_back_to_api(self):
        row = self.pipeline.articles_df.iloc[1]
        content, is_scraped = self.pipeline.get_article_content(row)
        self.assertFalse(is_scraped)
        self.assertEqual(content, "api content B")


# ══════════════════════════════════════════════════════════════════════════════
# Run
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main(verbosity=2)
