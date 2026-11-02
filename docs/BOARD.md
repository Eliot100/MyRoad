# MyRoad Board

Board: https://github.com/users/Eliot100/projects/4 (Project #4, id `PVT_kwHOAsGk884Bp51j`)

## Fields

- **Status**: Backlog (not yet sequenced), Ready (sequenced, can start), In progress, In review (PR open), Blocked (waiting on something), Done (merged).
- **Owner**: the bot or person responsible (dev, ui, content, pm, frank, Eliot, ...).
- **Priority**: P0 urgent, P1 high, P2 normal, P3 later.
- **Phase**: English, Arabic, Math, Psychometric, Platform, Stage 0 docs.

## Rules

1. Work from the top of Ready: highest Priority first, then lowest issue number.
2. Every bot moves its own card: In progress when it starts, In review when the PR opens, Blocked with a one-line issue comment saying what it waits for, Done when merged.
3. Anything waiting for Eliot gets Owner=Eliot and Status=Blocked.
4. New work = an issue with a `bot:<name>` label plus a card in Backlog.
5. PM owns the ordering and keeps Ready to at most about 10 cards.
6. frank reviews the board daily and decides priorities that are not product direction.

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

Status option ids: Backlog `666f56e2`, Ready `3f6d2ea8`, In progress `db041781`, In review `1ac4efee`, Blocked `a03b8f42`, Done `98236657`.

Other fields (same command, different field id):

- Owner `PVTSSF_lAHOAsGk884Bp51jzhoTSug`: dev `31e73fa4`, ui `fc47e641`, content `14e1e9c0`, pm `59930b65`, frank `ed8d9fca`, Eliot `1dc756a1`.
- Priority `PVTSSF_lAHOAsGk884Bp51jzhoTSvc`: P0 `dfafa265`, P1 `483dd8f7`, P2 `40bf7bb7`, P3 `bac1217d`.
- Phase `PVTSSF_lAHOAsGk884Bp51jzhoTSv4`: English `00b5bb79`, Arabic `53e5dc8c`, Math `68fafd77`, Psychometric `e0ca2430`, Platform `dd73a101`, Stage 0 docs `aaae7317`.

Add an issue to the board:

```sh
gh project item-add 4 --owner Eliot100 --url https://github.com/Eliot100/MyRoad/issues/123
```
