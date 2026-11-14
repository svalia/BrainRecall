from __future__ import annotations

from fastapi.testclient import TestClient

from brainrecall.main import app
from brainrecall.scheduler import compute_next_review_state


def test_m2_scheduler_intervals_and_assisted_rules() -> None:
    # Step 0 -> Step 1 (1 day) on independent correct
    t1 = compute_next_review_state(
        current_step_index=0,
        last_independent_success_date=None,
        grade="correct",
        assisted=False,
        local_date="2026-04-14",
    )
    assert t1["step_index"] == 1
    assert t1["interval_days"] == 1
    assert t1["increment_independent"] is True

    # Same-day repeat does NOT advance step_index beyond 1
    t_same_day = compute_next_review_state(
        current_step_index=1,
        last_independent_success_date="2026-04-14",
        grade="correct",
        assisted=False,
        local_date="2026-04-14",
    )
    assert t_same_day["step_index"] == 1
    assert t_same_day["increment_independent"] is False

    # Next local day advances Step 1 -> Step 2 (3 days) -> Step 3 (7 days)
    t2 = compute_next_review_state(
        current_step_index=1,
        last_independent_success_date="2026-04-14",
        grade="correct",
        assisted=False,
        local_date="2026-04-15",
    )
    assert t2["step_index"] == 2
    assert t2["interval_days"] == 3

    # Assisted success caps interval at 1 day and does not increment independent count
    t_assisted = compute_next_review_state(
        current_step_index=2,
        last_independent_success_date="2026-04-15",
        grade="correct",
        assisted=True,
        local_date="2026-04-18",
    )
    assert t_assisted["interval_days"] == 1
    assert t_assisted["increment_independent"] is False


def test_study_session_flow_rubric_gap_and_corrective_retry() -> None:
    with TestClient(app) as client:
        boot = client.post(
            "/api/v1/auth/bootstrap",
            headers={"X-Demo-User-Id": "999000333"},
            json={"demo_mode": True, "locale_hint": "ru"},
        )
        token = boot.json()["session_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create topic and item with explain objective & 3 rubric criteria
        r_top = client.post(
            "/api/v1/topics",
            headers=headers,
            json={"title": "Методы обучения M1-M5", "goal": "exam"},
        )
        assert r_top.status_code == 201, r_top.text
        topic_id = r_top.json()["topic"]["id"]

        r_it = client.post(
            "/api/v1/items",
            headers=headers,
            json={
                "topic_id": topic_id,
                "item_type": "concept",
                "prompt": "Почему самообъяснение (M4) помогает заметить иллюзию понимания?",
                "answer": "Оно заставляет проследить причинно-следственные связи и выявить пропущенные звенья механизма.",
                "rubric_criteria": [
                    "Названа причинно-следственная цепочка",
                    "Упомянута иллюзия глубины понимания",
                    "Указано выявление пробела до подсказки",
                ],
                "applicable_objectives": ["explain"],
                "quote_text": "Chi et al. (1994) & Rozenblit & Keil (2002)",
                "anchor_label": "гл. 4, абз. 2",
            },
        )
        assert r_it.status_code == 201

        # Start a study session (D10)
        r_sess = client.post(
            "/api/v1/sessions",
            headers=headers,
            json={"mode": "regular", "topic_id": topic_id, "max_units": 5},
        )
        assert r_sess.status_code == 201
        sess = r_sess.json()["session"]
        sess_id = sess["id"]
        assert sess["total_units"] >= 1
        unit = sess["current_unit"]
        ex_id = unit["exercise_id"]

        # Save draft answer (Section 3.14 exception: active session draft preserved)
        r_draft = client.patch(
            f"/api/v1/sessions/{sess_id}/draft",
            headers=headers,
            json={"draft_answer": "Черновик объяснения", "support_seen": []},
        )
        assert r_draft.status_code == 200
        assert r_draft.json()["draft_answer"] == "Черновик объяснения"

        # Submit partial attempt missing criterion #2 -> triggers needs_corrective=True
        r_att1 = client.post(
            f"/api/v1/sessions/{sess_id}/attempts",
            headers=headers,
            json={
                "exercise_id": ex_id,
                "phase": "first_attempt",
                "answer_text": "Помогает связать причины и следствия",
                "answer_mode": "written",
                "grading_mode": "self_check",
                "rubric_checked_indices": [0, 1],
            },
        )
        assert r_att1.status_code == 200
        att1_data = r_att1.json()
        assert att1_data["attempt"]["grade"] == "partial"
        assert "выявление пробела" in (att1_data["attempt"]["gap_summary"] or "")
        assert att1_data["needs_corrective"] is True
        assert att1_data["session"]["current_phase"] == "corrective"

        # Submit corrective retry -> marks assisted=True and advances session
        r_att2 = client.post(
            f"/api/v1/sessions/{sess_id}/attempts",
            headers=headers,
            json={
                "exercise_id": ex_id,
                "phase": "corrective",
                "answer_text": "Полное объяснение всех трёх критериев после сверки с источником.",
                "answer_mode": "written",
                "grading_mode": "self_check",
                "self_grade": "correct",
            },
        )
        assert r_att2.status_code == 200
        att2_data = r_att2.json()
        assert att2_data["attempt"]["assisted"] is True
        assert att2_data["needs_corrective"] is False
