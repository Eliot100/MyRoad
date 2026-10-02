# How to add a UI locale (e.g. Russian `ru`)

No Python changes. Translation rows/files only.

## 1. Manifest

Edit `packages/core/locales/manifest.json`:

```json
{
  "default": "he",
  "fallback": ["en", "he"],
  "locales": [
    {"code": "he", "label": "עברית", "dir": "rtl"},
    {"code": "en", "label": "English", "dir": "ltr"},
    {"code": "ar", "label": "العربية", "dir": "rtl"},
    {"code": "ru", "label": "Русский", "dir": "ltr"}
  ]
}
```

## 2. Shell strings

Copy `packages/core/locales/en.json` → `ru.json` and translate values.
Keys must match (missing keys fall back via the manifest chain).

## 3. Catalog / path chrome

For each path under `packages/core/content/**/*.json`, add the new code to
`titles` and `blurbs` (and each topic's `titles`):

```json
"titles": {
  "he": "חיבור עד 20",
  "en": "Addition up to 20",
  "ar": "الجمع حتى 20",
  "ru": "Сложение до 20"
}
```

## 4. Verify

```bash
cd packages/core && pytest tests/test_catalog_locale.py -q
```

`test_fake_ru_locale_needs_no_code_change` proves the picker works for any
manifest locale without code edits.
