#!/usr/bin/env python3
"""Seed 200 realistic fake job postings and run the full NLP pipeline on them.

This script generates deterministic demo data so the dashboard is not empty
on first deploy.  Run it once, pointed at your Supabase DATABASE_URL, before
the first Railway deploy:

    DATABASE_URL=postgresql+psycopg2://... python scripts/seed_demo_data.py

Options:
    --count N      Total postings to generate (default: 200)
    --weeks N      Spread postings across this many past weeks (default: 8)
    --roles R,R…   Comma-separated role list (default: 5 roles below)
    --dry-run      Print what would be inserted, don't write to DB
    --wipe         DELETE existing job_postings first (use carefully!)

The script is idempotent on re-runs: postings with duplicate URLs are skipped.
"""

from __future__ import annotations

import argparse
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

# ── Path bootstrap ─────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import os
os.environ.setdefault("DATABASE_URL", "sqlite:///demo_seed.db")

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from roleprint.db.base import Base
from roleprint.db.models import JobPosting
from roleprint.nlp.pipeline import run_all as nlp_run_all

# ── Seed corpus ───────────────────────────────────────────────────────────────

random.seed(42)  # deterministic across runs

# ── Companies ─────────────────────────────────────────────────────────────────

_COMPANIES = [
    "Monzo", "Revolut", "Deliveroo", "Wise", "Checkout.com",
    "Bumble", "Babylon Health", "Cazoo", "Starling Bank", "GoCardless",
    "Thought Machine", "Cleo", "Curve", "ComplyAdvantage", "Faculty AI",
    "Palantir", "Anthropic", "Scale AI", "Cohere", "Mistral AI",
    "Bloomberg", "Barclays Digital", "HSBC Technology", "Lloyds Tech", "NatWest Digital",
    "Accenture AI", "McKinsey Digital", "Bain & Company", "Deloitte Digital", "PwC Tech",
    "Airbnb", "Stripe", "Shopify", "Elastic", "Cloudflare",
    "Expedia Group", "Booking.com", "Just Eat", "Ocado Technology", "Farfetch",
]

_LOCATIONS = [
    "London, UK", "Remote (UK)", "Remote", "Manchester, UK",
    "Edinburgh, UK", "Bristol, UK", "London / Remote",
    "New York, NY", "San Francisco, CA", "Remote (US)",
    "Berlin, Germany", "Amsterdam, Netherlands",
]

_SOURCES = ["reed", "remoteok"]

# ── Role-specific skill pools ──────────────────────────────────────────────────
# Each skill is listed with a relative frequency weight (higher = more common).

_ROLE_CONFIG: Dict[str, dict] = {
    "data analyst": {
        "titles": [
            "Data Analyst", "Senior Data Analyst", "Business Intelligence Analyst",
            "Commercial Analyst", "Product Analyst", "Analytics Engineer",
            "Insight Analyst", "Marketing Data Analyst",
        ],
        "core_skills": ["SQL", "Python", "Excel"],
        "skill_pool": [
            ("SQL", 0.92), ("Python", 0.78), ("Excel", 0.65),
            ("Tableau", 0.52), ("Power BI", 0.48), ("dbt", 0.35),
            ("Snowflake", 0.30), ("BigQuery", 0.28), ("Looker", 0.22),
            ("pandas", 0.45), ("NumPy", 0.28), ("Spark", 0.15),
            ("stakeholder management", 0.60), ("agile", 0.40), ("scrum", 0.30),
            ("data storytelling", 0.35), ("A/B testing", 0.40),
            ("Redshift", 0.18), ("Airflow", 0.12), ("REST API", 0.20),
        ],
        "urgency_rate": 0.15,
    },
    "data engineer": {
        "titles": [
            "Data Engineer", "Senior Data Engineer", "Staff Data Engineer",
            "Analytics Engineer", "Platform Engineer (Data)", "DataOps Engineer",
        ],
        "core_skills": ["Python", "SQL", "Spark"],
        "skill_pool": [
            ("Python", 0.90), ("SQL", 0.82), ("Apache Spark", 0.60),
            ("Kafka", 0.50), ("Airflow", 0.55), ("dbt", 0.48),
            ("Snowflake", 0.42), ("BigQuery", 0.38), ("Redshift", 0.28),
            ("AWS", 0.55), ("GCP", 0.40), ("Azure", 0.30),
            ("Docker", 0.52), ("Kubernetes", 0.38), ("Terraform", 0.30),
            ("pandas", 0.48), ("CI/CD", 0.42), ("DataOps", 0.25),
            ("PostgreSQL", 0.45), ("MongoDB", 0.20), ("Redis", 0.22),
            ("REST API", 0.30), ("agile", 0.35),
        ],
        "urgency_rate": 0.20,
    },
    "ml engineer": {
        "titles": [
            "Machine Learning Engineer", "ML Engineer", "Senior ML Engineer",
            "Applied ML Engineer", "AI Engineer", "Staff ML Engineer",
            "MLOps Engineer", "Research Engineer",
        ],
        "core_skills": ["Python", "PyTorch", "TensorFlow"],
        "skill_pool": [
            ("Python", 0.95), ("PyTorch", 0.72), ("TensorFlow", 0.55),
            ("scikit-learn", 0.60), ("Kubernetes", 0.55), ("Docker", 0.65),
            ("AWS", 0.50), ("GCP", 0.38), ("Azure", 0.28),
            ("MLOps", 0.48), ("Spark", 0.30), ("Kafka", 0.28),
            ("pandas", 0.55), ("NumPy", 0.60), ("SQL", 0.45),
            ("CI/CD", 0.45), ("Terraform", 0.28), ("FastAPI", 0.32),
            ("Hugging Face", 0.38), ("LangChain", 0.25), ("RAG", 0.20),
        ],
        "urgency_rate": 0.25,
    },
    "software engineer": {
        "titles": [
            "Software Engineer", "Senior Software Engineer", "Backend Engineer",
            "Full Stack Engineer", "Staff Engineer", "Platform Engineer",
            "Software Developer", "Principal Engineer",
        ],
        "core_skills": ["Python", "Java", "REST API"],
        "skill_pool": [
            ("Python", 0.68), ("Java", 0.45), ("Go", 0.30), ("TypeScript", 0.38),
            ("React", 0.35), ("REST API", 0.72), ("GraphQL", 0.28),
            ("Docker", 0.68), ("Kubernetes", 0.55), ("AWS", 0.60),
            ("PostgreSQL", 0.55), ("Redis", 0.42), ("MongoDB", 0.32),
            ("CI/CD", 0.62), ("Terraform", 0.35), ("Kafka", 0.32),
            ("microservices", 0.45), ("agile", 0.55), ("scrum", 0.45),
            ("SQL", 0.52), ("GCP", 0.28), ("Azure", 0.25),
        ],
        "urgency_rate": 0.18,
    },
    "product manager": {
        "titles": [
            "Product Manager", "Senior Product Manager", "Principal PM",
            "Group Product Manager", "Technical Product Manager",
            "Product Lead", "Head of Product",
        ],
        "core_skills": ["agile", "scrum", "stakeholder management"],
        "skill_pool": [
            ("agile", 0.82), ("scrum", 0.68), ("stakeholder management", 0.78),
            ("cross-functional", 0.72), ("roadmap", 0.65),
            ("OKRs", 0.55), ("user research", 0.60), ("A/B testing", 0.52),
            ("data analysis", 0.58), ("SQL", 0.35), ("Python", 0.18),
            ("Jira", 0.55), ("Figma", 0.42), ("Notion", 0.28),
            ("go-to-market", 0.48), ("product strategy", 0.60),
            ("growth", 0.40), ("NPS", 0.32), ("analytics", 0.50),
            ("prioritisation", 0.62), ("discovery", 0.45),
        ],
        "urgency_rate": 0.12,
    },
}

# ── JD sentence templates ──────────────────────────────────────────────────────

_OPENING_TEMPLATES = [
    "We are looking for a talented {title} to join our growing team.",
    "An exciting opportunity for an experienced {title} to drive impact at scale.",
    "We're hiring a {title} to help us build the next generation of data products.",
    "Join our world-class engineering team as a {title}.",
    "{company} is seeking a motivated {title} to strengthen our data capabilities.",
    "We have an opening for a {title} who is passionate about solving complex problems.",
    "Are you an ambitious {title} ready to make your mark? We want to hear from you.",
    "We're looking for a {title} to own our analytics infrastructure end-to-end.",
]

_URGENCY_PHRASES = [
    "This is an urgent hire — we are looking to move quickly.",
    "We need someone to start immediately or with minimal notice.",
    "This role is available for an immediate start.",
    "We are looking to fill this position ASAP.",
    "Urgently seeking a candidate who can join within 2–4 weeks.",
]

_RESPONSIBILITY_TEMPLATES = [
    "You will work closely with {team} to deliver {outcome}.",
    "Design, build, and maintain {artifact} used across the organisation.",
    "Own the end-to-end development of {artifact}.",
    "Collaborate with {team} to define requirements and deliver solutions.",
    "Analyse large datasets to surface insights that drive {outcome}.",
    "Lead the technical strategy for {artifact} in partnership with {team}.",
    "Champion best practices across {artifact} development.",
    "Drive adoption of {artifact} across {team}.",
]

_TEAMS = [
    "the product team", "cross-functional squads", "data scientists",
    "engineering leads", "business stakeholders", "the analytics guild",
    "senior leadership", "external partners",
]

_OUTCOMES = [
    "business growth", "product improvements", "data-driven decisions",
    "engineering excellence", "customer experience improvements",
    "operational efficiency", "revenue targets",
]

_ARTIFACTS = [
    "data pipelines", "ML models", "dashboards", "APIs",
    "the data platform", "analytical frameworks", "forecasting systems",
    "recommendation engines", "feature stores",
]

_REQUIREMENTS_INTRO = [
    "The ideal candidate will have:",
    "What we're looking for:",
    "Requirements:",
    "You'll need:",
    "Essential skills:",
]


def _pick_skills(role_config: dict, n_skills: int = None) -> List[str]:
    """Sample skills from the role's pool using weighted probabilities."""
    pool = role_config["skill_pool"]
    n = n_skills or random.randint(4, 8)
    weights = [w for _, w in pool]
    total = sum(weights)
    normalised = [w / total for w in weights]
    chosen = []
    for skill, _ in random.choices(pool, weights=normalised, k=n * 3):
        if skill not in chosen:
            chosen.append(skill)
        if len(chosen) >= n:
            break
    # Always include at least one core skill
    core = role_config["core_skills"]
    if not any(s in chosen for s in core):
        chosen[0] = random.choice(core)
    return chosen


def _generate_jd(role: str, title: str, company: str, skills: List[str]) -> str:
    """Compose a realistic-looking job description that mentions all skills."""
    cfg = _ROLE_CONFIG[role]
    parts: List[str] = []

    # Opening paragraph
    opening = random.choice(_OPENING_TEMPLATES).format(title=title, company=company)
    parts.append(opening)
    parts.append("")

    # Optionally add urgency
    if random.random() < cfg["urgency_rate"]:
        parts.append(random.choice(_URGENCY_PHRASES))
        parts.append("")

    # About the role
    parts.append("About the role:")
    n_resp = random.randint(3, 5)
    for _ in range(n_resp):
        line = random.choice(_RESPONSIBILITY_TEMPLATES).format(
            team=random.choice(_TEAMS),
            outcome=random.choice(_OUTCOMES),
            artifact=random.choice(_ARTIFACTS),
        )
        parts.append(f"• {line}")
    parts.append("")

    # Requirements — embed the skills naturally
    parts.append(random.choice(_REQUIREMENTS_INTRO))
    # First, list skills as bullet points
    for skill in skills:
        qualifier = random.choice([
            f"Strong proficiency in {skill}.",
            f"Experience with {skill} in a production environment.",
            f"{skill} — essential for this role.",
            f"Hands-on {skill} experience required.",
            f"Comfort with {skill} and related tooling.",
            f"Solid understanding of {skill}.",
        ])
        parts.append(f"• {qualifier}")

    # Mention some skills again in prose for better extraction signal
    if len(skills) >= 2:
        s1, s2 = random.sample(skills[:min(4, len(skills))], 2)
        prose_templates = [
            f"You'll be working extensively with {s1} and {s2} on a daily basis.",
            f"Day-to-day you'll use {s1} alongside {s2} to deliver high-quality work.",
            f"We expect deep familiarity with {s1}; experience with {s2} is highly valued.",
        ]
        parts.append("")
        parts.append(random.choice(prose_templates))

    parts.append("")
    parts.append("What we offer:")
    parts.append(f"• Competitive salary and equity at {company}")
    parts.append("• Flexible remote / hybrid working")
    parts.append("• Generous learning and development budget")
    parts.append("• Inclusive, collaborative culture")

    return "\n".join(parts)


def generate_postings(
    total: int,
    weeks: int,
    roles: List[str],
) -> List[dict]:
    """Return a list of posting dicts ready to insert into job_postings."""
    postings = []
    per_role = total // len(roles)
    now = datetime.now(tz=timezone.utc)

    for role in roles:
        cfg = _ROLE_CONFIG[role]
        for i in range(per_role + (1 if role == roles[0] else 0)):
            # Distribute postings across `weeks` historical weeks
            # More recent weeks get slightly more postings (realistic ramp-up)
            week_weights = [w + 1 for w in range(weeks)]
            chosen_week = random.choices(range(weeks), weights=week_weights, k=1)[0]

            # Random day within that week, random time of day
            days_ago = (weeks - 1 - chosen_week) * 7 + random.randint(0, 6)
            hours_ago = random.randint(0, 23)
            scraped_at = now - timedelta(days=days_ago, hours=hours_ago)

            company = random.choice(_COMPANIES)
            title = random.choice(cfg["titles"])
            location = random.choice(_LOCATIONS)
            source = random.choice(_SOURCES)
            skills = _pick_skills(cfg)
            raw_text = _generate_jd(role, title, company, skills)

            # Stable URL derived from role + index so reruns are idempotent
            url = f"https://seed.roleprint.io/{role.replace(' ', '-')}/{i:04d}"

            postings.append({
                "id": uuid.uuid4(),
                "source": source,
                "role_category": role,
                "title": title,
                "company": company,
                "location": location,
                "raw_text": raw_text,
                "url": url,
                "scraped_at": scraped_at,
                "is_processed": False,
            })

    random.shuffle(postings)
    return postings[:total]  # trim to exact count


def insert_postings(session: Session, postings: List[dict], dry_run: bool) -> int:
    """Insert postings, skipping URLs that already exist. Returns inserted count."""
    from sqlalchemy import select
    from roleprint.db.models import JobPosting

    existing_urls = set(session.scalars(
        select(JobPosting.url).where(
            JobPosting.url.in_([p["url"] for p in postings])
        )
    ))

    to_insert = [p for p in postings if p["url"] not in existing_urls]
    skipped = len(postings) - len(to_insert)

    if skipped:
        print(f"  Skipping {skipped} postings (URLs already in DB)")

    if dry_run:
        print(f"  [dry-run] Would insert {len(to_insert)} postings")
        for p in to_insert[:5]:
            print(f"    {p['role_category']:20s}  {p['title']:30s}  {p['company']}")
        if len(to_insert) > 5:
            print(f"    … and {len(to_insert) - 5} more")
        return 0

    for p in to_insert:
        obj = JobPosting(**p)
        session.add(obj)

    session.commit()
    print(f"  Inserted {len(to_insert)} postings")
    return len(to_insert)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=200, help="Total postings (default: 200)")
    parser.add_argument("--weeks", type=int, default=8, help="Historical spread in weeks (default: 8)")
    parser.add_argument(
        "--roles",
        default=",".join(list(_ROLE_CONFIG.keys())[:5]),
        help="Comma-separated role categories",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print without writing to DB")
    parser.add_argument("--wipe", action="store_true", help="Delete existing postings first")
    args = parser.parse_args()

    roles = [r.strip() for r in args.roles.split(",") if r.strip() in _ROLE_CONFIG]
    if not roles:
        print(f"Error: no valid roles. Choose from: {list(_ROLE_CONFIG.keys())}")
        sys.exit(1)

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("Error: DATABASE_URL environment variable is not set.")
        sys.exit(1)

    print(f"\nRoleprint demo seed")
    print(f"  DATABASE_URL : {db_url[:40]}…" if len(db_url) > 40 else f"  DATABASE_URL : {db_url}")
    print(f"  Roles        : {roles}")
    print(f"  Count        : {args.count}")
    print(f"  Weeks spread : {args.weeks}")
    print(f"  Dry run      : {args.dry_run}")
    print()

    engine = create_engine(db_url, pool_pre_ping=True)

    # Create tables if they don't exist yet (safe for fresh Supabase DBs;
    # for production prefer `alembic upgrade head` instead)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        if args.wipe and not args.dry_run:
            confirm = input("  ⚠  This will DELETE all job_postings. Type 'yes' to confirm: ")
            if confirm.strip().lower() != "yes":
                print("  Aborted.")
                sys.exit(0)
            session.execute(text("DELETE FROM processed_postings"))
            session.execute(text("DELETE FROM skill_trends"))
            session.execute(text("DELETE FROM job_postings"))
            session.commit()
            print("  Existing data wiped.")

        print("Generating postings…")
        postings = generate_postings(args.count, args.weeks, roles)

        print(f"Inserting into {db_url.split('@')[-1] if '@' in db_url else 'database'}…")
        inserted = insert_postings(session, postings, dry_run=args.dry_run)

    if args.dry_run or inserted == 0:
        print("\nDry-run complete. No data written.")
        return

    # ── Run NLP pipeline ──────────────────────────────────────────────────────
    print(f"\nRunning NLP pipeline on {inserted} new postings…")
    print("(This may take a few minutes for the first run — models load lazily)")

    # Temporarily override DATABASE_URL so pipeline's SessionLocal uses it
    os.environ["DATABASE_URL"] = db_url

    try:
        stats = nlp_run_all()
        print(f"\nNLP pipeline complete:")
        print(f"  processed : {stats.get('processed', '?')}")
        print(f"  failed    : {stats.get('failed', '?')}")
        print(f"  skipped   : {stats.get('skipped', '?')}")
    except Exception as exc:
        print(f"\n⚠  NLP pipeline error: {exc}")
        print("  You can re-run the pipeline manually with:")
        print("    PYTHONPATH=src python -m roleprint.nlp.pipeline")

    print(f"\nSeed complete. {inserted} postings ready.")
    print("Start the API server and open the dashboard to explore the data.")


if __name__ == "__main__":
    main()
