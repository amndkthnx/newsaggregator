import requests
from bs4 import BeautifulSoup
import re

class WebScraping:
    def __init__(self, timeout=10):
        self.timeout = timeout

    def fetch_and_parse(self, url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def extract_full_text(self, soup):
        if not soup:
            return None
        selectors = ['article','div[itemprop="articleBody"]','div.entry-content',
                     'div.article-content','div.story-body','div.post-content','main']
        for selector in selectors:
            content_div = soup.find(selector)
            if content_div:
                paragraphs = content_div.find_all('p')
                text = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                if text:
                    return text
        return soup.get_text(separator=' ', strip=True)

    def _normalize_text(self, text):
        if not text or not isinstance(text, str):
            return ""
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s]', '', text).strip()
        text = re.sub(r'\s+', ' ', text)
        return text

    def cross_check_scraped_text(self, full_text, api_description, api_content):
        if not full_text or not isinstance(full_text, str):
            return False, "No full text extracted for cross-check."
        # Coerce NaN floats (from pandas) to None
        if not isinstance(api_description, str):
            api_description = None
        if not isinstance(api_content, str):
            api_content = None
        api_text_to_compare = api_description if api_description else api_content
        if not api_text_to_compare:
            return True, "No API description/content for cross-check."
        normalized_full_text = self._normalize_text(full_text)
        normalized_api_text = self._normalize_text(api_text_to_compare)
        if len(normalized_full_text) < len(normalized_api_text) * 1.1:
            return False, f"Scraped text is not substantially longer than API text."
        api_words = set(w for w in normalized_api_text.split() if len(w) > 2)
        full_text_words = set(w for w in normalized_full_text.split() if len(w) > 2)
        if not api_words:
            return True, "No significant API words to cross-check against."
        match_ratio = len(api_words.intersection(full_text_words)) / len(api_words)
        if match_ratio < 0.7:
            return False, f"Only {match_ratio:.1%} of API words found in scraped text."
        return True, "Cross-check successful."
