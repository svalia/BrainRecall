from __future__ import annotations

from pathlib import Path
import re

from fastapi.testclient import TestClient
import pytest

from brainrecall.i18n import get_catalog, resolve_user_locale, t, verify_catalog_parity
from brainrecall.main import app


def test_i18n_catalog_parity() -> None:
    ok, errors = verify_catalog_parity()
    assert ok, f"Catalog parity errors: {errors}"
    assert t("miniapp.common.why_this_exercise", "ru") == "Зачем это упражнение?"
    assert t("miniapp.common.why_this_exercise", "en") == "Why this exercise?"


def test_locale_resolution_priority() -> None:
    assert (
        resolve_user_locale(
            locale_override="en",
            saved_locale="ru",
            telegram_language_code="ru",
            accept_language="ru-RU,ru;q=0.9",
        )
        == "en"
    )
    assert resolve_user_locale(telegram_language_code="en-US") == "en"
    assert resolve_user_locale(telegram_language_code="de") == "ru"


def test_no_shadowing_of_t_in_frontend_js() -> None:
    js_path = Path(__file__).resolve().parent.parent / "miniapp" / "app.js"
    code = js_path.read_text(encoding="utf-8")
    # Ensure no arrow/callback param `(t)` or `function(t)` or `let t =` or `const t =` shadows `function t(key, params)`
    forbidden_patterns = [
        r"\b(?:const|let|var)\s+t\s*=",
        r"function\s*\(\s*t\s*[,)]",
        r"\(\s*t\s*\)\s*=>",
        r"\bt\s*=>",
    ]
    for pat in forbidden_patterns:
        matches = re.findall(pat, code)
        assert not matches, f"Identifier `t` shadowed in miniapp/app.js matching {pat}: {matches}"


def test_bootstrap_and_d42_method_intros() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        # Bootstrap in demo mode
        resp = client.post(
            "/api/v1/auth/bootstrap",
            json={"demo_mode": True, "locale_hint": "en"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is True
        token = data["session_token"]
        assert token
        methods = data["method_intros"]
        assert len(methods) == 5
        m1 = next(m for m in methods if m["method_id"] == "M1")
        m5 = next(m for m in methods if m["method_id"] == "M5")
        assert m1["metrics_highlight"]["delayed_recall_test_pct"] == "80%"
        assert m5["evidence_level"] == "indirect"

        # Dismiss M1 -> status should be dismissed, not acknowledged
        r_dismiss = client.put(
            "/api/v1/me/method-intros/M1",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "dismissed"},
        )
        assert r_dismiss.status_code == 200
        assert r_dismiss.json()["status"] == "dismissed"
        assert r_dismiss.json()["seen_content_version"] is None

        # Acknowledge M1 -> status becomes acknowledged with seen_content_version
        r_ack = client.put(
            "/api/v1/me/method-intros/M1",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "acknowledged"},
        )
        assert r_ack.status_code == 200
        assert r_ack.json()["status"] == "acknowledged"
        assert r_ack.json()["seen_content_version"] == "2026-04-14.1"

        # Save onboarding D02
        r_onb = client.post(
            "/api/v1/onboarding",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "goal_focus": "both",
                "daily_study_minutes": 15,
                "reminder_window": "morning",
                "timezone": "Europe/Moscow",
                "locale_override": "ru",
            },
        )
        assert r_onb.status_code == 200
        assert r_onb.json()["user"]["onboarding_completed"] is True
        assert r_onb.json()["user"]["locale_override"] == "ru"
