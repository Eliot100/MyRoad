# Library Claude SKILL.md files gap (2026-11-05)

Source: `library-files/30`–`32`, `45`, `46` SKILL.md and the Claude skills text
exports (`26`, `27`).

## What Library held

| File | Skill | Role |
|---|---|---|
| 30 | Verification Before Completion | Evidence before claiming done |
| 31 | Systematic Debugging | Reproduce → measure → root cause → fix → verify |
| 32 | Ponytail (code restraint) | Smallest correct change before PR |
| 45 | Apple UI Principles (filtered) | Full HIG for native iOS only; web gets motion/restraint/reduced-motion only |
| 46 | Code Quality Review | Correctness, security, a11y; no auto-merge |

Also in the Claude export: completeness standard, graphify, Ruflo agent-comms
patterns — tooling for Eliot's Claude setup, not MyRoad product rules.

## Gap vs this repo

MyRoad `skills/` currently has `myroad-work` only. The five Library skills are
**not** checked in here. Cursor/agent-level skills may exist outside the repo;
this note does not install them.

## Action

Planning inventory only. Promoting any of these into `skills/` needs an explicit
Eliot/frank decision (product vs agent hygiene). Do not treat Claude export text
as MyRoad product glossary or UI rules — those stay in `docs/product/` and
`docs/ui/lessons.md`.

## Pass 3 addendum — `47-MEMORY.md`

Library `47-MEMORY.md` is a GeoColl/Setup memory index that restates the same
standing rules (verification, never-assume, root-cause, systematic debugging,
ponytail, code quality, humanizer, Apple UI filtered for web). No new MyRoad
product rule. Still not installed under `skills/` without an Eliot/frank call.
