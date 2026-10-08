# Vendored static files

| File | Source | Version | License |
|------|--------|---------|---------|
| `htmx-2.0.11.min.js` | npm `htmx.org@2.0.11`, `dist/htmx.min.js` (tarball shasum `a85363c4c5af94cd634df04c4b83d06dd0e91aa7`) | 2.0.11 | Zero-Clause BSD (0BSD) |

sha256 of the vendored file: `d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717`

Served from `/static`, no CDN at runtime. Only `play.html` (the step player) loads it.
To upgrade: replace the file with the new release's `dist/htmx.min.js`, rename it
with the new version, update the `<script>` tag in `templates/play.html`, this table,
and `HTMX_FILE` in `tests/test_step_player.py`.
