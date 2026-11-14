"""Materials upload/parsing, signed token estimation, Trial activation, Quota Ledger, DeepSeek AI import pipeline & D14-D18, D30 routes (Dev Spec v1.14 Sections 8, 9, 10)."""

from __future__ import annotations

import hashlib
import hmac
import io
import re
import uuid
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from brainrecall.analytics import analytics
from brainrecall.config import PLAN_LIMITS, settings
from brainrecall.db import get_session
from brainrecall.deepseek_adapter import deepseek_adapter, estimate_token_count
from brainrecall.i18n import resolve_user_locale
from brainrecall.knowledge_routes import _ensure_item_exercises_and_review_states
from brainrecall.models import (
    Candidate,
    Entitlement,
    ImportJob,
    KnowledgeItem,
    KnowledgeRelation,
    Material,
    QuotaLedger,
    SourceFragment,
    Topic,
    TrialRegistry,
    User,
)
from brainrecall.security import get_current_user

router = APIRouter(prefix="/api/v1", tags=["materials_ai"])

SUPPORTED_FORMATS = {"text", "txt", "md", "pdf", "docx", "epub"}


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def _extract_html_text(raw_html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(raw_html)
    return "\n\n".join(parser.parts)


def parse_file_bytes_safely(filename: str, raw_bytes: bytes) -> tuple[str, str]:
    """
    Safely parse TXT, MD, text PDF, DOCX, and EPUB up to 20 MiB.
    Returns (detected_format, extracted_text).
    Raises HTTPException(400/413/422) on size limit, scan PDF, or unsupported format.
    """
    if len(raw_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": "Maximum file size is 20 MiB.",
                "max_bytes": settings.max_upload_bytes,
            },
        )

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "UNSUPPORTED_FORMAT", "format": ext},
        )

    if ext in ("txt", "md", "text"):
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = raw_bytes.decode("cp1251", errors="replace")
        return ext, text.strip()

    if ext == "docx":
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                xml_bytes = zf.read("word/document.xml")
            root = ET.fromstring(xml_bytes)
            paragraphs: list[str] = []
            for p in root.iter():
                if p.tag.endswith("}p"):
                    texts = [t_el.text for t_el in p.iter() if t_el.tag.endswith("}t") and t_el.text]
                    if texts:
                        paragraphs.append("".join(texts).strip())
            extracted = "\n\n".join(p for p in paragraphs if p)
            if not extracted.strip():
                raise ValueError("Empty DOCX text")
            return "docx", extracted
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "DOCX_PARSE_FAILED", "message": f"Could not extract text from DOCX: {exc}"},
            ) from exc

    if ext == "epub":
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                html_files = sorted(
                    name
                    for name in zf.namelist()
                    if name.lower().endswith((".xhtml", ".html", ".htm"))
                )
                chunks: list[str] = []
                for name in html_files[:150]:
                    raw_html = zf.read(name).decode("utf-8", errors="replace")
                    chunk = _extract_html_text(raw_html)
                    if chunk.strip():
                        chunks.append(chunk.strip())
            extracted = "\n\n".join(chunks)
            if not extracted.strip():
                raise ValueError("Empty EPUB text")
            return "epub", extracted
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "EPUB_PARSE_FAILED", "message": f"Could not extract text from EPUB: {exc}"},
            ) from exc

    if ext == "pdf":
        # Lightweight text-layer extraction (supports pypdf if installed or PDF text stream extraction)
        extracted_pages: list[str] = []
        try:
            import pypdf  # type: ignore

            reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
            for idx, page in enumerate(reader.pages):
                p_text = (page.extract_text() or "").strip()
                if p_text:
                    extracted_pages.append(f"[Page {idx + 1}]\n{p_text}")
        except Exception:
            # Fallback PDF literal string extraction for text-based PDFs
            decoded = raw_bytes.decode("latin-1", errors="ignore")
            matches = re.findall(r"\(([^()\\]{4,})\)\s*Tj", decoded)
            if matches:
                extracted_pages.append("\n\n".join(matches))

        extracted = "\n\n".join(extracted_pages).strip()
        if len(extracted) < 20:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "PDF_SCAN_WITHOUT_TEXT",
                    "message": "PDF appears to be a scan without a text layer. OCR is not supported in MVP; please paste text or upload TXT/MD/DOCX.",
                },
            )
        return "pdf", extracted

    raise HTTPException(status_code=400, detail="Unsupported format")


def split_into_fragments(
    *,
    owner_id: str,
    material_id: str,
    material_title: str,
    extracted_text: str,
    source_revision: int = 1,
    is_en: bool = False,
) -> list[SourceFragment]:
    """Splits extracted material text into anchored SourceFragments for D34 provenance."""
    raw_blocks = [b.strip() for b in re.split(r"\n\s*\n+", extracted_text) if b.strip()]
    if not raw_blocks and extracted_text.strip():
        raw_blocks = [extracted_text.strip()]

    # Merge tiny blocks or split huge blocks (>1000 chars)
    normalized_blocks: list[str] = []
    for block in raw_blocks:
        if len(block) <= 1000:
            normalized_blocks.append(block)
        else:
            for offset in range(0, len(block), 900):
                chunk = block[offset : offset + 900].strip()
                if chunk:
                    normalized_blocks.append(chunk)

    fragments: list[SourceFragment] = []
    cursor = 0
    current_chapter = "Раздел 1" if not is_en else "Section 1"

    for idx, block in enumerate(normalized_blocks[:120]):
        if block.startswith("#"):
            current_chapter = block.lstrip("#").strip()[:80] or current_chapter
        para_num = idx + 1
        anchor_label = (
            f"{current_chapter} · para. {para_num}"
            if is_en
            else f"{current_chapter} · абз. {para_num}"
        )
        before_txt = normalized_blocks[idx - 1][:220] if idx > 0 else ""
        after_txt = normalized_blocks[idx + 1][:220] if idx + 1 < len(normalized_blocks) else ""
        start_pos = cursor
        end_pos = cursor + len(block)
        cursor = end_pos + 2

        fragments.append(
            SourceFragment(
                owner_id=owner_id,
                material_id=material_id,
                material_title_snapshot=material_title,
                anchor_label=anchor_label[:120],
                chapter_title=current_chapter[:250],
                paragraph_index=para_num,
                char_offset_start=start_pos,
                char_offset_end=end_pos,
                quote_text=block,
                context_before=before_txt,
                context_after=after_txt,
                source_revision=source_revision,
            )
        )
    return fragments


def _compute_estimate_signature(
    *,
    user_id: str,
    material_id: str,
    source_revision: int,
    token_count: int,
    period_id: str,
) -> str:
    payload = f"{user_id}:{material_id}:{source_revision}:{token_count}:{period_id}"
    return hmac.new(
        settings.app_secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _hash_telegram_id(telegram_id: int) -> str:
    return hashlib.sha256(f"br-trial:{telegram_id}".encode("utf-8")).hexdigest()


async def ensure_or_get_entitlement(session: AsyncSession, user: User) -> Entitlement:
    res = await session.execute(select(Entitlement).where(Entitlement.owner_id == user.id))
    ent = res.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if ent is None:
        limits = PLAN_LIMITS["free"]
        ent = Entitlement(
            owner_id=user.id,
            plan_code="free",
            status="active",
            trial_used=False,
            period_id=f"free-{user.id[:8]}",
            period_start=now,
            import_tokens_limit=limits["import_tokens"],
            ai_checks_limit=limits["ai_checks"],
            ai_cases_limit=limits["ai_cases"],
            ai_plans_limit=limits["ai_plans"],
            ai_reviews_limit=limits["ai_reviews"],
        )
        session.add(ent)
        await session.flush()

    # Check if Trial Registry already marks this telegram_id as trial_used
    tg_hash = _hash_telegram_id(user.telegram_id)
    tr_res = await session.execute(
        select(TrialRegistry).where(TrialRegistry.telegram_id_hash == tg_hash)
    )
    if tr_res.scalar_one_or_none() is not None and not ent.trial_used:
        ent.trial_used = True
        await session.flush()

    # Check period expiration
    if ent.period_end is not None:
        p_end = ent.period_end.replace(tzinfo=timezone.utc) if ent.period_end.tzinfo is None else ent.period_end
        if p_end <= now and ent.plan_code != "free":
            ent.plan_code = "free"
            ent.status = "active"
            ent.auto_renew = False
            ent.import_tokens_limit = 0
            ent.ai_checks_limit = 0
            ent.ai_cases_limit = 0
            ent.ai_plans_limit = 0
            ent.ai_reviews_limit = 0
            await session.flush()

    return ent


def build_d30_quota_payload(ent: Entitlement, resource: str, required_amount: int = 1) -> dict[str, Any]:
    used = getattr(ent, f"{resource}_used", 0)
    reserved = getattr(ent, f"{resource}_reserved", 0)
    limit = getattr(ent, f"{resource}_limit", 0)
    remaining = max(0, limit - used - reserved)
    return {
        "code": "QUOTA_EXCEEDED",
        "screen": "D30",
        "plan_code": ent.plan_code,
        "trial_eligible": not ent.trial_used and ent.plan_code == "free",
        "resource": resource,
        "required_amount": required_amount,
        "used": used,
        "reserved": reserved,
        "limit": limit,
        "remaining": remaining,
        "period_end": ent.period_end.isoformat() if ent.period_end else None,
        "manual_mode_available": True,
        "upgrade_plans": [
            {"code": "start", "price_xtr": PLAN_LIMITS["start"]["price_xtr"], "import_tokens": PLAN_LIMITS["start"]["import_tokens"]},
            {"code": "pro", "price_xtr": PLAN_LIMITS["pro"]["price_xtr"], "import_tokens": PLAN_LIMITS["pro"]["import_tokens"]},
        ],
    }


class MaterialTextCreateRequest(BaseModel):
    topic_id: str | None = None
    topic_title: str | None = Field(default=None, max_length=200)
    title: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(default="exam", max_length=64)
    language: str = Field(default="ru", max_length=16)
    text: str = Field(..., min_length=10, max_length=500_000)


class EstimateRequest(BaseModel):
    material_id: str


class StartImportJobRequest(BaseModel):
    material_id: str
    operation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    estimate_signature: str | None = None
    activate_trial: bool = False
    ai_consent_accepted: bool = True


class CandidateUpdateRequest(BaseModel):
    prompt: str | None = Field(default=None, min_length=1, max_length=2000)
    answer: str | None = Field(default=None, min_length=1, max_length=4000)
    applicability: str | None = Field(default=None, max_length=1000)
    item_type: str | None = None
    selected: bool | None = None
    review_status: str | None = Field(default=None, pattern="^(pending|accepted|rejected)$")


class AcceptCandidatesRequest(BaseModel):
    item_candidate_ids: list[str] | None = None  # If None, all selected item candidates
    relation_candidate_ids: list[str] | None = None  # Separate M5 relation confirmation per Section 3.14


async def _resolve_or_create_topic_for_material(
    session: AsyncSession,
    user: User,
    topic_id: str | None,
    topic_title: str | None,
    fallback_title: str,
    goal: str,
) -> Topic:
    if topic_id:
        res = await session.execute(
            select(Topic).where(Topic.id == topic_id, Topic.owner_id == user.id)
        )
        topic = res.scalar_one_or_none()
        if topic is not None:
            return topic

    # Check if user already has an active topic or create one
    t_title = (topic_title or fallback_title or "Новая тема").strip()[:200]
    topic = Topic(
        owner_id=user.id,
        title=t_title,
        goal=goal or "exam",
        icon="topic-book",
        status="active",
    )
    session.add(topic)
    await session.flush()
    return topic


@router.post("/materials/text", status_code=status.HTTP_201_CREATED)
async def create_material_from_text_d14(
    payload: MaterialTextCreateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """D14: Create material from pasted text, split into anchored SourceFragments, and compute token count."""
    cleaned_text = payload.text.strip()
    token_count = estimate_token_count(cleaned_text)
    if token_count > settings.max_source_tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "SOURCE_TOKENS_EXCEEDED",
                "token_count": token_count,
                "max_tokens": settings.max_source_tokens,
            },
        )

    topic = await _resolve_or_create_topic_for_material(
        session,
        user,
        payload.topic_id,
        payload.topic_title,
        payload.title,
        payload.goal,
    )

    content_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
    mat = Material(
        owner_id=user.id,
        topic_id=topic.id,
        title=payload.title.strip(),
        format="text",
        goal=payload.goal,
        language=payload.language,
        extracted_text=cleaned_text,
        content_hash=content_hash,
        token_count=token_count,
        status="parsed",
        source_revision=1,
    )
    session.add(mat)
    await session.flush()

    loc = resolve_user_locale(
        locale_override=user.locale if user.locale_override else None,
        saved_locale=user.locale,
    )
    fragments = split_into_fragments(
        owner_id=user.id,
        material_id=mat.id,
        material_title=mat.title,
        extracted_text=cleaned_text,
        source_revision=mat.source_revision,
        is_en=(loc == "en"),
    )
    for frag in fragments:
        session.add(frag)

    await session.commit()
    await session.refresh(mat)
    return {
        "material": {
            "id": mat.id,
            "topic_id": mat.topic_id,
            "title": mat.title,
            "format": mat.format,
            "goal": mat.goal,
            "language": mat.language,
            "token_count": mat.token_count,
            "fragments_count": len(fragments),
            "status": mat.status,
            "source_revision": mat.source_revision,
        }
    }


@router.post("/materials/upload", status_code=status.HTTP_201_CREATED)
async def upload_material_file_d15(
    file: UploadFile = File(...),
    topic_id: str | None = Form(default=None),
    topic_title: str | None = Form(default=None),
    title: str | None = Form(default=None),
    goal: str = Form(default="exam"),
    language: str = Form(default="ru"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """D15: Upload and safely parse TXT, MD, text PDF, DOCX, or EPUB up to 20 MiB and 100,000 tokens."""
    raw_bytes = await file.read()
    filename = file.filename or "document.txt"
    detected_format, extracted_text = parse_file_bytes_safely(filename, raw_bytes)

    token_count = estimate_token_count(extracted_text)
    if token_count > settings.max_source_tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "SOURCE_TOKENS_EXCEEDED",
                "token_count": token_count,
                "max_tokens": settings.max_source_tokens,
            },
        )

    mat_title = (title or filename.rsplit(".", 1)[0] or "Материал").strip()[:200]
    topic = await _resolve_or_create_topic_for_material(
        session,
        user,
        topic_id,
        topic_title,
        mat_title,
        goal,
    )

    content_hash = hashlib.sha256(extracted_text.encode("utf-8")).hexdigest()
    mat = Material(
        owner_id=user.id,
        topic_id=topic.id,
        title=mat_title,
        format=detected_format,
        goal=goal,
        language=language,
        extracted_text=extracted_text,
        content_hash=content_hash,
        token_count=token_count,
        status="parsed",
        source_revision=1,
    )
    session.add(mat)
    await session.flush()

    loc = resolve_user_locale(
        locale_override=user.locale if user.locale_override else None,
        saved_locale=user.locale,
    )
    fragments = split_into_fragments(
        owner_id=user.id,
        material_id=mat.id,
        material_title=mat.title,
        extracted_text=extracted_text,
        source_revision=mat.source_revision,
        is_en=(loc == "en"),
    )
    for frag in fragments:
        session.add(frag)

    await session.commit()
    await session.refresh(mat)
    return {
        "material": {
            "id": mat.id,
            "topic_id": mat.topic_id,
            "title": mat.title,
            "format": mat.format,
            "goal": mat.goal,
            "language": mat.language,
            "token_count": mat.token_count,
            "fragments_count": len(fragments),
            "status": mat.status,
            "source_revision": mat.source_revision,
        }
    }


@router.post("/materials/estimate")
async def estimate_material_d16(
    payload: EstimateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    D16: Returns signed token estimate, current entitlement quota state, and whether 7-day Trial can be activated.
    """
    res = await session.execute(
        select(Material).where(Material.id == payload.material_id, Material.owner_id == user.id)
    )
    mat = res.scalar_one_or_none()
    if mat is None:
        raise HTTPException(status_code=404, detail="Material not found")

    ent = await ensure_or_get_entitlement(session, user)
    trial_eligible = (not ent.trial_used) and (ent.plan_code == "free")

    # Effective quota if trial is activated vs current plan
    current_remaining = max(0, ent.import_tokens_limit - ent.import_tokens_used - ent.import_tokens_reserved)
    trial_limit = PLAN_LIMITS["trial"]["import_tokens"]
    effective_remaining = trial_limit if trial_eligible else current_remaining
    can_proceed = mat.token_count <= effective_remaining

    signature = _compute_estimate_signature(
        user_id=user.id,
        material_id=mat.id,
        source_revision=mat.source_revision,
        token_count=mat.token_count,
        period_id=ent.period_id,
    )

    await session.commit()
    return {
        "material_id": mat.id,
        "title": mat.title,
        "format": mat.format,
        "token_count": mat.token_count,
        "source_revision": mat.source_revision,
        "estimate_signature": signature,
        "plan_code": ent.plan_code,
        "trial_eligible": trial_eligible,
        "trial_days": PLAN_LIMITS["trial"]["period_days"],
        "trial_import_tokens": trial_limit,
        "quota": {
            "limit": ent.import_tokens_limit,
            "used": ent.import_tokens_used,
            "reserved": ent.import_tokens_reserved,
            "remaining": current_remaining,
            "effective_remaining": effective_remaining,
            "after_operation": max(0, effective_remaining - mat.token_count),
        },
        "can_proceed": can_proceed,
        "ai_disclosure_required": user.ai_consent_version is None,
    }


@router.post("/materials/import-jobs", status_code=status.HTTP_201_CREATED)
async def start_ai_import_job_d16_d17(
    payload: StartImportJobRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    D16 -> D17:
    - Idempotent by `operation_id`.
    - Atomically activates one-time 7-day Trial if `activate_trial=True` and eligible (`TrialRegistry` anti-abuse).
    - Reserves `token_count` in `QuotaLedger` (`reserved` -> `committed` on success, `released` on failure/cancel).
    - Runs DeepSeek extraction pipeline (`queued -> extract -> exercises -> validate -> ready`).
    """
    existing_job = (
        await session.execute(
            select(ImportJob).where(
                ImportJob.operation_id == payload.operation_id,
                ImportJob.owner_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if existing_job is not None:
        return await _serialize_import_job_with_candidates(session, existing_job)

    mat = (
        await session.execute(
            select(Material).where(Material.id == payload.material_id, Material.owner_id == user.id)
        )
    ).scalar_one_or_none()
    if mat is None:
        raise HTTPException(status_code=404, detail="Material not found")

    ent = await ensure_or_get_entitlement(session, user)
    now = datetime.now(timezone.utc)

    # Record AI disclosure consent if accepted
    if payload.ai_consent_accepted and user.ai_consent_version is None:
        user.ai_consent_version = "v1.14"
        user.ai_consent_at = now

    # Activate 7-day Trial atomically on first confirmed AI action if eligible
    if (payload.activate_trial or ent.plan_code == "free") and not ent.trial_used:
        tg_hash = _hash_telegram_id(user.telegram_id)
        existing_tr = (
            await session.execute(select(TrialRegistry).where(TrialRegistry.telegram_id_hash == tg_hash))
        ).scalar_one_or_none()
        if existing_tr is None:
            session.add(TrialRegistry(telegram_id_hash=tg_hash, trial_started_at=now))
            t_limits = PLAN_LIMITS["trial"]
            ent.plan_code = "trial"
            ent.status = "active"
            ent.trial_used = True
            ent.period_id = f"trial-{user.id[:8]}-{int(now.timestamp())}"
            ent.period_start = now
            ent.period_end = now + timedelta(days=t_limits["period_days"])
            ent.import_tokens_limit = t_limits["import_tokens"]
            ent.import_tokens_used = 0
            ent.import_tokens_reserved = 0
            ent.ai_checks_limit = t_limits["ai_checks"]
            ent.ai_checks_used = 0
            ent.ai_checks_reserved = 0
            ent.ai_cases_limit = t_limits["ai_cases"]
            ent.ai_cases_used = 0
            ent.ai_cases_reserved = 0
            ent.ai_plans_limit = t_limits["ai_plans"]
            ent.ai_plans_used = 0
            ent.ai_plans_reserved = 0
            ent.ai_reviews_limit = t_limits["ai_reviews"]
            ent.ai_reviews_used = 0
            ent.ai_reviews_reserved = 0
            await analytics.track(
                session,
                event_name="trial_started",
                user=user,
                properties={"period_id": ent.period_id, "import_tokens_limit": ent.import_tokens_limit},
            )
            await session.flush()
        else:
            ent.trial_used = True
            await session.flush()

    remaining = ent.import_tokens_limit - ent.import_tokens_used - ent.import_tokens_reserved
    if mat.token_count > remaining:
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=build_d30_quota_payload(ent, "import_tokens", mat.token_count),
        )

    # 1. Reserve tokens in QuotaLedger & Entitlement
    ent.import_tokens_reserved += mat.token_count
    ledger = QuotaLedger(
        operation_id=payload.operation_id,
        owner_id=user.id,
        period_id=ent.period_id,
        resource="import_tokens",
        reserved_amount=mat.token_count,
        committed_amount=0,
        status="reserved",
        provider_model=settings.deepseek_model,
    )
    session.add(ledger)

    job = ImportJob(
        operation_id=payload.operation_id,
        owner_id=user.id,
        material_id=mat.id,
        topic_id=mat.topic_id,
        source_revision=mat.source_revision,
        stage="extract",
        reserved_tokens=mat.token_count,
        estimate_signature=payload.estimate_signature,
    )
    session.add(job)
    mat.status = "processing"
    await session.flush()

    # Load fragments for extraction
    frags_res = await session.execute(
        select(SourceFragment)
        .where(SourceFragment.material_id == mat.id)
        .order_by(SourceFragment.paragraph_index.asc())
    )
    frags = [
        {
            "id": f.id,
            "anchor_label": f.anchor_label,
            "quote_text": f.quote_text,
        }
        for f in frags_res.scalars().all()
    ]

    try:
        ai_result = await deepseek_adapter.extract_candidates_from_fragments(
            title=mat.title,
            goal=mat.goal,
            language=mat.language,
            fragments=frags,
        )
        job.stage = "exercises"
        item_candidates: list[Candidate] = []
        for raw_it in ai_result["items"]:
            cand = Candidate(
                import_job_id=job.id,
                material_id=mat.id,
                owner_id=user.id,
                topic_id=mat.topic_id,
                candidate_kind="item",
                item_type=raw_it["item_type"],
                prompt=raw_it["prompt"],
                answer=raw_it["answer"],
                applicability=raw_it.get("applicability") or "",
                fragment_id=raw_it.get("fragment_id"),
                anchor_label=raw_it.get("anchor_label") or "",
                quote_text=raw_it.get("quote_text") or "",
                warning_note=raw_it.get("warning_note"),
                selected=True,
                review_status="pending",
            )
            session.add(cand)
            item_candidates.append(cand)

        await session.flush()

        job.stage = "validate"
        rel_candidates: list[Candidate] = []
        for raw_rel in ai_result["relations"]:
            fi = raw_rel["from_item_index"]
            ti = raw_rel["to_item_index"]
            if 0 <= fi < len(item_candidates) and 0 <= ti < len(item_candidates):
                from_c = item_candidates[fi]
                to_c = item_candidates[ti]
                rcand = Candidate(
                    import_job_id=job.id,
                    material_id=mat.id,
                    owner_id=user.id,
                    topic_id=mat.topic_id,
                    candidate_kind="relation",
                    item_type="concept",
                    prompt=f"{from_c.prompt[:80]} → {to_c.prompt[:80]}",
                    answer=raw_rel.get("explanation") or "",
                    applicability=raw_rel.get("relation_type") or "consequence",
                    fragment_id=from_c.fragment_id,
                    anchor_label=from_c.anchor_label,
                    quote_text=from_c.quote_text,
                    extra_payload={
                        "from_candidate_id": from_c.id,
                        "to_candidate_id": to_c.id,
                        "relation_type": raw_rel.get("relation_type") or "consequence",
                        "explanation": raw_rel.get("explanation") or "",
                    },
                    selected=True,
                    review_status="pending",
                )
                session.add(rcand)
                rel_candidates.append(rcand)

        # Commit quota reservation on ready
        ent.import_tokens_reserved = max(0, ent.import_tokens_reserved - mat.token_count)
        ent.import_tokens_used += mat.token_count
        ledger.committed_amount = mat.token_count
        ledger.status = "committed"
        ledger.provider_input_tokens = ai_result["input_tokens"]
        ledger.provider_output_tokens = ai_result["output_tokens"]
        ledger.provider_cost_usd = ai_result["cost_usd"]

        job.stage = "ready"
        job.committed_tokens = mat.token_count
        job.provider_input_tokens = ai_result["input_tokens"]
        job.provider_output_tokens = ai_result["output_tokens"]
        job.provider_cost_usd = ai_result["cost_usd"]
        job.candidates_count = len(item_candidates)
        job.relations_count = len(rel_candidates)
        mat.status = "review"

        await analytics.track(
            session,
            event_name="import_job_ready",
            user=user,
            properties={
                "job_id": job.id,
                "material_id": mat.id,
                "committed_tokens": job.committed_tokens,
                "candidates_count": job.candidates_count,
                "relations_count": job.relations_count,
            },
        )
        await session.commit()
    except Exception as exc:
        # Release reserved quota on failure
        ent.import_tokens_reserved = max(0, ent.import_tokens_reserved - mat.token_count)
        ledger.status = "released"
        ledger.committed_amount = 0
        job.stage = "failed"
        job.error_code = "EXTRACTION_FAILED"
        job.error_message = str(exc)
        mat.status = "failed"
        await session.commit()
        raise HTTPException(
            status_code=500,
            detail={"code": "EXTRACTION_FAILED", "message": str(exc)},
        ) from exc

    return await _serialize_import_job_with_candidates(session, job)


async def _serialize_import_job_with_candidates(session: AsyncSession, job: ImportJob) -> dict[str, Any]:
    cands_res = await session.execute(
        select(Candidate)
        .where(Candidate.import_job_id == job.id)
        .order_by(Candidate.created_at.asc())
    )
    all_cands = list(cands_res.scalars().all())
    items_payload = [
        {
            "id": c.id,
            "candidate_kind": c.candidate_kind,
            "item_type": c.item_type,
            "prompt": c.prompt,
            "answer": c.answer,
            "applicability": c.applicability,
            "fragment_id": c.fragment_id,
            "anchor_label": c.anchor_label,
            "quote_text": c.quote_text,
            "warning_note": c.warning_note,
            "selected": c.selected,
            "review_status": c.review_status,
            "accepted_entity_id": c.accepted_entity_id,
        }
        for c in all_cands
        if c.candidate_kind == "item"
    ]
    relations_payload = [
        {
            "id": c.id,
            "candidate_kind": c.candidate_kind,
            "prompt": c.prompt,
            "explanation": c.answer,
            "relation_type": (c.extra_payload or {}).get("relation_type", c.applicability or "consequence"),
            "from_candidate_id": (c.extra_payload or {}).get("from_candidate_id"),
            "to_candidate_id": (c.extra_payload or {}).get("to_candidate_id"),
            "anchor_label": c.anchor_label,
            "selected": c.selected,
            "review_status": c.review_status,
            "accepted_entity_id": c.accepted_entity_id,
        }
        for c in all_cands
        if c.candidate_kind == "relation"
    ]
    return {
        "job": {
            "id": job.id,
            "operation_id": job.operation_id,
            "material_id": job.material_id,
            "topic_id": job.topic_id,
            "stage": job.stage,
            "reserved_tokens": job.reserved_tokens,
            "committed_tokens": job.committed_tokens,
            "candidates_count": len(items_payload),
            "relations_count": len(relations_payload),
            "error_code": job.error_code,
            "error_message": job.error_message,
        },
        "item_candidates": items_payload,
        "relation_candidates": relations_payload,
    }


@router.get("/materials/import-jobs/{job_id}")
async def get_import_job_d17_d18(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    job = (
        await session.execute(
            select(ImportJob).where(ImportJob.id == job_id, ImportJob.owner_id == user.id)
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Import job not found")
    return await _serialize_import_job_with_candidates(session, job)


@router.post("/materials/import-jobs/{job_id}/cancel")
async def cancel_import_job_d17(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """D17: Cancel an import job and release any reserved quota."""
    job = (
        await session.execute(
            select(ImportJob).where(ImportJob.id == job_id, ImportJob.owner_id == user.id)
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Import job not found")

    if job.stage not in ("ready", "cancelled", "failed"):
        ent = await ensure_or_get_entitlement(session, user)
        ent.import_tokens_reserved = max(0, ent.import_tokens_reserved - job.reserved_tokens)
        ledger = (
            await session.execute(
                select(QuotaLedger).where(QuotaLedger.operation_id == job.operation_id)
            )
        ).scalar_one_or_none()
        if ledger and ledger.status == "reserved":
            ledger.status = "released"
            ledger.committed_amount = 0
        job.stage = "cancelled"
        job.cancel_requested = True
        await session.commit()

    return {"ok": True, "stage": job.stage}


@router.patch("/materials/candidates/{candidate_id}")
async def update_candidate_d18(
    candidate_id: str,
    payload: CandidateUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """D18: Edit candidate prompt, answer, applicability, item_type, or selection before accepting."""
    cand = (
        await session.execute(
            select(Candidate).where(Candidate.id == candidate_id, Candidate.owner_id == user.id)
        )
    ).scalar_one_or_none()
    if cand is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if payload.prompt is not None:
        cand.prompt = payload.prompt.strip()
    if payload.answer is not None:
        cand.answer = payload.answer.strip()
    if payload.applicability is not None:
        cand.applicability = payload.applicability.strip()
    if payload.item_type is not None:
        cand.item_type = payload.item_type
    if payload.selected is not None:
        cand.selected = payload.selected
    if payload.review_status is not None:
        cand.review_status = payload.review_status

    await session.commit()
    return {
        "candidate": {
            "id": cand.id,
            "item_type": cand.item_type,
            "prompt": cand.prompt,
            "answer": cand.answer,
            "applicability": cand.applicability,
            "selected": cand.selected,
            "review_status": cand.review_status,
        }
    }


@router.post("/materials/import-jobs/{job_id}/accept")
async def accept_candidates_d18(
    job_id: str,
    payload: AcceptCandidatesRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    D18 -> D18-Accepted:
    - Converts selected/specified `item` candidates into active `KnowledgeItem`s with `ReviewState`s and `Exercise`s.
    - Separately converts confirmed `relation` candidates into `KnowledgeRelation`s (never auto-activating unconfirmed AI relations).
    """
    job = (
        await session.execute(
            select(ImportJob).where(ImportJob.id == job_id, ImportJob.owner_id == user.id)
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Import job not found")

    cands_res = await session.execute(
        select(Candidate).where(Candidate.import_job_id == job.id).order_by(Candidate.created_at.asc())
    )
    all_cands = list(cands_res.scalars().all())

    item_id_filter = set(payload.item_candidate_ids) if payload.item_candidate_ids is not None else None
    rel_id_filter = set(payload.relation_candidate_ids) if payload.relation_candidate_ids is not None else None

    cand_to_item_id: dict[str, str] = {}
    accepted_items: list[KnowledgeItem] = []

    for c in all_cands:
        if c.candidate_kind != "item":
            continue
        should_accept = (c.id in item_id_filter) if item_id_filter is not None else c.selected
        if not should_accept:
            c.review_status = "rejected"
            continue
        if c.review_status == "accepted" and c.accepted_entity_id:
            cand_to_item_id[c.id] = c.accepted_entity_id
            continue

        objs = ["recall", "explain"] if c.item_type in ("concept", "procedure") else ["recall"]
        item = KnowledgeItem(
            owner_id=user.id,
            topic_id=job.topic_id,
            material_id=job.material_id,
            fragment_id=c.fragment_id,
            item_type=c.item_type,
            origin="ai_accepted",
            prompt=c.prompt,
            answer=c.answer,
            applicability=c.applicability,
            applicable_objectives=objs,
            status="active",
        )
        session.add(item)
        await session.flush()
        await _ensure_item_exercises_and_review_states(session, item)

        c.review_status = "accepted"
        c.accepted_entity_id = item.id
        cand_to_item_id[c.id] = item.id
        accepted_items.append(item)

    accepted_relations: list[KnowledgeRelation] = []
    for c in all_cands:
        if c.candidate_kind != "relation":
            continue
        should_accept_rel = (c.id in rel_id_filter) if rel_id_filter is not None else c.selected
        if not should_accept_rel:
            c.review_status = "rejected"
            continue
        if c.review_status == "accepted" and c.accepted_entity_id:
            continue

        extra = c.extra_payload or {}
        from_cid = extra.get("from_candidate_id")
        to_cid = extra.get("to_candidate_id")
        from_iid = cand_to_item_id.get(from_cid) if from_cid else None
        to_iid = cand_to_item_id.get(to_cid) if to_cid else None
        if not from_iid or not to_iid:
            continue

        rel = KnowledgeRelation(
            owner_id=user.id,
            topic_id=job.topic_id,
            from_item_id=from_iid,
            to_item_id=to_iid,
            relation_type=extra.get("relation_type") or "consequence",
            direction="forward",
            explanation=c.answer or extra.get("explanation") or "",
            provenance="ai_draft",
            approval_status="confirmed",
        )
        session.add(rel)
        await session.flush()
        c.review_status = "accepted"
        c.accepted_entity_id = rel.id
        accepted_relations.append(rel)

    mat = (
        await session.execute(select(Material).where(Material.id == job.material_id))
    ).scalar_one_or_none()
    if mat:
        mat.status = "accepted"

    if user.first_activation_at is None and accepted_items:
        user.first_activation_at = datetime.now(timezone.utc)

    await analytics.track(
        session,
        event_name="candidates_accepted",
        user=user,
        properties={
            "job_id": job.id,
            "topic_id": job.topic_id,
            "accepted_items_count": len(accepted_items),
            "accepted_relations_count": len(accepted_relations),
        },
    )
    await session.commit()

    return {
        "ok": True,
        "topic_id": job.topic_id,
        "accepted_items_count": len(accepted_items),
        "accepted_relations_count": len(accepted_relations),
        "accepted_item_ids": [it.id for it in accepted_items],
        "accepted_relation_ids": [r.id for r in accepted_relations],
    }


@router.get("/quota/status")
async def get_quota_status_d30(
    resource: str = "import_tokens",
    required_amount: int = 1,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """D30: Quota and limit state sheet payload."""
    ent = await ensure_or_get_entitlement(session, user)
    await session.commit()
    return build_d30_quota_payload(ent, resource, required_amount)
