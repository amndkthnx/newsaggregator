# 📰 News Aggregator & Visualisation Tool  
## End-to-End News Intelligence Pipeline with NLP, Web Scraping & Interactive Analytics

A Python-based desktop application that implements a complete **data engineering and news intelligence pipeline**. The system collects live news from NewsAPI, enriches incomplete metadata using web scraping, processes text using NLP techniques, and visualises insights through an interactive Tkinter-based GUI.

This project demonstrates applied competencies in:
- API-based data acquisition
- Web scraping under real-world constraints
- NLP-based text processing and feature extraction
- Data engineering (caching, pipeline design, transformation)
- Software architecture and modular design
- Interactive data visualisation systems

---

# 👥 Team Members

| Member | Student ID |
|--------|------------|
| Amanda Kistilensa | 26029102 |
| Aryan Goel | 26040826 |
| Silvia |  |
| Kiemas Zn | 26054407 |

---

# 📌 Table of Contents

1. Project Overview  
2. Problem Definition  
3. System Architecture  
4. Design Decisions & Rationale  
5. Data Pipeline  
6. Key Features  
7. Technical Implementation  
8. Evaluation & Results  
9. Limitations  
10. Ethical Considerations  
11. Future Improvements  
12. Installation & Setup  
13. Usage Guide  
14. Testing Strategy  
15. Technologies Used  

---

# 1. 📊 Project Overview

Modern news consumption is fragmented across platforms, with limited ability to extract structured insights from live news streams.

This project addresses this gap by building a **unified news intelligence system** that:
- Aggregates real-time news from NewsAPI
- Enriches incomplete metadata via scraping
- Extracts meaningful keywords using NLP
- Visualises trends and distributions interactively
- Optimises performance using caching and concurrency

The system transforms unstructured, noisy news data into structured, analyzable insights.

---

# 2. ❗ Problem Definition

While NewsAPI provides structured metadata, it suffers from:
- Incomplete article content
- Limited analytical capability
- No built-in support for trend detection or summarisation

### 🎯 Research Question
> How can a scalable data pipeline transform raw news feeds into enriched, analyzable insights using NLP and web scraping under real-world constraints?

---

# 3. 🏗 System Architecture

## High-Level Pipeline

```text
NewsAPI
   ↓
API Client Layer
   ↓
Cache Layer (API Response Cache)
   ↓
Data Pipeline Orchestrator
   ↓
Web Scraper (BeautifulSoup)
   ↓
Validation Layer (Content Consistency Check)
   ↓
NLP Engine (NLTK)
   ↓
Feature Extraction Layer
   ↓
Visualisation Engine (Matplotlib / WordCloud)
   ↓
Tkinter GUI
```

---

## Design Principles

- **Modularity** → Each component is independently maintainable
- **Separation of Concerns** → Clear division between API, scraping, NLP, UI
- **Efficiency** → Multi-layer caching reduces redundant computation
- **Scalability** → Threaded execution prevents GUI blocking
- **Robustness** → Fallback mechanisms ensure system reliability

---

# 4. 🧠 Design Decisions & Rationale

## Choice of Tkinter
Tkinter was selected due to:
- Lightweight nature (no external UI dependencies)
- Native Python integration
- Sufficient for desktop-level interactive dashboards

## Caching Strategy
Two-layer caching was implemented:
- API Cache → reduces NewsAPI calls (rate limit mitigation)
- Scrape Cache → avoids repeated HTTP scraping overhead

## Web Scraping Fallback Design
Scraping is unreliable due to anti-bot protections. Therefore:
- System validates scrape success
- Automatically falls back to API content when blocked

## Threading Model
Background threads were used to:
- Maintain GUI responsiveness
- Prevent blocking during enrichment
- Improve perceived performance

---

# 5. 🔄 Data Pipeline

## Stage 1: Data Acquisition
- Fetch articles via NewsAPI
- Filter by category
- Store in API cache (JSON)

## Stage 2: Data Enrichment
- Extract article URLs
- Scrape full content using BeautifulSoup
- Validate against API summaries

## Stage 3: NLP Processing
- Tokenisation (NLTK)
- Stopword removal
- Frequency-based keyword extraction

## Stage 4: Insight Generation
- Keyword ranking
- Category distribution analysis
- Word cloud generation

---

# 6. 🚀 Key Features

## News Collection
- Up to 7 NewsAPI categories
- Structured metadata extraction (title, author, date, source)

## Content Enrichment
- Full article scraping
- Source validation layer
- Automatic fallback system

## Interactive GUI
- Tkinter-based desktop interface
- Article browsing system
- Filtering and search capability
- Real-time content preview

## Visual Analytics
- Category distribution pie chart
- Keyword frequency bar charts
- Word cloud generation per category

## Performance Optimisation
- Multi-threaded processing
- Two-layer caching architecture
- Reduced redundant API requests (~60–80% reduction)

---

# 7. ⚙ Technical Implementation

## Core Modules
- `main.py` → GUI controller
- `data_pipeline.py` → orchestration logic
- `news_api_client.py` → API interface
- `web_scraper.py` → HTML parsing
- `keyword_extractor.py` → NLP processing
- `visualiser.py` → charts & graphs

---

# 8. 📈 Evaluation & Results

## System Performance

| Metric | Outcome |
|--------|--------|
| API call reduction | ~60–80% via caching |
| UI responsiveness | Maintained via threading |
| Scraping reliability | Variable (site-dependent) |
| Test coverage | 42 unit tests (fully mocked) |

## Key Findings (Data Insights)

- News distribution is heavily category-skewed (some categories dominate content volume)
- Scraping success varies significantly across news sources due to bot protection
- Keyword extraction reveals strong repetition bias in news headlines
- API metadata alone is insufficient for meaningful NLP analysis

## System Effectiveness

The pipeline successfully demonstrates:
- End-to-end data transformation
- Real-world constraint handling (rate limits, scraping blocks)
- Scalable architecture for incremental data processing

---

# 9. ⚠ Limitations

- NewsAPI rate limits restrict large-scale usage
- Scraping is inconsistent due to anti-bot protections (403 errors)
- NLP is frequency-based (no semantic understanding or embeddings)
- No real-time streaming capability
- No persistent database layer (JSON-only caching)

---

# 10. 🧠 Ethical Considerations

- Only publicly available news data is accessed
- No personal user data is collected or stored
- API usage complies with NewsAPI terms
- Scraping respects fallback mechanisms when blocked
- System avoids bypassing restricted content

---

# 11. 🚀 Future Improvements

- Sentiment analysis using transformer models
- Named Entity Recognition (NER) for structured insights
- Topic modelling (LDA / BERTopic)
- Real-time streaming news ingestion
- Database integration (SQLite/PostgreSQL)
- Web-based dashboard (Streamlit/Dash)
- Machine learning recommendation system

---

# 12. 📦 Installation

```bash
pip install requests beautifulsoup4 pandas numpy matplotlib wordcloud nltk
```

## NLTK Setup
```bash
python -c "import nltk; nltk.download('stopwords'); nltk.download('wordnet'); nltk.download('punkt')"
```

---

# 13. 🖥 Usage

1. Fetch Articles → Select categories
2. Enrichment → Extract full text
3. Browse → View articles
4. Visualise → Explore trends

---

# 14. 🧪 Testing Strategy

- 42 unit tests
- Fully mocked API layer
- No external dependency required
- Validates:
  - caching logic
  - scraping fallback
  - pipeline consistency

```bash
python -m unittest tests.test_all -v
```

---

# 15. 🛠 Technologies Used

| Category | Tools |
|----------|------|
| Language | Python 3.11 |
| GUI | Tkinter |
| API | NewsAPI |
| Scraping | BeautifulSoup |
| NLP | NLTK |
| Data | Pandas, NumPy |
| Visualisation | Matplotlib, WordCloud |
| Testing | unittest |
| Storage | JSON caching |

---

# 🏁 Conclusion

This project demonstrates a complete **end-to-end data engineering pipeline** integrating real-time data acquisition, web scraping, NLP processing, and interactive visual analytics.

The system highlights strong software engineering principles including modular architecture, performance optimisation, and robustness under real-world constraints.

Overall, the project successfully transforms raw, unstructured news data into structured and meaningful analytical insights suitable for decision-making and trend analysis.