# MyRoad Board

Board: https://github.com/users/Eliot100/projects/4 (Project #4 "MyRoad - לוח עבודה", id `PVT_kwHOAsGk884Bp51j`)

## Fields

- **Status**: רעיונות (Backlog) = not yet sequenced, מוכן (Ready) = sequenced, can start, בעבודה (In progress), בבדיקה (In review) = PR open, חסום (Blocked) = waiting on something, הושלם (Done) = merged.
- **Owner**: the bot or person responsible (dev, ui, content, pm, frank, Eliot, ...).
- **Priority**: P0 דחוף (urgent), P1 גבוה (high), P2 רגיל (normal), P3 בהמשך (later).
- **Phase**: אנגלית (English), ערבית (Arabic), מתמטיקה (Math), פסיכומטרי (Psychometric), פלטפורמה (Platform), שלב 0 מסמכים (Stage 0 docs).

## Rules

1. Work from the top of Ready: highest Priority first, then lowest issue number.
2. Every bot moves its own card: In progress when it starts, In review when the PR opens, Blocked with a one-line issue comment saying what it waits for, Done when merged.
3. Anything waiting for Eliot gets Owner=Eliot and Status=Blocked.
4. New work = an issue with a `bot:<name>` label plus a card in Backlog.
5. PM owns the ordering and keeps Ready to at most about 10 cards.
6. frank reviews the board daily and decides priorities that are not product direction.
7. New cards get short, plain Hebrew titles. Keep code identifiers (#123, file names, API names) as they are.
8. Option names are bilingual, Hebrew first. When you match a Status or Phase by name, match the English part in parentheses (for example `test("\\(In review\\)$")`), never the full string. For Priority, match the `P0`..`P3` prefix. Best of all, use the option ids below; they did not change in the rename.

## Commands

Find an item id for issue 123:

```sh
gh project item-list 4 --owner Eliot100 --limit 300 --format json \
  --jq '.items[] | select(.content.number==123) | .id'
```

Set Status (replace ITEM_ID and the option id):

```sh
gh project item-edit --project-id PVT_kwHOAsGk884Bp51j --id ITEM_ID \
  --field-id PVTSSF_lAHOAsGk884Bp51jzhoTSoI --single-select-option-id 1ac4efee
```

Status option ids: רעיונות (Backlog) `666f56e2`, מוכן (Ready) `3f6d2ea8`, בעבודה (In progress) `db041781`, בבדיקה (In review) `1ac4efee`, חסום (Blocked) `a03b8f42`, הושלם (Done) `98236657`.

Other fields (same command, different field id):

- Owner `PVTSSF_lAHOAsGk884Bp51jzhoTSug`: dev `31e73fa4`, ui `fc47e641`, content `14e1e9c0`, pm `59930b65`, frank `ed8d9fca`, Eliot `1dc756a1`.
- Priority `PVTSSF_lAHOAsGk884Bp51jzhoTSvc`: P0 דחוף `dfafa265`, P1 גבוה `483dd8f7`, P2 רגיל `40bf7bb7`, P3 בהמשך `bac1217d`.
- Phase `PVTSSF_lAHOAsGk884Bp51jzhoTSv4`: אנגלית (English) `00b5bb79`, ערבית (Arabic) `53e5dc8c`, מתמטיקה (Math) `68fafd77`, פסיכומטרי (Psychometric) `e0ca2430`, פלטפורמה (Platform) `dd73a101`, שלב 0 מסמכים (Stage 0 docs) `aaae7317`.

Add an issue to the board:

```sh
gh project item-add 4 --owner Eliot100 --url https://github.com/Eliot100/MyRoad/issues/123
```

## CI checks on main

Ruleset "required CI checks on main" (id 24684510) requires `core-tests`, `validate-freeze-json` and `a11y` (axe + Playwright, incl. the service-worker browser tests) before a PR can merge. `docker-image` runs but isn't required. `a11y` became required on 2026-11-03 after 10 green runs on main in a row with no re-runs (decision 0008). To change the list, `GET repos/Eliot100/MyRoad/rulesets/24684510`, edit `required_status_checks`, and `PUT` the whole ruleset back so no other rule is lost.
