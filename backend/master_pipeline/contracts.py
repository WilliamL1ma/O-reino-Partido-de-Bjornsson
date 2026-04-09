from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MechanicsAgentResult:
    event: dict | None
    diagnostics: list[str] = field(default_factory=list)
