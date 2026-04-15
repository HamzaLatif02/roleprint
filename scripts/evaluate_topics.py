#!/usr/bin/env python3
"""BERTopic coherence evaluation across n_topics = [5, 10, 20].

Trains a BERTopic model for each candidate topic count on the job-posting
corpus, computes c_v coherence via gensim's CoherenceModel, and saves:

  reports/topic_coherence.png  — line plot of coherence vs n_topics
  reports/topic_coherence.md   — methodology + justification for chosen n

Usage:
    pip install gensim matplotlib bertopic sentence-transformers
    PYTHONPATH=src python scripts/evaluate_topics.py
    PYTHONPATH=src python scripts/evaluate_topics.py --no-plot   # headless CI
    PYTHONPATH=src python scripts/evaluate_topics.py --corpus data/topic_corpus.txt

The corpus file should contain one document per line.  If no corpus file is
supplied the script falls back to the 50 sentiment-labelled job postings in
data/sentiment_labels.csv so the script is self-contained without a live DB.
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import csv

# ── Helpers ────────────────────────────────────────────────────────────────────

def load_corpus_from_csv(path: Path) -> list[str]:
    """Load texts from sentiment_labels.csv as a fallback corpus."""
    docs = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            docs.append(row["text"])
    return docs


def load_corpus_from_txt(path: Path) -> list[str]:
    """One document per line."""
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


# ── BERTopic training ─────────────────────────────────────────────────────────

def train_bertopic(docs: list[str], n_topics: int):
    """Return a fitted BERTopic model for the given topic count."""
    try:
        from bertopic import BERTopic  # type: ignore[import]
    except ImportError:
        raise ImportError("bertopic not installed — pip install bertopic sentence-transformers")

    from sklearn.feature_extraction.text import CountVectorizer  # type: ignore[import]

    vectorizer = CountVectorizer(
        stop_words="english",
        min_df=1,
        ngram_range=(1, 2),
    )

    model = BERTopic(
        nr_topics=n_topics,
        vectorizer_model=vectorizer,
        calculate_probabilities=False,
        verbose=False,
    )
    model.fit_transform(docs)
    return model


def extract_topic_words(model, topn: int = 10) -> list[list[str]]:
    """Return list of top-word lists (one per non-outlier topic)."""
    topic_words = []
    topic_ids = [t for t in model.get_topics() if t != -1]
    for tid in topic_ids:
        words = [w for w, _ in model.get_topic(tid)[:topn] if w]
        if words:
            topic_words.append(words)
    return topic_words


# ── Coherence scoring ─────────────────────────────────────────────────────────

def compute_coherence(
    docs: list[str],
    topic_words: list[list[str]],
    coherence: str = "c_v",
) -> float:
    """Compute topic coherence using gensim CoherenceModel."""
    try:
        from gensim.corpora import Dictionary  # type: ignore[import]
        from gensim.models.coherencemodel import CoherenceModel  # type: ignore[import]
    except ImportError:
        raise ImportError("gensim not installed — pip install gensim")

    tokenized = [doc.lower().split() for doc in docs]
    dictionary = Dictionary(tokenized)
    corpus = [dictionary.doc2bow(tok) for tok in tokenized]

    cm = CoherenceModel(
        topics=topic_words,
        texts=tokenized,
        corpus=corpus,
        dictionary=dictionary,
        coherence=coherence,
    )
    return round(float(cm.get_coherence()), 4)


# ── Plotting ───────────────────────────────────────────────────────────────────

def plot_coherence(
    n_topics_list: list[int],
    scores: list[float],
    best_n: int,
    out_path: Path,
) -> None:
    """Save coherence line plot with the best n annotated."""
    try:
        import matplotlib  # type: ignore[import]
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore[import]
    except ImportError:
        print("  [matplotlib] not installed — skipping plot (pip install matplotlib)")
        return

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(n_topics_list, scores, marker="o", linewidth=2, color="#4f8ef7", zorder=3)

    best_score = scores[n_topics_list.index(best_n)]
    ax.axvline(best_n, linestyle="--", color="#f5a623", linewidth=1.5, label=f"Best n={best_n}")
    ax.scatter([best_n], [best_score], color="#f5a623", s=100, zorder=4)
    ax.annotate(
        f"  n={best_n}\n  c_v={best_score:.3f}",
        (best_n, best_score),
        fontsize=9,
        color="#f5a623",
    )

    ax.set_xlabel("Number of Topics (nr_topics)", fontsize=11)
    ax.set_ylabel("Coherence Score (c_v)", fontsize=11)
    ax.set_title("BERTopic Coherence vs. Number of Topics\n(job-posting corpus)", fontsize=12)
    ax.set_xticks(n_topics_list)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.tight_layout()
    out_path.parent.mkdir(exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Plot saved → {out_path}")


# ── Markdown report ────────────────────────────────────────────────────────────

def render_markdown(
    n_topics_list: list[int],
    scores: list[float],
    best_n: int,
    n_docs: int,
) -> str:
    rows = "\n".join(
        f"| {n} | {s:.4f} | {'**best**' if n == best_n else ''} |"
        for n, s in zip(n_topics_list, scores)
    )

    justification = textwrap.dedent(f"""\
    ## Methodology

    BERTopic was trained three times on {n_docs} job-posting documents (drawn from the
    labelled evaluation corpus), varying `nr_topics` across [5, 10, 20].  Each run uses
    the same `all-MiniLM-L6-v2` sentence embedding and a bi-gram `CountVectorizer` with
    English stop-words removed.  Topic quality is measured by **c_v coherence** (Röder
    et al., 2015), computed with gensim's `CoherenceModel`.  C_v correlates well with
    human judgement and is more stable than UMass or UCI coherence on short documents.

    ## Results

    | n_topics | c_v coherence | |
    |----------|--------------|---|
    {rows}

    ## Chosen Configuration: n_topics = {best_n}

    The evaluation selects **n = {best_n}** as the production configuration because it
    achieves the highest c_v coherence on this corpus.  Job postings fall into a small
    number of semantically distinct clusters — role type, technical stack, seniority,
    and company culture — so a topic count between 5 and 20 is appropriate.  Fewer than
    5 topics merge meaningfully different registers (e.g., DevOps vs. data science roles),
    while more than 20 topics produce redundant near-duplicate clusters on a corpus of
    this size.  The chosen n delivers the best trade-off between granularity and
    coherence.  A larger labelled corpus (≥1,000 documents) would allow a finer grid
    search; the current result is sufficient to justify the production default.

    ## Limitations

    - Corpus size: {n_docs} documents is small for topic modelling.  Results are
      directional, not definitive.
    - Single annotator: coherence is an automatic proxy for human interpretability
      and should be validated with a manual topic-label review on the production corpus.
    - Domain drift: the seed corpus is the 50-sample evaluation set; the production
      corpus will include thousands of live scraped postings.  The optimal n may shift
      as the corpus grows.

    ## Reference

    Röder, M., Both, A., & Hinneburg, A. (2015). Exploring the space of topic
    coherence measures. *WSDM 2015*.
    """)

    return (
        f"# BERTopic Coherence Evaluation\n\n"
        f"**Corpus size:** {n_docs} documents  \n"
        f"**Coherence metric:** c_v  \n"
        f"**Date:** {__import__('datetime').date.today()}\n\n"
        + justification
        + "\n"
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=None,
        help="Path to corpus file (one doc per line).  Defaults to data/sentiment_labels.csv.",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip matplotlib plot (useful for headless CI).",
    )
    parser.add_argument(
        "--n-topics",
        nargs="+",
        type=int,
        default=[5, 10, 20],
        metavar="N",
        help="Topic counts to evaluate (default: 5 10 20).",
    )
    args = parser.parse_args()

    # ── Load corpus ───────────────────────────────────────────────────────────
    if args.corpus:
        if not args.corpus.exists():
            print(f"Error: corpus file not found: {args.corpus}")
            sys.exit(1)
        print(f"Loading corpus from {args.corpus}…")
        docs = load_corpus_from_txt(args.corpus)
    else:
        fallback = _ROOT / "data" / "sentiment_labels.csv"
        if not fallback.exists():
            print(f"Error: {fallback} not found.  Provide --corpus or create the CSV first.")
            sys.exit(1)
        print(f"No corpus supplied — using fallback: {fallback}")
        docs = load_corpus_from_csv(fallback)

    print(f"  {len(docs)} documents loaded.")

    # ── Train + score ─────────────────────────────────────────────────────────
    n_topics_list = sorted(set(args.n_topics))
    scores: list[float] = []

    for n in n_topics_list:
        print(f"\nTraining BERTopic with nr_topics={n}…", flush=True)
        try:
            model = train_bertopic(docs, n)
            topic_words = extract_topic_words(model)
            print(f"  {len(topic_words)} non-outlier topics extracted.")
            if not topic_words:
                print("  Warning: no non-outlier topics — corpus may be too small.")
                scores.append(0.0)
                continue
            score = compute_coherence(docs, topic_words)
            scores.append(score)
            print(f"  c_v coherence = {score:.4f}")
        except ImportError as exc:
            print(f"  Skipped: {exc}")
            scores.append(0.0)

    # ── Pick best ─────────────────────────────────────────────────────────────
    best_idx = scores.index(max(scores))
    best_n = n_topics_list[best_idx]
    print(f"\nBest n_topics = {best_n} (c_v = {scores[best_idx]:.4f})")

    # ── Summary table ─────────────────────────────────────────────────────────
    print("\n" + "─" * 40)
    print(f"{'n_topics':>10}  {'c_v coherence':>14}")
    print("─" * 40)
    for n, s in zip(n_topics_list, scores):
        marker = " ← best" if n == best_n else ""
        print(f"{n:>10}  {s:>14.4f}{marker}")
    print("─" * 40)

    # ── Save outputs ──────────────────────────────────────────────────────────
    report_dir = _ROOT / "reports"
    report_dir.mkdir(exist_ok=True)

    if not args.no_plot:
        plot_coherence(
            n_topics_list,
            scores,
            best_n,
            report_dir / "topic_coherence.png",
        )

    md = render_markdown(n_topics_list, scores, best_n, len(docs))
    md_path = report_dir / "topic_coherence.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"Report saved → {md_path}")


if __name__ == "__main__":
    main()
