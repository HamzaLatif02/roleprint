"""Text cleaning for raw job posting content.

Strips HTML, removes boilerplate, and normalises whitespace.
All functions are pure (no I/O) and return a cleaned string.
"""

from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup

# ── Boilerplate patterns ──────────────────────────────────────────────────────
# Ordered from most specific to most general so the earlier patterns
# don't eat text needed by later ones.

_BOILERPLATE_PATTERNS: list = [
    # Equal opportunities / diversity
    r"we are an equal\s+opportunit(?:y|ies)\s+employer[^.]*\.",
    r"equal\s+opportunit(?:y|ies)\s+employer[^.]*\.",
    r"equal\s+opportunit(?:y|ies)\s+and\s+diversity[^.]*\.",
    r"we\s+celebrate\s+diversity[^.]*\.",
    r"we\s+(?:are\s+)?committed\s+to\s+(?:a\s+)?(?:diverse|inclusive)[^.]*\.",
    r"diversity[,\s]+equity[,\s]+and\s+inclusion[^.]*\.",
    r"dei\b[^.]*\.",
    # Right to work / legal
    r"applicants\s+must\s+(?:have\s+the\s+)?(?:right|eligibility)\s+to\s+work\s+in\s+(?:the\s+)?(?:uk|united\s+kingdom)[^.]*\.",
    r"right\s+to\s+work\s+in\s+(?:the\s+)?(?:uk|united\s+kingdom)[^.]*\.",
    r"criminal\s+records?\s+(?:bureau\s+)?(?:check|disclosure)[^.]*\.",
    r"dbs\s+check[^.]*\.",
    r"this\s+role\s+is\s+subject\s+to[^.]*\.",
    # GDPR / data handling
    r"by\s+submitting\s+(?:your\s+)?(?:application|cv)[^.]*gdpr[^.]*\.",
    r"in\s+line\s+with\s+gdpr[^.]*\.",
    r"your\s+data\s+will\s+be\s+(?:processed|stored|held)[^.]*\.",
    # Recruitment agency boilerplate
    r"no\s+agencies\s+please[^.]*\.",
    r"agency\s+applications?\s+will\s+not\s+be\s+(?:accepted|considered)[^.]*\.",
    r"please\s+do\s+not\s+contact\s+us\s+directly[^.]*\.",
    # Salary / benefits admin text
    r"salary\s+will\s+be\s+(?:discussed|confirmed|revealed)[^.]*\.",
    r"competitive\s+salary\s+(?:and\s+benefits?\s+)?package[^.]*\.",
]

_COMPILED_BOILERPLATE = [
    re.compile(pat, re.IGNORECASE | re.DOTALL) for pat in _BOILERPLATE_PATTERNS
]

# Collapse 3+ newlines to 2
_MULTI_NEWLINE = re.compile(r"\n{3,}")
# Collapse runs of spaces / tabs
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
# Bullet characters → dash for uniform tokenisation
_BULLET_CHARS = re.compile(r"[•·▪▸►‣⁃✓✗✘★☆]")


# ── Public API ────────────────────────────────────────────────────────────────


def strip_html(text: str) -> str:
    """Remove all HTML/XML tags and decode entities.

    Args:
        text: Raw text that may contain HTML markup.

    Returns:
        Plain text with tags removed and HTML entities decoded.
    """
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(separator=" ")


def remove_boilerplate(text: str) -> str:
    """Strip common job-posting boilerplate sentences.

    Patterns include equal-opportunities disclaimers, GDPR notices,
    right-to-work clauses, and agency notices.

    Args:
        text: Plain-text job description.

    Returns:
        Text with boilerplate sentences removed.
    """
    for pattern in _COMPILED_BOILERPLATE:
        text = pattern.sub("", text)
    return text


def normalise_whitespace(text: str) -> str:
    """Collapse runs of whitespace and strip leading/trailing space."""
    text = _BULLET_CHARS.sub("-", text)
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def normalise_unicode(text: str) -> str:
    """Replace fancy quotes/dashes and normalise to NFC unicode form."""
    # Smart quotes → plain quotes
    replacements = {
        "\u2018": "'",
        "\u2019": "'",  # left/right single quotation marks
        "\u201c": '"',
        "\u201d": '"',  # left/right double quotation marks
        "\u2013": "-",
        "\u2014": "-",  # en-dash, em-dash
        "\u00a0": " ",  # non-breaking space
        "\u2022": "-",  # bullet
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return unicodedata.normalize("NFC", text)


def clean(text: str) -> str:
    """Full cleaning pipeline: HTML → boilerplate → unicode → whitespace.

    This is the main entry point.  The returned text is suitable for
    downstream NLP (skill extraction, sentiment, NER).

    Args:
        text: Raw job description text (may include HTML).

    Returns:
        Cleaned plain text, original casing preserved.
    """
    if not text or not text.strip():
        return ""

    text = strip_html(text)
    text = normalise_unicode(text)
    text = remove_boilerplate(text)
    text = normalise_whitespace(text)
    return text


def clean_for_analysis(text: str) -> str:
    """Return ``clean(text)`` lowercased, for case-insensitive NLP analysis."""
    return clean(text).lower()
