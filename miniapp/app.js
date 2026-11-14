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
    topicsList: [],
    topicsLimit: 3,
    activeTopicId: null,
    activeTopicDetail: null,
    activeTopicTab: "items",
    activeItemId: null,
    activeItemDetail: null,
    activeGroupId: null,
    activeGroupDetail: null,
    searchQuery: "",
    searchResults: null,
    itemDraft: null,
    groupDraft: null,
    returnToD41AfterItemCreate: false,
    sessionSetupMode: "regular",
    sessionTopicFilter: null,
    sessionGroupFilter: null,
    activeStudySession: null,
    studyAnswerMode: "written",
    studyFormulaRevealed: false,
    studyCheckedCriteria: [],
    lastAttemptResult: null,
    lastNeedsCorrective: false,
    todayData: null,
    habitsList: [],
    habitsLimit: 3,
    activeHabitId: null,
    activeHabitDetail: null,
    habitDraft: null,
    streaksData: null,
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
    } else if (state.currentScreen === "D04") {
      renderD04(vp);
    } else if (state.currentScreen === "D05") {
      renderD05(vp);
    } else if (state.currentScreen === "D07") {
      renderD07(vp);
    } else if (state.currentScreen === "D08") {
      renderD08(vp);
    } else if (state.currentScreen === "D09") {
      renderD09(vp);
    } else if (state.currentScreen === "D09-Edit") {
      renderD09Edit(vp);
    } else if (state.currentScreen === "D40") {
      renderD40(vp);
    } else if (state.currentScreen === "D41") {
      renderD41(vp);
    } else if (state.currentScreen === "D10") {
      renderD10(vp);
    } else if (state.currentScreen === "D11") {
      renderD11(vp);
    } else if (state.currentScreen === "D12") {
      renderD12(vp);
    } else if (state.currentScreen === "D13") {
      renderD13(vp);
    } else if (state.currentScreen === "D14" || state.currentScreen === "D15") {
      renderD14D15(vp);
    } else if (state.currentScreen === "D16") {
      renderD16(vp);
    } else if (state.currentScreen === "D17") {
      renderD17(vp);
    } else if (state.currentScreen === "D18") {
      renderD18(vp);
    } else if (state.currentScreen === "D19") {
      renderD19(vp);
    } else if (state.currentScreen === "D20") {
      renderD20(vp);
    } else if (state.currentScreen === "D21") {
      renderD21(vp);
    } else if (state.currentScreen === "D24") {
      renderD24(vp);
    } else if (state.currentScreen === "D25") {
      renderD25(vp);
    } else if (state.currentScreen === "D26") {
      renderD26(vp);
    } else if (state.currentScreen === "D27" || state.currentScreen === "D28") {
      renderD27D28(vp);
    } else if (state.currentScreen === "D29") {
      renderD29(vp);
    } else if (state.currentScreen === "D31") {
      renderD31(vp);
    } else if (state.currentScreen === "D32") {
      renderD32(vp);
    } else if (state.currentScreen === "D33") {
      renderD33(vp);
    } else if (state.currentScreen === "D35") {
      renderD35(vp);
    } else if (state.currentScreen === "D36") {
      renderD36(vp);
    } else if (state.currentScreen === "D39") {
      renderD39(vp);
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

  // ==================== D03: Live Today Screen ====================
  async function renderD03(vp) {
    vp.innerHTML =
      renderTopBar(t("miniapp.d03.greeting"), false) +
      '<div class="sk" style="height:110px; border-radius:28px;"></div>' +
      '<div class="sk" style="height:150px; border-radius:24px;"></div>';
    bindLanguageButtons(vp);

    try {
      const td = await apiFetch("api/v1/today");
      state.todayData = td;
      const dp = td.day_plan || {};
      const stk = td.streak || { current: 0, best: 0, freeze_stock: 0, freeze_max: 2 };
      const habits = td.habits || [];

      const statusKey = "miniapp.d03.day_status_" + (dp.day_state || "neutral");
      const habitsHtml = habits.length
        ? '<div class="list">' +
          habits
            .map(function (h) {
              const badge =
                h.today_outcome === "full_done"
                  ? '<span class="chip c-ok">✓</span>'
                  : h.today_outcome === "minimum_done"
                  ? '<span class="chip c-em">2m ✓</span>'
                  : '<span class="chip">○</span>';
              return (
                '<button type="button" class="li" data-d03-habit="' +
                escapeHtml(h.id) +
                '" style="width:100%; background:none; border:0; border-top:1px solid var(--ln); text-align:left; cursor:pointer; font-family:inherit;">' +
                '<div class="col grow" style="gap:2px;">' +
                '<div class="b">' +
                escapeHtml(h.title) +
                "</div>" +
                '<div class="sm mu">' +
                escapeHtml(h.minimum_version) +
                "</div>" +
                "</div>" +
                badge +
                "</button>"
              );
            })
            .join("") +
          "</div>"
        : '<div class="card col"><p class="sm mu">' +
          escapeHtml(t("miniapp.d03.habits_empty")) +
          '</p><button type="button" class="btn b2 bsm" id="d03-add-habit-btn">' +
          escapeHtml(t("miniapp.d03.add_first_habit")) +
          "</button></div>";

      vp.innerHTML =
        renderTopBar(t("miniapp.d03.greeting"), false) +
        '<section class="streak" id="d03-streak-card" style="cursor:pointer;">' +
        '<div class="stk-top">' +
        '<div class="row" style="gap:12px;">' +
        '<span class="stk-n">' +
        stk.current +
        "</span>" +
        '<div class="stk-u">' +
        escapeHtml(t(statusKey)) +
        "<span>❄️ " +
        stk.freeze_stock +
        "/" +
        stk.freeze_max +
        " · " +
        escapeHtml(t("miniapp.common.free_forever")) +
        "</span></div>" +
        "</div>" +
        '<button type="button" class="btn b2 bsm" id="d03-open-d36-btn">🔥 D36</button>' +
        "</div>" +
        "</section>" +
        '<section class="card cardp col">' +
        '<div class="row sp">' +
        '<h2 class="h2">' +
        escapeHtml(t("miniapp.d03.study_card_title")) +
        "</h2>" +
        '<span class="chip c-pr">' +
        dp.required_reviews_done +
        "/" +
        dp.required_reviews_total +
        "</span>" +
        "</div>" +
        '<p class="mu sm">' +
        escapeHtml(t("miniapp.d03.study_card_empty")) +
        "</p>" +
        '<div class="col" style="gap:8px;">' +
        '<button type="button" class="btn" id="d03-start-session-btn">' +
        escapeHtml(td.active_session_id ? t("miniapp.d03.resume_session_cta") : t("miniapp.d03.start_session_cta")) +
        "</button>" +
        '<div class="row" style="gap:8px;">' +
        '<button type="button" class="btn b2 bsm grow" id="d03-open-d42-btn">' +
        escapeHtml(t("miniapp.common.why_this_exercise")) +
        "</button>" +
        '<button type="button" class="btn b2 bsm grow" id="d03-open-landing-btn">D01</button>' +
        "</div>" +
        "</div>" +
        "</section>" +
        '<section class="col" style="gap:10px;">' +
        '<div class="row sp">' +
        '<h2 class="h2">' +
        escapeHtml(t("miniapp.d03.habits_card_title")) +
        "</h2>" +
        '<span class="chip">' +
        dp.required_habits_done +
        "/" +
        dp.required_habits_total +
        "</span>" +
        "</div>" +
        habitsHtml +
        "</section>";

      bindLanguageButtons(vp);

      const openD36 = document.getElementById("d03-open-d36-btn");
      if (openD36) {
        openD36.addEventListener("click", function (ev) {
          ev.stopPropagation();
          navigateTo("D36");
        });
      }
      const stkCard = document.getElementById("d03-streak-card");
      if (stkCard) {
        stkCard.addEventListener("click", function () {
          navigateTo("D36");
        });
      }
      const openD42 = document.getElementById("d03-open-d42-btn");
      if (openD42) {
        openD42.addEventListener("click", function () {
          openScienceSheet("M1");
        });
      }
      const startSess = document.getElementById("d03-start-session-btn");
      if (startSess) {
        startSess.addEventListener("click", function () {
          state.sessionTopicFilter = null;
          state.sessionGroupFilter = null;
          navigateTo("D10");
        });
      }
      const openLanding = document.getElementById("d03-open-landing-btn");
      if (openLanding) {
        openLanding.addEventListener("click", function () {
          navigateTo("D01");
        });
      }
      const addHabitBtn = document.getElementById("d03-add-habit-btn");
      if (addHabitBtn) {
        addHabitBtn.addEventListener("click", function () {
          openHabitWizardD20(null);
        });
      }
      vp.querySelectorAll("[data-d03-habit]").forEach(function (el) {
        el.addEventListener("click", function () {
          const hid = el.getAttribute("data-d03-habit");
          const hObj = habits.find(function (x) {
            return x.id === hid;
          });
          if (hObj) openHabitMarkSheetD22(hObj);
        });
      });

      if (td.celebration) {
        openCelebrationSheetD38(td.celebration);
      }
    } catch (_e) {}
  }

  // ==================== D04: Knowledge & Topics Hub ====================
  async function renderD04(vp) {
    vp.innerHTML =
      renderTopBar(t("miniapp.knowledge.title"), false) +
      '<div class="row" style="gap:8px;">' +
      '<button type="button" class="inp grow row" id="d04-search-trigger" style="text-align:left; cursor:pointer; color:var(--mu);">' +
      escapeHtml(t("miniapp.knowledge.search_placeholder")) +
      "</button>" +
      '<button type="button" class="btn bsm" id="d04-add-btn">' +
      escapeHtml(t("miniapp.knowledge.add_btn")) +
      "</button>" +
      "</div>" +
      '<div id="d04-topics-container" class="col" style="gap:12px;">' +
      '<div class="sk" style="height:68px; border-radius:20px;"></div>' +
      "</div>";

    bindLanguageButtons(vp);

    const searchTrig = document.getElementById("d04-search-trigger");
    if (searchTrig) {
      searchTrig.addEventListener("click", function () {
        state.searchQuery = "";
        state.searchResults = null;
        navigateTo("D05");
      });
    }

    const addBtn = document.getElementById("d04-add-btn");
    if (addBtn) {
      addBtn.addEventListener("click", function () {
        openAddSheetD06(null);
      });
    }

    try {
      const data = await apiFetch("api/v1/topics");
      state.topicsList = data.topics || [];
      state.topicsLimit = data.active_limit || 3;
      const box = document.getElementById("d04-topics-container");
      if (!box) return;

      const quotaText = t("miniapp.knowledge.active_topics_quota", {
        used: data.active_count || 0,
        limit: state.topicsLimit,
      });

      if (state.topicsList.length === 0) {
        box.innerHTML =
          '<div class="chip">' +
          escapeHtml(quotaText) +
          "</div>" +
          '<div class="card col" style="text-align:center; padding:26px 18px;">' +
          '<p class="mu">' +
          escapeHtml(t("miniapp.knowledge.empty_topics")) +
          "</p>" +
          '<button type="button" class="btn" id="d04-create-first-topic">' +
          escapeHtml(t("miniapp.knowledge.add_topic_opt")) +
          "</button>" +
          "</div>";
        const firstBtn = document.getElementById("d04-create-first-topic");
        if (firstBtn) {
          firstBtn.addEventListener("click", function () {
            openTopicFormD07(null);
          });
        }
        return;
      }

      const listHtml = state.topicsList
        .map(function (tp) {
          return (
            '<button type="button" class="card col" data-open-topic="' +
            escapeHtml(tp.id) +
            '" style="text-align:left; cursor:pointer; width:100%; font-family:inherit;">' +
            '<div class="row sp">' +
            '<span class="h3">' +
            escapeHtml(tp.title) +
            "</span>" +
            '<span class="chip">' +
            escapeHtml(tp.status) +
            "</span>" +
            "</div>" +
            '<div class="rw sm mu">' +
            "<span>" +
            escapeHtml(t("miniapp.knowledge.tab_items") + ": " + tp.items_count) +
            "</span>" +
            "<span>·</span>" +
            "<span>" +
            escapeHtml(t("miniapp.knowledge.tab_groups") + ": " + tp.groups_count) +
            "</span>" +
            "</div>" +
            "</button>"
          );
        })
        .join("");

      box.innerHTML = '<div class="chip">' + escapeHtml(quotaText) + "</div>" + listHtml;
      box.querySelectorAll("[data-open-topic]").forEach(function (el) {
        el.addEventListener("click", function () {
          state.activeTopicId = el.getAttribute("data-open-topic");
          state.activeTopicTab = "items";
          navigateTo("D08");
        });
      });
    } catch (_e) {}
  }

  // ==================== D05: Search Screen ====================
  function renderD05(vp) {
    vp.innerHTML =
      renderTopBar(t("miniapp.knowledge.title"), true) +
      '<div class="row" style="gap:8px;">' +
      '<input id="d05-search-input" class="inp grow" type="search" placeholder="' +
      escapeHtml(t("miniapp.knowledge.search_placeholder")) +
      '" value="' +
      escapeHtml(state.searchQuery) +
      '" />' +
      "</div>" +
      '<div id="d05-results-box" class="col" style="gap:10px;"></div>';

    bindLanguageButtons(vp);
    const inp = document.getElementById("d05-search-input");
    if (inp) {
      inp.focus();
      inp.addEventListener("input", async function () {
        state.searchQuery = inp.value;
        await runSearchD05();
      });
    }
    runSearchD05();
  }

  async function runSearchD05() {
    const box = document.getElementById("d05-results-box");
    if (!box) return;
    try {
      const res = await apiFetch("api/v1/search?q=" + encodeURIComponent(state.searchQuery || ""));
      const itemsHtml = (res.items || [])
        .map(function (it) {
          return (
            '<button type="button" class="li" data-search-item="' +
            escapeHtml(it.id) +
            '" style="width:100%; background:none; border:0; border-top:1px solid var(--ln); text-align:left; cursor:pointer; font-family:inherit;">' +
            '<div class="col grow" style="gap:2px;">' +
            '<div class="b">' +
            escapeHtml(it.prompt) +
            "</div>" +
            '<div class="sm mu">' +
            escapeHtml(it.answer) +
            "</div>" +
            "</div>" +
            '<span class="chip">' +
            escapeHtml(it.item_type) +
            "</span>" +
            "</button>"
          );
        })
        .join("");

      const groupsHtml = (res.groups || [])
        .map(function (g) {
          return (
            '<button type="button" class="li" data-search-group="' +
            escapeHtml(g.id) +
            '" style="width:100%; background:none; border:0; border-top:1px solid var(--ln); text-align:left; cursor:pointer; font-family:inherit;">' +
            '<div class="col grow" style="gap:2px;">' +
            '<div class="b">🕸 ' +
            escapeHtml(g.title) +
            "</div>" +
            '<div class="sm mu">' +
            escapeHtml(g.principle) +
            "</div>" +
            "</div>" +
            "</button>"
          );
        })
        .join("");

      box.innerHTML =
        (groupsHtml ? '<div class="list">' + groupsHtml + "</div>" : "") +
        (itemsHtml ? '<div class="list">' + itemsHtml + "</div>" : "");

      box.querySelectorAll("[data-search-item]").forEach(function (el) {
        el.addEventListener("click", function () {
          state.activeItemId = el.getAttribute("data-search-item");
          navigateTo("D09");
        });
      });
      box.querySelectorAll("[data-search-group]").forEach(function (el) {
        el.addEventListener("click", function () {
          state.activeGroupId = el.getAttribute("data-search-group");
          navigateTo("D40");
        });
      });
    } catch (_e) {}
  }

  // ==================== D06: Add Action Bottom Sheet ====================
  function openAddSheetD06(topicId) {
    openBottomSheet({
      size: "small",
      title: t("miniapp.knowledge.add_sheet_title"),
      bodyHtml:
        '<div class="col" style="gap:10px;">' +
        '<button type="button" class="opt" id="d06-opt-topic"><span class="grow b">' +
        escapeHtml(t("miniapp.knowledge.add_topic_opt")) +
        "</span></button>" +
        '<button type="button" class="opt" id="d06-opt-material"><span class="grow b">✨ ' +
        escapeHtml(t("miniapp.materials.d14_title")) +
        "</span></button>" +
        (topicId
          ? '<button type="button" class="opt" id="d06-opt-item"><span class="grow b">' +
            escapeHtml(t("miniapp.knowledge.add_item_opt")) +
            "</span></button>" +
            '<button type="button" class="opt" id="d06-opt-group"><span class="grow b">' +
            escapeHtml(t("miniapp.knowledge.add_group_opt")) +
            "</span></button>"
          : "") +
        "</div>",
    });

    const optTopic = document.getElementById("d06-opt-topic");
    if (optTopic) {
      optTopic.addEventListener("click", function () {
        closeBottomSheet();
        openTopicFormD07(null);
      });
    }
    const optMat = document.getElementById("d06-opt-material");
    if (optMat) {
      optMat.addEventListener("click", function () {
        closeBottomSheet();
        openMaterialInputD14(topicId || null);
      });
    }
    const optItem = document.getElementById("d06-opt-item");
    if (optItem) {
      optItem.addEventListener("click", function () {
        closeBottomSheet();
        openItemEditorD09Edit(topicId, null, false);
      });
    }
    const optGroup = document.getElementById("d06-opt-group");
    if (optGroup) {
      optGroup.addEventListener("click", function () {
        closeBottomSheet();
        openGroupEditorD41(topicId, null);
      });
    }
  }

  // ==================== D07: Create / Edit Topic ====================
  function openTopicFormD07(existingTopic) {
    state.topicDraft = existingTopic
      ? {
          id: existingTopic.id,
          title: existingTopic.title,
          goal: existingTopic.goal,
          goal_note: existingTopic.goal_note || "",
          revision: existingTopic.revision,
        }
      : { id: null, title: "", goal: "free", goal_note: "" };
    navigateTo("D07");
  }

  function renderD07(vp) {
    const draft = state.topicDraft || { id: null, title: "", goal: "free", goal_note: "" };
    const isEdit = Boolean(draft.id);
    const titleStr = isEdit ? t("miniapp.knowledge.edit_topic_title") : t("miniapp.knowledge.create_topic_title");

    vp.innerHTML =
      renderTopBar(titleStr, true) +
      '<section class="card col" style="gap:14px;">' +
      '<h1 class="h2">' +
      escapeHtml(titleStr) +
      "</h1>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d07-title">' +
      escapeHtml(t("miniapp.knowledge.topic_name_label")) +
      "</label>" +
      '<input id="d07-title" class="inp" type="text" placeholder="' +
      escapeHtml(t("miniapp.knowledge.topic_name_placeholder")) +
      '" value="' +
      escapeHtml(draft.title) +
      '" />' +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab">' +
      escapeHtml(t("miniapp.knowledge.topic_goal_label")) +
      "</label>" +
      renderGoalChip("exam", t("miniapp.knowledge.goal_exam"), draft.goal === "exam") +
      renderGoalChip("work", t("miniapp.knowledge.goal_work"), draft.goal === "work") +
      renderGoalChip("communication", t("miniapp.knowledge.goal_communication"), draft.goal === "communication") +
      renderGoalChip("personal", t("miniapp.knowledge.goal_personal"), draft.goal === "personal") +
      renderGoalChip("free", t("miniapp.knowledge.goal_free"), draft.goal === "free") +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d07-note">' +
      escapeHtml(t("miniapp.knowledge.topic_note_label")) +
      "</label>" +
      '<textarea id="d07-note" class="inp ta">' +
      escapeHtml(draft.goal_note) +
      "</textarea>" +
      "</div>" +
      '<button type="button" class="btn" id="d07-save-btn">' +
      escapeHtml(t("miniapp.common.save")) +
      "</button>" +
      "</section>";

    bindLanguageButtons(vp);

    const titleInp = document.getElementById("d07-title");
    const noteInp = document.getElementById("d07-note");
    if (titleInp) {
      titleInp.addEventListener("input", function () {
        draft.title = titleInp.value;
      });
    }
    if (noteInp) {
      noteInp.addEventListener("input", function () {
        draft.goal_note = noteInp.value;
      });
    }

    vp.querySelectorAll("[data-goal-opt]").forEach(function (el) {
      el.addEventListener("click", function () {
        draft.goal = el.getAttribute("data-goal-opt");
        renderCurrentScreen();
      });
    });

    const saveBtn = document.getElementById("d07-save-btn");
    if (saveBtn) {
      saveBtn.addEventListener("click", async function () {
        if (!draft.title.trim()) return;
        triggerHaptic("notification", "success");
        try {
          if (isEdit) {
            await apiFetch("api/v1/topics/" + encodeURIComponent(draft.id), {
              method: "PATCH",
              body: {
                title: draft.title,
                goal: draft.goal,
                goal_note: draft.goal_note,
                revision: draft.revision,
              },
            });
            state.activeTopicId = draft.id;
          } else {
            const res = await apiFetch("api/v1/topics", {
              method: "POST",
              body: {
                title: draft.title,
                goal: draft.goal,
                goal_note: draft.goal_note,
              },
            });
            state.activeTopicId = res.topic.id;
          }
          state.topicDraft = null;
          navigateTo("D08", { pushHistory: false });
        } catch (_e) {}
      });
    }
  }

  function renderGoalChip(goalCode, label, active) {
    return (
      '<button type="button" class="opt ' +
      (active ? "on" : "") +
      '" data-goal-opt="' +
      escapeHtml(goalCode) +
      '">' +
      '<span class="rad"></span><span class="grow">' +
      escapeHtml(label) +
      "</span></button>"
    );
  }

  // ==================== D08: Topic Detail (Items / Meaning Groups M5 / Materials) ====================
  async function renderD08(vp) {
    vp.innerHTML =
      renderTopBar(t("miniapp.knowledge.title"), true) +
      '<div class="sk" style="height:120px; border-radius:24px;"></div>';
    bindLanguageButtons(vp);

    if (!state.activeTopicId) {
      navigateTo("D04", { pushHistory: false });
      return;
    }

    try {
      const detail = await apiFetch("api/v1/topics/" + encodeURIComponent(state.activeTopicId));
      state.activeTopicDetail = detail;
      const top = detail.topic;
      const items = detail.items || [];
      const groups = detail.groups || [];

      let tabContentHtml = "";
      if (state.activeTopicTab === "groups") {
        tabContentHtml =
          '<button type="button" class="btn b2" id="d08-new-group-btn">' +
          escapeHtml(t("miniapp.knowledge.add_group_opt")) +
          "</button>" +
          (groups.length
            ? '<div class="list">' +
              groups
                .map(function (g) {
                  const statusChip =
                    g.status === "needs_review"
                      ? '<span class="chip c-wn">!</span>'
                      : '<span class="chip">' + escapeHtml(g.members.length + "/7") + "</span>";
                  return (
                    '<button type="button" class="li" data-open-group="' +
                    escapeHtml(g.id) +
                    '" style="width:100%; background:none; border:0; border-top:1px solid var(--ln); text-align:left; cursor:pointer; font-family:inherit;">' +
                    '<div class="col grow" style="gap:2px;">' +
                    '<div class="b">🕸 ' +
                    escapeHtml(g.title) +
                    "</div>" +
                    '<div class="sm mu">' +
                    escapeHtml(g.principle) +
                    "</div>" +
                    "</div>" +
                    statusChip +
                    "</button>"
                  );
                })
                .join("") +
              "</div>"
            : "");
      } else {
        tabContentHtml =
          '<button type="button" class="btn b2" id="d08-new-item-btn">' +
          escapeHtml(t("miniapp.knowledge.add_item_opt")) +
          "</button>" +
          (items.length
            ? '<div class="list">' +
              items
                .map(function (it) {
                  return (
                    '<button type="button" class="li" data-open-item="' +
                    escapeHtml(it.id) +
                    '" style="width:100%; background:none; border:0; border-top:1px solid var(--ln); text-align:left; cursor:pointer; font-family:inherit;">' +
                    '<div class="col grow" style="gap:2px;">' +
                    '<div class="b">' +
                    escapeHtml(it.prompt) +
                    "</div>" +
                    '<div class="sm mu">' +
                    escapeHtml(it.answer) +
                    "</div>" +
                    "</div>" +
                    '<span class="chip">' +
                    escapeHtml(it.item_type) +
                    "</span>" +
                    "</button>"
                  );
                })
                .join("") +
              "</div>"
            : "");
      }

      vp.innerHTML =
        renderTopBar(top.title, true) +
        '<section class="card col" style="gap:10px;">' +
        '<div class="row sp">' +
        '<h1 class="h2">' +
        escapeHtml(top.title) +
        "</h1>" +
        '<div class="row" style="gap:6px;">' +
        '<button type="button" class="btn b2 bsm" id="d08-edit-topic-btn">' +
        escapeHtml(t("miniapp.common.edit")) +
        "</button>" +
        '<button type="button" class="btn bsm" id="d08-add-sheet-btn">+</button>' +
        "</div>" +
        "</div>" +
        (top.goal_note ? '<p class="sm mu">' + escapeHtml(top.goal_note) + "</p>" : "") +
        "</section>" +
        '<div class="seg">' +
        '<button type="button" class="' +
        (state.activeTopicTab === "items" ? "on" : "") +
        '" data-topic-tab="items">' +
        escapeHtml(t("miniapp.knowledge.tab_items") + " (" + items.length + ")") +
        "</button>" +
        '<button type="button" class="' +
        (state.activeTopicTab === "groups" ? "on" : "") +
        '" data-topic-tab="groups">' +
        escapeHtml(t("miniapp.knowledge.tab_groups") + " (" + groups.length + ")") +
        "</button>" +
        "</div>" +
        tabContentHtml;

      bindLanguageButtons(vp);

      vp.querySelectorAll("[data-topic-tab]").forEach(function (tabBtn) {
        tabBtn.addEventListener("click", function () {
          state.activeTopicTab = tabBtn.getAttribute("data-topic-tab");
          renderCurrentScreen();
        });
      });

      const editTopicBtn = document.getElementById("d08-edit-topic-btn");
      if (editTopicBtn) {
        editTopicBtn.addEventListener("click", function () {
          openTopicFormD07(top);
        });
      }

      const addSheetBtn = document.getElementById("d08-add-sheet-btn");
      if (addSheetBtn) {
        addSheetBtn.addEventListener("click", function () {
          openAddSheetD06(top.id);
        });
      }

      const newItemBtn = document.getElementById("d08-new-item-btn");
      if (newItemBtn) {
        newItemBtn.addEventListener("click", function () {
          openItemEditorD09Edit(top.id, null, false);
        });
      }

      const newGroupBtn = document.getElementById("d08-new-group-btn");
      if (newGroupBtn) {
        newGroupBtn.addEventListener("click", function () {
          openGroupEditorD41(top.id, null);
        });
      }

      vp.querySelectorAll("[data-open-item]").forEach(function (el) {
        el.addEventListener("click", function () {
          state.activeItemId = el.getAttribute("data-open-item");
          navigateTo("D09");
        });
      });

      vp.querySelectorAll("[data-open-group]").forEach(function (el) {
        el.addEventListener("click", function () {
          state.activeGroupId = el.getAttribute("data-open-group");
          navigateTo("D40");
        });
      });
    } catch (_e) {}
  }

  // ==================== D09 & D09-Edit & D34: Knowledge Item View, Editor & Source Excerpt Sheet ====================
  async function renderD09(vp) {
    vp.innerHTML = renderTopBar("", true) + '<div class="sk" style="height:140px;"></div>';
    bindLanguageButtons(vp);
    if (!state.activeItemId) return;

    try {
      const res = await apiFetch("api/v1/items/" + encodeURIComponent(state.activeItemId));
      state.activeItemDetail = res;
      const item = res.item;
      const frag = item.source_fragment;

      const rubricHtml = (item.rubric_criteria || [])
        .map(function (c) {
          return '<div class="sm">• ' + escapeHtml(c) + "</div>";
        })
        .join("");

      vp.innerHTML =
        renderTopBar(t("miniapp.knowledge.tab_items"), true) +
        '<section class="card col" style="gap:12px;">' +
        '<div class="row sp">' +
        '<span class="chip c-pr">' +
        escapeHtml(item.item_type) +
        "</span>" +
        '<button type="button" class="btn b2 bsm" id="d09-edit-btn">' +
        escapeHtml(t("miniapp.common.edit")) +
        "</button>" +
        "</div>" +
        '<h1 class="h2">' +
        escapeHtml(item.prompt) +
        "</h1>" +
        '<div class="dv"></div>' +
        "<div>" +
        escapeHtml(item.answer) +
        "</div>" +
        (item.applicability
          ? '<div class="bn in col" style="gap:4px;"><div class="eyebrow">' +
            escapeHtml(t("miniapp.knowledge.item_applicability_label")) +
            "</div><div>" +
            escapeHtml(item.applicability) +
            "</div></div>"
          : "") +
        (item.formula_expression ? '<div class="math">' + escapeHtml(item.formula_expression) + "</div>" : "") +
        (rubricHtml
          ? '<div class="col" style="gap:4px;"><div class="eyebrow">' +
            escapeHtml(t("miniapp.knowledge.item_rubric_label")) +
            "</div>" +
            rubricHtml +
            "</div>"
          : "") +
        (frag
          ? '<button type="button" class="btn b3" id="d09-open-d34-btn">' +
            escapeHtml(t("miniapp.common.source_fragment") + " (" + frag.anchor_label + ")") +
            "</button>"
          : "") +
        "</section>";

      bindLanguageButtons(vp);

      const editBtn = document.getElementById("d09-edit-btn");
      if (editBtn) {
        editBtn.addEventListener("click", function () {
          openItemEditorD09Edit(item.topic_id, item, false);
        });
      }

      const d34Btn = document.getElementById("d09-open-d34-btn");
      if (d34Btn && frag) {
        d34Btn.addEventListener("click", function () {
          openSourceFragmentSheetD34(frag);
        });
      }
    } catch (_e) {}
  }

  function openSourceFragmentSheetD34(frag) {
    openBottomSheet({
      size: "medium",
      title: t("miniapp.knowledge.d34_title"),
      bodyHtml:
        '<div class="col" style="gap:10px;">' +
        (frag.source_deleted
          ? '<div class="bn wn">' + escapeHtml(t("miniapp.knowledge.d34_deleted_banner")) + "</div>"
          : "") +
        '<div class="eyebrow">' +
        escapeHtml((frag.material_title_snapshot || "") + " · " + (frag.anchor_label || "")) +
        "</div>" +
        '<blockquote class="src">' +
        escapeHtml(frag.quote_text) +
        "</blockquote>" +
        "</div>",
    });
  }

  function openItemEditorD09Edit(topicId, existingItem, returnToD41) {
    state.returnToD41AfterItemCreate = Boolean(returnToD41);
    state.itemDraft = existingItem
      ? {
          id: existingItem.id,
          topic_id: existingItem.topic_id,
          item_type: existingItem.item_type,
          prompt: existingItem.prompt,
          answer: existingItem.answer,
          applicability: existingItem.applicability || "",
          formula_expression: existingItem.formula_expression || "",
          rubric_lines: (existingItem.rubric_criteria || []).join("\n"),
          quote_text: existingItem.source_fragment ? existingItem.source_fragment.quote_text : "",
          anchor_label: existingItem.source_fragment ? existingItem.source_fragment.anchor_label : "",
          revision: existingItem.revision,
        }
      : {
          id: null,
          topic_id: topicId,
          item_type: "concept",
          prompt: "",
          answer: "",
          applicability: "",
          formula_expression: "",
          rubric_lines: "",
          quote_text: "",
          anchor_label: "",
        };
    navigateTo("D09-Edit");
  }

  function renderD09Edit(vp) {
    const draft = state.itemDraft;
    if (!draft) {
      handleHierarchicalBack();
      return;
    }
    const isEdit = Boolean(draft.id);
    const titleStr = isEdit ? t("miniapp.knowledge.item_edit_title") : t("miniapp.knowledge.item_create_title");

    const types = ["fact", "concept", "word", "formula", "procedure", "opinion", "hypothesis"];
    const typeChips = types
      .map(function (tp) {
        return (
          '<button type="button" class="chip ' +
          (draft.item_type === tp ? "c-pr" : "") +
          '" data-item-type="' +
          tp +
          '" style="cursor:pointer;">' +
          escapeHtml(t("miniapp.knowledge.type_" + tp)) +
          "</button>"
        );
      })
      .join("");

    vp.innerHTML =
      renderTopBar(titleStr, true) +
      '<section class="card col" style="gap:12px;">' +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab">' +
      escapeHtml(t("miniapp.knowledge.item_type_label")) +
      "</label>" +
      '<div class="rw">' +
      typeChips +
      "</div>" +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d09-prompt">' +
      escapeHtml(t("miniapp.knowledge.item_prompt_label")) +
      "</label>" +
      '<textarea id="d09-prompt" class="inp ta">' +
      escapeHtml(draft.prompt) +
      "</textarea>" +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d09-answer">' +
      escapeHtml(t("miniapp.knowledge.item_answer_label")) +
      "</label>" +
      '<textarea id="d09-answer" class="inp ta">' +
      escapeHtml(draft.answer) +
      "</textarea>" +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d09-app">' +
      escapeHtml(t("miniapp.knowledge.item_applicability_label")) +
      "</label>" +
      '<input id="d09-app" class="inp" type="text" value="' +
      escapeHtml(draft.applicability) +
      '" />' +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d09-formula">' +
      escapeHtml(t("miniapp.knowledge.item_formula_label")) +
      "</label>" +
      '<input id="d09-formula" class="inp" type="text" value="' +
      escapeHtml(draft.formula_expression) +
      '" />' +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d09-rubric">' +
      escapeHtml(t("miniapp.knowledge.item_rubric_label")) +
      "</label>" +
      '<textarea id="d09-rubric" class="inp ta">' +
      escapeHtml(draft.rubric_lines) +
      "</textarea>" +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d09-quote">' +
      escapeHtml(t("miniapp.knowledge.item_quote_label")) +
      "</label>" +
      '<textarea id="d09-quote" class="inp ta">' +
      escapeHtml(draft.quote_text) +
      "</textarea>" +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d09-anchor">' +
      escapeHtml(t("miniapp.knowledge.item_anchor_label")) +
      "</label>" +
      '<input id="d09-anchor" class="inp" type="text" value="' +
      escapeHtml(draft.anchor_label) +
      '" />' +
      "</div>" +
      '<button type="button" class="btn" id="d09-save-btn">' +
      escapeHtml(t("miniapp.common.save")) +
      "</button>" +
      "</section>";

    bindLanguageButtons(vp);

    function syncFields() {
      const pEl = document.getElementById("d09-prompt");
      const aEl = document.getElementById("d09-answer");
      const apEl = document.getElementById("d09-app");
      const fEl = document.getElementById("d09-formula");
      const rEl = document.getElementById("d09-rubric");
      const qEl = document.getElementById("d09-quote");
      const anEl = document.getElementById("d09-anchor");
      if (pEl) draft.prompt = pEl.value;
      if (aEl) draft.answer = aEl.value;
      if (apEl) draft.applicability = apEl.value;
      if (fEl) draft.formula_expression = fEl.value;
      if (rEl) draft.rubric_lines = rEl.value;
      if (qEl) draft.quote_text = qEl.value;
      if (anEl) draft.anchor_label = anEl.value;
    }

    vp.querySelectorAll("[data-item-type]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        syncFields();
        draft.item_type = btn.getAttribute("data-item-type");
        renderCurrentScreen();
      });
    });

    const saveBtn = document.getElementById("d09-save-btn");
    if (saveBtn) {
      saveBtn.addEventListener("click", async function () {
        syncFields();
        if (!draft.prompt.trim() || !draft.answer.trim()) return;
        triggerHaptic("notification", "success");
        const criteria = draft.rubric_lines
          .split("\n")
          .map(function (s) {
            return s.trim();
          })
          .filter(Boolean);
        const objs = ["recall"];
        if (criteria.length > 0 || draft.item_type === "concept") objs.push("explain");
        if (draft.formula_expression.trim()) objs.push("apply");

        try {
          if (isEdit) {
            const res = await apiFetch("api/v1/items/" + encodeURIComponent(draft.id), {
              method: "PATCH",
              body: {
                item_type: draft.item_type,
                prompt: draft.prompt,
                answer: draft.answer,
                applicability: draft.applicability,
                formula_expression: draft.formula_expression,
                rubric_criteria: criteria,
                applicable_objectives: objs,
                quote_text: draft.quote_text,
                anchor_label: draft.anchor_label,
                revision: draft.revision,
              },
            });
            state.activeItemId = res.item.id;
            state.itemDraft = null;
            navigateTo("D09", { pushHistory: false });
          } else {
            const res = await apiFetch("api/v1/items", {
              method: "POST",
              body: {
                topic_id: draft.topic_id,
                item_type: draft.item_type,
                prompt: draft.prompt,
                answer: draft.answer,
                applicability: draft.applicability,
                formula_expression: draft.formula_expression,
                rubric_criteria: criteria,
                applicable_objectives: objs,
                quote_text: draft.quote_text,
                anchor_label: draft.anchor_label,
              },
            });
            const createdItem = res.item;
            state.itemDraft = null;

            // Preserve D41 draft when creating an item inline for a Meaning Group (Section 3.14 exception)
            if (state.returnToD41AfterItemCreate && state.groupDraft) {
              state.returnToD41AfterItemCreate = false;
              state.groupDraft.availableItems.unshift(createdItem);
              if (state.groupDraft.selectedIds.length < 7) {
                state.groupDraft.selectedIds.push(createdItem.id);
              }
              navigateTo("D41", { pushHistory: false });
            } else {
              state.activeItemId = createdItem.id;
              navigateTo("D09", { pushHistory: false });
            }
          }
        } catch (_e) {}
      });
    }
  }

  // ==================== D40: M5 Meaning Group View ====================
  async function renderD40(vp) {
    vp.innerHTML = renderTopBar(t("miniapp.knowledge.d40_title"), true) + '<div class="sk" style="height:140px;"></div>';
    bindLanguageButtons(vp);
    if (!state.activeGroupId) return;

    try {
      const res = await apiFetch("api/v1/groups/" + encodeURIComponent(state.activeGroupId));
      const grp = res.group;
      state.activeGroupDetail = grp;

      const itemTitleById = {};
      (grp.members || []).forEach(function (m) {
        itemTitleById[m.item_id] = m.prompt;
      });

      const membersHtml = (grp.members || [])
        .map(function (m, idx) {
          return (
            '<div class="li">' +
            '<span class="pill">' +
            (idx + 1) +
            "</span>" +
            '<div class="col grow" style="gap:2px;">' +
            '<div class="b">' +
            escapeHtml(m.prompt) +
            "</div>" +
            '<div class="sm mu">' +
            escapeHtml(m.answer) +
            "</div>" +
            "</div>" +
            '<span class="chip">' +
            escapeHtml(m.role_label) +
            "</span>" +
            "</div>"
          );
        })
        .join("");

      const relsHtml = (grp.relations || [])
        .map(function (r) {
          const fromLabel = itemTitleById[r.from_item_id] || r.from_item_id;
          const toLabel = itemTitleById[r.to_item_id] || r.to_item_id;
          const relKey = "miniapp.knowledge.rel_" + r.relation_type;
          return (
            '<div class="bn col" style="gap:4px;">' +
            '<div class="rw sm">' +
            '<span class="b">' +
            escapeHtml(fromLabel) +
            "</span>" +
            '<span class="chip c-pr">' +
            escapeHtml(t(relKey)) +
            "</span>" +
            '<span class="b">' +
            escapeHtml(toLabel) +
            "</span>" +
            "</div>" +
            (r.explanation ? '<div class="sm mu">' + escapeHtml(r.explanation) + "</div>" : "") +
            "</div>"
          );
        })
        .join("");

      vp.innerHTML =
        renderTopBar(t("miniapp.knowledge.d40_title"), true) +
        (grp.status === "needs_review"
          ? '<div class="bn wn">' + escapeHtml(t("miniapp.knowledge.d40_needs_review")) + "</div>"
          : "") +
        '<section class="card col" style="gap:10px;">' +
        '<div class="row sp">' +
        '<h1 class="h2">🕸 ' +
        escapeHtml(grp.title) +
        "</h1>" +
        '<div class="row" style="gap:6px;">' +
        '<button type="button" class="btn b2 bsm" id="d40-why-m5-btn">M5</button>' +
        '<button type="button" class="btn b2 bsm" id="d40-edit-btn">' +
        escapeHtml(t("miniapp.common.edit")) +
        "</button>" +
        "</div>" +
        "</div>" +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.knowledge.d40_principle")) +
        "</div>" +
        "<div>" +
        escapeHtml(grp.principle) +
        "</div>" +
        (grp.condition
          ? '<div class="eyebrow">' +
            escapeHtml(t("miniapp.knowledge.d40_condition")) +
            "</div><div class='sm mu'>" +
            escapeHtml(grp.condition) +
            "</div>"
          : "") +
        "</section>" +
        '<section class="col" style="gap:8px;">' +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.knowledge.d40_members", { count: (grp.members || []).length })) +
        "</div>" +
        '<div class="list">' +
        membersHtml +
        "</div>" +
        "</section>" +
        (relsHtml
          ? '<section class="col" style="gap:8px;">' +
            '<div class="eyebrow">' +
            escapeHtml(t("miniapp.knowledge.d40_relations")) +
            "</div>" +
            relsHtml +
            "</section>"
          : "");

      bindLanguageButtons(vp);

      const whyBtn = document.getElementById("d40-why-m5-btn");
      if (whyBtn) {
        whyBtn.addEventListener("click", function () {
          openScienceSheet("M5");
        });
      }

      const editBtn = document.getElementById("d40-edit-btn");
      if (editBtn) {
        editBtn.addEventListener("click", function () {
          openGroupEditorD41(grp.topic_id, grp);
        });
      }
    } catch (_e) {}
  }

  // ==================== D41: M5 Meaning Group & Relations Editor (2–7 items) ====================
  async function openGroupEditorD41(topicId, existingGroup) {
    try {
      const topDetail = await apiFetch("api/v1/topics/" + encodeURIComponent(topicId));
      const availableItems = (topDetail.items || []).filter(function (it) {
        return it.status === "active";
      });
      state.groupDraft = existingGroup
        ? {
            id: existingGroup.id,
            topic_id: topicId,
            title: existingGroup.title,
            principle: existingGroup.principle,
            condition: existingGroup.condition || "",
            selectedIds: (existingGroup.members || []).map(function (m) {
              return m.item_id;
            }),
            relations: (existingGroup.relations || []).map(function (r) {
              return {
                from_item_id: r.from_item_id,
                to_item_id: r.to_item_id,
                relation_type: r.relation_type,
                direction: r.direction || "forward",
                explanation: r.explanation || "",
              };
            }),
            availableItems: availableItems,
            revision: existingGroup.revision,
          }
        : {
            id: null,
            topic_id: topicId,
            title: "",
            principle: "",
            condition: "",
            selectedIds: availableItems.slice(0, 2).map(function (it) {
              return it.id;
            }),
            relations: [],
            availableItems: availableItems,
          };
      navigateTo("D41");
    } catch (_e) {}
  }

  function renderD41(vp) {
    const draft = state.groupDraft;
    if (!draft) {
      handleHierarchicalBack();
      return;
    }
    const isEdit = Boolean(draft.id);
    const titleStr = isEdit ? t("miniapp.knowledge.d41_edit_title") : t("miniapp.knowledge.d41_create_title");

    const itemsPickerHtml = (draft.availableItems || [])
      .map(function (it) {
        const isSel = draft.selectedIds.indexOf(it.id) !== -1;
        return (
          '<button type="button" class="opt ' +
          (isSel ? "on" : "") +
          '" data-toggle-member="' +
          escapeHtml(it.id) +
          '">' +
          '<span class="cbx ' +
          (isSel ? "on" : "") +
          '">✓</span>' +
          '<span class="grow">' +
          escapeHtml(it.prompt) +
          "</span>" +
          "</button>"
        );
      })
      .join("");

    const countValid = draft.selectedIds.length >= 2 && draft.selectedIds.length <= 7;

    vp.innerHTML =
      renderTopBar(titleStr, true) +
      '<section class="card col" style="gap:12px;">' +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d41-title">' +
      escapeHtml(t("miniapp.knowledge.d41_title_label")) +
      "</label>" +
      '<input id="d41-title" class="inp" type="text" value="' +
      escapeHtml(draft.title) +
      '" />' +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d41-principle">' +
      escapeHtml(t("miniapp.knowledge.d41_principle_label")) +
      "</label>" +
      '<textarea id="d41-principle" class="inp ta">' +
      escapeHtml(draft.principle) +
      "</textarea>" +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d41-cond">' +
      escapeHtml(t("miniapp.knowledge.d41_condition_label")) +
      "</label>" +
      '<input id="d41-cond" class="inp" type="text" value="' +
      escapeHtml(draft.condition) +
      '" />' +
      "</div>" +
      '<div class="col" style="gap:8px;">' +
      '<div class="row sp">' +
      '<span class="lab">' +
      escapeHtml(t("miniapp.knowledge.d41_select_members")) +
      "</span>" +
      '<span class="chip ' +
      (countValid ? "c-ok" : "c-er") +
      '">' +
      draft.selectedIds.length +
      " / 2–7</span>" +
      "</div>" +
      itemsPickerHtml +
      '<button type="button" class="btn b2 bsm" id="d41-inline-item-btn">' +
      escapeHtml(t("miniapp.knowledge.d41_create_inline_item")) +
      "</button>" +
      "</div>" +
      '<button type="button" class="btn ' +
      (countValid ? "" : "bdis") +
      '" id="d41-save-btn">' +
      escapeHtml(t("miniapp.common.save")) +
      "</button>" +
      "</section>";

    bindLanguageButtons(vp);

    function syncGroupDraftInputs() {
      const tEl = document.getElementById("d41-title");
      const pEl = document.getElementById("d41-principle");
      const cEl = document.getElementById("d41-cond");
      if (tEl) draft.title = tEl.value;
      if (pEl) draft.principle = pEl.value;
      if (cEl) draft.condition = cEl.value;
    }

    vp.querySelectorAll("[data-toggle-member]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        syncGroupDraftInputs();
        const iid = btn.getAttribute("data-toggle-member");
        const pos = draft.selectedIds.indexOf(iid);
        if (pos !== -1) {
          draft.selectedIds.splice(pos, 1);
        } else if (draft.selectedIds.length < 7) {
          draft.selectedIds.push(iid);
        }
        renderCurrentScreen();
      });
    });

    const inlineItemBtn = document.getElementById("d41-inline-item-btn");
    if (inlineItemBtn) {
      inlineItemBtn.addEventListener("click", function () {
        syncGroupDraftInputs();
        openItemEditorD09Edit(draft.topic_id, null, true);
      });
    }

    const saveBtn = document.getElementById("d41-save-btn");
    if (saveBtn) {
      saveBtn.addEventListener("click", async function () {
        syncGroupDraftInputs();
        if (!countValid || !draft.title.trim() || !draft.principle.trim()) return;
        triggerHaptic("notification", "success");

        const membersPayload = draft.selectedIds.map(function (iid, idx) {
          return {
            item_id: iid,
            role_label: idx === 0 ? "basis" : "consequence",
            explanation: "",
          };
        });
        const relationsPayload =
          draft.selectedIds.length >= 2
            ? [
                {
                  from_item_id: draft.selectedIds[0],
                  to_item_id: draft.selectedIds[1],
                  relation_type: "consequence",
                  direction: "forward",
                  explanation: draft.principle,
                },
              ]
            : [];

        try {
          if (isEdit) {
            const res = await apiFetch("api/v1/groups/" + encodeURIComponent(draft.id), {
              method: "PUT",
              body: {
                title: draft.title,
                principle: draft.principle,
                condition: draft.condition,
                members: membersPayload,
                relations: relationsPayload,
                revision: draft.revision,
              },
            });
            state.activeGroupId = res.group.id;
          } else {
            const res = await apiFetch("api/v1/groups", {
              method: "POST",
              body: {
                topic_id: draft.topic_id,
                title: draft.title,
                principle: draft.principle,
                condition: draft.condition,
                members: membersPayload,
                relations: relationsPayload,
              },
            });
            state.activeGroupId = res.group.id;
          }
          state.groupDraft = null;
          navigateTo("D40", { pushHistory: false });
        } catch (_e) {}
      });
    }
  }

  // ==================== D10: Study Session Setup & Method Intro Prompt ====================
  async function renderD10(vp) {
    vp.innerHTML =
      renderTopBar(t("miniapp.study.d10_title"), true) +
      '<section class="card col" style="gap:14px;">' +
      '<h1 class="h2">' +
      escapeHtml(t("miniapp.study.d10_title")) +
      "</h1>" +
      '<div class="col" style="gap:8px;">' +
      renderModeOpt("regular", t("miniapp.study.d10_mode_regular"), state.sessionSetupMode === "regular") +
      renderModeOpt("targeted_mix", t("miniapp.study.d10_mode_mix"), state.sessionSetupMode === "targeted_mix") +
      renderModeOpt("intro", t("miniapp.study.d10_mode_intro"), state.sessionSetupMode === "intro") +
      "</div>" +
      '<button type="button" class="btn b2" id="d10-open-d42-btn">' +
      escapeHtml(t("miniapp.common.why_this_exercise")) +
      "</button>" +
      '<button type="button" class="btn" id="d10-launch-btn">' +
      escapeHtml(t("miniapp.d03.start_session_cta")) +
      "</button>" +
      "</section>";

    bindLanguageButtons(vp);

    vp.querySelectorAll("[data-sess-mode]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.sessionSetupMode = btn.getAttribute("data-sess-mode");
        renderCurrentScreen();
      });
    });

    const d42Btn = document.getElementById("d10-open-d42-btn");
    if (d42Btn) {
      d42Btn.addEventListener("click", function () {
        openScienceSheet("M1");
      });
    }

    const launchBtn = document.getElementById("d10-launch-btn");
    if (launchBtn) {
      launchBtn.addEventListener("click", async function () {
        triggerHaptic("impact", "light");
        try {
          const res = await apiFetch("api/v1/sessions", {
            method: "POST",
            body: {
              mode: state.sessionSetupMode,
              topic_id: state.sessionTopicFilter,
              group_id: state.sessionGroupFilter,
              max_units: 10,
            },
          });
          state.activeStudySession = res.session;
          state.studyFormulaRevealed = false;
          if (!state.activeStudySession || state.activeStudySession.total_units === 0) {
            vp.insertAdjacentHTML(
              "beforeend",
              '<div class="bn wn">' + escapeHtml(t("miniapp.study.d10_empty_queue")) + "</div>"
            );
            return;
          }
          navigateTo("D11", { pushHistory: false });
        } catch (_e) {}
      });
    }
  }

  function renderModeOpt(modeCode, label, active) {
    return (
      '<button type="button" class="opt ' +
      (active ? "on" : "") +
      '" data-sess-mode="' +
      escapeHtml(modeCode) +
      '">' +
      '<span class="rad"></span><span class="grow">' +
      escapeHtml(label) +
      "</span></button>"
    );
  }

  // ==================== D11: Active Exercise Screen (M1/M3/M4/M5 + Science Link + Draft Persistence) ====================
  function renderD11(vp) {
    const sess = state.activeStudySession;
    if (!sess || !sess.current_unit) {
      navigateTo("D13", { pushHistory: false });
      return;
    }

    const unit = sess.current_unit;
    const objKey = "miniapp.study.d11_obj_" + (unit.objective || "recall");
    const primaryMethodId = (unit.science_method_ids && unit.science_method_ids[0]) || "M1";

    // Formula is ONLY shown if allowed_support includes "formula", objective != "discriminate", and user clicks reveal
    const canShowFormula =
      unit.objective !== "discriminate" &&
      unit.formula_support_text &&
      (unit.allowed_support || []).indexOf("formula") !== -1;

    const introBannerHtml = sess.recommended_intro_method
      ? '<div class="bn ai row sp" style="align-items:center;">' +
        '<span class="sm">' +
        escapeHtml(t("miniapp.study.d10_method_intro_banner", { method: sess.recommended_intro_method })) +
        "</span>" +
        '<button type="button" class="btn b2 bsm" id="d11-intro-open-btn">' +
        escapeHtml(t("miniapp.common.why_this_exercise")) +
        "</button>" +
        "</div>"
      : "";

    const fallbackHtml = sess.fallback_reason
      ? '<div class="bn in sm">' + escapeHtml(t("miniapp.study.d10_fallback_notice")) + "</div>"
      : "";

    vp.innerHTML =
      renderTopBar(
        t("miniapp.study.d11_progress", { current: sess.current_index + 1, total: sess.total_units }),
        true
      ) +
      introBannerHtml +
      fallbackHtml +
      '<section class="card col" style="gap:12px;">' +
      '<div class="row sp">' +
      '<span class="chip c-pr">' +
      escapeHtml(t(objKey)) +
      "</span>" +
      '<button type="button" class="btn b3 bsm" id="d11-science-link-btn" style="width:auto; padding:4px 8px;">' +
      escapeHtml(t("miniapp.common.why_this_exercise")) +
      "</button>" +
      "</div>" +
      '<h1 class="h2">' +
      escapeHtml(unit.prompt) +
      "</h1>" +
      (canShowFormula
        ? state.studyFormulaRevealed
          ? '<div class="math">' + escapeHtml(unit.formula_support_text) + "</div>"
          : '<button type="button" class="btn b2 bsm" id="d11-reveal-formula-btn">' +
            escapeHtml(t("miniapp.study.d11_show_formula_btn")) +
            "</button>"
        : "") +
      '<div class="seg">' +
      '<button type="button" class="' +
      (state.studyAnswerMode === "written" ? "on" : "") +
      '" data-ans-mode="written">' +
      escapeHtml(t("miniapp.study.d11_mode_written")) +
      "</button>" +
      '<button type="button" class="' +
      (state.studyAnswerMode === "aloud" ? "on" : "") +
      '" data-ans-mode="aloud">' +
      escapeHtml(t("miniapp.study.d11_mode_aloud")) +
      "</button>" +
      "</div>" +
      (state.studyAnswerMode === "written"
        ? '<textarea id="d11-answer-input" class="inp ta" placeholder="' +
          escapeHtml(t("miniapp.study.d11_answer_placeholder")) +
          '">' +
          escapeHtml(sess.draft_answer || "") +
          "</textarea>"
        : "") +
      (unit.fragment_id
        ? '<button type="button" class="btn b3 bsm" id="d11-source-btn">' +
          escapeHtml(t("miniapp.study.d11_show_source_btn")) +
          "</button>"
        : "") +
      '<div class="col" style="gap:8px; margin-top:4px;">' +
      '<button type="button" class="btn" id="d11-check-btn">' +
      escapeHtml(t("miniapp.study.d11_reveal_answer_btn")) +
      "</button>" +
      '<button type="button" class="btn b2" id="d11-dont-know-btn">' +
      escapeHtml(t("miniapp.study.d11_dont_know_btn")) +
      "</button>" +
      "</div>" +
      "</section>";

    bindLanguageButtons(vp);

    const ansInput = document.getElementById("d11-answer-input");
    if (ansInput) {
      ansInput.addEventListener("input", function () {
        sess.draft_answer = ansInput.value;
        apiFetch("api/v1/sessions/" + encodeURIComponent(sess.id) + "/draft", {
          method: "PATCH",
          body: { draft_answer: ansInput.value, support_seen: sess.draft_support_seen || [] },
        }).catch(function () {});
      });
    }

    vp.querySelectorAll("[data-ans-mode]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.studyAnswerMode = btn.getAttribute("data-ans-mode");
        renderCurrentScreen();
      });
    });

    const revFormulaBtn = document.getElementById("d11-reveal-formula-btn");
    if (revFormulaBtn) {
      revFormulaBtn.addEventListener("click", function () {
        state.studyFormulaRevealed = true;
        renderCurrentScreen();
      });
    }

    const sciBtn = document.getElementById("d11-science-link-btn");
    if (sciBtn) {
      sciBtn.addEventListener("click", function () {
        openScienceSheet(primaryMethodId);
      });
    }

    const introOpenBtn = document.getElementById("d11-intro-open-btn");
    if (introOpenBtn) {
      introOpenBtn.addEventListener("click", function () {
        openScienceSheet(sess.recommended_intro_method || primaryMethodId);
      });
    }

    const srcBtn = document.getElementById("d11-source-btn");
    if (srcBtn && unit.fragment_id) {
      srcBtn.addEventListener("click", async function () {
        sess.draft_support_seen = (sess.draft_support_seen || []).concat(["source"]);
        try {
          await apiFetch("api/v1/sessions/" + encodeURIComponent(sess.id) + "/draft", {
            method: "PATCH",
            body: { draft_answer: sess.draft_answer || "", support_seen: ["source"] },
          });
          const fRes = await apiFetch("api/v1/fragments/" + encodeURIComponent(unit.fragment_id));
          if (fRes.fragment) openSourceFragmentSheetD34(fRes.fragment);
        } catch (_e) {}
      });
    }

    const checkBtn = document.getElementById("d11-check-btn");
    if (checkBtn) {
      checkBtn.addEventListener("click", function () {
        triggerHaptic("impact", "light");
        state.studyCheckedCriteria = (unit.rubric_criteria || []).map(function (_c, idx) {
          return idx;
        });
        state.lastAttemptResult = null;
        state.lastNeedsCorrective = false;
        navigateTo("D12");
      });
    }

    const dkBtn = document.getElementById("d11-dont-know-btn");
    if (dkBtn) {
      dkBtn.addEventListener("click", async function () {
        triggerHaptic("notification", "warning");
        await submitAttemptAndTransition("dont_know", []);
      });
    }
  }

  // ==================== D12: Rubric Feedback, Gap Card & Corrective Retry ====================
  function renderD12(vp) {
    const sess = state.activeStudySession;
    if (!sess || !sess.current_unit) {
      navigateTo("D13", { pushHistory: false });
      return;
    }
    const unit = sess.current_unit;
    const criteria = unit.rubric_criteria || [];

    if (state.lastNeedsCorrective && state.lastAttemptResult) {
      const gapText = state.lastAttemptResult.gap_summary || unit.reference_answer;
      vp.innerHTML =
        renderTopBar(t("miniapp.study.d12_gap_title"), true) +
        '<section class="card col" style="gap:12px;">' +
        '<div class="bn wn col" style="gap:4px;">' +
        '<div class="b">' +
        escapeHtml(t("miniapp.study.d12_gap_title")) +
        "</div>" +
        '<div class="sm">' +
        escapeHtml(t("miniapp.study.d12_gap_desc", { gap: gapText })) +
        "</div>" +
        "</div>" +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.study.d12_reference_label")) +
        "</div>" +
        '<blockquote class="src">' +
        escapeHtml(unit.reference_answer) +
        "</blockquote>" +
        '<textarea id="d12-retry-input" class="inp ta" placeholder="' +
        escapeHtml(t("miniapp.study.d12_retry_placeholder")) +
        '"></textarea>' +
        '<div class="col" style="gap:8px;">' +
        '<button type="button" class="btn" id="d12-submit-retry-btn">' +
        escapeHtml(t("miniapp.study.d12_submit_retry_btn")) +
        "</button>" +
        '<button type="button" class="btn b2" id="d12-skip-retry-btn">' +
        escapeHtml(t("miniapp.study.d12_skip_retry_btn")) +
        "</button>" +
        "</div>" +
        "</section>";

      bindLanguageButtons(vp);

      const retryBtn = document.getElementById("d12-submit-retry-btn");
      if (retryBtn) {
        retryBtn.addEventListener("click", async function () {
          const inp = document.getElementById("d12-retry-input");
          const val = inp ? inp.value : "";
          triggerHaptic("notification", "success");
          try {
            const res = await apiFetch("api/v1/sessions/" + encodeURIComponent(sess.id) + "/attempts", {
              method: "POST",
              body: {
                exercise_id: unit.exercise_id,
                phase: "corrective",
                answer_text: val,
                answer_mode: "written",
                grading_mode: "self_check",
                self_grade: "correct",
              },
            });
            state.activeStudySession = res.session;
            state.lastNeedsCorrective = false;
            state.lastAttemptResult = null;
            if (state.activeStudySession.status === "completed") {
              navigateTo("D13", { pushHistory: false });
            } else {
              navigateTo("D11", { pushHistory: false });
            }
          } catch (_e) {}
        });
      }

      const skipBtn = document.getElementById("d12-skip-retry-btn");
      if (skipBtn) {
        skipBtn.addEventListener("click", async function () {
          try {
            const res = await apiFetch("api/v1/sessions/" + encodeURIComponent(sess.id) + "/advance", {
              method: "POST",
            });
            state.activeStudySession = res.session;
            state.lastNeedsCorrective = false;
            state.lastAttemptResult = null;
            if (state.activeStudySession.status === "completed") {
              navigateTo("D13", { pushHistory: false });
            } else {
              navigateTo("D11", { pushHistory: false });
            }
          } catch (_e) {}
        });
      }
      return;
    }

    const criteriaHtml = criteria
      .map(function (cText, idx) {
        const checked = state.studyCheckedCriteria.indexOf(idx) !== -1;
        return (
          '<button type="button" class="opt ' +
          (checked ? "on" : "") +
          '" data-crit-idx="' +
          idx +
          '">' +
          '<span class="cbx ' +
          (checked ? "on" : "") +
          '">✓</span>' +
          '<span class="grow">' +
          escapeHtml(cText) +
          "</span>" +
          "</button>"
        );
      })
      .join("");

    vp.innerHTML =
      renderTopBar(t("miniapp.study.d12_reference_label"), true) +
      '<section class="card col" style="gap:12px;">' +
      '<div class="eyebrow">' +
      escapeHtml(t("miniapp.study.d12_reference_label")) +
      "</div>" +
      '<div class="b">' +
      escapeHtml(unit.reference_answer) +
      "</div>" +
      (unit.explanation ? '<div class="sm mu">' + escapeHtml(unit.explanation) + "</div>" : "") +
      (criteriaHtml
        ? '<div class="col" style="gap:8px;"><div class="eyebrow">' +
          escapeHtml(t("miniapp.study.d12_rubric_label")) +
          "</div>" +
          criteriaHtml +
          "</div>"
        : "") +
      '<div class="col" style="gap:8px; margin-top:4px;">' +
      '<button type="button" class="btn" data-self-grade="correct">' +
      escapeHtml(t("miniapp.study.d12_self_correct")) +
      "</button>" +
      '<button type="button" class="btn b2" data-self-grade="partial">' +
      escapeHtml(t("miniapp.study.d12_self_partial")) +
      "</button>" +
      '<button type="button" class="btn bd" data-self-grade="wrong">' +
      escapeHtml(t("miniapp.study.d12_self_wrong")) +
      "</button>" +
      "</div>" +
      "</section>";

    bindLanguageButtons(vp);

    vp.querySelectorAll("[data-crit-idx]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const cIdx = parseInt(btn.getAttribute("data-crit-idx"), 10);
        const pos = state.studyCheckedCriteria.indexOf(cIdx);
        if (pos !== -1) {
          state.studyCheckedCriteria.splice(pos, 1);
        } else {
          state.studyCheckedCriteria.push(cIdx);
        }
        renderCurrentScreen();
      });
    });

    vp.querySelectorAll("[data-self-grade]").forEach(function (gBtn) {
      gBtn.addEventListener("click", async function () {
        const gVal = gBtn.getAttribute("data-self-grade");
        triggerHaptic("notification", gVal === "correct" ? "success" : "warning");
        const checkedIndices =
          gVal === "correct"
            ? criteria.map(function (_c, idx) {
                return idx;
              })
            : gVal === "wrong"
            ? []
            : state.studyCheckedCriteria.slice(0, Math.max(0, criteria.length - 1));
        await submitAttemptAndTransition(gVal, checkedIndices);
      });
    });
  }

  async function submitAttemptAndTransition(selfGrade, checkedIndices) {
    const sess = state.activeStudySession;
    if (!sess || !sess.current_unit) return;
    const unit = sess.current_unit;

    try {
      const res = await apiFetch("api/v1/sessions/" + encodeURIComponent(sess.id) + "/attempts", {
        method: "POST",
        body: {
          exercise_id: unit.exercise_id,
          phase: "first_attempt",
          answer_text: sess.draft_answer || "",
          answer_mode: state.studyAnswerMode,
          grading_mode: "self_check",
          self_grade: selfGrade,
          rubric_checked_indices: checkedIndices,
          source_seen: (sess.draft_support_seen || []).indexOf("source") !== -1,
        },
      });
      state.activeStudySession = res.session;
      state.lastAttemptResult = res.attempt;
      state.lastNeedsCorrective = Boolean(res.needs_corrective);
      state.studyFormulaRevealed = false;

      if (state.lastNeedsCorrective) {
        navigateTo("D12", { pushHistory: false });
      } else if (state.activeStudySession.status === "completed") {
        navigateTo("D13", { pushHistory: false });
      } else {
        navigateTo("D11", { pushHistory: false });
      }
    } catch (_e) {}
  }

  // ==================== D13: Study Session Summary ====================
  function renderD13(vp) {
    const sess = state.activeStudySession;
    const sum = (sess && sess.summary) || {
      independent_ok: 0,
      assisted_ok: 0,
      needs_repeat: 0,
    };

    vp.innerHTML =
      renderTopBar(t("miniapp.study.d13_title"), false) +
      '<section class="card cardp col" style="gap:14px; text-align:center; padding:26px 20px;">' +
      '<h1 class="h1">' +
      escapeHtml(t("miniapp.study.d13_title")) +
      "</h1>" +
      '<p class="mu">' +
      escapeHtml(t("miniapp.study.d13_subtitle")) +
      "</p>" +
      '<div class="col" style="gap:10px; text-align:left;">' +
      '<div class="bn ok row sp"><span>' +
      escapeHtml(t("miniapp.study.d13_stat_independent")) +
      '</span><span class="b">' +
      sum.independent_ok +
      "</span></div>" +
      '<div class="bn in row sp"><span>' +
      escapeHtml(t("miniapp.study.d13_stat_assisted")) +
      '</span><span class="b">' +
      sum.assisted_ok +
      "</span></div>" +
      '<div class="bn row sp"><span>' +
      escapeHtml(t("miniapp.study.d13_stat_repeat")) +
      '</span><span class="b">' +
      sum.needs_repeat +
      "</span></div>" +
      "</div>" +
      '<button type="button" class="btn" id="d13-finish-btn">' +
      escapeHtml(t("miniapp.study.d13_finish_cta")) +
      "</button>" +
      "</section>";

    bindLanguageButtons(vp);

    const finBtn = document.getElementById("d13-finish-btn");
    if (finBtn) {
      finBtn.addEventListener("click", function () {
        state.historyStack = [];
        navigateTo("D03", { pushHistory: false });
      });
    }
  }

  // ==================== D19–D23: Atomic Habits List, Wizard, Detail, Check-In & AI Draft ====================
  async function renderD19(vp) {
    vp.innerHTML =
      renderTopBar(t("miniapp.habits.d19_title"), false) +
      '<div class="sk" style="height:120px; border-radius:24px;"></div>';
    bindLanguageButtons(vp);

    try {
      const res = await apiFetch("api/v1/habits");
      state.habitsList = res.habits || [];
      state.habitsLimit = res.active_limit || 3;

      const quotaChip = t("miniapp.habits.d19_quota", {
        used: res.active_count || 0,
        limit: state.habitsLimit,
      });

      const listHtml = state.habitsList.length
        ? '<div class="list">' +
          state.habitsList
            .map(function (h) {
              return (
                '<button type="button" class="li" data-open-habit="' +
                escapeHtml(h.id) +
                '" style="width:100%; background:none; border:0; border-top:1px solid var(--ln); text-align:left; cursor:pointer; font-family:inherit;">' +
                '<div class="col grow" style="gap:2px;">' +
                '<div class="b">' +
                escapeHtml(h.title) +
                "</div>" +
                '<div class="sm mu">2m: ' +
                escapeHtml(h.minimum_version) +
                "</div>" +
                "</div>" +
                '<span class="stk">' +
                h.current_streak +
                "</span>" +
                "</button>"
              );
            })
            .join("") +
          "</div>"
        : '<div class="card col" style="text-align:center; padding:26px 18px;"><p class="mu">' +
          escapeHtml(t("miniapp.habits.d19_empty")) +
          "</p></div>";

      vp.innerHTML =
        renderTopBar(t("miniapp.habits.d19_title"), false) +
        '<div class="row sp">' +
        '<span class="chip">' +
        escapeHtml(quotaChip) +
        "</span>" +
        '<button type="button" class="btn bsm" id="d19-new-habit-btn">' +
        escapeHtml(t("miniapp.habits.d19_add_btn")) +
        "</button>" +
        "</div>" +
        listHtml;

      bindLanguageButtons(vp);

      const newBtn = document.getElementById("d19-new-habit-btn");
      if (newBtn) {
        newBtn.addEventListener("click", function () {
          openHabitWizardD20(null);
        });
      }

      vp.querySelectorAll("[data-open-habit]").forEach(function (el) {
        el.addEventListener("click", function () {
          state.activeHabitId = el.getAttribute("data-open-habit");
          navigateTo("D21");
        });
      });
    } catch (_e) {}
  }

  function openHabitWizardD20(existingHabit) {
    state.habitDraft = existingHabit
      ? {
          id: existingHabit.id,
          habit_kind: existingHabit.habit_kind || "build",
          title: existingHabit.title,
          signal: existingHabit.signal,
          action: existingHabit.action,
          minimum_version: existingHabit.minimum_version,
          environment_prep: existingHabit.environment_prep || "",
        }
      : {
          id: null,
          habit_kind: "build",
          title: "",
          signal: "",
          action: "",
          minimum_version: "",
          environment_prep: "",
        };
    navigateTo("D20");
  }

  function renderD20(vp) {
    const draft = state.habitDraft;
    if (!draft) {
      handleHierarchicalBack();
      return;
    }
    const isEdit = Boolean(draft.id);
    const titleStr = isEdit ? t("miniapp.habits.d20_edit_title") : t("miniapp.habits.d20_create_title");

    vp.innerHTML =
      renderTopBar(titleStr, true) +
      '<section class="card col" style="gap:12px;">' +
      '<div class="seg">' +
      '<button type="button" class="' +
      (draft.habit_kind === "build" ? "on" : "") +
      '" data-h-kind="build">' +
      escapeHtml(t("miniapp.habits.d20_kind_build")) +
      "</button>" +
      '<button type="button" class="' +
      (draft.habit_kind === "replace" ? "on" : "") +
      '" data-h-kind="replace">' +
      escapeHtml(t("miniapp.habits.d20_kind_replace")) +
      "</button>" +
      "</div>" +
      '<button type="button" class="btn b2 bsm" id="d20-open-d23-btn">' +
      escapeHtml(t("miniapp.habits.d20_ai_draft_btn")) +
      "</button>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d20-title">' +
      escapeHtml(t("miniapp.habits.d20_title_label")) +
      "</label>" +
      '<input id="d20-title" class="inp" type="text" value="' +
      escapeHtml(draft.title) +
      '" />' +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d20-signal">' +
      escapeHtml(t("miniapp.habits.d20_signal_label")) +
      "</label>" +
      '<input id="d20-signal" class="inp" type="text" value="' +
      escapeHtml(draft.signal) +
      '" />' +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d20-action">' +
      escapeHtml(t("miniapp.habits.d20_action_label")) +
      "</label>" +
      '<input id="d20-action" class="inp" type="text" value="' +
      escapeHtml(draft.action) +
      '" />' +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d20-min">' +
      escapeHtml(t("miniapp.habits.d20_min_label")) +
      "</label>" +
      '<input id="d20-min" class="inp" type="text" value="' +
      escapeHtml(draft.minimum_version) +
      '" />' +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d20-env">' +
      escapeHtml(t("miniapp.habits.d20_env_label")) +
      "</label>" +
      '<textarea id="d20-env" class="inp ta">' +
      escapeHtml(draft.environment_prep) +
      "</textarea>" +
      "</div>" +
      '<button type="button" class="btn" id="d20-save-btn">' +
      escapeHtml(t("miniapp.common.save")) +
      "</button>" +
      "</section>";

    bindLanguageButtons(vp);

    function syncHabitInputs() {
      const ti = document.getElementById("d20-title");
      const si = document.getElementById("d20-signal");
      const ac = document.getElementById("d20-action");
      const mi = document.getElementById("d20-min");
      const en = document.getElementById("d20-env");
      if (ti) draft.title = ti.value;
      if (si) draft.signal = si.value;
      if (ac) draft.action = ac.value;
      if (mi) draft.minimum_version = mi.value;
      if (en) draft.environment_prep = en.value;
    }

    vp.querySelectorAll("[data-h-kind]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        syncHabitInputs();
        draft.habit_kind = btn.getAttribute("data-h-kind");
        renderCurrentScreen();
      });
    });

    const d23Btn = document.getElementById("d20-open-d23-btn");
    if (d23Btn) {
      d23Btn.addEventListener("click", function () {
        syncHabitInputs();
        openHabitAiSheetD23();
      });
    }

    const saveBtn = document.getElementById("d20-save-btn");
    if (saveBtn) {
      saveBtn.addEventListener("click", async function () {
        syncHabitInputs();
        if (!draft.title.trim() || !draft.signal.trim() || !draft.action.trim() || !draft.minimum_version.trim()) return;
        triggerHaptic("notification", "success");
        try {
          if (isEdit) {
            const res = await apiFetch("api/v1/habits/" + encodeURIComponent(draft.id), {
              method: "PATCH",
              body: draft,
            });
            state.activeHabitId = res.habit.id;
          } else {
            const res = await apiFetch("api/v1/habits", {
              method: "POST",
              body: draft,
            });
            state.activeHabitId = res.habit.id;
          }
          state.habitDraft = null;
          navigateTo("D21", { pushHistory: false });
        } catch (_e) {}
      });
    }
  }

  function openHabitAiSheetD23() {
    openBottomSheet({
      size: "medium",
      title: t("miniapp.habits.d23_sheet_title"),
      bodyHtml:
        '<div class="col" style="gap:10px;">' +
        '<textarea id="d23-goal-inp" class="inp ta" placeholder="' +
        escapeHtml(t("miniapp.habits.d23_prompt_placeholder")) +
        '"></textarea>' +
        '<button type="button" class="btn" id="d23-gen-btn">' +
        escapeHtml(t("miniapp.habits.d23_apply_btn")) +
        "</button>" +
        "</div>",
    });

    const genBtn = document.getElementById("d23-gen-btn");
    if (genBtn) {
      genBtn.addEventListener("click", async function () {
        const inp = document.getElementById("d23-goal-inp");
        const goal = inp ? inp.value.trim() : "";
        if (goal.length < 3) return;
        try {
          const res = await apiFetch("api/v1/habits/ai-draft", {
            method: "POST",
            body: {
              goal_description: goal,
              habit_kind: (state.habitDraft && state.habitDraft.habit_kind) || "build",
            },
          });
          if (res.draft && state.habitDraft) {
            state.habitDraft.title = res.draft.title;
            state.habitDraft.signal = res.draft.signal;
            state.habitDraft.action = res.draft.action;
            state.habitDraft.minimum_version = res.draft.minimum_version;
            state.habitDraft.environment_prep = res.draft.environment_prep;
          }
          closeBottomSheet();
          renderCurrentScreen();
        } catch (_e) {}
      });
    }
  }

  async function renderD21(vp) {
    vp.innerHTML = renderTopBar(t("miniapp.habits.d21_title"), true) + '<div class="sk" style="height:140px;"></div>';
    bindLanguageButtons(vp);
    if (!state.activeHabitId) return;

    try {
      const res = await apiFetch("api/v1/habits/" + encodeURIComponent(state.activeHabitId));
      const h = res.habit;
      state.activeHabitDetail = h;

      vp.innerHTML =
        renderTopBar(t("miniapp.habits.d21_title"), true) +
        '<section class="card col" style="gap:12px;">' +
        '<div class="row sp">' +
        '<span class="stk">' +
        escapeHtml(t("miniapp.habits.d21_streak_label", { cur: h.current_streak, best: h.best_streak })) +
        "</span>" +
        '<button type="button" class="btn b2 bsm" id="d21-edit-btn">' +
        escapeHtml(t("miniapp.common.edit")) +
        "</button>" +
        "</div>" +
        '<h1 class="h2">' +
        escapeHtml(h.title) +
        "</h1>" +
        '<div class="bn col" style="gap:4px;">' +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.habits.d20_signal_label")) +
        "</div><div>" +
        escapeHtml(h.signal) +
        "</div></div>" +
        '<div class="bn ok col" style="gap:4px;">' +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.habits.d20_min_label")) +
        "</div><div>" +
        escapeHtml(h.minimum_version) +
        "</div></div>" +
        '<button type="button" class="btn" id="d21-mark-btn">' +
        escapeHtml(t("miniapp.habits.d21_mark_today_btn")) +
        "</button>" +
        "</section>";

      bindLanguageButtons(vp);

      const editBtn = document.getElementById("d21-edit-btn");
      if (editBtn) {
        editBtn.addEventListener("click", function () {
          openHabitWizardD20(h);
        });
      }

      const markBtn = document.getElementById("d21-mark-btn");
      if (markBtn) {
        markBtn.addEventListener("click", function () {
          openHabitMarkSheetD22(h);
        });
      }
    } catch (_e) {}
  }

  function openHabitMarkSheetD22(habit) {
    openBottomSheet({
      size: "medium",
      title: habit.title,
      bodyHtml:
        '<div class="col" style="gap:10px;">' +
        '<button type="button" class="btn" data-h-outcome="full_done">' +
        escapeHtml(t("miniapp.habits.d22_full_done")) +
        "</button>" +
        '<button type="button" class="btn b2" data-h-outcome="minimum_done">' +
        escapeHtml(t("miniapp.habits.d22_min_done")) +
        "</button>" +
        '<button type="button" class="btn b2" data-h-outcome="no_opportunity">' +
        escapeHtml(t("miniapp.habits.d22_no_opp")) +
        "</button>" +
        '<button type="button" class="btn bd" data-h-outcome="skipped">' +
        escapeHtml(t("miniapp.habits.d22_skipped")) +
        "</button>" +
        "</div>",
    });

    const bodyEl = document.getElementById("sheet-body");
    if (bodyEl) {
      bodyEl.querySelectorAll("[data-h-outcome]").forEach(function (btn) {
        btn.addEventListener("click", async function () {
          const outcome = btn.getAttribute("data-h-outcome");
          triggerHaptic("notification", outcome === "skipped" ? "warning" : "success");
          try {
            await apiFetch("api/v1/habits/" + encodeURIComponent(habit.id) + "/checkin", {
              method: "POST",
              body: { outcome: outcome },
            });
            closeBottomSheet();
            renderCurrentScreen();
          } catch (_e) {}
        });
      });
    }
  }

  // ==================== D36–D39: Streaks, Achievements, Celebration & Freeze Protection ====================
  function openCelebrationSheetD38(cel) {
    openBottomSheet({
      size: "small",
      title: t("miniapp.habits.d38_title", { days: cel.highest_threshold || 1 }),
      bodyHtml:
        '<div class="col" style="gap:12px; text-align:center;">' +
        (cel.free_freeze_granted
          ? '<div class="bn ok b">' + escapeHtml(t("miniapp.habits.d38_freeze_bonus")) + "</div>"
          : "") +
        '<button type="button" class="btn" id="d38-ack-btn">' +
        escapeHtml(t("miniapp.common.continue")) +
        "</button>" +
        "</div>",
    });
    const ackBtn = document.getElementById("d38-ack-btn");
    if (ackBtn) {
      ackBtn.addEventListener("click", async function () {
        await apiFetch("api/v1/celebrations/" + encodeURIComponent(cel.id) + "/ack", { method: "POST" }).catch(
          function () {}
        );
        closeBottomSheet();
      });
    }
  }

  async function renderD36(vp) {
    vp.innerHTML = renderTopBar(t("miniapp.habits.d36_title"), true) + '<div class="sk" style="height:140px;"></div>';
    bindLanguageButtons(vp);

    try {
      const st = await apiFetch("api/v1/streaks");
      state.streaksData = st;
      const badgesHtml = (st.badges || [])
        .map(function (b) {
          return (
            '<span class="chip ' +
            (b.unlocked ? "c-em" : "") +
            '">' +
            (b.unlocked ? "🔥 " : "🔒 ") +
            b.threshold +
            "d</span>"
          );
        })
        .join("");

      vp.innerHTML =
        renderTopBar(t("miniapp.habits.d36_title"), true) +
        '<section class="streak">' +
        '<div class="stk-top">' +
        '<span class="stk-n">' +
        st.current_streak +
        "</span>" +
        '<div class="stk-u">' +
        escapeHtml(t("miniapp.habits.d36_best_streak", { best: st.best_streak })) +
        "<span>" +
        escapeHtml(t("miniapp.habits.d36_earned_total", { total: st.earned_total })) +
        "</span></div>" +
        "</div>" +
        '<button type="button" class="btn b2" id="d36-open-d39-btn">' +
        escapeHtml(t("miniapp.habits.d36_open_freeze_btn")) +
        "</button>" +
        "</section>" +
        '<section class="card col" style="gap:10px;">' +
        '<h2 class="h3">' +
        escapeHtml(t("miniapp.habits.d36_badges_title")) +
        "</h2>" +
        '<div class="rw">' +
        badgesHtml +
        "</div>" +
        "</section>";

      bindLanguageButtons(vp);

      const d39Btn = document.getElementById("d36-open-d39-btn");
      if (d39Btn) {
        d39Btn.addEventListener("click", function () {
          navigateTo("D39");
        });
      }
    } catch (_e) {}
  }

  async function renderD39(vp) {
    vp.innerHTML = renderTopBar(t("miniapp.habits.d39_title"), true) + '<div class="sk" style="height:140px;"></div>';
    bindLanguageButtons(vp);

    try {
      const st = await apiFetch("api/v1/streaks");
      const fr = st.freeze;

      vp.innerHTML =
        renderTopBar(t("miniapp.habits.d39_title"), true) +
        '<section class="card col" style="gap:12px;">' +
        '<h1 class="h2">❄️ ' +
        escapeHtml(t("miniapp.habits.d39_title")) +
        "</h1>" +
        '<div class="bn ok b">' +
        escapeHtml(t("miniapp.habits.d39_stock_label", { stock: fr.stock, max: fr.max_stock })) +
        "</div>" +
        '<div class="sm mu">' +
        escapeHtml(t("miniapp.habits.d39_next_free", { days: st.days_until_next_free_freeze })) +
        "</div>" +
        '<div class="sm mu">' +
        escapeHtml(t("miniapp.habits.d39_rolling_cap", { used: fr.protected_30d_used, cap: fr.protected_30d_cap })) +
        "</div>" +
        '<button type="button" class="opt ' +
        (fr.auto_enabled ? "on" : "") +
        '" id="d39-toggle-auto">' +
        '<span class="cbx ' +
        (fr.auto_enabled ? "on" : "") +
        '">✓</span>' +
        '<span class="grow">' +
        escapeHtml(t("miniapp.habits.d39_auto_label")) +
        "</span>" +
        "</button>" +
        '<div class="col" style="gap:8px; margin-top:6px;">' +
        (fr.stock > 0
          ? '<button type="button" class="btn" id="d39-apply-btn">' +
            escapeHtml(t("miniapp.habits.d39_apply_today_btn")) +
            "</button>"
          : "") +
        '<button type="button" class="btn b2" id="d39-buy-day-btn">' +
        escapeHtml(t("miniapp.habits.d39_buy_day_btn", { price: fr.price_day_xtr })) +
        "</button>" +
        '<button type="button" class="btn b2" id="d39-buy-week-btn">' +
        escapeHtml(t("miniapp.habits.d39_buy_week_btn", { price: fr.price_week_xtr })) +
        "</button>" +
        "</div>" +
        "</section>";

      bindLanguageButtons(vp);

      const autoBtn = document.getElementById("d39-toggle-auto");
      if (autoBtn) {
        autoBtn.addEventListener("click", async function () {
          await apiFetch("api/v1/streaks/freeze-settings", {
            method: "PATCH",
            body: { freeze_auto_enabled: !fr.auto_enabled },
          });
          renderCurrentScreen();
        });
      }

      const applyBtn = document.getElementById("d39-apply-btn");
      if (applyBtn) {
        applyBtn.addEventListener("click", async function () {
          triggerHaptic("notification", "success");
          await apiFetch("api/v1/streaks/freeze-apply", { method: "POST", body: {} });
          renderCurrentScreen();
        });
      }

      const buyDayBtn = document.getElementById("d39-buy-day-btn");
      if (buyDayBtn) {
        buyDayBtn.addEventListener("click", async function () {
          const res = await apiFetch("api/v1/streaks/freeze-purchase", {
            method: "POST",
            body: { kind: "freeze_day" },
          });
          if (res.invoice_link && tg && typeof tg.openInvoice === "function") {
            tg.openInvoice(res.invoice_link, function () {
              renderCurrentScreen();
            });
          }
        });
      }

      const buyWeekBtn = document.getElementById("d39-buy-week-btn");
      if (buyWeekBtn) {
        buyWeekBtn.addEventListener("click", async function () {
          const res = await apiFetch("api/v1/streaks/freeze-purchase", {
            method: "POST",
            body: { kind: "freeze_week" },
          });
          if (res.invoice_link && tg && typeof tg.openInvoice === "function") {
            tg.openInvoice(res.invoice_link, function () {
              renderCurrentScreen();
            });
          }
        });
      }
    } catch (_e) {}
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

  // ==================== D14, D15, D16, D17, D18 & D30: Materials, AI Import & Quota Sheet ====================
  function openMaterialInputD14(topicId) {
    state.materialDraft = {
      topic_id: topicId || state.activeTopicId || null,
      mode: "text",
      title: "",
      goal: "exam",
      text: "",
    };
    navigateTo("D14");
  }

  function renderD14D15(vp) {
    const draft = state.materialDraft || {
      topic_id: state.activeTopicId || null,
      mode: "text",
      title: "",
      goal: "exam",
      text: "",
    };
    state.materialDraft = draft;

    vp.innerHTML =
      renderTopBar(t("miniapp.materials.d14_title"), true) +
      '<section class="card col" style="gap:14px;">' +
      '<div class="seg">' +
      '<button type="button" class="' +
      (draft.mode === "text" ? "on" : "") +
      '" data-mat-mode="text">' +
      escapeHtml(t("miniapp.materials.d14_tab_text")) +
      "</button>" +
      '<button type="button" class="' +
      (draft.mode === "file" ? "on" : "") +
      '" data-mat-mode="file">' +
      escapeHtml(t("miniapp.materials.d14_tab_file")) +
      "</button>" +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d14-title">' +
      escapeHtml(t("miniapp.materials.d14_title_label")) +
      "</label>" +
      '<input id="d14-title" class="inp" type="text" value="' +
      escapeHtml(draft.title) +
      '" />' +
      "</div>" +
      (draft.mode === "text"
        ? '<div class="col" style="gap:6px;">' +
          '<label class="lab" for="d14-text">' +
          escapeHtml(t("miniapp.materials.d14_text_label")) +
          "</label>" +
          '<textarea id="d14-text" class="inp ta" style="min-height:160px;" placeholder="' +
          escapeHtml(t("miniapp.materials.d14_text_placeholder")) +
          '">' +
          escapeHtml(draft.text) +
          "</textarea>" +
          "</div>" +
          '<button type="button" class="btn" id="d14-submit-text-btn">' +
          escapeHtml(t("miniapp.materials.d14_estimate_btn")) +
          "</button>"
        : '<div class="col" style="gap:10px;">' +
          '<div class="bn in">' +
          escapeHtml(t("miniapp.materials.d15_file_hint")) +
          "</div>" +
          '<input id="d15-file-inp" class="inp" type="file" accept=".txt,.md,.pdf,.docx,.epub" />' +
          '<button type="button" class="btn" id="d15-upload-btn">' +
          escapeHtml(t("miniapp.materials.d15_upload_btn")) +
          "</button>" +
          "</div>") +
      "</section>";

    bindLanguageButtons(vp);

    vp.querySelectorAll("[data-mat-mode]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        draft.mode = btn.getAttribute("data-mat-mode");
        renderCurrentScreen();
      });
    });

    const titleInp = document.getElementById("d14-title");
    if (titleInp) {
      titleInp.addEventListener("input", function () {
        draft.title = titleInp.value;
      });
    }

    const textInp = document.getElementById("d14-text");
    if (textInp) {
      textInp.addEventListener("input", function () {
        draft.text = textInp.value;
      });
    }

    const submitTextBtn = document.getElementById("d14-submit-text-btn");
    if (submitTextBtn) {
      submitTextBtn.addEventListener("click", async function () {
        if (!draft.title.trim() || draft.text.trim().length < 10) return;
        triggerHaptic("impact", "light");
        try {
          const created = await apiFetch("api/v1/materials/text", {
            method: "POST",
            body: {
              topic_id: draft.topic_id,
              title: draft.title.trim(),
              goal: draft.goal || "exam",
              language: state.locale,
              text: draft.text.trim(),
            },
          });
          state.activeMaterial = created.material;
          state.activeTopicId = created.material.topic_id;
          navigateTo("D16");
        } catch (_e) {}
      });
    }

    const uploadBtn = document.getElementById("d15-upload-btn");
    if (uploadBtn) {
      uploadBtn.addEventListener("click", async function () {
        const fileInp = document.getElementById("d15-file-inp");
        if (!fileInp || !fileInp.files || !fileInp.files[0]) return;
        const f = fileInp.files[0];
        const formData = new FormData();
        formData.append("file", f);
        if (draft.topic_id) formData.append("topic_id", draft.topic_id);
        if (draft.title.trim()) formData.append("title", draft.title.trim());
        formData.append("goal", draft.goal || "exam");
        formData.append("language", state.locale);

        const headers = {};
        if (state.sessionToken) headers["Authorization"] = "Bearer " + state.sessionToken;
        if (!state.insideTelegram) headers["X-Demo-User-Id"] = "999000111";

        try {
          const resp = await fetch("api/v1/materials/upload", {
            method: "POST",
            headers: headers,
            body: formData,
          });
          if (!resp.ok) return;
          const created = await resp.json();
          state.activeMaterial = created.material;
          state.activeTopicId = created.material.topic_id;
          navigateTo("D16");
        } catch (_e) {}
      });
    }
  }

  async function renderD16(vp) {
    vp.innerHTML = renderTopBar(t("miniapp.materials.d16_title"), true) + '<div class="sk" style="height:140px;"></div>';
    bindLanguageButtons(vp);

    if (!state.activeMaterial || !state.activeMaterial.id) {
      navigateTo("D14", { pushHistory: false });
      return;
    }

    try {
      const est = await apiFetch("api/v1/materials/estimate", {
        method: "POST",
        body: { material_id: state.activeMaterial.id },
      });
      state.activeEstimate = est;

      const ctaLabel = est.trial_eligible
        ? t("miniapp.materials.d16_start_trial_cta")
        : t("miniapp.materials.d16_start_cta");

      vp.innerHTML =
        renderTopBar(t("miniapp.materials.d16_title"), true) +
        '<section class="card col" style="gap:12px;">' +
        '<h1 class="h2">' +
        escapeHtml(est.title) +
        "</h1>" +
        '<div class="chip c-pr">' +
        escapeHtml(t("miniapp.materials.d16_tokens_label", { tokens: est.token_count })) +
        "</div>" +
        '<div class="sm mu">' +
        escapeHtml(t("miniapp.materials.d16_quota_after", { remaining: est.quota.after_operation })) +
        "</div>" +
        (est.trial_eligible
          ? '<div class="bn ok">' + escapeHtml(t("miniapp.materials.d16_trial_banner")) + "</div>"
          : "") +
        '<div class="bn in">' +
        escapeHtml(t("miniapp.materials.d16_ai_disclosure")) +
        "</div>" +
        '<button type="button" class="btn" id="d16-confirm-ai-btn">' +
        escapeHtml(ctaLabel) +
        "</button>" +
        '<button type="button" class="btn b2" id="d16-manual-btn">' +
        escapeHtml(t("miniapp.materials.d16_manual_fallback")) +
        "</button>" +
        "</section>";

      bindLanguageButtons(vp);

      const confirmBtn = document.getElementById("d16-confirm-ai-btn");
      if (confirmBtn) {
        confirmBtn.addEventListener("click", async function () {
          if (!est.can_proceed) {
            openQuotaLimitSheetD30({
              required_amount: est.token_count,
              remaining: est.quota.effective_remaining,
            });
            return;
          }
          state.pendingImportRequest = {
            material_id: est.material_id,
            operation_id: "op-" + Date.now(),
            estimate_signature: est.estimate_signature,
            activate_trial: Boolean(est.trial_eligible),
            ai_consent_accepted: true,
          };
          navigateTo("D17");
        });
      }

      const manualBtn = document.getElementById("d16-manual-btn");
      if (manualBtn) {
        manualBtn.addEventListener("click", function () {
          openItemEditorD09Edit(state.activeTopicId, null, false);
        });
      }
    } catch (_e) {}
  }

  async function renderD17(vp) {
    vp.innerHTML =
      renderTopBar(t("miniapp.materials.d17_title"), true) +
      '<section class="card col" style="gap:14px;">' +
      '<h1 class="h2">' +
      escapeHtml(t("miniapp.materials.d17_title")) +
      "</h1>" +
      '<div class="col" style="gap:8px;">' +
      '<div class="bn in">1. ' +
      escapeHtml(t("miniapp.materials.d17_stage_extract")) +
      "</div>" +
      '<div class="bn in">2. ' +
      escapeHtml(t("miniapp.materials.d17_stage_exercises")) +
      "</div>" +
      '<div class="bn in">3. ' +
      escapeHtml(t("miniapp.materials.d17_stage_validate")) +
      "</div>" +
      "</div>" +
      '<div class="sk" style="height:24px;"></div>' +
      "</section>";
    bindLanguageButtons(vp);

    if (!state.pendingImportRequest) {
      navigateTo("D04", { pushHistory: false });
      return;
    }

    try {
      const reqBody = state.pendingImportRequest;
      state.pendingImportRequest = null;
      const res = await apiFetch("api/v1/materials/import-jobs", {
        method: "POST",
        body: reqBody,
      });
      state.activeImportJob = res;
      navigateTo("D18", { pushHistory: false });
    } catch (err) {
      openQuotaLimitSheetD30({ required_amount: 1000, remaining: 0 });
      navigateTo("D16", { pushHistory: false });
    }
  }

  function renderD18(vp) {
    const jobData = state.activeImportJob;
    if (!jobData || !jobData.job) {
      navigateTo("D04", { pushHistory: false });
      return;
    }

    const items = jobData.item_candidates || [];
    const rels = jobData.relation_candidates || [];

    const itemsHtml = items
      .map(function (c, idx) {
        return (
          '<div class="card col" style="gap:8px; padding:12px;">' +
          '<div class="row sp">' +
          '<span class="chip c-pr">' +
          escapeHtml(c.item_type) +
          "</span>" +
          '<input type="checkbox" data-cand-item="' +
          escapeHtml(c.id) +
          '" ' +
          (c.selected ? "checked" : "") +
          " />" +
          "</div>" +
          '<div class="b">' +
          escapeHtml(c.prompt) +
          "</div>" +
          '<div class="sm">' +
          escapeHtml(c.answer) +
          "</div>" +
          (c.anchor_label
            ? '<div class="xs mu">📖 ' + escapeHtml(c.anchor_label) + "</div>"
            : "") +
          (c.warning_note
            ? '<div class="bn wn xs">' + escapeHtml(c.warning_note) + "</div>"
            : "") +
          "</div>"
        );
      })
      .join("");

    const relsHtml = rels
      .map(function (r) {
        return (
          '<div class="card col" style="gap:6px; padding:12px;">' +
          '<div class="row sp">' +
          '<span class="chip">M5 · ' +
          escapeHtml(r.relation_type) +
          "</span>" +
          '<input type="checkbox" data-cand-rel="' +
          escapeHtml(r.id) +
          '" ' +
          (r.selected ? "checked" : "") +
          " />" +
          "</div>" +
          '<div class="sm b">' +
          escapeHtml(r.prompt) +
          "</div>" +
          '<div class="xs mu">' +
          escapeHtml(r.explanation) +
          "</div>" +
          "</div>"
        );
      })
      .join("");

    vp.innerHTML =
      renderTopBar(t("miniapp.materials.d18_title"), true) +
      '<section class="card col" style="gap:10px;">' +
      '<h1 class="h2">' +
      escapeHtml(t("miniapp.materials.d18_title")) +
      "</h1>" +
      '<p class="sm mu">' +
      escapeHtml(t("miniapp.materials.d18_subtitle")) +
      "</p>" +
      "</section>" +
      '<div class="eyebrow">' +
      escapeHtml(t("miniapp.materials.d18_items_section", { count: items.length })) +
      "</div>" +
      itemsHtml +
      (rels.length
        ? '<div class="eyebrow">' +
          escapeHtml(t("miniapp.materials.d18_relations_section", { count: rels.length })) +
          "</div>" +
          '<div class="xs mu">' +
          escapeHtml(t("miniapp.materials.d18_relations_hint")) +
          "</div>" +
          relsHtml
        : "") +
      '<button type="button" class="btn" id="d18-accept-btn">' +
      escapeHtml(t("miniapp.materials.d18_accept_cta")) +
      "</button>";

    bindLanguageButtons(vp);

    const acceptBtn = document.getElementById("d18-accept-btn");
    if (acceptBtn) {
      acceptBtn.addEventListener("click", async function () {
        const selectedItemIds = [];
        vp.querySelectorAll("[data-cand-item]").forEach(function (cb) {
          if (cb.checked) selectedItemIds.push(cb.getAttribute("data-cand-item"));
        });
        const selectedRelIds = [];
        vp.querySelectorAll("[data-cand-rel]").forEach(function (cb) {
          if (cb.checked) selectedRelIds.push(cb.getAttribute("data-cand-rel"));
        });

        triggerHaptic("notification", "success");
        try {
          const accepted = await apiFetch(
            "api/v1/materials/import-jobs/" + encodeURIComponent(jobData.job.id) + "/accept",
            {
              method: "POST",
              body: {
                item_candidate_ids: selectedItemIds,
                relation_candidate_ids: selectedRelIds,
              },
            }
          );
          state.activeTopicId = accepted.topic_id;
          openBottomSheet({
            size: "small",
            title: t("miniapp.materials.d18_accepted_title"),
            bodyHtml:
              '<div class="col" style="gap:12px;">' +
              '<p class="sm">' +
              escapeHtml(
                t("miniapp.materials.d18_accepted_desc", {
                  items: accepted.accepted_items_count,
                  relations: accepted.accepted_relations_count,
                })
              ) +
              "</p>" +
              '<button type="button" class="btn" id="d18-go-study-btn">' +
              escapeHtml(t("miniapp.materials.d18_start_study_cta")) +
              "</button>" +
              "</div>",
          });
          const goStudyBtn = document.getElementById("d18-go-study-btn");
          if (goStudyBtn) {
            goStudyBtn.addEventListener("click", function () {
              closeBottomSheet();
              navigateTo("D10", { pushHistory: false });
            });
          }
          navigateTo("D08", { pushHistory: false });
        } catch (_e) {}
      });
    }
  }

  function openQuotaLimitSheetD30(info) {
    const req = (info && info.required_amount) || 1000;
    const rem = (info && info.remaining) || 0;
    openBottomSheet({
      size: "medium",
      title: t("miniapp.materials.d30_title"),
      bodyHtml:
        '<div class="col" style="gap:12px;">' +
        '<div class="bn wn">' +
        escapeHtml(t("miniapp.materials.d30_desc", { required: req, remaining: rem })) +
        "</div>" +
        '<button type="button" class="btn" id="d30-open-plans-btn">' +
        escapeHtml(t("miniapp.materials.d30_upgrade_cta")) +
        "</button>" +
        '<button type="button" class="btn b2" id="d30-manual-btn">' +
        escapeHtml(t("miniapp.materials.d30_manual_cta")) +
        "</button>" +
        "</div>",
    });
    const upBtn = document.getElementById("d30-open-plans-btn");
    if (upBtn) {
      upBtn.addEventListener("click", function () {
        closeBottomSheet();
        navigateTo("D27");
      });
    }
    const manBtn = document.getElementById("d30-manual-btn");
    if (manBtn) {
      manBtn.addEventListener("click", function () {
        closeBottomSheet();
        openItemEditorD09Edit(state.activeTopicId, null, false);
      });
    }
  }

  // ==================== D27, D28 & D29: Telegram Stars Billing, Subscriptions & Downgrade Active Set ====================
  async function renderD27D28(vp) {
    vp.innerHTML = renderTopBar(t("miniapp.billing.d27_title"), true) + '<div class="sk" style="height:180px;"></div>';
    bindLanguageButtons(vp);

    try {
      const data = await apiFetch("api/v1/billing/plans");
      const ent = data.entitlement;
      const usage = ent.usage;

      vp.innerHTML =
        renderTopBar(t("miniapp.billing.d27_title"), true) +
        (ent.downgrade_selection_required
          ? '<div class="bn wn col" style="gap:8px;"><div>' +
            escapeHtml(t("miniapp.billing.d27_downgrade_banner")) +
            '</div><button type="button" class="btn b2 bsm" id="d27-open-d29-btn">' +
            escapeHtml(t("miniapp.billing.d29_title")) +
            "</button></div>"
          : "") +
        '<section class="card col" style="gap:10px;">' +
        '<div class="row sp">' +
        '<span class="chip c-pr">' +
        escapeHtml(t("miniapp.billing.d27_current_plan", { plan: ent.plan_code.toUpperCase() })) +
        "</span>" +
        (ent.period_end
          ? '<span class="xs mu">' +
            escapeHtml(t("miniapp.billing.d27_period_end", { date: ent.period_end.slice(0, 10) })) +
            "</span>"
          : "") +
        "</div>" +
        '<div class="sm">' +
        escapeHtml(t("miniapp.billing.d27_usage_topics", { used: usage.active_topics, limit: usage.topics_limit })) +
        "</div>" +
        '<div class="sm">' +
        escapeHtml(t("miniapp.billing.d27_usage_habits", { used: usage.active_habits, limit: usage.habits_limit })) +
        "</div>" +
        '<div class="sm">' +
        escapeHtml(
          t("miniapp.billing.d27_usage_tokens", {
            used: usage.import_tokens.used,
            limit: usage.import_tokens.limit,
          })
        ) +
        "</div>" +
        '<div class="sm">' +
        escapeHtml(
          t("miniapp.billing.d27_usage_checks", {
            used: usage.ai_checks.used,
            limit: usage.ai_checks.limit,
          })
        ) +
        "</div>" +
        (ent.plan_code === "start" || ent.plan_code === "pro"
          ? '<div class="dv"></div>' +
            '<div class="xs mu">' +
            escapeHtml(
              ent.auto_renew ? t("miniapp.billing.d28_auto_renew_on") : t("miniapp.billing.d28_auto_renew_off")
            ) +
            "</div>" +
            (ent.auto_renew
              ? '<button type="button" class="btn b2 bsm" id="d28-cancel-btn">' +
                escapeHtml(t("miniapp.billing.d28_cancel_btn")) +
                "</button>"
              : "") +
            '<button type="button" class="btn b3 bsm" id="d28-refund-btn">' +
            escapeHtml(t("miniapp.billing.d28_refund_btn")) +
            "</button>"
          : "") +
        "</section>" +
        '<section class="card col" style="gap:12px;">' +
        '<div class="sm">' +
        escapeHtml(t("miniapp.billing.d27_plan_free")) +
        "</div>" +
        '<div class="dv"></div>' +
        '<div class="b">' +
        escapeHtml(t("miniapp.billing.d27_plan_start")) +
        "</div>" +
        '<button type="button" class="btn" id="d27-sub-start-btn">' +
        escapeHtml(t("miniapp.billing.d27_subscribe_start_btn")) +
        "</button>" +
        '<div class="dv"></div>' +
        '<div class="b">' +
        escapeHtml(t("miniapp.billing.d27_plan_pro")) +
        "</div>" +
        '<button type="button" class="btn" id="d27-sub-pro-btn">' +
        escapeHtml(t("miniapp.billing.d27_subscribe_pro_btn")) +
        "</button>" +
        "</section>";

      bindLanguageButtons(vp);

      const d29Btn = document.getElementById("d27-open-d29-btn");
      if (d29Btn) {
        d29Btn.addEventListener("click", function () {
          navigateTo("D29");
        });
      }

      async function handleSubscribe(planCode) {
        triggerHaptic("impact", "light");
        try {
          const res = await apiFetch("api/v1/billing/subscribe", {
            method: "POST",
            body: { plan_code: planCode, confirm_immediately_in_dev: !state.insideTelegram },
          });
          if (res.invoice_link && tg && typeof tg.openInvoice === "function") {
            tg.openInvoice(res.invoice_link, function () {
              renderCurrentScreen();
            });
          } else {
            renderCurrentScreen();
          }
        } catch (_e) {}
      }

      const startBtn = document.getElementById("d27-sub-start-btn");
      if (startBtn) {
        startBtn.addEventListener("click", function () {
          handleSubscribe("start");
        });
      }
      const proBtn = document.getElementById("d27-sub-pro-btn");
      if (proBtn) {
        proBtn.addEventListener("click", function () {
          handleSubscribe("pro");
        });
      }

      const cancelBtn = document.getElementById("d28-cancel-btn");
      if (cancelBtn) {
        cancelBtn.addEventListener("click", async function () {
          try {
            await apiFetch("api/v1/billing/cancel", { method: "POST", body: {} });
            renderCurrentScreen();
          } catch (_e) {}
        });
      }

      const refundBtn = document.getElementById("d28-refund-btn");
      if (refundBtn) {
        refundBtn.addEventListener("click", async function () {
          try {
            const ref = await apiFetch("api/v1/billing/refund", { method: "POST", body: {} });
            if (ref.downgrade_selection_required) {
              navigateTo("D29");
            } else {
              renderCurrentScreen();
            }
          } catch (_e) {}
        });
      }
    } catch (_e) {}
  }

  async function renderD29(vp) {
    vp.innerHTML = renderTopBar(t("miniapp.billing.d29_title"), true) + '<div class="sk" style="height:160px;"></div>';
    bindLanguageButtons(vp);

    try {
      const opts = await apiFetch("api/v1/billing/downgrade-options");
      const topics = opts.topics || [];
      const habits = opts.habits || [];

      const topicsHtml = topics
        .map(function (tp, idx) {
          return (
            '<label class="opt" style="cursor:pointer;">' +
            '<input type="checkbox" data-d29-topic="' +
            escapeHtml(tp.id) +
            '" ' +
            (idx < 3 ? "checked" : "") +
            " />" +
            '<span class="grow b">' +
            escapeHtml(tp.title) +
            "</span></label>"
          );
        })
        .join("");

      const habitsHtml = habits
        .map(function (hb, idx) {
          return (
            '<label class="opt" style="cursor:pointer;">' +
            '<input type="checkbox" data-d29-habit="' +
            escapeHtml(hb.id) +
            '" ' +
            (idx < 3 ? "checked" : "") +
            " />" +
            '<span class="grow b">' +
            escapeHtml(hb.title) +
            "</span></label>"
          );
        })
        .join("");

      vp.innerHTML =
        renderTopBar(t("miniapp.billing.d29_title"), true) +
        '<section class="card col" style="gap:12px;">' +
        '<h1 class="h2">' +
        escapeHtml(t("miniapp.billing.d29_title")) +
        "</h1>" +
        '<p class="sm mu">' +
        escapeHtml(t("miniapp.billing.d29_desc")) +
        "</p>" +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.billing.d29_topics_header")) +
        "</div>" +
        topicsHtml +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.billing.d29_habits_header")) +
        "</div>" +
        habitsHtml +
        '<button type="button" class="btn" id="d29-save-btn">' +
        escapeHtml(t("miniapp.billing.d29_save_cta")) +
        "</button>" +
        "</section>";

      bindLanguageButtons(vp);

      const saveBtn = document.getElementById("d29-save-btn");
      if (saveBtn) {
        saveBtn.addEventListener("click", async function () {
          const selTopics = [];
          vp.querySelectorAll("[data-d29-topic]").forEach(function (cb) {
            if (cb.checked && selTopics.length < 3) selTopics.push(cb.getAttribute("data-d29-topic"));
          });
          const selHabits = [];
          vp.querySelectorAll("[data-d29-habit]").forEach(function (cb) {
            if (cb.checked && selHabits.length < 3) selHabits.push(cb.getAttribute("data-d29-habit"));
          });

          try {
            await apiFetch("api/v1/billing/select-active-set", {
              method: "POST",
              body: { active_topic_ids: selTopics, active_habit_ids: selHabits },
            });
            navigateTo("D04", { pushHistory: false });
          } catch (_e) {}
        });
      }
    } catch (_e) {}
  }

  // ==================== D24, D25, D26, D31, D32, D33 & D35: Progress, Settings, Notifications, Export & Deletion ====================
  function formatMetricLine(metricObj) {
    if (!metricObj) return "";
    const denom = t("miniapp.progress.d24_k_of_n", {
      k: metricObj.correct_count,
      n: metricObj.total_count,
    });
    if (!metricObj.sufficient_data) {
      return denom + " · " + t("miniapp.progress.d24_not_enough_data");
    }
    return metricObj.percentage + "% (" + denom + ")";
  }

  async function renderD24(vp) {
    const winDays = state.progressWindowDays || 7;
    vp.innerHTML =
      renderTopBar(t("miniapp.progress.d24_title"), false) +
      '<div class="sk" style="height:180px;"></div>';
    bindLanguageButtons(vp);

    try {
      const p = await apiFetch("api/v1/progress?window_days=" + encodeURIComponent(winDays));
      const ov = p.overall;
      const byObj = p.by_objective || {};
      const hb = p.habits_summary || {};

      vp.innerHTML =
        renderTopBar(t("miniapp.progress.d24_title"), false) +
        '<div class="seg">' +
        '<button type="button" class="' +
        (winDays === 7 ? "on" : "") +
        '" data-prog-win="7">' +
        escapeHtml(t("miniapp.progress.d24_window_7d")) +
        "</button>" +
        '<button type="button" class="' +
        (winDays === 30 ? "on" : "") +
        '" data-prog-win="30">' +
        escapeHtml(t("miniapp.progress.d24_window_30d")) +
        "</button>" +
        "</div>" +
        '<section class="card col" style="gap:10px;">' +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.progress.d24_overall_label")) +
        "</div>" +
        '<div class="h2">' +
        escapeHtml(formatMetricLine(ov)) +
        "</div>" +
        '<div class="dv"></div>' +
        '<div class="sm"><b>' +
        escapeHtml(t("miniapp.progress.d24_obj_recall")) +
        ":</b> " +
        escapeHtml(formatMetricLine(byObj.recall)) +
        "</div>" +
        '<div class="sm"><b>' +
        escapeHtml(t("miniapp.progress.d24_obj_explain")) +
        ":</b> " +
        escapeHtml(formatMetricLine(byObj.explain)) +
        "</div>" +
        '<div class="sm"><b>' +
        escapeHtml(t("miniapp.progress.d24_obj_discriminate")) +
        ":</b> " +
        escapeHtml(formatMetricLine(byObj.discriminate)) +
        "</div>" +
        '<div class="sm"><b>' +
        escapeHtml(t("miniapp.progress.d24_obj_relate")) +
        ":</b> " +
        escapeHtml(formatMetricLine(byObj.relate)) +
        "</div>" +
        "</section>" +
        '<section class="card col" style="gap:8px;">' +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.progress.d24_habits_label")) +
        "</div>" +
        '<div class="sm">' +
        escapeHtml(
          t("miniapp.progress.d24_habits_k_of_n", {
            k: hb.completed_count || 0,
            n: hb.planned_count || 0,
            min: hb.minimum_count || 0,
          })
        ) +
        "</div>" +
        "</section>" +
        '<div class="col" style="gap:8px;">' +
        '<button type="button" class="btn b2" id="d24-drilldown-btn">' +
        escapeHtml(t("miniapp.progress.d24_open_drilldown_btn")) +
        "</button>" +
        '<button type="button" class="btn b2" id="d24-weekly-btn">' +
        escapeHtml(t("miniapp.progress.d24_open_weekly_btn")) +
        "</button>" +
        '<button type="button" class="btn b3" id="d24-settings-btn">' +
        escapeHtml(t("miniapp.progress.d24_open_settings_btn")) +
        "</button>" +
        "</div>";

      bindLanguageButtons(vp);

      vp.querySelectorAll("[data-prog-win]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          state.progressWindowDays = parseInt(btn.getAttribute("data-prog-win"), 10) || 7;
          renderCurrentScreen();
        });
      });

      const ddBtn = document.getElementById("d24-drilldown-btn");
      if (ddBtn) {
        ddBtn.addEventListener("click", function () {
          navigateTo("D25");
        });
      }
      const wkBtn = document.getElementById("d24-weekly-btn");
      if (wkBtn) {
        wkBtn.addEventListener("click", function () {
          navigateTo("D35");
        });
      }
      const stBtn = document.getElementById("d24-settings-btn");
      if (stBtn) {
        stBtn.addEventListener("click", function () {
          navigateTo("D26");
        });
      }
    } catch (_e) {}
  }

  async function renderD25(vp) {
    vp.innerHTML = renderTopBar(t("miniapp.progress.d25_title"), true) + '<div class="sk" style="height:180px;"></div>';
    bindLanguageButtons(vp);

    try {
      const dd = await apiFetch("api/v1/progress/drilldown?window_days=30");
      const topicsHtml = (dd.topics || [])
        .map(function (tp) {
          return (
            '<div class="card col" style="gap:4px; padding:12px;">' +
            '<div class="b">' +
            escapeHtml(tp.title) +
            "</div>" +
            '<div class="sm mu">' +
            escapeHtml(formatMetricLine(tp.metrics)) +
            "</div></div>"
          );
        })
        .join("");

      const groupsHtml = (dd.groups || [])
        .map(function (gr) {
          return (
            '<div class="card col" style="gap:4px; padding:12px;">' +
            '<div class="b">🕸 ' +
            escapeHtml(gr.title) +
            "</div>" +
            '<div class="sm mu">' +
            escapeHtml(formatMetricLine(gr.metrics)) +
            "</div></div>"
          );
        })
        .join("");

      const habitsHtml = (dd.habits || [])
        .map(function (hb) {
          return (
            '<div class="card col" style="gap:4px; padding:12px;">' +
            '<div class="b">🌱 ' +
            escapeHtml(hb.title) +
            "</div>" +
            '<div class="sm mu">' +
            escapeHtml(
              t("miniapp.progress.d24_habits_k_of_n", {
                k: hb.completed_count,
                n: hb.planned_count,
                min: hb.minimum_count,
              })
            ) +
            "</div></div>"
          );
        })
        .join("");

      vp.innerHTML =
        renderTopBar(t("miniapp.progress.d25_title"), true) +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.progress.d25_topics_header")) +
        "</div>" +
        (topicsHtml || '<div class="sm mu">—</div>') +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.progress.d25_groups_header")) +
        "</div>" +
        (groupsHtml || '<div class="sm mu">—</div>') +
        '<div class="eyebrow">' +
        escapeHtml(t("miniapp.progress.d25_habits_header")) +
        "</div>" +
        (habitsHtml || '<div class="sm mu">—</div>');

      bindLanguageButtons(vp);
    } catch (_e) {}
  }

  async function renderD35(vp) {
    vp.innerHTML = renderTopBar(t("miniapp.progress.d35_title"), true) + '<div class="sk" style="height:160px;"></div>';
    bindLanguageButtons(vp);

    try {
      const res = await apiFetch("api/v1/weekly-reviews");
      const list = res.weekly_reviews || [];

      const cardsHtml = list
        .map(function (wr) {
          const suggHtml = (wr.ai_suggestions || [])
            .map(function (s) {
              return '<div class="xs">• ' + escapeHtml(s.text) + "</div>";
            })
            .join("");
          return (
            '<section class="card col" style="gap:8px;">' +
            '<div class="eyebrow">' +
            escapeHtml(wr.period_label) +
            "</div>" +
            '<div class="sm">' +
            escapeHtml(wr.ai_summary || "") +
            "</div>" +
            suggHtml +
            "</section>"
          );
        })
        .join("");

      vp.innerHTML =
        renderTopBar(t("miniapp.progress.d35_title"), true) +
        '<button type="button" class="btn" id="d35-gen-btn">' +
        escapeHtml(t("miniapp.progress.d35_generate_btn")) +
        "</button>" +
        cardsHtml;

      bindLanguageButtons(vp);

      const genBtn = document.getElementById("d35-gen-btn");
      if (genBtn) {
        genBtn.addEventListener("click", async function () {
          try {
            await apiFetch("api/v1/weekly-reviews/generate?use_ai=true", { method: "POST", body: {} });
            renderCurrentScreen();
          } catch (_e) {}
        });
      }
    } catch (_e) {}
  }

  function renderD26(vp) {
    const u = state.user || {};
    vp.innerHTML =
      renderTopBar(t("miniapp.progress.d26_title"), true) +
      '<section class="card col" style="gap:12px;">' +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d26-min">' +
      escapeHtml(t("miniapp.progress.d26_rhythm_label")) +
      "</label>" +
      '<input id="d26-min" class="inp" type="number" min="5" max="60" value="' +
      escapeHtml(u.daily_study_minutes || 10) +
      '" />' +
      "</div>" +
      '<div class="col" style="gap:6px;">' +
      '<label class="lab" for="d26-tz">' +
      escapeHtml(t("miniapp.progress.d26_tz_label")) +
      "</label>" +
      '<input id="d26-tz" class="inp" type="text" value="' +
      escapeHtml(u.timezone || "Europe/Moscow") +
      '" />' +
      "</div>" +
      '<label class="opt" style="cursor:pointer;">' +
      '<input type="checkbox" id="d26-haptics" ' +
      (u.haptics_enabled !== false ? "checked" : "") +
      " />" +
      '<span class="grow">' +
      escapeHtml(t("miniapp.progress.d26_haptics_label")) +
      "</span></label>" +
      '<label class="opt" style="cursor:pointer;">' +
      '<input type="checkbox" id="d26-analytics" ' +
      (u.analytics_allowed !== false ? "checked" : "") +
      " />" +
      '<span class="grow">' +
      escapeHtml(t("miniapp.progress.d26_analytics_label")) +
      "</span></label>" +
      '<button type="button" class="btn" id="d26-save-btn">' +
      escapeHtml(t("miniapp.common.save")) +
      "</button>" +
      "</section>" +
      '<div class="col" style="gap:8px;">' +
      '<button type="button" class="btn b2" id="d26-nav-d27">' +
      escapeHtml(t("miniapp.progress.d26_open_billing_btn")) +
      "</button>" +
      '<button type="button" class="btn b2" id="d26-nav-d31">' +
      escapeHtml(t("miniapp.progress.d26_open_notif_btn")) +
      "</button>" +
      '<button type="button" class="btn b2" id="d26-nav-d32">' +
      escapeHtml(t("miniapp.progress.d26_open_privacy_btn")) +
      "</button>" +
      '<button type="button" class="btn b3" id="d26-nav-d33">' +
      escapeHtml(t("miniapp.progress.d26_open_help_btn")) +
      "</button>" +
      "</div>";

    bindLanguageButtons(vp);

    const saveBtn = document.getElementById("d26-save-btn");
    if (saveBtn) {
      saveBtn.addEventListener("click", async function () {
        const minInp = document.getElementById("d26-min");
        const tzInp = document.getElementById("d26-tz");
        const hapInp = document.getElementById("d26-haptics");
        const anInp = document.getElementById("d26-analytics");
        try {
          const res = await apiFetch("api/v1/settings", {
            method: "PATCH",
            body: {
              daily_study_minutes: parseInt(minInp.value, 10) || 10,
              timezone: tzInp.value.trim() || "Europe/Moscow",
              haptics_enabled: Boolean(hapInp && hapInp.checked),
              analytics_allowed: Boolean(anInp && anInp.checked),
            },
          });
          if (res.user) state.user = res.user;
          triggerHaptic("notification", "success");
        } catch (_e) {}
      });
    }

    const b27 = document.getElementById("d26-nav-d27");
    if (b27) b27.addEventListener("click", function () { navigateTo("D27"); });
    const b31 = document.getElementById("d26-nav-d31");
    if (b31) b31.addEventListener("click", function () { navigateTo("D31"); });
    const b32 = document.getElementById("d26-nav-d32");
    if (b32) b32.addEventListener("click", function () { navigateTo("D32"); });
    const b33 = document.getElementById("d26-nav-d33");
    if (b33) b33.addEventListener("click", function () { navigateTo("D33"); });
  }

  async function renderD31(vp) {
    vp.innerHTML = renderTopBar(t("miniapp.progress.d31_title"), true) + '<div class="sk" style="height:140px;"></div>';
    bindLanguageButtons(vp);

    try {
      const res = await apiFetch("api/v1/notifications");
      const n = res.notifications || {};

      vp.innerHTML =
        renderTopBar(t("miniapp.progress.d31_title"), true) +
        '<section class="card col" style="gap:12px;">' +
        '<label class="opt" style="cursor:pointer;">' +
        '<input type="checkbox" id="d31-enabled" ' +
        (n.enabled ? "checked" : "") +
        " />" +
        '<span class="grow b">' +
        escapeHtml(t("miniapp.progress.d31_enabled_label")) +
        "</span></label>" +
        '<div class="col" style="gap:6px;">' +
        '<label class="lab" for="d31-time">' +
        escapeHtml(t("miniapp.progress.d31_time_label")) +
        "</label>" +
        '<input id="d31-time" class="inp" type="time" value="' +
        escapeHtml(n.daily_time || "08:30") +
        '" />' +
        "</div>" +
        '<div class="sm mu">' +
        escapeHtml(t("miniapp.progress.d31_quiet_label") + ": " + (n.quiet_start || "22:00") + " – " + (n.quiet_end || "08:00")) +
        "</div>" +
        '<button type="button" class="btn" id="d31-save-btn">' +
        escapeHtml(t("miniapp.common.save")) +
        "</button>" +
        '<button type="button" class="btn b2" id="d31-test-btn">' +
        escapeHtml(t("miniapp.progress.d31_test_btn")) +
        "</button>" +
        "</section>";

      bindLanguageButtons(vp);

      const saveBtn = document.getElementById("d31-save-btn");
      if (saveBtn) {
        saveBtn.addEventListener("click", async function () {
          const enCb = document.getElementById("d31-enabled");
          const tmInp = document.getElementById("d31-time");
          if (enCb && enCb.checked && tg && typeof tg.requestWriteAccess === "function") {
            try {
              tg.requestWriteAccess();
            } catch (_e) {}
          }
          try {
            await apiFetch("api/v1/notifications", {
              method: "PATCH",
              body: {
                enabled: Boolean(enCb && enCb.checked),
                write_access_granted: Boolean(enCb && enCb.checked),
                daily_time: tmInp ? tmInp.value : "08:30",
              },
            });
            triggerHaptic("notification", "success");
          } catch (_e) {}
        });
      }

      const testBtn = document.getElementById("d31-test-btn");
      if (testBtn) {
        testBtn.addEventListener("click", async function () {
          try {
            await apiFetch("api/v1/notifications/test", { method: "POST", body: {} });
            triggerHaptic("notification", "success");
          } catch (_e) {}
        });
      }
    } catch (_e) {}
  }

  function renderD32(vp) {
    vp.innerHTML =
      renderTopBar(t("miniapp.progress.d32_title"), true) +
      '<section class="card col" style="gap:10px;">' +
      '<h2 class="h2">' +
      escapeHtml(t("miniapp.progress.d32_title")) +
      "</h2>" +
      '<p class="sm mu">' +
      escapeHtml(t("miniapp.progress.d32_export_desc")) +
      "</p>" +
      '<button type="button" class="btn" id="d32-export-btn">' +
      escapeHtml(t("miniapp.progress.d32_export_btn")) +
      "</button>" +
      '<div id="d32-export-box"></div>' +
      "</section>" +
      '<section class="card col" style="gap:10px; border-color:var(--er);">' +
      '<h3 class="h3">' +
      escapeHtml(t("miniapp.progress.d32_delete_title")) +
      "</h3>" +
      '<p class="sm mu">' +
      escapeHtml(t("miniapp.progress.d32_delete_desc")) +
      "</p>" +
      '<button type="button" class="btn b2" id="d32-delete-btn" style="color:var(--er);">' +
      escapeHtml(t("miniapp.progress.d32_delete_btn")) +
      "</button>" +
      "</section>";

    bindLanguageButtons(vp);

    const expBtn = document.getElementById("d32-export-btn");
    if (expBtn) {
      expBtn.addEventListener("click", async function () {
        try {
          const res = await apiFetch("api/v1/exports", { method: "POST", body: {} });
          const box = document.getElementById("d32-export-box");
          if (box) {
            box.innerHTML =
              '<textarea class="inp ta xs" readonly style="min-height:140px;">' +
              escapeHtml(res.markdown_preview || "") +
              "</textarea>";
          }
        } catch (_e) {}
      });
    }

    const delBtn = document.getElementById("d32-delete-btn");
    if (delBtn) {
      delBtn.addEventListener("click", async function () {
        try {
          await apiFetch("api/v1/account/delete", {
            method: "POST",
            body: { confirm_phrase: "DELETE" },
          });
          localStorage.removeItem("br_session_token");
          state.sessionToken = null;
          state.user = null;
          navigateTo("D01", { pushHistory: false });
        } catch (_e) {}
      });
    }
  }

  function renderD33(vp) {
    vp.innerHTML =
      renderTopBar(t("miniapp.progress.d33_title"), true) +
      '<section class="card col" style="gap:12px;">' +
      '<h1 class="h2">' +
      escapeHtml(t("miniapp.progress.d33_title")) +
      "</h1>" +
      '<p class="sm">' +
      escapeHtml(t("miniapp.progress.d33_support_note")) +
      "</p>" +
      '<button type="button" class="btn" id="d33-open-d42">' +
      escapeHtml(t("miniapp.progress.d33_science_btn")) +
      "</button>" +
      "</section>";

    bindLanguageButtons(vp);

    const scBtn = document.getElementById("d33-open-d42");
    if (scBtn) {
      scBtn.addEventListener("click", function () {
        openScienceSheet("M1");
      });
    }
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
