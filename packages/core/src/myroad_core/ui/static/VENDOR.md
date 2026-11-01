# Vendored static files

| File | Source | Version | License |
|------|--------|---------|---------|
| `htmx-2.0.11.min.js` | npm `htmx.org@2.0.11`, `dist/htmx.min.js` (tarball shasum `a85363c4c5af94cd634df04c4b83d06dd0e91aa7`) | 2.0.11 | Zero-Clause BSD (0BSD) |

sha256 of the vendored file: `d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717`

Served from `/static`, no CDN at runtime. Only `play.html` (the step player) loads it.
To upgrade: replace the file with the new release's `dist/htmx.min.js`, rename it
with the new version, update the `<script>` tag in `templates/play.html`, this table,
and `HTMX_FILE` in `tests/test_step_player.py`.

| `fonts/noto-naskh-arabic-wght.woff2` | npm `@fontsource-variable/noto-naskh-arabic@5.3.0`, `files/noto-naskh-arabic-arabic-wght-normal.woff2` (Arabic subset, wght 400-700) | 5.3.0 | SIL OFL 1.1 (`fonts/OFL-noto-naskh-arabic.txt`) |

sha256: `2a10d33e1f7129ab2b6ec76666e82ac5b509fbcfa7b4a3a1289bff42d2d64cd7`. Declared in `platform.css` as "MyRoad Naskh" with an Arabic `unicode-range`, so pages without Arabic never download it.
