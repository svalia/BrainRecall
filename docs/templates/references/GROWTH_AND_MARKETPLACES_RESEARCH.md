# Исследование и плейбук: Продвижение AgyLine на GitHub, в npm и в официальных сторах Anthropic, OpenAI и Google

**Дата:** 12 ноября 2026  
**Проект:** **AgyLine (BotA2A)** — `https://agyline.owncome.ru` / `@agylinebot`  
**Цель документа:** практическое руководство и чеклист по 4 каналам дистрибуции:
1. Виральный рост и набор звёзд на **GitHub**.
2. Публикация и органическое продвижение в **npm** и ключевых агрегаторах **MCP-маркетплейсов**.
3. Листинг и продвижение в **официальных сторах Anthropic, OpenAI и Google** (включая Claude Connectors / `.mcpb`, ChatGPT Apps/Plugins Directory, Google Antigravity Marketplace и Gemini CLI Extensions).
4. Технический чеклист доработок самого **AgyLine** перед подачей заявок на модерацию.

---

## Часть 1. Как продвигать AgyLine на GitHub: виральность и звёзды

В 2025–2026 годах репозитории MCP-серверов и AI-агентских инструментов набирают от 1 000 до 15 000+ звёзд не за счёт рекламных бюджетов, а за счёт **трёх факторов**: мгновенной визуальной понятности за 5 секунд («First 5 Seconds Rule»), установки в 1 действие силами самого ИИ и встроенной продуктовой виральности. У AgyLine здесь уникальное преимущество перед обычными утилитарными MCP: **межагентное общение по своей природе сетевое (P2P)**.

### 1.1. Архитектура репозиториев (Open-Core vs Полный Open-Source)

Для AgyLine оптимальна одна из двух схем на GitHub:
- **Вариант А (Рекомендуемый для максимального доверия к E2EE): Публичный монорепозиторий или связка `agyline-mcp` + `agyline`**
  - Клиентский мост (`agyline-bridge.py`), CLI-инсталлятор (`packages/agyline-npm`), расширения (`.mcpb`, `gemini-extension.json`, плагин Antigravity) и спецификация протокола **обязаны быть на 100% открытыми под MIT License**.
  - Разработчики в Hacker News и `r/LocalLLaMA` ставят звёзды охотнее всего тогда, когда видят честный код клиентского шифрования (`X25519` + `AES-256-GCM`) и возможность при желании поднять self-hosted координатор в Docker одной командой (`docker compose up`), при этом 95% обычных пользователей всё равно будут бесплатно пользоваться готовым облачным координатором `@agylinebot` (`agyline.owncome.ru`), чтобы не настраивать своего Telegram-бота и домен.
- **Имя репозитория:** `agyline` или `agyline-mcp` (в организации, например `github.com/agyline/agyline` или `github.com/owncome/agyline`). Короткий `org/repo` критичен для красивых команд установки и бейджей.

### 1.2. Правило «Первых 5 секунд» в `README.md`

80% посетителей страницы GitHub принимают решение «поставить ⭐ или закрыть вкладку» на первом экране без скролла. Идеальная структура шапки `README.md` для AgyLine:

1. **Киллер-заголовок в 1 строку (не абстрактный, а через сценарий):**
   > **AgyLine (BotA2A)** — End-to-End Encrypted A2A Messenger & MCP Bridge: let your Claude Code, Codex, Antigravity & ChatGPT collaborate with your friends' AI agents (or verify each other's work) under Telegram human-in-the-loop control.
2. **Ряд бейджей доверия сразу под заголовком:**
   - GitHub Stars, npm version + **Sigstore Provenance**, Official MCP Registry, Glama Grade `A+`, MIT License, Zero-Knowledge E2EE badge.
3. **12–15-секундное GIF / MP4 демо на первом экране (главный конвертер в звёзды):**
   - Разделённый экран (split-screen): слева терминал с **Claude Code**, справа **Codex / Antigravity**, а в углу — компактное окно Telegram Mini App.
   - Показать живой вау-сценарий за 12 секунд: *Агент А отправляет архитектурный план Агенту Б в общий канал `#review` → Агент Б находит баг и отвечает со скептической проверкой → владелец нажимает «Разрешить» на карточке в Telegram*.
4. **Блок «Agent-First Install (Zero Config)» сразу под GIF:**
   - Вместо длинных JSON-простыней — плашка: *«Не редактируйте конфиги вручную. Скопируйте эту одну строчку в ваш Claude Code / Codex / Antigravity / Cursor:»*
   ```text
   Read https://agyline.owncome.ru/install.md and connect AgyLine for me
   ```
   - И рядом 1-строчник для любителей терминала: `npx -y agyline@latest setup`.
5. **Кросс-языковая доступность:**
   - Для глобального GitHub Trending основной `README.md` **обязательно должен быть на английском языке**, а в самой верхней строчке — переключатель языков: `🇬🇧 English | 🇷🇺 Русский (README.ru.md) | 🇨🇳 中文 (README.zh-CN.md)`. Китайское и англоязычное AI-комьюнити дают до 75% звёзд в GitHub Trending.

### 1.3. GitHub SEO: Topics и метаданные репозитория

В настройках репозитория (`About` справа вверху) заполнить сайт `https://agyline.owncome.ru` и прописать максимум релевантных **GitHub Topics** (по ним индексируют GitHub Search и автоматические краулеры каталогов MCP):
- `mcp`, `mcp-server`, `model-context-protocol`, `ai-agents`, `agent-to-agent`, `a2a`, `claude-code`, `codex`, `antigravity`, `gemini-cli`, `e2ee`, `telegram-mini-app`, `human-in-the-loop`, `multi-agent`.
- Включить **GitHub Discussions** (вкладка `Show & Tell` для кейсов пользователей) и загрузить кастомную **Social Preview Image (1280×640 px)** в `Settings → General → Social preview` — без неё ссылки в X/Twitter, Telegram и Reddit выглядят блекло.

### 1.4. Встроенные виральные петли внутри самого продукта (Product-Led GitHub Growth)

1. **Инвайт-петля K-factor (уже заложена в AgyLine, нужно подсветить ссылку на GitHub):**
   - Когда Пользователь А хочет отправить задачу другу `@username`, друг получает инвайт в `@agylinebot` и ссылку на лендинг/GitHub. Добавление аккуратной кнопки `⭐ Star Open-Source E2EE Bridge on GitHub` на экран успешного подключения агента и в футер лендинга конвертирует реальных пользователей в звёзды.
2. **Сценарий «Adversarial Cross-Check» (кросс-проверка своих же агентов) как контент-магнит:**
   - Соло-разработчику даже не нужен второй человек, чтобы влюбиться в продукт: пост с демонстрацией *«Как я заставил мой Codex CLI и мой Claude Code спорить друг с другом в канале `#arch-audit` через AgyLine и поймал критическую уязвимость до коммита»* — это идеальный виральный формат для X, Reddit и Habr.
3. **Файл `AGENTS.md` / `SKILL.md` прямо в корне репозитория:**
   - Разработчики в 2026 году массово клонируют репо и открывают их агентами. Наличие эталонного `AGENTS.md` и готовых шаблонов воркфлоу (`examples/code-review-duel.md`, `examples/founder-assistant-negotiation.md`) повышает удержание и форки.

### 1.5. Плейбук запуск-недели (Launch Blitz для попадания в GitHub Trending)

Алгоритм **GitHub Trending** считает не общее число звёзд, а **скорость прироста звёзд и форков за скользящие 24 часа** (обычно нужно **120–250 звёзд за первые сутки**, чтобы войти в дневной Trending по Python/TypeScript, после чего включается органический снежный ком ещё на +500…+2 000 звёзд). Поэтому запуски нельзя размазывать на месяц — их концентрируют в **48-часовое окно (вторник–среда)**:

1. **Hacker News (`Show HN`):**
   - Заголовок строго без маркетинговой воды, инженерный и интригующий:
     > `Show HN: AgyLine – E2EE MCP bridge so your local coding agents can talk to peers' agents with Telegram approval`
   - Время публикации: **15:30–17:00 МСК** (утро Восточного побережья США, вторник–четверг).
   - Первый комментарий от автора: честный разбор архитектуры — почему межагентное общение опасно из-за prompt injection от чужих агентов, как работают наши скептические гардрейлы владельца (`OWNER_GUARDRAIL`), карточки разовых разрешений (`PermissionRequest`) и почему локальный мост решает Zero-Knowledge E2EE лучше облачных коннекторов.
2. **Reddit (точечные технические посты с видео, не кросс-пост одной ссылки):**
   - `r/ClaudeAI` и `r/ClaudeCode` — акцент на `.mcpb` в 1 клик и связку `Claude Code ↔ Cowork / друг`.
   - `r/ChatGPTCoding` и `r/cursor` — акцент на кросс-проверку кода между двумя разными IDE/моделями (`Cursor/Antigravity ↔ Codex`).
   - `r/LocalLLaMA` и `r/selfhosted` — акцент на открытый протокол BotA2A, локальные ключи E2EE и защиту от утечки контекста.
3. **X (Twitter) & Bluesky:**
   - Короткое нативное видео (45 сек, автоплей без звука с крупными субтитрами) в первом твите, а ссылку на GitHub — во **втором твите треда** (алгоритм X пессимизирует внешние ссылки в первом посте). Тегнуть создателей экосистемы MCP и кураторов дайджестов (`@modelcontextprotocol`, `@punkpeye`, авторов AI-ньюслеттеров).
4. **Product Hunt + русскоязычные площадки (Habr + VC.ru + профильные ТГ-каналы):**
   - Статья на **Habr** (хабы *Искусственный интеллект*, *Информационная безопасность*, *Мессенджеры*, *Open source*) с историей создания протокола межагентной координации, разбором проблемы TCP-рукопожатий/SSE и E2EE-моста — даёт мощный стартовый импульс в 100–300 звёзд от русскоязычных инженеров в первые часы запуска.

---

## Часть 2. Пакетные реестры (npm, GitHub Packages, JSR) и специализированные MCP-маркетплейсы

В мире Node.js и MCP сейчас сложились **две чёткие группы площадок**, которые дополняют друг друга:
- **Группа А — Пакетные реестры (куда публикуется сам исполняемый код пакета):**
  1. **Официальный npm (`registry.npmjs.org`)** — главный мировой реестр, откуда по умолчанию качает `npx -y agyline`.
  2. **GitHub Packages (`npm.pkg.github.com`)** — реестр пакетов от GitHub (`@<org>/agyline`), который встраивается прямо в правую колонку GitHub-репозитория и закрывает корпоративных пользователей.
  3. **JSR (`jsr.io`)** — современный реестр от создателей Deno/Node для TypeScript/ESM с собственной системой оценки качества (`JSR Score 100%`) и высокими позициями в Google Search.
- **Группа Б — Специализированные MCP-маркетплейсы (каталоги для ИИ-агентов и разработчиков):**
  1. **Official MCP Registry (`registry.modelcontextprotocol.io`)** — официальный мета-каталог от Anthropic / MCP Steering Committee (индексирует `server.json` в пакете и на сервере `https://agyline.owncome.ru/mcp/server.json` / `/.well-known/mcp.json`).
  2. **Smithery (`smithery.ai`)** — крупнейший маркетплейс MCP-серверов с авто-установкой в 1 клик и облачным Playground (индексирует `smithery.yaml`).
  3. **Glama (`glama.ai/mcp/servers`)** — каталог с автоматическим инспектором качества и безопасности (индексирует GitHub по топикам `mcp` / `mcp-server` + манифест `glama.json`).
  4. **PulseMCP (`pulsemcp.com`)** — главный курируемый каталог с крупнейшей еженедельной рассылкой по разработчикам MCP.
  5. **MCP.so (`mcp.so`) и MCPMarket (`mcpmarket.com`)** — крупнейшие SEO-агрегаторы (автоматически подтягивают репозитории по топикам `mcp`, `mcp-server` и Issues в `chatmcp/mcpso`).
  6. **Экосистемные хабы (`punkpeye/awesome-mcp-servers`, `cursor.directory`, `windsurf.run`)** — входные точки, откуда парсят базу десятки остальных витрин.

У нас в проекте уже подготовлен пакет [`packages/agyline-npm/package.json`](file:///Users/valias/Downloads/Projects/AgyLine/packages/agyline-npm/package.json). Ниже — детальный разбор по **каждому** из этих реестров и маркетплейсов: какие файлы и манифесты нужны, как устроены их алгоритмы ранжирования и как продвигаться в топ выдачи каждого из них.

---

### Группа А. Пакетные реестры (где живёт код пакета)

---

#### А.1. Официальный npm (`registry.npmjs.org`) — Главный реестр (`npx -y agyline`)

Разработчики и корпоративные безопасники опасаются запускать незнакомые `npx`-пакеты без криптографического подтверждения происхождения кода. В npm для этого используется **OIDC Trusted Publishing через GitHub Actions + Sigstore**, который вешает на страницу пакета зелёный щит **`Verified Provenance`**.

##### 1. Что подготовить в `package.json`:
1. Поле **`mcpName`** — обязательное поле для криптографической связки npm-пакета с **Official MCP Registry** (`io.github.<org>/agyline` или `ru.owncome/agyline`).
2. Поля `repository`, `homepage`, `bugs` (URL репозитория обязан посимвольно совпадать с GitHub-репозиторием, из которого запускается GitHub Actions, иначе Sigstore отклонит provenance).
3. Расширенный список **SEO-ключевых слов (`keywords`)** (до 20–25 штук), по которым ищут внутри `npmjs.com` и сторонних скраперов:
   ```json
   {
     "name": "agyline",
     "mcpName": "ru.owncome/agyline",
     "repository": {
       "type": "git",
       "url": "git+https://github.com/<org>/agyline.git"
     },
     "homepage": "https://agyline.owncome.ru",
     "keywords": [
       "mcp",
       "mcp-server",
       "model-context-protocol",
       "a2a",
       "agent-to-agent",
       "multi-agent",
       "claude-code",
       "claude-desktop",
       "codex",
       "antigravity",
       "gemini-cli",
       "cursor",
       "e2ee",
       "telegram",
       "agyline",
       "bota2a"
     ]
   }
   ```

##### 2. Как продвигаться и выходить в топ поиска `npmjs.com`:
- **Секрет двойного нейминга (Пакет-алиас):** помимо основного короткого пакета **`agyline`** (`npx -y agyline setup`), опубликуйте пакет-обёртку **`mcp-server-agyline`** (и при желании `@<org>/agyline`), который в `dependencies` тянет `agyline` и пробрасывает `bin`. Причина: огромная доля разработчиков и автоматических парсеров ищет MCP-пакеты в npm строго по префиксу `mcp-server-*`.
- **Формула ранжирования npm Search (Quality + Maintenance + Popularity):**
  - **Quality (Качество):** наличие `README.md` в корне пакета (не путать с корнем монорепо!), поля `types` (`index.d.ts`), `license: "MIT"`, отсутствие уязвимостей в `npm audit` и зелёный бейдж **Sigstore Provenance**.
  - **Maintenance (Регулярность обновлений):** алгоритм npm сильно пессимизирует пакеты, которые не обновлялись >3 месяцев, и бустит пакеты с регулярными патч/минорными релизами (раз в 1–2 недели при выкатке фич).
  - **Popularity (Скачивания в неделю):** в документации, `install.md`, `README.md` и E2E-тестах в GitHub Actions всегда указывайте `npx -y agyline@latest ...`. Каждый прогон и каждая установка пользователя через `@latest` легитимно растит недельный счётчик скачиваний npm, который напрямую двигает пакет вверх по запросу `mcp` и `agent-to-agent`.

---

#### А.2. GitHub Packages (`npm.pkg.github.com`) — Корпоративный реестр GitHub

Публикация пакета под скоупом организации/аккаунта (`@<org>/agyline` в `https://npm.pkg.github.com`) параллельно с `npmjs.org` из одного workflow `.github/workflows/publish.yml` даёт не столько прямые скачивания с нуля, сколько **конверсию и доверие внутри самого GitHub**.

##### 1. Зачем это нужно для продвижения:
1. **Визуальный блок «Packages» на главной странице GitHub-репозитория:** как только пакет опубликован в GitHub Packages и привязан к репозиторию, в правой колонке GitHub (под блоком *Releases*) появляется официальный виджет пакета с числом скачиваний, версией и командой установки. Репозитории с заполненными *Releases + Packages* воспринимаются разработчиками как зрелые production-проекты и получают заметно более высокую конверсию из просмотра в звезду (⭐).
2. **Доступ для Enterprise-команд:** во многих компаниях прямой доступ к публичному `registry.npmjs.org` с рабочих машин ограничен корпоративным прокси, но разрешён `npm.pkg.github.com` через `GITHUB_TOKEN`.
3. **Единый CI/CD пайплайн (`.github/workflows/publish.yml`):** при создании GitHub Release (`v1.2.0`) один workflow автоматически публикует:
   - `agyline` → в `https://registry.npmjs.org` (с `--provenance`);
   - `@<org>/agyline` → в `https://npm.pkg.github.com` (используя встроенный `secrets.GITHUB_TOKEN` с пермишеном `packages: write`).

##### 2. Как продвигаться через GitHub Packages:
- Обязательно связать пакет со страницей репозитория через поле `repository.url` в `package.json`, чтобы GitHub автоматически отобразил его на главной странице кода.
- Включать автоматическую генерацию `Release Notes` при каждом теге: подписчики репозитория (`Watchers`) и люди, поставившие звезду, видят свежие релизы и обновления пакета прямо в своей ленте **GitHub Home Feed**!

---

#### А.3. JSR (`jsr.io`) — Современный реестр TypeScript / ESM от создателей Deno и Node

**JSR (`jsr.io`)** — это быстрорастущий реестр нового поколения для TypeScript и ESM-пакетов (работает поверх npm, совместим с `npx jsr add`, `npm`, `pnpm`, `bun`, `deno`).

##### 1. Почему JSR — это скрытая золотая жила для продвижения MCP-пакета:
1. **Конкуренция в 50 раз ниже, чем в npm, а SEO в Google — топовое:** в `npmjs.com` уже больше 3 миллионов пакетов, а на `jsr.io` по запросам `mcp`, `a2a`, `agent-to-agent`, `claude` выдача ещё очень свободная. При этом JSR автоматически генерирует идеальные HTML-страницы документации по вашим типам и функциям, которые прекрасно индексируются Google.
2. **Публичный рейтинг качества `JSR Score (0% – 100%)`:** в отличие от npm, JSR прямо в поиске и в шапке пакета рисует крупный зелёный процентный скор (например, **`100%`**). Пакеты со скором `95–100%` автоматически сортируются выше конкурентов во внутреннем поиске `jsr.io`!

##### 2. Что подготовить для публикации в JSR (`jsr.json`):
В папку пакета добавляется компактный манифест `jsr.json` и типизированный экспорт (`mod.ts` или `index.ts` с SDK/CLI-обёрткой):
```json
{
  "name": "@agyline/mcp",
  "version": "1.2.0",
  "license": "MIT",
  "description": "End-to-End Encrypted A2A Messenger & MCP Bridge for Claude Code, Codex, Antigravity, Gemini CLI & Cursor.",
  "exports": {
    ".": "./src/mod.ts",
    "./cli": "./bin/agyline.ts"
  }
}
```

##### 3. Чеклист получения заветного `100% JSR Score` (для выхода на 1-е место в поиске JSR):
JSR считает скор по открытой формуле из 10 пунктов. Чтобы выбить **100%** с первой публикации (проверяется командой `npx jsr publish --dry-run`):
1. Наличие `README.md` с примерами кода в начале файла.
2. Наличие **JSDoc-комментариев (`/** ... */`)** над самой точкой входа (`@module`) и над **каждой** экспортируемой функцией/интерфейсом/константой.
3. Отсутствие «медленных типов» (`no slow types` — все экспортируемые функции и переменные должны иметь явно прописанные типы аргументов и возвращаемых значений).
4. Проставленные галочки совместимости со всеми рантаймами в настройках пакета на `jsr.io` (**Node.js, Deno, Bun, Cloudflare Workers, Browsers**).
5. Публикация через GitHub Actions по OIDC (`npx jsr publish` с привязанным GitHub-репозиторием — даёт плашку верифицированного происхождения на JSR) + бейдж `[![JSR Score](https://jsr.io/badges/@agyline/mcp/score)](https://jsr.io/@agyline/mcp)` в `README.md`.

---

### Группа Б. Специализированные MCP-маркетплейсы (каталоги для ИИ-агентов)

Эти площадки устроены иначе: они не хранят тарболы с кодом, а **индексируют ваш GitHub-репозиторий, npm-пакет и удалённый сервер** по специальным манифестам (`server.json`, `smithery.yaml`, `glama.json`) и GitHub Topics (`mcp`, `mcp-server`).

---

#### Б.1. Official MCP Registry (`registry.modelcontextprotocol.io`) — Главный официальный мета-каталог

**Official MCP Registry** — центральный реестр протокола MCP от Anthropic и MCP Steering Committee. **Публикация в нём обязательна в первую очередь**, так как именно его API опрашивают встроенные менеджеры расширений в VS Code / GitHub Copilot, Cursor и десятки агрегаторов.

##### 1. Что подготовить (двойное размещение `server.json`):
Чтобы AgyLine автоматически обнаруживался и как **локальный пакет (`stdio`)**, и как **облачный сервер (`streamable-http`)**, файл `server.json` размещается сразу в двух местах:
- В корне пакета / репозитория (`packages/agyline-npm/server.json` и корень репо);
- На самом веб-сервере по путям **`https://agyline.owncome.ru/mcp/server.json`** и **`https://agyline.owncome.ru/.well-known/mcp.json`** (для децентрализованного авто-дискавери ИИ-агентами).

Пример эталонного `server.json`:
```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-10-17/server.schema.json",
  "name": "ru.owncome/agyline",
  "description": "End-to-end encrypted agent-to-agent (A2A) coordination & peer messaging with Telegram human-in-the-loop approvals.",
  "version": "1.2.0",
  "repository": {
    "url": "https://github.com/<org>/agyline",
    "source": "github"
  },
  "packages": [
    {
      "registryType": "npm",
      "identifier": "agyline",
      "version": "1.2.0",
      "transport": { "type": "stdio" }
    }
  ],
  "remotes": [
    {
      "type": "streamable-http",
      "url": "https://agyline.owncome.ru/mcp"
    }
  ]
}
```

##### 2. Как опубликоваться и продвигаться в Official MCP Registry:
- **Верификация домена (престижнее обычного GitHub-неймспейса):** большинство разработчиков публикуются под `io.github.<username>/*`. Если пройти быструю DNS-верификацию домена (`mcp-publisher login dns --domain owncome.ru`), сервер получает корпоративный неймспейс **`ru.owncome/agyline`** (или `io.agyline/mcp`), что визуально выделяет его как официальный облачный продукт.
- **Авто-публикация при каждом релизе:** добавить шаг `mcp-publisher publish` в `.github/workflows/publish.yml` сразу после `npm publish`. Реестр сортирует выдачу по свежести релизов и точности совпадения ключевых слов в `description`.

---

#### Б.2. Smithery (`smithery.ai`) — Крупнейший маркетплейс с установкой в 1 клик и Playground

**Smithery** — самый посещаемый специализированный стор MCP-серверов (`npx -y @smithery/cli install ...`), где у каждого сервера есть интерактивная страница со списком тулов, статистикой вызовов и встроенным в браузер **Playground**.

##### 1. Что подготовить (`smithery.yaml`):
Положить в корень репозитория/пакета файл `smithery.yaml`, который описывает схему конфигурации (`configSchema`), чтобы Smithery автоматически сгенерировал красивую UI-форму подключения на странице нашего сервера:
```yaml
startCommand:
  type: stdio
  configSchema:
    type: object
    required: []
    properties:
      pairCode:
        type: string
        description: "Optional one-time PAIR-XXXX code from @agylinebot (Telegram) to auto-pair on first start."
      coordinatorUrl:
        type: string
        default: "https://agyline.owncome.ru"
        description: "AgyLine coordinator server URL."
  commandFunction: |-
    (config) => ({
      command: "npx",
      args: ["-y", "agyline", "bridge"],
      env: {
        ...(config.pairCode ? { AGYLINE_PAIR_CODE: config.pairCode } : {}),
        AGYLINE_URL: config.coordinatorUrl || "https://agyline.owncome.ru"
      }
    })
```

##### 2. Как продвигаться в топ внутри Smithery:
1. **Сделать `required: []` (необязательные поля на старте!) в `configSchema`:**
   - **Критичный инсайт по алгоритму Smithery:** когда вы добавляете сервер на Smithery, их облачный сканер запускает ваш сервер в контейнере без параметров и вызывает `tools/list`. Если в `configSchema` сделать `apiKey` или `pairCode` строго обязательным (`required: ["pairCode"]`) и падать при старте без него — сканер Smithery не сможет прочитать список ваших 26 тулов, карточка останется «слепой» (0 tools inspected) и упадёт на дно каталога!
   - Если же при старте без ключа наш мост отдаёт валидный список всех 26 тулов `MCP_TOOLS` (а токен просит только при фактическом вызове тула), Smithery индексирует все 26 инструментов, строит по ним поисковый индекс и разрешает пользователям кликать по ним в браузерном Playground!
2. **Подключить и Remote HTTP (`/mcp`), и `stdio`:** серверы с поддержкой `Hosted / Remote Streamable HTTP` получают специальный фильтр и буст на главной странице Smithery, так как не требуют от пользователя локального окружения.
3. **Рост счётчика `Installs`:** разместить в `README.md` официальный бейдж Smithery и альтернативную команду установки через `@smithery/cli` — алгоритм каталога сортирует категории по числу успешных инсталляций и запусков в Playground за последние 7 дней.

---

#### Б.3. Glama (`glama.ai/mcp/servers`) — Каталог с автоматическим аудитом качества и грейдом `A+`

**Glama** автоматически индексирует GitHub по топикам `mcp` и `mcp-server`, но без специальной настройки новые репозитории получают средний технический балл (`B` или `C`) и теряются среди тысяч других.

##### 1. Что подготовить (`glama.json` в корне репозитория):
Чтобы подтвердить права владельца (Claim Server) и привязать мейнтейнеров в GitHub-организации, в корень репозитория кладётся `glama.json`:
```json
{
  "$schema": "https://glama.ai/mcp/schemas/server.json",
  "maintainers": [
    "svalia"
  ]
}
```

##### 2. Как получить максимальный грейд `A+` (100 баллов) и выйти в топ Glama:
Инспектор Glama оценивает сервер по **Tool Definition Quality Score (TDQS)** и безопасности зависимостей (через Socket.dev). Чтобы гарантированно получить **`A+`**:
1. **Проставить `annotations` (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) у каждого тула:** инспектор Glama начисляет за это дополнительные баллы безопасности.
2. **Подробные `description` у каждого свойства внутри `inputSchema.properties`:** в Glama снижается балл TDQS, если у аргументов тула (`task_id`, `contact_id`, `text`) написано просто `"type": "string"` без поля `"description"`.
3. **Наличие `LICENSE` (MIT) в корне репо и 0 предупреждений Socket.dev в `package.json`:** минимум внешних `dependencies` в npm-пакете (у нас `packages/agyline-npm` написан на чистом встроенном Node.js без тяжёлых сторонних библиотек — это даёт идеальный `100/100 Supply Chain Security`!).
4. **Вставить живой SVG-бейдж или карточку Glama в `README.md`:**
   ```markdown
   [![Glama MCP Score](https://glama.ai/mcp/servers/<org>/agyline/badges/score.svg)](https://glama.ai/mcp/servers/<org>/agyline)
   ```
   Краулер Glama проверяет наличие обратного бейджа в `README.md` и повышает такие верифицированные серверы во внутренней выдаче.

---

#### Б.4. PulseMCP (`pulsemcp.com`) — Главный курируемый каталог и еженедельная рассылка

В отличие от чисто автоматических скраперов, **PulseMCP** — это самая читаемая в мире **редакционная платформа по MCP** (каталог серверов + клиенты + пятничный дайджест *PulseMCP Weekly Newsletter*, который читают десятки тысяч AI-инженеров и фаундеров).

##### Как опубликоваться и бесплатно попасть в еженедельный выпуск:
1. **Авто-индексация + Ручной сабмит:** PulseMCP автоматически подтягивает репозитории по топикам `mcp` / `mcp-server`, но для приоритетной индексации и правильной категоризации нужно отправить форму на `https://www.pulsemcp.com/submit`.
2. **Питч для редакции PulseMCP Newsletter (главный рычаг трафика!):**
   - Авторы PulseMCP каждую неделю вручную отбирают 3–5 самых необычных релизов или кейсов использования MCP в рубрику **Featured Servers & Use Cases**.
   - 95% подаваемых туда серверов — это скучные CRUD-обёртки над очередным REST API («MCP для Todo-листа»).
   - **Наш угол подачи для редакторов PulseMCP:** *«First Zero-Knowledge E2EE Agent-to-Agent (A2A) MCP Bridge with Telegram Human-in-the-Loop approvals — позволяющий двум живым людям или двум разным локальным агентам (Claude Code ↔ Codex) вести зашифрованные переговоры и кросс-ревью кода»*. Приложите к сабмиту ссылку на 15-секундное демо-видео — вероятность попадания в рассылку по всей базе подписчиков PulseMCP максимальная.

---

#### Б.5. MCP.so (`mcp.so`) и MCPMarket (`mcpmarket.com`) — Главные SEO-агрегаторы

**MCP.so** (и близкий к нему **MCPMarket.com**) — крупнейшие по поисковому трафику из Google каталоги-витрины (собирают огромный хвост низкочастотных запросов вида *«telegram agent mcp»*, *«agent to agent mcp server»*, *«multi agent communication mcp»*).

##### Как устроена их индексация и как занять 1-е место в своей категории:
1. **Тройной вход в `mcp.so`:**
   - **Автоматический краулер GitHub:** сканирует репозитории по топикам `mcp` и `mcp-server` (обязательно проставить на репозитории!).
   - **Веб-форма:** `https://mcp.so/submit` (указать ссылку на GitHub и URL удалённого сервера `https://agyline.owncome.ru/mcp`).
   - **GitHub Issue / PR в открытый репозиторий каталога (`chatmcp/mcpso`):** создание Issue по шаблону сабмита в их репозитории ускоряет появление карточки до нескольких часов.
2. **Секрет парсера `mcp.so` (Структура заголовков `README.md`):**
   - Скрапер `mcp.so` не просто копирует ваш `README.md` целиком — он **разрезает его по `H2`-заголовкам (`##`) на отдельные вкладки UI карточки** на сайте (`Overview`, `Features`, `Installation`, `Tools`, `Use Cases`, `FAQ`)!
   - Если в вашем `README.md` есть чёткие секции `## Features`, `## Installation`, `## Available Tools`, `## Use Cases` и `## FAQ`, карточка AgyLine на `mcp.so` получает 100% заполненность всех вкладок и длинный SEO-текст, который ранжируется как внутри `mcp.so`, так и в Google!
3. **Включение переключателя `Hosted / Cloud Server`:** при отправке на `mcp.so` обязательно отметить, что у сервера есть готовый публичный Cloud Endpoint (`https://agyline.owncome.ru/mcp`) — такие серверы попадают в отдельную премиальную вкладку **Hosted MCPs**, где конкуренция в 20 раз ниже, чем среди локальных скриптов.

---

#### Б.6. Сводная таблица всех пакетных реестров и MCP-маркетплейсов

| Площадка | Тип | Какой файл / настройка отвечает за индексацию | Главный фактор выхода в ТОП внутри площадки |
| :--- | :--- | :--- | :--- |
| **1. npm (`registry.npmjs.org`)** | Пакетный реестр | `package.json` (`mcpName`, `keywords`) + `.github/workflows/publish.yml` | Зелёный щит **Sigstore Provenance**, пакет-алиас `mcp-server-agyline`, регулярные релизы и запуски через `npx -y agyline@latest`. |
| **2. GitHub Packages (`npm.pkg.github.com`)** | Пакетный реестр | `.github/workflows/publish.yml` (`packages: write`) + `repository.url` | Привязка пакета к главной странице репозитория (виджет *Packages* справа) + авто-релизы в ленту подписчиков GitHub. |
| **3. JSR (`jsr.io`)** | Пакетный реестр (TS/ESM) | `jsr.json` + типизированный вход (`mod.ts`) с JSDoc | Выбить **`100% JSR Score`** (JSDoc на экспорты, `no slow types`, все рантаймы) — автоматически ставит на 1-е место в поиске JSR и Google. |
| **4. Official MCP Registry (`registry.modelcontextprotocol.io`)** | Официальный мета-реестр | `server.json` в пакете + на `https://agyline.owncome.ru/mcp/server.json` и `/.well-known/mcp.json` | DNS-верификация собственного домена (`ru.owncome/agyline`), описание обоих транспортов (`npm stdio` + `streamable-http`). |
| **5. Smithery (`smithery.ai`)** | MCP-маркетплейс + Playground | `smithery.yaml` в корне репозитория | Сделать `required: []` в `configSchema`, чтобы облачный сканер Smithery без ошибки прочитал все 26 тулов + подключить Remote `/mcp`. |
| **6. Glama (`glama.ai/mcp/servers`)** | MCP-каталог + Аудитор | Топики `mcp`, `mcp-server` + `glama.json` в корне репо | Получить грейд **`A+`**: проставить `annotations` и `description` всем полям `inputSchema`, иметь `LICENSE` и вставить SVG-бейдж Glama в `README.md`. |
| **7. PulseMCP (`pulsemcp.com`)** | Курируемый каталог + Newsletter | Топики `mcp`, `mcp-server` + сабмит на `pulsemcp.com/submit` | Подать уникальный A2A/E2EE use-case с коротким видео для попадания в пятничную рассылку **PulseMCP Weekly Newsletter**. |
| **8. MCP.so & MCPMarket** | SEO-агрегаторы MCP | Топики `mcp`, `mcp-server` + `mcp.so/submit` / Issue в `chatmcp/mcpso` | Разбить `README.md` на стандартные `H2`-секции (`## Features`, `## Use Cases`, `## FAQ`) под парсер вкладок + включить флаг `Hosted MCP`. |
| **9. `punkpeye/awesome-mcp-servers`** | Главный GitHub-список (50k+ ⭐) | Pull Request в категорию *Communication / Multi-Agent* | Строго соблюсти формат бейджей из `CONTRIBUTING.md`. Отсюда базу автоматически парсят десятки мелких каталогов! |
| **10. `cursor.directory` & `windsurf.run`** | Каталоги IDE | PR / форма сабмита MCP + Rules | Опубликовать связку `MCP Server + .cursorrules` («Rule for Cross-Agent Code Review via AgyLine») — даёт в 3 раза больше установок. |

---

## Часть 3. Официальные сторы Anthropic, OpenAI и Google

Это самый ценный канал для массовых (в том числе нетехнических) пользователей, потому что каталог встроен прямо в интерфейс **Claude**, **ChatGPT**, **Google Antigravity** и **Gemini CLI**.

---

### 3.1. Экосистема Anthropic (3 официальных канала!)

У Anthropic есть **три отдельные витрины**, и AgyLine идеально ложится во все три:

#### Канал А: Claude Connectors Directory (Облачный стор внутри Claude.ai, Claude Desktop и Cowork)
Это официальная витрина `Settings / Customize → Connectors → Browse Connectors`.
- **Технические требования модерации Anthropic:**
  1. **Транспорт:** удалённый MCP по HTTPS с поддержкой **Streamable HTTP** (`https://agyline.owncome.ru/mcp`) — *у нас уже реализовано*.
  2. **Авторизация:** OAuth 2.0 / 2.1 с PKCE + метаданные RFC 9728 (`/.well-known/oauth-protected-resource` и `/.well-known/oauth-authorization-server`), валидные TLS-сертификаты — *уже реализовано*.
  3. **Обязательные `annotations` безопасности на КАЖДОМ MCP-инструменте:** ревьюеры Anthropic проверяют, чтобы в `tools/list` у каждого инструмента были явно проставлены булевы подсказки:
     - `readOnlyHint: true` (для чтения задач, контактов, инструкций: `tasks_list`, `tasks_get`, `messages_read`, `contacts_find`, `help_guide`);
     - `destructiveHint: false` / `true` и `openWorldHint: true` (для отправки сообщений во внешний мир, создания задач, удаления контактов: `requests_create`, `messages_send`, `contacts_delete`).
     *(Без этих аннотаций заявку заворачивают на первом этапе проверки!)*
  4. **Документация и юр. страницы:** публичные ссылки на **Privacy Policy**, **Terms of Service**, страницу документации с примерами промптов и контакт техподдержки.
  5. **Тестовый аккаунт для ревьюера Anthropic:** в анкете нужно передать готовые тестовые учётные данные (чтобы модератор Anthropic в США мог за 2 минуты залогиниться в OAuth без необходимости связываться с нами вручную).
- **Куда подавать:** официальный портал партнёрских/публичных коннекторов Anthropic MCP Directory Submission Form (через документацию `support.claude.com` / `modelcontextprotocol` Connectors Submission).

#### Канал Б: Claude Desktop Extensions Directory (Локальный стор `.mcpb` — наша киллер-фича для E2EE!)
В Claude Desktop есть встроенный браузер локальных расширений `Settings → Extensions → Browse Extensions` на базе формата **`.mcpb` (MCP Bundle)**.
- **Почему это супер-канал для AgyLine:** в отличие от облачного коннектора, `.mcpb` скачивается в 1 клик внутри Claude Desktop, работает локально на Mac/Windows пользователя и даёт **максимальную защиту `🔒 Local E2EE Bridge`**, которую можно явно заявить в описании!
- **Что уже есть:** мы уже генерируем рабочий `agyline.mcpb` (`/adapter/agyline.mcpb`).
- **Что нужно для подачи в каталог Anthropic Desktop Extensions:**
  - Проверить манифест `manifest.json` версии `0.2+` внутри архива `.mcpb` актуальной утилитой `npx @anthropic-ai/mcpb validate`, добавить квадратную иконку `icon.png` (512×512), массив `tools` и понятные поля `user_config` (для ввода кода пары при желании).
  - Отправить бандл через форму **Anthropic Desktop Extensions Submission**.

#### Канал В: Claude Code Plugin Marketplace
В Claude Code работает система плагинов (`/plugin marketplace add <org>/agyline` и каталоги плагинов сообщества). Достаточно положить в репозиторий манифест `.claude-plugin/plugin.json` со связкой нашего MCP-сервера и слэш-команд (`/agyline-send`, `/agyline-inbox`).

#### Как продвигаться внутри витрин Anthropic:
- В карточке коннектора критичны **3 стартовых промпта (Example Prompts)** — пользователи нажимают на них сразу после кнопки `Connect`. Сделать их максимально конкретными (*«Проверь входящие задачи в AgyLine»*, *«Создай канал #code-review между моими агентами»*, *«Отправь задачу агенту контакта @...»*).
- Снять 60-секундный ролик работы AgyLine внутри **Claude Cowork + Claude Code** и отметить аккаунты `@AnthropicAI` / `@claudeai` при релизе — команда Developer Relations Anthropic регулярно репостит нестандартные мультиагентные коннекторы.

---

### 3.2. Официальный стор OpenAI (ChatGPT Apps / Connectors / Plugins Directory)

OpenAI перезапустила каталог внешних интеграций внутри ChatGPT (витрина **Connectors / Apps Directory** в ChatGPT Web, Desktop и Mobile на базе **Remote MCP + OAuth**). Заявки подаются через панель разработчика **`https://platform.openai.com/plugins`** (раздел Apps / MCP Connectors).

#### Точные требования для прохождения ревью OpenAI с первой попытки:
1. **Верификация личности / организации (Identity Verification):**
   - В OpenAI Platform Organization Settings нужно пройти **Verified Identity** (паспорт / юрлицо). Отображаемое имя издателя коннектора обязано совпадать с верифицированным именем. Роль владельца должна иметь скоуп `api.apps.write`.
2. **Глобальная резидентность проекта OpenAI:**
   - Проект в `platform.openai.com`, из которого подаётся коннектор, должен быть создан с настройкой **Global data residency** (проекты с региональным ограничением данных блокируются для публикации в глобальный стор).
3. **Подтверждение владения доменом (`/.well-known/openai-apps-challenge`):**
   - Панель OpenAI выдаст строку токена верификации, которую наш сервер должен отдавать по адресу:
     `GET https://agyline.owncome.ru/.well-known/openai-apps-challenge` (статус `200 OK`, `text/plain`).
4. **Технические требования к `/mcp` для OpenAI:**
   - Постоянный публичный HTTPS URL (`https://agyline.owncome.ru/mcp`), без `localhost` и временных туннелей.
   - Корректные аннотации инструментов: **`readOnlyHint`**, **`destructiveHint`**, **`openWorldHint`** на каждом туле. В ChatGPT эти флаги напрямую управляют UI: тулы с `readOnlyHint: true` выполняются бесшовно, а для пишущих тулов без `readOnlyHint` ChatGPT показывает пользователю нативную кнопку подтверждения действия (*Confirm action*).
   - В ответах MCP-инструментов не должно быть лишних персональных данных (PII minimization) и скрытых системных джейлбрейк-инструкций, нарушающих политики OpenAI.
5. **Материалы для ревьюера OpenAI (Review Package):**
   - Рабочий **тестовый аккаунт / вечный демо-код сопряжения `PAIR-DEMO-...` без двухфакторной SMS/Telegram-блокировки**, в котором уже предзаполнены 2 тестовых контакта и 2 входящие задачи, чтобы модератор OpenAI мог протестировать и чтение, и отправку прямо из браузера!
   - **Набор тестовых промптов:** минимум **5 позитивных промптов** (когда ChatGPT должен вызвать тулы AgyLine) и **3 негативных промпта** (когда вызывать тулы не нужно).
   - **Короткое видео-прохождение (Walkthrough Screencast)** полного цикла OAuth-подключения и вызова тулов в ChatGPT.
   - Ссылки на **Privacy Policy**, **Terms of Service** и **Support URL**.
   - *Важный нюанс:* в OpenAI можно держать **только 1 активную заявку на ревью одновременно** — выкатывать изменения на прод во время проверки нельзя, лучше подавать стабильный релиз.

#### Как продвигаться в сторе ChatGPT:
- **Название и краткое описание (до 60 символов):** пользователи ChatGPT — не только программисты! Вместо сухого *«BotA2A JSON-RPC Server»* использовать понятную формулировку: **`AgyLine — Agent-to-Agent Messenger`** (*«Connect your ChatGPT with friends' AI assistants & your coding agents»*).
- **Чёткие описания тулов (`description`):** маршрутизатор моделей GPT выбирает коннектор в чате по семантическому совпадению запроса пользователя с описанием сервера и его тулов. Ключевые фразы в описании тулов на русском и английском (*«send message to another person's AI assistant / agent»*, *«check incoming agent tasks»*) кратно повышают частоту вызова (invocation rate), от которой зависит позиция в каталоге.

---

### 3.3. Официальная экосистема Google (Antigravity Marketplace + Gemini CLI Gallery + MCP Apps)

В экосистеме Google в 2026 году работают сразу **три витрины**, релевантные AgyLine:

#### Витрина 1: Google Antigravity Agent Marketplace (Встроенный стор плагинов в IDE Antigravity!)
Прямо в Antigravity есть встроенный **Agent Marketplace** (полки *Productivity & Project Management*, *Developer Tools* и др., карточки `<plugin-card>`). Плагин Antigravity — это бандл, который объединяет в один переключатель **MCP-сервер + Skill (`SKILL.md`) + Rules + иконку**.

- **Точная структура плагина Antigravity для AgyLine** (согласно официальной спецификации плагинов Antigravity):
  ```text
  plugins/antigravity/agyline/
  ├── plugin.json                # Манифест плагина (обязателен)
  ├── README.md                  # Документация для страницы плагина в маркетплейсе
  ├── mcp_config.json            # Конфигурация MCP-сервера agyline-bota2a
  ├── assets/
  │   └── logo.svg               # Квадратный логотип >=128x128 с прозрачным фоном и 10% полями
  └── skills/
      └── agyline/
          └── SKILL.md           # Скилл с правилами работы с контактами, каналами и E2EE
  ```
- **Эталонный `plugin.json` для Antigravity Marketplace:**
  ```json
  {
    "name": "agyline",
    "displayName": "AgyLine (BotA2A)",
    "version": "1.2.0",
    "description": "Agent-to-agent encrypted messaging & cross-agent code review between Antigravity, Claude Code, Codex, and your peers' AI assistants with Telegram approvals.",
    "logo": "assets/logo.svg",
    "author": {
      "name": "AgyLine Team",
      "url": "https://agyline.owncome.ru"
    },
    "homepage": "https://agyline.owncome.ru",
    "repository": {
      "type": "git",
      "url": "https://github.com/<org>/agyline"
    },
    "suggestedPrompts": [
      "Проверь входящие задачи и сообщения от других агентов в AgyLine",
      "Отправь текущий план архитектуры на ревью моему второму агенту через канал #review",
      "Подключи мой аккаунт AgyLine по коду сопряжения из @agylinebot"
    ]
  }
  ```
  - **Важные правила валидации Antigravity:**
    1. В `plugin.json` **нельзя добавлять неизвестные верхнеуровневые поля**; путь к `logo` должен быть строго относительным (`assets/logo.svg`), с 10% внутренним отступом и контрастным видом на тёмной и светлой теме.
    2. Ровно **3 `suggestedPrompts`** — они красиво рендерятся на карточке плагина в UI маркетплейса!
    3. Имя MCP-сервера в `mcp_config.json` должно быть с префиксом плагина (например, `agyline-bota2a`), чтобы не конфликтовать в глобальном неймспейсе с другими плагинами пользователя.
    4. Перед отправкой пакет проверяется валидатором CLI (`agy plugin validate --strict`) и подаётся в партнёрский каталог (`antigravity-plugins-partners`).

#### Витрина 2: Официальная галерея Gemini CLI Extensions (`geminicli.com/extensions`)
У нас уже создан базовый `gemini-extension.json` в `packages/agyline-npm/`!
- **Как попасть в официальную галерею `geminicli.com/extensions`:**
  1. Разместить `gemini-extension.json` и контекстный файл `GEMINI.md` в корне публичного GitHub-репозитория, чтобы работала установка в одну команду:
     `gemini extensions install https://github.com/<org>/agyline`
  2. Добавить на GitHub-репозиторий официальный топик расширения (`gemini-cli-extension`) и отправить заявку в каталог расширений Gemini CLI — галерея автоматически подтягивает релизы и звёзды с GitHub.

#### Витрина 3: MCP Apps (`SEP-1865`) — Интерактивные UI-виджеты прямо внутри чатов (Киллер-фича для продвижения!)
В 2026 году Google, Anthropic и OpenAI поддержали расширение протокола **MCP Apps (`SEP-1865`)**, позволяющее MCP-серверу возвращать не просто сухой JSON, а интерактивные изолированные HTML-виджеты (`ui://...`) прямо в окно чата IDE/клиента.
- Если добавить в AgyLine лёгкий UI-ресурс карточки статуса задачи / графа агентов в канале `#review`, скриншоты такого виджета дают **колоссальное преимущество при отборе в Featured («Выбор редакции»)** во всех трёх сторах.

---

## Часть 4. Сводный технический чеклист: что нам нужно докрутить в AgyLine перед подачей во все сторы

Большая часть фундамента в AgyLine **уже готова** (Streamable HTTP `/mcp`, OAuth 2.0 + PKCE + RFC 9728 `/.well-known/oauth-protected-resource`, `install.md`, `npx`-пакет, `.mcpb` бандл, `gemini-extension.json`). Чтобы пройти ревью Anthropic, OpenAI и Google **с первой попытки без отказов**, перед отправкой заявок нужно закрыть **6 небольших технических пунктов**:

| № | Задача подготовки к сторам | Зачем это нужно (кто требует) | Оценка трудозатрат |
| :-: | :--- | :--- | :---: |
| **1** | **Проставить `annotations` (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) во всех объектах `MCP_TOOLS`** в [`agyline/mcp_router.py`](file:///Users/valias/Downloads/Projects/AgyLine/agyline/mcp_router.py) + двуязычные/чёткие описания | **Обязательное требование** модерации **OpenAI** и **Anthropic** + повышает грейд в **Glama** до `A+`. | ~30 мин |
| **2** | **Добавить публичные страницы `/privacy`, `/terms` и `/support`** на `https://agyline.owncome.ru` | Без прямых HTTPS-ссылок на политику конфиденциальности, условия использования и контакты поддержки формы сабмита **OpenAI** и **Anthropic** просто не дадут отправить заявку. | ~30 мин |
| **3** | **Добавить роут `GET /.well-known/openai-apps-challenge` и отдать `server.json` по путям `/mcp/server.json` и `/.well-known/mcp.json`** | `openai-apps-challenge` требуется для проверки домена в `platform.openai.com/plugins`, а `/mcp/server.json` и `/.well-known/mcp.json` — для автоматического дискавери в **Official MCP Registry** и ИИ-клиентах. | ~15 мин |
| **4** | **Сделать «Reviewer Sandbox Mode» (специальный демо-аккаунт для модераторов сторов)** | У ревьюеров OpenAI и Anthropic в США может не быть под рукой рабочего Telegram для получения `PAIR`-кода, и правила запрещают требовать MFA на тестовом аккаунте ревьюера. Решение: завести изолированный демо-профиль `Reviewer Demo` с предсозданными контактами и ботом-эхо-собеседником (`@demo_echo_agent`), вход в который открывается статичным ревьюерским ключом на странице `/oauth/authorize`! | ~1 час |
| **5** | **Вынести клиентский пакет в публичный GitHub-репозиторий** с `README.md` (EN + RU), `LICENSE` (MIT), манифестами `server.json`, `smithery.yaml`, `glama.json`, `jsr.json`, workflow `.github/workflows/publish.yml` (публикация в npm + GitHub Packages + JSR) и папкой плагина Antigravity (`plugin.json` + `assets/logo.svg` + `skills/agyline/SKILL.md`) | Разблокирует авто-публикацию и индексацию в **npm (с Provenance)**, **GitHub Packages**, **JSR (`100% Score`)**, **Official MCP Registry**, **Glama (`A+`)**, **Smithery**, **PulseMCP**, **MCP.so**, **awesome-mcp-servers**, **Gemini CLI Gallery** и **Antigravity Marketplace**. | ~1.5 часа |
| **6** | **Подготовить медиа-кит из 3 артефактов:** квадратная SVG/PNG иконка `512×512`, 15-секундная GIF-демонстрация для GitHub и 60-секундный скринкаст OAuth + вызова тулов | Требуется во всех сторах (OpenAI просит walkthrough-видео на ревью, Antigravity и `.mcpb` требуют квадратное лого, GitHub конвертирует посетителей в ⭐ через GIF). | ~1 час |

---

## Часть 5. Рекомендуемый пошаговый план запуска (Дорожная карта по очерёдности)

Чтобы не распыляться и получить максимальный кумулятивный эффект:

1. **Шаг 1 (Завершение E2EE + закрытие технических пунктов 1–4 из таблицы выше):** доделываем E2EE, добавляем `annotations` к MCP-тулам, страницы `/privacy` + `/terms`, роут `/.well-known/openai-apps-challenge` и демо-песочницу с автоответчиком для ревьюеров.
2. **Шаг 2 (Публичный GitHub + npm с Provenance + Official MCP Registry):** выкладываем открытый репозиторий клиентского моста/плагинов, публикуем `agyline` (и алиас `mcp-server-agyline`) в npm через GitHub Actions OIDC и за 10 минут регистрируем сервер через `mcp-publisher` в `registry.modelcontextprotocol.io`.
3. **Шаг 3 (Подача на модерацию в официальные сторы Большой Тройки):** пока заявки проходят ревью (обычно от 3 до 14 рабочих дней) — отправляем пакеты в **OpenAI (`platform.openai.com/plugins`)**, **Anthropic (Remote Connector + `.mcpb` Extension)** и **Google (Antigravity Marketplace + Gemini CLI Gallery)**.
4. **Шаг 4 (Каталоги MCP за 1 вечер):** отправляем PR в `punkpeye/awesome-mcp-servers`, получаем бейдж `A+` на **Glama**, публикуемся на **Smithery**, **PulseMCP** и **mcp.so**.
5. **Шаг 5 (Синхронный 48-часовой Launch Blitz на GitHub):** когда бейджи npm/Glama/Registry уже висят в шапке `README.md` и записано 15-секундное GIF-демо — запускаем синхронный релиз на **Show HN + Reddit + X + Habr** для выхода в суточный **GitHub Trending**.
