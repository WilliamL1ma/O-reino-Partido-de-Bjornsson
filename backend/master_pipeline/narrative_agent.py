from __future__ import annotations

import logging

from .contracts import NarrativeAgentResult
from .parsers import parse_narrative_payload
from .prompts import build_narrative_messages, build_narrative_revision_messages
from .reviewers import build_narrative_fallback, review_narration
from .runtime import LLMStageInvoker, log_stage


class NarrativeAgent:
    def __init__(self, invoker: LLMStageInvoker | None = None) -> None:
        self._invoker = invoker or LLMStageInvoker()

    def _generate(self, state: dict, mechanics_event: dict | None) -> tuple[str, str | None, dict | None]:
        raw = self._invoker.invoke(
            build_narrative_messages(state, mechanics_event),
            temperature=0.7 if state.get("mode") == "turn" else 0.6,
        )
        return parse_narrative_payload(
            raw,
            state.get("allowed_next_scenes", []),
            state.get("available_monsters", []),
        )

    def _revise(
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
        )
        return parse_narrative_payload(
            raw,
            state.get("allowed_next_scenes", []),
            state.get("available_monsters", []),
        )

    def run(self, state: dict, mechanics_event: dict | None) -> NarrativeAgentResult:
        mode = str(state.get("mode", "turn"))
        diagnostics: list[str] = []

        try:
            draft_narration, draft_next_scene, draft_story_event = self._generate(state, mechanics_event)
            review = review_narration(
                narration=draft_narration,
                player_message=str(state.get("player_message", "")),
                recent_messages=state.get("recent_messages", []),
            )

            if not review.valid:
                diagnostics.append("narrative_review:failed")
                log_stage(logging.WARNING, "narrative_review_failed", review.feedback, mode=mode)
                draft_narration, draft_next_scene, draft_story_event = self._revise(
                    state,
                    draft_narration,
                    draft_next_scene,
                    draft_story_event,
                    mechanics_event,
                    review.feedback,
                )
                review = review_narration(
                    narration=draft_narration,
                    player_message=str(state.get("player_message", "")),
                    recent_messages=state.get("recent_messages", []),
                )

            if not review.valid:
                diagnostics.append("narrative_fallback")
                log_stage(logging.WARNING, "narrative_fallback", review.feedback, mode=mode)
                return NarrativeAgentResult(
                    narration=build_narrative_fallback(state),
                    next_scene=None,
                    story_event=None,
                    used_fallback=True,
                    diagnostics=diagnostics,
                )

            diagnostics.append("narrative:ok")
            return NarrativeAgentResult(
                narration=draft_narration,
                next_scene=draft_next_scene,
                story_event=draft_story_event,
                used_fallback=False,
                diagnostics=diagnostics,
            )
        except Exception as error:
            log_stage(logging.WARNING, "narrative_failed", str(error), mode=mode)
            diagnostics.extend(["narrative:error", "narrative_fallback"])
            return NarrativeAgentResult(
                narration=build_narrative_fallback(state),
                next_scene=None,
                story_event=None,
                used_fallback=True,
                diagnostics=diagnostics,
            )
