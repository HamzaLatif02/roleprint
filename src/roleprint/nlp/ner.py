"""Named Entity Recognition for job postings.

Uses spaCy's ``en_core_web_sm`` model to extract:
- ORG  — organisations (companies, tools treated as products/orgs)
- GPE  — geo-political entities (cities, countries)
- PRODUCT — product names
- LOC  — non-GPE locations (e.g. "the City")

The ``extract_entities`` function accepts an optional pre-loaded spaCy model
so callers (and tests) can inject a mock or reuse a shared model instance.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)

# Entity labels we care about
_KEPT_LABELS = {"ORG", "GPE", "PRODUCT", "LOC"}

# Known tech tools/frameworks that spaCy mis-labels or misses entirely.
# These are injected as synthetic ORG entities.
_TECH_OVERRIDE_PATTERNS = [
    "Python",
    "SQL",
    "dbt",
    "Spark",
    "Kafka",
    "Airflow",
    "Kubernetes",
    "Docker",
    "Terraform",
    "React",
    "TypeScript",
    "PostgreSQL",
    "Snowflake",
    "Databricks",
    "Redis",
    "FastAPI",
    "Django",
    "Flask",
    "PyTorch",
    "TensorFlow",
    "scikit-learn",
    "pandas",
    "NumPy",
    "Tableau",
    "Power BI",
]

# ── spaCy loader ──────────────────────────────────────────────────────────────

_nlp = None


def get_nlp() -> Any:
    """Load and cache ``en_core_web_sm``.  Raises ``RuntimeError`` if missing."""
    global _nlp
    if _nlp is None:
        import spacy

        try:
            _nlp = spacy.load("en_core_web_sm")
            log.debug("ner.model_loaded", model="en_core_web_sm")
        except OSError as exc:
            raise RuntimeError(
                "spaCy model 'en_core_web_sm' not found.\n"
                "Run: python -m spacy download en_core_web_sm"
            ) from exc
    return _nlp


# ── Public API ────────────────────────────────────────────────────────────────


def extract_entities(
    text: str,
    nlp: Optional[Any] = None,
) -> Dict[str, List[str]]:
    """Extract named entities from *text*.

    Args:
        text: Cleaned job description (original casing preferred — NER
              models are sensitive to capitalisation).
        nlp:  Loaded spaCy model.  When ``None``, ``get_nlp()`` is called
              to load the default model.  Pass a mock here in tests.

    Returns:
        Dict with string lists:
        ``{"orgs": [...], "locations": [...], "products": [...]}``

        Entities are deduplicated and sorted alphabetically.
    """
    if not text or not text.strip():
        return {"orgs": [], "locations": [], "products": []}

    if nlp is None:
        nlp = get_nlp()

    doc = nlp(text)
    buckets: Dict[str, set] = defaultdict(set)

    for ent in doc.ents:
        label = ent.label_
        entity_text = ent.text.strip()
        if not entity_text:
            continue

        if label == "ORG":
            buckets["orgs"].add(entity_text)
        elif label in ("GPE", "LOC"):
            buckets["locations"].add(entity_text)
        elif label == "PRODUCT":
            buckets["products"].add(entity_text)

    # Deduplicate and sort
    return {
        "orgs": sorted(buckets["orgs"]),
        "locations": sorted(buckets["locations"]),
        "products": sorted(buckets["products"]),
    }


def merge_tool_entities(
    entities: Dict[str, List[str]],
    skills: List[str],
) -> Dict[str, List[str]]:
    """Add recognised technical skills to the ``orgs`` bucket.

    spaCy's small model often fails to tag tools like "Kubernetes" or
    "Snowflake" as ORG.  This function supplements NER output by cross-
    referencing with the skill extraction results.

    Args:
        entities: Output of ``extract_entities``.
        skills:   List of skill names found by ``skill_extractor``.

    Returns:
        Updated entities dict (new dict, original not mutated).
    """
    orgs = set(entities.get("orgs", []))
    # Add technical skills that look like named tools (start with upper)
    for skill in skills:
        if skill[0].isupper():
            orgs.add(skill)
    return {**entities, "orgs": sorted(orgs)}
