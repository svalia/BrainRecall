from __future__ import annotations

from fastapi.testclient import TestClient

from brainrecall.main import app


def test_billing_plans_subscribe_cancel_refund_and_d29_active_set() -> None:
    headers = {"X-Demo-User-Id": "770006"}

    with TestClient(app) as client:
        # 1. Bootstrap user
        r = client.post("/api/v1/auth/bootstrap", headers=headers, json={})
        assert r.status_code == 200

        # 2. D27: Fetch plans and initial Free entitlement
        r = client.get("/api/v1/billing/plans", headers=headers)
        assert r.status_code == 200
        plans_data = r.json()
        assert plans_data["entitlement"]["plan_code"] == "free"
        assert plans_data["plans"]["start"]["price_xtr"] == 499
        assert plans_data["plans"]["pro"]["price_xtr"] == 1099

        # 3. D28: Subscribe to Start (499 XTR, 30 days) in dev mode
        r = client.post(
            "/api/v1/billing/subscribe",
            headers=headers,
            json={"plan_code": "start", "confirm_immediately_in_dev": True},
        )
        assert r.status_code == 200
        sub_res = r.json()
        assert sub_res["ok"] is True
        assert sub_res["plan_code"] == "start"
        assert sub_res["amount_xtr"] == 499
        assert sub_res["subscription_period"] == 2592000
        assert sub_res["status"] == "paid"

        # Verify Start quotas are active (10 topics, 10 habits, 200k import tokens)
        r = client.get("/api/v1/billing/plans", headers=headers)
        assert r.status_code == 200
        ent = r.json()["entitlement"]
        assert ent["plan_code"] == "start"
        assert ent["auto_renew"] is True
        assert ent["usage"]["import_tokens"]["limit"] == 200000
        assert ent["usage"]["topics_limit"] == 10

        # Create 5 topics and 4 habits while on Start
        topic_ids: list[str] = []
        for idx in range(5):
            rt = client.post(
                "/api/v1/topics",
                headers=headers,
                json={"title": f"Тема Start #{idx + 1}", "goal": "exam"},
            )
            assert rt.status_code == 201
            topic_ids.append(rt.json()["topic"]["id"])

        habit_ids: list[str] = []
        for idx in range(4):
            rh = client.post(
                "/api/v1/habits",
                headers=headers,
                json={
                    "habit_kind": "build",
                    "title": f"Привычка Start #{idx + 1}",
                    "signal": "Утром",
                    "action": "15 минут практики",
                    "minimum_version": "2 минуты",
                },
            )
            assert rh.status_code == 201
            habit_ids.append(rh.json()["habit"]["id"])

        # 4. D28: Cancel auto-renewal -> access remains active until period_end
        r = client.post("/api/v1/billing/cancel", headers=headers)
        assert r.status_code == 200
        cancel_res = r.json()
        assert cancel_res["ok"] is True
        assert cancel_res["plan_code"] == "start"
        assert cancel_res["auto_renew"] is False
        assert cancel_res["period_end"] is not None

        # 5. D28: Request refund (0 AI quota used) -> reverts to Free and flags D29 downgrade selection
        r = client.post("/api/v1/billing/refund", headers=headers, json={"reason": "Тестовый возврат"})
        assert r.status_code == 200
        ref_res = r.json()
        assert ref_res["ok"] is True
        assert ref_res["plan_code"] == "free"
        assert ref_res["downgrade_selection_required"] is True
        assert ref_res["active_topics"] == 5
        assert ref_res["active_habits"] == 4

        # 6. D29: Select 3 active topics and 3 active habits -> remaining become readonly (never deleted)
        r = client.post(
            "/api/v1/billing/select-active-set",
            headers=headers,
            json={
                "active_topic_ids": topic_ids[:3],
                "active_habit_ids": habit_ids[:3],
            },
        )
        assert r.status_code == 200
        sel_res = r.json()
        assert sel_res["ok"] is True
        assert sel_res["active_topics_count"] == 3
        assert sel_res["readonly_topics_count"] == 2
        assert sel_res["active_habits_count"] == 3
        assert sel_res["readonly_habits_count"] == 1
