"""Practice modes on a stage: typing, voice, a calm round, a short level test.

Choice tiles stay the default. A typed answer or a transcript is checked against
the same label the choices already use. Nothing here invents a new fact.
A round is a few questions from one stage, with a clock and a run of correct
answers that dies with the round. It is not a day streak and not a game.
A level test asks one saved question from each stage in that level. It does
not lock the next level.
"""

from __future__ import annotations

import re
import time
from typing import Any

from myroad_core.content.exercise_gen import StageGenerator
from myroad_core.content.loader import load_content_paths
from myroad_core.content.schema import ContentPath
from myroad_core.ui.answers import _normalize_token

ROUND_SECONDS = 180
ROUND_SIZE = 5
_HARAKAT = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_PUNCT = re.compile(r"[.!?؟،,:;\"'«»()\[\]…]+")
_DECIMAL = re.compile(r"(?<=\d)\.(?=\d)")
_ALEF = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})
_DEC_MARK = "\u0001"


def fold(value: str | None) -> str:
    """One comparison form: Arabic letters, punctuation, then the shared token fold."""
    text = _HARAKAT.sub("", str(value or ""))
    text = text.translate(_ALEF)
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    # A dot between digits is a decimal, not a sentence stop, so 8 and 8.0 match.
    text = _DECIMAL.sub(_DEC_MARK, text)
    text = _PUNCT.sub(" ", text)
    text = text.replace(_DEC_MARK, ".")
    return _normalize_token(text)


def _labels_for(kids: dict[str, Any], ids: list[str]) -> list[str]:
    wanted = set(ids)
    out: list[str] = []
    for choice in kids.get("choices") or []:
        if choice.get("id") in wanted and (choice.get("label") or "").strip():
            out.append(str(choice["label"]))
    return out


def correct_labels(kids: dict[str, Any]) -> list[str]:
    """Labels of the correct choice. Empty when more than one choice is correct."""
    correct = kids.get("correct")
    if isinstance(correct, list):
        if len(correct) != 1:
            return []
        correct = correct[0]
    if not isinstance(correct, str) or not correct:
        return []
    return _labels_for(kids, [correct])


def speak_target(kids: dict[str, Any]) -> str:
    for key in ("speak_text", "speak_ui", "body_content"):
        value = kids.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    labels = correct_labels(kids)
    return labels[0] if labels else ""


def _matches_any(given: str, targets: list[str]) -> bool:
    folded = fold(given)
    if not folded:
        return False
    for target in targets:
        wanted = fold(target)
        if not wanted:
            continue
        if folded == wanted:
            return True
        if len(wanted) >= 4 and " " in wanted and wanted in folded:
            return True
        if len(wanted) > 40 and wanted[:40] in folded:
            return True
    return False


def check_typed(kids: dict[str, Any], typed: str) -> bool:
    labels = correct_labels(kids)
    if labels:
        return _matches_any(typed, labels)
    target = speak_target(kids)
    return bool(target) and _matches_any(typed, [target])


def check_transcript(kids: dict[str, Any], transcript: str) -> bool:
    labels = correct_labels(kids)
    if labels:
        return _matches_any(transcript, labels)
    target = speak_target(kids)
    return bool(target) and _matches_any(transcript, [target])


def voice_lang(kids: dict[str, Any], content_locale: str) -> str:
    sample = speak_target(kids) or str(kids.get("body_content") or "")
    if re.search(r"[\u0600-\u06FF]", sample):
        return "ar"
    if re.search(r"[\u0590-\u05FF]", sample) and not re.search(r"[A-Za-z]", sample):
        return "he-IL"
    loc = (content_locale or "en").split("-")[0].lower()
    if loc == "ar":
        return "ar"
    if loc == "he":
        return "he-IL"
    return "en-US"


def _path(path_id: str) -> ContentPath | None:
    for path in load_content_paths():
        if path.id == path_id:
            return path
    return None


def _topic_of_node(path: ContentPath, node_id: str | None):
    if not node_id:
        return None
    base = node_id.split("__", 1)[0]
    for topic in path.topics or []:
        for nid in topic.node_ids:
            if nid == node_id or nid.split("__", 1)[0] == base:
                return topic
    return None


def step_modes(doc: dict[str, Any], block: dict[str, Any] | None, kids: dict[str, Any]) -> dict[str, Any]:
    """What the step card may offer. Choice tiles stay available whenever they exist."""
    node_type = kids.get("type") or ""
    has_choices = bool(kids.get("choices")) and bool(correct_labels(kids))
    content_locale = str(doc.get("contentLocale") or doc.get("contentLanguage") or "he")
    spoken = node_type == "speak" or bool(kids.get("speak_text") or kids.get("speak_ui"))
    voice = spoken or content_locale.split("-")[0].lower() in ("en", "ar") or has_choices
    if voice and not has_choices and not speak_target(kids):
        voice = False
    show = node_type in ("practice", "check", "speak") or spoken
    path_id = str(doc.get("pathId") or "")
    teaching = "_bagrut5_" in path_id and "placement" not in path_id
    round_href = None
    level_href = None
    if teaching and block:
        path = _path(path_id)
        node_id = kids.get("id") or (block.get("content") or {}).get("nodeId")
        topic = _topic_of_node(path, node_id) if path else None
        if topic is not None and topic.level in (1, 2, 3):
            round_href = f"/play/{path_id}/round/{topic.id}"
            if path and _is_level_end(path, topic.id):
                level_href = f"/play/{path_id}/level/{topic.level}"
    return {
        "show": show and (has_choices or voice or round_href),
        "choices": has_choices and node_type in ("practice", "check"),
        "type": has_choices and node_type in ("practice", "check"),
        "voice": bool(voice and show),
        "listen": True,
        "round_href": round_href,
        "level_href": level_href,
        "voice_lang": voice_lang(kids, content_locale),
    }


def _is_level_end(path: ContentPath, topic_id: str) -> bool:
    topic = next((t for t in (path.topics or []) if t.id == topic_id), None)
    if topic is None or topic.level not in (1, 2, 3):
        return False
    same = [t for t in (path.topics or []) if t.level == topic.level]
    return bool(same) and same[-1].id == topic_id


def _items_from_stage(path: ContentPath, topic, limit: int) -> list[dict[str, Any]]:
    stage = StageGenerator(path, topic)
    seeds = stage._seed_exercises()
    if len(seeds) < limit:
        seeds = seeds + [item for item in stage.samples(limit) if item.parameters[0] != "seed"]
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    title = (topic.titles or {}).get("he") or topic.title_he or topic.id
    for exercise in seeds:
        if exercise.prompt in seen:
            continue
        seen.add(exercise.prompt)
        node_id = exercise.parameters[1] if exercise.parameters[0] == "seed" else None
        out.append(
            {
                "prompt": exercise.prompt,
                "choices": list(exercise.choices),
                "answer": exercise.answer,
                "node_id": node_id,
                "stage": title,
            }
        )
        if len(out) >= limit:
            break
    return out


def build_round(path_id: str, topic_id: str) -> list[dict[str, Any]]:
    path = _path(path_id)
    if path is None:
        return []
    topic = next((t for t in (path.topics or []) if t.id == topic_id and t.level in (1, 2, 3)), None)
    if topic is None:
        return []
    return _items_from_stage(path, topic, ROUND_SIZE)


def build_level_test(path_id: str, level: int) -> list[dict[str, Any]]:
    path = _path(path_id)
    if path is None or level not in (1, 2, 3):
        return []
    out: list[dict[str, Any]] = []
    for topic in path.topics or []:
        if topic.level != level:
            continue
        picked = _items_from_stage(path, topic, 1)
        if picked:
            out.append(picked[0])
    return out


def new_round_state(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "items": items,
        "index": 0,
        "streak": 0,
        "best": 0,
        "hits": 0,
        "started": time.monotonic(),
        "done": not items,
    }


def round_view(state: dict[str, Any], now: float | None = None) -> dict[str, Any]:
    """Public view. The answer stays on the state dict and is not copied here."""
    clock = time.monotonic() if now is None else now
    elapsed = clock - float(state.get("started") or clock)
    left = max(0, ROUND_SECONDS - int(elapsed))
    items = state.get("items") or []
    index = int(state.get("index") or 0)
    timed_out = left <= 0 and bool(items) and index < len(items)
    done = bool(state.get("done")) or timed_out or index >= len(items)
    current = items[index] if items and not done else None
    return {
        "done": done or not items,
        "timed_out": timed_out,
        "left_min": max(0, (left + 59) // 60) if not done else 0,
        "streak": int(state.get("streak") or 0),
        "best": int(state.get("best") or 0),
        "hits": int(state.get("hits") or 0),
        "total": len(items),
        "index": min(index, max(0, len(items) - 1)),
        "prompt": None if current is None else current["prompt"],
        "choices": [] if current is None else list(current["choices"]),
        "empty": not items,
    }


def mark_round(state: dict[str, Any], choice: str) -> bool:
    items = state.get("items") or []
    index = int(state.get("index") or 0)
    if index >= len(items):
        state["done"] = True
        return False
    ok = fold(choice) == fold(items[index]["answer"]) and fold(choice) != ""
    if ok:
        state["hits"] = int(state.get("hits") or 0) + 1
        state["streak"] = int(state.get("streak") or 0) + 1
        state["best"] = max(int(state.get("best") or 0), int(state["streak"]))
    else:
        state["streak"] = 0
    state["index"] = index + 1
    if state["index"] >= len(items):
        state["done"] = True
    return ok


def new_level_state(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"items": items, "index": 0, "hits": 0, "misses": [], "done": not items}


def level_view(state: dict[str, Any]) -> dict[str, Any]:
    items = state.get("items") or []
    index = int(state.get("index") or 0)
    done = bool(state.get("done")) or index >= len(items)
    current = items[index] if items and not done else None
    return {
        "done": done or not items,
        "empty": not items,
        "hits": int(state.get("hits") or 0),
        "total": len(items),
        "index": index if not done else max(0, len(items) - 1),
        "prompt": None if current is None else current["prompt"],
        "choices": [] if current is None else list(current["choices"]),
        "stage": "" if current is None else current.get("stage") or "",
        "misses": list(state.get("misses") or []),
    }


def mark_level(state: dict[str, Any], choice: str) -> bool:
    items = state.get("items") or []
    index = int(state.get("index") or 0)
    if index >= len(items):
        state["done"] = True
        return False
    item = items[index]
    ok = fold(choice) == fold(item["answer"]) and fold(choice) != ""
    if ok:
        state["hits"] = int(state.get("hits") or 0) + 1
    else:
        misses = list(state.get("misses") or [])
        stage = item.get("stage") or ""
        if stage and stage not in misses:
            misses.append(stage)
        state["misses"] = misses
    state["index"] = index + 1
    if state["index"] >= len(items):
        state["done"] = True
    return ok
