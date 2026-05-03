"""
visualiser.py — Visualiser class
Wraps matplotlib/wordcloud plotting logic.
Called by main.py; never imports tkinter directly.
"""

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from collections import Counter

try:
    from wordcloud import WordCloud
    _WORDCLOUD_AVAILABLE = True
except ImportError:
    _WORDCLOUD_AVAILABLE = False

BG       = "#1a1a2e"
PANEL    = "#16213e"
ACCENT   = "#0f3460"
RED      = "#e94560"
TEXT     = "#eaeaea"
MUTED    = "#8892a4"
COLORS   = [RED, ACCENT, "#4a9eff", "#4caf50", "#ff9800", "#9c27b0", "#00bcd4"]


class Visualiser:
    """Produces matplotlib figures for the News Aggregator GUI."""

    # ── Internal figure builders ──────────────────────────────────────────────

    def _make_pie_figure(self, df: pd.DataFrame):
        """Return a matplotlib Figure for the category pie chart."""
        category_counts = df["category"].value_counts()
        fig, ax = plt.subplots(figsize=(6, 5))
        fig.patch.set_facecolor(BG)
        ax.set_facecolor(BG)
        wedges, texts, autotexts = ax.pie(
            category_counts,
            labels=category_counts.index,
            autopct="%1.1f%%",
            startangle=140,
            pctdistance=0.82,
            colors=COLORS[:len(category_counts)],
        )
        for t in texts:
            t.set_color(TEXT)
        for at in autotexts:
            at.set_color("#ffffff")
            at.set_fontsize(9)
        ax.set_title("Articles by Category", color=TEXT, fontsize=13, pad=16)
        ax.axis("equal")
        fig.tight_layout()
        return fig

    def _make_keywords_figure(self, df: pd.DataFrame, category: str, keyword_extractor):
        """Return a matplotlib Figure for the word cloud + bar chart."""
        cat_df = df[df["category"] == category] if "category" in df.columns else df

        all_keywords: Counter = Counter()
        for _, row in cat_df.iterrows():
            scraped     = row.get("content_scraping")
            api_content = row.get("content")
            api_desc    = row.get("description")
            scraped     = scraped     if isinstance(scraped,     str) else None
            api_content = api_content if isinstance(api_content, str) else None
            api_desc    = api_desc    if isinstance(api_desc,    str) else None
            content = scraped or api_content or api_desc or ""
            if content:
                kws = keyword_extractor.extract_keywords(content, top_n=None)
                all_keywords.update(dict(kws))

        if not all_keywords:
            return None

        top20  = all_keywords.most_common(20)
        words  = [w for w, _ in top20]
        counts = [c for _, c in top20]

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        fig.patch.set_facecolor(BG)

        # Word cloud
        ax_wc = axes[0]
        ax_wc.set_facecolor(BG)
        if _WORDCLOUD_AVAILABLE:
            wc = WordCloud(
                width=500, height=350,
                background_color=PANEL,
                colormap="RdYlBu",
                max_words=80,
            ).generate_from_frequencies(dict(all_keywords))
            ax_wc.imshow(wc, interpolation="bilinear")
        else:
            ax_wc.text(0.5, 0.5, "wordcloud not installed\npip install wordcloud",
                       ha="center", va="center", color=TEXT)
        ax_wc.axis("off")
        ax_wc.set_title(f"Word Cloud — {category.capitalize()}", color=TEXT, fontsize=12)

        # Bar chart
        ax_bar = axes[1]
        ax_bar.set_facecolor(PANEL)
        ax_bar.barh(words[::-1], counts[::-1], color=RED, edgecolor="none")
        ax_bar.set_xlabel("Frequency", color=MUTED)
        ax_bar.set_title("Top 20 Keywords", color=TEXT, fontsize=12)
        ax_bar.tick_params(colors=TEXT, labelsize=9)
        for spine in ax_bar.spines.values():
            spine.set_edgecolor(ACCENT)
        fig.patch.set_facecolor(BG)
        fig.tight_layout(pad=2)
        return fig

    # ── Embed into a frame (used by the inline vis window) ────────────────────

    def render_pie_chart(self, df: pd.DataFrame, container: tk.Frame):
        """Render pie chart into *container*, clearing any previous chart."""
        if df.empty or "category" not in df.columns:
            return
        self._clear_container(container)
        fig = self._make_pie_figure(df)
        self._embed_figure(fig, container)

    def render_keywords_chart(self, df: pd.DataFrame, category: str,
                               keyword_extractor, container: tk.Frame):
        """Render word cloud + bar chart into *container*."""
        cat_df = df[df["category"] == category] if "category" in df.columns else df
        if cat_df.empty:
            tk.Label(container, text=f"No articles found for '{category}'.",
                     bg=BG, fg=MUTED, font=("Helvetica", 11)).pack(expand=True)
            return
        self._clear_container(container)
        fig = self._make_keywords_figure(df, category, keyword_extractor)
        if fig is None:
            tk.Label(container, text="No keyword data available for this category.",
                     bg=BG, fg=MUTED, font=("Helvetica", 11)).pack(expand=True)
            return
        self._embed_figure(fig, container)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _clear_container(self, container: tk.Frame):
        """Destroy all child widgets and close any open matplotlib figures."""
        for widget in container.winfo_children():
            widget.destroy()
        plt.close("all")

    def _embed_figure(self, fig, container: tk.Frame):
        canvas = FigureCanvasTkAgg(fig, master=container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # ── Standalone Toplevel versions (kept for backwards compat) ──────────────

    def pie_chart(self, df: pd.DataFrame):
        if df.empty or "category" not in df.columns:
            return
        win = tk.Toplevel()
        win.title("Articles by Category")
        win.configure(bg=BG)
        fig = self._make_pie_figure(df)
        self._embed_figure(fig, win)

    def keywords_chart(self, df: pd.DataFrame, category: str, keyword_extractor):
        cat_df = df[df["category"] == category] if "category" in df.columns else df
        if cat_df.empty:
            return
        win = tk.Toplevel()
        win.title(f"Keywords — {category.capitalize()}")
        win.configure(bg=BG)
        fig = self._make_keywords_figure(df, category, keyword_extractor)
        if fig:
            self._embed_figure(fig, win)
