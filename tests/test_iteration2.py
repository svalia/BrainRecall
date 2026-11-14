from __future__ import annotations

from fastapi.testclient import TestClient

from brainrecall.main import app


def test_topics_items_d34_groups_d40_d41_and_search() -> None:
    with TestClient(app) as client:
        boot = client.post(
            "/api/v1/auth/bootstrap",
            headers={"X-Demo-User-Id": "999000222"},
            json={"demo_mode": True, "locale_hint": "ru"},
        )
        assert boot.status_code == 200
        token = boot.json()["session_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create a Topic (D07)
        r_topic = client.post(
            "/api/v1/topics",
            headers=headers,
            json={
                "title": "Когнитивная психология",
                "goal": "exam",
                "goal_note": "Подготовка к экзамену по памяти",
            },
        )
        assert r_topic.status_code == 201
        topic = r_topic.json()["topic"]
        topic_id = topic["id"]
        assert topic["revision"] == 1

        # 2. Optimistic concurrency check on Topic update
        r_top_ok = client.patch(
            f"/api/v1/topics/{topic_id}",
            headers=headers,
            json={"title": "Когнитивная психология и память", "revision": 1},
        )
        assert r_top_ok.status_code == 200
        assert r_top_ok.json()["topic"]["revision"] == 2

        r_top_conflict = client.patch(
            f"/api/v1/topics/{topic_id}",
            headers=headers,
            json={"title": "Stale revision", "revision": 1},
        )
        assert r_top_conflict.status_code == 409

        # 3. Create 3 Knowledge Items with source quote (D09 / D34)
        items_created = []
        for idx in range(1, 4):
            r_it = client.post(
                "/api/v1/items",
                headers=headers,
                json={
                    "topic_id": topic_id,
                    "item_type": "concept",
                    "prompt": f"Понятие #{idx}: Эффект тестирования",
                    "answer": f"Извлечение из памяти усиливает след #{idx}",
                    "applicability": "При отсроченной проверке через неделю",
                    "rubric_criteria": ["Активное извлечение", "Долговременное удержание"],
                    "applicable_objectives": ["recall", "explain"],
                    "quote_text": f"Цитата из Roediger & Karpicke (2006), абзац {idx}",
                    "anchor_label": f"стр. {10 + idx}, абз. {idx}",
                },
            )
            assert r_it.status_code == 201
            items_created.append(r_it.json()["item"])

        # Verify D34 fragment endpoint
        frag_id = items_created[0]["fragment_id"]
        assert frag_id
        r_frag = client.get(f"/api/v1/fragments/{frag_id}", headers=headers)
        assert r_frag.status_code == 200
        assert "Roediger" in r_frag.json()["fragment"]["quote_text"]

        # 4. Validate D41 Meaning Group constraints (min 2, max 7, no self-relations)
        r_grp_too_small = client.post(
            "/api/v1/groups",
            headers=headers,
            json={
                "topic_id": topic_id,
                "title": "Неполная группа",
                "principle": "Один элемент",
                "members": [{"item_id": items_created[0]["id"], "role_label": "basis"}],
                "relations": [],
            },
        )
        assert r_grp_too_small.status_code == 422 or r_grp_too_small.status_code == 400

        # Valid 3-member group with directed relation
        r_grp = client.post(
            "/api/v1/groups",
            headers=headers,
            json={
                "topic_id": topic_id,
                "title": "Механизмы долговременного удержания",
                "principle": "Усилие извлечения и распределение во времени гасят забывание",
                "condition": "При наличии обратной связи после попытки",
                "members": [
                    {"item_id": items_created[0]["id"], "role_label": "basis"},
                    {"item_id": items_created[1]["id"], "role_label": "consequence"},
                    {"item_id": items_created[2]["id"], "role_label": "strengthens"},
                ],
                "relations": [
                    {
                        "from_item_id": items_created[0]["id"],
                        "to_item_id": items_created[1]["id"],
                        "relation_type": "consequence",
                        "direction": "forward",
                        "explanation": "Припоминание ведёт к перестройке следа памяти",
                    }
                ],
            },
        )
        assert r_grp.status_code == 201
        grp = r_grp.json()["group"]
        group_id = grp["id"]
        assert grp["status"] == "confirmed"
        assert len(grp["members"]) == 3
        assert len(grp["relations"]) == 1

        # 5. Archive an item in the relation -> relation becomes broken & group transitions to needs_review
        r_arch = client.patch(
            f"/api/v1/items/{items_created[1]['id']}",
            headers=headers,
            json={"status": "archived"},
        )
        assert r_arch.status_code == 200

        r_grp_after = client.get(f"/api/v1/groups/{group_id}", headers=headers)
        assert r_grp_after.status_code == 200
        grp_after = r_grp_after.json()["group"]
        assert grp_after["status"] == "needs_review"
        assert grp_after["relations"][0]["approval_status"] == "broken"

        # 6. Search (D05)
        r_search = client.get("/api/v1/search?q=тестирования", headers=headers)
        assert r_search.status_code == 200
        assert len(r_search.json()["items"]) >= 3
