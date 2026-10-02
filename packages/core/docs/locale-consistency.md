# Locale consistency rule

Platform **UI language** drives shell chrome **and** all catalog/path card chrome
(titles, blurbs, group names, subject labels, tab labels).

Learning **content tokens** (vocab/phrases being taught) stay in the path's
`content_locale` — they do **not** switch when the UI language changes.

## Data-driven locales (add a language with zero code changes)

1. Register the code in `packages/core/locales/manifest.json`
   (`code`, `label`, `dir` = `ltr`|`rtl`).
2. Add `packages/core/locales/<code>.json` with the same keys as `en.json`
   (shell strings).
3. On each content path, add entries under `titles` / `blurbs` (and topic
   `titles`) for that code — e.g. `"ru": "Сложение"`.

The language switcher, `t()`, `dir_for()`, and catalog picker (`pick` /
`list_catalog_cards(..., locale=)`) all read the manifest — no Python edits.

Fallback chain (manifest `fallback`, default `en` → `he`): requested locale →
fallback chain → any non-empty map value.

## Split

| Layer | Follows | Examples |
|-------|---------|----------|
| Platform UI / catalog chrome | UI locale (`myroad_locale`) | Tab labels, subject chips, group banner, **path card title & blurb** |
| Path explanations | UI locale | `body_ui` / `body_he` / `body_en`, feedback chrome |
| Content tokens | `content_locale` | `body_content`, `speak_text`, target vocab choice labels |

## Catalog strings

Each content path authors chrome as locale maps:

```json
{
  "id": "path_grade3_math_add20",
  "titles": {"he": "חיבור עד 20", "en": "Addition up to 20", "ar": "الجمع حتى 20"},
  "blurbs": {"he": "...", "en": "...", "ar": "..."}
}
```

Legacy flat fields (`title_he`, `title_en`, `title_ar`, `blurb_*`) are still
accepted and merged into the maps on load. Home cards pick via
`pick(map, locale)` / `list_catalog_cards(..., locale=)`.

`validate_catalog_chrome` requires every locale listed in the manifest.

- UI in Hebrew + English-learning path → Hebrew chrome/explanations; English words only
  in `body_content` / `speak_text` / choice labels that are the target vocab.
- Switching UI language switches shell + explanation + **catalog titles**; content tokens stay.

Enforced by schema maps + `myroad_core.content.locale_rules` + catalog locale tests (CI via pytest).
