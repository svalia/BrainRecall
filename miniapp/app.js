/* BrainRecall Mini App — Core Shell, i18n, Gestures-Back, BottomSheet & Screens D00, D01, D02, D03, D42
   NOTE: Never shadow the function identifier `t` in any scope (Dev Spec Section 3.16). */

(function () {
  "use strict";

  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

  const state = {
    authenticated: false,
    insideTelegram: false,
    sessionToken: localStorage.getItem("br_session_token") || null,
    locale: localStorage.getItem("br_locale") || "ru",
    catalog: {},
    user: null,
    counts: { topics: 0, habits: 0, items: 0 },
    methodIntros: [],
    currentScreen: "D00",
    historyStack: [],
    sheetOpen: false,
    sheetOnClose: null,
    activeMethodTab: "M1",
    demoStep: 1,
    demoAnswer: "",
    demoChecked: false,
    onboardingDraft: {
      goal_focus: "both",
      daily_study_minutes: 10,
      reminder_window: "evening",
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Moscow",
    },
  };

  function t(key, params) {
    const parts = String(key).split(".");
    let cur = state.catalog;
    for (let idx = 0; idx < parts.length; idx += 1) {
      if (cur && typeof cur === "object" && parts[idx] in cur) {
        cur = cur[parts[idx]];
      } else {
        cur = null;
        break;
      }
    }
    let str = typeof cur === "string" ? cur : key;
    if (params && typeof params === "object") {
      Object.keys(params).forEach(function (k) {
        str = str.replace(new RegExp("\\{" + k + "\\}", "g"), String(params[k]));
      });
    }
    return str;
  }

  // Expose `t` globally for debugging and parity checks
  window.t = t;
  window.brState = state;

  function triggerHaptic(kind, level) {
    if (state.user && state.user.haptics_enabled === false) return;
    if (!tg || !tg.HapticFeedback) return;
    try {
      if (kind === "impact") {
        tg.HapticFeedback.impactOccurred(level || "light");
      } else if (kind === "notification") {
        tg.HapticFeedback.notificationOccurred(level || "success");
      } else if (kind === "selection") {
        tg.HapticFeedback.selectionChanged();
      }
    } catch (_e) {
      // Ignore on unsupported clients
    }
  }

  function applyTelegramThemeAndSafeAreas() {
    const shell = document.getElementById("app-shell");
    if (!shell) return;

    if (tg) {
      try {
        tg.ready();
        tg.expand();
      } catch (_e) {}

      if (tg.colorScheme === "dark") {
        shell.classList.add("dk");
      } else {
        shell.classList.remove("dk");
      }

      const safeTop = (tg.safeAreaInset && tg.safeAreaInset.top) || 0;
      const safeBottom = (tg.safeAreaInset && tg.safeAreaInset.bottom) || 10;
      const contentTop = (tg.contentSafeAreaInset && tg.contentSafeAreaInset.top) || 0;

      document.documentElement.style.setProperty("--tg-safe-top", safeTop + "px");
      document.documentElement.style.setProperty("--tg-safe-bottom", safeBottom + "px");
      document.documentElement.style.setProperty("--tg-content-safe-top", contentTop + "px");
    }
  }

  async function apiFetch(path, options) {
    const opts = Object.assign({ method: "GET", headers: {} }, options || {});
    opts.headers["Accept-Language"] = state.locale;
    if (state.sessionToken) {
      opts.headers["Authorization"] = "Bearer " + state.sessionToken;
    }
    if (tg && tg.initData) {
      opts.headers["X-Telegram-Init-Data"] = tg.initData;
    }
    if (opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }
    const resp = await fetch(path, opts);
    if (!resp.ok) {
      let errPayload = {};
      try {
        errPayload = await resp.json();
      } catch (_e) {}
      const err = new Error(errPayload.detail || "API Error " + resp.status);
      err.status = resp.status;
      err.payload = errPayload;
      throw err;
    }
    return resp.json();
  }

  function syncBackButton() {
    if (!tg || !tg.BackButton) return;
    const canGoBack = state.sheetOpen || state.historyStack.length > 0;
    try {
      if (canGoBack) {
        tg.BackButton.show();
      } else {
        tg.BackButton.hide();
      }
    } catch (_e) {}
  }

  function handleHierarchicalBack() {
    if (state.sheetOpen) {
      closeBottomSheet();
      return true;
    }
    if (state.historyStack.length > 0) {
      const prevScreen = state.historyStack.pop();
      navigateTo(prevScreen, { pushHistory: false });
      return true;
    }
    return false;
  }

  function navigateTo(screenId, opts) {
    const options = Object.assign({ pushHistory: true }, opts || {});
    if (options.pushHistory && state.currentScreen && state.currentScreen !== screenId && state.currentScreen !== "D00") {
      state.historyStack.push(state.currentScreen);
    }
    state.currentScreen = screenId;

    // Ephemeral forms reset on navigation unless explicitly preserved (Section 3.14)
    if (screenId === "D02") {
      state.onboardingDraft = {
        goal_focus: (state.user && state.user.goal_focus) || "both",
        daily_study_minutes: (state.user && state.user.daily_study_minutes) || 10,
        reminder_window: (state.user && state.user.reminder_window) || "evening",
        timezone: (state.user && state.user.timezone) || Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Moscow",
      };
    }

    renderCurrentScreen();
    syncBackButton();
  }

  async function switchLocale(targetLocale) {
    triggerHaptic("selection");
    state.locale = targetLocale;
    localStorage.setItem("br_locale", targetLocale);

    try {
      if (state.authenticated) {
        const res = await apiFetch("api/v1/settings", {
          method: "PATCH",
          body: { locale_override: targetLocale },
        });
        state.catalog = res.catalog || state.catalog;
        state.user = res.user || state.user;
        state.methodIntros = res.method_intros || state.methodIntros;
      } else {
        const res = await apiFetch("api/v1/auth/bootstrap", {
          method: "POST",
          body: { locale_hint: targetLocale },
        });
        state.catalog = res.catalog || state.catalog;
        state.methodIntros = res.method_intros || state.methodIntros;
      }
    } catch (_e) {}

    renderCurrentScreen();
    if (state.sheetOpen && state.currentSheetType === "D42") {
      openScienceSheet(state.activeMethodTab);
    }
  }

  function renderTopBar(titleText, showBack) {
    const ruActive = state.locale === "ru" ? "c-pr" : "";
    const enActive = state.locale === "en" ? "c-pr" : "";
    return (
      '<header class="hdr">' +
      '<div class="row" style="gap:8px;">' +
      (showBack
        ? '<button type="button" class="btn b2 bsm" id="top-back-btn" style="min-height:38px; padding:6px 14px;">‹ ' +
          escapeHtml(t("miniapp.common.back")) +
          "</button>"
        : '<span class="h2">' + escapeHtml(titleText || "BrainRecall") + "</span>") +
      "</div>" +
      '<div class="row" style="gap:6px;">' +
      '<button type="button" class="chip ' +
      ruActive +
      '" data-set-lang="ru" style="cursor:pointer;">RU</button>' +
      '<button type="button" class="chip ' +
      enActive +
      '" data-set-lang="en" style="cursor:pointer;">EN</button>' +
      "</div>" +
      "</header>"
    );
  }

  function bindLanguageButtons(container) {
    const btns = (container || document).querySelectorAll("[data-set-lang]");
    btns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        const lang = btn.getAttribute("data-set-lang");
        if (lang && lang !== state.locale) {
          switchLocale(lang);
        }
      });
    });
    const backBtn = document.getElementById("top-back-btn");
    if (backBtn) {
      backBtn.addEventListener("click", function () {
        handleHierarchicalBack();
      });
    }
  }

  function updateBottomNavVisibility() {
    const nav = document.getElementById("bottom-nav");
    if (!nav) return;
    const primaryScreens = ["D03", "D04", "D19", "D24"];
    if (primaryScreens.indexOf(state.currentScreen) !== -1) {
      nav.style.display = "flex";
      const tabs = nav.querySelectorAll(".tab");
      tabs.forEach(function (tabEl) {
        const target = tabEl.getAttribute("data-nav");
        if (target === state.currentScreen) {
          tabEl.classList.add("on");
        } else {
          tabEl.classList.remove("on");
        }
      });
    } else {
      nav.style.display = "none";
    }

    // Update bottom nav labels
    nav.querySelectorAll("[data-i18n]").forEach(function (el) {
      el.textContent = t(el.getAttribute("data-i18n"));
    });
  }

  function renderCurrentScreen() {
    const vp = document.getElementById("screen-viewport");
    if (!vp) return;
    updateBottomNavVisibility();

    if (state.currentScreen === "D00") {
      renderD00(vp);
    } else if (state.currentScreen === "D01") {
      renderD01(vp);
    } else if (state.currentScreen === "D02") {
      renderD02(vp);
    } else if (state.currentScreen === "D03") {
      renderD03(vp);
    } else {
      renderD03(vp);
    }
  }

  // ==================== D00: Bootstrap / Outside Telegram ====================
  function renderD00(vp) {
    vp.innerHTML =
      renderTopBar("BrainRecall", false) +
      '<div class="card col" style="margin-top:24px; text-align:center; padding:28px 20px;">' +
      '<div class="h2">' +
      escapeHtml(t("miniapp.d00.loading_title")) +
      "</div>" +
      '<p class="mu">' +
      escapeHtml(t("miniapp.d00.loading_sub")) +
      "</p>" +
      '<div class="sk" style="width:100%; height:14px; margin-top:12px;"></div>' +
      '<div class="sk" style="width:72%; height:14px; align-self:center;"></div>' +
      "</div>";
    bindLanguageButtons(vp);
  }

  // ==================== D01: Product Landing, Interactive Demo, 5 Methods, Pricing & FAQ ====================
  function renderD01(vp) {
    const methodsHtml = (state.methodIntros || [])
      .map(function (m) {
        const badgeHtml =
          m.evidence_level === "indirect"
            ? '<span class="chip c-wn">' + escapeHtml(t("miniapp.common.indirect_badge")) + "</span>"
            : m.metrics_highlight
            ? '<span class="chip c-ok">' +
              escapeHtml(m.metrics_highlight.delayed_recall_test_pct + " vs " + m.metrics_highlight.delayed_recall_reread_pct) +
              "</span>"
            : '<span class="chip">DOI</span>';
        return (
          '<button type="button" class="li" data-open-science="' +
          escapeHtml(m.method_id) +
          '" style="width:100%; background:none; border:0; border-top:1px solid var(--ln); text-align:left; cursor:pointer; font-family:inherit;">' +
          '<span class="pill">' +
          escapeHtml(m.method_id) +
          "</span>" +
          '<div class="col grow" style="gap:2px;">' +
          '<div class="b">' +
          escapeHtml(m.short_title) +
          "</div>" +
          '<div class="sm mu">' +
          escapeHtml(m.subtitle) +
          "</div>" +
          "</div>" +
          badgeHtml +
          "</button>"
        );
      })
      .join("");

    vp.innerHTML =
      renderTopBar("BrainRecall", state.historyStack.length > 0) +
      /* Hero Card */
      '<section class="card cardp col" style="gap:14px;">' +
      '<div class="rw">' +
      '<span class="chip c-em">' +
      escapeHtml(t("miniapp.d01.hero_badge")) +
      "</span>" +
      '<span class="chip">' +
      escapeHtml(t("miniapp.common.free_forever")) +
      "</span>" +
      "</div>" +
      '<h1 class="h1">' +
      escapeHtml(t("miniapp.d01.hero_title")) +
      "</h1>" +
      '<p class="mu">' +
      escapeHtml(t("miniapp.d01.hero_subtitle")) +
      "</p>" +
      '<div class="col" style="gap:8px; margin-top:4px;">' +
      '<button type="button" class="btn" id="d01-start-btn">' +
      escapeHtml(t("miniapp.d01.cta_start_free")) +
      "</button>" +
      '<button type="button" class="btn b2" id="d01-scroll-demo-btn">' +
      escapeHtml(t("miniapp.d01.cta_try_demo")) +
      "</button>" +
      "</div>" +
      "</section>" +
      /* Problem section */
      '<section class="card col">' +
      '<h2 class="h2">' +
      escapeHtml(t("miniapp.d01.section_problem_title")) +
      "</h2>" +
      '<p class="mu">' +
      escapeHtml(t("miniapp.d01.section_problem_desc")) +
      "</p>" +
      "</section>" +
      /* Interactive 3-step Demo */
      '<section class="card col" id="d01-demo-section">' +
      '<div class="row sp">' +
      '<h2 class="h2">' +
      escapeHtml(t("miniapp.d01.section_demo_title")) +
      "</h2>" +
      '<button type="button" class="btn b3 bsm" id="d01-why-btn" style="width:auto; padding:4px 8px;">' +
      escapeHtml(t("miniapp.common.why_this_exercise")) +
      "</button>" +
      "</div>" +
      '<div class="seg">' +
      '<button type="button" class="' +
      (state.demoStep === 1 ? "on" : "") +
      '" data-demo-step="1">' +
      escapeHtml(t("miniapp.d01.demo_step_1")) +
      "</button>" +
      '<button type="button" class="' +
      (state.demoStep === 2 ? "on" : "") +
      '" data-demo-step="2">' +
      escapeHtml(t("miniapp.d01.demo_step_2")) +
      "</button>" +
      '<button type="button" class="' +
      (state.demoStep === 3 ? "on" : "") +
      '" data-demo-step="3">' +
      escapeHtml(t("miniapp.d01.demo_step_3")) +
      "</button>" +
      "</div>" +
      renderDemoStepBody() +
      "</section>" +
      /* 5 Evidence-Based Methods */
      '<section class="col" style="gap:10px;">' +
      '<div class="col" style="gap:4px; padding:0 4px;">' +
      '<h2 class="h2">' +
      escapeHtml(t("miniapp.d01.section_science_title")) +
      "</h2>" +
      '<p class="sm mu">' +
      escapeHtml(t("miniapp.d01.section_science_subtitle")) +
      "</p>" +
      "</div>" +
      '<div class="list">' +
      methodsHtml +
      "</div>" +
      "</section>" +
      /* Habits & Freeze */
      '<section class="card col">' +
      '<h2 class="h2">' +
      escapeHtml(t("miniapp.d01.section_habits_title")) +
      "</h2>" +
      '<div class="bn ok col" style="gap:4px;">' +
      '<div class="b">' +
      escapeHtml(t("miniapp.d01.habits_feature_1_title")) +
      "</div>" +
      '<div class="sm">' +
      escapeHtml(t("miniapp.d01.habits_feature_1_desc")) +
      "</div>" +
      "</div>" +
      '<div class="bn in col" style="gap:4px;">' +
      '<div class="b">' +
      escapeHtml(t("miniapp.d01.habits_feature_2_title")) +
      "</div>" +
      '<div class="sm">' +
      escapeHtml(t("miniapp.d01.habits_feature_2_desc")) +
      "</div>" +
      "</div>" +
      "</section>" +
      /* Plans & Quotas */
      '<section class="card col">' +
      '<h2 class="h2">' +
      escapeHtml(t("miniapp.d01.section_pricing_title")) +
      "</h2>" +
      '<div class="col" style="gap:10px;">' +
      '<div class="bn col" style="gap:4px;"><div class="b">' +
      escapeHtml(t("miniapp.d01.pricing_free_title")) +
      '</div><div class="sm mu">' +
      escapeHtml(t("miniapp.d01.pricing_free_desc")) +
      "</div></div>" +
      '<div class="bn ai col" style="gap:4px;"><div class="b">' +
      escapeHtml(t("miniapp.d01.pricing_trial_title")) +
      '</div><div class="sm">' +
      escapeHtml(t("miniapp.d01.pricing_trial_desc")) +
      "</div></div>" +
      '<div class="bn col" style="gap:4px;"><div class="b">' +
      escapeHtml(t("miniapp.d01.pricing_start_title")) +
      '</div><div class="sm mu">' +
      escapeHtml(t("miniapp.d01.pricing_start_desc")) +
      "</div></div>" +
      '<div class="bn col" style="gap:4px;"><div class="b">' +
      escapeHtml(t("miniapp.d01.pricing_pro_title")) +
      '</div><div class="sm mu">' +
      escapeHtml(t("miniapp.d01.pricing_pro_desc")) +
      "</div></div>" +
      "</div>" +
      "</section>" +
      /* FAQ */
      '<section class="card col">' +
      '<h2 class="h2">' +
      escapeHtml(t("miniapp.d01.section_faq_title")) +
      "</h2>" +
      '<div class="col" style="gap:12px;">' +
      '<div><div class="b">' +
      escapeHtml(t("miniapp.d01.faq_1_q")) +
      '</div><div class="sm mu" style="margin-top:4px;">' +
      escapeHtml(t("miniapp.d01.faq_1_a")) +
      "</div></div>" +
      '<div class="dv"></div>' +
      '<div><div class="b">' +
      escapeHtml(t("miniapp.d01.faq_2_q")) +
      '</div><div class="sm mu" style="margin-top:4px;">' +
      escapeHtml(t("miniapp.d01.faq_2_a")) +
      "</div></div>" +
      '<div class="dv"></div>' +
      '<div><div class="b">' +
      escapeHtml(t("miniapp.d01.faq_3_q")) +
      '</div><div class="sm mu" style="margin-top:4px;">' +
      escapeHtml(t("miniapp.d01.faq_3_a")) +
      "</div></div>" +
      "</div>" +
      "</section>";

    bindLanguageButtons(vp);

    const startBtn = document.getElementById("d01-start-btn");
    if (startBtn) {
      startBtn.addEventListener("click", async function () {
        triggerHaptic("impact", "light");
        if (!state.authenticated) {
          try {
            const res = await apiFetch("api/v1/auth/bootstrap", {
              method: "POST",
              body: { demo_mode: true, locale_hint: state.locale },
            });
            if (res.authenticated) {
              state.authenticated = true;
              state.sessionToken = res.session_token;
              localStorage.setItem("br_session_token", res.session_token);
              state.user = res.user;
              state.methodIntros = res.method_intros || state.methodIntros;
            }
          } catch (_e) {}
        }
        navigateTo("D02");
      });
    }

    const demoScrollBtn = document.getElementById("d01-scroll-demo-btn");
    if (demoScrollBtn) {
      demoScrollBtn.addEventListener("click", function () {
        const sec = document.getElementById("d01-demo-section");
        if (sec) sec.scrollIntoView({ behavior: "smooth" });
      });
    }

    const whyBtn = document.getElementById("d01-why-btn");
    if (whyBtn) {
      whyBtn.addEventListener("click", function () {
        openScienceSheet("M1");
      });
    }

    vp.querySelectorAll("[data-demo-step]").forEach(function (stepBtn) {
      stepBtn.addEventListener("click", function () {
        state.demoStep = parseInt(stepBtn.getAttribute("data-demo-step"), 10) || 1;
        renderCurrentScreen();
      });
    });

    const demoNextBtn = document.getElementById("demo-next-step-btn");
    if (demoNextBtn) {
      demoNextBtn.addEventListener("click", function () {
        triggerHaptic("selection");
        if (state.demoStep === 1) {
          state.demoStep = 2;
        } else if (state.demoStep === 2) {
          const ta = document.getElementById("demo-answer-input");
          if (ta) state.demoAnswer = ta.value;
          state.demoStep = 3;
          state.demoChecked = true;
        } else {
          state.demoStep = 1;
          state.demoAnswer = "";
          state.demoChecked = false;
        }
        renderCurrentScreen();
      });
    }

    vp.querySelectorAll("[data-open-science]").forEach(function (mBtn) {
      mBtn.addEventListener("click", function () {
        const mid = mBtn.getAttribute("data-open-science") || "M1";
        openScienceSheet(mid);
      });
    });
  }

  function renderDemoStepBody() {
    if (state.demoStep === 1) {
      return (
        '<div class="col" style="gap:10px;">' +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.d01.demo_card_concept")) +
        "</div>" +
        '<blockquote class="src">' +
        escapeHtml(t("miniapp.d01.demo_card_text")) +
        "</blockquote>" +
        '<button type="button" class="btn b2" id="demo-next-step-btn">' +
        escapeHtml(t("miniapp.d01.demo_step_2")) +
        " →</button>" +
        "</div>"
      );
    }
    if (state.demoStep === 2) {
      return (
        '<div class="col" style="gap:10px;">' +
        '<div class="b">' +
        escapeHtml(t("miniapp.d01.demo_prompt")) +
        "</div>" +
        '<textarea id="demo-answer-input" class="inp ta" placeholder="' +
        escapeHtml(t("miniapp.d01.demo_placeholder")) +
        '">' +
        escapeHtml(state.demoAnswer) +
        "</textarea>" +
        '<button type="button" class="btn" id="demo-next-step-btn">' +
        escapeHtml(t("miniapp.d01.demo_check_btn")) +
        "</button>" +
        "</div>"
      );
    }
    return (
      '<div class="col" style="gap:10px;">' +
      '<div class="bn ok col" style="gap:6px;">' +
      '<div class="b">✓ ' +
      escapeHtml(t("miniapp.d01.demo_rubric_1")) +
      "</div>" +
      '<div class="b">✓ ' +
      escapeHtml(t("miniapp.d01.demo_rubric_2")) +
      "</div>" +
      '<div class="b">✓ ' +
      escapeHtml(t("miniapp.d01.demo_rubric_3")) +
      "</div>" +
      "</div>" +
      '<button type="button" class="btn b2" id="demo-next-step-btn">' +
      escapeHtml(t("miniapp.d01.demo_reset_btn")) +
      "</button>" +
      "</div>"
    );
  }

  // ==================== D02: Rhythm & Timezone Setup ====================
  function renderD02(vp) {
    const draft = state.onboardingDraft;
    vp.innerHTML =
      renderTopBar(t("miniapp.d02.title"), true) +
      '<section class="card col" style="gap:16px;">' +
      '<h1 class="h2">' +
      escapeHtml(t("miniapp.d02.title")) +
      "</h1>" +
      '<p class="mu sm">' +
      escapeHtml(t("miniapp.d02.subtitle")) +
      "</p>" +
      /* Goal Focus */
      '<div class="col" style="gap:8px;">' +
      '<label class="lab">' +
      escapeHtml(t("miniapp.d02.goal_label")) +
      "</label>" +
      renderRadioOpt("goal_focus", "both", t("miniapp.d02.goal_both"), draft.goal_focus === "both") +
      renderRadioOpt("goal_focus", "knowledge", t("miniapp.d02.goal_knowledge"), draft.goal_focus === "knowledge") +
      renderRadioOpt("goal_focus", "habits", t("miniapp.d02.goal_habits"), draft.goal_focus === "habits") +
      "</div>" +
      /* Daily Minutes */
      '<div class="col" style="gap:8px;">' +
      '<label class="lab">' +
      escapeHtml(t("miniapp.d02.minutes_label")) +
      "</label>" +
      '<div class="rw">' +
      renderMinutesChip(5, t("miniapp.d02.min_5"), draft.daily_study_minutes === 5) +
      renderMinutesChip(10, t("miniapp.d02.min_10"), draft.daily_study_minutes === 10) +
      renderMinutesChip(15, t("miniapp.d02.min_15"), draft.daily_study_minutes === 15) +
      renderMinutesChip(20, t("miniapp.d02.min_20"), draft.daily_study_minutes === 20) +
      "</div>" +
      "</div>" +
      /* Reminder Window */
      '<div class="col" style="gap:8px;">' +
      '<label class="lab">' +
      escapeHtml(t("miniapp.d02.window_label")) +
      "</label>" +
      renderRadioOpt("reminder_window", "morning", t("miniapp.d02.win_morning"), draft.reminder_window === "morning") +
      renderRadioOpt("reminder_window", "afternoon", t("miniapp.d02.win_afternoon"), draft.reminder_window === "afternoon") +
      renderRadioOpt("reminder_window", "evening", t("miniapp.d02.win_evening"), draft.reminder_window === "evening") +
      "</div>" +
      /* Timezone */
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d02-tz-input">' +
      escapeHtml(t("miniapp.d02.tz_label")) +
      "</label>" +
      '<input id="d02-tz-input" class="inp" type="text" value="' +
      escapeHtml(draft.timezone) +
      '" />' +
      "</div>" +
      '<div class="col" style="gap:8px; margin-top:6px;">' +
      '<button type="button" class="btn" id="d02-save-btn">' +
      escapeHtml(t("miniapp.d02.submit_cta")) +
      "</button>" +
      '<button type="button" class="btn b3" id="d02-skip-btn">' +
      escapeHtml(t("miniapp.d02.skip_cta")) +
      "</button>" +
      "</div>" +
      "</section>";

    bindLanguageButtons(vp);

    vp.querySelectorAll("[data-opt-field]").forEach(function (el) {
      el.addEventListener("click", function () {
        triggerHaptic("selection");
        const field = el.getAttribute("data-opt-field");
        const val = el.getAttribute("data-opt-val");
        if (field === "daily_study_minutes") {
          state.onboardingDraft.daily_study_minutes = parseInt(val, 10);
        } else {
          state.onboardingDraft[field] = val;
        }
        renderCurrentScreen();
      });
    });

    const tzInput = document.getElementById("d02-tz-input");
    if (tzInput) {
      tzInput.addEventListener("input", function () {
        state.onboardingDraft.timezone = tzInput.value.trim();
      });
    }

    const saveBtn = document.getElementById("d02-save-btn");
    if (saveBtn) {
      saveBtn.addEventListener("click", async function () {
        triggerHaptic("notification", "success");
        try {
          if (state.authenticated) {
            const res = await apiFetch("api/v1/onboarding", {
              method: "POST",
              body: state.onboardingDraft,
            });
            if (res.user) state.user = res.user;
          }
        } catch (_e) {}
        state.historyStack = [];
        navigateTo("D03", { pushHistory: false });
      });
    }

    const skipBtn = document.getElementById("d02-skip-btn");
    if (skipBtn) {
      skipBtn.addEventListener("click", function () {
        state.historyStack = [];
        navigateTo("D03", { pushHistory: false });
      });
    }
  }

  function renderRadioOpt(field, val, label, active) {
    return (
      '<button type="button" class="opt ' +
      (active ? "on" : "") +
      '" data-opt-field="' +
      escapeHtml(field) +
      '" data-opt-val="' +
      escapeHtml(val) +
      '">' +
      '<span class="rad"></span>' +
      '<span class="grow">' +
      escapeHtml(label) +
      "</span>" +
      "</button>"
    );
  }

  function renderMinutesChip(val, label, active) {
    return (
      '<button type="button" class="chip ' +
      (active ? "c-pr" : "") +
      '" data-opt-field="daily_study_minutes" data-opt-val="' +
      val +
      '" style="cursor:pointer; min-height:38px; padding:6px 14px;">' +
      escapeHtml(label) +
      "</button>"
    );
  }

  // ==================== D03: Today Screen Shell ====================
  function renderD03(vp) {
    vp.innerHTML =
      renderTopBar(t("miniapp.d03.greeting"), false) +
      '<section class="streak">' +
      '<div class="stk-top">' +
      '<div class="row" style="gap:12px;">' +
      '<span class="stk-n">0</span>' +
      '<div class="stk-u">' +
      escapeHtml(t("miniapp.d03.day_status_neutral")) +
      "<span>" +
      escapeHtml(t("miniapp.common.free_forever")) +
      "</span></div>" +
      "</div>" +
      '<button type="button" class="btn b2 bsm" id="d03-open-d42-btn">' +
      escapeHtml(t("miniapp.common.why_this_exercise")) +
      "</button>" +
      "</div>" +
      "</section>" +
      '<section class="card cardp col">' +
      '<div class="row sp">' +
      '<h2 class="h2">' +
      escapeHtml(t("miniapp.d03.study_card_title")) +
      "</h2>" +
      '<span class="chip c-pr">' +
      escapeHtml(((state.user && state.user.daily_study_minutes) || 10) + " " + t("miniapp.common.minutes_short")) +
      "</span>" +
      "</div>" +
      '<p class="mu sm">' +
      escapeHtml(t("miniapp.d03.study_card_empty")) +
      "</p>" +
      '<button type="button" class="btn" id="d03-open-landing-btn">' +
      escapeHtml(t("miniapp.d00.view_landing_cta")) +
      "</button>" +
      "</section>";

    bindLanguageButtons(vp);

    const openD42 = document.getElementById("d03-open-d42-btn");
    if (openD42) {
      openD42.addEventListener("click", function () {
        openScienceSheet("M1");
      });
    }
    const openLanding = document.getElementById("d03-open-landing-btn");
    if (openLanding) {
      openLanding.addEventListener("click", function () {
        navigateTo("D01");
      });
    }
  }

  // ==================== D42: "Why This Exercise?" Science Bottom Sheet ====================
  function openScienceSheet(methodId) {
    state.activeMethodTab = methodId || "M1";
    state.currentSheetType = "D42";
    const methods = state.methodIntros || [];
    const activeObj =
      methods.find(function (m) {
        return m.method_id === state.activeMethodTab;
      }) || methods[0];

    const tabsHtml = ["M1", "M2", "M3", "M4", "M5"]
      .map(function (mid) {
        const key = "miniapp.d42.tab_" + mid.toLowerCase();
        return (
          '<button type="button" class="' +
          (state.activeMethodTab === mid ? "on" : "") +
          '" data-science-tab="' +
          mid +
          '">' +
          escapeHtml(t(key)) +
          "</button>"
        );
      })
      .join("");

    let detailHtml = "";
    if (activeObj) {
      const badges = [];
      if (activeObj.is_updated) {
        badges.push('<span class="chip c-ai">' + escapeHtml(t("miniapp.common.updated_badge")) + "</span>");
      }
      if (activeObj.evidence_level === "indirect") {
        badges.push('<span class="chip c-wn">' + escapeHtml(t("miniapp.common.indirect_badge")) + "</span>");
      }
      const metricsHtml = activeObj.metrics_highlight
        ? '<div class="bn ok col" style="gap:4px;">' +
          '<div class="b">' +
          escapeHtml(
            activeObj.metrics_highlight.delayed_recall_test_pct +
              " vs " +
              activeObj.metrics_highlight.delayed_recall_reread_pct +
              " (" +
              activeObj.metrics_highlight.delay +
              ")"
          ) +
          "</div>" +
          '<div class="sm">' +
          escapeHtml(activeObj.metrics_highlight.scope_caveat) +
          "</div>" +
          "</div>"
        : "";

      const sourcesHtml = (activeObj.sources || [])
        .map(function (s) {
          return (
            '<div class="sm" style="margin-bottom:6px;">• ' +
            escapeHtml(s.citation) +
            ' <a href="' +
            escapeHtml(s.url) +
            '" target="_blank" rel="noopener noreferrer">DOI</a></div>'
          );
        })
        .join("");

      detailHtml =
        '<div class="rw">' +
        badges.join("") +
        "</div>" +
        '<div class="h2">' +
        escapeHtml(activeObj.title) +
        "</div>" +
        '<p class="mu sm">' +
        escapeHtml(activeObj.subtitle) +
        "</p>" +
        metricsHtml +
        '<div class="card col" style="gap:6px;">' +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.d42.section_what")) +
        "</div>" +
        "<div>" +
        escapeHtml(activeObj.what_you_do) +
        "</div>" +
        "</div>" +
        '<div class="card col" style="gap:6px;">' +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.d42.section_why")) +
        "</div>" +
        "<div>" +
        escapeHtml(activeObj.why_it_works) +
        "</div>" +
        "</div>" +
        '<div class="card col" style="gap:6px;">' +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.d42.section_exp")) +
        "</div>" +
        "<div>" +
        escapeHtml(activeObj.experiments) +
        "</div>" +
        "</div>" +
        '<div class="card col" style="gap:6px;">' +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.d42.section_limits")) +
        "</div>" +
        "<div>" +
        escapeHtml(activeObj.limitations) +
        "</div>" +
        "</div>" +
        '<div class="card col" style="gap:6px;">' +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.d42.section_sources")) +
        "</div>" +
        sourcesHtml +
        "</div>" +
        '<div class="row" style="gap:10px; margin-top:4px;">' +
        '<button type="button" class="btn" id="d42-ack-btn">' +
        escapeHtml(t("miniapp.common.got_it")) +
        "</button>" +
        '<button type="button" class="btn b2" id="d42-later-btn">' +
        escapeHtml(t("miniapp.common.later")) +
        "</button>" +
        "</div>";
    }

    openBottomSheet({
      size: "large",
      title: t("miniapp.d42.sheet_title"),
      bodyHtml: '<div class="seg">' + tabsHtml + "</div>" + detailHtml,
    });

    const bodyEl = document.getElementById("sheet-body");
    if (bodyEl) {
      bodyEl.querySelectorAll("[data-science-tab]").forEach(function (tabBtn) {
        tabBtn.addEventListener("click", function () {
          triggerHaptic("selection");
          openScienceSheet(tabBtn.getAttribute("data-science-tab"));
        });
      });

      const ackBtn = document.getElementById("d42-ack-btn");
      if (ackBtn) {
        ackBtn.addEventListener("click", async function () {
          triggerHaptic("notification", "success");
          await recordMethodIntroStatus(state.activeMethodTab, "acknowledged");
          closeBottomSheet();
        });
      }

      const laterBtn = document.getElementById("d42-later-btn");
      if (laterBtn) {
        laterBtn.addEventListener("click", async function () {
          await recordMethodIntroStatus(state.activeMethodTab, "dismissed");
          closeBottomSheet();
        });
      }
    }
  }

  async function recordMethodIntroStatus(methodId, statusVal) {
    if (!state.authenticated) return;
    try {
      const res = await apiFetch("api/v1/me/method-intros/" + encodeURIComponent(methodId), {
        method: "PUT",
        body: { status: statusVal },
      });
      if (res.methods) {
        state.methodIntros = res.methods;
      }
    } catch (_e) {}
  }

  // ==================== Bottom Sheet Controller (Section 3.12) ====================
  function openBottomSheet(cfg) {
    const root = document.getElementById("sheet-root");
    const panel = document.getElementById("sheet-panel");
    const titleEl = document.getElementById("sheet-title");
    const closeBtn = document.getElementById("sheet-close-btn");
    const bodyEl = document.getElementById("sheet-body");
    if (!root || !panel || !titleEl || !bodyEl) return;

    panel.className = cfg.size || "medium";
    titleEl.textContent = cfg.title || "";
    if (closeBtn) closeBtn.textContent = t("miniapp.common.close");
    bodyEl.innerHTML = cfg.bodyHtml || "";

    state.sheetOpen = true;
    state.sheetOnClose = cfg.onClose || null;
    root.classList.add("open");
    root.setAttribute("aria-hidden", "false");

    if (tg && typeof tg.disableVerticalSwipes === "function") {
      try {
        tg.disableVerticalSwipes();
      } catch (_e) {}
    }
    syncBackButton();
  }

  function closeBottomSheet() {
    const root = document.getElementById("sheet-root");
    const panel = document.getElementById("sheet-panel");
    if (!root || !panel) return;

    state.sheetOpen = false;
    state.currentSheetType = null;
    panel.style.transform = "";
    root.classList.remove("open");
    root.setAttribute("aria-hidden", "true");

    if (typeof state.sheetOnClose === "function") {
      const cb = state.sheetOnClose;
      state.sheetOnClose = null;
      cb();
    }
    syncBackButton();
  }

  function initSheetDragAndEvents() {
    const scrim = document.getElementById("sheet-scrim");
    const closeBtn = document.getElementById("sheet-close-btn");
    const header = document.getElementById("sheet-header");
    const panel = document.getElementById("sheet-panel");

    if (scrim) scrim.addEventListener("click", closeBottomSheet);
    if (closeBtn) closeBtn.addEventListener("click", closeBottomSheet);

    if (header && panel) {
      let startY = 0;
      let currentDelta = 0;
      let dragging = false;

      header.addEventListener(
        "touchstart",
        function (ev) {
          if (!state.sheetOpen || ev.touches.length !== 1) return;
          startY = ev.touches[0].clientY;
          currentDelta = 0;
          dragging = true;
          panel.style.transition = "none";
        },
        { passive: true }
      );

      header.addEventListener(
        "touchmove",
        function (ev) {
          if (!dragging) return;
          const dy = Math.max(0, ev.touches[0].clientY - startY);
          currentDelta = dy;
          panel.style.transform = "translateY(" + dy + "px)";
        },
        { passive: true }
      );

      header.addEventListener("touchend", function () {
        if (!dragging) return;
        dragging = false;
        panel.style.transition = "";
        if (currentDelta > 72) {
          closeBottomSheet();
        } else {
          panel.style.transform = "";
        }
      });
    }
  }

  // ==================== Edge-Back Gesture (Left & Right Edges, Section 3.13) ====================
  function initEdgeBackGesture() {
    const indicator = document.getElementById("edge-back-indicator");
    const shell = document.getElementById("app-shell");
    if (!indicator || !shell) return;

    const EDGE_ZONE_PX = 24;
    const TRIGGER_THRESHOLD_PX = 84;

    let activeSide = null;
    let startX = 0;
    let startY = 0;
    let armed = false;
    let canceled = false;

    shell.addEventListener(
      "touchstart",
      function (ev) {
        if (ev.touches.length !== 1) return;
        const canGoBack = state.sheetOpen || state.historyStack.length > 0;
        if (!canGoBack) return;

        const touch = ev.touches[0];
        const rect = shell.getBoundingClientRect();
        const relX = touch.clientX - rect.left;
        const width = rect.width;

        if (relX <= EDGE_ZONE_PX) {
          activeSide = "left";
        } else if (width - relX <= EDGE_ZONE_PX) {
          activeSide = "right";
        } else {
          activeSide = null;
          return;
        }

        startX = touch.clientX;
        startY = touch.clientY;
        armed = false;
        canceled = false;

        indicator.className = activeSide;
        indicator.style.opacity = "0";
      },
      { passive: true }
    );

    shell.addEventListener(
      "touchmove",
      function (ev) {
        if (!activeSide || canceled || ev.touches.length !== 1) return;
        const touch = ev.touches[0];
        const dx = activeSide === "left" ? touch.clientX - startX : startX - touch.clientX;
        const dy = Math.abs(touch.clientY - startY);

        if (dy > 42 && dy > Math.abs(dx)) {
          canceled = true;
          indicator.style.opacity = "0";
          return;
        }

        if (dx <= 6) {
          indicator.style.opacity = "0";
          return;
        }

        const progress = Math.min(1, dx / TRIGGER_THRESHOLD_PX);
        indicator.style.opacity = String(Math.min(1, progress * 1.2));
        const shift = activeSide === "left" ? Math.min(28, dx * 0.28) : -Math.min(28, dx * 0.28);
        indicator.style.transform = "translateX(" + shift + "px)";

        const nowArmed = dx >= TRIGGER_THRESHOLD_PX;
        if (nowArmed && !armed) {
          armed = true;
          indicator.classList.add("armed");
          triggerHaptic("impact", "light");
        } else if (!nowArmed && armed) {
          armed = false;
          indicator.classList.remove("armed");
        }
      },
      { passive: true }
    );

    function finishEdgeGesture() {
      if (!activeSide) return;
      const shouldTrigger = armed && !canceled;
      activeSide = null;
      armed = false;
      indicator.style.opacity = "0";
      indicator.style.transform = "";
      indicator.classList.remove("armed");

      if (shouldTrigger) {
        handleHierarchicalBack();
      }
    }

    shell.addEventListener("touchend", finishEdgeGesture);
    shell.addEventListener("touchcancel", finishEdgeGesture);
  }

  function escapeHtml(raw) {
    return String(raw == null ? "" : raw)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function bootstrapApp() {
    applyTelegramThemeAndSafeAreas();
    initSheetDragAndEvents();
    initEdgeBackGesture();

    if (tg && tg.BackButton) {
      try {
        tg.BackButton.onClick(function () {
          handleHierarchicalBack();
        });
      } catch (_e) {}
    }

    const nav = document.getElementById("bottom-nav");
    if (nav) {
      nav.querySelectorAll(".tab").forEach(function (tabEl) {
        tabEl.addEventListener("click", function (ev) {
          ev.preventDefault();
          const dest = tabEl.getAttribute("data-nav");
          if (dest) {
            state.historyStack = [];
            navigateTo(dest, { pushHistory: false });
          }
        });
      });
    }

    window.addEventListener("online", function () {
      const b = document.getElementById("offline-banner");
      if (b) b.style.display = "none";
    });
    window.addEventListener("offline", function () {
      const b = document.getElementById("offline-banner");
      const bt = document.getElementById("offline-banner-text");
      if (bt) bt.textContent = t("miniapp.common.offline_banner");
      if (b) b.style.display = "flex";
    });

    try {
      const res = await apiFetch("api/v1/auth/bootstrap", {
        method: "POST",
        body: {
          init_data: tg && tg.initData ? tg.initData : null,
          locale_hint: state.locale,
          timezone_hint: Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Moscow",
        },
      });
      state.authenticated = Boolean(res.authenticated);
      state.insideTelegram = Boolean(res.inside_telegram);
      if (res.session_token) {
        state.sessionToken = res.session_token;
        localStorage.setItem("br_session_token", res.session_token);
      }
      if (res.locale) {
        state.locale = res.locale;
        localStorage.setItem("br_locale", res.locale);
      }
      state.catalog = res.catalog || {};
      state.user = res.user || null;
      state.counts = res.counts || { topics: 0, habits: 0, items: 0 };
      state.methodIntros = res.method_intros || [];

      navigateTo(res.initial_screen || "D01", { pushHistory: false });
    } catch (_err) {
      navigateTo("D01", { pushHistory: false });
    }
  }

  document.addEventListener("DOMContentLoaded", bootstrapApp);
})();
