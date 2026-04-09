from __future__ import annotations

import json
import re
import unicodedata


def fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return without_accents.lower().strip()


def extract_json_text(raw_text: str) -> str:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3:
            cleaned = "\n".join(lines[1:-1]).strip()
    return cleaned


def split_narration_and_jsonish(raw_text: str) -> tuple[str, str]:
    cleaned = extract_json_text(raw_text)
    match = re.search(r"(\{[\s\S]*\})\s*$", cleaned)
    if not match:
        return cleaned.strip(), ""

    jsonish = match.group(1).strip()
    narration = cleaned[: match.start()].strip()
    return narration, jsonish


def strip_json_artifacts(raw_text: str) -> str:
    cleaned = re.sub(r"```(?:json)?\s*[\s\S]*?```", "", raw_text, flags=re.IGNORECASE).strip()
    leading_narration, jsonish = split_narration_and_jsonish(cleaned)
    if jsonish:
        return leading_narration.strip()
    return cleaned


def normalize_jsonish(candidate: str) -> str:
    normalized = candidate.strip()
    if not normalized:
        return normalized

    normalized = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)", r'\1"\2"\3', normalized)
    normalized = re.sub(r"\bNone\b", "null", normalized)
    normalized = re.sub(r"\bTrue\b", "true", normalized)
    normalized = re.sub(r"\bFalse\b", "false", normalized)
    return normalized


def _decode_json_string_literal(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        return ""
    try:
        return json.loads(f'"{candidate}"')
    except json.JSONDecodeError:
        return candidate.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t").strip()


def _extract_partial_narration(raw_text: str) -> str:
    cleaned = extract_json_text(raw_text)
    match = re.search(r'"narration"\s*:\s*"((?:\\.|[^"\\])*)', cleaned, flags=re.IGNORECASE)
    if not match:
        return ""
    return _decode_json_string_literal(match.group(1)).strip()


def extract_partial_narration(raw_text: str) -> str:
    return _extract_partial_narration(raw_text)


def _extract_partial_suggested_actions(raw_text: str) -> list[str]:
    cleaned = extract_json_text(raw_text)
    if '"suggested_actions"' not in cleaned:
        return []

    actions: list[str] = []
    for match in re.finditer(
        r'"(?:acao|ação|action|label|text|title|name|summary)"\s*:\s*"((?:\\.|[^"\\])*)',
        cleaned,
        flags=re.IGNORECASE,
    ):
        text = _decode_json_string_literal(match.group(1)).strip()
        if text and text not in actions:
            actions.append(text)
        if len(actions) == 5:
            break
    return actions


def extract_partial_suggested_actions(raw_text: str) -> list[str]:
    return _extract_partial_suggested_actions(raw_text)


def normalize_narrative_dialogue(narration: str) -> str:
    text = narration.strip()
    if not text:
        return text

    # Remove outer quotes when the whole narration was accidentally serialized as one giant string.
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        inner = text[1:-1].strip()
        if inner:
            text = inner
    elif text.startswith('"') and text.count('"') == 1:
        text = text[1:].strip()
    elif text.endswith('"') and text.count('"') == 1:
        text = text[:-1].strip()

    text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")

    # Normalize dialogue introduced with single quotes after a speech verb.
    text = re.sub(
        r"(:\s*)'([^'\n]+)'",
        lambda match: f'{match.group(1)}"{match.group(2).strip()}"',
        text,
    )

    return text.strip()


def extract_action_text(item: object) -> str:
    if isinstance(item, dict):
        for key in ("acao", "ação", "action", "label", "text", "title", "name", "summary"):
            value = item.get(key)
            if value is not None:
                text = str(value).strip()
                if text:
                    return text
        return ""
    return str(item).strip()


def sanitize_actions(actions: object, fallback_actions: list[str]) -> list[str]:
    if not isinstance(actions, list):
        return fallback_actions[:5]

    sanitized: list[str] = []
    for item in actions:
        text = extract_action_text(item)
        if text and text not in sanitized:
            sanitized.append(text)
        if len(sanitized) == 5:
            break

    return sanitized or fallback_actions[:5]


def looks_like_action_header(line: str) -> bool:
    folded = fold_text(line).rstrip(":")
    return bool(
        re.match(
            r"^((aqui estao )?(algumas )?sugestoes( de acoes)?( possiveis)?|suggested actions|suggested_actions|voce (agora )?(tem as seguintes opcoes|pode|pode fazer|poderia|poderia fazer)|voce (pode|pode fazer|poderia|poderia fazer) agora|acoes recomendadas para este momento|opcoes recomendadas|opcoes|escolhas possiveis)$",
            folded,
        )
    )


def split_action_header(line: str) -> tuple[str, bool]:
    folded = fold_text(line)
    match = re.search(
        r"((aqui estao )?(algumas )?sugestoes( de acoes)?( possiveis)?|suggested actions|suggested_actions|voce (agora )?(tem as seguintes opcoes|pode|pode fazer|poderia|poderia fazer)|voce (pode|pode fazer|poderia|poderia fazer) agora|acoes recomendadas para este momento|opcoes recomendadas|opcoes|escolhas possiveis)\s*:?\s*$",
        folded,
    )
    if not match:
        return line, False

    before = line[: match.start()].rstrip()
    if before and before[-1] not in ".!?:":
        return line, False
    return before, True


def is_action_prompt(line: str) -> bool:
    folded = fold_text(line).rstrip(":")
    return folded in {
        "o que voce deseja fazer",
        "qual sera sua proxima acao",
        "qual sera a sua proxima acao",
        "como voce deseja agir",
    }


def extract_embedded_actions(narration: str) -> tuple[str, list[str]]:
    text = narration.strip()
    if not text:
        return text, []

    original_lines = text.splitlines()
    before_lines: list[str] | None = None
    remainder_lines: list[str] | None = None

    for index, line in enumerate(original_lines):
        stripped = line.strip()
        if not stripped:
            continue

        inline_before, has_header = split_action_header(stripped)
        if not has_header:
            continue

        before_lines = [part for part in original_lines[:index] if part.strip()]
        if inline_before:
            before_lines.append(inline_before)
        remainder_lines = original_lines[index + 1 :]
        break

    if before_lines is None or remainder_lines is None:
        return text, []

    before = "\n".join(before_lines).rstrip()
    remainder = "\n".join(remainder_lines).strip()
    if not remainder:
        return before, []

    actions: list[str] = []
    trailing_text: list[str] = []

    for raw_line in remainder.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        inline_before, has_header = split_action_header(stripped)
        if has_header:
            if inline_before:
                trailing_text.append(inline_before)
            continue

        normalized = re.sub(r"^\d+\.\s*", "", stripped)
        normalized = re.sub(r"^[\*\-\u2022]\s*", "", normalized).strip()
        if looks_like_action_header(normalized):
            continue
        if is_action_prompt(normalized):
            continue
        if normalized and len(actions) < 5:
            actions.append(normalized)
            continue
        trailing_text.append(stripped)

    cleaned_parts = [part for part in [before, " ".join(trailing_text).strip()] if part]
    cleaned_narration = "\n\n".join(cleaned_parts).strip()
    return cleaned_narration or before, actions


def parse_json_payload(
    raw_text: str,
    allowed_next_scenes: list[str],
    available_monsters: list[str],
    fallback_actions: list[str],
    contextual_actions_from_narration,
) -> tuple[str, dict | None, str | None, list[str]]:
    leading_narration, jsonish = split_narration_and_jsonish(raw_text)
    candidate = normalize_jsonish(jsonish or extract_json_text(raw_text))
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        partial_narration = _extract_partial_narration(raw_text)
        partial_actions = _extract_partial_suggested_actions(raw_text)
        if partial_narration:
            contextual_actions = contextual_actions_from_narration(partial_narration)
            return (
                partial_narration,
                None,
                None,
                sanitize_actions(partial_actions or contextual_actions, fallback_actions),
            )
        plain_narration, embedded_actions = extract_embedded_actions(leading_narration or raw_text.strip())
        if embedded_actions:
            return plain_narration, None, None, sanitize_actions(embedded_actions, fallback_actions)
        contextual_actions = contextual_actions_from_narration(plain_narration)
        if contextual_actions:
            return plain_narration, None, None, contextual_actions
        return plain_narration, None, None, fallback_actions[:5]

    narration = str(parsed.get("narration", "")).strip() or leading_narration or "O mestre permanece em silencio por um instante."
    event = parsed.get("event")
    if not isinstance(event, dict):
        event = None
    else:
        event_type = str(event.get("type", "")).strip().lower()
        attribute = str(event.get("attribute", "")).strip().lower()
        if event_type not in {"skill_check", "encounter"}:
            event = None
        elif attribute not in {
            "strength",
            "dexterity",
            "constitution",
            "intelligence",
            "wisdom",
            "charisma",
            "perception",
        }:
            event = None
        elif event_type == "encounter":
            monster_slug = str(event.get("monster_slug", "")).strip().lower()
            if monster_slug not in available_monsters:
                event = None

    next_scene = str(parsed.get("next_scene", "")).strip() or None
    if next_scene not in allowed_next_scenes:
        next_scene = None

    embedded_narration, embedded_actions = extract_embedded_actions(narration)
    narration = embedded_narration
    suggested_actions = sanitize_actions(parsed.get("suggested_actions"), fallback_actions)
    if embedded_actions:
        suggested_actions = sanitize_actions(embedded_actions, fallback_actions)
    elif suggested_actions == fallback_actions[:5]:
        contextual_actions = contextual_actions_from_narration(narration)
        if contextual_actions:
            suggested_actions = contextual_actions
    return narration, event, next_scene, suggested_actions

