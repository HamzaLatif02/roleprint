"""Sentiment analysis and urgency scoring for job descriptions.

Uses VADER (Valence Aware Dictionary and sEntiment Reasoner) — well-suited
to short, structured text like job ads, unlike model-based approaches that
need fine-tuning on this domain.
"""

from __future__ import annotations

import re

import structlog

log = structlog.get_logger(__name__)

# ── Urgency signal phrases ────────────────────────────────────────────────────
# Phrases that indicate time pressure or hiring urgency.

_URGENCY_PATTERNS: list = [
    re.compile(r"\basap\b", re.IGNORECASE),
    re.compile(r"\bimmediate(?:ly)?\b", re.IGNORECASE),
    re.compile(r"\bimmediately?\s+available\b", re.IGNORECASE),
    re.compile(r"\burgent(?:ly)?\b", re.IGNORECASE),
    re.compile(r"\bright\s+away\b", re.IGNORECASE),
    re.compile(r"\bstarting\s+immediately\b", re.IGNORECASE),
    re.compile(r"\bimmediate\s+start\b", re.IGNORECASE),
    re.compile(r"\bstart\s+(?:as\s+soon|immediately)\b", re.IGNORECASE),
    re.compile(r"\bno\s+delay\b", re.IGNORECASE),
    re.compile(r"\b(?:hiring\s+)?now\b", re.IGNORECASE),
    re.compile(r"\bdeadline\b", re.IGNORECASE),
    re.compile(r"\btime[\s-]sensitive\b", re.IGNORECASE),
    re.compile(r"\bfill\s+immediately\b", re.IGNORECASE),
]

# ── VADER loader ─────────────────────────────────────────────────────────────

_analyzer = None


def _get_analyzer():
    """Lazily load VADER, downloading the lexicon if missing."""
    global _analyzer
    if _analyzer is None:
        import nltk

        try:
            from nltk.sentiment.vader import SentimentIntensityAnalyzer
        except LookupError:
            log.info("sentiment.downloading_vader_lexicon")
            nltk.download("vader_lexicon", quiet=True)
            from nltk.sentiment.vader import SentimentIntensityAnalyzer
        _analyzer = SentimentIntensityAnalyzer()
        log.debug("sentiment.vader_loaded")
    return _analyzer


# ── Public API ────────────────────────────────────────────────────────────────


def analyse(text: str) -> dict[str, float]:
    """Compute sentiment and urgency signals for a job description.

    Args:
        text: Cleaned job description text.

    Returns:
        Dict with keys:
        - ``compound``:  VADER compound score in [-1.0, 1.0].
          Positive values indicate a warm/positive tone; negative values
          indicate a demanding/negative tone.
        - ``positive``:  VADER pos score  [0.0, 1.0].
        - ``negative``:  VADER neg score  [0.0, 1.0].
        - ``neutral``:   VADER neu score  [0.0, 1.0].
        - ``urgency``:   Count of urgency phrases detected.
    """
    if not text or not text.strip():
        return {
            "compound": 0.0,
            "positive": 0.0,
            "negative": 0.0,
            "neutral": 1.0,
            "urgency": 0,
        }

    analyzer = _get_analyzer()
    scores = analyzer.polarity_scores(text)

    urgency_count = count_urgency(text)

    return {
        "compound": round(scores["compound"], 4),
        "positive": round(scores["pos"], 4),
        "negative": round(scores["neg"], 4),
        "neutral": round(scores["neu"], 4),
        "urgency": urgency_count,
    }


def compound_score(text: str) -> float:
    """Return just the VADER compound score. Convenience wrapper."""
    return analyse(text)["compound"]


def count_urgency(text: str) -> int:
    """Count the number of urgency signal phrases found in *text*.

    Args:
        text: Any text string.

    Returns:
        Integer count of distinct urgency pattern matches.
    """
    if not text:
        return 0
    total = 0
    for pattern in _URGENCY_PATTERNS:
        total += len(pattern.findall(text))
    return total
