import requests

class NewsAPIClient:
    def __init__(self, api_key, default_page_size=100, default_language='en'):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2/"
        self.default_page_size = default_page_size
        self.default_language = default_language

    def fetch_articles(self, endpoint="top-headlines", query_params=None, page_size=None):
        effective_page_size = page_size if page_size is not None else self.default_page_size
        params = {'apiKey': self.api_key, 'pageSize': effective_page_size}
        if query_params and 'language' not in query_params:
            params['language'] = self.default_language
        elif not query_params:
            params['language'] = self.default_language
        if query_params:
            params.update(query_params)
        try:
            response = requests.get(f"{self.base_url}{endpoint}", params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Request Error: {e}")
            return None
