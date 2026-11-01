# Optional scratchpad on practice steps (2026-11-01, UI bot)

## Context
Eliot, on math step 2 (487 + 256, multiple choice): there is no place to write out working.
Constraints: no server route or store change, never graded, light/dark, RTL, 375px, he/en/ar,
no game mechanics. DoD: closed by default; text survives Previous / Next; axe clean; 4 screenshots.

## Options considered (drawing)
| Option | Pros | Cons | Score | Cost to switch later |
| --- | --- | --- | --- | --- |
| A. Textarea + small canvas with pointer events (chosen) | ~90 lines of vanilla JS, no dependency, works with finger, pen and mouse, strokes redrawn in the theme ink | No undo, no pressure; canvas is not readable by screen readers (the textarea is the accessible path) | 22/25 | low |
| B. Textarea only | Smallest, fully accessible | Column addition and fractions are easier to sketch than type | 18/25 | low: add A later |
| C. Library (perfect-freehand, signature_pad, Excalidraw) | Smoother strokes, undo, export | New vendored dependency and licence review for a scratch area; Excalidraw is far too heavy | 17/25 | medium |

## Decision
A. Typing stays the primary, accessible path (labelled dir=auto textarea); the canvas is an
optional extra with a labelled clear button, touch-action none, and currentColor ink so it follows
the theme. Stored as normalised points, redrawn on resize and theme change.

Storage: localStorage key `myroad.scratch.<userId>.<pathId>.<blockId>` holding
{t: text, s: strokes, o: open}. Nothing is posted; nothing is graded. Capped at 4000 points.

Worked method: content nodes get an optional `worked_method` string (explain locale, plain text,
newlines kept, math isolated with the bdi filter), shown in a closed details block above the pad.
Existing JSON without the field is unchanged.

## Verified
- pytest (full core suite) passes, incl. tests/test_scratchpad.py (headless Chrome: text survives Previous then Next).
- axe on the open pad: 0 violations, 375 and 1280, light and dark.
- Screenshots: docs/ui/screens/183/.

## Known limits
- The pad lives on one device and browser; clearing site data clears it.
- No undo for strokes (clear only).
- The method field is only rendered once Content adds `worked_method` to nodes.

## How to switch
To B: remove the .scratch-draw block in _step_card.html and the canvas part of the scratchpad
script in platform.js. To C: vendor the library under static/, replace the pointer handlers; the
storage key and template stay the same.
