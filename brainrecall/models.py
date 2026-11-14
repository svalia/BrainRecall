"""SQLAlchemy 2.0 ORM models for BrainRecall (Dev Spec v1.14 + Delta 1.1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from brainrecall.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Localization (Section 3.6)
    locale: Mapped[str] = mapped_column(String(16), default="ru", nullable=False)
    locale_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Rhythm & Preferences
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow", nullable=False)
    daily_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    daily_new_cap: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    haptics_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    achievement_effects_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    freeze_auto_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    analytics_consent: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ai_consent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ai_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Onboarding & Landing state
    landing_passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rhythm_configured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_activation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Account status
    analytics_user_id: Mapped[str] = mapped_column(String(36), unique=True, default=new_id, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)  # active / deleting / deleted
    session_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class TrialRegistry(Base):
    """Minimal anti-abuse record so trial is one-time per Telegram ID even after account reset."""

    __tablename__ = "trial_registry"

    telegram_id_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    trial_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    goal: Mapped[str] = mapped_column(String(64), default="free", nullable=False)  # exam / communication / work / personal / free
    goal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(64), default="topic-book", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)  # active / paused / archived / readonly
    paused_until: Mapped[str | None] = mapped_column(String(16), nullable=True)  # YYYY-MM-DD local
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    format: Mapped[str] = mapped_column(String(24), default="text", nullable=False)  # text / txt / md / pdf / docx / epub
    goal: Mapped[str] = mapped_column(String(64), default="free", nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="ru", nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="parsed", nullable=False
    )  # parsed / processing / review / accepted / failed / deleted
    source_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class SourceFragment(Base):
    __tablename__ = "source_fragments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    material_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("materials.id", ondelete="SET NULL"), index=True, nullable=True
    )
    material_title_snapshot: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    anchor_label: Mapped[str] = mapped_column(String(128), default="", nullable=False)  # e.g., "гл. 22 · абзац 6"
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapter_title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    paragraph_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_offset_start: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    char_offset_end: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quote_text: Mapped[str] = mapped_column(Text, nullable=False)
    context_before: Mapped[str] = mapped_column(Text, default="", nullable=False)
    context_after: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    operation_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    material_id: Mapped[str] = mapped_column(String(36), ForeignKey("materials.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    source_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    stage: Mapped[str] = mapped_column(
        String(32), default="queued", nullable=False
    )  # queued / extract / exercises / validate / ready / cancelled / failed
    reserved_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    committed_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    provider_input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    provider_output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    provider_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    candidates_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    relations_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    estimate_signature: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    import_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("import_jobs.id", ondelete="CASCADE"), index=True)
    material_id: Mapped[str] = mapped_column(String(36), ForeignKey("materials.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    candidate_kind: Mapped[str] = mapped_column(String(24), default="item", nullable=False)  # item / relation
    item_type: Mapped[str] = mapped_column(
        String(32), default="fact", nullable=False
    )  # fact / concept / word / formula / procedure / opinion / hypothesis
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    applicability: Mapped[str] = mapped_column(Text, default="", nullable=False)
    fragment_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("source_fragments.id", ondelete="SET NULL"))
    anchor_label: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    quote_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    warning_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(24), default="pending", nullable=False
    )  # pending / accepted / rejected
    accepted_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    material_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("materials.id", ondelete="SET NULL"), nullable=True
    )
    fragment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("source_fragments.id", ondelete="SET NULL"), nullable=True
    )
    item_type: Mapped[str] = mapped_column(
        String(32), default="fact", nullable=False
    )  # fact / concept / word / formula / procedure / opinion / hypothesis
    origin: Mapped[str] = mapped_column(String(24), default="manual", nullable=False)  # manual / ai_accepted
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    applicability: Mapped[str] = mapped_column(Text, default="", nullable=False)
    formula_expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    counterexample_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    rubric_criteria: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    applicable_objectives: Mapped[list[str]] = mapped_column(
        JSON, default=lambda: ["recall"], nullable=False
    )  # recall, explain, discriminate, relate, apply
    family_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contrast_set_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    intro_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), default="active", nullable=False
    )  # active / readonly / archived
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class KnowledgeGroup(Base):
    """M5 Meaning Group (D40 / D41): 2–7 existing items united by a principle."""

    __tablename__ = "knowledge_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    principle: Mapped[str] = mapped_column(Text, nullable=False)
    condition: Mapped[str] = mapped_column(Text, default="", nullable=False)
    example: Mapped[str] = mapped_column(Text, default="", nullable=False)
    counterexample: Mapped[str] = mapped_column(Text, default="", nullable=False)
    provenance: Mapped[str] = mapped_column(String(128), default="user", nullable=False)  # user / ai_draft / confirmed
    status: Mapped[str] = mapped_column(
        String(24), default="confirmed", nullable=False
    )  # draft / confirmed / needs_review / archived
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "item_id", name="uq_group_member"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_groups.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_items.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    role_label: Mapped[str] = mapped_column(String(64), default="basis", nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)


class KnowledgeRelation(Base):
    __tablename__ = "knowledge_relations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("knowledge_groups.id", ondelete="CASCADE"), index=True, nullable=True
    )
    from_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_items.id", ondelete="CASCADE"), index=True
    )
    to_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_items.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[str] = mapped_column(
        String(32), default="consequence", nullable=False
    )  # basis / consequence / strengthens / limits / example / counterexample / contrasts / condition_for / part_of
    direction: Mapped[str] = mapped_column(String(16), default="forward", nullable=False)  # forward / backward
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    provenance: Mapped[str] = mapped_column(String(32), default="user", nullable=False)  # user / ai_draft / source_anchor
    approval_status: Mapped[str] = mapped_column(
        String(24), default="confirmed", nullable=False
    )  # draft / confirmed / rejected / broken
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("knowledge_items.id", ondelete="CASCADE"), index=True, nullable=True
    )
    group_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("knowledge_groups.id", ondelete="CASCADE"), index=True, nullable=True
    )
    objective: Mapped[str] = mapped_column(
        String(32), default="recall", nullable=False
    )  # recall / explain / discriminate / relate / apply
    kind: Mapped[str] = mapped_column(
        String(32), default="free_text", nullable=False
    )  # free_text / self_recall / numeric / choice / discriminate_choice / explain_rubric / relate_pair / error_find
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    reference_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    hint_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    numeric_tolerance: Mapped[float | None] = mapped_column(Float, default=0.5, nullable=True)
    numeric_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rubric_criteria: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    allowed_support: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )  # e.g. ["formula"] for arithmetic calculation
    formula_support_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    science_method_ids: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["M1"], nullable=False)
    assessed_item_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)  # active / needs_review / archived
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ReviewState(Base):
    __tablename__ = "review_states"
    __table_args__ = (UniqueConstraint("owner_id", "scope_type", "scope_id", "objective", name="uq_review_scope_obj"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    scope_type: Mapped[str] = mapped_column(String(16), default="item", nullable=False)  # item / group
    scope_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    objective: Mapped[str] = mapped_column(
        String(32), default="recall", nullable=False
    )  # recall / explain / discriminate / relate / apply
    step_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0=new, 1=1d, 2=3d, 3=7d, 4=14d, 5=30d, 6=60d, 7=120d
    interval_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    independent_successes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_outcome: Mapped[str | None] = mapped_column(String(24), nullable=True)  # correct / partial / wrong / dont_know
    last_assisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_independent_success_date: Mapped[str | None] = mapped_column(String(16), nullable=True)  # YYYY-MM-DD local
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduler_version: Mapped[str] = mapped_column(String(16), default="v1.14", nullable=False)


class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    group_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("knowledge_groups.id", ondelete="SET NULL"), nullable=True
    )
    mode: Mapped[str] = mapped_column(
        String(32), default="regular", nullable=False
    )  # regular / intro / targeted_mix / group
    effective_mode: Mapped[str] = mapped_column(String(32), default="regular", nullable=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    queue_seed: Mapped[str] = mapped_column(String(36), default=new_id, nullable=False)
    queue_policy_version: Mapped[str] = mapped_column(String(16), default="v1.14", nullable=False)
    units: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    current_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_phase: Mapped[str] = mapped_column(
        String(32), default="attempt", nullable=False
    )  # attempt / feedback / corrective
    draft_answer: Mapped[str] = mapped_column(Text, default="", nullable=False)
    draft_support_seen: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), default="active", nullable=False
    )  # active / paused / completed / abandoned
    local_date: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("study_sessions.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("knowledge_items.id", ondelete="SET NULL"), index=True, nullable=True
    )
    group_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("knowledge_groups.id", ondelete="SET NULL"), index=True, nullable=True
    )
    exercise_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("exercises.id", ondelete="SET NULL"), nullable=True
    )
    parent_attempt_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    objective: Mapped[str] = mapped_column(String(32), default="recall", nullable=False)
    phase: Mapped[str] = mapped_column(
        String(24), default="first_attempt", nullable=False
    )  # first_attempt / corrective
    answer_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    answer_mode: Mapped[str] = mapped_column(String(24), default="written", nullable=False)  # written / aloud / choice
    grading_mode: Mapped[str] = mapped_column(
        String(24), default="self_check", nullable=False
    )  # exact / self_check / ai_rubric
    grade: Mapped[str] = mapped_column(
        String(24), default="correct", nullable=False
    )  # correct / partial / wrong / dont_know / uncertain
    assisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hint_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_seen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    map_seen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rubric_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    gap_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    disputed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dispute_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    elapsed_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hours_since_last_review: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    item_revision_snapshot: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    local_date: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)


class Habit(Base):
    __tablename__ = "habits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    linked_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("knowledge_items.id", ondelete="SET NULL"), nullable=True
    )
    habit_kind: Mapped[str] = mapped_column(String(24), default="build", nullable=False)  # build / replace
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    signal: Mapped[str] = mapped_column(String(256), nullable=False)
    action: Mapped[str] = mapped_column(String(256), nullable=False)
    minimum_version: Mapped[str] = mapped_column(String(256), nullable=False)
    environment_prep: Mapped[str] = mapped_column(Text, default="", nullable=False)
    attractiveness: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reward: Mapped[str] = mapped_column(Text, default="", nullable=False)
    obstacle: Mapped[str] = mapped_column(Text, default="", nullable=False)
    fallback_plan: Mapped[str] = mapped_column(Text, default="", nullable=False)
    unwanted_need: Mapped[str] = mapped_column(Text, default="", nullable=False)
    days_of_week: Mapped[list[int]] = mapped_column(
        JSON, default=lambda: [1, 2, 3, 4, 5, 6, 7], nullable=False
    )  # 1=Mon..7=Sun
    reminder_time: Mapped[str | None] = mapped_column(String(16), nullable=True)  # HH:MM
    status: Mapped[str] = mapped_column(
        String(24), default="active", nullable=False
    )  # active / paused / archived / readonly
    paused_from: Mapped[str | None] = mapped_column(String(16), nullable=True)
    paused_until: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class HabitOccurrence(Base):
    __tablename__ = "habit_occurrences"
    __table_args__ = (UniqueConstraint("habit_id", "local_date", name="uq_habit_local_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    habit_id: Mapped[str] = mapped_column(String(36), ForeignKey("habits.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    local_date: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # YYYY-MM-DD
    timezone_snapshot: Mapped[str] = mapped_column(String(64), default="Europe/Moscow", nullable=False)
    planned_opportunity: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    outcome: Mapped[str] = mapped_column(
        String(24), nullable=False
    )  # full_done / minimum_done / skipped / no_opportunity / planned_pause
    reason_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class DayPlan(Base):
    """Fixed daily plan snapshot (Section 7.1)."""

    __tablename__ = "day_plans"
    __table_args__ = (UniqueConstraint("owner_id", "local_date", name="uq_day_plan_user_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    local_date: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    timezone_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(16), default="v1.14", nullable=False)
    required_reviews_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required_reviews_done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required_habits_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required_habits_done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required_item_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    completed_item_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    required_habit_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    completed_habit_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    topic_requirements: Mapped[dict[str, dict[str, int]]] = mapped_column(JSON, default=dict, nullable=False)
    voluntary_practice_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    day_state: Mapped[str] = mapped_column(
        String(24), default="pending", nullable=False
    )  # pending / earned / missed / neutral / frozen
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class StreakAggregate(Base):
    __tablename__ = "streak_aggregates"
    __table_args__ = (UniqueConstraint("owner_id", "scope_type", "scope_id", name="uq_streak_scope"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)  # user / topic / habit
    scope_id: Mapped[str] = mapped_column(String(36), nullable=False)  # user.id or topic.id or habit.id
    current_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_earned_date: Mapped[str | None] = mapped_column(String(16), nullable=True)
    as_of_date: Mapped[str | None] = mapped_column(String(16), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class AchievementGrant(Base):
    __tablename__ = "achievement_grants"
    __table_args__ = (UniqueConstraint("owner_id", "scope_type", "scope_id", "threshold", name="uq_achievement_grant"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)  # user / topic / habit
    scope_id: Mapped[str] = mapped_column(String(36), nullable=False)
    scope_title_snapshot: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)  # 1,3,7,14,30,60,100,180,365
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)  # active / corrected
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CelebrationInbox(Base):
    __tablename__ = "celebration_inbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    grants_payload: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    highest_threshold: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    free_freeze_granted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ReturnNotice(Base):
    __tablename__ = "return_notices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    gap_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    scopes_payload: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    previous_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class FreezeLedger(Base):
    """Freeze ledger (Section 7.2): cap 2 in stock, free grant on 1st earned + every 7 earned."""

    __tablename__ = "freeze_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    entry_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # grant / purchase / consume / compensate / skipped_at_cap / refund
    origin_kind: Mapped[str] = mapped_column(String(16), default="free", nullable=False)  # free / paid
    amount_delta: Mapped[int] = mapped_column(Integer, nullable=False)  # +1, -1, 0
    balance_after: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    local_date: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RewardCycle(Base):
    __tablename__ = "reward_cycles"

    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    earned_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    starter_grant_issued: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_processed_threshold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class ProtectionInterval(Base):
    __tablename__ = "protection_intervals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[str] = mapped_column(String(16), nullable=False)  # YYYY-MM-DD inclusive
    end_date_exclusive: Mapped[str] = mapped_column(String(16), nullable=False)  # start_date + 7 days
    timezone_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(
        String(24), default="active", nullable=False
    )  # pending / active / completed / refunded / cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ProtectedDate(Base):
    __tablename__ = "protected_dates"
    __table_args__ = (UniqueConstraint("owner_id", "local_date", name="uq_protected_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    local_date: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)  # day_stock / week_interval
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    streak_saved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class UserMethodIntro(Base):
    """D42 preference state per user and method M1..M5 (Section 7.4)."""

    __tablename__ = "user_method_intros"
    __table_args__ = (UniqueConstraint("owner_id", "method_id", name="uq_user_method_intro"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    method_id: Mapped[str] = mapped_column(String(16), nullable=False)  # M1..M5
    status: Mapped[str] = mapped_column(String(24), default="unseen", nullable=False)  # unseen / dismissed / acknowledged
    intro_shown_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_content_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Entitlement(Base):
    __tablename__ = "entitlements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    plan_code: Mapped[str] = mapped_column(String(24), default="free", nullable=False)  # free / trial / start / pro
    plan_version: Mapped[str] = mapped_column(String(16), default="v1.14", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)  # active / expired / cancelled
    trial_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    period_id: Mapped[str] = mapped_column(String(64), default="free-default", nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    desired_next_plan: Mapped[str | None] = mapped_column(String(24), nullable=True)
    telegram_charge_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    downgrade_selection_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Period quotas used + reserved
    import_tokens_limit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    import_tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    import_tokens_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    ai_checks_limit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_checks_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_checks_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    ai_cases_limit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_cases_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_cases_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    ai_plans_limit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_plans_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_plans_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    ai_reviews_limit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_reviews_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_reviews_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class QuotaLedger(Base):
    __tablename__ = "quota_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    operation_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    period_id: Mapped[str] = mapped_column(String(64), nullable=False)
    resource: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # import_tokens / ai_checks / ai_cases / ai_plans / ai_reviews
    reserved_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    committed_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), default="reserved", nullable=False
    )  # reserved / committed / released
    provider_model: Mapped[str] = mapped_column(String(64), default="deepseek-chat", nullable=False)
    provider_input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    provider_output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    provider_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class PaymentOrder(Base):
    __tablename__ = "payment_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    product_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # plan_start / plan_pro / freeze_day / freeze_week
    plan_code: Mapped[str | None] = mapped_column(String(24), nullable=True)
    amount_xtr: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="XTR", nullable=False)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    week_start_date: Mapped[str | None] = mapped_column(String(16), nullable=True)
    invoice_payload: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    invoice_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_payment_charge_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(
        String(24), default="pending", nullable=False
    )  # pending / paid / cancelled / failed / refunded
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReminderPreference(Base):
    __tablename__ = "reminder_preferences"

    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    write_access_granted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bot_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    daily_time: Mapped[str] = mapped_column(String(16), default="08:30", nullable=False)
    quiet_start: Mapped[str] = mapped_column(String(16), default="22:00", nullable=False)
    quiet_end: Mapped[str] = mapped_column(String(16), default="08:00", nullable=False)
    days_of_week: Mapped[list[int]] = mapped_column(JSON, default=lambda: [1, 2, 3, 4, 5, 6, 7], nullable=False)
    last_sent_local_date: Mapped[str | None] = mapped_column(String(16), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class WeeklyReview(Base):
    __tablename__ = "weekly_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    period_label: Mapped[str] = mapped_column(String(64), nullable=False)
    stats_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_suggestions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="completed", nullable=False)  # pending / completed / failed
    download_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    json_payload: Mapped[str] = mapped_column(Text, default="", nullable=False)
    markdown_payload: Mapped[str] = mapped_column(Text, default="", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class DeletionJob(Base):
    __tablename__ = "deletion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    status_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)  # pending / completed / failed
    subscription_cancelled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    audit_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AnalyticsEvent(Base):
    """Canonical analytics storage / outbox (Section 3.8)."""

    __tablename__ = "analytics_events"
    __table_args__ = (Index("ix_analytics_user_event", "analytics_user_id", "event_name"),)

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), default="1.0", nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="server", nullable=False)  # client / bot / server
    analytics_user_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_properties: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    user_properties_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ProcessedTelegramUpdate(Base):
    __tablename__ = "processed_telegram_updates"

    update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
