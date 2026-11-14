from __future__ import annotations

from fastapi.testclient import TestClient

from brainrecall.main import app


def test_progress_weekly_reviews_notifications_exports_deletion_and_mcp() -> None:
    headers = {"X-Demo-User-Id": "770007"}

    with TestClient(app) as client:
        # 1. Bootstrap user & create a topic + card
        r = client.post("/api/v1/auth/bootstrap", headers=headers, json={})
        assert r.status_code == 200

        rt = client.post(
            "/api/v1/topics",
            headers=headers,
            json={"title": "Нейробиология памяти", "goal": "exam"},
        )
        assert rt.status_code == 201
        topic_id = rt.json()["topic"]["id"]

        ri = client.post(
            "/api/v1/items",
            headers=headers,
            json={
                "topic_id": topic_id,
                "item_type": "concept",
                "prompt": "В чём роль гиппокампа в консолидации памяти?",
                "answer": "Гиппокамп связывает распределённые корковые следы в единый эпизод и переносит их в неокортекс.",
                "applicable_objectives": ["recall", "explain"],
            },
        )
        assert ri.status_code == 201

        # 2. D24: Progress summary -> <3 attempts shows sufficient_data == False and explicit k/N
        r_prog = client.get("/api/v1/progress?window_days=7", headers=headers)
        assert r_prog.status_code == 200
        prog = r_prog.json()
        assert prog["overall"]["total_count"] == 0
        assert prog["overall"]["sufficient_data"] is False
        assert prog["overall"]["percentage"] is None

        # 3. D25: Progress drilldown
        r_dd = client.get("/api/v1/progress/drilldown?window_days=30", headers=headers)
        assert r_dd.status_code == 200
        assert len(r_dd.json()["topics"]) == 1

        # 4. D35: Generate Weekly Review
        r_wr = client.post("/api/v1/weekly-reviews/generate?use_ai=false", headers=headers)
        assert r_wr.status_code == 201
        wr = r_wr.json()["weekly_review"]
        assert wr["ai_summary"]
        assert len(wr["ai_suggestions"]) >= 2

        # 5. D31: Notification settings & quiet hours
        r_not = client.patch(
            "/api/v1/notifications",
            headers=headers,
            json={
                "enabled": True,
                "write_access_granted": True,
                "daily_time": "09:15",
                "quiet_start": "22:30",
                "quiet_end": "07:30",
            },
        )
        assert r_not.status_code == 200
        notif = r_not.json()["notifications"]
        assert notif["enabled"] is True
        assert notif["write_access_granted"] is True
        assert notif["daily_time"] == "09:15"

        # 6. MCP Assistant Endpoint (/api/v1/mcp)
        r_mcp_init = client.post(
            "/api/v1/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
        assert r_mcp_init.status_code == 200
        assert r_mcp_init.json()["result"]["serverInfo"]["name"] == "brainrecall-mcp"

        r_mcp_call = client.post(
            "/api/v1/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "search_knowledge", "arguments": {"query": "гиппокамп"}},
            },
        )
        assert r_mcp_call.status_code == 200
        assert "гиппокамп" in r_mcp_call.json()["result"]["content"][0]["text"].lower()

        # 7. D32: Data export (JSON & Markdown)
        r_exp = client.post("/api/v1/exports", headers=headers)
        assert r_exp.status_code == 201
        exp_data = r_exp.json()
        assert exp_data["ok"] is True
        assert exp_data["counts"]["topics"] == 1
        assert exp_data["counts"]["items"] == 1
        dl_token = exp_data["download_token"]

        r_dl_md = client.get(f"/api/v1/exports/{dl_token}?format=md")
        assert r_dl_md.status_code == 200
        assert "Нейробиология памяти" in r_dl_md.json()["content"]

        # 8. D32: Account & Data Deletion -> purges user, topics, items, and analytics; leaves DeletionJob token
        r_del = client.post(
            "/api/v1/account/delete",
            headers=headers,
            json={"confirm_phrase": "DELETE"},
        )
        assert r_del.status_code == 200
        del_res = r_del.json()
        assert del_res["ok"] is True
        assert del_res["status"] == "completed"
        status_token = del_res["status_token"]

        r_status = client.get(f"/api/v1/account/deletion-status/{status_token}")
        assert r_status.status_code == 200
        assert r_status.json()["status"] == "completed"
