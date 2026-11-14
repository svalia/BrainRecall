# ✅ Чек-лист публикации в каталогах и Telegram Apps Center (Listing Checklist)

Чек-лист готовности `@BrainRecallBot` к модерации в Telegram Apps Center, FindMini и каталогах мини-приложений (раздел 15 дев-ТЗ 1.14).

---

## 1. Обязательные команды и метаданные бота (`@BrainRecallBot`)
- [x] Зарегистрированы команды для `RU` и `EN` через `setMyCommands`:
  - `/start` — Открыть BrainRecall и план на сегодня / Open BrainRecall & Today's plan
  - `/lang` — Сменить язык (RU / EN) / Switch language (RU / EN)
  - `/help` — Справка по 5 методикам и привычкам / Help on 5 learning methods & habits
  - `/paysupport` — Помощь по оплате и возвратам Telegram Stars / Billing & Telegram Stars support
- [x] Кнопка меню бота (`setChatMenuButton`) ведёт на продакшен URL Mini App: `https://owncome.ru/brainrecall/`.
- [x] Webhook бота настроен и отвечает `< 200 мс`: `https://owncome.ru/brainrecall/webhook/telegram`.

## 2. Соответствие требованиям Telegram Mini Apps и мобильной эргономики
- [x] Поддержка `safe-area-inset-*` и `contentSafeAreaInset` (экраны не перекрываются шапкой Telegram).
- [x] Поддержка светлой и тёмной темы (`tokens.css` + адаптация к `Telegram.WebApp.colorScheme`).
- [x] Двусторонний жест «Назад» от левого и правого края экрана (`Gestures-Back`) + корректный приоритет закрытия открытого bottom sheet без сворачивания Mini App.
- [x] Полная локализация `RU` и `EN` со 100% паритетом ключей (`i18n_parity: true`).

## 3. Платежи Telegram Stars и прозрачность условий
- [x] Оплата цифровых подписок (`Start 499 XTR`, `Pro 1099 XTR`) и защиты серии (`49 XTR` / `199 XTR`) исключительно через Telegram Stars (`XTR`).
- [x] Пробный доступ на 7 дней (`Trial`) включается без автосписаний и только по явному действию пользователя (`D16`).
- [x] Команда `/paysupport` и экран `D28` предоставляют прозрачное отключение автопродления (`editUserStarSubscription`) и возврат Stars (`refundStarPayment`) при неизрасходованной квоте.

## 4. Приватность и переносимость данных (`D32`)
- [x] Полная выгрузка пользовательских данных в `JSON` и `Markdown`.
- [x] Полное удаление аккаунта и данных с отменой автопродления и очисткой аналитики.
