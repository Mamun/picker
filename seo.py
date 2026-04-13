"""
SEO helpers for the Streamlit app.

Streamlit controls the <head> tag, so meta tags injected via st.markdown()
land in <body>.  The JS snippet below runs at page-load and upserts each tag
directly into <head>, where crawlers and social parsers expect them.
"""
import streamlit as st

# ── Target keywords (informed by what traders actually search) ─────────────────
_DESCRIPTION = (
    "Free stock market analyzer with real-time technical analysis. "
    "Scan S&P 500 for MA5/20/50/100/200, RSI, Fibonacci retracement, "
    "short squeeze setups, MA-200 bounce candidates, and Munger-quality "
    "stocks near their 200-week moving average."
)

_KEYWORDS = ", ".join([
    "stock technical analysis",
    "free stock screener",
    "S&P 500 screener",
    "moving average stock analysis",
    "RSI overbought oversold",
    "Fibonacci retracement calculator",
    "short squeeze scanner",
    "short interest analysis",
    "200 day moving average",
    "200 week moving average",
    "stock bounce radar",
    "MA200 support stocks",
    "Charlie Munger stock strategy",
    "buy quality stocks",
    "overbought stocks list",
    "oversold stocks list",
    "stock market analyzer",
    "candlestick reversal patterns",
    "trading signals",
    "weekly monthly stock screener",
])

_TITLE = "IndexIQ — Free S&P 500 Technical Analysis & Screener"

_JSON_LD = """{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebApplication",
      "name": "IndexIQ",
      "description": "Real-time technical analysis tool for S&P 500 stocks with moving averages, RSI, Fibonacci retracement, short squeeze scanner, bounce radar, and Munger quality watchlist.",
      "applicationCategory": "FinanceApplication",
      "operatingSystem": "Any (Web Browser)",
      "inLanguage": "en",
      "isAccessibleForFree": true,
      "offers": {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "USD"
      },
      "featureList": [
        "Moving averages MA5, MA20, MA50, MA100, MA200",
        "200-week moving average overlay",
        "RSI-14 overbought and oversold indicator",
        "Fibonacci retracement levels",
        "Candlestick reversal pattern detection (Hammer, Engulfing, Doji, Morning Star)",
        "S&P 500 weekly and monthly candle screener",
        "Short squeeze scanner with squeeze score",
        "Bounce radar for stocks near 200-day MA",
        "Charlie Munger quality stock watchlist near 200-week MA",
        "Buy and sell signal generation"
      ]
    },
    {
      "@type": "FAQPage",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "What is a short squeeze scanner?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "A short squeeze scanner finds overbought stocks with high short interest. When price rises, short sellers are forced to buy shares to cover losses, accelerating the move upward."
          }
        },
        {
          "@type": "Question",
          "name": "What is the 200-day moving average used for?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "The 200-day moving average is a key long-term support and resistance level. Stocks that dip to this level while oversold (RSI < 30) often produce bounce opportunities."
          }
        },
        {
          "@type": "Question",
          "name": "What is Charlie Munger's stock strategy?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Charlie Munger advocated buying high-quality companies — strong ROE, high profit margins, low debt, consistent earnings growth — at a fair price, ideally near their 200-week moving average."
          }
        },
        {
          "@type": "Question",
          "name": "How is the RSI indicator calculated?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "The Relative Strength Index (RSI-14) measures momentum over 14 periods using Wilder's smoothing. RSI above 70 signals overbought conditions; below 30 signals oversold."
          }
        }
      ]
    }
  ]
}"""


def inject_seo() -> None:
    """
    Call once at the top of app.py.
    Injects meta tags into <head> via JavaScript and emits JSON-LD into <body>.
    """
    # ── JS: upsert every meta/link tag into <head> ────────────────────────────
    meta_rows = [
        # Standard
        ("name",     "description",         _DESCRIPTION),
        ("name",     "keywords",             _KEYWORDS),
        ("name",     "author",               "IndexIQ"),
        ("name",     "robots",               "index, follow"),
        ("name",     "theme-color",          "#0F172A"),
        # OpenGraph
        ("property", "og:type",              "website"),
        ("property", "og:title",             _TITLE),
        ("property", "og:description",       _DESCRIPTION),
        ("property", "og:site_name",         "IndexIQ"),
        ("property", "og:locale",            "en_US"),
        # Twitter Card
        ("name",     "twitter:card",         "summary"),
        ("name",     "twitter:title",        _TITLE),
        ("name",     "twitter:description",  _DESCRIPTION),
    ]

    # Build JS upsert calls
    js_calls = []
    for attr, key, val in meta_rows:
        safe_val = val.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
        js_calls.append(
            f'  upsertMeta("{attr}", "{key}", "{safe_val}");'
        )

    script = f"""
<script>
(function() {{
  function upsertMeta(attr, key, content) {{
    var sel = 'meta[' + attr + '="' + key + '"]';
    var el = document.querySelector(sel);
    if (!el) {{
      el = document.createElement('meta');
      el.setAttribute(attr, key);
      document.head.appendChild(el);
    }}
    el.setAttribute('content', content);
  }}

  function upsertCanonical() {{
    var el = document.querySelector('link[rel="canonical"]');
    if (!el) {{
      el = document.createElement('link');
      el.rel = 'canonical';
      document.head.appendChild(el);
    }}
    el.href = window.location.origin + window.location.pathname;
  }}

  function setTitle() {{
    document.title = "{_TITLE}";
  }}

{chr(10).join(js_calls)}

  upsertCanonical();
  setTitle();
}})();
</script>
"""

    # ── JSON-LD structured data (valid anywhere in the document) ─────────────
    json_ld = f'<script type="application/ld+json">{_JSON_LD}</script>'

    st.markdown(script + "\n" + json_ld, unsafe_allow_html=True)
