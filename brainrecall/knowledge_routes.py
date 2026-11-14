"""Knowledge domain service & API routes: Topics, Knowledge Items, Source Fragments, Search, and M5 Meaning Groups & Relations (D04-D09, D34, D40, D41)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from brainrecall.analytics import analytics
from brainrecall.config import PLAN_LIMITS
from brainrecall.db import get_session
from brainrecall.i18n import resolve_user_locale, t
from brainrecall.models import (
    Entitlement,
    Exercise,
    GroupMember,
    KnowledgeGroup,
    KnowledgeItem,
    KnowledgeRelation,
    Material,
    ReviewState,
    SourceFragment,
    Topic,
    User,
)
from brainrecall.security import get_current_user

router = APIRouter(prefix="/api/v1", tags=["knowledge"])

VALID_ITEM_TYPES = {"fact", "concept", "word", "formula", "procedure", "opinion", "hypothesis"}
VALID_OBJECTIVES = {"recall", "explain", "discriminate", "relate", "apply"}
VALID_RELATION_TYPES = {
    "basis",
    "consequence",
    "strengthens",
    "limits",
    "example",
    "counterexample",
    "contrasts",
    "condition_for",
    "part_of",
}


class TopicCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(default="free", max_length=64)
    goal_note: str | None = Field(default=None, max_length=500)
    icon: str = Field(default="topic-book", max_length=64)


class TopicUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    goal: str | None = Field(default=None, max_length=64)
    goal_note: str | None = Field(default=None, max_length=500)
    icon: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, pattern="^(active|paused|archived)$")
    paused_until: str | None = None
    revision: int | None = None


class KnowledgeItemCreateRequest(BaseModel):
    topic_id: str
    item_type: str = Field(default="fact")
    prompt: str = Field(..., min_length=1, max_length=2000)
    answer: str = Field(..., min_length=1, max_length=4000)
    applicability: str = Field(default="", max_length=1000)
    formula_expression: str | None = Field(default=None, max_length=500)
    example_text: str = Field(default="", max_length=2000)
    counterexample_text: str = Field(default="", max_length=2000)
    rubric_criteria: list[str] = Field(default_factory=list)
    applicable_objectives: list[str] = Field(default_factory=lambda: ["recall"])
    quote_text: str | None = Field(default=None, max_length=4000)
    anchor_label: str | None = Field(default=None, max_length=128)
    material_title_snapshot: str | None = Field(default=None, max_length=256)


class KnowledgeItemUpdateRequest(BaseModel):
    item_type: str | None = None
    prompt: str | None = Field(default=None, min_length=1, max_length=2000)
    answer: str | None = Field(default=None, min_length=1, max_length=4000)
    applicability: str | None = Field(default=None, max_length=1000)
    formula_expression: str | None = None
    example_text: str | None = None
    counterexample_text: str | None = None
    rubric_criteria: list[str] | None = None
    applicable_objectives: list[str] | None = None
    status: str | None = Field(default=None, pattern="^(active|archived)$")
    quote_text: str | None = None
    anchor_label: str | None = None
    revision: int | None = None


class GroupMemberInput(BaseModel):
    item_id: str
    role_label: str = Field(default="basis", max_length=64)
    explanation: str = Field(default="", max_length=1000)


class RelationInput(BaseModel):
    from_item_id: str
    to_item_id: str
    relation_type: str = Field(default="consequence")
    direction: str = Field(default="forward", pattern="^(forward|backward)$")
    explanation: str = Field(default="", max_length=1000)


class KnowledgeGroupCreateRequest(BaseModel):
    topic_id: str
    title: str = Field(..., min_length=1, max_length=256)
    principle: str = Field(..., min_length=1, max_length=2000)
    condition: str = Field(default="", max_length=1000)
    example: str = Field(default="", max_length=1000)
    counterexample: str = Field(default="", max_length=1000)
    members: list[GroupMemberInput] = Field(..., min_length=2, max_length=7)
    relations: list[RelationInput] = Field(default_factory=list)


class KnowledgeGroupUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    principle: str | None = Field(default=None, min_length=1, max_length=2000)
    condition: str | None = None
    example: str | None = None
    counterexample: str | None = None
    status: str | None = Field(default=None, pattern="^(draft|confirmed|needs_review|archived)$")
    members: list[GroupMemberInput] | None = None
    relations: list[RelationInput] | None = None
    revision: int | None = None


async def _get_user_plan_limits(session: AsyncSession, user: User) -> tuple[str, dict[str, Any]]:
    res = await session.execute(select(Entitlement).where(Entitlement.owner_id == user.id))
    ent = res.scalar_one_or_none()
    plan_code = ent.plan_code if (ent and ent.status == "active") else "free"
    return plan_code, PLAN_LIMITS.get(plan_code, PLAN_LIMITS["free"])


async def _ensure_item_exercises_and_review_states(
    session: AsyncSession,
    item: KnowledgeItem,
) -> None:
    objectives = [obj for obj in item.applicable_objectives if obj in VALID_OBJECTIVES]
    if not objectives:
        objectives = ["recall"]

    now = datetime.now(timezone.utc)
    for obj in objectives:
        rs_res = await session.execute(
            select(ReviewState).where(
                ReviewState.owner_id == item.owner_id,
                ReviewState.scope_type == "item",
                ReviewState.scope_id == item.id,
                ReviewState.objective == obj,
            )
        )
        if rs_res.scalar_one_or_none() is None:
            session.add(
                ReviewState(
                    owner_id=item.owner_id,
                    topic_id=item.topic_id,
                    scope_type="item",
                    scope_id=item.id,
                    objective=obj,
                    step_index=0,
                    interval_days=0,
                    due_at=now,
                )
            )

        ex_res = await session.execute(
            select(Exercise).where(
                Exercise.owner_id == item.owner_id,
                Exercise.item_id == item.id,
                Exercise.objective == obj,
            )
        )
        existing_ex = ex_res.scalar_one_or_none()
        kind = "free_text"
        methods = ["M1", "M2"]
        allowed_support: list[str] = []
        if obj == "explain":
            kind = "explain_rubric"
            methods = ["M4", "M1"]
        elif obj == "discriminate":
            kind = "discriminate_choice"
            methods = ["M3", "M1"]
        elif obj == "apply" and item.formula_expression:
            kind = "numeric"
            methods = ["M3", "M1"]
            allowed_support = ["formula"]

        criteria = item.rubric_criteria if item.rubric_criteria else [item.answer[:140]]
        if existing_ex is None:
            session.add(
                Exercise(
                    owner_id=item.owner_id,
                    topic_id=item.topic_id,
                    item_id=item.id,
                    objective=obj,
                    kind=kind,
                    prompt=item.prompt,
                    reference_answer=item.answer,
                    explanation=item.applicability or item.answer,
                    rubric_criteria=criteria,
                    allowed_support=allowed_support,
                    formula_support_text=item.formula_expression if "formula" in allowed_support else None,
                    science_method_ids=methods,
                    assessed_item_ids=[item.id],
                )
            )
        else:
            existing_ex.prompt = item.prompt
            existing_ex.reference_answer = item.answer
            existing_ex.explanation = item.applicability or item.answer
            existing_ex.rubric_criteria = criteria
            existing_ex.formula_support_text = item.formula_expression if "formula" in allowed_support else None


async def _ensure_group_exercises_and_review_state(
    session: AsyncSession,
    group: KnowledgeGroup,
    member_item_ids: list[str],
    relations: list[KnowledgeRelation],
) -> None:
    now = datetime.now(timezone.utc)
    rs_res = await session.execute(
        select(ReviewState).where(
            ReviewState.owner_id == group.owner_id,
            ReviewState.scope_type == "group",
            ReviewState.scope_id == group.id,
            ReviewState.objective == "relate",
        )
    )
    if rs_res.scalar_one_or_none() is None:
        session.add(
            ReviewState(
                owner_id=group.owner_id,
                topic_id=group.topic_id,
                scope_type="group",
                scope_id=group.id,
                objective="relate",
                step_index=0,
                interval_days=0,
                due_at=now,
            )
        )

    ex_res = await session.execute(
        select(Exercise).where(
            Exercise.owner_id == group.owner_id,
            Exercise.group_id == group.id,
            Exercise.objective == "relate",
        )
    )
    existing_ex = ex_res.scalar_one_or_none()
    rel_summary = (
        relations[0].explanation
        if relations and relations[0].explanation
        else group.principle
    )
    options = [
        {"id": r_type, "label": r_type, "correct": bool(relations and relations[0].relation_type == r_type)}
        for r_type in ("basis", "consequence", "contrasts", "condition_for")
    ]
    if existing_ex is None:
        session.add(
            Exercise(
                owner_id=group.owner_id,
                topic_id=group.topic_id,
                group_id=group.id,
                objective="relate",
                kind="relate_pair",
                prompt=f"{group.title}: {group.principle}",
                reference_answer=rel_summary,
                explanation=group.condition or group.principle,
                options=options,
                rubric_criteria=[group.principle, rel_summary],
                science_method_ids=["M5", "M1"],
                assessed_item_ids=member_item_ids,
            )
        )
    else:
        existing_ex.prompt = f"{group.title}: {group.principle}"
        existing_ex.reference_answer = rel_summary
        existing_ex.explanation = group.condition or group.principle
        existing_ex.options = options
        existing_ex.assessed_item_ids = member_item_ids


def _serialize_topic(topic: Topic, items_count: int = 0, groups_count: int = 0, due_count: int = 0) -> dict[str, Any]:
    return {
        "id": topic.id,
        "title": topic.title,
        "goal": topic.goal,
        "goal_note": topic.goal_note or "",
        "icon": topic.icon,
        "priority": topic.priority,
        "status": topic.status,
        "paused_until": topic.paused_until,
        "revision": topic.revision,
        "items_count": items_count,
        "groups_count": groups_count,
        "due_count": due_count,
        "created_at": topic.created_at.isoformat(),
        "updated_at": topic.updated_at.isoformat(),
    }


def _serialize_item(item: KnowledgeItem, fragment: SourceFragment | None = None) -> dict[str, Any]:
    return {
        "id": item.id,
        "topic_id": item.topic_id,
        "material_id": item.material_id,
        "fragment_id": item.fragment_id,
        "item_type": item.item_type,
        "origin": item.origin,
        "prompt": item.prompt,
        "answer": item.answer,
        "applicability": item.applicability,
        "formula_expression": item.formula_expression,
        "example_text": item.example_text,
        "counterexample_text": item.counterexample_text,
        "rubric_criteria": item.rubric_criteria or [],
        "applicable_objectives": item.applicable_objectives or ["recall"],
        "intro_completed": item.intro_completed,
        "status": item.status,
        "revision": item.revision,
        "source_fragment": (
            {
                "id": fragment.id,
                "material_title_snapshot": fragment.material_title_snapshot,
                "anchor_label": fragment.anchor_label,
                "quote_text": fragment.quote_text,
                "context_before": fragment.context_before,
                "context_after": fragment.context_after,
                "source_deleted": fragment.source_deleted,
            }
            if fragment
            else None
        ),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


@router.get("/topics")
async def list_topics(
    status_filter: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    stmt = select(Topic).where(Topic.owner_id == user.id)
    if status_filter:
        stmt = stmt.where(Topic.status == status_filter)
    stmt = stmt.order_by(Topic.created_at.desc())
    topics = (await session.execute(stmt)).scalars().all()

    now = datetime.now(timezone.utc)
    result: list[dict[str, Any]] = []
    for top in topics:
        ic_res = await session.execute(
            select(func.count(KnowledgeItem.id)).where(
                KnowledgeItem.topic_id == top.id,
                KnowledgeItem.status != "archived",
            )
        )
        items_count = int(ic_res.scalar() or 0)

        gc_res = await session.execute(
            select(func.count(KnowledgeGroup.id)).where(
                KnowledgeGroup.topic_id == top.id,
                KnowledgeGroup.status != "archived",
            )
        )
        groups_count = int(gc_res.scalar() or 0)

        due_res = await session.execute(
            select(func.count(ReviewState.id)).where(
                ReviewState.topic_id == top.id,
                ReviewState.due_at <= now,
            )
        )
        due_count = int(due_res.scalar() or 0)

        result.append(_serialize_topic(top, items_count, groups_count, due_count))

    plan_code, limits = await _get_user_plan_limits(session, user)
    active_count = sum(1 for x in result if x["status"] == "active")
    return {
        "topics": result,
        "active_count": active_count,
        "active_limit": limits["topics"],
        "plan": plan_code,
    }


@router.post("/topics", status_code=status.HTTP_201_CREATED)
async def create_topic(
    payload: TopicCreateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    plan_code, limits = await _get_user_plan_limits(session, user)
    active_res = await session.execute(
        select(func.count(Topic.id)).where(
            Topic.owner_id == user.id,
            Topic.status == "active",
        )
    )
    active_topics = int(active_res.scalar() or 0)
    if active_topics >= limits["topics"]:
        loc = resolve_user_locale(
            locale_override=user.locale if user.locale_override else None,
            saved_locale=user.locale,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TOPIC_LIMIT_REACHED",
                "message": t("api.errors.quota_exceeded", loc),
                "plan": plan_code,
                "limit": limits["topics"],
            },
        )

    topic = Topic(
        owner_id=user.id,
        title=payload.title.strip(),
        goal=payload.goal,
        goal_note=payload.goal_note.strip() if payload.goal_note else None,
        icon=payload.icon,
        status="active",
    )
    session.add(topic)
    await session.flush()

    if user.first_activation_at is None:
        user.first_activation_at = datetime.now(timezone.utc)

    await analytics.track(
        session,
        event_name="topic_created",
        user=user,
        properties={"topic_id": topic.id, "goal": topic.goal},
    )
    await session.commit()
    await session.refresh(topic)
    return {"topic": _serialize_topic(topic)}


@router.get("/topics/{topic_id}")
async def get_topic_detail(
    topic_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    res = await session.execute(
        select(Topic).where(Topic.id == topic_id, Topic.owner_id == user.id)
    )
    topic = res.scalar_one_or_none()
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    items_res = await session.execute(
        select(KnowledgeItem)
        .where(KnowledgeItem.topic_id == topic.id, KnowledgeItem.owner_id == user.id)
        .order_by(KnowledgeItem.created_at.desc())
    )
    items = items_res.scalars().all()

    frag_ids = [it.fragment_id for it in items if it.fragment_id]
    frags_map: dict[str, SourceFragment] = {}
    if frag_ids:
        f_res = await session.execute(select(SourceFragment).where(SourceFragment.id.in_(frag_ids)))
        for fr in f_res.scalars().all():
            frags_map[fr.id] = fr

    groups_res = await session.execute(
        select(KnowledgeGroup)
        .where(KnowledgeGroup.topic_id == topic.id, KnowledgeGroup.owner_id == user.id)
        .order_by(KnowledgeGroup.created_at.desc())
    )
    groups = groups_res.scalars().all()
    serialized_groups: list[dict[str, Any]] = []
    for grp in groups:
        serialized_groups.append(await _serialize_group_detail(session, grp))

    mats_res = await session.execute(
        select(Material)
        .where(Material.topic_id == topic.id, Material.owner_id == user.id, Material.status != "deleted")
        .order_by(Material.created_at.desc())
    )
    materials = [
        {
            "id": m.id,
            "title": m.title,
            "format": m.format,
            "token_count": m.token_count,
            "status": m.status,
            "created_at": m.created_at.isoformat(),
        }
        for m in mats_res.scalars().all()
    ]

    now = datetime.now(timezone.utc)
    due_res = await session.execute(
        select(func.count(ReviewState.id)).where(
            ReviewState.topic_id == topic.id,
            ReviewState.due_at <= now,
        )
    )
    due_count = int(due_res.scalar() or 0)

    return {
        "topic": _serialize_topic(
            topic,
            items_count=sum(1 for it in items if it.status != "archived"),
            groups_count=sum(1 for g in groups if g.status != "archived"),
            due_count=due_count,
        ),
        "items": [_serialize_item(it, frags_map.get(it.fragment_id or "")) for it in items],
        "groups": serialized_groups,
        "materials": materials,
    }


@router.patch("/topics/{topic_id}")
async def update_topic(
    topic_id: str,
    payload: TopicUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    res = await session.execute(
        select(Topic).where(Topic.id == topic_id, Topic.owner_id == user.id)
    )
    topic = res.scalar_one_or_none()
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    if payload.revision is not None and payload.revision != topic.revision:
        raise HTTPException(status_code=409, detail="Revision conflict")

    if payload.status == "active" and topic.status != "active":
        plan_code, limits = await _get_user_plan_limits(session, user)
        active_res = await session.execute(
            select(func.count(Topic.id)).where(
                Topic.owner_id == user.id,
                Topic.status == "active",
            )
        )
        if int(active_res.scalar() or 0) >= limits["topics"]:
            raise HTTPException(
                status_code=403,
                detail={"code": "TOPIC_LIMIT_REACHED", "plan": plan_code, "limit": limits["topics"]},
            )

    if payload.title is not None:
        topic.title = payload.title.strip()
    if payload.goal is not None:
        topic.goal = payload.goal
    if payload.goal_note is not None:
        topic.goal_note = payload.goal_note.strip()
    if payload.icon is not None:
        topic.icon = payload.icon
    if payload.status is not None:
        topic.status = payload.status
    if payload.paused_until is not None:
        topic.paused_until = payload.paused_until

    topic.revision += 1
    await session.commit()
    await session.refresh(topic)
    return {"topic": _serialize_topic(topic)}


@router.post("/items", status_code=status.HTTP_201_CREATED)
async def create_knowledge_item(
    payload: KnowledgeItemCreateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    top_res = await session.execute(
        select(Topic).where(Topic.id == payload.topic_id, Topic.owner_id == user.id)
    )
    topic = top_res.scalar_one_or_none()
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.status == "readonly":
        raise HTTPException(status_code=403, detail="Topic is read-only on current plan")

    plan_code, limits = await _get_user_plan_limits(session, user)
    active_items_res = await session.execute(
        select(func.count(KnowledgeItem.id)).where(
            KnowledgeItem.owner_id == user.id,
            KnowledgeItem.status == "active",
        )
    )
    if int(active_items_res.scalar() or 0) >= limits["items"]:
        raise HTTPException(
            status_code=403,
            detail={"code": "ITEM_LIMIT_REACHED", "plan": plan_code, "limit": limits["items"]},
        )

    item_type = payload.item_type if payload.item_type in VALID_ITEM_TYPES else "fact"
    objectives = [obj for obj in payload.applicable_objectives if obj in VALID_OBJECTIVES]
    if not objectives:
        objectives = ["recall"]
        if item_type in ("concept", "opinion", "hypothesis") or payload.rubric_criteria:
            objectives.append("explain")

    fragment: SourceFragment | None = None
    if payload.quote_text and payload.quote_text.strip():
        fragment = SourceFragment(
            owner_id=user.id,
            material_title_snapshot=(payload.material_title_snapshot or topic.title).strip(),
            anchor_label=(payload.anchor_label or "Ручная цитата").strip(),
            quote_text=payload.quote_text.strip(),
        )
        session.add(fragment)
        await session.flush()

    criteria = [c.strip() for c in payload.rubric_criteria if c.strip()]
    if not criteria and "explain" in objectives:
        criteria = [payload.answer.strip()[:160]]

    item = KnowledgeItem(
        owner_id=user.id,
        topic_id=topic.id,
        fragment_id=fragment.id if fragment else None,
        item_type=item_type,
        origin="manual",
        prompt=payload.prompt.strip(),
        answer=payload.answer.strip(),
        applicability=payload.applicability.strip(),
        formula_expression=payload.formula_expression.strip() if payload.formula_expression else None,
        example_text=payload.example_text.strip(),
        counterexample_text=payload.counterexample_text.strip(),
        rubric_criteria=criteria,
        applicable_objectives=objectives,
        status="active",
    )
    session.add(item)
    await session.flush()

    await _ensure_item_exercises_and_review_states(session, item)

    if user.first_activation_at is None:
        user.first_activation_at = datetime.now(timezone.utc)

    await analytics.track(
        session,
        event_name="knowledge_item_created",
        user=user,
        properties={"item_id": item.id, "topic_id": topic.id, "item_type": item.item_type},
    )
    await session.commit()
    await session.refresh(item)
    return {"item": _serialize_item(item, fragment)}


@router.get("/items/{item_id}")
async def get_knowledge_item(
    item_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    res = await session.execute(
        select(KnowledgeItem).where(KnowledgeItem.id == item_id, KnowledgeItem.owner_id == user.id)
    )
    item = res.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")

    fragment: SourceFragment | None = None
    if item.fragment_id:
        f_res = await session.execute(select(SourceFragment).where(SourceFragment.id == item.fragment_id))
        fragment = f_res.scalar_one_or_none()

    # Check groups containing this item
    gm_res = await session.execute(select(GroupMember).where(GroupMember.item_id == item.id))
    group_ids = [gm.group_id for gm in gm_res.scalars().all()]
    groups: list[dict[str, Any]] = []
    if group_ids:
        g_res = await session.execute(select(KnowledgeGroup).where(KnowledgeGroup.id.in_(group_ids)))
        groups = [
            {"id": g.id, "title": g.title, "principle": g.principle, "status": g.status}
            for g in g_res.scalars().all()
        ]

    rs_res = await session.execute(
        select(ReviewState).where(
            ReviewState.owner_id == user.id,
            ReviewState.scope_type == "item",
            ReviewState.scope_id == item.id,
        )
    )
    review_states = [
        {
            "objective": rs.objective,
            "step_index": rs.step_index,
            "interval_days": rs.interval_days,
            "due_at": rs.due_at.isoformat(),
            "independent_successes": rs.independent_successes,
            "last_outcome": rs.last_outcome,
            "last_assisted": rs.last_assisted,
        }
        for rs in rs_res.scalars().all()
    ]

    return {
        "item": _serialize_item(item, fragment),
        "groups": groups,
        "review_states": review_states,
    }


@router.patch("/items/{item_id}")
async def update_knowledge_item(
    item_id: str,
    payload: KnowledgeItemUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    res = await session.execute(
        select(KnowledgeItem).where(KnowledgeItem.id == item_id, KnowledgeItem.owner_id == user.id)
    )
    item = res.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")

    if payload.revision is not None and payload.revision != item.revision:
        raise HTTPException(status_code=409, detail="Revision conflict")

    if payload.item_type and payload.item_type in VALID_ITEM_TYPES:
        item.item_type = payload.item_type
    if payload.prompt is not None:
        item.prompt = payload.prompt.strip()
    if payload.answer is not None:
        item.answer = payload.answer.strip()
    if payload.applicability is not None:
        item.applicability = payload.applicability.strip()
    if payload.formula_expression is not None:
        item.formula_expression = payload.formula_expression.strip() or None
    if payload.example_text is not None:
        item.example_text = payload.example_text.strip()
    if payload.counterexample_text is not None:
        item.counterexample_text = payload.counterexample_text.strip()
    if payload.rubric_criteria is not None:
        item.rubric_criteria = [c.strip() for c in payload.rubric_criteria if c.strip()]
    if payload.applicable_objectives is not None:
        objs = [o for o in payload.applicable_objectives if o in VALID_OBJECTIVES]
        if objs:
            item.applicable_objectives = objs

    fragment: SourceFragment | None = None
    if item.fragment_id:
        f_res = await session.execute(select(SourceFragment).where(SourceFragment.id == item.fragment_id))
        fragment = f_res.scalar_one_or_none()

    if payload.quote_text is not None:
        q_clean = payload.quote_text.strip()
        if q_clean:
            if fragment is None:
                fragment = SourceFragment(
                    owner_id=user.id,
                    material_title_snapshot="Источник",
                    anchor_label=(payload.anchor_label or "Фрагмент").strip(),
                    quote_text=q_clean,
                )
                session.add(fragment)
                await session.flush()
                item.fragment_id = fragment.id
            else:
                fragment.quote_text = q_clean
                if payload.anchor_label:
                    fragment.anchor_label = payload.anchor_label.strip()

    if payload.status is not None and payload.status != item.status:
        item.status = payload.status
        if item.status == "archived":
            # Mark any relations touching this item as broken and check groups (Section 7.3)
            rel_res = await session.execute(
                select(KnowledgeRelation).where(
                    or_(
                        KnowledgeRelation.from_item_id == item.id,
                        KnowledgeRelation.to_item_id == item.id,
                    )
                )
            )
            for rel in rel_res.scalars().all():
                rel.approval_status = "broken"

            gm_res = await session.execute(select(GroupMember).where(GroupMember.item_id == item.id))
            affected_group_ids = [gm.group_id for gm in gm_res.scalars().all()]
            for gid in affected_group_ids:
                g_res = await session.execute(select(KnowledgeGroup).where(KnowledgeGroup.id == gid))
                grp = g_res.scalar_one_or_none()
                if grp:
                    active_members_res = await session.execute(
                        select(func.count(GroupMember.id))
                        .join(KnowledgeItem, KnowledgeItem.id == GroupMember.item_id)
                        .where(GroupMember.group_id == gid, KnowledgeItem.status == "active")
                    )
                    if int(active_members_res.scalar() or 0) < 2:
                        grp.status = "needs_review"

    item.revision += 1
    await _ensure_item_exercises_and_review_states(session, item)
    await session.commit()
    await session.refresh(item)
    return {"item": _serialize_item(item, fragment)}


@router.get("/fragments/{fragment_id}")
async def get_source_fragment(
    fragment_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    res = await session.execute(
        select(SourceFragment).where(
            SourceFragment.id == fragment_id,
            SourceFragment.owner_id == user.id,
        )
    )
    frag = res.scalar_one_or_none()
    if frag is None:
        raise HTTPException(status_code=404, detail="Source fragment not found")
    return {
        "fragment": {
            "id": frag.id,
            "material_id": frag.material_id,
            "material_title_snapshot": frag.material_title_snapshot,
            "anchor_label": frag.anchor_label,
            "page_number": frag.page_number,
            "chapter_title": frag.chapter_title,
            "paragraph_index": frag.paragraph_index,
            "quote_text": frag.quote_text,
            "context_before": frag.context_before,
            "context_after": frag.context_after,
            "source_deleted": frag.source_deleted,
        }
    }


async def _serialize_group_detail(session: AsyncSession, group: KnowledgeGroup) -> dict[str, Any]:
    gm_res = await session.execute(
        select(GroupMember, KnowledgeItem)
        .join(KnowledgeItem, KnowledgeItem.id == GroupMember.item_id)
        .where(GroupMember.group_id == group.id)
        .order_by(GroupMember.position.asc())
    )
    members_rows = gm_res.all()
    members = [
        {
            "item_id": it.id,
            "prompt": it.prompt,
            "answer": it.answer,
            "item_type": it.item_type,
            "item_status": it.status,
            "position": gm.position,
            "role_label": gm.role_label,
            "explanation": gm.explanation,
        }
        for gm, it in members_rows
    ]

    rel_res = await session.execute(
        select(KnowledgeRelation).where(KnowledgeRelation.group_id == group.id)
    )
    relations = [
        {
            "id": r.id,
            "from_item_id": r.from_item_id,
            "to_item_id": r.to_item_id,
            "relation_type": r.relation_type,
            "direction": r.direction,
            "explanation": r.explanation,
            "provenance": r.provenance,
            "approval_status": r.approval_status,
        }
        for r in rel_res.scalars().all()
    ]

    active_member_count = sum(1 for m in members if m["item_status"] == "active")
    has_broken = any(r["approval_status"] == "broken" for r in relations) or active_member_count < 2
    effective_status = "needs_review" if (has_broken and group.status == "confirmed") else group.status

    return {
        "id": group.id,
        "topic_id": group.topic_id,
        "title": group.title,
        "principle": group.principle,
        "condition": group.condition,
        "example": group.example,
        "counterexample": group.counterexample,
        "provenance": group.provenance,
        "status": effective_status,
        "revision": group.revision,
        "members": members,
        "relations": relations,
        "created_at": group.created_at.isoformat(),
        "updated_at": group.updated_at.isoformat(),
    }


async def _validate_group_members_and_relations(
    session: AsyncSession,
    *,
    user_id: str,
    topic_id: str,
    members: list[GroupMemberInput],
    relations: list[RelationInput],
) -> list[KnowledgeItem]:
    if len(members) < 2 or len(members) > 7:
        raise HTTPException(
            status_code=400,
            detail="A meaning group must contain between 2 and 7 items.",
        )

    item_ids = [m.item_id for m in members]
    if len(set(item_ids)) != len(item_ids):
        raise HTTPException(
            status_code=400,
            detail="Duplicate items are not allowed in the same meaning group.",
        )

    items_res = await session.execute(
        select(KnowledgeItem).where(
            KnowledgeItem.id.in_(item_ids),
            KnowledgeItem.owner_id == user_id,
        )
    )
    found_items = {it.id: it for it in items_res.scalars().all()}
    if len(found_items) != len(item_ids):
        raise HTTPException(status_code=400, detail="One or more member items do not exist.")

    for iid in item_ids:
        it = found_items[iid]
        if it.topic_id != topic_id:
            raise HTTPException(
                status_code=400,
                detail="All items in a meaning group must belong to the same topic.",
            )
        if it.status == "archived":
            raise HTTPException(
                status_code=400,
                detail="Archived items cannot be added to a meaning group.",
            )

    member_set = set(item_ids)
    for rel in relations:
        if rel.from_item_id == rel.to_item_id:
            raise HTTPException(status_code=400, detail="Self-relations are not allowed.")
        if rel.from_item_id not in member_set or rel.to_item_id not in member_set:
            raise HTTPException(
                status_code=400,
                detail="Relation endpoints must be members of the group.",
            )
        if rel.relation_type not in VALID_RELATION_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid relation_type: {rel.relation_type}",
            )

    return [found_items[iid] for iid in item_ids]


@router.post("/groups", status_code=status.HTTP_201_CREATED)
async def create_knowledge_group(
    payload: KnowledgeGroupCreateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    top_res = await session.execute(
        select(Topic).where(Topic.id == payload.topic_id, Topic.owner_id == user.id)
    )
    topic = top_res.scalar_one_or_none()
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.status == "readonly":
        raise HTTPException(status_code=403, detail="Topic is read-only")

    validated_items = await _validate_group_members_and_relations(
        session,
        user_id=user.id,
        topic_id=topic.id,
        members=payload.members,
        relations=payload.relations,
    )

    group = KnowledgeGroup(
        owner_id=user.id,
        topic_id=topic.id,
        title=payload.title.strip(),
        principle=payload.principle.strip(),
        condition=payload.condition.strip(),
        example=payload.example.strip(),
        counterexample=payload.counterexample.strip(),
        provenance="user",
        status="confirmed",
    )
    session.add(group)
    await session.flush()

    for idx, m_in in enumerate(payload.members):
        session.add(
            GroupMember(
                group_id=group.id,
                item_id=m_in.item_id,
                position=idx,
                role_label=m_in.role_label.strip() or "basis",
                explanation=m_in.explanation.strip(),
            )
        )

    created_relations: list[KnowledgeRelation] = []
    for r_in in payload.relations:
        rel = KnowledgeRelation(
            owner_id=user.id,
            topic_id=topic.id,
            group_id=group.id,
            from_item_id=r_in.from_item_id,
            to_item_id=r_in.to_item_id,
            relation_type=r_in.relation_type,
            direction=r_in.direction,
            explanation=r_in.explanation.strip(),
            provenance="user",
            approval_status="confirmed",
        )
        session.add(rel)
        created_relations.append(rel)

    await session.flush()
    await _ensure_group_exercises_and_review_state(
        session,
        group,
        [it.id for it in validated_items],
        created_relations,
    )

    await analytics.track(
        session,
        event_name="knowledge_group_created",
        user=user,
        properties={
            "group_id": group.id,
            "topic_id": topic.id,
            "members_count": len(validated_items),
            "relations_count": len(created_relations),
        },
    )
    await session.commit()
    await session.refresh(group)
    return {"group": await _serialize_group_detail(session, group)}


@router.get("/groups/{group_id}")
async def get_knowledge_group(
    group_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    res = await session.execute(
        select(KnowledgeGroup).where(KnowledgeGroup.id == group_id, KnowledgeGroup.owner_id == user.id)
    )
    group = res.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Meaning group not found")
    return {"group": await _serialize_group_detail(session, group)}


@router.put("/groups/{group_id}")
async def update_knowledge_group(
    group_id: str,
    payload: KnowledgeGroupUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    res = await session.execute(
        select(KnowledgeGroup).where(KnowledgeGroup.id == group_id, KnowledgeGroup.owner_id == user.id)
    )
    group = res.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Meaning group not found")

    if payload.revision is not None and payload.revision != group.revision:
        raise HTTPException(status_code=409, detail="Revision conflict")

    if payload.title is not None:
        group.title = payload.title.strip()
    if payload.principle is not None:
        group.principle = payload.principle.strip()
    if payload.condition is not None:
        group.condition = payload.condition.strip()
    if payload.example is not None:
        group.example = payload.example.strip()
    if payload.counterexample is not None:
        group.counterexample = payload.counterexample.strip()
    if payload.status is not None:
        group.status = payload.status

    if payload.members is not None:
        rels_to_validate = payload.relations or []
        validated_items = await _validate_group_members_and_relations(
            session,
            user_id=user.id,
            topic_id=group.topic_id,
            members=payload.members,
            relations=rels_to_validate,
        )
        await session.execute(delete(GroupMember).where(GroupMember.group_id == group.id))
        for idx, m_in in enumerate(payload.members):
            session.add(
                GroupMember(
                    group_id=group.id,
                    item_id=m_in.item_id,
                    position=idx,
                    role_label=m_in.role_label.strip() or "basis",
                    explanation=m_in.explanation.strip(),
                )
            )

        if payload.relations is not None:
            await session.execute(delete(KnowledgeRelation).where(KnowledgeRelation.group_id == group.id))
            new_rels: list[KnowledgeRelation] = []
            for r_in in payload.relations:
                rel = KnowledgeRelation(
                    owner_id=user.id,
                    topic_id=group.topic_id,
                    group_id=group.id,
                    from_item_id=r_in.from_item_id,
                    to_item_id=r_in.to_item_id,
                    relation_type=r_in.relation_type,
                    direction=r_in.direction,
                    explanation=r_in.explanation.strip(),
                    provenance="user",
                    approval_status="confirmed",
                )
                session.add(rel)
                new_rels.append(rel)
            await session.flush()
            await _ensure_group_exercises_and_review_state(
                session,
                group,
                [it.id for it in validated_items],
                new_rels,
            )

    group.revision += 1
    await session.commit()
    await session.refresh(group)
    return {"group": await _serialize_group_detail(session, group)}


@router.get("/search")
async def search_knowledge(
    q: str = Query(default="", max_length=200),
    topic_id: str | None = Query(default=None),
    item_type: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    query_str = q.strip()
    pattern = f"%{query_str}%"

    topics_stmt = select(Topic).where(Topic.owner_id == user.id)
    if query_str:
        topics_stmt = topics_stmt.where(
            or_(Topic.title.ilike(pattern), Topic.goal_note.ilike(pattern))
        )
    topics = (await session.execute(topics_stmt.limit(20))).scalars().all()

    items_stmt = select(KnowledgeItem).where(KnowledgeItem.owner_id == user.id)
    if topic_id:
        items_stmt = items_stmt.where(KnowledgeItem.topic_id == topic_id)
    if item_type:
        items_stmt = items_stmt.where(KnowledgeItem.item_type == item_type)
    if query_str:
        items_stmt = items_stmt.where(
            or_(
                KnowledgeItem.prompt.ilike(pattern),
                KnowledgeItem.answer.ilike(pattern),
                KnowledgeItem.applicability.ilike(pattern),
            )
        )
    items = (await session.execute(items_stmt.order_by(KnowledgeItem.updated_at.desc()).limit(40))).scalars().all()

    groups_stmt = select(KnowledgeGroup).where(KnowledgeGroup.owner_id == user.id)
    if topic_id:
        groups_stmt = groups_stmt.where(KnowledgeGroup.topic_id == topic_id)
    if query_str:
        groups_stmt = groups_stmt.where(
            or_(
                KnowledgeGroup.title.ilike(pattern),
                KnowledgeGroup.principle.ilike(pattern),
            )
        )
    groups = (await session.execute(groups_stmt.order_by(KnowledgeGroup.updated_at.desc()).limit(20))).scalars().all()

    return {
        "query": query_str,
        "topics": [_serialize_topic(tp) for tp in topics],
        "items": [_serialize_item(it) for it in items],
        "groups": [
            {
                "id": g.id,
                "topic_id": g.topic_id,
                "title": g.title,
                "principle": g.principle,
                "status": g.status,
            }
            for g in groups
        ],
    }
