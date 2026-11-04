# Limdara

Learning roads. דרכי למידה.

This directory is the web platform and the Android app. It lives on the
`limdara-platform` branch so `main` — the Python MyRoad platform — stays as it was.

## Name

**Limdara** (said lim-DAR-ah) is the mark. It is coined from *limud* (learning)
and *derekh* (a road).

**דרכי למידה** is the Hebrew name published with it. That phrase is the meaning,
not the trademark: a line that only says “ways of learning” is descriptive, and
*Darchei* alone is already used by schools. “Learning roads” is the English line
for the same reason.

Before a company or a store listing, search Israel, the United States, and the
European Union in classes 9, 41, and 42. This note is not a legal clearance.

## What it is

- Web: five study roads (5-unit mathematics, English, physics, Arabic, and the psychometric), review, progress on the device, and the Forge audit.
- Android: the same platform, installed full screen from the browser (Chrome → Install app / Add to Home screen). A Play Store wrapper can come later; it would ship this app, not a second syllabus.

Progress stays in the browser. There are no accounts on this build.

## Run

```bash
cd apps/limdara
npm install
npm run dev
```

The dev server listens on port 8080.
