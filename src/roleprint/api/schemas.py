"""Pydantic response models for the Roleprint API.

Every public endpoint has a typed response model here.
Models are separated from ORM models (no SQLAlchemy coupling).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── /api/skills/trending ──────────────────────────────────────────────────────


class SkillTrendItem(BaseModel):
    skill: str
    role_category: str
    mention_count: int
    pct_of_postings: float = Field(
        ge=0.0, description="Fraction of postings mentioning this skill (0–1)"
    )
    wow_change: float = Field(description="Week-over-week % change")
    is_rising: bool = Field(description="True when wow_change > 20 %")


class SkillTrendPage(BaseModel):
    data: List[SkillTrendItem]
    page: int
    page_size: int
    total_count: int
    total_pages: int
    has_next: bool
    has_prev: bool


# ── /api/skills/compare ───────────────────────────────────────────────────────


class RoleSkillProfile(BaseModel):
    top_skills: List[str] = Field(description="Top skills by pct_of_postings")
    unique_skills: List[str] = Field(description="Skills not present in the other role")


class SkillCompareResponse(BaseModel):
    roles: List[str]
    overlap_pct: float = Field(
        ge=0.0,
        le=100.0,
        description="Jaccard similarity × 100 across skill sets",
    )
    similarity_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Cosine similarity of pct_of_postings vectors",
    )
    shared_skills: List[str]
    role_profiles: Dict[str, RoleSkillProfile]


# ── /api/topics ───────────────────────────────────────────────────────────────


class TopicItem(BaseModel):
    topic_id: int
    topic_label: str
    posting_count: int
    avg_probability: float


# ── /api/sentiment/timeline ───────────────────────────────────────────────────


class SentimentWeek(BaseModel):
    week: str = Field(description="ISO date string of the Monday week-start")
    avg_sentiment: float = Field(ge=-1.0, le=1.0)
    urgency_score: int = Field(ge=0, description="Sum of urgency phrase hits that week")
    posting_count: int


# ── /api/roles ────────────────────────────────────────────────────────────────


class RoleItem(BaseModel):
    role_category: str
    posting_count: int
    processed_count: int
    unprocessed_count: int


# ── /api/skills/emerging ─────────────────────────────────────────────────────


class EmergingSkillItem(BaseModel):
    skill: str
    role_category: str
    growth_pct: float
    current_count: int
    old_count: int
    current_week: str


# ── /api/postings/recent ─────────────────────────────────────────────────────


class PostingItem(BaseModel):
    id: str
    title: str
    company: str
    location: str
    url: str
    source: str
    role_category: str
    scraped_at: str
    posted_at: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    sentiment_score: Optional[float] = None
    topics: Dict[str, Any] = Field(default_factory=dict)
    entities: Dict[str, Any] = Field(default_factory=dict)


class PaginatedPostings(BaseModel):
    data: List[PostingItem]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_count: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    has_next: bool
    has_prev: bool


# ── /api/stats/summary ────────────────────────────────────────────────────────


class StatsSummary(BaseModel):
    total_postings: int
    processed_postings: int
    unprocessed_postings: int
    last_updated: Optional[str] = None
    last_scraped: Optional[str] = Field(
        default=None,
        description="ISO timestamp of the most recent scraped_at in job_postings for the queried scope",
    )
    roles_tracked: int
    weeks_of_data: int
    sources: List[str] = Field(default_factory=list)


# ── /api/skills/gap ──────────────────────────────────────────────────────────


class SkillGapRequest(BaseModel):
    role_category: str = Field(description="Role to analyse, e.g. 'data analyst'")
    user_skills: List[str] = Field(description="Skills the user already has")


class SkillGapSkillItem(BaseModel):
    skill: str
    pct: float = Field(description="Demand % — share of postings that mention this skill (0-100)")
    status: str = Field(description="'matched', 'missing', or 'bonus'")


class SkillGapResponse(BaseModel):
    role_category: str
    match_score: float = Field(ge=0.0, le=100.0, description="% of top-30 skills the user has")
    matched_skills: List[SkillGapSkillItem]
    missing_skills: List[SkillGapSkillItem]
    bonus_skills: List[SkillGapSkillItem]
    total_postings_analysed: int


# ── /health ───────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = Field(description="'ok' or 'degraded'")
    db: str = Field(description="'connected' or error message")
    redis: str = Field(description="'connected' or 'unavailable'")
    version: str
