from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from brainrecall.main import app


def test_today_habits_streaks_and_freeze() -> None:
    headers = {"X-Demo-User-Id": "770004"}

    with TestClient(app) as client:
        # 1. Bootstrap user
        r = client.post("/api/v1/auth/bootstrap", headers=headers, json={})
        assert r.status_code == 200

        # 2. Fetch /api/v1/today (D03) -> when no items and no habits exist, day_state is neutral
        r = client.get("/api/v1/today", headers=headers)
        assert r.status_code == 200
        today_data = r.json()
        assert "day_plan" in today_data
        assert today_data["day_plan"]["day_state"] in ("neutral", "pending")
        assert today_data["streak"]["current"] == 0
        assert today_data["streak"]["freeze_stock"] == 0

        # 3. Create an atomic habit (D20)
        r = client.post(
            "/api/v1/habits",
            headers=headers,
            json={
                "habit_kind": "build",
                "title": "Читать 10 страниц",
                "signal": "После утреннего кофе",
                "action": "Прочитать 10 страниц книги и выписать 1 идею",
                "minimum_version": "Прочитать 1 абзац",
            },
        )
        assert r.status_code == 201
        habit_id = r.json()["habit"]["id"]

        # Verify /api/v1/today now shows pending since a habit is scheduled
        r = client.get("/api/v1/today", headers=headers)
        assert r.status_code == 200
        assert r.json()["day_plan"]["day_state"] == "pending"

        # 4. Check in habit with minimum_done (D22) -> earns Day 1 + starter freeze + milestone 1
        r = client.post(
            f"/api/v1/habits/{habit_id}/checkin",
            headers=headers,
            json={
                "outcome": "minimum_done",
                "reason_note": "Сделал минимум за кофе",
            },
        )
        assert r.status_code == 200
        checkin_res = r.json()
        assert checkin_res["ok"] is True
        assert checkin_res["habit"]["today_outcome"] == "minimum_done"
        assert checkin_res["day_state"] == "earned"

        # 5. Verify streak, starter freeze (stock == 1), and milestone 1 badge (D36/D38)
        r = client.get("/api/v1/streaks", headers=headers)
        assert r.status_code == 200
        streak_data = r.json()
        assert streak_data["current_streak"] >= 1
        assert streak_data["freeze"]["stock"] == 1
        badges = {b["threshold"]: b for b in streak_data["badges"]}
        assert badges[1]["unlocked"] is True

        # 6. Apply freeze protection to yesterday (D39)
        yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        r = client.post(
            "/api/v1/streaks/freeze-apply",
            headers=headers,
            json={
                "local_date": yesterday_str,
            },
        )
        assert r.status_code == 200
        freeze_res = r.json()
        assert freeze_res["ok"] is True
        assert freeze_res["day_state"] == "frozen"
        assert freeze_res["stock_after"] == 0

        # 7. Verify 7-day retroactive window validation on habit check-in
        too_old_str = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
        r = client.post(
            f"/api/v1/habits/{habit_id}/checkin",
            headers=headers,
            json={
                "outcome": "full_done",
                "local_date": too_old_str,
            },
        )
        assert r.status_code == 400
