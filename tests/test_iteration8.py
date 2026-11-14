from __future__ import annotations

from pathlib import Path
from fastapi.testclient import TestClient

from brainrecall.config import PLAN_LIMITS
from brainrecall.i18n import verify_catalog_parity
from brainrecall.main import app
from brainrecall.science_catalog import get_science_catalog_for_locale

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_acceptance_gate_docs_and_catalogs() -> None:
    # 1. Verify required handover documentation exists and is non-empty
    for doc_name in ("README.md", "GROWTH_PLAN.md", "LISTING_CHECKLIST.md", "OPS_RUNBOOK.md"):
        doc_path = PROJECT_ROOT / doc_name
        assert doc_path.exists(), f"Missing required handover doc: {doc_name}"
        assert len(doc_path.read_text(encoding="utf-8")) > 200

    # 2. Verify 100% i18n parity between RU and EN
    ok, errors = verify_catalog_parity()
    assert ok is True, f"i18n parity errors: {errors}"

    # 3. Verify D42 science catalog rules (80% and 33-36% only on M1, M5 indirect)
    for loc in ("ru", "en"):
        cat = get_science_catalog_for_locale(loc)
        assert len(cat) == 5
        by_id = {m["method_id"]: m for m in cat}
        assert by_id["M1"]["metrics_highlight"]["delayed_recall_test_pct"] == "80%"
        assert by_id["M5"]["evidence_level"] == "indirect"
        for mid in ("M2", "M3", "M4", "M5"):
            assert by_id[mid]["metrics_highlight"] is None

    # 4. Verify PLAN_LIMITS match Dev Spec v1.14 table exactly
    assert PLAN_LIMITS["free"]["price_xtr"] == 0
    assert PLAN_LIMITS["free"]["topics"] == 3
    assert PLAN_LIMITS["free"]["habits"] == 3
    assert PLAN_LIMITS["free"]["items"] == 500
    assert PLAN_LIMITS["trial"]["period_days"] == 7
    assert PLAN_LIMITS["trial"]["import_tokens"] == 30_000
    assert PLAN_LIMITS["start"]["price_xtr"] == 499
    assert PLAN_LIMITS["start"]["import_tokens"] == 200_000
    assert PLAN_LIMITS["pro"]["price_xtr"] == 1099
    assert PLAN_LIMITS["pro"]["import_tokens"] == 600_000


def test_full_end_to_end_journey_and_anti_abuse_trial_registry() -> None:
    headers = {"X-Demo-User-Id": "770008"}

    with TestClient(app) as client:
        # 1. Bootstrap & complete onboarding D02
        r = client.post("/api/v1/auth/bootstrap", headers=headers, json={})
        assert r.status_code == 200
        r_onb = client.post(
            "/api/v1/onboarding",
            headers=headers,
            json={
                "goal_focus": "both",
                "daily_study_minutes": 10,
                "reminder_window": "morning",
                "timezone": "Europe/Moscow",
            },
        )
        assert r_onb.status_code == 200
        assert r_onb.json()["next_screen"] == "D03"

        # 2. Activate 7-day Trial via AI material import
        r_mat = client.post(
            "/api/v1/materials/text",
            headers=headers,
            json={
                "title": "Проверка защиты пробного периода",
                "goal": "exam",
                "language": "ru",
                "text": "Активное припоминание — извлечение ответа из памяти без подсказки. Интервальное повторение закрепляет след.",
            },
        )
        assert r_mat.status_code == 201
        mat_id = r_mat.json()["material"]["id"]

        r_job = client.post(
            "/api/v1/materials/import-jobs",
            headers=headers,
            json={
                "material_id": mat_id,
                "operation_id": "qa-trial-op-1",
                "activate_trial": True,
                "ai_consent_accepted": True,
            },
        )
        assert r_job.status_code == 201

        # 3. Delete account completely (D32)
        r_del = client.post("/api/v1/account/delete", headers=headers, json={"confirm_phrase": "DELETE"})
        assert r_del.status_code == 200

        # 4. Re-register with the SAME Telegram ID -> TrialRegistry prevents a second free trial!
        r_re = client.post("/api/v1/auth/bootstrap", headers=headers, json={})
        assert r_re.status_code == 200

        r_plans = client.get("/api/v1/billing/plans", headers=headers)
        assert r_plans.status_code == 200
        ent = r_plans.json()["entitlement"]
        assert ent["plan_code"] == "free"
        assert ent["trial_used"] is True
        assert ent["trial_eligible"] is False
