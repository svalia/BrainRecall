# 🧠 BrainRecall (`@BrainRecallBot`)

**Долговременное запоминание знаний (5 доказательных методик M1–M5) и атомарные привычки в Telegram Mini App.**  
**Long-term knowledge retention (5 evidence-based methods M1–M5) and atomic habits inside Telegram Mini App.**

---

## 🇷🇺 О проекте (RU)

**BrainRecall** — связка Telegram-бота [`@BrainRecallBot`](https://t.me/BrainRecallBot) и веб-приложения Telegram Mini App (`https://owncome.ru/brainrecall/`), которая помогает:
1. **Запоминать знания на месяцы, а не до завтра** с помощью пяти когнитивных методик:
   - **M1 · Припоминание из памяти (Retrieval Practice)** — ответ формулируется самостоятельно до показа эталона (Roediger & Karpicke, 2006; метаанализ Rowland, 2014).
   - **M2 · Интервальное повторение (Spaced Practice)** — расширяющиеся интервалы `1 → 3 → 7 → 14 → 30 → 60 → 120` дней отдельно по каждой учебной цели (Cepeda et al., 2006).
   - **M3 · Чередование и различение (Interleaved Practice)** — смешивание похожих концепций и задач выбора метода без преждевременного показа формулы (Rohrer & Taylor, 2007).
   - **M4 · Объяснение своими словами (Self-Explanation)** — проверка по смысловым критериям (рубрике), выявление пробела и повтор с помощью (Chi et al., 1994; Bisra et al., 2018).
   - **M5 · Связывание и смысловая группировка (Chunking & Elaboration)** — объединение `2–7` карточек в смысловые группы (`D40`/`D41`) с направленными связями и косвенным научным основанием (Cowan, 2001).
2. **Укреплять ежедневные привычки** по 4 законам изменения поведения («Атомные привычки»): очевидный сигнал, полное действие, программа-минимум на 2 минуты (`minimum_done` сохраняет серию в трудный день) и резервный план «если — то».
3. **Разбирать конспекты и книги с ИИ (DeepSeek)** (`TXT`, `MD`, текстовый `PDF`, `DOCX`, `EPUB` до 20 МБ и 100 000 токенов) с привязкой каждой карточки к точному абзацу и цитате источника (`D34`).

### Тарифы (Telegram Stars ⭐)
- **Free (0 ⭐)** — навсегда бесплатно: до 3 активных тем, 3 активных привычек, 500 карточек вручную, все 5 методик M1–M5, серии и экспорт.
- **Trial (0 ⭐, 7 дней)** — активируется один раз при первом подтверждённом ИИ-действии (`D16`), без автосписаний: 30 000 токенов ИИ-разбора, 20 ИИ-проверок ответов.
- **Start (499 ⭐ / 30 дней)** — 10 тем, 10 привычек, 200 000 токенов ИИ-разбора, 200 ИИ-проверок.
- **Pro (1 099 ⭐ / 30 дней)** — 50 тем, 30 привычек, 600 000 токенов ИИ-разбора, 1 000 ИИ-проверок.

---

## 🇬🇧 Overview (EN)

**BrainRecall** is a bilingual (`RU` / `EN`) Telegram Bot (`@BrainRecallBot`) and Telegram Mini App (`https://owncome.ru/brainrecall/`) designed for durable knowledge retention and resilient daily habits:
- **5 Evidence-Based Learning Methods (`M1–M5`)** with an interactive Science Sheet (`D42`) citing peer-reviewed primary sources and DOIs.
- **Atomic Habits Builder (`D19–D23`)** with a 2-minute minimum version that protects your streak on busy days, plus Streak Freeze protection (`D36–D39`).
- **DeepSeek AI Material Extraction (`D14–D18`)** with signed token estimates, transactional `QuotaLedger`, and anchored source quotes (`D34`).
- **Full Data Portability & Privacy (`D32`)**: one-click JSON + Markdown export and complete account/data deletion.
- **MCP Assistant Endpoint (`/api/v1/mcp`)**: JSON-RPC 2.0 Model Context Protocol endpoint for AI assistants.

---

## 🏗 Архитектура и запуск / Architecture & Setup

```bash
# 1. Установка зависимостей / Install dependencies
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# 2. Запуск тестов / Run verification suite
.venv/bin/pytest -v

# 3. Локальный запуск / Run locally
.venv/bin/uvicorn brainrecall.main:app --reload --port 8096

# 4. Деплой на прод-сервер Selectel / Deploy to Selectel production
./deploy/deploy.sh
```
