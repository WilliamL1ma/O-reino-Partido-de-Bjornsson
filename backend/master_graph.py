from __future__ import annotations

import logging
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from master_state import MasterGraphState, MasterState, prepare_master_graph_state
from master_pipeline.mechanics_agent import MechanicsAgent
from master_pipeline.narrative_agent import NarrativeAgent
from master_pipeline.reviewers import build_narrative_fallback, build_suggestion_fallback, review_narration, review_suggestions
from master_pipeline.runtime import LLMStageInvoker, log_stage
from master_pipeline.suggestion_agent import SuggestionAgent
from narrative.authority import sanitize_suggested_actions


_MAX_NARRATIVE_REVISIONS = 1
_MAX_SUGGESTION_REVISIONS = 1


class _StageBundle:
    def __init__(
        self,
        *,
        mechanics_agent: MechanicsAgent,
        narrative_agent: NarrativeAgent,
        suggestion_agent: SuggestionAgent,
    ) -> None:
        self.mechanics_agent = mechanics_agent
        self.narrative_agent = narrative_agent
        self.suggestion_agent = suggestion_agent


def _parser_list(value: object) -> list:
    return list(value) if isinstance(value, list) else []


def _build_node_update(
    state: MasterGraphState,
    node_name: str,
    *,
    diagnostics: list[str] | None = None,
    **updates: object,
) -> MasterGraphState:
    payload: MasterGraphState = dict(updates)  # type: ignore[assignment]
    payload["execution_trace"] = [*state.get("execution_trace", []), node_name]
    if diagnostics:
        payload["pipeline_diagnostics"] = [*state.get("pipeline_diagnostics", []), *diagnostics]
    return payload


@lru_cache(maxsize=1)
def _get_stage_bundle() -> _StageBundle:
    invoker = LLMStageInvoker()
    return _StageBundle(
        mechanics_agent=MechanicsAgent(invoker),
        narrative_agent=NarrativeAgent(invoker),
        suggestion_agent=SuggestionAgent(invoker),
    )


def _prepare_state_node(state: MasterGraphState) -> MasterGraphState:
    normalized = prepare_master_graph_state(state)
    return _build_node_update(
        normalized,
        "prepare_state",
        mode=normalized["mode"],
        scene=normalized.get("scene", {}),
        scene_title=normalized.get("scene_title", ""),
        scene_lead=normalized.get("scene_lead", ""),
        current_scene=normalized.get("current_scene", ""),
        allowed_next_scenes=normalized.get("allowed_next_scenes", []),
        available_monsters=normalized.get("available_monsters", []),
        lore_packet=normalized.get("lore_packet", {}),
        character_state=normalized.get("character_state", {}),
        inventory=normalized.get("inventory", []),
        pending_event=normalized.get("pending_event"),
        context_hint=normalized.get("context_hint"),
        recent_reward=normalized.get("recent_reward"),
        persisted_authority=normalized.get("persisted_authority"),
        authoritative_state=normalized.get("authoritative_state", {}),
        recent_messages=normalized.get("recent_messages", []),
        player_message=normalized.get("player_message", ""),
        roll_resolution=normalized.get("roll_resolution", {}),
        fallback_actions=normalized.get("fallback_actions", []),
        mechanics_event=None,
        narrative_draft="",
        narrative_next_scene=None,
        narrative_story_event=None,
        narrative_review_valid=False,
        narrative_review_feedback="",
        narrative_revision_attempts=0,
        narrative_force_fallback=False,
        narrative_error="",
        narrative_used_fallback=False,
        approved_narration="",
        approved_next_scene=None,
        approved_story_event=None,
        suggestion_draft=[],
        suggestion_review_valid=False,
        suggestion_review_feedback="",
        suggestion_revision_attempts=0,
        suggestion_force_fallback=False,
        suggestion_error="",
        suggestion_used_fallback=False,
        suggestions_blocked=False,
        approved_suggested_actions=[],
        pipeline_diagnostics=_parser_list(normalized.get("pipeline_diagnostics")),
    )


def _mechanics_node(state: MasterGraphState) -> MasterGraphState:
    result = _get_stage_bundle().mechanics_agent.detect_event(state)
    return _build_node_update(
        state,
        "mechanics",
        diagnostics=result.diagnostics,
        mechanics_event=result.event,
    )


def _narrative_generate_node(state: MasterGraphState) -> MasterGraphState:
    try:
        narration, next_scene, story_event = _get_stage_bundle().narrative_agent.generate(
            state,
            state.get("mechanics_event"),
        )
        return _build_node_update(
            state,
            "narrative_generate",
            narrative_draft=narration,
            narrative_next_scene=next_scene,
            narrative_story_event=story_event,
            narrative_force_fallback=False,
            narrative_error="",
        )
    except Exception as error:  # pragma: no cover - exercised through tests via routing.
        log_stage(logging.WARNING, "narrative_failed", str(error), mode=str(state.get("mode", "turn")))
        return _build_node_update(
            state,
            "narrative_generate",
            diagnostics=["narrative:error"],
            narrative_draft="",
            narrative_next_scene=None,
            narrative_story_event=None,
            narrative_force_fallback=True,
            narrative_error=str(error),
        )


def _review_narrative_node(state: MasterGraphState) -> MasterGraphState:
    review = review_narration(
        narration=str(state.get("narrative_draft", "")),
        player_message=str(state.get("player_message", "")),
        recent_messages=state.get("recent_messages", []),
    )
    diagnostics: list[str] = []
    if not review.valid and int(state.get("narrative_revision_attempts", 0)) < _MAX_NARRATIVE_REVISIONS:
        diagnostics.append("narrative_review:failed")
        log_stage(logging.WARNING, "narrative_review_failed", review.feedback, mode=str(state.get("mode", "turn")))
    return _build_node_update(
        state,
        "narrative_review",
        diagnostics=diagnostics,
        narrative_review_valid=review.valid,
        narrative_review_feedback=review.feedback,
    )


def _approve_narrative_node(state: MasterGraphState) -> MasterGraphState:
    return _build_node_update(
        state,
        "narrative_approved",
        diagnostics=["narrative:ok"],
        approved_narration=str(state.get("narrative_draft", "")).strip(),
        approved_next_scene=state.get("narrative_next_scene"),
        approved_story_event=state.get("narrative_story_event"),
        narrative_used_fallback=False,
    )


def _revise_narrative_node(state: MasterGraphState) -> MasterGraphState:
    revise_attempt = int(state.get("narrative_revision_attempts", 0)) + 1
    try:
        narration, next_scene, story_event = _get_stage_bundle().narrative_agent.revise(
            state,
            str(state.get("narrative_draft", "")),
            state.get("narrative_next_scene"),
            state.get("narrative_story_event"),
            state.get("mechanics_event"),
            str(state.get("narrative_review_feedback", "")),
        )
        return _build_node_update(
            state,
            "narrative_revise",
            narrative_revision_attempts=revise_attempt,
            narrative_draft=narration,
            narrative_next_scene=next_scene,
            narrative_story_event=story_event,
            narrative_force_fallback=False,
            narrative_error="",
        )
    except Exception as error:  # pragma: no cover - exercised through tests via routing.
        log_stage(logging.WARNING, "narrative_failed", str(error), mode=str(state.get("mode", "turn")))
        return _build_node_update(
            state,
            "narrative_revise",
            diagnostics=["narrative:error"],
            narrative_revision_attempts=revise_attempt,
            narrative_force_fallback=True,
            narrative_error=str(error),
        )


def _narrative_fallback_node(state: MasterGraphState) -> MasterGraphState:
    feedback = str(state.get("narrative_review_feedback") or state.get("narrative_error") or "").strip()
    if feedback:
        log_stage(logging.WARNING, "narrative_fallback", feedback, mode=str(state.get("mode", "turn")))
    return _build_node_update(
        state,
        "narrative_fallback",
        diagnostics=["narrative_fallback"],
        approved_narration=build_narrative_fallback(state),
        approved_next_scene=None,
        approved_story_event=None,
        narrative_used_fallback=True,
    )


def _skip_suggestions_node(state: MasterGraphState) -> MasterGraphState:
    return _build_node_update(
        state,
        "suggestions_blocked",
        diagnostics=["suggestions:blocked_pending_event"],
        approved_suggested_actions=[],
        suggestions_blocked=True,
        suggestion_used_fallback=False,
    )


def _generate_suggestions_node(state: MasterGraphState) -> MasterGraphState:
    try:
        actions = _get_stage_bundle().suggestion_agent.generate(
            state,
            str(state.get("approved_narration", "")),
        )
        return _build_node_update(
            state,
            "suggestions_generate",
            suggestion_draft=actions,
            suggestion_force_fallback=False,
            suggestion_error="",
        )
    except Exception as error:  # pragma: no cover - exercised through tests via routing.
        log_stage(logging.WARNING, "suggestions_failed", str(error), mode=str(state.get("mode", "turn")))
        return _build_node_update(
            state,
            "suggestions_generate",
            diagnostics=["suggestions:error"],
            suggestion_draft=[],
            suggestion_force_fallback=True,
            suggestion_error=str(error),
        )


def _review_suggestions_node(state: MasterGraphState) -> MasterGraphState:
    reviewed_actions, review = review_suggestions(
        actions=state.get("suggestion_draft", []),
        narration=str(state.get("approved_narration", "")),
        authority=state.get("authoritative_state", {}),
        fallback_actions=state.get("fallback_actions", []),
    )
    diagnostics: list[str] = []
    if not review.valid and int(state.get("suggestion_revision_attempts", 0)) < _MAX_SUGGESTION_REVISIONS:
        diagnostics.append("suggestion_review:failed")
        log_stage(logging.WARNING, "suggestion_review_failed", review.feedback, mode=str(state.get("mode", "turn")))
    return _build_node_update(
        state,
        "suggestions_review",
        diagnostics=diagnostics,
        suggestion_draft=reviewed_actions,
        suggestion_review_valid=review.valid,
        suggestion_review_feedback=review.feedback,
    )


def _approve_suggestions_node(state: MasterGraphState) -> MasterGraphState:
    return _build_node_update(
        state,
        "suggestions_approved",
        diagnostics=["suggestions:ok"],
        approved_suggested_actions=sanitize_suggested_actions(
            state.get("suggestion_draft", []),
            state.get("authoritative_state", {}),
            state.get("fallback_actions", []),
        ),
        suggestion_used_fallback=False,
    )


def _revise_suggestions_node(state: MasterGraphState) -> MasterGraphState:
    revise_attempt = int(state.get("suggestion_revision_attempts", 0)) + 1
    try:
        actions = _get_stage_bundle().suggestion_agent.revise(
            state,
            str(state.get("approved_narration", "")),
            state.get("suggestion_draft", []),
            str(state.get("suggestion_review_feedback", "")),
        )
        return _build_node_update(
            state,
            "suggestions_revise",
            suggestion_revision_attempts=revise_attempt,
            suggestion_draft=actions,
            suggestion_force_fallback=False,
            suggestion_error="",
        )
    except Exception as error:  # pragma: no cover - exercised through tests via routing.
        log_stage(logging.WARNING, "suggestions_failed", str(error), mode=str(state.get("mode", "turn")))
        return _build_node_update(
            state,
            "suggestions_revise",
            diagnostics=["suggestions:error"],
            suggestion_revision_attempts=revise_attempt,
            suggestion_force_fallback=True,
            suggestion_error=str(error),
        )


def _suggestion_fallback_node(state: MasterGraphState) -> MasterGraphState:
    feedback = str(state.get("suggestion_review_feedback") or state.get("suggestion_error") or "").strip()
    if feedback:
        log_stage(logging.WARNING, "suggestion_fallback", feedback, mode=str(state.get("mode", "turn")))
    return _build_node_update(
        state,
        "suggestions_fallback",
        diagnostics=["suggestion_fallback"],
        approved_suggested_actions=build_suggestion_fallback(state, str(state.get("approved_narration", ""))),
        suggestion_used_fallback=True,
    )


def _finalize_node(state: MasterGraphState) -> MasterGraphState:
    narrative_review_valid = bool(state.get("narrative_review_valid"))
    suggestion_review_valid = bool(state.get("suggestion_review_valid"))
    narrative_used_fallback = bool(state.get("narrative_used_fallback"))
    suggestion_used_fallback = bool(state.get("suggestion_used_fallback"))
    blocked_suggestions = bool(state.get("suggestions_blocked"))

    narration = str(state.get("approved_narration", "")).strip()
    next_scene = state.get("approved_next_scene")
    story_event = state.get("approved_story_event")
    if not narration:
        if state.get("narrative_force_fallback") or not narrative_review_valid:
            narration = build_narrative_fallback(state)
            next_scene = None
            story_event = None
            narrative_used_fallback = True
        else:
            narration = str(state.get("narrative_draft", "")).strip()
            next_scene = state.get("narrative_next_scene")
            story_event = state.get("narrative_story_event")

    actions = state.get("approved_suggested_actions")
    if actions is None:
        actions = []
    if not isinstance(actions, list):
        actions = []
    if not actions and not blocked_suggestions:
        if state.get("suggestion_force_fallback") or not suggestion_review_valid:
            actions = build_suggestion_fallback(state, narration)
            suggestion_used_fallback = True
        else:
            actions = sanitize_suggested_actions(
                state.get("suggestion_draft", []),
                state.get("authoritative_state", {}),
                state.get("fallback_actions", []),
            )
    elif actions and not blocked_suggestions:
        actions = sanitize_suggested_actions(
            actions,
            state.get("authoritative_state", {}),
            state.get("fallback_actions", []),
        )

    diagnostics = list(state.get("pipeline_diagnostics", []))
    if narrative_used_fallback and not suggestion_used_fallback:
        diagnostics.append("fallbacks:only_narrative")
    elif suggestion_used_fallback and not narrative_used_fallback:
        diagnostics.append("fallbacks:only_suggestions")
    elif narrative_used_fallback and suggestion_used_fallback:
        diagnostics.append("fallbacks:both")

    return _build_node_update(
        state,
        "finalize",
        pipeline_diagnostics=diagnostics,
        result_narration=narration,
        result_event=state.get("mechanics_event"),
        result_next_scene=next_scene,
        result_story_event=story_event,
        result_suggested_actions=actions,
    )


def _route_review(state: dict, *, max_revisions: int = 2) -> str:
    if bool(state.get("review_valid")):
        return "finalize"
    return "revise" if int(state.get("revise_attempt", 0)) < max_revisions else "finalize"


def _route_after_narrative_generation(state: MasterGraphState) -> str:
    return "narrative_fallback" if state.get("narrative_force_fallback") else "narrative_review"


def _route_narrative_review(state: MasterGraphState) -> str:
    if state.get("narrative_review_valid"):
        return "narrative_approved"
    route = _route_review(
        {
            "review_valid": state.get("narrative_review_valid"),
            "revise_attempt": state.get("narrative_revision_attempts", 0),
        },
        max_revisions=_MAX_NARRATIVE_REVISIONS,
    )
    return "narrative_revise" if route == "revise" else "narrative_fallback"


def _route_after_narrative(state: MasterGraphState) -> str:
    mode = str(state.get("mode", "turn"))
    if mode == "turn" and (state.get("mechanics_event") is not None or state.get("approved_story_event") is not None):
        return "suggestions_blocked"
    return "suggestions_generate"


def _route_after_suggestion_generation(state: MasterGraphState) -> str:
    return "suggestions_fallback" if state.get("suggestion_force_fallback") else "suggestions_review"


def _route_suggestion_review(state: MasterGraphState) -> str:
    if state.get("suggestion_review_valid"):
        return "suggestions_approved"
    route = _route_review(
        {
            "review_valid": state.get("suggestion_review_valid"),
            "revise_attempt": state.get("suggestion_revision_attempts", 0),
        },
        max_revisions=_MAX_SUGGESTION_REVISIONS,
    )
    return "suggestions_revise" if route == "revise" else "suggestions_fallback"


@lru_cache(maxsize=1)
def get_master_graph():
    graph = StateGraph(MasterGraphState)
    graph.add_node("prepare_state", _prepare_state_node)
    graph.add_node("mechanics", _mechanics_node)
    graph.add_node("narrative_generate", _narrative_generate_node)
    graph.add_node("narrative_review", _review_narrative_node)
    graph.add_node("narrative_revise", _revise_narrative_node)
    graph.add_node("narrative_fallback", _narrative_fallback_node)
    graph.add_node("narrative_approved", _approve_narrative_node)
    graph.add_node("suggestions_blocked", _skip_suggestions_node)
    graph.add_node("suggestions_generate", _generate_suggestions_node)
    graph.add_node("suggestions_review", _review_suggestions_node)
    graph.add_node("suggestions_revise", _revise_suggestions_node)
    graph.add_node("suggestions_fallback", _suggestion_fallback_node)
    graph.add_node("suggestions_approved", _approve_suggestions_node)
    graph.add_node("finalize", _finalize_node)

    graph.add_edge(START, "prepare_state")
    graph.add_edge("prepare_state", "mechanics")
    graph.add_edge("mechanics", "narrative_generate")
    graph.add_conditional_edges(
        "narrative_generate",
        _route_after_narrative_generation,
        {
            "narrative_review": "narrative_review",
            "narrative_fallback": "narrative_fallback",
        },
    )
    graph.add_conditional_edges(
        "narrative_review",
        _route_narrative_review,
        {
            "narrative_approved": "narrative_approved",
            "narrative_revise": "narrative_revise",
            "narrative_fallback": "narrative_fallback",
        },
    )
    graph.add_edge("narrative_revise", "narrative_review")
    graph.add_conditional_edges(
        "narrative_approved",
        _route_after_narrative,
        {
            "suggestions_blocked": "suggestions_blocked",
            "suggestions_generate": "suggestions_generate",
        },
    )
    graph.add_conditional_edges(
        "narrative_fallback",
        _route_after_narrative,
        {
            "suggestions_blocked": "suggestions_blocked",
            "suggestions_generate": "suggestions_generate",
        },
    )
    graph.add_conditional_edges(
        "suggestions_generate",
        _route_after_suggestion_generation,
        {
            "suggestions_review": "suggestions_review",
            "suggestions_fallback": "suggestions_fallback",
        },
    )
    graph.add_conditional_edges(
        "suggestions_review",
        _route_suggestion_review,
        {
            "suggestions_approved": "suggestions_approved",
            "suggestions_revise": "suggestions_revise",
            "suggestions_fallback": "suggestions_fallback",
        },
    )
    graph.add_edge("suggestions_revise", "suggestions_review")
    graph.add_edge("suggestions_blocked", "finalize")
    graph.add_edge("suggestions_approved", "finalize")
    graph.add_edge("suggestions_fallback", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def invoke_master_graph(state: MasterState) -> dict:
    return get_master_graph().invoke(dict(state or {}))
