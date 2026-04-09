from __future__ import annotations

import logging

from .contracts import MechanicsAgentResult
from .parsers import parse_mechanics_event
from .prompts import build_mechanics_messages
from .runtime import LLMStageInvoker, log_stage


class MechanicsAgent:
    def __init__(self, invoker: LLMStageInvoker | None = None) -> None:
        self._invoker = invoker or LLMStageInvoker()

    def detect_event(self, state: dict) -> MechanicsAgentResult:
        mode = str(state.get("mode", "turn"))
        if mode != "turn" or not str(state.get("player_message", "")).strip():
            return MechanicsAgentResult(event=None, diagnostics=["mechanics:skipped"])

        try:
            raw = self._invoker.invoke(build_mechanics_messages(state), temperature=0.15, stage="mechanics")
            event = parse_mechanics_event(raw, state.get("available_monsters", []))
            return MechanicsAgentResult(
                event=event,
                diagnostics=[f"mechanics:ok:{'event' if event else 'none'}"],
            )
        except Exception as error:
            log_stage(logging.WARNING, "mechanics_failed", str(error), mode=mode)
            return MechanicsAgentResult(event=None, diagnostics=["mechanics:error"])
