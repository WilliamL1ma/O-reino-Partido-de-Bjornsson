from __future__ import annotations


def get_story_flags(character, *, narrative_get_story_flags):
    return narrative_get_story_flags(character)


def get_story_inventory(character, *, narrative_get_story_inventory):
    return narrative_get_story_inventory(character)


def get_pending_event(character, *, narrative_get_pending_event):
    return narrative_get_pending_event(character)


def persist_story_state(
    character_id: int,
    *,
    narrative_persist_story_state,
    scene: str | None = None,
    act: int | None = None,
    flags: dict | None = None,
    inventory: list[dict] | None = None,
    xp_delta: int = 0,
    gold_delta: int = 0,
) -> None:
    narrative_persist_story_state(
        character_id,
        scene=scene,
        act=act,
        flags=flags,
        inventory=inventory,
        xp_delta=xp_delta,
        gold_delta=gold_delta,
    )


def summarize_memory_if_needed(character, *, narrative_summarize_memory_if_needed_with_llm, narrative_summarize_memory_if_needed) -> None:
    narrative_summarize_memory_if_needed_with_llm(
        character,
        summarize_memory=narrative_summarize_memory_if_needed,
    )
