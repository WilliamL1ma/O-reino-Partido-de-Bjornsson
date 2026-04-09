from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any


DEFAULT_GROQ_MODEL = "qwen/qwen3-32b"
DEFAULT_GROQ_FAST_MODEL = "llama-3.1-8b-instant"
DEFAULT_GROQ_TIMEOUT_SECONDS = 25.0
DEFAULT_GROQ_MAX_TOKENS = 700


class LLMGatewayError(RuntimeError):
    pass


class LLMRateLimitError(LLMGatewayError):
    pass


@dataclass(frozen=True)
class GroqSettings:
    api_key: str
    model: str
    timeout: float
    max_tokens: int = DEFAULT_GROQ_MAX_TOKENS


def _parse_timeout(raw_value: str | None) -> float:
    try:
        timeout = float(raw_value or DEFAULT_GROQ_TIMEOUT_SECONDS)
    except (TypeError, ValueError):
        return DEFAULT_GROQ_TIMEOUT_SECONDS
    return timeout if timeout > 0 else DEFAULT_GROQ_TIMEOUT_SECONDS


def _parse_max_tokens(raw_value: str | None) -> int:
    try:
        max_tokens = int(raw_value or DEFAULT_GROQ_MAX_TOKENS)
    except (TypeError, ValueError):
        return DEFAULT_GROQ_MAX_TOKENS
    return max_tokens if max_tokens > 0 else DEFAULT_GROQ_MAX_TOKENS


def _normalize_stage(stage: str | None) -> str | None:
    normalized = (stage or "").strip().lower()
    if normalized in {"fast", "narrative"}:
        return normalized
    return None


def _resolve_stage_model(stage: str | None) -> str:
    stage_key = _normalize_stage(stage)
    if stage_key == "fast":
        return os.getenv("GROQ_MODEL_FAST", "").strip() or DEFAULT_GROQ_FAST_MODEL
    return os.getenv("GROQ_MODEL_NARRATIVE", "").strip() or os.getenv("GROQ_MODEL", "").strip() or DEFAULT_GROQ_MODEL


def _resolve_stage_timeout(stage: str | None) -> float:
    stage_key = _normalize_stage(stage)
    if stage_key == "fast":
        return _parse_timeout(os.getenv("GROQ_TIMEOUT_SECONDS_FAST") or os.getenv("GROQ_TIMEOUT_SECONDS"))
    return _parse_timeout(os.getenv("GROQ_TIMEOUT_SECONDS_NARRATIVE") or os.getenv("GROQ_TIMEOUT_SECONDS"))


def _resolve_stage_max_tokens(stage: str | None) -> int:
    stage_key = _normalize_stage(stage)
    if stage_key == "fast":
        return _parse_max_tokens(os.getenv("GROQ_MAX_TOKENS_FAST") or os.getenv("GROQ_MAX_TOKENS"))
    return _parse_max_tokens(os.getenv("GROQ_MAX_TOKENS_NARRATIVE") or os.getenv("GROQ_MAX_TOKENS"))


def load_groq_settings(*, stage: str | None = None) -> GroqSettings:
    return GroqSettings(
        api_key=os.getenv("GROQ_API_KEY", "").strip(),
        model=_resolve_stage_model(stage),
        timeout=_resolve_stage_timeout(stage),
        max_tokens=_resolve_stage_max_tokens(stage),
    )


def groq_is_configured() -> bool:
    return bool(load_groq_settings().api_key)


def require_groq_settings() -> GroqSettings:
    settings = load_groq_settings()
    if not settings.api_key:
        raise LLMGatewayError("GROQ_API_KEY não configurada.")
    return settings


def create_groq_client(settings: GroqSettings | None = None) -> Any:
    resolved_settings = settings or require_groq_settings()
    from groq import Groq

    return Groq(
        api_key=resolved_settings.api_key,
        timeout=resolved_settings.timeout,
    )


def _extract_retry_delay_seconds(error_text: str) -> float | None:
    match = re.search(r"try again in\s+([0-9]+(?:\.[0-9]+)?)\s*(ms|s)\b", error_text, flags=re.IGNORECASE)
    if not match:
        return None

    value = float(match.group(1))
    unit = match.group(2).lower()
    return value / 1000.0 if unit == "ms" else value


def _strip_reasoning_artifacts(content: str) -> str:
    cleaned = (content or "").strip()
    if not cleaned:
        return cleaned

    cleaned = re.sub(r"<think>[\s\S]*?</think>\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^\s*think\s*:\s*[\s\S]*?(?=(?:\{|\[|\"?[A-Za-zÀ-ÿ]))", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def format_groq_error(error: Exception) -> LLMGatewayError:
    error_name = type(error).__name__
    error_text = str(error)

    if error_name == "APIConnectionError":
        return LLMGatewayError(f"Falha ao conectar na Groq: {error}")

    if error_name == "APIStatusError":
        detail = getattr(error, "response", None)
        status_code = getattr(detail, "status_code", "desconhecido")
        body = getattr(detail, "text", "") or ""
        body_text = body[:240] if body else error_text[:240]
        if str(status_code) == "429" or "rate limit" in error_text.lower() or "rate_limit_exceeded" in error_text.lower():
            retry_after = _extract_retry_delay_seconds(error_text) or _extract_retry_delay_seconds(body_text)
            message = "Limite de uso da Groq atingido no momento. Tente novamente em alguns instantes."
            if retry_after is not None:
                wait_ms = max(1, round(retry_after * 1000))
                message = f"{message} Aguarde cerca de {wait_ms} ms."
            return LLMRateLimitError(message)
        return LLMGatewayError(f"Groq retornou erro HTTP {status_code}: {body_text}") 

    if "rate limit" in error_text.lower() or "rate_limit_exceeded" in error_text.lower():
        retry_after = _extract_retry_delay_seconds(error_text)
        message = "Limite de uso da Groq atingido no momento. Tente novamente em alguns instantes."
        if retry_after is not None:
            wait_ms = max(1, round(retry_after * 1000))
            message = f"{message} Aguarde cerca de {wait_ms} ms."
        return LLMRateLimitError(message)

    return LLMGatewayError(f"Falha inesperada ao consultar a Groq: {error}")


def call_groq_messages(
    messages: list[dict],
    *,
    temperature: float = 0.7,
    json_mode: bool = False,
    settings: GroqSettings | None = None,
    client: Any | None = None,
) -> str:
    resolved_settings = settings or require_groq_settings()
    resolved_client = client or create_groq_client(resolved_settings)
    completion_kwargs = {
        "model": resolved_settings.model,
        "messages": messages,
        "temperature": temperature,
        "max_completion_tokens": resolved_settings.max_tokens,
    }
    if json_mode:
        completion_kwargs["response_format"] = {"type": "json_object"}

    try:
        response = resolved_client.chat.completions.create(**completion_kwargs)
    except Exception as error:
        raise format_groq_error(error) from error

    try:
        return _strip_reasoning_artifacts(response.choices[0].message.content)
    except (KeyError, IndexError, AttributeError) as error:
        raise LLMGatewayError("Resposta inválida recebida da Groq.") from error


def build_groq_chat_model(*, temperature: float, settings: GroqSettings | None = None) -> Any:
    resolved_settings = settings or require_groq_settings()
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=resolved_settings.model,
        api_key=resolved_settings.api_key,
        timeout=resolved_settings.timeout,
        temperature=temperature,
        max_tokens=resolved_settings.max_tokens,
    )
