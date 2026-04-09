from __future__ import annotations

from .parsers import parse_suggestion_payload
from .prompts import build_suggestion_messages, build_suggestion_revision_messages
from .runtime import LLMStageInvoker


class SuggestionAgent:
    def __init__(self, invoker: LLMStageInvoker | None = None) -> None:
        self._invoker = invoker or LLMStageInvoker()

    def generate(self, state: dict, narration: str) -> list[str]:
        raw = self._invoker.invoke(build_suggestion_messages(state, narration), temperature=0.45, stage="suggestions")
        return parse_suggestion_payload(raw, state.get("fallback_actions", []))

    def revise(self, state: dict, narration: str, actions: list[str], feedback: str) -> list[str]:
        raw = self._invoker.invoke(
            build_suggestion_revision_messages(state, narration, actions, feedback),
            temperature=0.15,
            stage="suggestions",
        )
        return parse_suggestion_payload(raw, state.get("fallback_actions", []))
