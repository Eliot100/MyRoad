"""Enumerate every first-try answer pattern of the adaptive placement (real content) and the starting level it gives."""
import json, os, sys
from collections import Counter
from myroad_core import placement_cat as cat
from myroad_core.content.loader import load_content_paths, content_to_path_version
from myroad_core.content.variants import select_variants
from pathlib import Path
from myroad_core.content.placement_score import level_from_counts, tie_up_from_answers
CD = os.environ["CONTENT_DIR"]
PATHS = {p.id: p for p in load_content_paths(Path(CD))}
for subj in ["english", "math", "physics", "arabic"]:
    doc = content_to_path_version(PATHS[f"path_{subj}_bagrut5_00_placement"]).model_dump(mode="json", by_alias=True)
    doc = select_variants(doc, {})
    items = cat.items_from_doc(doc)
    levels = Counter(); lengths = Counter()
    def walk(resp):
        nxt = cat.next_item(items, resp)
        if nxt is None:
            c = sum(ok for _, ok in resp); w = len(resp) - c
            tie = tie_up_from_answers(items, resp)
            levels[level_from_counts(c, w, tie_up=tie)] += 1; lengths[len(resp)] += 1
            return
        for ok in (True, False):
            walk(resp + [(nxt.block_id, ok)])
    walk([])
    print(subj, "items", len(items), "patterns", sum(levels.values()), "levels", dict(sorted(levels.items())), "test lengths", dict(sorted(lengths.items())))
