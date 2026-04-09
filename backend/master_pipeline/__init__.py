from __future__ import annotations

from .mechanics_agent import MechanicsAgent
from .narrative_agent import NarrativeAgent
from .suggestion_agent import SuggestionAgent

__all__ = [
    "MechanicsAgent",
    "NarrativeAgent",
    "SuggestionAgent",
    "MasterOrchestrator",
    "invoke_master_pipeline",
]


def invoke_master_pipeline(state: dict) -> dict:
    from master_graph import invoke_master_graph

    return invoke_master_graph(state)


def __getattr__(name: str):
    if name == "MasterOrchestrator":
        from .orchestrator import MasterOrchestrator

        return MasterOrchestrator
    raise AttributeError(name)
