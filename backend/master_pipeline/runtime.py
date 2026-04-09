from __future__ import annotations

import logging
import time

from narrative.llm_gateway import LLMRateLimitError, call_groq_messages, format_groq_error, load_groq_settings


LOGGER = logging.getLogger("master_pipeline")
_STAGE_MODEL_PROFILES = {
    "mechanics": "fast",
    "suggestions": "fast",
    "narrative": "narrative",
}


def log_stage(level: int, stage: str, detail: str, *, mode: str) -> None:
    LOGGER.log(level, "[master_pipeline][%s][%s] %s", mode, stage, detail)


class LLMStageInvoker:
    def invoke(self, messages: list[object], *, temperature: float, attempts: int = 2, stage: str | None = None) -> str:
        settings = load_groq_settings(stage=_STAGE_MODEL_PROFILES.get((stage or "").strip().lower()))
        last_error = None
        for attempt in range(attempts):
            try:
                return call_groq_messages(messages, temperature=temperature, json_mode=False, settings=settings)
            except Exception as error:
                mapped_error = format_groq_error(error)
                last_error = mapped_error
                if isinstance(mapped_error, LLMRateLimitError) and attempt + 1 < attempts:
                    time.sleep(0.4)
                    continue
                raise mapped_error from error
        raise last_error or RuntimeError("Falha ao invocar o modelo do mestre.")
