from __future__ import annotations

from .parsers import parse_narrative_payload
from .prompts import build_narrative_messages, build_narrative_revision_messages
from .runtime import LLMStageInvoker


class NarrativeAgent:
    def __init__(self, invoker: LLMStageInvoker | None = None) -> None:
        self._invoker = invoker or LLMStageInvoker()

    def generate(self, state: dict, mechanics_event: dict | None) -> tuple[str, str | None, dict | None]:
        raw = self._invoker.invoke(
            build_narrative_messages(state, mechanics_event),
            temperature=0.7 if state.get("mode") == "turn" else 0.6,
            stage="narrative",
        )
        return parse_narrative_payload(
            raw,
            state.get("allowed_next_scenes", []),
            state.get("available_monsters", []),
        )

    def revise(
        self,
        state: dict,
        narration: str,
        next_scene: str | None,
        story_event: dict | None,
        mechanics_event: dict | None,
        feedback: str,
    ) -> tuple[str, str | None, dict | None]:
        raw = self._invoker.invoke(
            build_narrative_revision_messages(state, narration, next_scene, story_event, mechanics_event, feedback),
            temperature=0.2,
            stage="narrative",
        )
        return parse_narrative_payload(
            raw,
            state.get("allowed_next_scenes", []),
            state.get("available_monsters", []),
        )
