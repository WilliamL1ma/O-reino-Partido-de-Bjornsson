from __future__ import annotations

from .mechanics_agent import MechanicsAgent
from .narrative_agent import NarrativeAgent
from .contracts import SuggestionAgentResult
from .runtime import LLMStageInvoker
from .suggestion_agent import SuggestionAgent


class MasterOrchestrator:
    def __init__(
        self,
        *,
        invoker: LLMStageInvoker | None = None,
        mechanics_agent: MechanicsAgent | None = None,
        narrative_agent: NarrativeAgent | None = None,
        suggestion_agent: SuggestionAgent | None = None,
    ) -> None:
        shared_invoker = invoker or LLMStageInvoker()
        self.mechanics_agent = mechanics_agent or MechanicsAgent(shared_invoker)
        self.narrative_agent = narrative_agent or NarrativeAgent(shared_invoker)
        self.suggestion_agent = suggestion_agent or SuggestionAgent(shared_invoker)

    def invoke(self, state: dict) -> dict:
        diagnostics: list[str] = []
        mode = str(state.get("mode", "turn"))

        mechanics_result = self.mechanics_agent.run(state)
        diagnostics.extend(mechanics_result.diagnostics)

        narrative_result = self.narrative_agent.run(state, mechanics_result.event)
        diagnostics.extend(narrative_result.diagnostics)

        if mode == "turn" and (mechanics_result.event is not None or narrative_result.story_event is not None):
            suggestion_result = SuggestionAgentResult(
                actions=[],
                used_fallback=False,
                diagnostics=["suggestions:blocked_pending_event"],
            )
        else:
            suggestion_result = self.suggestion_agent.run(state, narrative_result.narration)
        diagnostics.extend(suggestion_result.diagnostics)

        if narrative_result.used_fallback and not suggestion_result.used_fallback:
            diagnostics.append("fallbacks:only_narrative")
        elif suggestion_result.used_fallback and not narrative_result.used_fallback:
            diagnostics.append("fallbacks:only_suggestions")
        elif suggestion_result.used_fallback and narrative_result.used_fallback:
            diagnostics.append("fallbacks:both")

        return {
            "result_narration": narrative_result.narration,
            "result_event": mechanics_result.event,
            "result_next_scene": narrative_result.next_scene,
            "result_story_event": narrative_result.story_event,
            "result_suggested_actions": suggestion_result.actions,
            "pipeline_diagnostics": diagnostics,
        }


def invoke_master_pipeline(state: dict) -> dict:
    return MasterOrchestrator().invoke(state)
