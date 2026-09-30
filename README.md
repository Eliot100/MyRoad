# MyRoad / מיי-רואד

**MyRoad** is an adaptive learning platform POC: turn a learner goal into a measurable path (blocks, edges, mastery)—not another unstructured tutoring chat.

**MyRoad** היא POC לפלטפורמת למידה אדפטיבית: המרת מטרת לומד למסלול מדיד (בלוקים, קשתות, שליטה) — לא עוד צ'אט חופשי.

**Product ID:** `MyRoad` · **Never auto-publish** — human approval is required to publish any learning path.

## v0 freeze contents / תוכן הקפאת v0

| Path | Description |
|------|-------------|
| `freeze/v0/01-path-before-feedback.json` | Golden scenario draft (quadratic equations / משוואות ריבועיות) before feedback |
| `freeze/v0/02-path-after-feedback.json` | Same path after feedback + remediation + `_diff` |
| `freeze/v0/03-agent-tool-contract.md` | Agent/tool ops, RBAC, audit — agent may draft/revise; **never auto-publish** |
| `freeze/v0/04-comparison.md` | Comparison vs first generic scaffold / השוואה לפיגום הגנרי |
| `docs/design-extraction.md` | Requirements extraction from design docs |

## Next build steps / שלבי בנייה הבאים

1. **Persistence** — versions, statuses, event log  
2. **Agent API** — tool contract + RBAC + audit  
3. **Thin UI** — learner path + minimal author/editor  
4. **Golden loop** — topic → draft → learn → feedback → revise → human publish  

## CI

On push/PR to `main`: checkout and validate both freeze path JSON files with `python -m json.tool`.

## License / note

Docs and freeze artifacts only in this commit. No published learning paths.
