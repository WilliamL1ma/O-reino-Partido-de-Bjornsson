from __future__ import annotations

import json
from typing import Any

from master_graph_components.parser import (
    extract_embedded_actions,
    extract_partial_narration,
    extract_json_text,
    extract_partial_suggested_actions,
    normalize_narrative_dialogue,
    normalize_jsonish,
    sanitize_actions,
    split_narration_and_jsonish,
    strip_json_artifacts,
)
from master_graph_components.review import contextual_actions_from_narration
from narrative.story_events import sanitize_story_event, story_event_from_next_scene

import re


VALID_ATTRIBUTES = {
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
    "perception",
}


def _load_json_candidate(raw_text: str) -> dict[str, Any] | None:
    leading_narration, jsonish = split_narration_and_jsonish(raw_text)
    candidate = normalize_jsonish(jsonish or extract_json_text(raw_text))
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return parsed
    if leading_narration:
        return {"narration": leading_narration}
    return None


def parse_mechanics_event(raw_text: str, available_monsters: list[str]) -> dict | None:
    parsed = _load_json_candidate(raw_text)
    if not isinstance(parsed, dict):
        return None

    event = parsed.get("event", parsed)
    if not isinstance(event, dict):
        return None

    event_type = str(event.get("type", "")).strip().lower()
    attribute = str(event.get("attribute", "")).strip().lower()
    if event_type not in {"skill_check", "encounter"}:
        return None
    if attribute and attribute not in VALID_ATTRIBUTES:
        return None

    cleaned = dict(event)
    if event_type == "encounter":
        monster_slug = str(cleaned.get("monster_slug", "")).strip().lower()
        if monster_slug and monster_slug not in available_monsters:
            return None
        if monster_slug:
            cleaned["monster_slug"] = monster_slug

    return cleaned


_EMBEDDED_NEXT_SCENE_RE = re.compile(r"\*{0,2}\s*next_scene\s*\*{0,2}\s*:\s*\"?([a-z0-9_]+)\"?", re.IGNORECASE)


def parse_narrative_payload(
    raw_text: str,
    allowed_next_scenes: list[str],
    available_monsters: list[str],
) -> tuple[str, str | None, dict | None]:
    parsed = _load_json_candidate(raw_text)
    leading_narration, _ = split_narration_and_jsonish(raw_text)

    narration = ""
    next_scene = None
    story_event = None
    if isinstance(parsed, dict):
        narration = str(parsed.get("narration", "")).strip()
        next_scene = str(parsed.get("next_scene", "")).strip() or None
        story_event = sanitize_story_event(
            parsed.get("story_event"),
            allowed_next_scenes=allowed_next_scenes,
            available_monsters=available_monsters,
        )

    if not narration:
        narration = extract_partial_narration(raw_text)
    narration = narration or leading_narration or strip_json_artifacts(raw_text).strip()
    embedded_match = _EMBEDDED_NEXT_SCENE_RE.search(narration)
    if embedded_match and not next_scene and not story_event:
        next_scene = embedded_match.group(1).strip()
    narration = _EMBEDDED_NEXT_SCENE_RE.sub("", narration).strip()
    narration, _ = extract_embedded_actions(narration)
    narration = normalize_narrative_dialogue(narration)
    narration = re.sub(r"\n{3,}", "\n\n", narration).strip()
    if next_scene not in allowed_next_scenes:
        next_scene = None
    if not story_event:
        story_event = story_event_from_next_scene(
            next_scene,
            allowed_next_scenes=allowed_next_scenes,
            available_monsters=available_monsters,
        )
    if story_event:
        next_scene = None
    return narration.strip(), next_scene, story_event


def parse_suggestion_payload(raw_text: str, fallback_actions: list[str]) -> list[str]:
    parsed = _load_json_candidate(raw_text)
    narration = ""
    if isinstance(parsed, dict):
        narration = str(parsed.get("narration", "")).strip()
        actions = sanitize_actions(parsed.get("suggested_actions"), fallback_actions)
        clean_narration, embedded_actions = extract_embedded_actions(narration)
        if embedded_actions:
            return sanitize_actions(embedded_actions, fallback_actions)
        if actions != fallback_actions[:5]:
            return actions
        contextual = contextual_actions_from_narration(clean_narration)
        return sanitize_actions(contextual, fallback_actions) if contextual else actions

    partial_actions = extract_partial_suggested_actions(raw_text)
    if partial_actions:
        return sanitize_actions(partial_actions, fallback_actions)

    stripped = strip_json_artifacts(raw_text).strip()
    clean_narration, embedded_actions = extract_embedded_actions(stripped)
    if embedded_actions:
        return sanitize_actions(embedded_actions, fallback_actions)
    contextual = contextual_actions_from_narration(clean_narration)
    if contextual:
        return sanitize_actions(contextual, fallback_actions)
    return fallback_actions[:5]
