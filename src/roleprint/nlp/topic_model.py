"""BERTopic wrapper for job posting topic modelling.

Model lifecycle:
- If ``models/topic_model.pkl`` exists: load and use it.
- If corpus >= MIN_DOCS: train a new model and save it.
- If corpus < MIN_DOCS: return empty topic dicts (not enough data).

The sentence-transformer model used is ``all-MiniLM-L6-v2`` (~80 MB).
Training is intentionally done once and the result persisted to disk.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)

_MODEL_PATH = Path("models/topic_model.pkl")
_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
MIN_DOCS = 50  # minimum corpus size to train
_EMPTY_TOPIC: dict = {}

# ── Model cache ───────────────────────────────────────────────────────────────

_topic_model: Any | None = None


def _load_or_none() -> Any | None:
    """Load a saved BERTopic model from disk, or return None."""
    global _topic_model
    if _topic_model is not None:
        return _topic_model
    if _MODEL_PATH.exists():
        with open(_MODEL_PATH, "rb") as fh:
            _topic_model = pickle.load(fh)
        log.info("topic_model.loaded", path=str(_MODEL_PATH))
    return _topic_model


def _save(model: Any) -> None:
    """Persist a trained BERTopic model to disk."""
    _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_MODEL_PATH, "wb") as fh:
        pickle.dump(model, fh)
    log.info("topic_model.saved", path=str(_MODEL_PATH))


# ── Public API ────────────────────────────────────────────────────────────────


def train(docs: list[str]) -> Any | None:
    """Train a BERTopic model on *docs* and save it to disk.

    Args:
        docs: List of cleaned job description strings (≥ MIN_DOCS recommended).

    Returns:
        Trained BERTopic model, or ``None`` if the corpus is too small or
        BERTopic is unavailable.
    """
    global _topic_model

    if len(docs) < MIN_DOCS:
        log.warning(
            "topic_model.insufficient_data",
            have=len(docs),
            need=MIN_DOCS,
        )
        return None

    try:
        from bertopic import BERTopic
        from sentence_transformers import SentenceTransformer
    except ImportError:
        log.warning("topic_model.bertopic_unavailable")
        return None

    log.info("topic_model.training", n_docs=len(docs), embedding=_EMBEDDING_MODEL)
    embedding_model = SentenceTransformer(_EMBEDDING_MODEL)
    model = BERTopic(embedding_model=embedding_model, verbose=False)
    model.fit(docs)
    _topic_model = model
    _save(model)
    log.info("topic_model.training_complete")
    return model


def get_or_train(docs: list[str]) -> Any | None:
    """Return saved model if available, otherwise train one.

    Args:
        docs: Full corpus to use if training is needed.

    Returns:
        BERTopic model or ``None``.
    """
    model = _load_or_none()
    if model is not None:
        return model
    return train(docs)


def assign_topics(
    texts: list[str],
    model: Any | None = None,
) -> list[dict]:
    """Assign a topic to each text in *texts*.

    Args:
        texts: Cleaned job description strings.
        model: BERTopic model.  When ``None``, ``_load_or_none()`` is tried.
               If no model is available, empty dicts are returned for each
               text — the pipeline continues gracefully.

    Returns:
        List of topic dicts, one per input text::

            {
                "topic_id": int,        # -1 = outlier
                "topic_label": str,     # e.g. "machine learning models"
                "probability": float,
            }
    """
    if model is None:
        model = _load_or_none()

    if model is None:
        return [_EMPTY_TOPIC] * len(texts)

    try:
        topic_ids, probs = model.transform(texts)
        topic_info = model.get_topic_info()
        id_to_label = dict(zip(topic_info["Topic"], topic_info["Name"]))

        results = []
        for tid, prob in zip(topic_ids, probs):
            results.append(
                {
                    "topic_id": int(tid),
                    "topic_label": id_to_label.get(int(tid), "unknown"),
                    "probability": round(float(prob), 4),
                }
            )
        return results

    except Exception as exc:
        log.error("topic_model.assignment_failed", error=str(exc))
        return [_EMPTY_TOPIC] * len(texts)


def reset() -> None:
    """Clear the in-memory model cache (useful in tests)."""
    global _topic_model
    _topic_model = None
