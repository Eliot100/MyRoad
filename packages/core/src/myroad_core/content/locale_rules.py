"""Locale consistency rules for published learning paths.

Rule (brief):
  Platform UI language and path *explanations* must match the learner's UI locale.
  Learning *content tokens* (vocab/phrases being taught) stay in the path's
  content_locale (e.g. English words in English-learning paths).

  Example: learning English with UI in Hebrew → chrome + explanations in Hebrew;
  only target vocabulary/phrases in English. Switching UI language swaps shell +
  explanation strings; content tokens do not switch.
"""

from __future__ import annotations

import re
from typing import Any

from myroad_core.content.schema import ContentNode, ContentPath

# Latin letters (target EN tokens) vs Hebrew letters (common explain locale)
_HE_CHARS = re.compile(r"[\u0590-\u05FF]")
_LATIN_WORDS = re.compile(r"[A-Za-z]{2,}")
_AR_CHARS = re.compile(r"[\u0600-\u06FF]")


def _latin_word_count(text: str) -> int:
    return len(_LATIN_WORDS.findall(text or ""))


def _he_char_count(text: str) -> int:
    return len(_HE_CHARS.findall(text or ""))


def _ar_char_count(text: str) -> int:
    return len(_AR_CHARS.findall(text or ""))


def explanation_text(node: ContentNode, ui_locale: str) -> str:
    """Pick the UI explanation for a node given the platform UI locale."""
    loc = (ui_locale or "he").split("-")[0].lower()
    if loc == "en" and node.body_en:
        return node.body_en
    if node.body_ui:
        return node.body_ui
    # Prefer body_he as default authored explain (often HE for demos)
    if node.body_he:
        return node.body_he
    if node.body_en:
        return node.body_en
    return ""


def content_token_text(node: ContentNode) -> str:
    """Target vocabulary / phrases (content_locale), not UI chrome."""
    parts: list[str] = []
    if node.body_content:
        parts.append(node.body_content)
    if node.speak_text:
        parts.append(node.speak_text)
    return " ".join(parts).strip()


def validate_locale_consistency(path: ContentPath) -> list[str]:
    """
    Return a list of human-readable errors. Empty list means OK.

    English-learning paths (subject == english) must:
      - declare content_locale == 'en' and explain_locale set
      - separate explanations (body_ui / body_he / body_en) from content tokens
        (body_content and/or speak_text)
      - not leave unexplained English-only chrome in HE explain fields
    """
    errors: list[str] = []
    explain = (path.explain_locale or "he").split("-")[0].lower()
    content = (path.content_locale or explain).split("-")[0].lower()

    if path.subject == "english":
        if content != "en":
            errors.append(
                f"{path.id}: english subject requires content_locale='en' (got {path.content_locale!r})"
            )
        if not path.explain_locale:
            errors.append(f"{path.id}: english subject requires explain_locale")

        # At least one node must expose content tokens
        token_nodes = [
            n
            for n in path.nodes
            if (n.body_content and n.body_content.strip())
            or (n.speak_text and n.speak_text.strip())
        ]
        if len(token_nodes) < 3:
            errors.append(
                f"{path.id}: english path needs body_content and/or speak_text on "
                f"at least 3 nodes (got {len(token_nodes)})"
            )

        for node in path.nodes:
            nid = node.id or node.title
            ui_text = node.body_ui or node.body_he or ""
            if not ui_text.strip() and not (node.body_en or "").strip():
                errors.append(f"{path.id}/{nid}: missing UI explanation (body_ui/body_he/body_en)")
                continue

            # Unexplained mixed chrome: HE explain field that is mostly English
            # with almost no Hebrew, and no body_content to hold the tokens.
            if explain == "he" and ui_text:
                he_n = _he_char_count(ui_text)
                lat_n = _latin_word_count(ui_text)
                if lat_n >= 4 and he_n < 3 and not (node.body_content or "").strip():
                    errors.append(
                        f"{path.id}/{nid}: unexplained English chrome in HE explanation "
                        f"(add body_content for target tokens, keep body_he/body_ui in Hebrew)"
                    )

            # Feedback chrome should follow explain locale when present
            for field_name in ("feedback_ok", "feedback_try"):
                fb = getattr(node, field_name, None)
                if not fb:
                    continue
                if explain == "he":
                    if _latin_word_count(fb) >= 5 and _he_char_count(fb) < 2:
                        errors.append(
                            f"{path.id}/{nid}: {field_name} looks English-only while "
                            f"explain_locale=he (keep feedback in UI language; tokens OK)"
                        )

            # Practice/check with EN content: choices that teach EN words may stay Latin;
            # require speak_text or body_content so tokens are explicit.
            if node.type in ("practice", "check", "speak", "learn") and content == "en":
                if node.type != "celebrate" and not content_token_text(node):
                    # celebrate can skip; others should carry tokens somehow
                    if node.type in ("practice", "check", "speak"):
                        errors.append(
                            f"{path.id}/{nid}: {node.type} node missing body_content/speak_text "
                            f"for content_locale=en"
                        )

    # Non-english paths: content_locale defaults OK; soft check only if declared split
    if content != explain and path.subject != "english":
        # still require that nodes have some explanation text
        for node in path.nodes:
            if not (node.body_ui or node.body_he or node.body_en):
                errors.append(
                    f"{path.id}/{node.id or node.title}: missing explanation when "
                    f"content_locale != explain_locale"
                )

    return errors


def assert_locale_consistent(path: ContentPath) -> None:
    errs = validate_locale_consistency(path)
    if errs:
        raise ValueError("; ".join(errs))


def resolve_node_display(
    node: ContentNode | dict[str, Any],
    *,
    ui_locale: str,
    content_locale: str | None = None,
) -> dict[str, str]:
    """
    Resolve strings for the player:
      - body: explanation in UI locale
      - body_content: target tokens (unchanged by UI locale)
      - speak: TTS prefers content speak_text; speak_ui for explanation if needed
    """
    if isinstance(node, dict):
        body_he = node.get("body_he") or ""
        body_en = node.get("body_en") or ""
        body_ui = node.get("body_ui") or ""
        body_content = node.get("body_content") or ""
        speak_text = node.get("speak_text") or ""
        speak_ui = node.get("speak_ui") or ""
        title = node.get("title") or ""
        title_en = node.get("title_en") or ""
    else:
        body_he = node.body_he or ""
        body_en = node.body_en or ""
        body_ui = node.body_ui or ""
        body_content = node.body_content or ""
        speak_text = node.speak_text or ""
        speak_ui = node.speak_ui or ""
        title = node.title or ""
        title_en = node.title_en or ""

    loc = (ui_locale or "he").split("-")[0].lower()
    if loc == "en" and body_en:
        body = body_en
    elif body_ui:
        body = body_ui
    else:
        body = body_he or body_en

    display_title = title_en if loc == "en" and title_en else title
    speak = speak_text or body_content or speak_ui or body
    return {
        "title": display_title,
        "body": body,
        "body_content": body_content,
        "speak": speak,
        "speak_content": speak_text or body_content,
        "speak_ui": speak_ui or body,
    }


def validate_catalog_chrome(
    path: ContentPath,
    *,
    require_locales: list[str] | None = None,
    require_en: bool | None = None,
    require_ar: bool | None = None,
) -> list[str]:
    """Catalog/card chrome must cover UI locales via titles/blurbs maps.

    By default requires every code listed in ``locales/manifest.json``.
    ``require_en`` / ``require_ar`` remain as back-compat toggles.
    """
    from myroad_core.ui.i18n import locale_codes

    errors: list[str] = []
    titles = dict(path.titles or {})
    blurbs = dict(path.blurbs or {})
    # legacy mirrors
    if path.title_he:
        titles.setdefault("he", path.title_he)
    if path.title_en:
        titles.setdefault("en", path.title_en)
    if path.title_ar:
        titles.setdefault("ar", path.title_ar)
    if path.blurb_he:
        blurbs.setdefault("he", path.blurb_he)
    if path.blurb_en:
        blurbs.setdefault("en", path.blurb_en)
    if path.blurb_ar:
        blurbs.setdefault("ar", path.blurb_ar)

    if not (titles.get("he") or "").strip():
        errors.append(f"{path.id}: missing titles.he")
    if not (blurbs.get("he") or "").strip():
        errors.append(f"{path.id}: missing blurbs.he")

    needed: list[str] = list(require_locales) if require_locales is not None else list(locale_codes())
    # Back-compat flags override membership when explicitly False/True
    if require_en is False and "en" in needed:
        needed = [c for c in needed if c != "en"]
    if require_ar is False and "ar" in needed:
        needed = [c for c in needed if c != "ar"]
    if require_en is True and "en" not in needed:
        needed.append("en")
    if require_ar is True and "ar" not in needed:
        needed.append("ar")

    for code in needed:
        if code == "he":
            continue
        if not (titles.get(code) or "").strip():
            errors.append(f"{path.id}: missing titles.{code} for catalog UI locale={code}")
        if not (blurbs.get(code) or "").strip():
            errors.append(f"{path.id}: missing blurbs.{code} for catalog UI locale={code}")
    return errors
