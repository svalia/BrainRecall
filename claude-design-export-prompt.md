# Экспорт проекта Claude Design в архив для дев-агента

Используй, когда нужно выгрузить любой канвас Claude Design (артефакт типа Design со страницами и артбордами `*.dc.html`) в локальный zip-архив, по которому дев-агент сможет вести разработку: PNG всех экранов и состояний, статический HTML без шаблонов, токены и CSS дизайн-системы, ассеты, шрифты, `SCREENS.md` и `AGENTS.md`.

## Вход
- Ссылка на артефакт Design (claude.ai/artifact/…). Если её не дали — найди через Artifact `action: "list"` (тип Design) и уточни у пользователя, какой проект.
- Опционально: ТЗ / документы проекта (для `AGENTS.md`).

## Результат
`<Project>-design.zip`, внутри папка `<Project>-design/`:

| Путь | Что |
|---|---|
| `AGENTS.md` | инструкция для дев-агента (пишешь сам, шаг 7) |
| `README.md` | коротко: что в архиве и куда положить |
| `SCREENS.md`, `boards.json` | все артборды по страницам: варианты, PNG, HTML, переходы, текст |
| `screenshots/` | PNG каждого артборда × каждый вариант настроек (тема, состояния) |
| `rendered/` | статический HTML (шаблоны подставлены), открывается офлайн |
| `canvas/` | исходники `*.dc.html`, общий CSS, `canvas.json` |
| `design-system/` | `tokens.css`, `tokens.json`, полный CSS |
| `assets/` | ассеты из хранилища артефакта + `fonts/` |

## Шаги

Рабочая папка: `$W` = новая папка в scratchpad. Скрипты — в `$W/tools`, проект — в `$W/<Project>-design`.

1. **Список файлов.** Artifact `action: "list"`, `url`, `scope: "files"`. Нужны все пути, которые начинаются с `project/` (артборды `*.dc.html`, общий CSS, `canvas.json`, прочие файлы проекта). Файлы `artifact-type/*`, `index.html`, `SKILL.md` — платформа, их НЕ берём.
2. **Скачать проект.** Artifact `action: "read"`, `url`, `paths: [все project/…]` (до 256 за вызов), `out_dir: "$W/live"`. Скопируй `$W/live/project` → `<Project>-design/canvas`.
3. **Скачать ассеты.** Artifact `action: "list"`, `url`, `scope: "assets"` (продолжай по `after`, пока есть) — даёт id, тип, размер и sha256, но не исходные имена. Скачай каждый: Artifact `action: "read"`, `url`, `paths: [id, id, …]` (если `paths` с id не принимается — по одному через `path: "<id>"`), `out_dir: "<Project>-design/assets/store"`; файлы сохраняются как `<id>.<ext>`.
   Имена: если у пользователя есть исходный пакет ассетов (zip дизайнера), посчитай sha256 его файлов, сопоставь с sha256 из листинга и запиши `assets/store/names.json` вида {"<id>": "исходное-имя.png"}; сам пакет положи в `assets/` рядом.
   Затем `python3 -I tools/dc-assets.py <Project>-design/canvas <Project>-design/assets/store` — все `/_blob/<id>` в HTML/CSS станут относительными путями. Если скрипт сообщил `missing` — эти id не нашлись; скажи пользователю.
4. **Шрифты.** `cd tools && npm init -y >/dev/null && node dc-fonts.js ../<Project>-design/canvas ../<Project>-design/assets/fonts` — подтягивает Google Fonts из npm (@fontsource) для офлайна. Шрифты не из Google — перечисли в README как внешние.
5. **Рендер.** `cd tools && node dc-export.js ../<Project>-design/canvas ../<Project>-design ../<Project>-design/assets/fonts/fonts.css`. Нужен Playwright (`require('playwright')`; в облачной среде он предустановлен — не переустанавливай). Скрипт: инлайнит маленькие картинки из CSS в data URI (иначе маски-иконки не работают с file://), для каждого артборда рендерит вариант по умолчанию + все опции enum-настроек (`theme` → `--dark`, прочие → `--<настройка>-<n>-<опция>`), пишет `rendered/*.html`, `screenshots/*.png`, `boards.json`. Строки `renderVals error` в логе = артборд отрисован без данных: открой его PNG и проверь.
6. **Справочник.** `python3 -I tools/dc-screens-md.py <Project>-design` → `SCREENS.md`.
7. **Дизайн-система.** Найди в общем CSS блок(и) с CSS-переменными для светлой и тёмной темы (обычно корневой класс артборда и его тёмный модификатор). Выгрузи их в `design-system/tokens.json` ({"light": {…}, "dark": {…}}) и `design-system/tokens.css` (`:root` + `[data-theme="dark"]`); скопируй полный CSS в `design-system/` (пути `../assets/...` остаются рабочими — папка на том же уровне, что `canvas/`).
8. **AGENTS.md** — пишешь по факту проекта (прочитай артборды карт/флоу/компонентов/токенов, заметки из `canvas.json`, ТЗ если есть):
   - с чего начать: `SCREENS.md` → картинки → `rendered/` → `design-system/`; какие артборды — карты (архитектура, флоу, оболочка, компоненты, токены);
   - таблица структуры архива;
   - **что на макетах служебное**: аннотации, safe-area/платформенные слои, пометки haptic/анимаций, ссылки-«прототип», заглушки ассетов, подписи над состояниями, плейсхолдеры `[…]`;
   - словарь ключевых классов CSS (раскладка, кнопки, поверхности, формы, навигация, специфичные компоненты) и как подключать иконки/иллюстрации;
   - правила продукта, которые легко нарушить (навигация «Назад», адаптив, доступность, запреты из ТЗ);
   - «ТЗ важнее макета; расхождения фиксируй, не исправляй молча».
9. **README.md** — 10 строк: что внутри, «агенту — начать с AGENTS.md», куда положить (например `docs/design/`), чего ещё нет (недоделанные ассеты).
10. **Проверка.** Открой 3–5 PNG (корень приложения в светлой и тёмной, экран со списком/`sc-for`, экран с enum-вариантами) — данные подставлены, иконки и шрифты на месте, нет `{{`. `grep -l "{{" rendered/*.html` — пусто. Открой один `rendered/*.html` через file:// без сети — выглядит так же.
11. **Упаковка и выдача.** `zip -qr -9 <Project>-design.zip <Project>-design`, отправь файл пользователю (SendUserFile). Если сессия связана с компьютером пользователя — дополнительно положи распакованную папку туда, куда он скажет.

## Подводные камни
- Не публикуй ничего в артефакт: экспорт только читает его.
- Если пользователь недавно правил канвас — всегда читай файлы заново (шаг 2), а не бери локальные копии.
- Артборд может переполняться по высоте — PNG снимается `fullPage`, это видно; сообщи о таких местах пользователю, не правь молча.
- Глифы-символы (◐, ‖ и т. п.) могут рендериться запасным шрифтом — это особенность шрифта, не экспорта.

## Скрипты

### tools/dc-export.js
```js
// dc-export.js — renders Claude Design canvas artboards (*.dc.html) into static HTML + PNG.
// Usage: node dc-export.js <canvasDir> <outDir> [fontsCssPath]
//   canvasDir: folder with *.dc.html, canvas.json and shared css (asset urls already local)
//   outDir:    gets rendered/<Board>[--variant].html, screenshots/<Board>[--variant].png, boards.json
// Needs Playwright (require('playwright')). No network needed; Google Fonts links are stripped
// and replaced by fontsCss if given.
const fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const [canvasDir, outDir, fontsCss] = process.argv.slice(2);
if (!canvasDir || !outDir) { console.error('usage: node dc-export.js <canvasDir> <outDir> [fontsCss]'); process.exit(1); }

const TR = { а:'a',б:'b',в:'v',г:'g',д:'d',е:'e',ё:'e',ж:'zh',з:'z',и:'i',й:'y',к:'k',л:'l',м:'m',н:'n',о:'o',п:'p',р:'r',с:'s',т:'t',у:'u',ф:'f',х:'h',ц:'ts',ч:'ch',ш:'sh',щ:'sch',ъ:'',ы:'y',ь:'',э:'e',ю:'yu',я:'ya' };
const slug = (s) => String(s).toLowerCase().replace(/[а-яё]/g, c => TR[c] ?? '').replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 32) || 'opt';

const RENDER = `
(function(){
  class DCLogic { constructor(p){ this.props = p || {}; this.state = {}; } setState(o){ Object.assign(this.state, typeof o === 'function' ? o(this.state, this.props) : o); } }
  const ev = (e, s) => { try { return Function('s', 'with(s){return (' + e + ')}')(s); } catch (x) { return ''; } };
  const strip = (v) => { const m = /^\\s*\\{\\{([\\s\\S]+)\\}\\}\\s*$/.exec(v || ''); return m ? m[1] : v; };
  const interp = (str, s) => str.replace(/\\{\\{([\\s\\S]+?)\\}\\}/g, (_, e) => { const v = ev(e, s); return v == null || typeof v === 'function' || v === false ? '' : String(v); });
  function walk(node, s) {
    for (const c of [...node.childNodes]) {
      if (c.nodeType === 3) { if (c.data.includes('{{')) c.data = interp(c.data, s); continue; }
      if (c.nodeType !== 1) continue;
      const tag = c.tagName.toLowerCase();
      if (tag === 'sc-for') {
        const list = ev(strip(c.getAttribute('list')), s) || [], as = c.getAttribute('as') || 'item', frag = document.createDocumentFragment();
        (Array.isArray(list) ? list : []).forEach((it, i) => { const w = document.createElement('div'); w.innerHTML = c.innerHTML; walk(w, Object.assign(Object.create(s), { [as]: it, index: i })); while (w.firstChild) frag.appendChild(w.firstChild); });
        c.replaceWith(frag); continue;
      }
      if (tag === 'sc-if') {
        if (ev(strip(c.getAttribute('value')), s)) { walk(c, s); c.replaceWith(...c.childNodes); } else c.remove();
        continue;
      }
      for (const a of [...c.attributes]) {
        if (/^on/i.test(a.name) || a.name.startsWith('hint-')) { c.removeAttribute(a.name); continue; }
        if (a.value.includes('{{')) c.setAttribute(a.name, interp(a.value, s));
        if (a.name === 'href' && /\\.dc\\.html/.test(a.value)) c.setAttribute('href', a.value.replace(/\\.dc\\.html/, '.html'));
      }
      if (tag === 'template' || tag === 'script' || tag === 'style') continue;
      walk(c, s);
    }
  }
  window.__dcRender = function(overrides){
    const sc = document.querySelector('script[type="text/x-dc"]');
    const meta = JSON.parse((sc && sc.getAttribute('data-props')) || '{}');
    const props = {}; for (const [k, v] of Object.entries(meta)) if (!k.startsWith('$') && v && 'default' in v) props[k] = v.default;
    Object.assign(props, overrides || {});
    let vals = {};
    if (sc) { try { const C = Function('DCLogic', sc.textContent + '\\n;return Component;')(DCLogic); const inst = new C(props); inst.props = props; vals = (inst.renderVals && inst.renderVals()) || {}; } catch (e) { console.log('renderVals error', e.message); } }
    const root = document.querySelector('x-dc');
    const scope = Object.assign(Object.create(null), props, vals);
    if (root) {
      const h = root.querySelector('helmet'); if (h) { [...h.children].forEach(n => document.head.appendChild(n)); h.remove(); }
      walk(root, scope); root.replaceWith(...root.childNodes);
    }
    document.querySelectorAll('script').forEach(n => n.remove());
    document.querySelectorAll('link[href*="fonts.googleapis"]').forEach(n => n.remove());
    return meta;
  };
})();`;

(async () => {
  const canvas = JSON.parse(fs.readFileSync(path.join(canvasDir, 'canvas.json'), 'utf8'));
  const boards = canvas.order || Object.keys(canvas.boards || {});
  const fontTag = fontsCss ? `<link rel="stylesheet" href="${path.relative(path.join(outDir, 'rendered'), fontsCss).split(path.sep).join('/')}">` : '';
  fs.mkdirSync(path.join(outDir, 'rendered'), { recursive: true });
  fs.mkdirSync(path.join(outDir, 'screenshots'), { recursive: true });
  // Small images used as CSS masks (icons) are blocked by Chrome on file:// (CORS) — inline them as data URIs.
  for (const f of fs.readdirSync(canvasDir)) if (f.endsWith('.css')) {
    const p = path.join(canvasDir, f);
    const css = fs.readFileSync(p, 'utf8').replace(/url\((['"]?)([^)'"]+\.(png|svg))\1\)/g, (m, q, u, ext) => {
      const fp = path.resolve(canvasDir, u); if (!fs.existsSync(fp) || fs.statSync(fp).size > 12000) return m;
      return `url(data:image/${ext === 'svg' ? 'svg+xml' : 'png'};base64,${fs.readFileSync(fp).toString('base64')})`;
    });
    fs.writeFileSync(p, css);
    // shared css next to rendered pages (same relative depth as canvas/, so ../assets paths keep working)
    fs.copyFileSync(p, path.join(outDir, 'rendered', f));
  }
  const browser = await chromium.launch();
  const index = [];
  for (const b of boards) {
    const file = path.join(canvasDir, b); if (!fs.existsSync(file)) continue;
    const info = (canvas.boards || {})[b] || {};
    const html = fs.readFileSync(file, 'utf8');
    const metaM = /data-props=(['"])([\s\S]*?)\1/.exec(html);
    let meta = {}; try { meta = JSON.parse((metaM ? metaM[2] : '{}').replace(/&quot;/g, '"').replace(/&amp;/g, '&')); } catch (e) {}
    const pv = meta.$preview || {}; const w = pv.width || info.w || 390, h = pv.height || info.h || 844;
    // variants: default, dark theme, every other option of each non-theme enum tweak
    const variants = [{ id: '', o: {} }];
    for (const [k, v] of Object.entries(meta)) {
      if (k.startsWith('$') || !v || v.editor !== 'enum') continue;
      (v.options || []).forEach((opt, i) => { if (opt !== v.default) variants.push({ id: (k === 'theme' ? '' : k + '-' + (i + 1) + '-') + slug(opt), o: { [k]: opt } }); });
    }
    const base = b.replace(/\.dc\.html$/, '');
    const out = { board: b, name: base, title: info.title || base, page: info.page || '', width: w, height: h, tweaks: Object.fromEntries(Object.entries(meta).filter(([k]) => !k.startsWith('$'))), variants: [] };
    for (const v of variants) {
      const page = await browser.newPage({ viewport: { width: Math.min(w, 2400), height: Math.min(h, 3000) }, deviceScaleFactor: w <= 600 ? 2 : 1 });
      page.on('console', m => { if (/error/i.test(m.text())) console.log(`  [${b}${v.id ? ' ' + v.id : ''}] ${m.text()}`); });
      await page.route('**/*', r => /^file:|^data:/.test(r.request().url()) ? r.continue() : r.abort());
      await page.goto('file://' + path.resolve(file));
      await page.addScriptTag({ content: RENDER });
      await page.evaluate(o => window.__dcRender(o), v.o);
      if (fontTag) await page.evaluate(t => document.head.insertAdjacentHTML('afterbegin', t), fontTag.replace(/href="([^"]+)"/, (m, p) => `href="${'file://' + path.resolve(outDir, 'rendered', p)}"`));
      await page.evaluate(() => document.fonts && document.fonts.ready);
      await page.waitForTimeout(400);
      const name = base + (v.id ? '--' + v.id : '');
      let doc = await page.evaluate(() => '<!doctype html>\n' + document.documentElement.outerHTML);
      doc = doc.replace(/<link rel="stylesheet" href="file:[^"]*">/g, '').replace('<head>', '<head>' + fontTag);
      fs.writeFileSync(path.join(outDir, 'rendered', name + '.html'), doc);
      await page.screenshot({ path: path.join(outDir, 'screenshots', name + '.png'), fullPage: true });
      const text = await page.evaluate(() => document.body.innerText.replace(/\n{3,}/g, '\n\n').trim());
      const links = await page.evaluate(() => [...new Set([...document.querySelectorAll('a[href$=".html"]')].map(a => a.getAttribute('href').replace(/\.html$/, '')))]);
      out.variants.push({ id: v.id || 'default', overrides: v.o, html: 'rendered/' + name + '.html', png: 'screenshots/' + name + '.png', links, text });
      await page.close();
    }
    index.push(out); console.log('ok', b, out.variants.length);
  }
  await browser.close();
  fs.writeFileSync(path.join(outDir, 'boards.json'), JSON.stringify({ title: canvas.title, pages: canvas.pages, notes: canvas.notes, boards: index }, null, 1));
})();
```

### tools/dc-screens-md.py
```python
# dc-screens-md.py — builds SCREENS.md (one section per canvas page/artboard) from boards.json made by dc-export.js
# Usage: python3 dc-screens-md.py <outDir>
import json, sys, os, re
out = sys.argv[1]
d = json.load(open(os.path.join(out, 'boards.json')))
pages = {p['id']: p['name'] for p in d.get('pages') or []}
notes = d.get('notes') or {}
by_page = {}
for b in d['boards']:
    by_page.setdefault(b['page'], []).append(b)
order = [p['id'] for p in d.get('pages') or []] + [p for p in by_page if p not in pages]
L = [f"# {d.get('title') or 'Design'} — экраны и состояния", '',
     'Сгенерировано из канваса. Для каждого артборда: картинки (светлая/тёмная/варианты), чистый HTML, переходы и весь видимый текст.',
     'Пути относительны корня архива.', '']
L.append('## Оглавление'); L.append('')
for pid in order:
    if pid not in by_page: continue
    L.append(f"- **{pages.get(pid, pid or 'без страницы')}**: " + ', '.join(f"[{b['name']}](#{b['name'].lower()})" for b in by_page[pid]))
L.append('')
for pid in order:
    if pid not in by_page: continue
    L += [f"## {pages.get(pid, pid or 'Без страницы')}", '']
    for n in notes.values():
        if n.get('page') == pid and n.get('text') and not str(n.get('kind', '')).startswith('title'):
            L.append('> ' + n['text'].replace('\n', ' '))
            L.append('')
    for b in by_page[pid]:
        L += [f"### {b['name']}", '', f"**{b['title']}** · исходник `canvas/{b['board']}` · {b['width']}×{b['height']}", '']
        L.append('| Вариант | Картинка | HTML |'); L.append('|---|---|---|')
        for v in b['variants']:
            L.append(f"| {v['id']} {('`' + json.dumps(v['overrides'], ensure_ascii=False) + '`') if v['overrides'] else ''} | [{os.path.basename(v['png'])}]({v['png']}) | [{os.path.basename(v['html'])}]({v['html']}) |")
        L.append('')
        tw = {k: v for k, v in b['tweaks'].items() if k not in ('theme',)}
        if tw:
            L.append('Настройки артборда: ' + '; '.join(f"`{k}` = {', '.join(map(str, v.get('options', []))) if v.get('editor') == 'enum' else v.get('editor')} (по умолчанию {v.get('default')})" for k, v in tw.items()))
            L.append('')
        links = sorted({l for v in b['variants'] for l in v['links'] if l != b['name']})
        if links: L += ['Переходы: ' + ', '.join(f"[{l}](#{l.lower()})" for l in links), '']
        txt = b['variants'][0]['text']
        txt = re.sub(r'\n{2,}', '\n', txt).strip()
        if len(txt) > 6000: txt = txt[:6000] + '\n…'
        L += ['<details><summary>Текст на экране</summary>', '', '```text', txt, '```', '</details>', '']
open(os.path.join(out, 'SCREENS.md'), 'w').write('\n'.join(L))
print('SCREENS.md', len(L), 'lines')
```

### tools/dc-assets.py
```python
# dc-assets.py — rewrites /_blob/<id> asset URLs in canvas files to local files.
# Usage: python3 dc-assets.py <canvasDir> <assetsDir>
#   assetsDir holds files downloaded from the artifact's asset store, named <32-hex id>.<ext>
#   (optionally renamed later; a names.json {id: "nice-name.png"} in assetsDir is honoured).
import os, re, sys, json
canvas, assets = sys.argv[1], sys.argv[2]
names = json.load(open(os.path.join(assets, 'names.json'))) if os.path.exists(os.path.join(assets, 'names.json')) else {}
files = {}
for root, _, fs in os.walk(assets):
    for f in fs:
        m = re.match(r'([0-9a-f]{32})\.', f)
        if m: files[m.group(1)] = os.path.join(root, f)
for i, n in names.items():  # optional human names
    if i in files:
        dst = os.path.join(os.path.dirname(files[i]), n); os.replace(files[i], dst); files[i] = dst
missing, n = set(), 0
for f in os.listdir(canvas):
    if not f.endswith(('.html', '.css')): continue
    p = os.path.join(canvas, f); s = open(p, encoding='utf8').read()
    def sub(m):
        global n
        i = m.group(1)
        if i not in files: missing.add(i); return m.group(0)
        n += 1; return os.path.relpath(files[i], canvas).replace(os.sep, '/')
    t = re.sub(r'(?:https://claude\.ai)?/_blob/([0-9a-f]{32})', sub, s)
    if t != s: open(p, 'w', encoding='utf8').write(t)
print('rewritten', n, 'missing', sorted(missing))
```

### tools/dc-fonts.js
```js
// dc-fonts.js — vendors the Google Fonts used by the canvas so the export works offline.
// Usage (run from a tools dir): node dc-fonts.js <canvasDir> <fontsOutDir>
// Finds fonts.googleapis.com links in *.html, installs @fontsource/<family> from npm, writes <fontsOutDir>/fonts.css + files/*.woff2
const fs = require('fs'), path = require('path'), { execSync } = require('child_process');
const [canvasDir, outDir] = process.argv.slice(2);
const fam = {};
for (const f of fs.readdirSync(canvasDir)) if (/\.html?$/.test(f)) {
  const html = fs.readFileSync(path.join(canvasDir, f), 'utf8').replace(/&amp;/g, '&');
  for (const m of html.matchAll(/fonts\.googleapis\.com\/css2?\?([^"' )]+)/g))
    for (const q of m[1].split('&')) if (q.startsWith('family=')) {
      const [name, axes] = decodeURIComponent(q.slice(7).replace(/\+/g, ' ')).split(':');
      const ws = fam[name] || (fam[name] = new Set());
      if (axes && axes.includes('@')) { const [keys, vals] = axes.split('@'); const wi = keys.split(',').indexOf('wght');
        for (const tuple of vals.split(';')) { const w = tuple.split(',')[wi]; if (w && !w.includes('..')) ws.add(w); else if (w) { const [a, b] = w.split('..').map(Number); for (let x = a; x <= b; x += 100) ws.add(String(x)); } } }
      else ws.add('400');
    }
}
fs.mkdirSync(path.join(outDir, 'files'), { recursive: true });
let css = '';
for (const [name, ws] of Object.entries(fam)) {
  const pkg = '@fontsource/' + name.toLowerCase().replace(/\s+/g, '-');
  try { execSync(`npm i -s ${pkg}`, { stdio: 'ignore' }); } catch (e) { console.log('skip (not on npm):', name); continue; }
  const dir = path.dirname(require.resolve(pkg + '/package.json', { paths: [process.cwd()] }));
  for (const w of ws) {
    const f = path.join(dir, w + '.css'); if (!fs.existsSync(f)) continue;
    let part = fs.readFileSync(f, 'utf8').replace(/,\s*url\(\.\/files\/[^)]+\.woff\) format\('woff'\)/g, '');
    for (const m of part.matchAll(/url\(\.\/files\/([^)]+\.woff2)\)/g)) fs.copyFileSync(path.join(dir, 'files', m[1]), path.join(outDir, 'files', m[1]));
    css += part + '\n';
  }
  if (fs.existsSync(path.join(dir, 'LICENSE'))) fs.copyFileSync(path.join(dir, 'LICENSE'), path.join(outDir, 'LICENSE-' + name.replace(/\s+/g, '') + '.txt'));
  console.log('font', name, [...ws].join(','));
}
fs.writeFileSync(path.join(outDir, 'fonts.css'), css);
```
