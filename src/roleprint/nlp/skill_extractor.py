"""Skill extraction from job posting text.

Primary method: regex vocabulary matching against skills_vocab.json.
Secondary method (optional): spaCy noun-chunk overlap for phrase discovery.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)

_VOCAB_PATH = Path(__file__).parent / "skills_vocab.json"

# ── Vocabulary loading ────────────────────────────────────────────────────────


def load_vocab(path: Path = _VOCAB_PATH) -> dict:
    """Load skills vocabulary from JSON.

    Returns a dict with keys ``"technical"`` (nested by category) and
    ``"soft"`` (flat list).
    """
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def flatten_vocab(vocab: dict) -> list[str]:
    """Return a flat list of all skill strings from the vocabulary."""
    skills: list[str] = []
    # Technical skills are nested by sub-category
    for category_skills in vocab.get("technical", {}).values():
        skills.extend(category_skills)
    # Soft skills are a flat list
    skills.extend(vocab.get("soft", []))
    return skills


def build_patterns(skills: list[str]) -> list[tuple[str, re.Pattern]]:
    """Compile one regex pattern per skill.

    Patterns use word-boundary anchors (``\\b``) to avoid partial matches.
    Skills are sorted longest-first so that "Apache Spark" matches before
    "Spark" when both are in the vocabulary.

    Returns:
        List of ``(canonical_skill_name, compiled_pattern)`` pairs.
    """
    # Deduplicate while preserving order
    seen: set = set()
    unique = []
    for s in skills:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)

    # Sort longest first to prefer specific matches
    unique.sort(key=len, reverse=True)

    patterns: list[tuple[str, re.Pattern]] = []
    for skill in unique:
        escaped = re.escape(skill)
        # Word boundary on both sides; also match at end of punctuation
        pattern = re.compile(
            r"(?<![a-zA-Z0-9_])" + escaped + r"(?![a-zA-Z0-9_])",
            re.IGNORECASE,
        )
        patterns.append((skill, pattern))

    return patterns


# ── Module-level singletons (loaded once) ────────────────────────────────────

_vocab: dict | None = None
_patterns: list[tuple[str, re.Pattern]] | None = None


def _ensure_loaded() -> None:
    global _vocab, _patterns
    if _patterns is None:
        _vocab = load_vocab()
        _patterns = build_patterns(flatten_vocab(_vocab))
        log.debug("skill_extractor.vocab_loaded", skill_count=len(_patterns))


# ── Public API ────────────────────────────────────────────────────────────────


def extract_skills(
    text: str,
    nlp: Any = None,
    min_count: int = 1,
) -> dict[str, int]:
    """Extract skills mentioned in *text*.

    Combines two approaches:
    1. **Vocabulary matching** (always): regex scan of the curated skills list.
    2. **Noun-chunk overlap** (when *nlp* is provided): spaCy noun chunks
       that overlap with vocab entries surface multi-word skills that may have
       been missed by regex.

    Args:
        text:      Cleaned job description text (original casing preserved).
        nlp:       Optional loaded spaCy model.  Pass ``None`` to skip
                   noun-chunk discovery (e.g. in unit tests).
        min_count: Drop skills with fewer than this many mentions.

    Returns:
        Dict mapping canonical skill name → mention count, sorted by count desc.
    """
    if not text or not text.strip():
        return {}

    _ensure_loaded()
    assert _patterns is not None

    counts: Counter = Counter()

    # ── 1. Vocabulary regex matching ─────────────────────────────────────────
    counts.update(_vocab_match(text))

    # ── 2. spaCy noun-chunk overlap (optional enhancement) ───────────────────
    if nlp is not None:
        counts.update(_spacy_noun_chunk_match(text, nlp))

    # Filter and sort
    result = {skill: cnt for skill, cnt in counts.items() if cnt >= min_count}
    return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))


def _vocab_match(text: str) -> Counter:
    """Pure regex scan — no external dependencies."""
    _ensure_loaded()
    assert _patterns is not None

    counts: Counter = Counter()
    for skill, pattern in _patterns:
        matches = pattern.findall(text)
        if matches:
            counts[skill] += len(matches)
    return counts


def _spacy_noun_chunk_match(text: str, nlp: Any) -> Counter:
    """Match spaCy noun chunks against the vocabulary.

    Only surfaces skills not already found by vocab matching.
    """
    _ensure_loaded()
    assert _patterns is not None

    doc = nlp(text)
    chunk_texts = {chunk.text.lower() for chunk in doc.noun_chunks}

    counts: Counter = Counter()
    for skill, _ in _patterns:
        if skill.lower() in chunk_texts:
            counts[skill] += 1
    return counts


def categorise_skills(skills: dict[str, int], vocab: dict | None = None) -> dict[str, list]:
    """Split extracted skills into ``technical`` and ``soft`` buckets.

    Args:
        skills: Output of ``extract_skills``.
        vocab:  Optional vocab dict; loaded from disk if not provided.

    Returns:
        ``{"technical": [...], "soft": [...]}``
    """
    if vocab is None:
        _ensure_loaded()
        vocab = _vocab

    assert vocab is not None

    soft_set = {s.lower() for s in vocab.get("soft", [])}
    technical: list[str] = []
    soft: list[str] = []

    for skill in skills:
        if skill.lower() in soft_set:
            soft.append(skill)
        else:
            technical.append(skill)

    return {"technical": technical, "soft": soft}
