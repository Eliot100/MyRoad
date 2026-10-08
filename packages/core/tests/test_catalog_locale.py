"""Catalog chrome follows UI locale via data-driven titles/blurbs maps."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from myroad_core.content.loader import (
    apply_catalog_locale,
    default_content_dir,
    list_catalog_cards,
    load_content_paths,
    seed_content_paths,
)
from myroad_core.content.locale_rules import validate_catalog_chrome
from myroad_core.store import PathStore
from myroad_core.ui.i18n import (
    localize_path_chrome,
    locale_codes,
    pick,
    reload_locale_packs,
    subject_label,
)

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient
from auth_helpers import login_with_code

from myroad_core.ui.app import create_learner_app


def _has_arabic(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06FF" for ch in text)


def _has_hebrew(text: str) -> bool:
    return any("\u0590" <= ch <= "\u05FF" for ch in text)


def _grade3_ids() -> set[str]:
    return {p.id for p in load_content_paths(default_content_dir()) if "grade3" in p.group_ids}


def test_all_grade3_paths_have_manifest_catalog_chrome() -> None:
    paths = [p for p in load_content_paths(default_content_dir()) if "grade3" in p.group_ids]
    assert paths, "no grade3 paths found"
    required = list(locale_codes())
    for p in paths:
        assert "he" in p.titles and p.titles["he"].strip()
        assert "he" in p.blurbs and p.blurbs["he"].strip()
        for code in required:
            assert (p.titles.get(code) or "").strip(), f"{p.id} missing titles.{code}"
            assert (p.blurbs.get(code) or "").strip(), f"{p.id} missing blurbs.{code}"
        assert any(ch.isascii() and ch.isalpha() for ch in p.titles["en"]), p.id
        assert _has_arabic(p.titles["ar"]), f"{p.id} titles.ar should include Arabic"
        # legacy mirrors still populated
        assert p.title_he == p.titles["he"]
        assert p.title_en == p.titles["en"]
        assert p.title_ar == p.titles["ar"]
        errs = validate_catalog_chrome(p)
        assert errs == [], errs


def test_validate_catalog_chrome_flags_missing_locale() -> None:
    paths = load_content_paths(default_content_dir())
    sample = paths[0].model_copy(
        update={
            "titles": {k: v for k, v in paths[0].titles.items() if k != "ar"},
            "blurbs": {k: v for k, v in paths[0].blurbs.items() if k != "ar"},
            "title_ar": None,
            "blurb_ar": None,
        }
    )
    errs = validate_catalog_chrome(sample, require_locales=["he", "en", "ar"])
    assert any("titles.ar" in e for e in errs)
    assert any("blurbs.ar" in e for e in errs)


def test_list_catalog_cards_pick_by_ui_locale(store: PathStore) -> None:
    seed_content_paths(store, content_dir=default_content_dir())
    raw = list_catalog_cards(store)
    assert len(raw) == len(load_content_paths(default_content_dir()))
    grade3 = _grade3_ids()
    for card in raw:
        assert card.get("titles", {}).get("en"), card["pathId"]
        if card["pathId"] not in grade3:
            continue  # full ar chrome is only required of the grade-3 demo set
        assert card.get("titles", {}).get("ar"), card["pathId"]
        assert _has_arabic(card["titles"]["ar"]), card["pathId"]

    for loc in locale_codes():
        cards = list_catalog_cards(store, locale=loc)
        assert len(cards) == len(raw)
        for card in cards:
            assert card["uiLocale"] == loc
            assert card["title"] == pick(card["titles"], loc)
            assert card["blurb"] == pick(card["blurbs"], loc)
            assert subject_label(card["subject"], loc) == card["subjectLabel"]
            if loc == "ar" and card["pathId"] in grade3:
                assert _has_arabic(card["title"])
                assert not _has_hebrew(card["title"])
            if loc == "he" and card["subject"] in {"math", "physics", "piano"}:
                assert _has_hebrew(card["title"])

    localized = apply_catalog_locale(raw[0], "ar")
    assert localized["title"] == raw[0]["titles"]["ar"]
    assert pick({"he": "א", "en": "A", "ar": "ع", "ru": "Р"}, "ru") == "Р"
    chrome = localize_path_chrome(locale="ar", titles=raw[0]["titles"], blurbs=raw[0]["blurbs"], subject=raw[0]["subject"])
    assert chrome["title"] == raw[0]["titles"]["ar"]


def test_fake_ru_locale_needs_no_code_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Adding Russian = manifest row + JSON pack + titles.ru on content; zero Python edits."""
    # Build a temporary locales dir with he/en/ar + ru
    src = Path(__file__).resolve().parents[1] / "locales"
    dest = tmp_path / "locales"
    dest.mkdir()
    for name in ("he.json", "en.json", "ar.json", "manifest.json"):
        (dest / name).write_text((src / name).read_text(encoding="utf-8"), encoding="utf-8")
    # Minimal ru pack (subset of keys is enough for pick/t smoke)
    en = json.loads((src / "en.json").read_text(encoding="utf-8"))
    ru_pack = {k: f"RU:{v}" for k, v in en.items()}
    ru_pack["catalog"] = "Каталог"
    ru_pack["product_badge"] = "Обучающая платформа"
    (dest / "ru.json").write_text(json.dumps(ru_pack, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    manifest["locales"].append({"code": "ru", "label": "Русский", "nativeLabel": "Русский", "dir": "ltr"})
    (dest / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    import myroad_core.ui.i18n as i18n

    monkeypatch.setattr(i18n, "DEFAULT_LOCALES_DIR", dest)
    monkeypatch.setattr(i18n, "default_locales_dir", lambda: dest)
    i18n.reload_locale_packs()

    assert "ru" in i18n.locale_codes()
    assert i18n.t("ru", "catalog") == "Каталог"
    assert i18n.dir_for("ru") == "ltr"

    # Content chrome: only add titles.ru / blurbs.ru — pick works without code changes
    titles = {"he": "חיבור", "en": "Addition", "ar": "الجمع", "ru": "Сложение"}
    blurbs = {"he": "ב", "en": "B", "ar": "ب", "ru": "Кратко"}
    assert pick(titles, "ru") == "Сложение"
    chrome = localize_path_chrome(locale="ru", titles=titles, blurbs=blurbs, subject="math")
    assert chrome["title"] == "Сложение"
    assert chrome["blurb"] == "Кратко"
    # Fallback when ru missing → en then he
    assert pick({"he": "חיבור", "en": "Addition"}, "ru") == "Addition"

    # Restore default packs for other tests
    monkeypatch.setattr(i18n, "DEFAULT_LOCALES_DIR", src)
    monkeypatch.setattr(i18n, "default_locales_dir", lambda: src)
    i18n.reload_locale_packs()


@pytest.fixture
def platform_client(tmp_path):
    store = PathStore(str(tmp_path / "plat.db"))
    app = create_learner_app(store=store, seed=True, seed_content=True)
    with TestClient(app) as c:
        login_with_code(
            c,
            data={
                "first_name": "Test",
                "last_name": "User",
                "email": "catalog@example.com",
                "next": "/",
            },
            follow_redirects=True,
        )
        yield c
    store.close()


def test_catalog_home_en_shows_english_path_titles(platform_client: TestClient) -> None:
    r = platform_client.post("/locale", data={"locale": "en", "next": "/?tab=catalog"}, follow_redirects=True)
    assert r.status_code == 200
    assert "Addition up to 20" in r.text
    assert "Light and shadow" in r.text
    assert "Do-Re-Mi" in r.text
    assert "Hand rhythm" in r.text
    assert "Multiplication as repeated addition" in r.text
    assert "Force and push" in r.text
    assert "Colors in English" in r.text
    assert "Animals" in r.text
    assert "Hello" in r.text and "Feelings" in r.text  # &amp; escaped in HTML
    assert "חיבור עד 20" not in r.text
    assert "אור וצל" not in r.text
    assert "Paths for Grade 3" in r.text


def test_catalog_home_ar_shows_arabic_path_titles(platform_client: TestClient) -> None:
    r = platform_client.post("/locale", data={"locale": "ar", "next": "/?tab=catalog"}, follow_redirects=True)
    assert r.status_code == 200
    assert "مسارات للصف الثالث" in r.text
    assert "الجمع حتى 20" in r.text
    assert "الضوء والظل" in r.text
    assert "دو-ري-مي" in r.text
    assert "إيقاع اليدين" in r.text
    assert "الضرب كتكرار للجمع" in r.text
    assert "القوة والدفع" in r.text
    assert "الطرح مع عناصر" in r.text
    assert "ألوان بالإنجليزية" in r.text
    assert "حيوانات بالإنجليزية" in r.text
    assert "مرحبا" in r.text
    assert "חיבור עד 20" not in r.text
    assert "אור וצל" not in r.text
    assert "חיות באנגלית" not in r.text
    assert "Addition up to 20" not in r.text
    assert 'data-ui-locale="ar"' in r.text


def test_catalog_home_he_keeps_hebrew_native_titles(platform_client: TestClient) -> None:
    r = platform_client.get("/?tab=catalog")
    assert r.status_code == 200
    assert "חיבור עד 20" in r.text
    assert "אור וצל" in r.text
    assert "Addition up to 20" not in r.text
    assert "الجمع حتى 20" not in r.text
