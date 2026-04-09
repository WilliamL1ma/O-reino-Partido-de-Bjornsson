from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MechanicsAgentResult:
    event: dict | None
    diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NarrativeAgentResult:
    narration: str
    next_scene: str | None
    story_event: dict | None
    used_fallback: bool
    diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SuggestionAgentResult:
    actions: list[str]
    used_fallback: bool
    diagnostics: list[str] = field(default_factory=list)
