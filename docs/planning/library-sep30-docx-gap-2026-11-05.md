# Library Sep 30 Hebrew docx gap (2026-11-05)

Sources (docx → text extract):
- `54-01-chazon-umatarah.docx` — vision and POC purpose
- `55-02-afyun-meforat.docx` — detailed entities / cycles
- `53-03-mimush-uvdinot.docx` — implementation stages and acceptance
- `52-04-lifney-mimush.docx` — lock-before-code risks

Status on disk: internal drafts, version 0.1, 30 Sep 2026, “טיוטת תכנון”.

## Relation to current `docs/product/`

These predate the Oct 21–31 product set (00–09, BOT-PROMPT) and the
2026-10-23 glossary “אושר פעמיים” structure. Current approved direction is
adult Hebrew speaker → English 5-unit series first, not the Sep 30 “generic
platform / founder-as-sole-evaluator / full agent draft” POC framing.

**Do not copy these docx into `docs/product/` as decisions.**

## Still useful as historical engineering notes

1. Lock before code (`52`): canonical path JSON contract; closed block/edge
   types; mastery per block type; version policy on open attempts; agent tool
   argument schemas; UI locale vs path language (RTL as schema, not polish).
2. Core vs shell content (`52`/`55`): verified core vs rewriteable shell;
   feedback of type “error” raises review, not only rephrase.
3. Implementation order (`53`): data model + event log → agent tools → thin
   learner UI → feedback/revise/publish golden loop → then width.
4. Entity sketch (`55`): attempt states, edge kinds
   (prerequisite/sequence/alternative/remediation), multi-channel block
   execution — largely echoed in path-viewer PathStore shapes already.

## Action

This note only. No product decision edits.
