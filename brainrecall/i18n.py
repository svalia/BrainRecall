from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SUPPORTED_LOCALES = ("ru", "en")
DEFAULT_LOCALE = "ru"

_LOCALES_DIR = Path(__file__).resolve().parent / "locales"
_CATALOGS: dict[str, dict[str, Any]] = {}


def load_catalogs() -> dict[str, dict[str, Any]]:
    global _CATALOGS
    if _CATALOGS:
        return _CATALOGS
    loaded: dict[str, dict[str, Any]] = {}
    for loc in SUPPORTED_LOCALES:
        path = _LOCALES_DIR / f"{loc}.json"
        with path.open("r", encoding="utf-8") as f:
            loaded[loc] = json.load(f)
    _CATALOGS = loaded
    return _CATALOGS


def normalize_locale(raw: str | None) -> str:
    if not raw:
        return DEFAULT_LOCALE
    cleaned = raw.strip().lower().replace("_", "-")
    primary = cleaned.split("-")[0]
    if primary in SUPPORTED_LOCALES:
        return primary
    return DEFAULT_LOCALE


def resolve_user_locale(
    *,
    locale_override: str | None = None,
    saved_locale: str | None = None,
    telegram_language_code: str | None = None,
    accept_language: str | None = None,
) -> str:
    if locale_override and locale_override in SUPPORTED_LOCALES:
        return locale_override
    if saved_locale and saved_locale in SUPPORTED_LOCALES:
        return saved_locale
    if telegram_language_code:
        return normalize_locale(telegram_language_code)
    if accept_language:
        first_part = accept_language.split(",")[0].split(";")[0].strip()
        return normalize_locale(first_part)
    return DEFAULT_LOCALE


def flatten_catalog(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in data.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten_catalog(v, full_key))
        else:
            out[full_key] = str(v)
    return out


def get_catalog(locale: str) -> dict[str, Any]:
    catalogs = load_catalogs()
    loc = normalize_locale(locale)
    return catalogs.get(loc, catalogs[DEFAULT_LOCALE])


def t(key: str, locale: str = DEFAULT_LOCALE, **kwargs: Any) -> str:
    catalogs = load_catalogs()
    loc = normalize_locale(locale)
    val = _lookup(catalogs.get(loc, {}), key)
    if val is None and loc != DEFAULT_LOCALE:
        val = _lookup(catalogs.get(DEFAULT_LOCALE, {}), key)
    if val is None:
        return key
    if kwargs:
        try:
            return str(val).format(**kwargs)
        except Exception:
            return str(val)
    return str(val)


def _lookup(catalog: dict[str, Any], dotted_key: str) -> Any:
    curr: Any = catalog
    for part in dotted_key.split("."):
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            return None
    return curr


def verify_catalog_parity() -> tuple[bool, list[str]]:
    catalogs = load_catalogs()
    ru_flat = flatten_catalog(catalogs["ru"])
    en_flat = flatten_catalog(catalogs["en"])
    errors: list[str] = []
    ru_keys = set(ru_flat.keys())
    en_keys = set(en_flat.keys())

    for missing_in_en in sorted(ru_keys - en_keys):
        errors.append(f"Missing in en.json: {missing_in_en}")
    for missing_in_ru in sorted(en_keys - ru_keys):
        errors.append(f"Missing in ru.json: {missing_in_ru}")
    for k in sorted(ru_keys & en_keys):
        if not ru_flat[k].strip():
            errors.append(f"Empty value in ru.json: {k}")
        if not en_flat[k].strip():
            errors.append(f"Empty value in en.json: {k}")
    return (len(errors) == 0, errors)
