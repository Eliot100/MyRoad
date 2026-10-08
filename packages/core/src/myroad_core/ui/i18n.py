"""Data-driven UI locale packs + generic chrome picker.

Shell strings live in ``packages/core/locales/<code>.json``.
Available languages are listed in ``packages/core/locales/manifest.json``.

Adding a language (e.g. Russian ``ru``):
  1. Add ``{"code": "ru", "label": "Русский", "dir": "ltr"}`` to manifest.json
  2. Add ``locales/ru.json`` with the same keys as ``en.json``
  3. Add ``titles.ru`` / ``blurbs.ru`` (and topic titles) on content paths
No Python changes required.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from markupsafe import Markup

COOKIE_LOCALE = "myroad_locale"
_LANG_RE = re.compile(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})?")
COOKIE_USER = "myroad_uid"

# packages/core/src/myroad_core/ui -> packages/core/locales
_PKG_CORE = Path(__file__).resolve().parents[3]
DEFAULT_LOCALES_DIR = _PKG_CORE / "locales"


def default_locales_dir() -> Path:
    return DEFAULT_LOCALES_DIR


@lru_cache(maxsize=4)
def _load_manifest(locales_dir: str) -> dict[str, Any]:
    path = Path(locales_dir) / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "locales" not in data:
        raise ValueError(f"invalid locale manifest: {path}")
    return data


def reload_locale_packs() -> None:
    """Clear cached manifest/string packs (tests that inject a locales dir)."""
    _load_manifest.cache_clear()
    _load_strings.cache_clear()
    # Reset module-level snapshots derived from default dir
    global LOCALES, DEFAULT_LOCALE, RTL_LOCALES, FALLBACK_CHAIN, _LOCALE_META
    LOCALES, DEFAULT_LOCALE, RTL_LOCALES, FALLBACK_CHAIN, _LOCALE_META = _snapshot(
        default_locales_dir()
    )


@lru_cache(maxsize=8)
def _load_strings(locales_dir: str, code: str) -> dict[str, str]:
    path = Path(locales_dir) / f"{code}.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"locale pack must be an object: {path}")
    return {str(k): str(v) for k, v in data.items()}


def _snapshot(locales_dir: Path) -> tuple[tuple[str, ...], str, frozenset[str], tuple[str, ...], dict[str, dict[str, str]]]:
    manifest = _load_manifest(str(locales_dir))
    entries = manifest.get("locales") or []
    codes: list[str] = []
    meta: dict[str, dict[str, str]] = {}
    rtl: set[str] = set()
    for entry in entries:
        code = str(entry.get("code") or "").strip().lower()
        if not code:
            continue
        codes.append(code)
        direction = str(entry.get("dir") or "ltr").lower()
        meta[code] = {
            "code": code,
            "label": str(entry.get("label") or code),
            "nativeLabel": str(entry.get("nativeLabel") or entry.get("label") or code),
            "dir": direction,
        }
        if direction == "rtl":
            rtl.add(code)
    default = str(manifest.get("default") or (codes[0] if codes else "he")).lower()
    fallback = tuple(
        str(x).lower() for x in (manifest.get("fallback") or ["en", "he"]) if str(x).strip()
    )
    if default not in fallback:
        fallback = (default, *fallback)
    return tuple(codes), default, frozenset(rtl), fallback, meta


LOCALES, DEFAULT_LOCALE, RTL_LOCALES, FALLBACK_CHAIN, _LOCALE_META = _snapshot(DEFAULT_LOCALES_DIR)


def locale_manifest(locales_dir: Path | None = None) -> dict[str, Any]:
    return _load_manifest(str(locales_dir or default_locales_dir()))


def locale_codes(locales_dir: Path | None = None) -> tuple[str, ...]:
    if locales_dir is None:
        return LOCALES
    codes, *_rest = _snapshot(locales_dir)
    return codes


def locale_meta(code: str, locales_dir: Path | None = None) -> dict[str, str]:
    if locales_dir is None:
        return dict(_LOCALE_META.get(normalize_locale(code)) or {"code": code, "label": code, "dir": "ltr"})
    _codes, _d, _r, _f, meta = _snapshot(locales_dir)
    loc = code.strip().lower().split("-")[0]
    return dict(meta.get(loc) or {"code": loc, "label": loc, "dir": "ltr"})


def pick(
    values: Mapping[str, str | None] | None,
    locale: str | None,
    *,
    fallback_chain: tuple[str, ...] | None = None,
    default: str = "",
) -> str:
    """Pick a localized string from a map.

    Fallback order: requested locale → manifest fallback chain (default en→he) →
    any non-empty value in the map → ``default``.
    """
    if not values:
        return default
    loc = (locale or DEFAULT_LOCALE).strip().lower().split("-")[0]
    chain = fallback_chain if fallback_chain is not None else FALLBACK_CHAIN
    ordered: list[str] = []
    for code in (loc, *chain):
        if code and code not in ordered:
            ordered.append(code)
    for code in ordered:
        val = values.get(code)
        if val is not None and str(val).strip():
            return str(val).strip()
    for val in values.values():
        if val is not None and str(val).strip():
            return str(val).strip()
    return default


def pick_content(
    values: Mapping[str, str | None] | None,
    locale: str | None,
    *,
    source_locale: str | None = None,
    default: str = "",
    default_lang: str | None = None,
) -> tuple[str, str | None]:
    """Pick a *content* string (path/topic/step text) and the language it is in.

    Fallback order: UI locale → the path's own language (``source_locale``, its
    ``explain_locale``; the platform default locale when unknown) → any other
    non-empty value (manifest locales first, then the rest) → ``default``.

    Unlike :func:`pick` (UI chrome, manifest chain en→he), content never jumps to
    English just because a translation is missing: an adult Hebrew path shown in
    the Arabic UI falls back to Hebrew, its own language.
    Returns ``(text, lang)`` so templates can mark fallback text with ``lang``.
    """
    if not values:
        return default, default_lang
    loc = (locale or DEFAULT_LOCALE).strip().lower().split("-")[0]
    src = (source_locale or DEFAULT_LOCALE).strip().lower().split("-")[0]
    normalized = {str(k).strip().lower(): v for k, v in values.items()}
    ordered: list[str] = []
    for code in (loc, src, *LOCALES, *normalized.keys()):
        if code and code not in ordered:
            ordered.append(code)
    for code in ordered:
        val = normalized.get(code)
        if val is not None and str(val).strip():
            return str(val).strip(), code
    return default, default_lang


def _lang_of(values: Mapping[str, str | None], text: str, locale: str | None) -> str | None:
    """Which key of ``values`` holds ``text`` (UI locale preferred on ties)."""
    if not text:
        return None
    loc = (locale or DEFAULT_LOCALE).strip().lower().split("-")[0]
    norm = {str(k).strip().lower(): v for k, v in values.items()}
    for code in (loc, *norm.keys()):
        val = norm.get(code)
        if val is not None and str(val).strip() == text:
            return code
    return None


def content_lang(text_lang: str | None, ui_locale: str | None, text: Any = None) -> Markup:
    """Jinja filter: `` lang="xx"`` when content text is not in the UI locale, else nothing.

    Pair it with ``dir="auto"`` on the same element (#57/#58): the browser then lays the
    fallback text out in its own direction and screen readers switch voice.
    ``text`` (optional) skips the attribute for text with no letters at all: a numeric
    answer like "2" has no language to switch to.
    """
    code = (text_lang or "").strip().lower()
    ui = (ui_locale or "").strip().lower().split("-")[0]
    if text is not None and not any(ch.isalpha() for ch in str(text)):
        return Markup("")
    if not code or code == ui or not _LANG_RE.fullmatch(code):
        return Markup("")
    return Markup(f' lang="{code}"')


def merge_locale_fields(
    data: dict[str, Any],
    *,
    map_key: str,
    legacy_prefix: str,
) -> dict[str, str]:
    """Merge ``titles``/``blurbs`` maps with legacy ``title_he``-style fields."""
    merged: dict[str, str] = {}
    raw_map = data.get(map_key) or {}
    if isinstance(raw_map, dict):
        for k, v in raw_map.items():
            if v is not None and str(v).strip():
                merged[str(k).lower()] = str(v).strip()
    # legacy flat fields: title_he / blurb_en / ...
    prefix = legacy_prefix
    for key, val in list(data.items()):
        if not isinstance(key, str) or not key.startswith(prefix + "_"):
            continue
        code = key[len(prefix) + 1 :].lower()
        if code and val is not None and str(val).strip() and code not in merged:
            merged[code] = str(val).strip()
    return merged


def normalize_locale(raw: str | None, *, locales_dir: Path | None = None) -> str:
    codes = locale_codes(locales_dir)
    default = DEFAULT_LOCALE if locales_dir is None else _snapshot(locales_dir)[1]
    if not raw:
        return default
    code = raw.strip().lower().split("-")[0]
    return code if code in codes else default


def t(locale: str, key: str, **kwargs: Any) -> str:
    loc = normalize_locale(locale)
    locales_dir = default_locales_dir()
    pack = _load_strings(str(locales_dir), loc)
    default_pack = _load_strings(str(locales_dir), DEFAULT_LOCALE)
    text = pack.get(key) or default_pack.get(key) or key
    # Try fallback chain for missing keys
    if text == key:
        for code in FALLBACK_CHAIN:
            alt = _load_strings(str(locales_dir), code).get(key)
            if alt:
                text = alt
                break
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text


def dir_for(locale: str) -> str:
    meta = locale_meta(locale)
    return meta.get("dir") or ("rtl" if normalize_locale(locale) in RTL_LOCALES else "ltr")


def html_lang(locale: str) -> str:
    return normalize_locale(locale)


def subject_label(subject: str, locale: str) -> str:
    meta = SUBJECTS_SAFE.get(subject) or SUBJECTS_SAFE["general"]
    # SUBJECTS values are already locale maps (plus color/emoji)
    labels = {k: v for k, v in meta.items() if k in LOCALES or k in ("he", "en", "ar") or (isinstance(v, str) and k not in {"color", "emoji"})}
    # Prefer known locale keys only
    label_map = {k: str(v) for k, v in meta.items() if isinstance(v, str) and k not in {"color", "emoji", "id"}}
    return pick(label_map, locale, default=subject)


def pick_localized(
    locale: str,
    *,
    he: str | None = None,
    en: str | None = None,
    ar: str | None = None,
    fallback: str = "",
    **extra: str | None,
) -> str:
    """Back-compat wrapper around :func:`pick` for keyword he/en/ar (+ extras)."""
    values: dict[str, str | None] = {"he": he, "en": en, "ar": ar}
    values.update(extra)
    return pick(values, locale, default=fallback)


def localize_path_chrome(
    *,
    locale: str,
    titles: Mapping[str, str | None] | None = None,
    blurbs: Mapping[str, str | None] | None = None,
    title_he: str | None = None,
    title_en: str | None = None,
    title_ar: str | None = None,
    blurb_he: str | None = None,
    blurb_en: str | None = None,
    blurb_ar: str | None = None,
    subject: str | None = None,
    source_locale: str | None = None,
) -> dict[str, str]:
    """Resolve catalog/path card title, blurb, and subject label for the UI locale.

    Title and blurb are content. When ``source_locale`` (the path's ``explain_locale``)
    is given, a missing translation falls back to that language, not to English
    (#58, see :func:`pick_content`). Without it the legacy manifest chain (en→he) is
    kept, so callers outside the UI view layer (the content loader's catalog
    localisation, the JSON API) behave exactly as before. ``titleLang`` /
    ``blurbLang`` name the language actually shown.
    """
    title_map: dict[str, str | None] = dict(titles or {})
    for code, val in (("he", title_he), ("en", title_en), ("ar", title_ar)):
        if val and not title_map.get(code):
            title_map[code] = val
    blurb_map: dict[str, str | None] = dict(blurbs or {})
    for code, val in (("he", blurb_he), ("en", blurb_en), ("ar", blurb_ar)):
        if val and not blurb_map.get(code):
            blurb_map[code] = val
    def _resolve(values: dict[str, str | None], default: str) -> tuple[str, str | None]:
        default_lang = "he" if default else None
        if source_locale:
            return pick_content(values, locale, source_locale=source_locale, default=default, default_lang=default_lang)
        text = pick(values, locale, default=default)
        return text, _lang_of(values, text, locale) or default_lang

    title, title_lang = _resolve(title_map, title_he or "")
    blurb, blurb_lang = _resolve(blurb_map, blurb_he or "")
    label = subject_label(subject, locale) if subject else ""
    return {
        "title": title,
        "blurb": blurb,
        "subjectLabel": label,
        "titleLang": title_lang or "",
        "blurbLang": blurb_lang or "",
    }


# Avoid circular import of schema SUBJECTS at module load for typing clarity
from myroad_core.content.schema import SUBJECTS as SUBJECTS_SAFE  # noqa: E402
