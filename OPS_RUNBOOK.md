# 🛠 BrainRecall — Эксплуатационный регламент (Operations Runbook)

Регламент сопровождения продакшен-сервера Selectel (`5.35.13.4` / `owncome.ru`) согласно разделу 16 дев-ТЗ 1.14.

---

## 1. Конфигурация продакшен-окружения

- **Сервер**: `root@5.35.13.4` (Ubuntu 24.04 LTS, BBR + fq включены, PMTU clamping активен).
- **Директория приложения**: `/opt/brainrecall/app`
- **Секреты окружения (вне Git)**: `/etc/brainrecall/brainrecall.env` (`chmod 600`)
- **База данных**: PostgreSQL 16 (`brainrecall` / роль `brainrecall` на `127.0.0.1:5432`)
- **Systemd-сервис**: `brainrecall.service` (`127.0.0.1:8096`)
- **Nginx Reverse Proxy**: `/etc/nginx/sites-enabled/owncome.conf` -> блок `location /brainrecall/`
- **Публичные эндпоинты**:
  - Mini App: `https://owncome.ru/brainrecall/`
  - Healthcheck: `https://owncome.ru/brainrecall/health`
  - Telegram Webhook: `https://owncome.ru/brainrecall/webhook/telegram`
  - MCP Endpoint: `https://owncome.ru/brainrecall/api/v1/mcp`

---

## 2. Основные команды управления и диагностики

```bash
# Проверка статуса сервиса
ssh -i ~/.ssh/owncome_deploy root@5.35.13.4 "systemctl status brainrecall.service --no-pager"

# Просмотр логов в реальном времени
ssh -i ~/.ssh/owncome_deploy root@5.35.13.4 "journalctl -u brainrecall.service -f"

# Проверка healthcheck и паритета локализации
curl -sS https://owncome.ru/brainrecall/health | jq .

# Деплой новой версии с локальной машины
./deploy/deploy.sh
```

---

## 3. Аварийное отключение ИИ и защита бюджета (Kill Switch)

Если внешний провайдер DeepSeek недоступен или требуется мгновенно переключить все операции на детерминированный локальный режим без расхода средств:
1. В `/etc/brainrecall/brainrecall.env` установить `AI_GLOBAL_KILL_SWITCH=true`.
2. Выполнить `systemctl restart brainrecall.service`.
3. Ручное создание карточек, учебные сессии `M1–M5`, привычки и детерминированный разбор продолжат работать штатно.

---

## 4. Резервное копирование PostgreSQL

```bash
ssh -i ~/.ssh/owncome_deploy root@5.35.13.4 \
  "sudo -u postgres pg_dump -Fc brainrecall > /var/backups/brainrecall_$(date +%F).dump"
```
