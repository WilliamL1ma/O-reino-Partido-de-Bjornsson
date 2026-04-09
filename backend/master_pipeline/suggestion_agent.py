from __future__ import annotations

import logging

from narrative.authority import sanitize_suggested_actions

from .contracts import SuggestionAgentResult
from .parsers import parse_suggestion_payload
from .prompts import build_suggestion_messages, build_suggestion_revision_messages
from .reviewers import build_suggestion_fallback, review_suggestions
from .runtime import LLMStageInvoker, log_stage


class SuggestionAgent:
    def __init__(self, invoker: LLMStageInvoker | None = None) -> None:
        self._invoker = invoker or LLMStageInvoker()

    def _generate(self, state: dict, narration: str) -> list[str]:
        raw = self._invoker.invoke(build_suggestion_messages(state, narration), temperature=0.45)
        return parse_suggestion_payload(raw, state.get("fallback_actions", []))

    def _revise(self, state: dict, narration: str, actions: list[str], feedback: str) -> list[str]:
        raw = self._invoker.invoke(
            build_suggestion_revision_messages(state, narration, actions, feedback),
            temperature=0.15,
        )
        return parse_suggestion_payload(raw, state.get("fallback_actions", []))

    def run(self, state: dict, narration: str) -> SuggestionAgentResult:
        mode = str(state.get("mode", "turn"))
        diagnostics: list[str] = []

        try:
            draft_actions = self._generate(state, narration)
            reviewed_actions, review = review_suggestions(
                actions=draft_actions,
                narration=narration,
                authority=state.get("authoritative_state", {}),
                fallback_actions=state.get("fallback_actions", []),
            )

            if not review.valid:
                diagnostics.append("suggestion_review:failed")
                log_stage(logging.WARNING, "suggestion_review_failed", review.feedback, mode=mode)
                revised_actions = self._revise(state, narration, reviewed_actions, review.feedback)
                reviewed_actions, review = review_suggestions(
                    actions=revised_actions,
                    narration=narration,
                    authority=state.get("authoritative_state", {}),
                    fallback_actions=state.get("fallback_actions", []),
                )

            if not review.valid:
                diagnostics.append("suggestion_fallback")
                log_stage(logging.WARNING, "suggestion_fallback", review.feedback, mode=mode)
                actions = build_suggestion_fallback(state, narration)
                return SuggestionAgentResult(
                    actions=sanitize_suggested_actions(
                        actions,
                        state.get("authoritative_state", {}),
                        state.get("fallback_actions", []),
                    ),
                    used_fallback=True,
                    diagnostics=diagnostics,
                )

            diagnostics.append("suggestions:ok")
            return SuggestionAgentResult(
                actions=sanitize_suggested_actions(
                    reviewed_actions,
                    state.get("authoritative_state", {}),
                    state.get("fallback_actions", []),
                ),
                used_fallback=False,
                diagnostics=diagnostics,
            )
        except Exception as error:
            log_stage(logging.WARNING, "suggestions_failed", str(error), mode=mode)
            diagnostics.extend(["suggestions:error", "suggestion_fallback"])
            actions = build_suggestion_fallback(state, narration)
            return SuggestionAgentResult(
                actions=sanitize_suggested_actions(
                    actions,
                    state.get("authoritative_state", {}),
                    state.get("fallback_actions", []),
                ),
                used_fallback=True,
                diagnostics=diagnostics,
            )
