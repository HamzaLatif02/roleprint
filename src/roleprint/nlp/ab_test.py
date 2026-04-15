"""A/B comparison of two skill extraction strategies.

Extractor A — Vocabulary regex (production)
    Compiles word-boundary anchored regex patterns from the 130+ skill
    vocabulary in skills_vocab.json.  Longest-match wins.

Extractor B — spaCy noun-chunk heuristic
    Extracts noun chunks from en_core_web_sm, then retains only those
    that contain at least one token matching a known skill keyword
    (case-insensitive substring check).

Both extractors are evaluated against the gold standard in
data/skill_labels.csv: 30 job-posting excerpts with comma-separated
skill annotations.

Metrics per extractor
    precision  TP / (TP + FP)
    recall     TP / (TP + FN)
    F1         harmonic mean

Usage (standalone):
    PYTHONPATH=src python src/roleprint/nlp/ab_test.py
    PYTHONPATH=src python src/roleprint/nlp/ab_test.py --labels path/to/skill_labels.csv

Usage (programmatic):
    from roleprint.nlp.ab_test import run_ab_test
    results = run_ab_test(labels_path=Path("data/skill_labels.csv"))
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parents[4]

# ── Gold-standard loading ─────────────────────────────────────────────────────

def load_gold(path: Path) -> tuple[list[str], list[set[str]]]:
    """Return (texts, gold_skill_sets) from skill_labels.csv.

    Skills are normalised to lower-case for case-insensitive comparison.
    """
    texts, gold = [], []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            texts.append(row["text"])
            skills = {s.strip().lower() for s in row["skills"].split(",") if s.strip()}
            gold.append(skills)
    return texts, gold


# ── Extractor A: vocab regex (mirrors production SkillExtractor) ──────────────

def _build_vocab_extractor():
    """Return a callable that extracts skills using the production regex."""
    try:
        from roleprint.nlp.skill_extractor import SkillExtractor  # type: ignore[import]
        extractor = SkillExtractor()

        def _extract(text: str) -> set[str]:
            return {s.lower() for s in extractor.extract(text)}

        return _extract
    except Exception as exc:
        # Graceful degradation: if the module isn't importable, return empty set
        print(f"  [extractor A] could not load SkillExtractor: {exc}", file=sys.stderr)

        def _fallback(text: str) -> set[str]:  # noqa: ARG001
            return set()

        return _fallback


# ── Extractor B: spaCy noun-chunk heuristic ───────────────────────────────────

def _build_spacy_extractor(skill_keywords: Optional[set[str]] = None):
    """Return a callable that extracts skills via spaCy noun chunks.

    The noun-chunk approach:
    1. Run en_core_web_sm on the text.
    2. Collect all noun chunks.
    3. Keep only chunks whose lower-cased text contains a keyword from
       `skill_keywords` (or from a built-in seed list if none supplied).
    4. Normalise: strip leading determiners ("a", "an", "the", "our").
    """
    _SEED_KEYWORDS = {
        "python", "sql", "spark", "kafka", "airflow", "pytorch", "tensorflow",
        "kubernetes", "docker", "aws", "gcp", "azure", "react", "fastapi",
        "postgresql", "redis", "mongodb", "dbt", "snowflake", "tableau",
        "pandas", "numpy", "scikit", "mlops", "terraform", "typescript",
        "graphql", "looker", "bigquery", "databricks", "linux", "go", "rust",
        "nlp", "bert", "transformers", "sagemaker", "redshift", "power bi",
        "devops", "agile", "scrum", "okr",
    }
    keywords = skill_keywords if skill_keywords is not None else _SEED_KEYWORDS

    try:
        import spacy  # type: ignore[import]
    except ImportError:
        print("  [extractor B] spaCy not installed — pip install spacy && python -m spacy download en_core_web_sm", file=sys.stderr)

        def _no_spacy(text: str) -> set[str]:  # noqa: ARG001
            return set()

        return _no_spacy

    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        print("  [extractor B] en_core_web_sm not found — python -m spacy download en_core_web_sm", file=sys.stderr)

        def _no_model(text: str) -> set[str]:  # noqa: ARG001
            return set()

        return _no_model

    _DET = {"a", "an", "the", "our", "your", "their", "its", "this", "that"}

    def _extract(text: str) -> set[str]:
        doc = nlp(text)
        results: set[str] = set()
        for chunk in doc.noun_chunks:
            chunk_lower = chunk.text.lower().strip()
            # Retain only if any keyword appears as a substring
            if any(kw in chunk_lower for kw in keywords):
                # Strip leading determiners
                tokens = chunk_lower.split()
                while tokens and tokens[0] in _DET:
                    tokens = tokens[1:]
                if tokens:
                    results.add(" ".join(tokens))
        return results

    return _extract


# ── Metrics ───────────────────────────────────────────────────────────────────

def _prf(gold_sets: list[set[str]], pred_sets: list[set[str]]) -> dict[str, float]:
    """Macro-averaged precision, recall, F1 over all examples."""
    precisions, recalls, f1s = [], [], []
    for gold, pred in zip(gold_sets, pred_sets):
        tp = len(gold & pred)
        fp = len(pred - gold)
        fn = len(gold - pred)
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        precisions.append(p)
        recalls.append(r)
        f1s.append(f)

    n = len(gold_sets)
    return {
        "precision": round(sum(precisions) / n, 3),
        "recall": round(sum(recalls) / n, 3),
        "f1": round(sum(f1s) / n, 3),
    }


def _micro_prf(gold_sets: list[set[str]], pred_sets: list[set[str]]) -> dict[str, float]:
    """Micro-averaged precision, recall, F1 (aggregate TP/FP/FN)."""
    tp = fp = fn = 0
    for gold, pred in zip(gold_sets, pred_sets):
        tp += len(gold & pred)
        fp += len(pred - gold)
        fn += len(gold - pred)
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}


# ── Main entry point ──────────────────────────────────────────────────────────

def run_ab_test(labels_path: Optional[Path] = None) -> dict[str, dict]:
    """Run the A/B comparison and return results dict.

    Returns:
        {
            "A (vocab regex)": {"precision": ..., "recall": ..., "f1": ...,
                                "micro": {...}},
            "B (spaCy noun chunks)": {...},
        }
    """
    if labels_path is None:
        labels_path = _ROOT / "data" / "skill_labels.csv"

    if not labels_path.exists():
        raise FileNotFoundError(f"Gold standard not found: {labels_path}")

    texts, gold_sets = load_gold(labels_path)

    extractor_a = _build_vocab_extractor()
    extractor_b = _build_spacy_extractor()

    pred_a = [extractor_a(t) for t in texts]
    pred_b = [extractor_b(t) for t in texts]

    results = {
        "A (vocab regex)": {
            **_prf(gold_sets, pred_a),
            "micro": _micro_prf(gold_sets, pred_a),
        },
        "B (spaCy noun chunks)": {
            **_prf(gold_sets, pred_b),
            "micro": _micro_prf(gold_sets, pred_b),
        },
    }
    return results


def _print_results(results: dict[str, dict]) -> None:
    print("\n" + "═" * 64)
    print(f"{'Skill Extractor A/B Test':^64}")
    print("═" * 64)
    print(f"\n  {'Extractor':<28} {'Precision':>10} {'Recall':>8} {'F1':>8}")
    print(f"  {'─'*28} {'─'*10} {'─'*8} {'─'*8}")
    for name, r in results.items():
        print(f"  {name:<28} {r['precision']:>10.3f} {r['recall']:>8.3f} {r['f1']:>8.3f}")
    print()
    print("  Micro-averaged:")
    print(f"  {'─'*28} {'─'*10} {'─'*8} {'─'*8}")
    for name, r in results.items():
        m = r["micro"]
        print(f"  {name:<28} {m['precision']:>10.3f} {m['recall']:>8.3f} {m['f1']:>8.3f}")
    print("\n" + "═" * 64)

    best = max(results, key=lambda k: results[k]["f1"])
    print(f"\n  Winner (macro F1): {best}")
    diff = abs(results["A (vocab regex)"]["f1"] - results["B (spaCy noun chunks)"]["f1"])
    print(f"  F1 margin: {diff:.3f}")
    print()

    print("  Interpretation")
    print("  ──────────────")
    a = results["A (vocab regex)"]
    b = results["B (spaCy noun chunks)"]
    if a["f1"] >= b["f1"]:
        print("  Extractor A (vocab regex) achieves equal or higher F1.")
        print("  The curated vocabulary gives better precision — it avoids noun")
        print("  phrases that look like skills but aren't (e.g. 'strong background').")
        print("  Extractor B may have higher recall on novel or multi-word skills")
        print("  not yet in the vocabulary, at the cost of more false positives.")
    else:
        print("  Extractor B (spaCy noun chunks) achieves higher F1.")
        print("  Noun-chunk matching generalises better to multi-word and unlisted")
        print("  skills.  Consider expanding the vocabulary to capture these.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=None,
        help="Path to skill_labels.csv (default: data/skill_labels.csv relative to repo root)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-example predictions for manual inspection",
    )
    args = parser.parse_args()

    labels_path = args.labels or (_ROOT / "data" / "skill_labels.csv")
    if not labels_path.exists():
        print(f"Error: {labels_path} not found.")
        sys.exit(1)

    print(f"Loading gold standard: {labels_path}")
    texts, gold_sets = load_gold(labels_path)
    print(f"  {len(texts)} examples loaded.")

    print("\nBuilding extractors…")
    extractor_a = _build_vocab_extractor()
    extractor_b = _build_spacy_extractor()

    print("Running extractor A (vocab regex)…")
    pred_a = [extractor_a(t) for t in texts]

    print("Running extractor B (spaCy noun chunks)…")
    pred_b = [extractor_b(t) for t in texts]

    if args.verbose:
        print("\n  Per-example predictions:")
        header = f"  {'#':>3}  {'Gold':<40} {'A':<40} {'B':<40}"
        print(header)
        print("  " + "─" * (len(header) - 2))
        for i, (gold, a, b) in enumerate(zip(gold_sets, pred_a, pred_b), 1):
            print(
                f"  {i:>3}  {str(sorted(gold)):<40} {str(sorted(a)):<40} {str(sorted(b)):<40}"
            )

    results = {
        "A (vocab regex)": {
            **_prf(gold_sets, pred_a),
            "micro": _micro_prf(gold_sets, pred_a),
        },
        "B (spaCy noun chunks)": {
            **_prf(gold_sets, pred_b),
            "micro": _micro_prf(gold_sets, pred_b),
        },
    }
    _print_results(results)


if __name__ == "__main__":
    main()
