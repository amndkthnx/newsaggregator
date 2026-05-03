import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
from collections import Counter
import string

# Download necessary NLTK data (only run once)
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')
try:
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('wordnet')
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    # This specific resource seems to be required by word_tokenize internally
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab')

class FrequentKeywords:
    def __init__(self):
        self.stop_words = set(stopwords.words('english'))
        # Add common news-related stopwords or non-informative words
        self.stop_words.update(['said', 'say', 'says', 'one', 'would', 'could', 'also', 'told', 'us', 'new', 'get', 'like', 'news', 'story', 'article', 'full', 'text', 'first', 'chars', 'may', 'even', 'see', 'pro', 'year', 'use', 'used', 'time', 'day', '2026', 'study', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'type', 'result', 'using', 'scholar', 'season', 'business', 'entertainment', 'general', 'health', 'science', 'sports', 'technology', 'people', 'want', 'think', 'team', 'research', 'researcher', 'game', 'play', 'go', 'back', 'show', 'know'])
        self.lemmatizer = WordNetLemmatizer()

    def _preprocess_text(self, text):
        if not text or not isinstance(text, str):  # Handle empty, None, or NaN (float)
            return []
        # Convert to lowercase
        text = text.lower()
        # Remove punctuation
        text = text.translate(str.maketrans('', '', string.punctuation))
        # Tokenize words
        tokens = word_tokenize(text)
        return tokens

    def _remove_stopwords(self, tokens):
        return [word for word in tokens if word not in self.stop_words]

    def _lemmatize_tokens(self, tokens):
        return [self.lemmatizer.lemmatize(word) for word in tokens]

    def extract_keywords(self, article_content, top_n=10):
        # Preprocess, remove stopwords, and lemmatize
        tokens = self._preprocess_text(article_content)
        filtered_tokens = self._remove_stopwords(tokens)
        lemmatized_tokens = self._lemmatize_tokens(filtered_tokens)

        # Remove single-character tokens after lemmatization/filtering
        lemmatized_tokens = [word for word in lemmatized_tokens if len(word) > 1]

        # Count word frequencies
        word_counts = Counter(lemmatized_tokens)
        return word_counts.most_common(top_n)