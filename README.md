# News Aggregator & Visualisation Tool

A Python desktop application that fetches live news articles from the NewsAPI, enriches them with full article text through web scraping, and presents the results through an interactive Tkinter GUI with keyword visualisations.

---

## Features

- Fetch articles across up to 7 news categories from the NewsAPI
- Enrich articles with full text (when available) via BeautifulSoup web scraping
- Browse articles with category filtering and adjustable display count
- View article details including title, source, author, date, URL, and content
- Visualise article distribution with a category pie chart
- Explore trending keywords with word clouds and bar charts by category
- Two-layer JSON caching to avoid repeated API calls and scraping requests

---

## Project Structure

```
news_aggregator/
├── main.py                 # Tkinter GUI — layout, callbacks, threading
├── data_pipeline.py        # NewsPipeline — fetch, enrich, cache, filter
├── news_api_client.py      # NewsAPIClient — NewsAPI HTTP requests
├── web_scraper.py          # WebScraping — BeautifulSoup scraping and validation
├── keyword_extractor.py    # FrequentKeywords — NLTK tokenisation and keyword ranking
├── visualiser.py           # Visualiser — Matplotlib pie chart and keyword charts
└── tests/
    ├── __init__.py
    └── test_all.py         # 42 unit tests (all network calls mocked)
```

A `.cache/` folder is created automatically on first run:
- `.cache/api_cache.json` — stores fetched article data, expires after 6 hours
- `.cache/scrape_cache.json` — stores scraped content per URL, no expiry

---

## Requirements

**Python 3.11 or later**

Install dependencies:

```bash
pip install requests beautifulsoup4 pandas numpy matplotlib wordcloud nltk
```

Download required NLTK data (run once):

```bash
python -c "import nltk; nltk.download('stopwords'); nltk.download('wordnet'); nltk.download('punkt'); nltk.download('punkt_tab')"
```

**API key:** A free NewsAPI key is required. Replace the `NEWS_API_KEY` value at the top of `main.py` with your key.

---

## Getting Started (Anaconda)

```bash
# Create and activate a new environment
conda create -n news_aggregator python=3.11 -y
conda activate news_aggregator

# Install dependencies
pip install requests beautifulsoup4 pandas numpy matplotlib wordcloud nltk

# Download NLTK data
python -c "import nltk; nltk.download('stopwords'); nltk.download('wordnet'); nltk.download('punkt'); nltk.download('punkt_tab')"

# Run the application
python main.py
```

If `wordcloud` fails to install via pip, try:
```bash
conda install -c conda-forge wordcloud
```

---

## Running the Tests

```bash
python -m unittest tests.test_all -v
```

No internet connection or API key is needed — all network calls are mocked.

---

## How to Use

### Fetching Articles
Select one or more categories using the checkboxes on the left panel, then click **Fetch Articles**. The total number of articles retrieved is shown below the button. Re-fetching the same category selection loads from cache and is indicated by a *(from cache)* label.

### Enriching with Web Scraping
Click **Initialise Enrichment** to retrieve full article text from the original web pages. The process runs in two phases in a background thread:
1. Probes one article per unique source to check whether scraping is available
2. Scrapes full text for all available sources and validates it against the API content

Scraped results are cached per URL, so re-running enrichment only processes new articles.

### Browsing Articles
The article list on the right shows titles numbered from 1 upward. Click any title to view its full details in the panel below. A green indicator means scraped content is being shown; grey means the API content is shown instead.

Use the **category dropdown** to filter by category and the **max articles** field to control how many titles appear in the list. Click **Apply Filter** or press Enter to update.

### Visualisations
Click **Visualisation Options** to open the visualisation window.

- **Pie Chart** — shows the proportion of articles fetched per category
- **Word Cloud + Bar Chart** — select a category and generate a word cloud alongside a ranked bar chart of the top 20 keywords extracted from articles in that category

Charts render inline in the same window. Switching between options replaces the current chart.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| 403 errors during scraping | Normal — some sites block automated requests. Those articles fall back to API content. |
| Visualisation shows no keywords | Run Enrich first to populate scraped content, then try again. |
| `ModuleNotFoundError: tests` | Use dots not slashes: `python -m unittest tests.test_all -v` |
| Tkinter not found | Run `conda install tk` |
| `wordcloud` install fails | Run `conda install -c conda-forge wordcloud` |
| NLTK LookupError | Re-run the NLTK download command above |
| API key error | Check `NEWS_API_KEY` in `main.py` matches your key from newsapi.org |
