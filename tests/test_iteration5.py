from __future__ import annotations

import io
import zipfile
from fastapi.testclient import TestClient

from brainrecall.main import app


def _make_sample_docx_bytes(paragraphs: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        body_xml = "".join(
            f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs
        )
        doc_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{body_xml}</w:body></w:document>"
        )
        zf.writestr("word/document.xml", doc_xml.encode("utf-8"))
    return buf.getvalue()


def test_materials_estimate_trial_ai_import_d18_and_d30() -> None:
    headers = {"X-Demo-User-Id": "770005"}

    with TestClient(app) as client:
        # 1. Bootstrap user
        r = client.post("/api/v1/auth/bootstrap", headers=headers, json={})
        assert r.status_code == 200

        # 2. D14: Create material from pasted text
        sample_text = (
            "# Глава 1. Долговременная память\n\n"
            "Припоминание из памяти (Retrieval Practice) — это активное извлечение ответа без подглядывания, "
            "которое укрепляет следы памяти значительно сильнее повторного перечитывания.\n\n"
            "Интервальное повторение (Spaced Practice) — распределение сессий во времени с шагами 1, 3, 7, 14, 30, 60 и 120 дней, "
            "позволяющее консолидировать знания на месяцы вперёд.\n\n"
            "Самообъяснение (Self-Explanation) — формулирование механизма «почему и при каких условиях» работает правило."
        )
        r = client.post(
            "/api/v1/materials/text",
            headers=headers,
            json={
                "title": "Конспект по когнитивной психологии",
                "goal": "exam",
                "language": "ru",
                "text": sample_text,
            },
        )
        assert r.status_code == 201
        mat = r.json()["material"]
        assert mat["token_count"] > 10
        assert mat["fragments_count"] >= 3
        mat_id = mat["id"]

        # 3. D16: Estimate tokens & check Trial eligibility
        r = client.post(
            "/api/v1/materials/estimate",
            headers=headers,
            json={"material_id": mat_id},
        )
        assert r.status_code == 200
        est = r.json()
        assert est["trial_eligible"] is True
        assert est["trial_import_tokens"] == 30000
        assert est["can_proceed"] is True
        assert est["estimate_signature"]

        # 4. D17: Start AI Import Job -> activates 7-day Trial and commits quota
        r = client.post(
            "/api/v1/materials/import-jobs",
            headers=headers,
            json={
                "material_id": mat_id,
                "operation_id": "test-op-iter5-001",
                "estimate_signature": est["estimate_signature"],
                "activate_trial": True,
                "ai_consent_accepted": True,
            },
        )
        assert r.status_code == 201
        job_data = r.json()
        assert job_data["job"]["stage"] == "ready"
        assert job_data["job"]["committed_tokens"] == mat["token_count"]
        item_cands = job_data["item_candidates"]
        rel_cands = job_data["relation_candidates"]
        assert len(item_cands) >= 2
        assert len(rel_cands) >= 1

        # Verify Trial is now active and no longer eligible for a second trial
        r_est2 = client.post(
            "/api/v1/materials/estimate",
            headers=headers,
            json={"material_id": mat_id},
        )
        assert r_est2.status_code == 200
        assert r_est2.json()["plan_code"] == "trial"
        assert r_est2.json()["trial_eligible"] is False
        assert r_est2.json()["quota"]["used"] == mat["token_count"]

        # 5. D18: Edit first candidate before accepting
        first_cand_id = item_cands[0]["id"]
        r = client.patch(
            f"/api/v1/materials/candidates/{first_cand_id}",
            headers=headers,
            json={
                "prompt": "Что такое активное припоминание (M1) и почему оно работает?",
                "item_type": "concept",
            },
        )
        assert r.status_code == 200
        assert "активное припоминание" in r.json()["candidate"]["prompt"]

        # 6. D18 -> D18-Accepted: Accept item candidates and relation candidates separately
        r = client.post(
            f"/api/v1/materials/import-jobs/{job_data['job']['id']}/accept",
            headers=headers,
            json={
                "item_candidate_ids": [c["id"] for c in item_cands],
                "relation_candidate_ids": [rc["id"] for rc in rel_cands],
            },
        )
        assert r.status_code == 200
        acc = r.json()
        assert acc["ok"] is True
        assert acc["accepted_items_count"] == len(item_cands)
        assert acc["accepted_relations_count"] == len(rel_cands)

        # Verify created items have anchored D34 source fragments
        first_item_id = acc["accepted_item_ids"][0]
        r_item = client.get(f"/api/v1/items/{first_item_id}", headers=headers)
        assert r_item.status_code == 200
        assert r_item.json()["item"]["source_fragment"] is not None

        # 7. D15: Upload DOCX file and verify parsing
        docx_bytes = _make_sample_docx_bytes(
            [
                "Глава 2. Эффект генерации и связывание знаний.",
                "Смысловая группировка позволяет удерживать до 4–7 связанных элементов в рабочей памяти.",
            ]
        )
        r_up = client.post(
            "/api/v1/materials/upload",
            headers=headers,
            files={"file": ("chapter2.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"title": "Глава 2 DOCX", "goal": "exam", "language": "ru"},
        )
        assert r_up.status_code == 201
        assert r_up.json()["material"]["format"] == "docx"
        assert r_up.json()["material"]["fragments_count"] >= 1

        # 8. Scan PDF detection (PDF without text layer -> 422 PDF_SCAN_WITHOUT_TEXT)
        r_scan = client.post(
            "/api/v1/materials/upload",
            headers=headers,
            files={"file": ("scan.pdf", b"%PDF-1.4\n%fake-binary-scan-only\n%%EOF", "application/pdf")},
            data={"title": "Скан без текста", "goal": "exam", "language": "ru"},
        )
        assert r_scan.status_code == 422
        assert r_scan.json()["detail"]["code"] == "PDF_SCAN_WITHOUT_TEXT"

        # 9. D30: Quota status endpoint
        r_q = client.get("/api/v1/quota/status?resource=import_tokens&required_amount=50000", headers=headers)
        assert r_q.status_code == 200
        assert r_q.json()["screen"] == "D30"
        assert r_q.json()["manual_mode_available"] is True
