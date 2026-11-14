from __future__ import annotations

from typing import Any

from brainrecall.i18n import normalize_locale

SCIENCE_CATALOG: dict[str, dict[str, Any]] = {
    "M1": {
        "method_id": "M1",
        "code": "retrieval_practice",
        "content_version": "2026-04-14.1",
        "updated_at": "2026-04-14",
        "evidence_level": "direct",
        "metrics_highlight": {
            "delayed_recall_test_pct": "80%",
            "delayed_recall_reread_pct": "33–36%",
            "delay": "1 week",
            "scope_caveat": {
                "ru": "Данные получены на связных научно-популярных текстах при проверке через 1 неделю (Roediger & Karpicke, 2006).",
                "en": "Measured on prose science passages tested after a 1-week delay (Roediger & Karpicke, 2006).",
            },
        },
        "ru": {
            "short_title": "Вспомнить по памяти",
            "title": "Практика припоминания (Retrieval Practice)",
            "subtitle": "Самостоятельное извлечение ответа из памяти вместо повторного перечитывания.",
            "what_you_do": (
                "Вы видите вопрос или понятие и сначала пытаетесь сформулировать ответ по памяти — "
                "коротко письменно, выбором или вслух — и только затем сверяетесь с эталоном и критериями."
            ),
            "why_it_works": (
                "Перечитывание создаёт иллюзию знакомости: пока текст перед глазами, кажется, что вы его знаете. "
                "Усилие по извлечению идеи из памяти перестраивает и укрепляет пути доступа к ней, а последующая "
                "проверка сразу показывает точные пробелы."
            ),
            "experiments": (
                "В классическом эксперименте Roediger & Karpicke (2006) студенты изучали научно-популярные тексты: "
                "одна группа перечитывала текст четыре раза (SSSS), а другая читала один раз и трижды вспоминала "
                "содержание по памяти (STTT). На тесте через 5 минут перечитывание давало небольшой перевес (81% против 75%), "
                "но через 1 неделю группа припоминания помнила около 80% ключевых идей против 33–36% у групп перечитывания."
            ),
            "limitations": (
                "Оговорка об условиях: цифры 80% и 33–36% получены именно для связных текстов на интервале 1 недели. "
                "Припоминание работает лучше всего, когда после попытки есть обратная связь (эталон или критерии), "
                "а материал сначала базово понят, а не заучивается механически без смысла."
            ),
        },
        "en": {
            "short_title": "Retrieval Practice",
            "title": "Retrieval Practice (Testing Effect)",
            "subtitle": "Actively pulling an answer from memory before looking at the source.",
            "what_you_do": (
                "You see a prompt or concept and first try to produce the answer from memory — "
                "in writing, by selection, or aloud — before checking the reference answer and criteria."
            ),
            "why_it_works": (
                "Rereading creates a fluency illusion: a passage feels familiar while you look at it. "
                "Retrieving an idea from memory strengthens retrieval routes and makes knowledge accessible "
                "when the source is no longer in front of you."
            ),
            "experiments": (
                "In Roediger & Karpicke (2006), students studied prose science passages either by rereading four times (SSSS) "
                "or reading once and practicing recall three times (STTT). While rereading led slightly after 5 minutes (81% vs. 75%), "
                "after 1 week the retrieval-practice group remembered ~80% of idea units compared to 33–36% for rereading groups."
            ),
            "limitations": (
                "Scope note: the 80% vs. 33–36% figures apply specifically to prose passages tested after 1 week. "
                "Retrieval practice is most effective when followed by corrective feedback and when initial comprehension "
                "is established rather than blind rote guessing."
            ),
        },
        "sources": [
            {
                "citation": "Roediger, H. L., & Karpicke, J. D. (2006). Test-enhanced learning: Taking memory tests improves long-term retention. Psychological Science, 17(3), 249–255.",
                "doi": "10.1111/j.1467-9280.2006.01693.x",
                "url": "https://doi.org/10.1111/j.1467-9280.2006.01693.x",
            },
            {
                "citation": "Rowland, C. A. (2014). The effect of testing versus restudy on retention: A meta-analytic review of the testing effect. Psychological Bulletin, 140(6), 1432–1463.",
                "doi": "10.1037/a0037559",
                "url": "https://doi.org/10.1037/a0037559",
            },
            {
                "citation": "Adesope, O. O., Trevisan, D. A., & Sundararajan, N. (2017). Rethinking the use of tests: A meta-analysis of practice testing. Review of Educational Research, 87(3), 659–701.",
                "doi": "10.3102/0034654316689306",
                "url": "https://doi.org/10.3102/0034654316689306",
            },
        ],
    },
    "M2": {
        "method_id": "M2",
        "code": "spaced_practice",
        "content_version": "2026-04-14.1",
        "updated_at": "2026-04-14",
        "evidence_level": "direct",
        "metrics_highlight": None,
        "ru": {
            "short_title": "Повторение с интервалами",
            "title": "Распределённая практика (Spaced Practice)",
            "subtitle": "Возврат к карточке через растущие интервалы дней (1 → 3 → 7 → 14 → 30 → 60 → 120).",
            "what_you_do": (
                "Вместо многократного повторения одной карточки в один вечер приложение возвращает вас к ней "
                "в новые календарные дни по мере того, как вы успешно справляетесь без подсказок."
            ),
            "why_it_works": (
                "Когда между попытками проходит время и след памяти немного ослабевает, повторное извлечение требует "
                "большего когнитивного усилия. Это консолидирует память и замедляет дальнейшее забывание."
            ),
            "experiments": (
                "Мета-анализ Cepeda et al. (2006) по 254 исследованиям (более 14 000 участников) показал устойчивое "
                "преимущество распределённой практики над массированной («зубрёжкой в один присест») на всех временных горизонтах. "
                "Оптимальный интервал между повторениями растёт пропорционально тому, как долго вы хотите помнить материал."
            ),
            "limitations": (
                "Повторение в тот же день полезно для первичного закрепления после ошибки, но не заменяет перенос на следующий день. "
                "Именно поэтому в BrainRecall шаг интервала продвигается только при самостоятельном успехе в новый календарный день."
            ),
        },
        "en": {
            "short_title": "Spaced Practice",
            "title": "Spaced Practice (Distributed Practice)",
            "subtitle": "Revisiting knowledge across expanding day intervals (1 → 3 → 7 → 14 → 30 → 60 → 120).",
            "what_you_do": (
                "Instead of cramming the same card repeatedly in a single evening, the scheduler brings it back "
                "on new calendar days as you succeed independently without hints."
            ),
            "why_it_works": (
                "Allowing some forgetting to occur between sessions makes subsequent retrieval more effortful, "
                "triggering reconsolidation and flattening the forgetting curve over weeks and months."
            ),
            "experiments": (
                "Cepeda et al. (2006) synthesized 254 studies (>14,000 participants) and confirmed a robust spacing effect "
                "across verbal, conceptual, and motor tasks compared to massed practice. Optimal lag between reviews increases "
                "as the desired retention interval grows."
            ),
            "limitations": (
                "Same-day repetition helps repair immediate errors, but cannot substitute for overnight consolidation. "
                "Therefore, BrainRecall advances your interval step only on an independent success on a new local day."
            ),
        },
        "sources": [
            {
                "citation": "Cepeda, N. J., Pashler, H., Vul, E., Wixted, J. T., & Rohrer, D. (2006). Distributed practice in verbal recall tasks: A review and quantitative synthesis. Psychological Bulletin, 132(3), 354–380.",
                "doi": "10.1037/0033-2909.132.3.354",
                "url": "https://doi.org/10.1037/0033-2909.132.3.354",
            },
            {
                "citation": "Dunlosky, J., Rawson, K. A., Marsh, E. J., Nathan, M. J., & Willingham, D. T. (2013). Improving students’ learning with effective learning techniques. Psychological Science in the Public Interest, 14(1), 4–58.",
                "doi": "10.1177/1529100612453266",
                "url": "https://doi.org/10.1177/1529100612453266",
            },
        ],
    },
    "M3": {
        "method_id": "M3",
        "code": "interleaved_practice",
        "content_version": "2026-04-14.1",
        "updated_at": "2026-04-14",
        "evidence_level": "direct",
        "metrics_highlight": None,
        "ru": {
            "short_title": "Чередование и выбор способа",
            "title": "Чередование и различение (Interleaved Practice)",
            "subtitle": "Смешивание близких понятий и выбор подходящего принципа до расчёта.",
            "what_you_do": (
                "В сессии чередуются разные типы задач и близкие понятия, а в упражнениях «Выбрать способ» "
                "вы сначала определяете, какой принцип или метод применим к ситуации, и только затем видите формулу или шаги."
            ),
            "why_it_works": (
                "При блочной практике (10 однотипных задач подряд) мозг перестаёт анализировать условие и просто "
                "подставляет шаблон. Чередование заставляет каждый раз распознавать диагностические признаки задачи и отличать похожие идеи."
            ),
            "experiments": (
                "В исследованиях Rohrer & Taylor (2007) и Kornell & Bjork (2008) чередование типов задач и категорий "
                "снижало кажущуюся лёгкость во время самой тренировки, но значительно повышало точность выбора правильного метода "
                "на отсроченном итоговом тесте (Мета-анализ Brunmair & Richter, 2019: средний эффект g ≈ 0.42 для математических и визуальных категорий)."
            ),
            "limitations": (
                "Чередование полезно для близких, легко путаемых понятий и после того, как вы уже познакомились с каждым из них по отдельности. "
                "Случайное смешивание совершенно несвязанных тем без первичного понимания не даёт выигрыша — поэтому в BrainRecall "
                "чередование включается только после первичного знакомства с карточкой."
            ),
        },
        "en": {
            "short_title": "Interleaved Practice",
            "title": "Interleaved Practice & Discrimination",
            "subtitle": "Mixing related concepts and selecting the right method before seeing the formula.",
            "what_you_do": (
                "Study sessions interleave contrasting concepts and objective types. In 'Choose the Method' exercises, "
                "you first identify which principle applies to a scenario before any formula or procedure is revealed."
            ),
            "why_it_works": (
                "When practicing 10 identical problems in a block, youalready know which formula to apply without reading carefully. "
                "Interleaving trains discriminative contrast — recognizing the diagnostic features that distinguish similar concepts."
            ),
            "experiments": (
                "Studies by Rohrer & Taylor (2007) and Kornell & Bjork (2008) demonstrated that interleaving slows initial practice "
                "performance yet substantially boosts delayed test accuracy in selecting and applying the right strategy "
                "(Brunmair & Richter, 2019 meta-analysis: g ≈ 0.42 for inductive category and problem-type learning)."
            ),
            "limitations": (
                "Interleaving works best for related, confusable categories after basic familiarity is achieved. "
                "Randomly shuffling unrelated topics before initial encoding is unhelpful — so BrainRecall gates interleaving "
                "until after a card's introductory pass."
            ),
        },
        "sources": [
            {
                "citation": "Rohrer, D., & Taylor, K. (2007). The shuffling of mathematics problems improves learning. Instructional Science, 35(6), 481–498.",
                "doi": "10.1007/s11251-007-9015-8",
                "url": "https://doi.org/10.1007/s11251-007-9015-8",
            },
            {
                "citation": "Kornell, N., & Bjork, R. A. (2008). Learning concepts and categories: Is spacing the “enemy of induction”? Psychological Science, 19(6), 585–592.",
                "doi": "10.1111/j.1467-9280.2008.02127.x",
                "url": "https://doi.org/10.1177/1467-9280.2008.02127.x",
            },
            {
                "citation": "Brunmair, M., & Richter, T. (2019). Similarity matters: A meta-analysis of interleaved learning and its moderators. Psychological Bulletin, 145(11), 1029–1052.",
                "doi": "10.1037/bul0000209",
                "url": "https://doi.org/10.1037/bul0000209",
            },
        ],
    },
    "M4": {
        "method_id": "M4",
        "code": "self_explanation",
        "content_version": "2026-04-14.1",
        "updated_at": "2026-04-14",
        "evidence_level": "direct",
        "metrics_highlight": None,
        "ru": {
            "short_title": "Объяснение своими словами",
            "title": "Самообъяснение и уточняющий вопрос (Self-Explanation & Elaborative Interrogation)",
            "subtitle": "Объяснение механизма «почему и как это работает» с проверкой по 2–4 критериям.",
            "what_you_do": (
                "Вы даёте короткое объяснение идеи своими словами (письменно или вслух), проверяете его по "
                "2–4 смысловым критериям, при пробеле сверяетесь с фрагментом источника (D34) и сразу делаете повторную попытку."
            ),
            "why_it_works": (
                "Попытка объяснить причинно-следственный механизм вскрывает «иллюзию глубины понимания» (Rozenblit & Keil, 2002): "
                "мы часто думаем, что понимаем систему, пока не попробуем описать, как именно связаны её шаги."
            ),
            "experiments": (
                "Chi et al. (1994) показали, что ученики, которых просили объяснять себе смысл каждого абзаца при изучении работы "
                "кровеносной системы, строили гораздо более точную ментальную модель и лучше решали сложные задачи на перенос. "
                "Мета-анализ Bisra et al. (2018) по 64 исследованиям подтвердил значимый положительный эффект самообъяснения (g ≈ 0.55)."
            ),
            "limitations": (
                "Свободное объяснение без проверки может закрепить неверную догадку. Поэтому в BrainRecall каждое объяснение "
                "сверяется с конкретными критериями и фрагментом первоисточника, а при пропуске критерия предлагается исправляющий повтор."
            ),
        },
        "en": {
            "short_title": "Self-Explanation",
            "title": "Self-Explanation & Elaborative Interrogation",
            "subtitle": "Explaining 'why and how it works' in your own words against 2–4 rubric criteria.",
            "what_you_do": (
                "You explain a concept in your own words (written or aloud), evaluate your answer against "
                "2–4 core criteria, inspect the source excerpt (D34) if a gap appears, and complete an immediate corrective retry."
            ),
            "why_it_works": (
                "Explaining causal mechanisms punctures the 'illusion of explanatory depth' (Rozenblit & Keil, 2002): "
                "people routinely overestimate how well they understand a mechanism until asked to trace its causal steps."
            ),
            "experiments": (
                "Chi et al. (1994) found that learners prompted to self-explain while reading biology texts formed markedly "
                "more accurate mental models and excelled on deep transfer questions. Bisra et al. (2018) meta-analyzed 64 studies "
                "and found a reliable positive effect of self-explanation prompts (g ≈ 0.55)."
            ),
            "limitations": (
                "Unchecked explanation can reinforce misconceptions. BrainRecall pairs every explanation prompt with "
                "2–4 explicit rubric criteria and direct access to the source passage, prompting a corrective retry when a criterion is missed."
            ),
        },
        "sources": [
            {
                "citation": "Chi, M. T. H., De Leeuw, N., Chiu, M.-H., & LaVancher, C. (1994). Eliciting self-explanations improves understanding. Cognitive Science, 18(3), 439–477.",
                "doi": "10.1207/s15516709cog1803_3",
                "url": "https://doi.org/10.1207/s15516709cog1803_3",
            },
            {
                "citation": "Rozenblit, L., & Keil, F. (2002). The misunderstood limits of folk science: An illusion of explanatory depth. Cognitive Science, 26(5), 521–562.",
                "doi": "10.1207/s15516709cog2605_1",
                "url": "https://doi.org/10.1207/s15516709cog2605_1",
            },
            {
                "citation": "Bisra, K., Liu, Q., Nesbit, J. C., Salimi, F., & Winne, P. H. (2018). Inducing self-explanation: A meta-analysis. Educational Psychology Review, 30(3), 703–725.",
                "doi": "10.1007/s10648-018-9434-x",
                "url": "https://doi.org/10.1007/s10648-018-9434-x",
            },
        ],
    },
    "M5": {
        "method_id": "M5",
        "code": "concept_relations",
        "content_version": "2026-04-14.1",
        "updated_at": "2026-04-14",
        "evidence_level": "indirect",
        "metrics_highlight": None,
        "ru": {
            "short_title": "Смысловые группы и связи",
            "title": "Смысловые группы (2–7 элементов) и явные связи между идеями",
            "subtitle": "Косвенное основание: опора на исследования чанкинга рабочей памяти и концепт-карт.",
            "what_you_do": (
                "Вы объединяете от 2 до 7 карточек одной темы в компактную смысловую группу (D40/D41), задаёте типизированные "
                "связи («основание для», «следствие», «контрастирует с» и др.) и в упражнении «Связать идеи» восстанавливаете "
                "тип связи и объясняете её смысл."
            ),
            "why_it_works": (
                "Рабочая память человека одновременно удерживает лишь около 4±1 независимых смысловых единиц (Cowan, 2001). "
                "Когда разрозненные факты связаны явными отношениями в компактный кластер, они начинают работать как единый "
                "смысловой узел (chunk) и легче извлекаются вместе."
            ),
            "experiments": (
                "Важная честная оговорка (косвенное основание): в отличие от M1–M4, конкретный интерфейс «групп из 2–7 карточек в мобильном "
                "приложении» не тестировался в отдельном РКИ. Это инженерное решение опирается на две косвенные линии доказательств: "
                "1) ограничения ёмкости рабочей памяти (Miller, 1956; Cowan, 2001) и 2) мета-анализы построения концепт-карт с подписанными "
                "связями (Nesbit & Adesope, 2006; Schroeder et al., 2018, g ≈ 0.58)."
            ),
            "limitations": (
                "Гигантские схемы из десятков узлов перегружают экран и превращаются в пассивную картинку. Поэтому в BrainRecall "
                "группа жёстко ограничена 2–7 карточками одной темы, а проверка связи всегда требует активного припоминания по памяти."
            ),
        },
        "en": {
            "short_title": "Concept Groups & Relations",
            "title": "Meaning Groups (2–7 items) & Explicit Concept Relations",
            "subtitle": "Indirect evidence: grounded in working-memory chunking limits and concept-mapping research.",
            "what_you_do": (
                "You group 2 to 7 knowledge items within a topic into a Meaning Group (D40/D41), define typed directed relations "
                "('basis for', 'consequence of', 'contrasts with', etc.), and practice recalling both the relation type and its rationale."
            ),
            "why_it_works": (
                "Human working memory holds roughly 4±1 independent chunks at once (Cowan, 2001). Organizing isolated facts "
                "into small, explicitly linked clusters helps compress them into coherent schemas that cue one another during recall."
            ),
            "experiments": (
                "Transparency note (indirect evidence): Unlike M1–M4, the specific UI constraint of '2–7 items per group in a mobile app' "
                "is an engineering design informed by two indirect bodies of literature: 1) working-memory capacity limits "
                "(Miller, 1956; Cowan, 2001) and 2) meta-analyses on node-link concept mapping with labeled propositions "
                "(Nesbit & Adesope, 2006; Schroeder et al., 2018, g ≈ 0.58)."
            ),
            "limitations": (
                "Sprawling diagrams with dozens of nodes cause visual overload and passive browsing. BrainRecall caps each group "
                "at 2–7 items in the same topic and turns every relation into an active retrieval prompt."
            ),
        },
        "sources": [
            {
                "citation": "Cowan, N. (2001). The magical number 4 in short-term memory: A reconsideration of mental storage capacity. Behavioral and Brain Sciences, 24(1), 87–114.",
                "doi": "10.1017/S0140525X01003922",
                "url": "https://doi.org/10.1017/S0140525X01003922",
            },
            {
                "citation": "Nesbit, J. C., & Adesope, O. O. (2006). Learning with concept and knowledge maps: A meta-analysis. Review of Educational Research, 76(3), 413–448.",
                "doi": "10.3102/00346543076003413",
                "url": "https://doi.org/10.3102/00346543076003413",
            },
            {
                "citation": "Schroeder, N. L., Nesbit, J. C., Anguiano, C. J., & Adesope, O. O. (2018). Studying and constructing concept maps: A meta-analysis. Educational Psychology Review, 30(2), 431–455.",
                "doi": "10.1007/s10648-017-9403-9",
                "url": "https://doi.org/10.1007/s10648-017-9403-9",
            },
        ],
    },
}

OBJECTIVE_TO_METHOD: dict[str, str] = {
    "recall": "M1",
    "spacing": "M2",
    "discriminate": "M3",
    "explain": "M4",
    "relate": "M5",
    "apply": "M3",
}


def get_science_catalog_for_locale(locale: str) -> list[dict[str, Any]]:
    loc = normalize_locale(locale)
    result: list[dict[str, Any]] = []
    for method_id in ("M1", "M2", "M3", "M4", "M5"):
        entry = SCIENCE_CATALOG[method_id]
        localized = entry[loc]
        metrics = None
        if entry.get("metrics_highlight"):
            mh = entry["metrics_highlight"]
            metrics = {
                "delayed_recall_test_pct": mh["delayed_recall_test_pct"],
                "delayed_recall_reread_pct": mh["delayed_recall_reread_pct"],
                "delay": mh["delay"],
                "scope_caveat": mh["scope_caveat"][loc],
            }
        result.append(
            {
                "method_id": method_id,
                "code": entry["code"],
                "content_version": entry["content_version"],
                "updated_at": entry["updated_at"],
                "evidence_level": entry["evidence_level"],
                "metrics_highlight": metrics,
                **localized,
                "sources": entry["sources"],
            }
        )
    return result
