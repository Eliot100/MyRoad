# Locale consistency rule

Platform **UI language** drives shell chrome **and** all catalog/path card chrome
(titles, blurbs, group names, subject labels, tab labels).

Learning **content tokens** (vocab/phrases being taught) stay in the path's
`content_locale` — they do **not** switch when the UI language changes.

## Split

| Layer | Follows | Examples |
|-------|---------|----------|
| Platform UI / catalog chrome | UI locale (`myroad_locale`) | Tab labels, subject chips, group banner, **path card title & blurb** |
| Path explanations | UI locale | `body_ui` / `body_he` / `body_en`, feedback chrome |
| Content tokens | `content_locale` | `body_content`, `speak_text`, target vocab choice labels |

## Catalog strings

Each content path should author `title_he` / `blurb_he` plus `title_en` / `blurb_en`
(and optionally `title_ar` / `blurb_ar`). Home cards pick the string by UI locale
with fallback (`pick_localized` / `list_catalog_cards(..., locale=)`).

- UI in Hebrew + English-learning path → Hebrew chrome/explanations; English words only
  in `body_content` / `speak_text` / choice labels that are the target vocab.
- Switching UI language switches shell + explanation + **catalog titles**; content tokens stay.

Enforced by schema fields + `myroad_core.content.locale_rules` + catalog locale tests (CI via pytest).
