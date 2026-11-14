"""DeepSeek AI adapter with deterministic fallback, cost tracking, and JSON validation (Dev Spec v1.14 Section 8)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from brainrecall.config import settings

logger = logging.getLogger(__name__)


def estimate_token_count(text: str) -> int:
    """Deterministic token estimate (~3.5 chars per token for mixed RU/EN text)."""
    cleaned = text.strip()
    if not cleaned:
        return 0
    return max(1, int(len(cleaned) / 3.5) + 1)


class DeepSeekAdapter:
    """Calls DeepSeek Chat API (`deepseek-chat`) with structured JSON output and deterministic fallback."""

    def __init__(self) -> None:
        self.api_key = settings.deepseek_api_key
        self.base_url = settings.deepseek_base_url.rstrip("/")
        self.model = settings.deepseek_model

    @property
    def is_live_enabled(self) -> bool:
        return bool(self.api_key and not settings.ai_global_kill_switch and settings.app_env == "production")

    async def extract_candidates_from_fragments(
        self,
        *,
        title: str,
        goal: str,
        language: str,
        fragments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Extract knowledge item candidates and M5 relation candidates from parsed source fragments.
        Returns:
          {
            "items": [...],
            "relations": [...],
            "input_tokens": int,
            "output_tokens": int,
            "cost_usd": float,
            "model": str
          }
        """
        if not fragments:
            return {
                "items": [],
                "relations": [],
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
                "model": "deterministic-empty",
            }

        if self.is_live_enabled:
            try:
                return await self._call_live_deepseek(
                    title=title,
                    goal=goal,
                    language=language,
                    fragments=fragments,
                )
            except Exception as exc:
                logger.warning("DeepSeek live extraction failed, using deterministic extractor: %s", exc)

        return self._deterministic_extract(
            title=title,
            goal=goal,
            language=language,
            fragments=fragments,
        )

    async def _call_live_deepseek(
        self,
        *,
        title: str,
        goal: str,
        language: str,
        fragments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        sample_fragments = fragments[:25]
        fragments_text = "\n\n".join(
            f"[FRAGMENT index={idx} id={f['id']} anchor=\"{f['anchor_label']}\"]\n{f['quote_text']}"
            for idx, f in enumerate(sample_fragments)
        )
        system_prompt = (
            "You are an expert cognitive learning extractor for BrainRecall. "
            "Extract verifiable knowledge items (fact, concept, formula, procedure, word, opinion) "
            "and directed semantic relations (basis, consequence, contrasts, condition_for, example) "
            "strictly grounded in the provided fragments. "
            "Return ONLY valid JSON with keys 'items' and 'relations'."
        )
        user_prompt = (
            f"Material Title: {title}\nGoal: {goal}\nLanguage: {language}\n\n"
            f"Source Fragments:\n{fragments_text}\n\n"
            "Output JSON schema:\n"
            "{\n"
            '  "items": [\n'
            '    {"item_type": "concept|fact|formula|procedure|word|opinion", '
            '"prompt": "Question for active recall", "answer": "Clear concise answer", '
            '"applicability": "When/where this applies", "fragment_index": 0, '
            '"warning_note": null}\n'
            "  ],\n"
            '  "relations": [\n'
            '    {"from_item_index": 0, "to_item_index": 1, '
            '"relation_type": "consequence|basis|contrasts|condition_for|example", '
            '"explanation": "Why item 0 leads to or contrasts with item 1"}\n'
            "  ]\n"
            "}"
        )

        async with httpx.AsyncClient(timeout=35.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                    "max_tokens": 2500,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        usage = data.get("usage") or {}
        in_tok = int(usage.get("prompt_tokens") or estimate_token_count(user_prompt))
        out_tok = int(usage.get("completion_tokens") or estimate_token_count(content))
        cost_usd = round((in_tok * 0.00000027) + (out_tok * 0.0000011), 6)

        items_out: list[dict[str, Any]] = []
        for raw_item in (parsed.get("items") or [])[:20]:
            f_idx = int(raw_item.get("fragment_index") or 0)
            frag = sample_fragments[min(max(0, f_idx), len(sample_fragments) - 1)]
            items_out.append(
                {
                    "item_type": raw_item.get("item_type") or "concept",
                    "prompt": str(raw_item.get("prompt") or "").strip(),
                    "answer": str(raw_item.get("answer") or "").strip(),
                    "applicability": str(raw_item.get("applicability") or "").strip(),
                    "fragment_id": frag["id"],
                    "anchor_label": frag["anchor_label"],
                    "quote_text": frag["quote_text"][:400],
                    "warning_note": raw_item.get("warning_note"),
                }
            )

        items_out = [it for it in items_out if it["prompt"] and it["answer"]]
        if not items_out:
            return self._deterministic_extract(title=title, goal=goal, language=language, fragments=fragments)

        relations_out: list[dict[str, Any]] = []
        for raw_rel in (parsed.get("relations") or [])[:10]:
            fi = int(raw_rel.get("from_item_index") or 0)
            ti = int(raw_rel.get("to_item_index") or 0)
            if 0 <= fi < len(items_out) and 0 <= ti < len(items_out) and fi != ti:
                relations_out.append(
                    {
                        "from_item_index": fi,
                        "to_item_index": ti,
                        "relation_type": raw_rel.get("relation_type") or "consequence",
                        "explanation": str(raw_rel.get("explanation") or "").strip(),
                    }
                )

        return {
            "items": items_out,
            "relations": relations_out,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cost_usd": cost_usd,
            "model": self.model,
        }

    def _deterministic_extract(
        self,
        *,
        title: str,
        goal: str,
        language: str,
        fragments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Deterministic high-precision fallback extractor from source fragments."""
        items_out: list[dict[str, Any]] = []
        is_en = language.lower().startswith("en")

        for idx, frag in enumerate(fragments[:12]):
            quote = frag["quote_text"].strip()
            if not quote:
                continue

            # Split into sentences or key definitions
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", quote) if len(s.strip()) >= 12]
            primary = sentences[0] if sentences else quote[:240]
            secondary = " ".join(sentences[1:3]) if len(sentences) > 1 else quote[:300]

            # Detect formula or opinion
            item_type = "concept"
            warning_note = None
            if "=" in quote and any(ch.isdigit() or ch in "+-*/^" for ch in quote):
                item_type = "formula"
            elif any(w in quote.lower() for w in ("считаю", "мнение", "вероятно", "opinion", "believe", "hypothesis")):
                item_type = "opinion"
                warning_note = (
                    "Requires verification: marked as author opinion/hypothesis"
                    if is_en
                    else "Требует проверки: отмечено как мнение или гипотеза"
                )
            elif idx % 2 == 1:
                item_type = "fact"

            # Check if colon/dash definition exists
            if "—" in primary or ":" in primary:
                sep = "—" if "—" in primary else ":"
                parts = primary.split(sep, 1)
                term = parts[0].strip(" -•*«»\"'")
                definition = parts[1].strip()
                if len(term) >= 3 and len(definition) >= 5:
                    prompt = (
                        f"What is {term} and how does it work?"
                        if is_en
                        else f"В чём суть понятия «{term}» и как оно работает?"
                    )
                    answer = definition if len(definition) >= 15 else quote[:280]
                else:
                    prompt = (
                        f"Key idea from {title} ({frag['anchor_label']})?"
                        if is_en
                        else f"Ключевая мысль из «{title}» ({frag['anchor_label']})?"
                    )
                    answer = quote[:280]
            else:
                snippet = primary[:70].rstrip(".!?")
                prompt = (
                    f"Explain the principle: \"{snippet}...\" ({frag['anchor_label']})"
                    if is_en
                    else f"Раскройте принцип: «{snippet}...» ({frag['anchor_label']})"
                )
                answer = secondary if len(secondary) >= 20 else primary

            applicability = (
                f"Goal: {goal} · Source: {frag['anchor_label']}"
                if is_en
                else f"Цель: {goal} · Источник: {frag['anchor_label']}"
            )

            items_out.append(
                {
                    "item_type": item_type,
                    "prompt": prompt,
                    "answer": answer,
                    "applicability": applicability,
                    "fragment_id": frag["id"],
                    "anchor_label": frag["anchor_label"],
                    "quote_text": quote[:400],
                    "warning_note": warning_note,
                }
            )

        relations_out: list[dict[str, Any]] = []
        if len(items_out) >= 2:
            relations_out.append(
                {
                    "from_item_index": 0,
                    "to_item_index": 1,
                    "relation_type": "consequence",
                    "explanation": (
                        "First concept provides the foundation for the second point in the source."
                        if is_en
                        else "Первое положение служит основой для следующего вывода в источнике."
                    ),
                }
            )
        if len(items_out) >= 3:
            relations_out.append(
                {
                    "from_item_index": 1,
                    "to_item_index": 2,
                    "relation_type": "condition_for",
                    "explanation": (
                        "Connects sequential steps from the material."
                        if is_en
                        else "Связывает последовательные шаги из исходного материала."
                    ),
                }
            )

        full_text = "\n".join(f["quote_text"] for f in fragments)
        in_tok = estimate_token_count(full_text)
        out_tok = max(60, len(items_out) * 45)
        cost_usd = round((in_tok * 0.00000027) + (out_tok * 0.0000011), 6)

        return {
            "items": items_out,
            "relations": relations_out,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cost_usd": cost_usd,
            "model": self.model,
        }


deepseek_adapter = DeepSeekAdapter()
